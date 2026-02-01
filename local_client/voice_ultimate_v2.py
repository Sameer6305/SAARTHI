#!/usr/bin/env python3
"""
SAARTHI Voice Ultimate v2.0
============================

PRODUCTION READY with robust architecture:
- Modular design with clear separation of concerns
- Robust VAD with state machine and adaptive threshold
- Safe TTS with URL/path blocking
- Intelligent intent parsing
- Universal knowledge routing
- Fault-tolerant execution

USAGE:
    python voice_ultimate_v2.py

Press SPACE BAR to speak, Q to quit.
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import whisper
import time
import json
import winsound
import msvcrt
import threading
import logging
import webbrowser
from collections import deque
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Import modular components
from saarthi_executor.audio_capture import AudioCapture, AudioCaptureConfig, create_audio_capture
from saarthi_executor.robust_vad import VADConfig, VADState
from saarthi_executor.tts_policy import SafeTTS, TTSPolicy, SpeechCategory, create_safe_tts
from saarthi_executor.intent_parser import IntentParser, IntentType, ParsedIntent, parse_intent
from saarthi_executor.knowledge_router import KnowledgeRouter, get_answer, KnowledgeResult
from saarthi_executor.integrated_assistant import create_assistant, SimpleTTS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SaarthiConfig:
    """Main configuration for SAARTHI."""
    # Audio
    sample_rate: int = 16000
    silence_duration: float = 1.5
    max_recording: float = 30.0
    min_speech_duration: float = 0.3
    
    # VAD
    silence_threshold: float = 0.01
    adaptive_threshold: bool = True
    
    # Whisper
    whisper_model: str = "tiny"
    whisper_language: str = "en"
    
    # TTS
    enable_tts: bool = True
    tts_speak_answers: bool = True
    tts_speak_greetings: bool = True
    tts_speak_errors: bool = True
    tts_block_urls: bool = True
    
    # Behavior
    audio_feedback: bool = True
    save_history: bool = True
    auto_confirm: bool = True
    
    # Timeouts
    knowledge_timeout: float = 3.0
    
    # Paths
    history_file: Path = Path(__file__).parent / "command_history.json"


# Global config
CONFIG = SaarthiConfig()


# =============================================================================
# CORE COMPONENTS
# =============================================================================

class WhisperSTT:
    """Whisper Speech-to-Text wrapper."""
    
    def __init__(self, model_name: str = "tiny", language: str = "en"):
        self.model_name = model_name
        self.language = language
        self._model = None
        self._lock = threading.Lock()
    
    def initialize(self) -> bool:
        """Load Whisper model."""
        try:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self._model = whisper.load_model(self.model_name)
            logger.info("Whisper model loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            return False
    
    def transcribe(self, audio: np.ndarray) -> Optional[str]:
        """
        Transcribe audio to text.
        
        Args:
            audio: Audio data as numpy array (float32, 16kHz)
            
        Returns:
            Transcribed text or None
        """
        if self._model is None:
            logger.error("Whisper model not initialized")
            return None
        
        if audio is None or len(audio) < CONFIG.sample_rate * 0.3:
            logger.warning("Audio too short for transcription")
            return None
        
        with self._lock:
            try:
                start = time.time()
                
                result = self._model.transcribe(
                    audio,
                    language=self.language,
                    fp16=False,
                    verbose=False,
                    temperature=0.0,
                    best_of=1,
                    beam_size=1,
                )
                
                text = result['text'].strip()
                elapsed = time.time() - start
                
                logger.info(f"Transcribed in {elapsed:.2f}s: {text[:50]}...")
                return text if text else None
                
            except Exception as e:
                logger.error(f"Transcription failed: {e}")
                return None


class CommandHistory:
    """Manages command history persistence."""
    
    def __init__(self, filepath: Path, max_entries: int = 100):
        self.filepath = filepath
        self.max_entries = max_entries
        self._history: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
    
    def load(self):
        """Load history from file."""
        if self.filepath.exists():
            try:
                with open(self.filepath) as f:
                    data = json.load(f)
                    self._history.extend(data[-self.max_entries:])
                logger.info(f"Loaded {len(self._history)} history entries")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
    
    def save(self):
        """Save history to file."""
        with self._lock:
            try:
                with open(self.filepath, 'w') as f:
                    json.dump(list(self._history), f, indent=2)
                logger.info(f"Saved {len(self._history)} history entries")
            except Exception as e:
                logger.warning(f"Failed to save history: {e}")
    
    def add(self, text: str, intent_type: str, success: bool):
        """Add entry to history."""
        with self._lock:
            self._history.append({
                "text": text,
                "intent": intent_type,
                "success": success,
                "timestamp": time.time(),
            })


class ActionExecutor:
    """Execute parsed intents safely."""
    
    def __init__(self, assistant):
        self._assistant = assistant
        self._stats = {
            "actions_executed": 0,
            "actions_failed": 0,
        }
    
    def execute(self, intent: ParsedIntent) -> Dict[str, Any]:
        """
        Execute a parsed intent.
        
        Returns:
            Dict with 'success', 'text', 'speak', 'category'
        """
        try:
            if intent.intent_type == IntentType.OPEN_URL:
                return self._open_url(intent)
            
            elif intent.intent_type == IntentType.OPEN_APP:
                return self._open_app(intent)
            
            elif intent.intent_type == IntentType.SEARCH_WEB:
                return self._search_web(intent)
            
            elif intent.intent_type == IntentType.PLAY_MEDIA:
                return self._play_media(intent)
            
            elif intent.intent_type == IntentType.GREETING:
                return self._greeting()
            
            elif intent.intent_type == IntentType.THANKS:
                return self._thanks()
            
            elif intent.intent_type == IntentType.QUESTION:
                return self._answer_question(intent)
            
            elif intent.intent_type == IntentType.EXPLAIN:
                return self._explain(intent)
            
            elif intent.intent_type == IntentType.STATUS:
                return self._status()
            
            elif intent.intent_type == IntentType.MULTI_STEP:
                return self._multi_step(intent)
            
            else:
                return self._fallback(intent)
        
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            self._stats["actions_failed"] += 1
            return {
                "success": False,
                "text": f"Sorry, something went wrong: {str(e)[:50]}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _open_url(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Open a URL."""
        url = intent.entities.get("url", "")
        site = intent.entities.get("site", "website")
        
        if not url:
            return {
                "success": False,
                "text": "I need a URL to open.",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
        
        try:
            webbrowser.open(url)
            self._stats["actions_executed"] += 1
            
            return {
                "success": True,
                "text": f"Opening {site}",  # No URL in text!
                "speak": False,  # Silent for actions
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        except Exception as e:
            return {
                "success": False,
                "text": f"Failed to open {site}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _open_app(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Open an application."""
        import subprocess
        
        exe = intent.entities.get("executable", "")
        app = intent.entities.get("app", exe)
        
        if not exe:
            return {
                "success": False,
                "text": "I need an application to open.",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
        
        try:
            subprocess.Popen(
                ["start", "", exe],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._stats["actions_executed"] += 1
            
            return {
                "success": True,
                "text": f"Opening {app}",
                "speak": False,  # Silent for actions
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        except Exception as e:
            return {
                "success": False,
                "text": f"Failed to open {app}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _search_web(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Search the web."""
        import urllib.parse
        
        query = intent.entities.get("query", "")
        
        if not query:
            return {
                "success": False,
                "text": "What would you like me to search for?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        try:
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            self._stats["actions_executed"] += 1
            
            return {
                "success": True,
                "text": f"Searching for {query}",
                "speak": False,  # Silent
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        except Exception as e:
            return {
                "success": False,
                "text": "Failed to search",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _play_media(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Play media on YouTube."""
        query = intent.entities.get("query", "")
        url = intent.entities.get("url", "")
        
        if not url and query:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        
        if url:
            try:
                webbrowser.open(url)
                self._stats["actions_executed"] += 1
                
                return {
                    "success": True,
                    "text": f"Playing {query}",
                    "speak": False,  # Silent
                    "category": SpeechCategory.ACTION_CONFIRM,
                }
            except Exception as e:
                pass
        
        return {
            "success": False,
            "text": "I couldn't play that",
            "speak": True,
            "category": SpeechCategory.ERROR,
        }
    
    def _greeting(self) -> Dict[str, Any]:
        """Handle greeting."""
        import random
        responses = [
            "Hello! How can I help you?",
            "Hey! What can I do for you?",
            "Hi there! Ready to assist.",
        ]
        return {
            "success": True,
            "text": random.choice(responses),
            "speak": True,
            "category": SpeechCategory.GREETING,
        }
    
    def _thanks(self) -> Dict[str, Any]:
        """Handle thanks."""
        import random
        responses = [
            "You're welcome!",
            "Happy to help!",
            "Anytime!",
        ]
        return {
            "success": True,
            "text": random.choice(responses),
            "speak": True,
            "category": SpeechCategory.THANKS,
        }
    
    def _answer_question(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Answer a question."""
        topic = intent.entities.get("topic", intent.raw_text)
        
        result = get_answer(topic, timeout=CONFIG.knowledge_timeout)
        
        return {
            "success": result.confidence > 0.5,
            "text": result.answer,
            "speak": True,
            "category": SpeechCategory.ANSWER,
            "source": result.source,
        }
    
    def _explain(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Explain a topic."""
        topic = intent.entities.get("topic", "")
        
        if not topic:
            return {
                "success": False,
                "text": "What topic would you like me to explain?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        result = get_answer(topic, timeout=CONFIG.knowledge_timeout)
        
        return {
            "success": result.confidence > 0.5,
            "text": result.answer,
            "speak": True,
            "category": SpeechCategory.EXPLANATION,
            "source": result.source,
        }
    
    def _status(self) -> Dict[str, Any]:
        """Return status."""
        return {
            "success": True,
            "text": f"I'm running well. Actions executed: {self._stats['actions_executed']}.",
            "speak": True,
            "category": SpeechCategory.STATUS,
        }
    
    def _multi_step(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Execute multi-step command."""
        if not intent.sub_intents:
            return self._fallback(intent)
        
        results = []
        all_success = True
        
        print(f"⚡ Multi-step command ({len(intent.sub_intents)} steps)...")
        
        for i, sub_intent in enumerate(intent.sub_intents, 1):
            print(f"   Step {i}: {sub_intent.normalized_text}")
            result = self.execute(sub_intent)
            results.append(result)
            
            if not result["success"]:
                all_success = False
            
            print(f"   {'✅' if result['success'] else '❌'} {result['text'][:50]}")
            time.sleep(0.5)
        
        return {
            "success": all_success,
            "text": f"Completed {len(results)} steps",
            "speak": False,  # Don't speak multi-step summary
            "category": SpeechCategory.ACTION_CONFIRM,
            "sub_results": results,
        }
    
    def _fallback(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Fallback for unknown intents."""
        # Try the integrated assistant
        try:
            response = self._assistant.process(intent.raw_text)
            
            # Auto-confirm if needed
            if "should i" in response.text.lower():
                response = self._assistant.process("yes")
            
            return {
                "success": response.action_executed or not response.error,
                "text": response.text,
                "speak": response.speak,
                "category": SpeechCategory.ANSWER if response.speak else SpeechCategory.ACTION_CONFIRM,
            }
        except Exception as e:
            logger.error(f"Assistant fallback failed: {e}")
        
        return {
            "success": False,
            "text": "I'm not sure how to help with that. Try asking me to open a website, explain a topic, or search the web.",
            "speak": True,
            "category": SpeechCategory.ERROR,
        }


# =============================================================================
# MAIN ASSISTANT
# =============================================================================

class SaarthiVoiceAssistant:
    """
    Main voice assistant orchestrator.
    
    Coordinates all components:
    - Audio capture with robust VAD
    - Whisper STT
    - Intent parsing
    - Action execution
    - Safe TTS
    """
    
    def __init__(self, config: SaarthiConfig):
        self.config = config
        
        # Components (initialized later)
        self._audio_capture: Optional[AudioCapture] = None
        self._stt: Optional[WhisperSTT] = None
        self._intent_parser: Optional[IntentParser] = None
        self._executor: Optional[ActionExecutor] = None
        self._tts: Optional[SafeTTS] = None
        self._history: Optional[CommandHistory] = None
        self._assistant = None
        
        # State
        self._initialized = False
        self._running = False
    
    def initialize(self) -> bool:
        """Initialize all components."""
        print()
        print("=" * 75)
        print("🎯 SAARTHI VOICE ULTIMATE v2.0 - Production Ready")
        print("=" * 75)
        print()
        
        try:
            # 1. Audio capture with robust VAD
            print("🎤 Initializing audio capture...")
            vad_config = VADConfig(
                sample_rate=self.config.sample_rate,
                silence_duration=self.config.silence_duration,
                max_recording_duration=self.config.max_recording,
                min_speech_duration=self.config.min_speech_duration,
                initial_threshold=self.config.silence_threshold,
            )
            audio_config = AudioCaptureConfig(
                sample_rate=self.config.sample_rate,
            )
            self._audio_capture = AudioCapture(audio_config, vad_config)
            print("   ✓ Audio capture ready")
            
            # 2. Whisper STT
            print("🔊 Loading Whisper model...")
            self._stt = WhisperSTT(
                model_name=self.config.whisper_model,
                language=self.config.whisper_language,
            )
            if not self._stt.initialize():
                raise RuntimeError("Failed to initialize Whisper")
            print("   ✓ Whisper ready")
            
            # 3. Intent parser
            print("🧠 Initializing intent parser...")
            self._intent_parser = IntentParser()
            print("   ✓ Intent parser ready")
            
            # 4. Integrated assistant (for fallback)
            print("🤖 Creating assistant...")
            self._assistant = create_assistant(enable_tts=False)  # We handle TTS separately
            print("   ✓ Assistant ready")
            
            # 5. Action executor
            print("⚡ Initializing action executor...")
            self._executor = ActionExecutor(self._assistant)
            print("   ✓ Action executor ready")
            
            # 6. Safe TTS
            if self.config.enable_tts:
                print("🔈 Initializing TTS...")
                base_tts = SimpleTTS()
                base_tts.initialize()
                self._tts = create_safe_tts(base_tts)
                self._tts.initialize()
                print("   ✓ TTS ready (with URL blocking)")
            
            # 7. Command history
            print("📝 Loading command history...")
            self._history = CommandHistory(self.config.history_file)
            self._history.load()
            print("   ✓ History loaded")
            
            self._initialized = True
            
            print()
            print("=" * 75)
            print("✅ ALL SYSTEMS READY!")
            print("=" * 75)
            print()
            print("HOW TO USE:")
            print("  1. Press SPACE BAR to start listening")
            print("  2. Speak your command clearly")
            print("  3. It automatically stops when you finish speaking")
            print("  4. Command executes instantly (no confirmation)")
            print()
            print("COMMANDS TO TRY:")
            print("  • 'open youtube'")
            print("  • 'play lofi music'")
            print("  • 'search for python tutorials'")
            print("  • 'explain binary search'")
            print("  • 'what is machine learning'")
            print("  • 'open calculator'")
            print()
            print("Press 'Q' to quit")
            print("=" * 75)
            print()
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            print(f"❌ Initialization failed: {e}")
            return False
    
    def _play_beep(self, frequency: int, duration: int):
        """Play a beep sound in background."""
        if self.config.audio_feedback:
            threading.Thread(
                target=lambda: winsound.Beep(frequency, duration),
                daemon=True
            ).start()
    
    def _on_speech_start(self):
        """Callback when speech starts."""
        logger.debug("Speech detected")
    
    def _on_speech_end(self):
        """Callback when speech ends."""
        logger.debug("Speech ended")
    
    def handle_voice_session(self):
        """Handle one complete voice session."""
        print("\n" + "─" * 75)
        
        try:
            # 1. Record with VAD
            self._play_beep(1000, 100)  # Start beep
            print("🎙️  LISTENING... (speak now, will auto-stop)")
            
            audio = self._audio_capture.record_with_vad(
                on_speech_start=self._on_speech_start,
                on_speech_end=self._on_speech_end,
            )
            
            self._play_beep(800, 100)  # Stop beep
            
            if audio is None:
                print("❌ No audio captured")
                return
            
            duration = len(audio) / self.config.sample_rate
            print(f"   ✓ Recorded {duration:.1f}s")
            
            # 2. Transcribe
            print("🔄 Transcribing...")
            text = self._stt.transcribe(audio)
            
            if not text:
                print("❌ No speech detected")
                return
            
            print(f"📝 You said: \"{text}\"")
            
            # 3. Parse intent
            intent = self._intent_parser.parse(text)
            logger.info(f"Intent: {intent.intent_type.value} (conf: {intent.confidence:.2f})")
            
            # 4. Execute
            if intent.intent_type == IntentType.QUESTION or intent.intent_type == IntentType.EXPLAIN:
                print("💡 Finding answer...")
            else:
                print("⚡ Executing...")
            
            result = self._executor.execute(intent)
            
            # 5. Output
            print(f"💬 SAARTHI: {result['text']}")
            
            if result.get("source"):
                print(f"   📚 Source: {result['source']}")
            
            # 6. TTS (with policy enforcement)
            if self._tts and result.get("speak", False):
                category = result.get("category", SpeechCategory.UNKNOWN)
                self._tts.speak(result["text"], category)
            
            # 7. Save history
            if self._history:
                self._history.add(
                    text=text,
                    intent_type=intent.intent_type.value,
                    success=result.get("success", False),
                )
            
        except Exception as e:
            logger.error(f"Session error: {e}")
            print(f"❌ Error: {e}")
        
        print("─" * 75)
        print("Press SPACE to speak again, Q to quit...")
        print()
    
    def run(self):
        """Main run loop."""
        if not self._initialized:
            if not self.initialize():
                return
        
        self._running = True
        print("🎯 Ready! Press SPACE BAR to start speaking...")
        print()
        
        try:
            while self._running:
                # Check for keypress
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    
                    if key == ' ':  # Space bar
                        self.handle_voice_session()
                    
                    elif key == 'q':  # Quit
                        print("\n👋 Goodbye!")
                        break
                
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        self._running = False
        
        if self._history:
            self._history.save()
            print("✓ Command history saved")
        
        if self._tts:
            self._tts.stop()
        
        logger.info("SAARTHI cleaned up")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    config = SaarthiConfig()
    assistant = SaarthiVoiceAssistant(config)
    assistant.run()


if __name__ == "__main__":
    main()
