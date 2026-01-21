#!/usr/bin/env python3
"""
SAARTHI Main Controller
========================

THE ENTRY POINT - Makes the assistant actually work.

USAGE:
    python main.py              # CLI mode (for testing)
    python main.py --tray       # Tray mode (background)
    python main.py --voice      # Voice mode with hotkey

CONTROL FLOW:
    ┌─────────────────────────────────────────────────────┐
    │                    MAIN LOOP                        │
    │                                                     │
    │  ┌─────────┐    ┌──────────┐    ┌──────────────┐   │
    │  │  INPUT  │───▶│ PROCESS  │───▶│   RESPOND    │   │
    │  │ (voice/ │    │ (planner │    │ (speak/act)  │   │
    │  │  text)  │    │  +tools) │    │              │   │
    │  └─────────┘    └──────────┘    └──────────────┘   │
    │       ▲                               │            │
    │       └───────────────────────────────┘            │
    │                  (loop)                            │
    └─────────────────────────────────────────────────────┘

STATES:
    SLEEPING  - Not listening, minimal resources
    ACTIVE    - Ready for input
    LISTENING - Recording voice
    PROCESSING - Thinking/planning
    EXECUTING - Running action
"""

import sys
import os
import logging
import argparse
import threading
import time
from pathlib import Path
from typing import Optional
from enum import Enum
from datetime import datetime

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(verbose: bool = False):
    """Configure logging with clear, readable output."""
    level = logging.DEBUG if verbose else logging.INFO
    
    # Custom formatter with emojis for clarity
    class SaarthiFormatter(logging.Formatter):
        FORMATS = {
            logging.DEBUG: "   [DEBUG] %(message)s",
            logging.INFO: "   %(message)s",
            logging.WARNING: "⚠  [WARN] %(message)s",
            logging.ERROR: "❌ [ERROR] %(message)s",
        }
        
        def format(self, record):
            fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
            formatter = logging.Formatter(fmt)
            return formatter.format(record)
    
    handler = logging.StreamHandler()
    handler.setFormatter(SaarthiFormatter())
    
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
    
    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger("saarthi")


# =============================================================================
# AGENT STATE
# =============================================================================

class AgentState(Enum):
    """Agent states."""
    SLEEPING = "sleeping"
    ACTIVE = "active"
    LISTENING = "listening"
    PROCESSING = "processing"
    EXECUTING = "executing"


# =============================================================================
# MAIN CONTROLLER
# =============================================================================

class SaarthiController:
    """
    Main controller for SAARTHI.
    
    This is the BRAIN that coordinates everything:
    - Input handling (voice/text)
    - Processing (planner)
    - Output (TTS/action)
    """
    
    def __init__(self, enable_tts: bool = True, enable_voice: bool = False):
        self.state = AgentState.SLEEPING
        self._running = False
        
        # Components (lazy loaded)
        self._assistant = None
        self._voice_activation = None
        
        # Config
        self._enable_tts = enable_tts
        self._enable_voice = enable_voice
        
        # Stats
        self._stats = {
            "started_at": None,
            "commands_processed": 0,
            "actions_executed": 0,
        }
        
        logger.info("Controller created")
    
    def initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns True if ready to use.
        """
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("🚀 SAARTHI Initializing...")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            # Import and create assistant
            from saarthi_executor.integrated_assistant import IntegratedAssistant
            
            self._assistant = IntegratedAssistant(
                enable_tts=self._enable_tts,
                llm_callback=self._llm_callback,
            )
            self._assistant.initialize()
            logger.info("✓ Assistant initialized")
            
            # Voice activation (optional)
            if self._enable_voice:
                try:
                    from saarthi_executor.voice.activation_methods import (
                        HotkeyActivation
                    )
                    self._voice_activation = HotkeyActivation(
                        hotkey="f5",
                        on_start=self._on_voice_start,
                        on_stop=self._on_voice_stop,
                        on_cancel=self._on_voice_cancel,
                    )
                    if self._voice_activation.start():
                        logger.info("✓ Voice activation ready (Press F5)")
                    else:
                        logger.warning("Voice activation failed")
                        self._voice_activation = None
                except ImportError:
                    logger.warning("Voice activation unavailable (install keyboard)")
                    self._voice_activation = None
            
            self._stats["started_at"] = datetime.now()
            self.state = AgentState.ACTIVE
            
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info("✅ SAARTHI Ready!")
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    def _llm_callback(self, prompt: str) -> str:
        """Optional local LLM callback (Ollama)."""
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "phi3",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 256, "temperature": 0.3},
                },
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json().get("response", "")
        except:
            pass
        return ""
    
    def process_input(self, text: str) -> str:
        """
        Process user input and return response.
        
        This is THE MAIN FUNCTION that handles all input.
        
        Flow:
        1. Log input
        2. Set state to PROCESSING
        3. Pass to assistant (planner)
        4. Get response
        5. If action needed, handle confirmation
        6. Speak response (if TTS enabled)
        7. Return to ACTIVE
        
        Args:
            text: User input (from voice or text)
            
        Returns:
            Response text
        """
        if not text or not text.strip():
            return ""
        
        text = text.strip()
        self._stats["commands_processed"] += 1
        
        # Log input
        logger.info(f"📥 Input: \"{text}\"")
        
        # Set state
        prev_state = self.state
        self.state = AgentState.PROCESSING
        logger.info("🔄 Processing...")
        
        try:
            # Process through assistant
            response = self._assistant.process(text)
            
            # Log result
            if response.action_executed:
                self._stats["actions_executed"] += 1
                logger.info(f"⚡ Action: {response.action_type}")
            
            if response.needs_clarification:
                logger.info("❓ Needs clarification")
            
            # Log response
            logger.info(f"📤 Response: \"{response.text[:60]}...\"" if len(response.text) > 60 else f"📤 Response: \"{response.text}\"")
            
            # TTS is handled inside assistant.process()
            
            return response.text
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return "Sorry, something went wrong."
            
        finally:
            # Return to active
            self.state = AgentState.ACTIVE
    
    def _on_voice_start(self):
        """Called when voice recording starts."""
        self.state = AgentState.LISTENING
        logger.info("🎤 Listening... (speak now)")
    
    def _on_voice_stop(self):
        """Called when voice recording stops."""
        logger.info("🎤 Processing voice...")
        # In full implementation, this would:
        # 1. Get audio from recorder
        # 2. Transcribe with Whisper
        # 3. Call process_input(transcribed_text)
        # For now, we're using CLI
    
    def _on_voice_cancel(self):
        """Called when voice is cancelled."""
        logger.info("🎤 Cancelled")
        self.state = AgentState.ACTIVE
    
    def sleep(self):
        """Enter sleep mode."""
        self.state = AgentState.SLEEPING
        logger.info("😴 Sleeping...")
    
    def wake(self):
        """Wake from sleep."""
        self.state = AgentState.ACTIVE
        logger.info("👋 Awake and ready!")
    
    def shutdown(self):
        """Clean shutdown."""
        logger.info("🛑 Shutting down...")
        
        self._running = False
        self.state = AgentState.SLEEPING
        
        if self._assistant:
            self._assistant.cleanup()
        
        if self._voice_activation:
            self._voice_activation.stop()
        
        logger.info("👋 Goodbye!")
    
    def get_status(self) -> dict:
        """Get current status."""
        uptime = None
        if self._stats["started_at"]:
            uptime = str(datetime.now() - self._stats["started_at"]).split(".")[0]
        
        return {
            "state": self.state.value,
            "uptime": uptime,
            "commands": self._stats["commands_processed"],
            "actions": self._stats["actions_executed"],
            "tts": self._enable_tts,
            "voice": self._enable_voice,
        }


# =============================================================================
# CLI MODE (For Testing)
# =============================================================================

def run_cli(controller: SaarthiController):
    """
    Run in CLI mode for testing.
    
    This is the simplest way to test the assistant.
    """
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║             SAARTHI - CLI Mode                             ║")
    print("╠════════════════════════════════════════════════════════════╣")
    print("║  Type a command and press Enter.                          ║")
    print("║                                                            ║")
    print("║  Examples:                                                 ║")
    print("║    > open youtube                                          ║")
    print("║    > explain binary search                                 ║")
    print("║    > search for python tutorials                           ║")
    print("║    > hi                                                    ║")
    print("║                                                            ║")
    print("║  Commands:                                                 ║")
    print("║    /status  - Show status                                  ║")
    print("║    /sleep   - Enter sleep mode                             ║")
    print("║    /wake    - Wake up                                      ║")
    print("║    /quit    - Exit                                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    while True:
        try:
            # Show prompt based on state
            if controller.state == AgentState.SLEEPING:
                prompt = "(sleeping) > "
            else:
                prompt = "You > "
            
            # Get input
            user_input = input(prompt).strip()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower()
                
                if cmd == "/quit" or cmd == "/exit":
                    break
                    
                elif cmd == "/status":
                    status = controller.get_status()
                    print(f"\n   State: {status['state']}")
                    print(f"   Uptime: {status['uptime']}")
                    print(f"   Commands: {status['commands']}")
                    print(f"   Actions: {status['actions']}")
                    print()
                    continue
                    
                elif cmd == "/sleep":
                    controller.sleep()
                    continue
                    
                elif cmd == "/wake":
                    controller.wake()
                    continue
                    
                elif cmd == "/help":
                    print("\n   Commands: /status, /sleep, /wake, /quit\n")
                    continue
                    
                else:
                    print(f"   Unknown command: {cmd}")
                    continue
            
            # Check if sleeping
            if controller.state == AgentState.SLEEPING:
                print("   (Type /wake to wake up)")
                continue
            
            # Process input
            response = controller.process_input(user_input)
            
            # Print response
            print(f"\n   SAARTHI: {response}\n")
            
        except KeyboardInterrupt:
            print("\n")
            break
        except EOFError:
            break
    
    controller.shutdown()


# =============================================================================
# VOICE MODE
# =============================================================================

def run_voice(controller: SaarthiController):
    """
    Run in voice mode with hotkey activation.
    
    Press F5 to start/stop voice.
    """
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║             SAARTHI - Voice Mode                           ║")
    print("╠════════════════════════════════════════════════════════════╣")
    print("║  Press F5 to start speaking                                ║")
    print("║  Press F5 again to stop and process                        ║")
    print("║  Press Escape to cancel                                    ║")
    print("║  Press Ctrl+C to quit                                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Also allow text input while waiting
    print("   (You can also type commands here)")
    print()
    
    # Run CLI in parallel
    run_cli(controller)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_tray():
    """
    Run in TRAY mode with system tray icon.
    
    This gives you:
    - System tray icon in taskbar
    - Right-click menu with options
    - "Send Command" for text input
    - "Voice Command" for voice input (push-to-talk)
    """
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║             SAARTHI - Tray Mode                            ║")
    print("╠════════════════════════════════════════════════════════════╣")
    print("║  Look for the SAARTHI icon in your system tray (taskbar)   ║")
    print("║                                                            ║")
    print("║  Right-click the icon to:                                  ║")
    print("║    • Wake Up / Go to Sleep                                 ║")
    print("║    • Send Command (type a command)                         ║")
    print("║    • Voice Command (speak a command)                       ║")
    print("║    • Exit                                                  ║")
    print("║                                                            ║")
    print("║  Press Ctrl+C here to exit                                 ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Import and run the existing tray-based executor
    from saarthi_executor.executor import SaarthiExecutor
    from saarthi_executor.logging_config import setup_logging as setup_executor_logging
    
    # Setup logging
    log_file = Path.home() / ".saarthi" / "executor.log"
    setup_executor_logging(log_level="INFO", log_file=log_file)
    
    # Create executor (disable backend connection to avoid errors)
    executor = SaarthiExecutor(
        use_mock_cloud=False,
        use_real_backend=False,  # Don't require backend server
        enable_voice=True,
    )
    
    try:
        executor.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        executor.stop()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SAARTHI - Your Local Study Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                 # CLI mode (for testing)
  python main.py --tray          # Tray mode (system tray icon)
  python main.py --no-tts        # CLI without speech
  python main.py --voice         # Enable F5 hotkey for voice
  python main.py -v              # Verbose logging
        """
    )
    
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Run with system tray icon (right-click for menu)",
    )
    parser.add_argument(
        "--no-tts",
        action="store_true",
        help="Disable text-to-speech",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable voice input with F5 hotkey",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    
    args = parser.parse_args()
    
    # TRAY MODE - Use the full executor with tray icon
    if args.tray:
        run_tray()
        return
    
    # CLI/VOICE MODE - Use the simple controller
    setup_logging(verbose=args.verbose)
    
    # Create controller
    controller = SaarthiController(
        enable_tts=not args.no_tts,
        enable_voice=args.voice,
    )
    
    # Initialize
    if not controller.initialize():
        logger.error("Failed to initialize. Exiting.")
        sys.exit(1)
    
    # Run
    try:
        if args.voice:
            run_voice(controller)
        else:
            run_cli(controller)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        controller.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
