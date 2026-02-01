#!/usr/bin/env python3
"""
SAARTHI Voice Ultimate v4.0 - Product Excellence Edition
==========================================================

A daily-use voice assistant for Windows with features that maximize
real-world usefulness, retention, and ease of use.

PRODUCT FEATURES:
  1. Contextual Session Memory - "do it again", "tell me more"
  2. Focus Mode - Reduced chatter for productivity
  3. Natural Follow-Up Handling - "why?", "how?", "simpler"
  4. Risk-Aware Confirmations - Only for dangerous actions
  5. Usage-Based Optimization - Learn your patterns
  6. Offline Graceful Degradation - Works without internet
  7. Visual State Indicator - System tray status

DESIGN PRINCIPLES:
  - Reduce friction: No unnecessary confirmations
  - Natural interactions: Follow-ups just work
  - Privacy-first: All learning is local
  - Fast: <2s response for common commands
  - Graceful: Offline mode, error recovery

USAGE:
    python voice_ultimate_v4.py

CONTROLS:
    SPACE  - Start listening
    M      - Metrics dashboard
    H      - History
    F      - Toggle focus mode
    S      - Status (connectivity, cache, usage)
    Q      - Quit

Author: SAARTHI Engineering Team
Version: 4.0.0
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
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime

# Core infrastructure (v3)
from saarthi_executor.audio_capture import AudioCapture, AudioCaptureConfig
from saarthi_executor.robust_vad import VADConfig
from saarthi_executor.tts_policy import SafeTTS, SpeechCategory, create_safe_tts
from saarthi_executor.knowledge_router import get_answer
from saarthi_executor.integrated_assistant import create_assistant, SimpleTTS
from saarthi_executor.assistant_state_machine import (
    AssistantStateMachine, AssistantState
)
from saarthi_executor.metrics import MetricsCollector
from saarthi_executor.intent_engine import IntentEngine, IntentType, ParsedIntent

# NEW v4 product modules
from saarthi_executor.session_memory import (
    SessionMemory, ContextType, SessionContext,
    FollowUpDetector, FollowUpType, FollowUpMatch,
    get_session_memory
)
from saarthi_executor.focus_mode import (
    FocusModeManager, FocusModeLevel, FocusModeConfig,
    truncate_to_sentences, get_focus_manager
)
from saarthi_executor.confirmation_system import (
    ConfirmationManager, RiskAssessment, RiskLevel,
    get_confirmation_manager
)
from saarthi_executor.usage_optimizer import (
    UsageOptimizer, get_usage_optimizer
)
from saarthi_executor.offline_manager import OfflineManager, get_offline_manager
from saarthi_executor.visual_indicator import (
    StateIndicatorManager, IndicatorState, map_assistant_state_to_indicator,
    get_indicator_manager
)
from saarthi_executor.audio_feedback import AudioFeedback, FeedbackType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SaarthiConfigV4:
    """Configuration for SAARTHI v4."""
    # Audio
    sample_rate: int = 16000
    silence_duration: float = 1.5
    max_recording: float = 30.0
    min_speech_duration: float = 0.3
    silence_threshold: float = 0.01
    
    # Whisper
    whisper_model: str = "tiny"
    whisper_language: str = "en"
    
    # TTS
    enable_tts: bool = True
    
    # Intent
    confidence_execute_threshold: float = 0.60
    confidence_confirm_threshold: float = 0.40
    
    # Behavior
    audio_feedback: bool = True  # Play beeps for state transitions
    save_usage_stats: bool = True
    enable_visual_indicator: bool = True
    
    # Timeouts
    stt_timeout: float = 10.0
    knowledge_timeout: float = 3.0
    
    # Paths
    history_file: Path = field(default_factory=lambda: Path(__file__).parent / "command_history.json")


CONFIG = SaarthiConfigV4()


# =============================================================================
# WHISPER STT (v4 - with offline awareness)
# =============================================================================

class WhisperSTTV4:
    """Whisper STT with offline awareness."""
    
    def __init__(self, model_name: str = "tiny", language: str = "en"):
        self.model_name = model_name
        self.language = language
        self._model = None
        self._lock = threading.Lock()
        self._metrics = MetricsCollector.instance()
    
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
        """Transcribe audio to text."""
        if self._model is None:
            return None
        
        audio_duration = len(audio) / CONFIG.sample_rate
        if audio_duration < CONFIG.min_speech_duration:
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
                
                self._metrics.latency.record("stt", elapsed * 1000)
                self._metrics.success.record("stt", True)
                
                logger.info(f"STT: {audio_duration:.1f}s → {elapsed:.2f}s → '{text[:50]}'")
                return text if text else None
                
            except Exception as e:
                self._metrics.success.record("stt", False)
                logger.error(f"Transcription failed: {e}")
                return None


# =============================================================================
# COMMAND HISTORY (v4 - with session context)
# =============================================================================

class CommandHistoryV4:
    """Command history with session context."""
    
    def __init__(self, filepath: Path, max_entries: int = 100):
        self.filepath = filepath
        self.max_entries = max_entries
        self._history: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()
    
    def load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath) as f:
                    data = json.load(f)
                    self._history.extend(data[-self.max_entries:])
                logger.info(f"Loaded {len(self._history)} history entries")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")
    
    def save(self):
        with self._lock:
            try:
                with open(self.filepath, 'w') as f:
                    json.dump(list(self._history), f, indent=2, default=str)
            except Exception as e:
                logger.warning(f"Failed to save history: {e}")
    
    def add(self, text: str, intent_type: str, success: bool, 
            confidence: float = 0.0, was_follow_up: bool = False):
        with self._lock:
            self._history.append({
                "text": text,
                "intent": intent_type,
                "success": success,
                "confidence": confidence,
                "was_follow_up": was_follow_up,
                "timestamp": datetime.now().isoformat(),
            })
    
    def get_recent(self, n: int = 10) -> List[Dict]:
        with self._lock:
            return list(self._history)[-n:]


# =============================================================================
# ACTION EXECUTOR (v4 - with all product features)
# =============================================================================

class ActionExecutorV4:
    """
    Execute parsed intents with product features.
    
    Integrations:
    - Session memory for context
    - Focus mode for response style
    - Usage optimization for learning
    - Offline manager for degradation
    - Confirmation system for safety
    """
    
    def __init__(
        self,
        assistant,
        memory: SessionMemory,
        focus: FocusModeManager,
        usage: UsageOptimizer,
        offline: OfflineManager,
        confirmation: ConfirmationManager,
        tts: Optional[SafeTTS] = None,
    ):
        self._assistant = assistant
        self._memory = memory
        self._focus = focus
        self._usage = usage
        self._offline = offline
        self._confirmation = confirmation
        self._tts = tts
        self._metrics = MetricsCollector.instance()
    
    def execute(self, intent: ParsedIntent, context: SessionContext) -> Dict[str, Any]:
        """Execute intent with full context."""
        start = time.time()
        
        try:
            # Route by intent type
            if intent.intent_type == IntentType.OPEN_WEBSITE:
                result = self._open_website(intent)
            elif intent.intent_type == IntentType.OPEN_APPLICATION:
                result = self._open_app(intent)
            elif intent.intent_type == IntentType.SEARCH_WEB:
                result = self._search_web(intent)
            elif intent.intent_type == IntentType.PLAY_MEDIA:
                result = self._play_media(intent)
            elif intent.intent_type == IntentType.QUESTION:
                result = self._answer_question(intent, context)
            elif intent.intent_type == IntentType.EXPLANATION:
                result = self._explain(intent, context)
            elif intent.intent_type == IntentType.GREETING:
                result = self._greeting()
            elif intent.intent_type == IntentType.THANKS:
                result = self._thanks()
            elif intent.intent_type == IntentType.STATUS:
                result = self._status()
            elif intent.intent_type == IntentType.MULTI_STEP:
                result = self._multi_step(intent, context)
            else:
                result = self._fallback(intent)
            
            # Apply focus mode to response
            result = self._apply_focus_mode(result)
            
            # Record usage
            self._record_usage(intent, result)
            
            # Record in session memory
            self._record_memory(intent, result)
            
            result["latency_ms"] = (time.time() - start) * 1000
            return result
            
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            return {
                "success": False,
                "text": "Something went wrong.",
                "speak": True,
                "category": SpeechCategory.ERROR,
                "latency_ms": (time.time() - start) * 1000,
            }
    
    def _open_website(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Open a website."""
        url = intent.get_slot("url", "")
        target = intent.get_slot("target", "website")
        
        if not url:
            return {
                "success": False,
                "text": "Which website?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        try:
            webbrowser.open(url)
            return {
                "success": True,
                "text": f"Opening {target}",
                "speak": False,  # Silent for actions
                "category": SpeechCategory.ACTION_CONFIRM,
                "target": target,
            }
        except Exception:
            return {
                "success": False,
                "text": f"Couldn't open {target}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _open_app(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Open an application."""
        import subprocess
        
        exe = intent.get_slot("executable", "")
        target = intent.get_slot("target", exe)
        
        if not exe:
            return {
                "success": False,
                "text": "Which app?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
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
                "text": f"Opening {target}",
                "speak": False,
                "category": SpeechCategory.ACTION_CONFIRM,
                "target": target,
            }
        except Exception:
            return {
                "success": False,
                "text": f"Couldn't open {target}",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _search_web(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Web search."""
        import urllib.parse
        
        query = intent.get_slot("query", "")
        
        if not query:
            return {
                "success": False,
                "text": "What should I search for?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        # Check offline
        if self._offline.is_offline():
            return {
                "success": False,
                "text": self._offline.get_offline_message("search"),
                "speak": True,
                "category": SpeechCategory.ERROR,
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
                "text": "Search failed",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _play_media(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Play media."""
        query = intent.get_slot("query", "")
        url = intent.get_slot("url", "")
        
        if not url and query:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        
        if url:
            try:
                webbrowser.open(url)
                return {
                    "success": True,
                    "text": f"Playing {query}" if query else "Playing",
                    "speak": False,
                    "category": SpeechCategory.ACTION_CONFIRM,
                }
            except Exception:
                pass
        
        return {
            "success": False,
            "text": "Couldn't play that",
            "speak": True,
            "category": SpeechCategory.ERROR,
        }
    
    def _answer_question(self, intent: ParsedIntent, context: SessionContext) -> Dict[str, Any]:
        """Answer a question with offline awareness."""
        topic = intent.get_slot("topic", intent.raw_input)
        
        # Check cache first (for offline)
        cached = self._offline.get_cached_answer(topic)
        if cached:
            return {
                "success": True,
                "text": cached,
                "speak": True,
                "category": SpeechCategory.ANSWER,
                "source": "cache",
                "topic": topic,
            }
        
        # Try online lookup
        if self._offline.is_offline():
            return {
                "success": False,
                "text": self._offline.get_offline_message("question"),
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
        
        result = get_answer(topic, timeout=CONFIG.knowledge_timeout)
        
        # Cache for future offline use
        if result.confidence > 0.5:
            self._offline.cache_answer(topic, result.answer, result.source)
        
        return {
            "success": result.confidence > 0.5,
            "text": result.answer,
            "speak": True,
            "category": SpeechCategory.ANSWER,
            "source": result.source,
            "topic": topic,
        }
    
    def _explain(self, intent: ParsedIntent, context: SessionContext) -> Dict[str, Any]:
        """Explain a topic."""
        topic = intent.get_slot("topic", "")
        
        if not topic and context.last_topic:
            # Use topic from context
            topic = context.last_topic
        
        if not topic:
            return {
                "success": False,
                "text": "What should I explain?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        # Reuse question logic
        return self._answer_question(
            ParsedIntent(
                intent_type=IntentType.QUESTION,
                confidence=intent.confidence,
                slots={"topic": intent.get_slot("topic") or topic},
                raw_input=topic,
            ),
            context
        )
    
    def _greeting(self) -> Dict[str, Any]:
        import random
        responses = [
            "Hey! What can I do?",
            "Hi! Ready to help.",
            "Hello!",
        ]
        return {
            "success": True,
            "text": random.choice(responses),
            "speak": self._focus.should_speak_greeting(),
            "category": SpeechCategory.GREETING,
        }
    
    def _thanks(self) -> Dict[str, Any]:
        import random
        responses = ["Welcome!", "Anytime!", "Sure!"]
        return {
            "success": True,
            "text": random.choice(responses),
            "speak": self._focus.should_speak_greeting(),
            "category": SpeechCategory.THANKS,
        }
    
    def _status(self) -> Dict[str, Any]:
        """System status with connectivity info."""
        parts = []
        
        # Connectivity
        if self._offline.is_online():
            parts.append("Online")
        else:
            parts.append("Offline")
        
        # Focus mode
        if self._focus.is_active():
            parts.append("Focus mode on")
        
        # Metrics
        health = self._metrics.get_health_check()
        parts.append(f"System {health['status']}")
        
        return {
            "success": True,
            "text": ". ".join(parts) + ".",
            "speak": True,
            "category": SpeechCategory.STATUS,
        }
    
    def _multi_step(self, intent: ParsedIntent, context: SessionContext) -> Dict[str, Any]:
        """Execute multi-step command."""
        if not intent.sub_intents:
            return self._fallback(intent)
        
        results = []
        all_success = True
        
        for sub_intent in intent.sub_intents:
            result = self.execute(sub_intent, context)
            results.append(result)
            if not result["success"]:
                all_success = False
            time.sleep(0.3)
        
        return {
            "success": all_success,
            "text": f"Done ({len(results)} steps)",
            "speak": False,
            "category": SpeechCategory.ACTION_CONFIRM,
        }
    
    def _fallback(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Fallback handler."""
        try:
            response = self._assistant.process(intent.raw_input)
            return {
                "success": response.action_executed or not response.error,
                "text": response.text,
                "speak": response.speak,
                "category": SpeechCategory.ANSWER,
            }
        except Exception:
            return {
                "success": False,
                "text": "I'm not sure how to help with that.",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
    
    def _apply_focus_mode(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Apply focus mode modifications to result."""
        if not self._focus.is_active():
            return result
        
        # Truncate long answers
        max_sentences = self._focus.get_max_sentences()
        if max_sentences > 0 and result.get("text"):
            result["text"] = truncate_to_sentences(result["text"], max_sentences)
        
        # Suppress non-essential speech
        category = result.get("category")
        if category == SpeechCategory.GREETING:
            result["speak"] = self._focus.should_speak_greeting()
        elif category == SpeechCategory.ACTION_CONFIRM:
            result["speak"] = self._focus.should_speak_confirmation()
        
        return result
    
    def _record_usage(self, intent: ParsedIntent, result: Dict[str, Any]):
        """Record usage for optimization."""
        if not result.get("success"):
            return
        
        target = result.get("target") or intent.get_slot("target")
        
        if intent.intent_type == IntentType.OPEN_WEBSITE and target:
            self._usage.record_open("website", target)
        elif intent.intent_type == IntentType.OPEN_APPLICATION and target:
            self._usage.record_open("app", target)
        elif intent.intent_type in (IntentType.QUESTION, IntentType.EXPLANATION):
            topic = result.get("topic") or intent.get_slot("topic")
            if topic:
                self._usage.record_question(topic)
    
    def _record_memory(self, intent: ParsedIntent, result: Dict[str, Any]):
        """Record in session memory."""
        target = result.get("target") or intent.get_slot("target")
        topic = result.get("topic") or intent.get_slot("topic")
        
        if intent.intent_type in (IntentType.OPEN_WEBSITE, IntentType.OPEN_APPLICATION,
                                   IntentType.SEARCH_WEB, IntentType.PLAY_MEDIA):
            self._memory.record_command(
                raw_text=intent.raw_input,
                intent_type=intent.intent_type.value,
                target=target,
                success=result.get("success", False),
                result_text=result.get("text", ""),
            )
        elif intent.intent_type in (IntentType.QUESTION, IntentType.EXPLANATION):
            if result.get("success") and topic:
                self._memory.record_question(
                    raw_text=intent.raw_input,
                    topic=topic,
                    answer=result.get("text", ""),
                    source=result.get("source", ""),
                )


# =============================================================================
# FOLLOW-UP HANDLER
# =============================================================================

class FollowUpHandler:
    """
    Handles follow-up utterances using session context.
    
    Converts partial utterances like "why?", "again", "more"
    into complete intents using session memory.
    """
    
    def __init__(
        self,
        memory: SessionMemory,
        intent_engine: IntentEngine,
        executor: ActionExecutorV4,
    ):
        self._memory = memory
        self._intent_engine = intent_engine
        self._executor = executor
        self._detector = FollowUpDetector()
    
    def is_follow_up(self, text: str) -> bool:
        """Check if text is a follow-up."""
        context = self._memory.get_context()
        return self._detector.is_follow_up(text, context)
    
    def handle(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Handle a follow-up utterance.
        
        Returns result dict if handled, None if not a follow-up.
        """
        context = self._memory.get_context()
        match = self._detector.detect(text, context)
        
        if match.follow_up_type == FollowUpType.NOT_FOLLOW_UP:
            return None
        
        logger.info(f"Follow-up detected: {match.follow_up_type.value}")
        
        # Handle by type
        if match.follow_up_type == FollowUpType.REPEAT:
            return self._handle_repeat(context)
        elif match.follow_up_type == FollowUpType.ELABORATE:
            return self._handle_elaborate(context)
        elif match.follow_up_type == FollowUpType.EXPLAIN_WHY:
            return self._handle_why(context)
        elif match.follow_up_type == FollowUpType.EXPLAIN_HOW:
            return self._handle_how(context)
        elif match.follow_up_type == FollowUpType.SIMPLIFY:
            return self._handle_simplify(context)
        elif match.follow_up_type == FollowUpType.EXAMPLE:
            return self._handle_example(context)
        elif match.follow_up_type == FollowUpType.CONFIRM:
            return self._handle_confirm()
        elif match.follow_up_type == FollowUpType.CANCEL:
            return self._handle_cancel()
        
        return None
    
    def _handle_repeat(self, context: SessionContext) -> Optional[Dict[str, Any]]:
        """Handle 'do it again'."""
        repeatable = self._memory.get_repeatable_action()
        if not repeatable:
            return {
                "success": False,
                "text": "Nothing to repeat.",
                "speak": True,
                "category": SpeechCategory.ERROR,
            }
        
        # Re-execute the original command
        intent = self._intent_engine.classify(repeatable.raw_text)
        return self._executor.execute(intent, context)
    
    def _handle_elaborate(self, context: SessionContext) -> Optional[Dict[str, Any]]:
        """Handle 'tell me more'."""
        topic = self._memory.get_topic_for_follow_up()
        if not topic:
            return {
                "success": False,
                "text": "More about what?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        # Ask for more about the topic
        intent = ParsedIntent(
            intent_type=IntentType.EXPLANATION,
            confidence=0.9,
            slots={"topic": topic},
            raw_input=f"tell me more about {topic}",
        )
        return self._executor.execute(intent, context)
    
    def _handle_why(self, context: SessionContext) -> Optional[Dict[str, Any]]:
        """Handle 'why?'."""
        topic = self._memory.get_topic_for_follow_up()
        if not topic:
            return {
                "success": False,
                "text": "Why what?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        intent = ParsedIntent(
            intent_type=IntentType.EXPLANATION,
            confidence=0.9,
            slots={"topic": f"why {topic}"},
            raw_input=f"why {topic}",
        )
        return self._executor.execute(intent, context)
    
    def _handle_how(self, context: SessionContext) -> Optional[Dict[str, Any]]:
        """Handle 'how?'."""
        topic = self._memory.get_topic_for_follow_up()
        if not topic:
            return {
                "success": False,
                "text": "How what?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        intent = ParsedIntent(
            intent_type=IntentType.EXPLANATION,
            confidence=0.9,
            slots={"topic": f"how {topic} works"},
            raw_input=f"how does {topic} work",
        )
        return self._executor.execute(intent, context)
    
    def _handle_simplify(self, context: SessionContext) -> Optional[Dict[str, Any]]:
        """Handle 'simpler'."""
        topic = self._memory.get_topic_for_follow_up()
        if not topic:
            return {
                "success": False,
                "text": "Simplify what?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        intent = ParsedIntent(
            intent_type=IntentType.EXPLANATION,
            confidence=0.9,
            slots={"topic": f"{topic} in simple terms"},
            raw_input=f"explain {topic} simply",
        )
        return self._executor.execute(intent, context)
    
    def _handle_example(self, context: SessionContext) -> Optional[Dict[str, Any]]:
        """Handle 'example'."""
        topic = self._memory.get_topic_for_follow_up()
        if not topic:
            return {
                "success": False,
                "text": "Example of what?",
                "speak": True,
                "category": SpeechCategory.QUESTION,
            }
        
        intent = ParsedIntent(
            intent_type=IntentType.EXPLANATION,
            confidence=0.9,
            slots={"topic": f"example of {topic}"},
            raw_input=f"give me an example of {topic}",
        )
        return self._executor.execute(intent, context)
    
    def _handle_confirm(self) -> Optional[Dict[str, Any]]:
        """Handle confirmation."""
        confirmation = get_confirmation_manager()
        if confirmation.has_pending():
            pending = confirmation.confirm_pending()
            if pending and pending.executor_callback:
                return pending.executor_callback()
        
        return {
            "success": True,
            "text": "Nothing pending.",
            "speak": False,
            "category": SpeechCategory.ACTION_CONFIRM,
        }
    
    def _handle_cancel(self) -> Optional[Dict[str, Any]]:
        """Handle cancellation."""
        confirmation = get_confirmation_manager()
        if confirmation.has_pending():
            confirmation.cancel_pending()
            return {
                "success": True,
                "text": "Cancelled.",
                "speak": True,
                "category": SpeechCategory.ACTION_CONFIRM,
            }
        
        return {
            "success": True,
            "text": "Nothing to cancel.",
            "speak": False,
            "category": SpeechCategory.ACTION_CONFIRM,
        }


# =============================================================================
# MAIN ASSISTANT (v4)
# =============================================================================

class SaarthiVoiceAssistantV4:
    """
    SAARTHI Voice Assistant v4.0 - Product Excellence Edition.
    
    Product Features:
    1. Session Memory - Follow-up conversations
    2. Focus Mode - Reduced chatter
    3. Natural Follow-Ups - "why?", "again", "more"
    4. Smart Confirmations - Only for risky actions
    5. Usage Learning - Improves with use
    6. Offline Mode - Works without internet
    7. Visual Indicator - System tray status
    """
    
    def __init__(self, config: SaarthiConfigV4):
        self.config = config
        
        # Core infrastructure
        self._state_machine: Optional[AssistantStateMachine] = None
        self._metrics = MetricsCollector.instance()
        self._intent_engine: Optional[IntentEngine] = None
        
        # I/O
        self._audio_capture: Optional[AudioCapture] = None
        self._stt: Optional[WhisperSTTV4] = None
        self._tts: Optional[SafeTTS] = None
        
        # Product features
        self._memory: Optional[SessionMemory] = None
        self._focus: Optional[FocusModeManager] = None
        self._usage: Optional[UsageOptimizer] = None
        self._offline: Optional[OfflineManager] = None
        self._confirmation: Optional[ConfirmationManager] = None
        self._indicator: Optional[StateIndicatorManager] = None
        self._audio_feedback: Optional[AudioFeedback] = None
        
        # Business logic
        self._executor: Optional[ActionExecutorV4] = None
        self._follow_up: Optional[FollowUpHandler] = None
        self._history: Optional[CommandHistoryV4] = None
        self._assistant = None
        
        # State
        self._initialized = False
        self._running = False
        self._session_count = 0
    
    def initialize(self) -> bool:
        """Initialize all components."""
        print()
        print("=" * 80)
        print("🎯 SAARTHI VOICE ULTIMATE v4.0 - Product Excellence Edition")
        print("=" * 80)
        print()
        
        try:
            # State machine
            print("⚙️  Initializing state machine...")
            self._state_machine = AssistantStateMachine()
            print("   ✓ State machine ready")
            
            # Product features (initialize first as they're used by other components)
            print("📦 Initializing product features...")
            self._memory = get_session_memory()
            self._focus = get_focus_manager()
            self._usage = get_usage_optimizer()
            self._offline = get_offline_manager()
            self._confirmation = get_confirmation_manager()
            print("   ✓ Session memory, focus mode, usage optimizer, offline manager")
            
            # Audio feedback
            print("🔊 Initializing audio feedback...")
            self._audio_feedback = AudioFeedback(enabled=self.config.audio_feedback)
            print(f"   ✓ Audio feedback {'enabled' if self._audio_feedback.is_enabled else 'disabled'}")
            
            # Visual indicator
            if self.config.enable_visual_indicator:
                print("👁️  Initializing visual indicator...")
                self._indicator = get_indicator_manager(on_quit=self._on_quit_request)
                self._indicator.start()
                print(f"   ✓ Visual indicator {'(tray)' if self._indicator.is_tray_available() else '(console)'}")
            
            # Audio
            print("🎤 Initializing audio capture...")
            vad_config = VADConfig(
                sample_rate=self.config.sample_rate,
                silence_duration=self.config.silence_duration,
                max_recording_duration=self.config.max_recording,
                min_speech_duration=self.config.min_speech_duration,
                initial_threshold=self.config.silence_threshold,
            )
            audio_config = AudioCaptureConfig(sample_rate=self.config.sample_rate)
            self._audio_capture = AudioCapture(audio_config, vad_config)
            print("   ✓ Audio capture ready")
            
            # STT
            print("🔊 Loading Whisper model...")
            self._stt = WhisperSTTV4(
                model_name=self.config.whisper_model,
                language=self.config.whisper_language,
            )
            if not self._stt.initialize():
                raise RuntimeError("Failed to initialize Whisper")
            print(f"   ✓ Whisper ready ({self.config.whisper_model})")
            
            # Intent engine
            print("🧠 Initializing intent engine...")
            self._intent_engine = IntentEngine()
            print("   ✓ Intent engine ready")
            
            # Assistant (fallback)
            print("🤖 Creating assistant...")
            self._assistant = create_assistant(enable_tts=False)
            print("   ✓ Fallback assistant ready")
            
            # TTS
            if self.config.enable_tts:
                print("🔈 Initializing TTS...")
                base_tts = SimpleTTS()
                base_tts.initialize()
                self._tts = create_safe_tts(base_tts)
                self._tts.initialize()
                print("   ✓ TTS ready")
            
            # Executor
            print("⚡ Initializing executor...")
            self._executor = ActionExecutorV4(
                assistant=self._assistant,
                memory=self._memory,
                focus=self._focus,
                usage=self._usage,
                offline=self._offline,
                confirmation=self._confirmation,
                tts=self._tts,
            )
            print("   ✓ Executor ready")
            
            # Follow-up handler
            self._follow_up = FollowUpHandler(
                memory=self._memory,
                intent_engine=self._intent_engine,
                executor=self._executor,
            )
            
            # History
            print("📝 Loading history...")
            self._history = CommandHistoryV4(self.config.history_file)
            self._history.load()
            print("   ✓ History loaded")
            
            self._initialized = True
            self._print_welcome()
            
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            print(f"❌ Initialization failed: {e}")
            return False
    
    def _print_welcome(self):
        """Print welcome message."""
        print()
        print("=" * 80)
        print("✅ ALL SYSTEMS READY!")
        print("=" * 80)
        print()
        print("CONTROLS:")
        print("  SPACE  - Start listening")
        print("  F      - Toggle focus mode")
        print("  M      - Metrics dashboard")
        print("  H      - History")
        print("  S      - Status (connectivity, cache)")
        print("  Q      - Quit")
        print()
        print("NEW IN v4:")
        print("  • Say 'again' to repeat last action")
        print("  • Say 'why?', 'how?', 'more' for follow-ups")
        print("  • Say 'focus mode' for less chatter")
        print("  • Works offline with cached answers")
        print()
        
        # Show connectivity status
        if self._offline.is_online():
            print("🌐 Online - Full features available")
        else:
            print("📴 Offline - Limited to cached answers and local apps")
        print()
        print("=" * 80)
        print()
    
    def _update_indicator(self, state: AssistantState):
        """Update visual indicator."""
        if self._indicator:
            indicator_state = map_assistant_state_to_indicator(
                state.name,
                is_offline=self._offline.is_offline(),
                is_focus_mode=self._focus.is_active(),
            )
            self._indicator.set_state(indicator_state)
    
    def handle_voice_session(self):
        """Handle one complete voice session."""
        print("\n" + "─" * 80)
        self._session_count += 1
        
        try:
            # LISTENING
            self._state_machine.transition(AssistantState.LISTENING, "space_pressed")
            self._update_indicator(AssistantState.LISTENING)
            if self._audio_feedback:
                self._audio_feedback.play_listening_start()
            
            print("🎙️  LISTENING... (speak now)")
            
            audio = self._audio_capture.record_with_vad()
            
            if audio is None:
                self._state_machine.force_idle("no_audio")
                self._update_indicator(AssistantState.IDLE)
                print("❌ No audio captured")
                return
            
            duration = len(audio) / self.config.sample_rate
            print(f"   ✓ Recorded {duration:.1f}s")
            
            # TRANSCRIBING
            self._state_machine.transition(AssistantState.TRANSCRIBING, "vad_complete")
            self._update_indicator(AssistantState.TRANSCRIBING)
            if self._audio_feedback:
                self._audio_feedback.play_listening_stop()
            
            print("🔄 Transcribing...")
            text = self._stt.transcribe(audio)
            
            if not text:
                self._state_machine.force_idle("stt_failed")
                self._update_indicator(AssistantState.IDLE)
                print("❌ No speech detected")
                return
            
            print(f"📝 You said: \"{text}\"")
            
            # Check for focus mode commands
            focus_level = self._focus.detect_activation(text)
            if focus_level:
                self._focus.activate(focus_level)
                self._speak("Focus mode on. I'll be brief.")
                self._state_machine.force_idle("focus_mode_activated")
                self._update_indicator(AssistantState.IDLE)
                return
            
            if self._focus.detect_deactivation(text):
                self._focus.deactivate()
                self._speak("Focus mode off.")
                self._state_machine.force_idle("focus_mode_deactivated")
                self._update_indicator(AssistantState.IDLE)
                return
            
            # THINKING
            self._state_machine.transition(AssistantState.THINKING, "stt_complete")
            self._update_indicator(AssistantState.THINKING)
            
            # Check for follow-up
            was_follow_up = False
            if self._follow_up.is_follow_up(text):
                was_follow_up = True
                result = self._follow_up.handle(text)
                if result:
                    self._handle_result(result, text, "follow_up", was_follow_up)
                    return
            
            # Normal intent classification
            print("🧠 Understanding...")
            intent = self._intent_engine.classify(text)
            
            print(f"   Intent: {intent.intent_type.value} ({intent.confidence:.0%})")
            
            # Check if confirmation needed
            assessment = self._confirmation.assess_action(
                intent.intent_type.value,
                text,
                intent.confidence,
            )
            
            if assessment.requires_confirmation:
                # Ask for confirmation
                self._speak(assessment.suggested_confirmation)
                self._confirmation.create_pending(
                    intent.intent_type.value, text, intent.slots, assessment
                )
                self._state_machine.force_idle("awaiting_confirmation")
                self._update_indicator(AssistantState.IDLE)
                return
            
            # EXECUTING
            self._state_machine.transition(AssistantState.EXECUTING, "intent_classified")
            self._update_indicator(AssistantState.EXECUTING)
            
            context = self._memory.get_context()
            result = self._executor.execute(intent, context)
            
            self._handle_result(result, text, intent.intent_type.value, was_follow_up)
            
        except Exception as e:
            logger.error(f"Session error: {e}")
            print(f"❌ Error: {e}")
            if self._audio_feedback:
                self._audio_feedback.play_error()
            self._state_machine.force_idle("error")
            self._update_indicator(AssistantState.ERROR)
            time.sleep(0.5)
            self._update_indicator(AssistantState.IDLE)
    
    def _handle_result(self, result: Dict[str, Any], text: str, 
                       intent_type: str, was_follow_up: bool):
        """Handle execution result."""
        print(f"💬 SAARTHI: {result['text']}")
        
        if result.get("source"):
            print(f"   📚 Source: {result['source']}")
        
        # Speak if needed
        if result.get("speak", False) and self._tts:
            self._state_machine.transition(AssistantState.SPEAKING, "needs_speech")
            self._update_indicator(AssistantState.SPEAKING)
            
            category = result.get("category", SpeechCategory.UNKNOWN)
            self._tts.speak(result["text"], category)
        
        # Record history
        if self._history:
            self._history.add(
                text=text,
                intent_type=intent_type,
                success=result.get("success", False),
                confidence=result.get("confidence", 0.0),
                was_follow_up=was_follow_up,
            )
        
        # Back to idle
        self._state_machine.force_idle("complete")
        self._update_indicator(AssistantState.IDLE)
        
        print("─" * 80)
        focus_badge = " [FOCUS]" if self._focus.is_active() else ""
        offline_badge = " [OFFLINE]" if self._offline.is_offline() else ""
        print(f"Ready{focus_badge}{offline_badge} | Sessions: {self._session_count} | "
              f"SPACE=speak F=focus M=metrics Q=quit")
    
    def _speak(self, text: str):
        """Speak text with TTS."""
        if self._tts:
            self._tts.speak(text, SpeechCategory.STATUS)
    
    def show_metrics(self):
        """Show metrics dashboard."""
        print("\n" + "=" * 80)
        print("📊 METRICS")
        print("=" * 80)
        
        summary = self._metrics.get_summary()
        
        # Latency
        print("\n⏱️  LATENCY:")
        for op, percentiles in summary.get("latency", {}).items():
            if percentiles.get("p50"):
                print(f"   {op:25s} P50:{percentiles['p50']:7.1f}ms  P90:{percentiles['p90']:7.1f}ms")
        
        # Usage stats
        print("\n📈 USAGE:")
        usage_stats = self._usage.get_statistics()
        for category, data in usage_stats.items():
            print(f"   {category}: {data['total_items']} items")
            for item in data['top_5'][:3]:
                print(f"      • {item['item']} (score: {item['score']})")
        
        print("\n" + "=" * 80)
    
    def show_history(self):
        """Show recent history."""
        print("\n" + "=" * 80)
        print("📜 RECENT HISTORY")
        print("=" * 80)
        
        entries = self._history.get_recent(10)
        for i, entry in enumerate(entries, 1):
            status = "✅" if entry.get("success") else "❌"
            follow_up = " (follow-up)" if entry.get("was_follow_up") else ""
            print(f"\n{i}. {status} \"{entry.get('text', '')[:50]}\"{follow_up}")
            print(f"   Intent: {entry.get('intent', 'N/A')}")
        
        print("\n" + "=" * 80)
    
    def show_status(self):
        """Show system status."""
        print("\n" + "=" * 80)
        print("📊 SYSTEM STATUS")
        print("=" * 80)
        
        # Connectivity
        print(f"\n🌐 Connectivity: {'Online' if self._offline.is_online() else 'OFFLINE'}")
        
        # Cache
        cache_stats = self._offline.get_cache_stats()
        print(f"💾 Offline cache: {cache_stats['entries']} / {cache_stats['max_entries']} entries")
        
        # Focus mode
        print(f"🎯 Focus mode: {'ON' if self._focus.is_active() else 'off'}")
        
        # Session memory
        session = self._memory.get_session_summary()
        print(f"🧠 Session: {session['command_count']} commands, "
              f"age: {session['session_age']:.0f}s")
        
        print("\n" + "=" * 80)
    
    def toggle_focus_mode(self):
        """Toggle focus mode."""
        if self._focus.is_active():
            self._focus.deactivate()
            print("🎯 Focus mode: OFF")
        else:
            self._focus.activate(FocusModeLevel.MINIMAL)
            print("🎯 Focus mode: ON (minimal chatter)")
        
        if self._indicator:
            self._indicator.set_focus_mode(self._focus.is_active())
    
    def _on_quit_request(self):
        """Handle quit request from tray."""
        self._running = False
    
    def run(self):
        """Main run loop."""
        if not self._initialized:
            if not self.initialize():
                return
        
        self._running = True
        print("🎯 Ready! Press SPACE to speak...")
        
        try:
            while self._running:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                    
                    if key == ' ':
                        self.handle_voice_session()
                    elif key == 'f':
                        self.toggle_focus_mode()
                    elif key == 'm':
                        self.show_metrics()
                    elif key == 'h':
                        self.show_history()
                    elif key == 's':
                        self.show_status()
                    elif key == 'q':
                        print("\n👋 Goodbye!")
                        break
                
                time.sleep(0.05)
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        self._running = False
        
        # Save usage stats
        if self._usage:
            self._usage.save(force=True)
        
        # Save history
        if self._history:
            self._history.save()
        
        # Stop indicator
        if self._indicator:
            self._indicator.stop()
        
        # Stop offline manager
        if self._offline:
            self._offline.stop()
        
        # Stop TTS
        if self._tts:
            self._tts.stop()
        
        logger.info("SAARTHI v4 cleaned up")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    print("\n🚀 Starting SAARTHI v4.0...\n")
    config = SaarthiConfigV4()
    assistant = SaarthiVoiceAssistantV4(config)
    assistant.run()


if __name__ == "__main__":
    main()
