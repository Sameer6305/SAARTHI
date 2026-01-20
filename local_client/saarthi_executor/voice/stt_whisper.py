"""
Speech-to-Text Module (Local Whisper)
=====================================

Local speech recognition using OpenAI Whisper.

PRIVACY GUARANTEES:
- 100% local processing (no cloud)
- Audio never leaves the device
- Audio discarded immediately after transcription
- No audio caching or storage

SECURITY:
- Audio buffer cleared after transcription
- Model runs in isolated thread
- Timeout enforced
- Low confidence results flagged
"""

import logging
import threading
import time
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from pathlib import Path

from saarthi_executor.voice.audio_capture import AudioBuffer
from saarthi_executor.voice.config import WhisperModel

logger = logging.getLogger(__name__)


class STTStatus(Enum):
    """STT processing status."""
    SUCCESS = "success"
    LOW_CONFIDENCE = "low_confidence"
    NO_SPEECH = "no_speech"
    TIMEOUT = "timeout"
    MODEL_ERROR = "model_error"
    AUDIO_ERROR = "audio_error"


@dataclass
class TranscriptionResult:
    """
    Result of speech-to-text transcription.
    
    IMPORTANT: The original audio is NOT stored here.
    Only the text result is kept.
    """
    status: STTStatus
    text: str
    confidence: float          # 0.0 to 1.0
    language: Optional[str]    # Detected language code
    duration_seconds: float    # Audio duration
    processing_seconds: float  # Time taken to transcribe
    is_ambiguous: bool         # True if needs confirmation
    error: Optional[str]
    
    @property
    def success(self) -> bool:
        return self.status == STTStatus.SUCCESS
    
    @property
    def needs_confirmation(self) -> bool:
        return self.is_ambiguous or self.status == STTStatus.LOW_CONFIDENCE


class LocalWhisperSTT:
    """
    Local Whisper speech-to-text engine.
    
    ALL PROCESSING IS LOCAL - no cloud, no network.
    """
    
    def __init__(
        self,
        model_name: WhisperModel = WhisperModel.TINY,
        model_path: Optional[Path] = None,
        device: str = "cpu",  # "cpu" or "cuda"
        timeout_seconds: float = 30.0,
        min_confidence: float = 0.3,
        ambiguous_confidence: float = 0.6,
    ):
        """
        Initialize Whisper STT.
        
        Args:
            model_name: Whisper model size
            model_path: Path to model (None = use default cache)
            device: Device to run on ("cpu" recommended for privacy)
            timeout_seconds: Max time for transcription
            min_confidence: Below this, reject as NO_SPEECH
            ambiguous_confidence: Below this, mark as ambiguous
        """
        self._model_name = model_name
        self._model_path = model_path
        self._device = device
        self._timeout = timeout_seconds
        self._min_confidence = min_confidence
        self._ambiguous_confidence = ambiguous_confidence
        
        self._model = None
        self._model_lock = threading.Lock()
        self._loaded = False
    
    @property
    def is_loaded(self) -> bool:
        """Whether the model is loaded."""
        return self._loaded
    
    def load_model(self) -> bool:
        """
        Load Whisper model.
        
        This may take a few seconds on first run (downloads model).
        Returns True if successful.
        """
        with self._model_lock:
            if self._loaded:
                return True
            
            try:
                import whisper
                
                logger.info(f"Loading Whisper model: {self._model_name.value}")
                start = time.time()
                
                self._model = whisper.load_model(
                    self._model_name.value,
                    device=self._device,
                    download_root=str(self._model_path) if self._model_path else None,
                )
                
                elapsed = time.time() - start
                logger.info(f"Whisper model loaded in {elapsed:.1f}s")
                
                self._loaded = True
                return True
                
            except ImportError:
                logger.error("Whisper not installed. Install with: pip install openai-whisper")
                return False
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                return False
    
    def unload_model(self) -> None:
        """Unload model to free memory."""
        with self._model_lock:
            if self._model:
                del self._model
                self._model = None
            self._loaded = False
            logger.info("Whisper model unloaded")
    
    def transcribe(self, audio: AudioBuffer) -> TranscriptionResult:
        """
        Transcribe audio to text.
        
        IMPORTANT: Audio is NOT stored. Only text result is returned.
        The caller is responsible for clearing the AudioBuffer after use.
        
        Args:
            audio: AudioBuffer containing the audio to transcribe
            
        Returns:
            TranscriptionResult with text and metadata
        """
        start_time = time.time()
        
        # Validate input
        if audio.data is None or len(audio.data) == 0:
            return TranscriptionResult(
                status=STTStatus.AUDIO_ERROR,
                text="",
                confidence=0.0,
                language=None,
                duration_seconds=0.0,
                processing_seconds=0.0,
                is_ambiguous=False,
                error="Empty audio buffer",
            )
        
        # Ensure model is loaded
        if not self._loaded and not self.load_model():
            return TranscriptionResult(
                status=STTStatus.MODEL_ERROR,
                text="",
                confidence=0.0,
                language=None,
                duration_seconds=audio.duration_seconds,
                processing_seconds=time.time() - start_time,
                is_ambiguous=False,
                error="Model not loaded",
            )
        
        try:
            # Run transcription in thread with timeout
            result = [None]
            error = [None]
            
            def do_transcribe():
                try:
                    # Ensure audio is float32 and correct sample rate
                    audio_data = audio.data.astype(np.float32)
                    
                    # Whisper expects audio at 16kHz
                    if audio.sample_rate != 16000:
                        # Resample if needed (rare case)
                        import scipy.signal as signal
                        samples = int(len(audio_data) * 16000 / audio.sample_rate)
                        audio_data = signal.resample(audio_data, samples)
                    
                    # Transcribe
                    with self._model_lock:
                        if self._model is None:
                            error[0] = "Model unloaded during transcription"
                            return
                        
                        # Using transcribe with optimized settings
                        transcription = self._model.transcribe(
                            audio_data,
                            language="en",          # Force English for accuracy
                            fp16=False,             # CPU compatibility
                            verbose=False,
                            task="transcribe",      # Not translate
                            temperature=0.0,        # Deterministic output
                            best_of=5,              # More candidates for accuracy
                            beam_size=5,            # Better beam search
                            condition_on_previous_text=False,  # Don't hallucinate
                            initial_prompt="Voice command: ",  # Hint it's a command
                        )
                    
                    result[0] = transcription
                    
                except Exception as e:
                    error[0] = str(e)
            
            # Run with timeout
            thread = threading.Thread(target=do_transcribe, daemon=True)
            thread.start()
            thread.join(timeout=self._timeout)
            
            processing_time = time.time() - start_time
            
            if thread.is_alive():
                # Timeout
                logger.warning("STT timeout exceeded")
                return TranscriptionResult(
                    status=STTStatus.TIMEOUT,
                    text="",
                    confidence=0.0,
                    language=None,
                    duration_seconds=audio.duration_seconds,
                    processing_seconds=processing_time,
                    is_ambiguous=False,
                    error=f"Transcription timed out after {self._timeout}s",
                )
            
            if error[0]:
                return TranscriptionResult(
                    status=STTStatus.MODEL_ERROR,
                    text="",
                    confidence=0.0,
                    language=None,
                    duration_seconds=audio.duration_seconds,
                    processing_seconds=processing_time,
                    is_ambiguous=False,
                    error=error[0],
                )
            
            if result[0] is None:
                return TranscriptionResult(
                    status=STTStatus.MODEL_ERROR,
                    text="",
                    confidence=0.0,
                    language=None,
                    duration_seconds=audio.duration_seconds,
                    processing_seconds=processing_time,
                    is_ambiguous=False,
                    error="No result from transcription",
                )
            
            # Extract results
            transcription = result[0]
            text = transcription.get("text", "").strip()
            language = transcription.get("language", "en")
            
            # Calculate confidence from segments
            segments = transcription.get("segments", [])
            if segments:
                # Average no_speech_prob (lower = more confident)
                no_speech_probs = [s.get("no_speech_prob", 0.5) for s in segments]
                avg_no_speech = sum(no_speech_probs) / len(no_speech_probs)
                confidence = 1.0 - avg_no_speech
            else:
                confidence = 0.5 if text else 0.0
            
            # Determine status
            if not text or confidence < self._min_confidence:
                status = STTStatus.NO_SPEECH
                is_ambiguous = False
            elif confidence < self._ambiguous_confidence:
                status = STTStatus.LOW_CONFIDENCE
                is_ambiguous = True
            else:
                status = STTStatus.SUCCESS
                is_ambiguous = False
            
            logger.info(f"Transcription: '{text[:50]}...' (confidence: {confidence:.2f})")
            
            return TranscriptionResult(
                status=status,
                text=text,
                confidence=confidence,
                language=language,
                duration_seconds=audio.duration_seconds,
                processing_seconds=processing_time,
                is_ambiguous=is_ambiguous,
                error=None,
            )
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return TranscriptionResult(
                status=STTStatus.MODEL_ERROR,
                text="",
                confidence=0.0,
                language=None,
                duration_seconds=audio.duration_seconds,
                processing_seconds=time.time() - start_time,
                is_ambiguous=False,
                error=str(e),
            )
    
    def transcribe_and_clear(self, audio: AudioBuffer) -> TranscriptionResult:
        """
        Transcribe audio and immediately clear the buffer.
        
        This is the RECOMMENDED method - ensures audio is discarded.
        """
        try:
            return self.transcribe(audio)
        finally:
            audio.clear()
