"""
SAARTHI Production Entry Point
==============================

Full production-grade voice assistant with:
- Hardened audio pipeline (correct .audio access)
- Comprehensive validation (RMS, duration, normalization)
- Strict intent routing (one path per input)
- Enhanced student assistance
- Direct knowledge answers (no planner for facts)
- Professional UX feedback
- Thread-safe operations
- Comprehensive error recovery

USAGE:
    python production_main.py

REQUIREMENTS:
    - Windows 10/11
    - Python 3.10+
    - Microphone access
    - keyboard package (for Ctrl+Space hotkey)
    - pyttsx3 or win32com (for TTS)

Author: Principal AI Systems Engineer
Version: 1.0.0
"""

import sys
import os
import time
import signal
import logging
import threading
from typing import Optional, Callable
from queue import Queue, Empty
from dataclasses import dataclass

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("SAARTHI.Production")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ProductionConfig:
    """Production configuration."""
    # Audio
    sample_rate: int = 16000
    min_duration: float = 0.5
    max_duration: float = 30.0
    silence_threshold: float = 0.01
    
    # Hotkey
    push_to_talk_key: str = "ctrl+space"
    
    # STT
    stt_confidence_threshold: float = 0.5
    stt_retry_count: int = 2
    
    # TTS
    enable_tts: bool = True
    tts_rate: int = 180
    
    # Routing
    routing_confidence_threshold: float = 0.7
    
    # LLM (optional)
    enable_llm: bool = False
    llm_endpoint: str = "http://localhost:11434/api/generate"
    llm_model: str = "llama3.1"  # Ollama model: llama3.1, phi3, mistral, etc.


# =============================================================================
# LLM CALLBACK (Optional)
# =============================================================================

def create_llm_callback(config: ProductionConfig) -> Optional[Callable]:
    """
    Create LLM callback using local Ollama instance.
    
    Returns:
        Callable that takes a prompt and returns response text, or None if LLM disabled
    """
    if not config.enable_llm:
        return None
    
    from saarthi_executor.openai_config import create_ollama_llm_callback
    
    try:
        logger.info(f"Initializing Ollama LLM with model: {config.llm_model}")
        return create_ollama_llm_callback(
            model=config.llm_model,
            temperature=0.7,
        )
    except RuntimeError as e:
        logger.error(f"Ollama setup failed: {e}")
        logger.info("Continuing without LLM support")
        return None


# =============================================================================
# PRODUCTION VOICE SYSTEM
# =============================================================================

class ProductionVoiceSystem:
    """
    Production-grade voice system integrating:
    - ProductionVoicePipeline (hardened audio)
    - ProductionAssistant (strict routing)
    - FeedbackManager (UX feedback)
    """
    
    def __init__(self, config: ProductionConfig):
        self.config = config
        
        # Components (initialized lazily)
        self._pipeline = None
        self._assistant = None
        self._feedback = None
        self._stt = None
        
        # State
        self._running = False
        self._shutdown_event = threading.Event()
        
        # Message queue for thread communication
        self._message_queue: Queue = Queue()
    
    def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("Initializing SAARTHI Production Voice System...")
        
        try:
            # Initialize feedback first (for status updates)
            from saarthi_executor.feedback_ux import get_feedback_manager
            self._feedback = get_feedback_manager(
                enable_tts=self.config.enable_tts,
                enable_notifications=True,
            )
            
            logger.info("✓ Feedback system initialized")
            
            # Initialize STT
            from saarthi_executor.voice.stt_whisper import LocalWhisperSTT
            self._stt = LocalWhisperSTT()
            if self._stt.initialize():
                logger.info("✓ STT (Whisper) initialized")
            else:
                logger.warning("⚠ STT initialization had issues, continuing anyway")
            
            # Initialize production pipeline
            from saarthi_executor.production_pipeline import ProductionVoicePipeline
            self._pipeline = ProductionVoicePipeline(
                stt=self._stt,
                on_transcription=self._on_transcription,
                on_error=self._on_error,
                on_status=self._on_status,
            )
            if self._pipeline.initialize():
                logger.info("✓ Voice pipeline initialized")
            else:
                logger.error("✗ Voice pipeline failed to initialize")
                return False
            
            # Initialize production assistant
            from saarthi_executor.production_router import create_production_assistant
            llm_callback = create_llm_callback(self.config)
            self._assistant = create_production_assistant(
                llm_callback=llm_callback,
                enable_tts=False,  # We handle TTS via feedback manager
            )
            logger.info("✓ Production assistant initialized")
            
            self._running = True
            logger.info("✓ SAARTHI Production Voice System ready!")
            self._feedback.speak("SAARTHI ready. Hold Control plus Space to speak.")
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _on_transcription(self, text: str, confidence: float):
        """Handle transcription from pipeline."""
        logger.info(f"Transcription: '{text}' (confidence: {confidence:.2f})")
        
        if confidence < self.config.stt_confidence_threshold:
            self._feedback.error_didnt_catch()
            return
        
        # Process through assistant
        try:
            response = self._assistant.process(text)
            
            # Provide feedback
            if response.speak and response.text:
                self._feedback.speak(response.text)
            
            if response.action_executed:
                self._feedback.action_complete(response.text)
            elif response.needs_clarification:
                # Already spoken via assistant
                pass
            
            logger.info(f"Response: {response.text[:100]}...")
            
        except Exception as e:
            logger.error(f"Assistant processing failed: {e}")
            self._feedback.error_didnt_catch()
    
    def _on_error(self, error: str):
        """Handle pipeline errors."""
        logger.error(f"Pipeline error: {error}")
        
        if "quiet" in error.lower() or "silent" in error.lower():
            self._feedback.error_too_quiet()
        elif "short" in error.lower():
            self._feedback.error_too_short()
        else:
            self._feedback.error_audio()
    
    def _on_status(self, status: str):
        """Handle pipeline status updates."""
        logger.debug(f"Pipeline status: {status}")
        
        if status == "listening":
            self._feedback.listening_started()
        elif status == "processing":
            self._feedback.processing()
    
    def run(self):
        """Run the voice system (blocking)."""
        if not self._running:
            if not self.initialize():
                return
        
        logger.info("SAARTHI Production Voice System running. Press Ctrl+C to exit.")
        
        try:
            # Wait for shutdown signal
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(timeout=0.5)
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Shutdown the voice system."""
        logger.info("Shutting down SAARTHI Production Voice System...")
        
        self._running = False
        self._shutdown_event.set()
        
        # Cleanup components
        if self._feedback:
            self._feedback.goodbye()
            time.sleep(0.5)  # Let goodbye play
            self._feedback.cleanup()
        
        if self._pipeline:
            self._pipeline.shutdown()
        
        if self._assistant:
            self._assistant.cleanup()
        
        logger.info("SAARTHI Production Voice System shutdown complete.")


# =============================================================================
# MINIMAL TRAY (optional)
# =============================================================================

def create_minimal_tray() -> Optional[object]:
    """Create minimal status tray if pystray available."""
    try:
        import pystray
        from PIL import Image, ImageDraw
        
        def create_icon():
            """Create a simple status icon."""
            img = Image.new('RGB', (64, 64), color=(30, 30, 30))
            draw = ImageDraw.Draw(img)
            # Green circle for "ready"
            draw.ellipse([16, 16, 48, 48], fill=(0, 200, 0))
            return img
        
        def on_exit(icon, item):
            icon.stop()
        
        menu = pystray.Menu(
            pystray.MenuItem("Exit", on_exit),
        )
        
        icon = pystray.Icon(
            "SAARTHI",
            create_icon(),
            "SAARTHI - Ready",
            menu,
        )
        
        return icon
        
    except ImportError:
        logger.info("pystray not available, running without tray icon")
        return None


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Main entry point."""
    print("=" * 60)
    print("SAARTHI Production Voice Assistant")
    print("=" * 60)
    print()
    
    print("Controls:")
    print("  • Hold Ctrl+Space to speak")
    print("  • Release to process")
    print("  • Ctrl+C to exit")
    print()
    
    # Configuration
    config = ProductionConfig(
        enable_tts=True,
        enable_llm=False,  # Set to True to enable LLM
        llm_model="llama3.1",
    )
    
    # Show LLM status and check Ollama
    if config.enable_llm:
        print(f"LLM Model: {config.llm_model}")
        print("Checking Ollama availability...")
        
        from saarthi_executor.openai_config import check_ollama
        is_available, message = check_ollama(config.llm_model)
        print(message)
        
        if not is_available:
            print()
            print("Continuing without LLM support...")
            config.enable_llm = False
        print()
    else:
        print("LLM: Disabled (knowledge base and patterns only)")
        print("  Set enable_llm=True in code to enable Ollama LLM")
        print()
    
    # Create and run system
    system = ProductionVoiceSystem(config)
    
    # Handle SIGINT gracefully
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        system.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run (blocking)
    system.run()


if __name__ == "__main__":
    main()
