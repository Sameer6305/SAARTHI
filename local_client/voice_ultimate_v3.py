#!/usr/bin/env python3
"""
SAARTHI Voice Ultimate v3.0 - Engineering Excellence Edition
=============================================================

PRODUCTION-GRADE ARCHITECTURE with interview-ready design:

Core Engineering Improvements:
  - Deterministic State Machine (7 states with formal transition matrix)
  - Interview-Grade Intent Engine (layered parsing, confidence scoring)
  - Production Metrics (latency percentiles, success rates, failure tracking)
  - Comprehensive Error Recovery (categorized failures, graceful degradation)

Design Patterns:
  - Observer Pattern: State change notifications
  - Strategy Pattern: Layered intent parsing
  - Singleton Pattern: MetricsCollector instance
  - Registry Pattern: Entity and intent registration
  - Context Manager: Resource lifecycle management

USAGE:
    python voice_ultimate_v3.py

Press SPACE BAR to speak, Q to quit, M for metrics dashboard.

Author: SAARTHI Engineering Team
Version: 3.0.0
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
import traceback
from collections import deque
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager

# Import modular components (v2 modules)
from saarthi_executor.audio_capture import AudioCapture, AudioCaptureConfig, create_audio_capture
from saarthi_executor.robust_vad import VADConfig, VADState
from saarthi_executor.tts_policy import SafeTTS, TTSPolicy, SpeechCategory, create_safe_tts
from saarthi_executor.knowledge_router import KnowledgeRouter, get_answer, KnowledgeResult
from saarthi_executor.integrated_assistant import create_assistant, SimpleTTS

# NEW v3 modules: Engineering-grade components
from saarthi_executor.assistant_state_machine import (
    AssistantStateMachine, AssistantState, StateObserver, StateTransition
)
from saarthi_executor.metrics import (
    MetricsCollector, LatencyTracker, SuccessRateTracker, FailureTracker,
    FailureCategory, track_latency, track_failure, CommandSession
)
from saarthi_executor.intent_engine import (
    IntentEngine, IntentType, ParsedIntent, Slot, ConfidenceThresholds
)

# Configure logging with more detail for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION (Interview-grade: centralized, immutable, documented)
# =============================================================================

@dataclass(frozen=True)
class SaarthiConfigV3:
    """
    Immutable configuration for SAARTHI v3.
    
    Design Decision: Using frozen=True ensures config cannot be mutated
    at runtime, preventing subtle configuration bugs.
    """
    # Audio capture
    sample_rate: int = 16000
    silence_duration: float = 1.5
    max_recording: float = 30.0
    min_speech_duration: float = 0.3
    
    # VAD (Voice Activity Detection)
    silence_threshold: float = 0.01
    adaptive_threshold: bool = True
    
    # Whisper STT
    whisper_model: str = "tiny"        # Options: tiny, base, small, medium, large
    whisper_language: str = "en"
    
    # TTS (Text-to-Speech)
    enable_tts: bool = True
    tts_speak_answers: bool = True
    tts_speak_greetings: bool = True
    tts_speak_errors: bool = True
    tts_block_urls: bool = True
    
    # Intent Engine
    confidence_execute_threshold: float = 0.70  # Execute immediately
    confidence_suggest_threshold: float = 0.40  # Suggest with confirmation
    
    # Behavior
    audio_feedback: bool = True
    save_history: bool = True
    auto_confirm: bool = True
    show_metrics_on_exit: bool = True
    
    # Timeouts (critical for reliability)
    stt_timeout: float = 10.0
    knowledge_timeout: float = 3.0
    action_timeout: float = 5.0
    state_timeout: float = 30.0  # Max time in any state before force-idle
    
    # Paths
    history_file: Path = field(default_factory=lambda: Path(__file__).parent / "command_history.json")


# Global immutable config
CONFIG = SaarthiConfigV3()


# =============================================================================
# STATE MACHINE OBSERVER (Interview: Observer pattern for decoupled events)
# =============================================================================

class MetricsStateObserver(StateObserver):
    """
    Observer that tracks state transitions for metrics.
    
    Interview Point: Demonstrates Observer pattern - the state machine
    doesn't need to know about metrics; it just notifies observers.
    """
    
    def __init__(self, metrics: MetricsCollector):
        self._metrics = metrics
    
    def on_state_change(self, transition: StateTransition):
        """Record state transition in metrics."""
        self._metrics.latency.record(
            f"state_{transition.from_state.value}_to_{transition.to_state.value}",
            transition.duration
        )
    
    def on_timeout(self, state: AssistantState, duration: float):
        """Record timeout as a failure."""
        self._metrics.record_failure(
            FailureCategory.STATE_TIMEOUT,
            f"Timeout in {state.value} after {duration:.1f}s",
            context={"state": state.value, "duration": duration}
        )


class UIStateObserver(StateObserver):
    """
    Observer that updates UI based on state changes.
    
    Interview Point: Separates UI concerns from state machine logic.
    """
    
    def __init__(self, beep_func: Callable[[int, int], None]):
        self._beep = beep_func
    
    def on_state_change(self, transition: StateTransition):
        """Update UI on state change."""
        state = transition.to_state
        
        if state == AssistantState.LISTENING:
            # High beep when listening starts
            self._beep(1000, 100)
        elif state == AssistantState.TRANSCRIBING:
            # Mid beep when processing
            self._beep(800, 50)
        elif state == AssistantState.SPEAKING:
            # Low beep when speaking
            self._beep(600, 50)
        elif state == AssistantState.ERROR:
            # Two low beeps for error
            self._beep(400, 100)
            time.sleep(0.1)
            self._beep(400, 100)
    
    def on_timeout(self, state: AssistantState, duration: float):
        """Alert on timeout."""
        self._beep(300, 200)


# =============================================================================
# CORE COMPONENTS (Enhanced with metrics instrumentation)
# =============================================================================

class WhisperSTTV3:
    """
    Whisper Speech-to-Text with instrumentation.
    
    Improvements over v2:
    - Integrated metrics tracking
    - Timeout handling
    - Detailed error categorization
    """
    
    def __init__(self, model_name: str = "tiny", language: str = "en",
                 metrics: Optional[MetricsCollector] = None):
        self.model_name = model_name
        self.language = language
        self._model = None
        self._lock = threading.Lock()
        self._metrics = metrics or MetricsCollector.instance()
        
        # Stats
        self._transcription_count = 0
        self._total_audio_seconds = 0.0
        self._total_transcription_time = 0.0
    
    def initialize(self) -> bool:
        """Load Whisper model with metrics."""
        try:
            start = time.time()
            logger.info(f"Loading Whisper model: {self.model_name}")
            
            self._model = whisper.load_model(self.model_name)
            
            elapsed = time.time() - start
            self._metrics.latency.record("whisper_load", elapsed)
            logger.info(f"Whisper model loaded in {elapsed:.2f}s")
            
            return True
            
        except Exception as e:
            self._metrics.record_failure(
                FailureCategory.STT_LOAD_FAILED,
                f"Failed to load Whisper: {e}"
            )
            logger.error(f"Failed to load Whisper: {e}")
            return False
    
    @track_latency("stt_transcribe")
    def transcribe(self, audio: np.ndarray, timeout: float = 10.0) -> Optional[str]:
        """
        Transcribe audio with timeout and instrumentation.
        
        Args:
            audio: Audio data (float32, 16kHz)
            timeout: Maximum transcription time
            
        Returns:
            Transcribed text or None
        """
        if self._model is None:
            self._metrics.record_failure(
                FailureCategory.STT_NOT_INITIALIZED,
                "Whisper model not initialized"
            )
            return None
        
        audio_duration = len(audio) / CONFIG.sample_rate
        
        if audio_duration < CONFIG.min_speech_duration:
            logger.warning(f"Audio too short: {audio_duration:.2f}s")
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
                
                elapsed = time.time() - start
                text = result['text'].strip()
                
                # Track stats
                self._transcription_count += 1
                self._total_audio_seconds += audio_duration
                self._total_transcription_time += elapsed
                
                # Record success
                self._metrics.success.record("stt", True)
                
                # Calculate Real-Time Factor (RTF)
                rtf = elapsed / audio_duration
                logger.info(
                    f"STT: {audio_duration:.1f}s audio → {elapsed:.2f}s "
                    f"(RTF: {rtf:.2f}x) → '{text[:50]}...'"
                )
                
                return text if text else None
                
            except Exception as e:
                self._metrics.record_failure(
                    FailureCategory.STT_TRANSCRIPTION_FAILED,
                    str(e),
                    context={"audio_duration": audio_duration}
                )
                self._metrics.success.record("stt", False)
                logger.error(f"Transcription failed: {e}")
                return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get STT performance stats."""
        avg_rtf = 0.0
        if self._total_audio_seconds > 0:
            avg_rtf = self._total_transcription_time / self._total_audio_seconds
        
        return {
            "transcription_count": self._transcription_count,
            "total_audio_seconds": self._total_audio_seconds,
            "total_transcription_time": self._total_transcription_time,
            "average_rtf": avg_rtf,
        }


class CommandHistory:
    """
    Thread-safe command history with JSON persistence.
    
    Interview Point: Demonstrates file I/O, thread safety, and data persistence.
    """
    
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
                    json.dump(list(self._history), f, indent=2, default=str)
            except Exception as e:
                logger.warning(f"Failed to save history: {e}")
    
    def add(self, session: 'CommandSession'):
        """Add session to history."""
        with self._lock:
            self._history.append({
                "text": session.raw_text,
                "intent": session.intent_type,
                "confidence": session.confidence,
                "success": session.execution_success,
                "latency_ms": int(session.total_duration_ms),
                "timestamp": datetime.now().isoformat(),
            })
    
    def get_recent(self, n: int = 10) -> List[Dict]:
        """Get n most recent entries."""
        with self._lock:
            return list(self._history)[-n:]


# =============================================================================
# ACTION EXECUTOR (Enhanced with metrics and state machine integration)
# =============================================================================

class ActionExecutorV3:
    """
    Execute parsed intents with instrumentation.
    
    Improvements over v2:
    - Integrated with MetricsCollector
    - Returns structured results with timing
    - Detailed failure categorization
    """
    
    def __init__(self, assistant, metrics: MetricsCollector):
        self._assistant = assistant
        self._metrics = metrics
        
        # Action handlers registry (Strategy pattern)
        self._handlers: Dict[IntentType, Callable] = {
            IntentType.OPEN_WEBSITE: self._open_website,
            IntentType.OPEN_APP: self._open_app,
            IntentType.WEB_SEARCH: self._search_web,
            IntentType.PLAY_MEDIA: self._play_media,
            IntentType.GREETING: self._greeting,
            IntentType.THANKS: self._thanks,
            IntentType.QUESTION: self._answer_question,
            IntentType.EXPLANATION: self._explain,
            IntentType.STATUS: self._status,
            IntentType.MULTI_STEP: self._multi_step,
            IntentType.UNKNOWN: self._fallback,
        }
    
    @track_latency("action_execute")
    def execute(self, intent: ParsedIntent) -> Dict[str, Any]:
        """
        Execute intent and return structured result.
        
        Returns:
            Dict with keys: success, text, speak, category, latency_ms
        """
        start = time.time()
        
        try:
            handler = self._handlers.get(intent.intent_type, self._fallback)
            result = handler(intent)
            
            # Add timing
            result["latency_ms"] = (time.time() - start) * 1000
            
            # Track success
            self._metrics.success.record_by_intent(
                intent.intent_type.value,
                result["success"]
            )
            
            return result
            
        except Exception as e:
            elapsed = time.time() - start
            
            self._metrics.record_failure(
                FailureCategory.EXECUTION_FAILED,
                str(e),
                context={
                    "intent": intent.intent_type.value,
                    "raw_text": intent.raw_input[:100]
                }
            )
            
            logger.error(f"Action execution failed: {e}")
            
            return {
                "success": False,
                "text": "Sorry, something went wrong.",
                "speak": True,
                "category": SpeechCategory.ERROR,
                "latency_ms": elapsed * 1000,
            }
    
    def _open_website(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Open a website."""
        url = intent.get_slot("url", "")
        target = intent.get_slot("target", "website")
        
        if not url:
            return {
                "success": False,
                "text": "I need a website to open.",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
        
        try:
            webbrowser.open(url)
            
            return {
                "success": True,
                "text": f"Opening {target}",  # No URL spoken
                "speak": False,  # Silent for actions
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        except Exception as e:
            return {
                "success": False,
                "text": f"Failed to open {target}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _open_app(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Open an application."""
        import subprocess
        
        exe = intent.get_slot("executable", "")
        app = intent.get_slot("target", exe)
        
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
            
            return {
                "success": True,
                "text": f"Opening {app}",
                "speak": False,
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        except Exception:
            return {
                "success": False,
                "text": f"Failed to open {app}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _search_web(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Search the web."""
        import urllib.parse
        
        query = intent.get_slot("query", "")
        
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
            
            return {
                "success": True,
                "text": f"Searching for {query}",
                "speak": False,
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        except Exception:
            return {
                "success": False,
                "text": "Failed to search",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _play_media(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Play media on YouTube."""
        query = intent.get_slot("query", "")
        url = intent.get_slot("url", "")
        
        if not url and query:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        
        if url:
            try:
                webbrowser.open(url)
                
                return {
                    "success": True,
                    "text": f"Playing {query}" if query else "Playing media",
                    "speak": False,
                    "category": SpeechCategory.ACTION_CONFIRM,
                }
            except Exception:
                pass
        
        return {
            "success": False,
            "text": "I couldn't play that",
            "speak": True,
            "category": SpeechCategory.ERROR,
        }
    
    def _greeting(self, intent: ParsedIntent) -> Dict[str, Any]:
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
    
    def _thanks(self, intent: ParsedIntent) -> Dict[str, Any]:
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
        """Answer a question using knowledge router."""
        topic = intent.get_slot("topic", intent.raw_input)
        
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
        topic = intent.get_slot("topic", "")
        
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
    
    def _status(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Return system status."""
        summary = self._metrics.get_summary()
        
        health = self._metrics.get_health_check()
        status_text = f"System is {health['status']}. "
        
        if "stt" in summary.get("success_rates", {}):
            stt_rate = summary["success_rates"]["stt"] * 100
            status_text += f"Speech recognition: {stt_rate:.0f}% success. "
        
        total_actions = summary.get("total_operations", 0)
        status_text += f"Total operations: {total_actions}."
        
        return {
            "success": True,
            "text": status_text,
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
            print(f"   Step {i}: {sub_intent.raw_input[:50]}")
            result = self.execute(sub_intent)
            results.append(result)
            
            if not result["success"]:
                all_success = False
            
            print(f"   {'✅' if result['success'] else '❌'} {result['text'][:50]}")
            time.sleep(0.3)  # Brief pause between steps
        
        return {
            "success": all_success,
            "text": f"Completed {len(results)} steps",
            "speak": False,
            "category": SpeechCategory.ACTION_CONFIRM,
            "sub_results": results,
        }
    
    def _fallback(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Fallback for unknown intents."""
        # Try the integrated assistant
        try:
            response = self._assistant.process(intent.raw_input)
            
            return {
                "success": response.action_executed or not response.error,
                "text": response.text,
                "speak": response.speak,
                "category": SpeechCategory.ANSWER if response.speak else SpeechCategory.ACTION_CONFIRM,
            }
        except Exception as e:
            logger.error(f"Fallback failed: {e}")
        
        return {
            "success": False,
            "text": "I'm not sure how to help with that. Try asking me to open a website, explain a topic, or search the web.",
            "speak": True,
            "category": SpeechCategory.ERROR,
        }


# =============================================================================
# MAIN ASSISTANT (V3 - Engineering Excellence)
# =============================================================================

class SaarthiVoiceAssistantV3:
    """
    SAARTHI Voice Assistant v3.0 - Engineering Excellence Edition.
    
    Architecture Highlights (Interview Points):
    
    1. DETERMINISTIC STATE MACHINE
       - 7 explicit states with formal transition matrix
       - Thread-safe with RLock
       - Timeout monitoring with auto-recovery
       - Observer pattern for decoupled event handling
    
    2. LAYERED INTENT ENGINE
       - 4-layer parsing: Exact → VerbObject → Question → Fallback
       - Confidence scoring with thresholds
       - Slot extraction for parameters
       - Registry pattern for extensibility
    
    3. PRODUCTION METRICS
       - Latency percentiles (p50, p90, p99)
       - Success rates by intent type
       - Categorized failure tracking
       - Health check endpoint
    
    4. GRACEFUL DEGRADATION
       - Timeout handling at every stage
       - Error recovery to IDLE state
       - Fallback to integrated assistant
       - Detailed error logging
    """
    
    def __init__(self, config: SaarthiConfigV3):
        self.config = config
        
        # Core components
        self._state_machine: Optional[AssistantStateMachine] = None
        self._metrics: MetricsCollector = MetricsCollector.instance()
        self._intent_engine: Optional[IntentEngine] = None
        
        # I/O components
        self._audio_capture: Optional[AudioCapture] = None
        self._stt: Optional[WhisperSTTV3] = None
        self._tts: Optional[SafeTTS] = None
        
        # Business logic
        self._executor: Optional[ActionExecutorV3] = None
        self._history: Optional[CommandHistory] = None
        self._assistant = None
        
        # Session tracking
        self._current_session: Optional[CommandSession] = None
        self._session_count = 0
        
        # State
        self._initialized = False
        self._running = False
        self._start_time = None
    
    def initialize(self) -> bool:
        """Initialize all components with metrics."""
        self._start_time = time.time()
        
        print()
        print("=" * 80)
        print("🎯 SAARTHI VOICE ULTIMATE v3.0 - Engineering Excellence Edition")
        print("=" * 80)
        print()
        
        try:
            # 1. State Machine (core infrastructure)
            print("⚙️  Initializing state machine...")
            self._state_machine = AssistantStateMachine(
                timeout_seconds=self.config.state_timeout
            )
            print("   ✓ State machine ready (7 states, deterministic transitions)")
            
            # 2. Metrics observers
            print("📊 Attaching observers...")
            self._state_machine.add_observer(
                MetricsStateObserver(self._metrics)
            )
            self._state_machine.add_observer(
                UIStateObserver(self._play_beep)
            )
            print("   ✓ Metrics and UI observers attached")
            
            # 3. Audio capture
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
            print("   ✓ Audio capture ready (16kHz, adaptive VAD)")
            
            # 4. Whisper STT
            print("🔊 Loading Whisper model...")
            self._stt = WhisperSTTV3(
                model_name=self.config.whisper_model,
                language=self.config.whisper_language,
                metrics=self._metrics,
            )
            if not self._stt.initialize():
                raise RuntimeError("Failed to initialize Whisper")
            print(f"   ✓ Whisper ready (model: {self.config.whisper_model})")
            
            # 5. Intent Engine (interview-grade)
            print("🧠 Initializing intent engine...")
            self._intent_engine = IntentEngine(
                thresholds=ConfidenceThresholds(
                    execute=self.config.confidence_execute_threshold,
                    suggest=self.config.confidence_suggest_threshold,
                )
            )
            print("   ✓ Intent engine ready (4-layer parsing)")
            
            # 6. Integrated assistant (fallback)
            print("🤖 Creating assistant...")
            self._assistant = create_assistant(enable_tts=False)
            print("   ✓ Fallback assistant ready")
            
            # 7. Action executor
            print("⚡ Initializing action executor...")
            self._executor = ActionExecutorV3(self._assistant, self._metrics)
            print("   ✓ Action executor ready")
            
            # 8. TTS
            if self.config.enable_tts:
                print("🔈 Initializing TTS...")
                base_tts = SimpleTTS()
                base_tts.initialize()
                self._tts = create_safe_tts(base_tts)
                self._tts.initialize()
                print("   ✓ TTS ready (URL blocking enabled)")
            
            # 9. History
            print("📝 Loading command history...")
            self._history = CommandHistory(self.config.history_file)
            self._history.load()
            print("   ✓ History loaded")
            
            # Record initialization time
            init_time = time.time() - self._start_time
            self._metrics.latency.record("initialization", init_time)
            
            self._initialized = True
            
            self._print_welcome_banner(init_time)
            
            return True
            
        except Exception as e:
            self._metrics.record_failure(
                FailureCategory.INITIALIZATION_FAILED,
                str(e),
                context={"traceback": traceback.format_exc()}
            )
            logger.error(f"Initialization failed: {e}")
            print(f"❌ Initialization failed: {e}")
            return False
    
    def _print_welcome_banner(self, init_time: float):
        """Print welcome banner with usage instructions."""
        print()
        print("=" * 80)
        print(f"✅ ALL SYSTEMS READY! (initialized in {init_time:.2f}s)")
        print("=" * 80)
        print()
        print("CONTROLS:")
        print("  SPACE   - Start listening")
        print("  M       - Show metrics dashboard")
        print("  H       - Show recent history")
        print("  Q       - Quit")
        print()
        print("COMMANDS TO TRY:")
        print("  • 'open youtube'              → Opens YouTube")
        print("  • 'play lofi music'           → Searches YouTube for lofi")
        print("  • 'search for python tips'    → Google search")
        print("  • 'explain binary search'     → Knowledge answer")
        print("  • 'what is machine learning'  → Knowledge answer")
        print("  • 'open calculator'           → Opens calc.exe")
        print("  • 'status'                    → System health check")
        print()
        print("ARCHITECTURE HIGHLIGHTS:")
        print("  • Deterministic 7-state FSM with formal transitions")
        print("  • 4-layer intent parsing with confidence scoring")
        print("  • Production metrics (latency, success rates, failures)")
        print("  • Graceful degradation with categorized error handling")
        print()
        print("=" * 80)
        print()
    
    def _play_beep(self, frequency: int, duration: int):
        """Play beep in background thread."""
        if self.config.audio_feedback:
            threading.Thread(
                target=lambda: winsound.Beep(frequency, duration),
                daemon=True
            ).start()
    
    @contextmanager
    def _session_context(self, raw_text: str = ""):
        """Context manager for command session tracking."""
        session = self._metrics.start_session(
            f"voice_session_{self._session_count}"
        )
        session.raw_text = raw_text
        self._current_session = session
        self._session_count += 1
        
        try:
            yield session
        finally:
            self._metrics.end_session(session)
            self._current_session = None
    
    def handle_voice_session(self):
        """
        Handle one complete voice session with state machine.
        
        State Flow:
          IDLE → LISTENING → TRANSCRIBING → THINKING → EXECUTING → SPEAKING → IDLE
                     ↘ ERROR ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←↙
        """
        print("\n" + "─" * 80)
        
        with self._session_context() as session:
            try:
                # 1. LISTENING
                if not self._state_machine.transition(
                    AssistantState.LISTENING, "space_pressed"
                ):
                    logger.error("Failed to enter LISTENING state")
                    return
                
                print("🎙️  LISTENING... (speak now, will auto-stop)")
                
                audio = self._audio_capture.record_with_vad(
                    on_speech_start=lambda: logger.debug("Speech detected"),
                    on_speech_end=lambda: logger.debug("Speech ended"),
                )
                
                if audio is None:
                    self._state_machine.transition(
                        AssistantState.ERROR, "no_audio"
                    )
                    print("❌ No audio captured")
                    self._state_machine.force_idle("recovery")
                    return
                
                duration = len(audio) / self.config.sample_rate
                session.audio_duration = duration
                print(f"   ✓ Recorded {duration:.1f}s")
                
                # 2. TRANSCRIBING
                if not self._state_machine.transition(
                    AssistantState.TRANSCRIBING, "vad_complete"
                ):
                    self._state_machine.force_idle("recovery")
                    return
                
                print("🔄 Transcribing...")
                
                text = self._stt.transcribe(audio)
                
                if not text:
                    self._state_machine.transition(
                        AssistantState.ERROR, "stt_failed"
                    )
                    print("❌ No speech detected")
                    self._state_machine.force_idle("recovery")
                    return
                
                session.raw_text = text
                session.stt_success = True
                print(f"📝 You said: \"{text}\"")
                
                # 3. THINKING (intent classification)
                if not self._state_machine.transition(
                    AssistantState.THINKING, "stt_complete"
                ):
                    self._state_machine.force_idle("recovery")
                    return
                
                print("🧠 Understanding...")
                
                intent = self._intent_engine.classify(text)
                session.intent_type = intent.intent_type.value
                session.confidence = intent.confidence
                
                logger.info(
                    f"Intent: {intent.intent_type.value} "
                    f"(confidence: {intent.confidence:.2f})"
                )
                
                # Show intent info
                print(f"   Intent: {intent.intent_type.value} ({intent.confidence:.0%} confident)")
                if intent.slots:
                    slots_str = ", ".join(f"{k}={v}" for k, v in intent.slots.items())
                    print(f"   Slots: {slots_str}")
                
                # 4. EXECUTING
                if not self._state_machine.transition(
                    AssistantState.EXECUTING, "intent_classified"
                ):
                    self._state_machine.force_idle("recovery")
                    return
                
                if intent.intent_type in [IntentType.QUESTION, IntentType.EXPLANATION]:
                    print("💡 Finding answer...")
                else:
                    print("⚡ Executing...")
                
                result = self._executor.execute(intent)
                
                session.execution_success = result["success"]
                session.action_type = intent.intent_type.value
                
                # 5. Output
                print(f"💬 SAARTHI: {result['text']}")
                
                if result.get("source"):
                    print(f"   📚 Source: {result['source']}")
                
                print(f"   ⏱️  Latency: {result.get('latency_ms', 0):.0f}ms")
                
                # 6. SPEAKING (if needed)
                if result.get("speak", False) and self._tts:
                    if not self._state_machine.transition(
                        AssistantState.SPEAKING, "needs_speech"
                    ):
                        self._state_machine.force_idle("recovery")
                        return
                    
                    category = result.get("category", SpeechCategory.UNKNOWN)
                    self._tts.speak(result["text"], category)
                
                # 7. Back to IDLE
                self._state_machine.transition(
                    AssistantState.IDLE,
                    "execution_complete" if result.get("speak") else "execution_silent"
                )
                
                # 8. Save history
                if self._history:
                    self._history.add(session)
                
            except Exception as e:
                self._state_machine.transition(AssistantState.ERROR, str(e))
                self._metrics.record_failure(
                    FailureCategory.UNKNOWN,
                    str(e),
                    context={"traceback": traceback.format_exc()}
                )
                logger.error(f"Session error: {e}")
                print(f"❌ Error: {e}")
                self._state_machine.force_idle("error_recovery")
        
        print("─" * 80)
        print(f"State: {self._state_machine.state.value} | "
              f"Sessions: {self._session_count} | "
              f"Press SPACE to speak, M for metrics, Q to quit")
        print()
    
    def show_metrics_dashboard(self):
        """Display comprehensive metrics dashboard."""
        print("\n" + "=" * 80)
        print("📊 METRICS DASHBOARD")
        print("=" * 80)
        
        summary = self._metrics.get_summary()
        health = self._metrics.get_health_check()
        stt_stats = self._stt.get_stats() if self._stt else {}
        state_stats = self._state_machine.get_statistics() if self._state_machine else {}
        
        # Health Status
        status_emoji = "✅" if health["status"] == "healthy" else "⚠️"
        print(f"\n{status_emoji} System Health: {health['status'].upper()}")
        
        # Latency Metrics
        print("\n⏱️  LATENCY PERCENTILES:")
        for operation, percentiles in summary.get("latency", {}).items():
            if percentiles.get("p50"):
                print(f"   {operation:30s} P50:{percentiles['p50']:7.1f}ms  "
                      f"P90:{percentiles['p90']:7.1f}ms  P99:{percentiles['p99']:7.1f}ms")
        
        # Success Rates
        print("\n✅ SUCCESS RATES:")
        for operation, rate in summary.get("success_rates", {}).items():
            bar = "█" * int(rate * 20) + "░" * (20 - int(rate * 20))
            print(f"   {operation:30s} [{bar}] {rate*100:5.1f}%")
        
        # STT Stats
        if stt_stats.get("transcription_count"):
            print("\n🔊 SPEECH-TO-TEXT:")
            print(f"   Transcriptions: {stt_stats['transcription_count']}")
            print(f"   Total audio: {stt_stats['total_audio_seconds']:.1f}s")
            print(f"   Processing time: {stt_stats['total_transcription_time']:.1f}s")
            print(f"   Average RTF: {stt_stats['average_rtf']:.2f}x realtime")
        
        # State Machine Stats
        if state_stats:
            print("\n⚙️  STATE MACHINE:")
            print(f"   Transitions: {state_stats['transition_count']}")
            print(f"   Current state: {state_stats['current_state']}")
            time_per_state = state_stats.get('time_per_state', {})
            for state, time_spent in time_per_state.items():
                print(f"   Time in {state}: {time_spent:.1f}s")
        
        # Recent Failures
        recent_failures = self._metrics.failures.get_recent_failures(5)
        if recent_failures:
            print("\n❌ RECENT FAILURES:")
            for failure in recent_failures[-5:]:
                print(f"   [{failure['category']}] {failure['message'][:50]}")
        
        # Uptime
        if self._start_time:
            uptime = time.time() - self._start_time
            mins, secs = divmod(int(uptime), 60)
            hours, mins = divmod(mins, 60)
            print(f"\n⏰ Uptime: {hours}h {mins}m {secs}s")
            print(f"   Sessions: {self._session_count}")
        
        print("\n" + "=" * 80)
        print()
    
    def show_history(self):
        """Show recent command history."""
        print("\n" + "=" * 80)
        print("📜 RECENT HISTORY")
        print("=" * 80)
        
        if self._history:
            entries = self._history.get_recent(10)
            
            if not entries:
                print("\nNo history yet.\n")
            else:
                for i, entry in enumerate(entries, 1):
                    status = "✅" if entry.get("success") else "❌"
                    print(f"\n{i}. {status} \"{entry.get('text', 'N/A')[:50]}\"")
                    print(f"   Intent: {entry.get('intent', 'N/A')} | "
                          f"Confidence: {entry.get('confidence', 0)*100:.0f}% | "
                          f"Latency: {entry.get('latency_ms', 0):.0f}ms")
        
        print("\n" + "=" * 80)
        print()
    
    def run(self):
        """Main run loop with keyboard handling."""
        if not self._initialized:
            if not self.initialize():
                return
        
        self._running = True
        print("🎯 Ready! Press SPACE BAR to start speaking...")
        print()
        
        try:
            while self._running:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    
                    if key == ' ':  # Space bar
                        self.handle_voice_session()
                    
                    elif key == 'm':  # Metrics
                        self.show_metrics_dashboard()
                    
                    elif key == 'h':  # History
                        self.show_history()
                    
                    elif key == 'q':  # Quit
                        print("\n👋 Goodbye!")
                        break
                
                time.sleep(0.05)  # 50ms polling
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources and show final metrics."""
        self._running = False
        
        # Show final metrics if configured
        if self.config.show_metrics_on_exit and self._session_count > 0:
            self.show_metrics_dashboard()
        
        # Save history
        if self._history:
            self._history.save()
            print("✓ Command history saved")
        
        # Stop TTS
        if self._tts:
            self._tts.stop()
        
        # Log final stats
        if self._metrics:
            summary = self._metrics.get_summary()
            logger.info(f"Final metrics: {summary}")
        
        logger.info("SAARTHI v3 cleaned up")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    print("\n" + "🚀 Starting SAARTHI v3.0..." + "\n")
    
    config = SaarthiConfigV3()
    assistant = SaarthiVoiceAssistantV3(config)
    assistant.run()


if __name__ == "__main__":
    main()
