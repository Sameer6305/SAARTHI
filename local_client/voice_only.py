#!/usr/bin/env python3
"""
SAARTHI Voice-Only Assistant
=============================

VOICE-ONLY, FAST, RELIABLE, PRIVACY-SAFE

USAGE:
    python voice_only.py

INTERACTION:
    Hold Ctrl+Space to speak
    Release to process
    
NO TEXT INPUT - Voice is the ONLY interaction method.

ARCHITECTURE:
    ┌─────────────────────────────────────────────────────────────┐
    │                    VOICE-ONLY FLOW                          │
    │                                                             │
    │  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────┐  │
    │  │ Ctrl+   │───▶│ RECORD   │───▶│TRANSCRIBE│───▶│PROCESS│  │
    │  │ Space   │    │ (mic)    │    │ (Whisper)│    │(planner)│  │
    │  └─────────┘    └──────────┘    └──────────┘    └───────┘  │
    │       │                                              │      │
    │       │              ┌───────────┐                   │      │
    │       └──────────────│  RESPOND  │◀──────────────────┘      │
    │                      │  (TTS)    │                          │
    │                      └───────────┘                          │
    └─────────────────────────────────────────────────────────────┘

SECURITY:
    - Mic ONLY during Ctrl+Space hold
    - No background listening
    - No audio stored on disk
    - Permission gate for actions
"""

import sys
import os
import logging
import signal
import threading
import time
from pathlib import Path
from typing import Optional

# Setup path
sys.path.insert(0, str(Path(__file__).parent))


# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging(verbose: bool = False):
    """Setup clean logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    class VoiceFormatter(logging.Formatter):
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
    handler.setFormatter(VoiceFormatter())
    
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(level)
    
    # Suppress noisy libraries
    for lib in ["urllib3", "requests", "httpx", "whisper", "torch", "numba"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

logger = logging.getLogger("saarthi.voice_only")


# =============================================================================
# VOICE-ONLY ASSISTANT
# =============================================================================

class VoiceOnlyAssistant:
    """
    Voice-only SAARTHI assistant.
    
    INTERACTION: Ctrl+Space (hold to speak)
    NO TEXT INPUT.
    """
    
    def __init__(self):
        self._running = False
        self._enabled = False
        
        # Components (lazy loaded)
        self._tray = None
        self._hotkey = None
        self._pipeline = None
        self._assistant = None
        self._security = None
        
        # State
        self._is_recording = False
        
        logger.info("VoiceOnlyAssistant created")
    
    def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("🚀 SAARTHI Voice-Only Initializing...")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            # 1. Initialize security logger
            from saarthi_executor.voice_security import get_security_logger
            self._security = get_security_logger()
            logger.info("✓ Security logger ready")
            
            # 2. Initialize integrated assistant (planner + TTS)
            from saarthi_executor.integrated_assistant import IntegratedAssistant
            self._assistant = IntegratedAssistant(
                enable_tts=True,
                llm_callback=self._llm_callback,
            )
            self._assistant.initialize()
            logger.info("✓ Assistant initialized")
            
            # 3. Initialize voice pipeline
            from saarthi_executor.hardened_pipeline import HardenedVoicePipeline, PipelineState
            self._pipeline = HardenedVoicePipeline(
                on_state_change=self._on_pipeline_state_change,
                on_result=self._on_pipeline_result,
                on_error=self._on_pipeline_error,
            )
            
            if not self._pipeline.initialize():
                logger.warning("Voice pipeline init failed - will retry on enable")
            else:
                logger.info("✓ Voice pipeline ready")
                # Pre-load STT model
                self._pipeline.preload_stt_model()
            
            # 4. Initialize hotkey system
            from saarthi_executor.hotkey_voice import HoldToTalkHotkey
            self._hotkey = HoldToTalkHotkey(
                on_recording_start=self._on_recording_start,
                on_recording_stop=self._on_recording_stop,
                on_error=self._on_hotkey_error,
                enabled_check=lambda: self._enabled,
            )
            logger.info("✓ Hotkey system ready")
            
            # 5. Initialize minimal tray
            from saarthi_executor.minimal_tray import MinimalTray, AssistantState
            self._tray = MinimalTray(
                on_enable=self._on_enable,
                on_disable=self._on_disable,
                on_exit=self._on_exit,
                initial_state=AssistantState.DISABLED,
            )
            logger.info("✓ System tray ready")
            
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            logger.info("✅ SAARTHI Voice-Only Ready!")
            logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run(self) -> None:
        """Run the voice-only assistant."""
        self._running = True
        
        print()
        print("╔════════════════════════════════════════════════════════════╗")
        print("║           SAARTHI - Voice-Only Assistant                   ║")
        print("╠════════════════════════════════════════════════════════════╣")
        print("║                                                            ║")
        print("║  1. Right-click tray icon → Enable Assistant               ║")
        print("║  2. HOLD Ctrl+Space to speak                               ║")
        print("║  3. RELEASE to process your command                        ║")
        print("║                                                            ║")
        print("║  NO TEXT INPUT - Voice only!                               ║")
        print("║                                                            ║")
        print("║  Press Ctrl+C to exit                                      ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        
        # Start tray
        self._tray.start_detached()
        
        # Keep main thread alive
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        
        self.shutdown()
    
    def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("🛑 Shutting down...")
        
        self._running = False
        self._enabled = False
        
        # Stop hotkey
        if self._hotkey:
            self._hotkey.stop()
        
        # Stop pipeline
        if self._pipeline:
            self._pipeline.cleanup()
        
        # Stop tray
        if self._tray:
            self._tray.stop()
        
        # Cleanup assistant
        if self._assistant:
            self._assistant.cleanup()
        
        logger.info("👋 Goodbye!")
    
    # ==================== CALLBACKS ====================
    
    def _on_enable(self) -> bool:
        """Handle Enable Assistant."""
        logger.info("Enabling assistant...")
        
        try:
            # Initialize pipeline if needed
            if self._pipeline and not self._pipeline._stt:
                self._pipeline.initialize()
            
            # Start hotkey listening
            if not self._hotkey.start():
                logger.error("Failed to start hotkey system")
                return False
            
            self._enabled = True
            
            if self._security:
                self._security.assistant_enabled()
            
            logger.info("✓ Assistant enabled - Hold Ctrl+Space to speak")
            return True
            
        except Exception as e:
            logger.error(f"Enable failed: {e}")
            return False
    
    def _on_disable(self) -> None:
        """Handle Disable Assistant."""
        logger.info("Disabling assistant...")
        
        self._enabled = False
        
        # Cancel any recording
        if self._pipeline and self._pipeline.is_busy:
            self._pipeline.cancel()
        
        # Stop hotkey
        if self._hotkey:
            self._hotkey.stop()
        
        if self._security:
            self._security.assistant_disabled()
        
        logger.info("✓ Assistant disabled")
    
    def _on_exit(self) -> None:
        """Handle Exit."""
        self._running = False
    
    def _on_recording_start(self) -> bool:
        """Handle hotkey press - start recording."""
        if not self._enabled:
            return False
        
        if self._pipeline and self._pipeline.is_busy:
            logger.warning("Pipeline busy - ignoring")
            return False
        
        logger.info("🎤 Recording... (keep holding Ctrl+Space)")
        
        # Update tray
        if self._tray:
            from saarthi_executor.minimal_tray import AssistantState
            self._tray.set_state(AssistantState.RECORDING)
        
        # Security log
        if self._security:
            self._security.hotkey_pressed()
            self._security.recording_started()
        
        # Start recording
        if self._pipeline:
            return self._pipeline.start_recording()
        
        return False
    
    def _on_recording_stop(self) -> Optional[str]:
        """Handle hotkey release - stop recording and process."""
        logger.info("🔄 Processing...")
        
        # Update tray
        if self._tray:
            from saarthi_executor.minimal_tray import AssistantState
            self._tray.set_state(AssistantState.PROCESSING)
        
        # Stop recording
        if self._pipeline:
            self._pipeline.stop_recording()
            
            # Wait for result (blocking, but brief)
            result = self._pipeline.get_result(timeout=30.0)
            
            if result and result.success and result.text:
                # Security log
                if self._security:
                    self._security.recording_stopped(result.duration_seconds)
                    self._security.transcription_complete(
                        len(result.text),
                        result.confidence,
                        True
                    )
                
                # Process through assistant
                self._process_voice_input(result.text)
                
                return result.text
            else:
                logger.info("No speech detected")
                
                if self._security:
                    self._security.recording_stopped(result.duration_seconds if result else 0)
                    self._security.transcription_complete(0, 0, False)
        
        # Return to enabled state
        if self._tray and self._enabled:
            from saarthi_executor.minimal_tray import AssistantState
            self._tray.set_state(AssistantState.ENABLED)
        
        return None
    
    def _on_hotkey_error(self, error: str) -> None:
        """Handle hotkey error."""
        logger.error(f"Hotkey error: {error}")
        
        if self._security:
            self._security.error("hotkey", error)
        
        if self._tray:
            self._tray.show_notification("Error", error)
    
    def _on_pipeline_state_change(self, state) -> None:
        """Handle pipeline state changes."""
        from saarthi_executor.hardened_pipeline import PipelineState
        from saarthi_executor.minimal_tray import AssistantState
        
        if not self._tray:
            return
        
        if state == PipelineState.IDLE and self._enabled:
            self._tray.set_state(AssistantState.ENABLED)
        elif state == PipelineState.RECORDING:
            self._tray.set_state(AssistantState.RECORDING)
        elif state == PipelineState.PROCESSING:
            self._tray.set_state(AssistantState.PROCESSING)
    
    def _on_pipeline_result(self, result) -> None:
        """Handle pipeline result (async callback)."""
        # This is called from background thread
        # Main processing happens in _on_recording_stop
        pass
    
    def _on_pipeline_error(self, error: str) -> None:
        """Handle pipeline error."""
        logger.error(f"Pipeline error: {error}")
        
        if self._security:
            self._security.error("pipeline", error)
            self._security.pipeline_reset(error)
        
        if self._tray:
            self._tray.show_notification("Voice Error", error)
    
    def _process_voice_input(self, text: str) -> None:
        """Process transcribed voice input through the assistant."""
        if not text or not text.strip():
            return
        
        text = text.strip()
        
        logger.info(f"📥 Voice: \"{text}\"")
        
        try:
            # Process through integrated assistant
            # This handles: planner, tools, TTS response
            response = self._assistant.process(text)
            
            # Security log
            if self._security:
                self._security.command_processed(
                    "voice",
                    response.action_type if response.action_executed else None
                )
                
                if response.action_executed:
                    self._security.action_executed(
                        response.action_type or "unknown",
                        True
                    )
            
            # Log response
            if response.text:
                logger.info(f"📤 SAARTHI: \"{response.text[:60]}...\"" 
                           if len(response.text) > 60 else f"📤 SAARTHI: \"{response.text}\"")
            
            # TTS is handled inside assistant.process()
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            
            if self._security:
                self._security.error("processing", str(e))
        
        finally:
            # Return to enabled state
            if self._tray and self._enabled:
                from saarthi_executor.minimal_tray import AssistantState
                self._tray.set_state(AssistantState.ENABLED)
    
    def _llm_callback(self, prompt: str) -> str:
        """Optional local LLM callback."""
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


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SAARTHI Voice-Only Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Hold Ctrl+Space to speak, release to process.
NO TEXT INPUT - Voice only!

Examples:
  python voice_only.py           # Normal mode
  python voice_only.py -v        # Verbose logging
        """
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose)
    
    # Create and run assistant
    assistant = VoiceOnlyAssistant()
    
    if not assistant.initialize():
        logger.error("Failed to initialize. Exiting.")
        sys.exit(1)
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Signal received, shutting down...")
        assistant.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run
    assistant.run()


if __name__ == "__main__":
    main()
