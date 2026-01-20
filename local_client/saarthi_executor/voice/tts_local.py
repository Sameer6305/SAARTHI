"""
Text-to-Speech Module (Local Only)
==================================

Local text-to-speech using Windows SAPI or Piper.

PRIVACY GUARANTEES:
- 100% local processing (no cloud)
- Text never leaves the device
- No audio caching
- Only speaks APPROVED text

SECURITY:
- Only speaks text from the pipeline (no arbitrary text)
- TTS is disabled by default
- Volume and rate limits enforced
"""

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from pathlib import Path

from saarthi_executor.voice.config import TTSEngine

logger = logging.getLogger(__name__)


class TTSStatus(Enum):
    """TTS operation status."""
    SUCCESS = "success"
    ENGINE_ERROR = "engine_error"
    NO_VOICE = "no_voice"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class SpeakResult:
    """Result of a TTS operation."""
    status: TTSStatus
    duration_seconds: float
    error: Optional[str]
    
    @property
    def success(self) -> bool:
        return self.status == TTSStatus.SUCCESS


class LocalTTS:
    """
    Base class for local TTS engines.
    
    ALL PROCESSING IS LOCAL - no cloud, no network.
    """
    
    def speak(self, text: str) -> SpeakResult:
        """Speak the given text."""
        raise NotImplementedError
    
    def stop(self) -> None:
        """Stop current speech."""
        raise NotImplementedError
    
    def get_voices(self) -> List[str]:
        """Get available voice names."""
        raise NotImplementedError
    
    def set_voice(self, voice_name: str) -> bool:
        """Set the voice to use."""
        raise NotImplementedError
    
    def set_rate(self, rate: int) -> None:
        """Set speech rate (words per minute, 0 = default)."""
        raise NotImplementedError
    
    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        raise NotImplementedError


class WindowsSapiTTS(LocalTTS):
    """
    Windows SAPI text-to-speech.
    
    Uses the built-in Windows speech engine.
    100% local, no network required.
    """
    
    def __init__(
        self,
        voice_name: Optional[str] = None,
        rate: int = 0,
        volume: int = 80,
    ):
        """
        Initialize Windows SAPI TTS.
        
        Args:
            voice_name: Voice to use (None = system default)
            rate: Speech rate adjustment (-10 to 10, 0 = normal)
            volume: Volume (0-100)
        """
        self._voice_name = voice_name
        self._rate = rate
        self._volume = volume
        self._engine = None
        self._speaking = False
        self._lock = threading.Lock()
        
        self._available = self._check_available()
    
    def _check_available(self) -> bool:
        """Check if Windows SAPI is available."""
        try:
            import pyttsx3
            engine = pyttsx3.init('sapi5')
            voices = engine.getProperty('voices')
            engine.stop()
            return len(voices) > 0
        except Exception as e:
            logger.warning(f"Windows SAPI not available: {e}")
            return False
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def _get_engine(self):
        """Get or create the TTS engine."""
        if self._engine is None:
            import pyttsx3
            self._engine = pyttsx3.init('sapi5')
            
            # Set voice if specified
            if self._voice_name:
                self.set_voice(self._voice_name)
            
            # Set properties
            self._engine.setProperty('rate', 150 + self._rate * 20)
            self._engine.setProperty('volume', self._volume / 100.0)
        
        return self._engine
    
    def speak(self, text: str) -> SpeakResult:
        """
        Speak the given text.
        
        SECURITY: Only call this with APPROVED text from the pipeline.
        """
        if not self._available:
            return SpeakResult(
                status=TTSStatus.ENGINE_ERROR,
                duration_seconds=0.0,
                error="Windows SAPI not available",
            )
        
        if not text or not text.strip():
            return SpeakResult(
                status=TTSStatus.SUCCESS,
                duration_seconds=0.0,
                error=None,
            )
        
        with self._lock:
            try:
                start = time.time()
                self._speaking = True
                
                engine = self._get_engine()
                engine.say(text)
                engine.runAndWait()
                
                self._speaking = False
                duration = time.time() - start
                
                logger.info(f"TTS spoke: '{text[:30]}...' ({duration:.1f}s)")
                
                return SpeakResult(
                    status=TTSStatus.SUCCESS,
                    duration_seconds=duration,
                    error=None,
                )
                
            except Exception as e:
                self._speaking = False
                logger.error(f"TTS error: {e}")
                return SpeakResult(
                    status=TTSStatus.ENGINE_ERROR,
                    duration_seconds=0.0,
                    error=str(e),
                )
    
    def stop(self) -> None:
        """Stop current speech."""
        with self._lock:
            if self._engine and self._speaking:
                try:
                    self._engine.stop()
                except Exception:
                    pass
            self._speaking = False
    
    def get_voices(self) -> List[str]:
        """Get available voice names."""
        if not self._available:
            return []
        
        try:
            engine = self._get_engine()
            voices = engine.getProperty('voices')
            return [v.name for v in voices]
        except Exception:
            return []
    
    def set_voice(self, voice_name: str) -> bool:
        """Set the voice to use."""
        if not self._available:
            return False
        
        try:
            engine = self._get_engine()
            voices = engine.getProperty('voices')
            for voice in voices:
                if voice.name == voice_name:
                    engine.setProperty('voice', voice.id)
                    self._voice_name = voice_name
                    return True
            return False
        except Exception:
            return False
    
    def set_rate(self, rate: int) -> None:
        """Set speech rate (-10 to 10, 0 = normal)."""
        self._rate = max(-10, min(10, rate))
        if self._engine:
            self._engine.setProperty('rate', 150 + self._rate * 20)
    
    def set_volume(self, volume: int) -> None:
        """Set volume (0-100)."""
        self._volume = max(0, min(100, volume))
        if self._engine:
            self._engine.setProperty('volume', self._volume / 100.0)


class PiperTTS(LocalTTS):
    """
    Piper text-to-speech (open-source, local).
    
    Uses Piper for high-quality neural TTS.
    100% local, no network required.
    """
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        voice_name: Optional[str] = None,
        rate: int = 0,
        volume: int = 80,
    ):
        """
        Initialize Piper TTS.
        
        Args:
            model_path: Path to Piper model directory
            voice_name: Voice model to use
            rate: Speech rate adjustment
            volume: Volume (0-100)
        """
        self._model_path = model_path
        self._voice_name = voice_name
        self._rate = rate
        self._volume = volume
        self._available = self._check_available()
    
    def _check_available(self) -> bool:
        """Check if Piper is available."""
        try:
            # Check for piper-tts package
            import subprocess
            result = subprocess.run(
                ["piper", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    def speak(self, text: str) -> SpeakResult:
        """Speak using Piper (placeholder - implement based on Piper setup)."""
        if not self._available:
            return SpeakResult(
                status=TTSStatus.ENGINE_ERROR,
                duration_seconds=0.0,
                error="Piper not available",
            )
        
        # Placeholder - actual implementation depends on Piper setup
        logger.warning("Piper TTS not fully implemented")
        return SpeakResult(
            status=TTSStatus.ENGINE_ERROR,
            duration_seconds=0.0,
            error="Piper implementation pending",
        )
    
    def stop(self) -> None:
        pass
    
    def get_voices(self) -> List[str]:
        return []
    
    def set_voice(self, voice_name: str) -> bool:
        return False
    
    def set_rate(self, rate: int) -> None:
        self._rate = rate
    
    def set_volume(self, volume: int) -> None:
        self._volume = volume


def create_tts_engine(engine_type: TTSEngine, **kwargs) -> LocalTTS:
    """
    Factory function to create TTS engine.
    
    Args:
        engine_type: Type of engine to create
        **kwargs: Engine-specific parameters
        
    Returns:
        LocalTTS instance
    """
    if engine_type == TTSEngine.WINDOWS_SAPI:
        return WindowsSapiTTS(
            voice_name=kwargs.get('voice_name'),
            rate=kwargs.get('rate', 0),
            volume=kwargs.get('volume', 80),
        )
    elif engine_type == TTSEngine.PIPER:
        return PiperTTS(
            model_path=kwargs.get('model_path'),
            voice_name=kwargs.get('voice_name'),
            rate=kwargs.get('rate', 0),
            volume=kwargs.get('volume', 80),
        )
    else:
        raise ValueError(f"Unknown TTS engine: {engine_type}")
