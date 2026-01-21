"""
Local Text-to-Speech System
===========================

FREE, LOCAL TTS with robotic, deep, cinematic voice.

ARCHITECTURE:
┌─────────────────────────────────────────────────────────┐
│                    TTSManager                           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│  │  Piper TTS  │───▶│ Audio FX    │───▶│  Playback   │ │
│  │  (Primary)  │    │ (Robotic)   │    │  (Async)    │ │
│  └──────┬──────┘    └─────────────┘    └─────────────┘ │
│         │ fallback                                      │
│         ▼                                               │
│  ┌─────────────┐                                        │
│  │ Windows SAPI│                                        │
│  │ (Fallback)  │                                        │
│  └─────────────┘                                        │
└─────────────────────────────────────────────────────────┘

VOICE OPTIONS COMPARISON:
┌────────────────┬──────────┬─────────┬──────────┬─────────────┐
│ Engine         │ Latency  │ Quality │ Robotic  │ Setup       │
├────────────────┼──────────┼─────────┼──────────┼─────────────┤
│ Piper TTS      │ ~50ms    │ High    │ Via FX   │ Model DL    │
│ Coqui TTS      │ ~500ms   │ High    │ Via FX   │ Heavy       │
│ Windows SAPI   │ ~20ms    │ Medium  │ Native   │ Built-in    │
└────────────────┴──────────┴─────────┴──────────┴─────────────┘

RECOMMENDED: Piper TTS (fast, high quality, easy setup)
FALLBACK: Windows SAPI (always available, no setup)
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Callable
import threading
import queue
import time
import os


class TTSEngine(Enum):
    """Available TTS engines."""
    PIPER = "piper"          # Primary: Fast, high quality
    SAPI = "sapi"            # Fallback: Windows built-in
    COQUI = "coqui"          # Alternative: Heavy but flexible


@dataclass
class VoiceProfile:
    """
    Voice profile for robotic, deep, cinematic tone.
    
    TUNING GUIDE:
    - pitch: -20 to +20 (negative = deeper)
    - rate: 0.5 to 2.0 (lower = slower, more dramatic)
    - volume: 0.0 to 1.0
    - robotize: Apply robotic effect
    - reverb: Add cinematic reverb
    """
    name: str = "SAARTHI"
    pitch: int = -8               # Deep voice
    rate: float = 0.85            # Slightly slower for drama
    volume: float = 0.9
    
    # Robotic effects
    robotize: bool = True         # Apply robotic modulation
    robot_freq: float = 30.0      # Robot modulation frequency (Hz)
    robot_depth: float = 0.3      # Robot effect depth (0-1)
    
    # Cinematic effects
    reverb: bool = True           # Add reverb for cinematic feel
    reverb_room: float = 0.3      # Room size (0-1)
    reverb_damp: float = 0.5      # Damping (0-1)
    
    # Voice model (for Piper)
    piper_model: str = "en_US-ryan-medium"  # Deep male voice
    piper_speaker: int = 0


@dataclass
class TTSConfig:
    """TTS system configuration."""
    # Engine selection
    primary_engine: TTSEngine = TTSEngine.PIPER
    fallback_engine: TTSEngine = TTSEngine.SAPI
    
    # Voice profile
    voice: VoiceProfile = field(default_factory=VoiceProfile)
    
    # Performance
    async_playback: bool = True   # Non-blocking playback
    cache_audio: bool = True      # Cache generated audio
    max_cache_size: int = 50      # Max cached phrases
    
    # Paths
    piper_path: Path = field(default_factory=lambda: Path.home() / ".saarthi" / "piper")
    cache_path: Path = field(default_factory=lambda: Path.home() / ".saarthi" / "tts_cache")
    
    # Latency optimization
    preload_engine: bool = True   # Load engine at startup
    chunk_long_text: bool = True  # Stream long text in chunks
    chunk_size: int = 100         # Characters per chunk


# =============================================================================
# PIPER TTS ENGINE (PRIMARY - RECOMMENDED)
# =============================================================================

class PiperTTS:
    """
    Piper TTS - Fast, high-quality local TTS.
    
    SETUP:
    1. Download piper.exe from https://github.com/rhasspy/piper/releases
    2. Download voice model (en_US-ryan-medium recommended for deep voice)
    3. Place in ~/.saarthi/piper/
    
    MODELS FOR DEEP/ROBOTIC VOICE:
    - en_US-ryan-medium (Male, deep, clear) ← RECOMMENDED
    - en_US-joe-medium (Male, deeper)
    - en_GB-alan-medium (Male, British, authoritative)
    
    LATENCY: ~50-100ms for short phrases
    """
    
    # Model download URLs
    MODELS = {
        "en_US-ryan-medium": {
            "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
            "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json",
        },
        "en_US-joe-medium": {
            "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/joe/medium/en_US-joe-medium.onnx",
            "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/joe/medium/en_US-joe-medium.onnx.json",
        },
    }
    
    def __init__(self, config: TTSConfig):
        self.config = config
        self._piper_exe: Optional[Path] = None
        self._model_path: Optional[Path] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize Piper TTS engine."""
        piper_dir = self.config.piper_path
        piper_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for piper executable
        self._piper_exe = piper_dir / "piper.exe"
        if not self._piper_exe.exists():
            print(f"[TTS] Piper not found at {self._piper_exe}")
            print("[TTS] Download from: https://github.com/rhasspy/piper/releases")
            return False
        
        # Check for model
        model_name = self.config.voice.piper_model
        self._model_path = piper_dir / f"{model_name}.onnx"
        
        if not self._model_path.exists():
            print(f"[TTS] Model not found: {self._model_path}")
            print(f"[TTS] Download model: {self.MODELS.get(model_name, {}).get('model', 'unknown')}")
            return False
        
        self._initialized = True
        print(f"[TTS] Piper initialized with model: {model_name}")
        return True
    
    def synthesize(self, text: str, output_path: Path) -> bool:
        """
        Synthesize text to audio file.
        
        Returns True on success.
        """
        if not self._initialized:
            return False
        
        import subprocess
        
        try:
            # Run piper to generate audio
            cmd = [
                str(self._piper_exe),
                "--model", str(self._model_path),
                "--output_file", str(output_path),
            ]
            
            # Pass text via stdin for security
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            return result.returncode == 0 and output_path.exists()
            
        except Exception as e:
            print(f"[TTS] Piper synthesis failed: {e}")
            return False
    
    def synthesize_stream(self, text: str) -> Optional[bytes]:
        """Synthesize to raw audio bytes (for streaming)."""
        if not self._initialized:
            return None
        
        import subprocess
        
        try:
            cmd = [
                str(self._piper_exe),
                "--model", str(self._model_path),
                "--output-raw",
            ]
            
            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode == 0:
                return result.stdout.encode('latin-1')  # Raw bytes
            return None
            
        except Exception:
            return None


# =============================================================================
# WINDOWS SAPI ENGINE (FALLBACK)
# =============================================================================

class WindowsSAPI:
    """
    Windows SAPI - Built-in Windows TTS.
    
    PROS:
    - Always available on Windows
    - Zero setup required
    - Very low latency (~20ms)
    - Native robotic effect support
    
    CONS:
    - Lower quality than neural TTS
    - Limited voice options
    
    ROBOTIC EFFECT:
    Use SSML to create robotic voice:
    - Low pitch (-10)
    - Slow rate (slow)
    - Emphasis on syllables
    """
    
    def __init__(self, config: TTSConfig):
        self.config = config
        self._engine = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize Windows SAPI."""
        try:
            import win32com.client
            self._engine = win32com.client.Dispatch("SAPI.SpVoice")
            
            # List available voices
            voices = self._engine.GetVoices()
            print(f"[TTS] SAPI voices available: {voices.Count}")
            
            # Try to find a deep male voice
            for i in range(voices.Count):
                voice = voices.Item(i)
                desc = voice.GetDescription()
                print(f"[TTS]   - {desc}")
                
                # Prefer David (deep male) or Mark
                if "David" in desc or "Mark" in desc:
                    self._engine.Voice = voice
                    print(f"[TTS] Selected voice: {desc}")
                    break
            
            # Apply voice settings
            voice_config = self.config.voice
            
            # Rate: -10 (slowest) to 10 (fastest), default 0
            # Map 0.5-2.0 to -10 to 10
            rate = int((voice_config.rate - 1.0) * 10)
            self._engine.Rate = max(-10, min(10, rate))
            
            # Volume: 0-100
            self._engine.Volume = int(voice_config.volume * 100)
            
            self._initialized = True
            print(f"[TTS] SAPI initialized (rate={rate}, volume={voice_config.volume})")
            return True
            
        except ImportError:
            print("[TTS] pywin32 not installed. Run: pip install pywin32")
            return False
        except Exception as e:
            print(f"[TTS] SAPI initialization failed: {e}")
            return False
    
    def speak(self, text: str, wait: bool = True) -> bool:
        """Speak text directly (no file)."""
        if not self._initialized or not self._engine:
            return False
        
        try:
            # Create SSML for robotic effect
            ssml = self._create_robotic_ssml(text)
            
            # Flags: 0 = sync, 1 = async
            flags = 0 if wait else 1
            
            # Use SSML
            self._engine.Speak(ssml, flags)
            return True
            
        except Exception as e:
            print(f"[TTS] SAPI speak failed: {e}")
            return False
    
    def _create_robotic_ssml(self, text: str) -> str:
        """Create SSML with robotic voice effect."""
        voice = self.config.voice
        
        # SSML for robotic effect
        # - pitch: -10 (50%) to +10 (150%)
        # - rate: x-slow, slow, medium, fast, x-fast
        # - emphasis: strong for robotic punch
        
        # Map pitch (-20 to +20) to SSML format
        pitch_val = voice.pitch  # e.g., -8
        pitch_str = f"{pitch_val:+d}st" if pitch_val != 0 else "default"
        
        # Map rate (0.5-2.0) to SSML
        if voice.rate < 0.7:
            rate_str = "x-slow"
        elif voice.rate < 0.9:
            rate_str = "slow"
        elif voice.rate < 1.1:
            rate_str = "medium"
        elif voice.rate < 1.5:
            rate_str = "fast"
        else:
            rate_str = "x-fast"
        
        # Build SSML
        ssml = f"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">
            <prosody pitch="{pitch_str}" rate="{rate_str}">
                <emphasis level="moderate">{text}</emphasis>
            </prosody>
        </speak>"""
        
        return ssml
    
    def synthesize_to_file(self, text: str, output_path: Path) -> bool:
        """Synthesize to WAV file."""
        if not self._initialized or not self._engine:
            return False
        
        try:
            import win32com.client
            
            # Create file stream
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            stream.Open(str(output_path), 3)  # 3 = SSFMCreateForWrite
            
            # Redirect output to file
            old_stream = self._engine.AudioOutputStream
            self._engine.AudioOutputStream = stream
            
            # Synthesize
            ssml = self._create_robotic_ssml(text)
            self._engine.Speak(ssml, 0)
            
            # Restore and close
            self._engine.AudioOutputStream = old_stream
            stream.Close()
            
            return output_path.exists()
            
        except Exception as e:
            print(f"[TTS] SAPI file synthesis failed: {e}")
            return False


# =============================================================================
# AUDIO EFFECTS (ROBOTIC/CINEMATIC)
# =============================================================================

class AudioEffects:
    """
    Audio effects for robotic, cinematic voice.
    
    EFFECTS CHAIN:
    Raw Audio → Pitch Shift → Robot Modulation → Reverb → Output
    
    ROBOTIC EFFECT:
    - Ring modulation at 30-50 Hz
    - Slight vocoder effect
    - Metallic resonance
    
    CINEMATIC:
    - Subtle reverb (room size 0.2-0.4)
    - Low-end boost
    - Compression for punch
    """
    
    @staticmethod
    def apply_robotic_effect(
        audio_data: bytes,
        sample_rate: int = 22050,
        robot_freq: float = 30.0,
        depth: float = 0.3,
    ) -> bytes:
        """
        Apply robotic modulation effect.
        
        Uses ring modulation to create metallic, robotic tone.
        """
        try:
            import numpy as np
            
            # Convert bytes to numpy array
            audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # Normalize
            audio = audio / 32768.0
            
            # Create modulation signal (sine wave)
            t = np.arange(len(audio)) / sample_rate
            modulator = np.sin(2 * np.pi * robot_freq * t)
            
            # Apply ring modulation
            modulated = audio * (1 - depth + depth * modulator)
            
            # Add slight chorus for metallic effect
            delay_samples = int(0.02 * sample_rate)  # 20ms delay
            if len(audio) > delay_samples:
                chorus = np.zeros_like(audio)
                chorus[delay_samples:] = audio[:-delay_samples] * 0.3
                modulated = modulated + chorus
            
            # Normalize and convert back
            modulated = np.clip(modulated, -1.0, 1.0)
            modulated = (modulated * 32767).astype(np.int16)
            
            return modulated.tobytes()
            
        except ImportError:
            print("[TTS] numpy not available for audio effects")
            return audio_data
        except Exception as e:
            print(f"[TTS] Audio effect failed: {e}")
            return audio_data
    
    @staticmethod
    def apply_pitch_shift(
        audio_data: bytes,
        sample_rate: int = 22050,
        semitones: int = -8,
    ) -> bytes:
        """
        Shift pitch down for deeper voice.
        
        Uses simple resampling method (fast but lower quality).
        """
        try:
            import numpy as np
            
            audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            
            # Simple pitch shift via resampling
            # Negative semitones = lower pitch = stretch audio
            factor = 2 ** (-semitones / 12)
            
            # Resample
            indices = np.arange(0, len(audio), factor)
            indices = indices[indices < len(audio) - 1].astype(int)
            shifted = audio[indices]
            
            return shifted.astype(np.int16).tobytes()
            
        except ImportError:
            return audio_data
        except Exception:
            return audio_data
    
    @staticmethod
    def apply_reverb(
        audio_data: bytes,
        sample_rate: int = 22050,
        room_size: float = 0.3,
        damping: float = 0.5,
    ) -> bytes:
        """
        Apply simple reverb for cinematic feel.
        
        Uses comb filter approach for fast processing.
        """
        try:
            import numpy as np
            
            audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio = audio / 32768.0
            
            # Simple comb filter reverb
            delay_ms = int(room_size * 100)  # 10-100ms
            delay_samples = int(delay_ms * sample_rate / 1000)
            
            if len(audio) > delay_samples:
                reverbed = audio.copy()
                decay = 1.0 - damping
                
                for i in range(delay_samples, len(audio)):
                    reverbed[i] += reverbed[i - delay_samples] * decay * 0.5
                
                # Mix dry and wet
                mix = 0.3  # 30% reverb
                output = audio * (1 - mix) + reverbed * mix
                
                output = np.clip(output, -1.0, 1.0)
                return (output * 32767).astype(np.int16).tobytes()
            
            return audio_data
            
        except ImportError:
            return audio_data
        except Exception:
            return audio_data


# =============================================================================
# TTS MANAGER (MAIN INTERFACE)
# =============================================================================

class TTSManager:
    """
    Main TTS manager with engine fallback and async playback.
    
    USAGE:
    ```python
    tts = TTSManager()
    tts.initialize()
    
    # Simple speak (async)
    tts.speak("Hello, I am SAARTHI")
    
    # Wait for completion
    tts.speak("Processing your request", wait=True)
    
    # Check if speaking
    if tts.is_speaking:
        tts.stop()
    ```
    """
    
    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        
        self._piper: Optional[PiperTTS] = None
        self._sapi: Optional[WindowsSAPI] = None
        self._active_engine: Optional[TTSEngine] = None
        
        self._audio_queue: queue.Queue = queue.Queue()
        self._playback_thread: Optional[threading.Thread] = None
        self._is_speaking = False
        self._stop_flag = False
        
        # Audio cache
        self._cache: dict = {}
        
        # Effects processor
        self._effects = AudioEffects()
    
    @property
    def is_speaking(self) -> bool:
        return self._is_speaking
    
    def initialize(self) -> bool:
        """Initialize TTS engines."""
        print("[TTS] Initializing TTS system...")
        
        # Try primary engine (Piper)
        if self.config.primary_engine == TTSEngine.PIPER:
            self._piper = PiperTTS(self.config)
            if self._piper.initialize():
                self._active_engine = TTSEngine.PIPER
                print("[TTS] Primary engine: Piper")
            else:
                print("[TTS] Piper not available, trying fallback...")
        
        # Initialize fallback (SAPI)
        self._sapi = WindowsSAPI(self.config)
        if self._sapi.initialize():
            if self._active_engine is None:
                self._active_engine = TTSEngine.SAPI
                print("[TTS] Using fallback engine: Windows SAPI")
        
        if self._active_engine is None:
            print("[TTS] ERROR: No TTS engine available!")
            return False
        
        # Start playback thread
        if self.config.async_playback:
            self._playback_thread = threading.Thread(
                target=self._playback_loop,
                daemon=True,
            )
            self._playback_thread.start()
        
        # Create cache directory
        self.config.cache_path.mkdir(parents=True, exist_ok=True)
        
        print("[TTS] TTS system ready!")
        return True
    
    def speak(self, text: str, wait: bool = False) -> bool:
        """
        Speak text.
        
        Args:
            text: Text to speak
            wait: If True, block until speech completes
        
        Returns:
            True if speech started successfully
        """
        if not self._active_engine:
            print("[TTS] Not initialized")
            return False
        
        if not text.strip():
            return False
        
        # Check cache
        cache_key = hash(text)
        if self.config.cache_audio and cache_key in self._cache:
            audio_data = self._cache[cache_key]
            return self._play_audio(audio_data, wait)
        
        # Use SAPI for direct speech (fastest)
        if self._active_engine == TTSEngine.SAPI and self._sapi:
            return self._sapi.speak(text, wait)
        
        # Use Piper with effects
        if self._active_engine == TTSEngine.PIPER and self._piper:
            return self._speak_with_piper(text, wait)
        
        return False
    
    def _speak_with_piper(self, text: str, wait: bool) -> bool:
        """Speak using Piper with robotic effects."""
        import tempfile
        
        # Generate to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)
        
        if not self._piper.synthesize(text, temp_path):
            # Fallback to SAPI
            if self._sapi:
                return self._sapi.speak(text, wait)
            return False
        
        # Read audio and apply effects
        try:
            with open(temp_path, "rb") as f:
                audio_data = f.read()
            
            # Apply robotic effects if enabled
            voice = self.config.voice
            if voice.robotize:
                # Skip WAV header (44 bytes)
                header = audio_data[:44]
                raw_audio = audio_data[44:]
                
                raw_audio = self._effects.apply_robotic_effect(
                    raw_audio,
                    robot_freq=voice.robot_freq,
                    depth=voice.robot_depth,
                )
                
                audio_data = header + raw_audio
            
            # Cache if enabled
            if self.config.cache_audio:
                cache_key = hash(text)
                self._cache[cache_key] = audio_data
                
                # Trim cache
                while len(self._cache) > self.config.max_cache_size:
                    self._cache.pop(next(iter(self._cache)))
            
            # Play audio
            return self._play_audio(audio_data, wait)
            
        finally:
            # Cleanup temp file
            try:
                temp_path.unlink()
            except:
                pass
    
    def _play_audio(self, audio_data: bytes, wait: bool) -> bool:
        """Play audio data."""
        if self.config.async_playback and not wait:
            self._audio_queue.put(audio_data)
            return True
        else:
            return self._play_audio_sync(audio_data)
    
    def _play_audio_sync(self, audio_data: bytes) -> bool:
        """Play audio synchronously."""
        try:
            import winsound
            import io
            
            # winsound can play from memory
            winsound.PlaySound(audio_data, winsound.SND_MEMORY)
            return True
            
        except Exception as e:
            print(f"[TTS] Playback failed: {e}")
            return False
    
    def _playback_loop(self):
        """Background thread for async playback."""
        while True:
            try:
                audio_data = self._audio_queue.get(timeout=1.0)
                
                if self._stop_flag:
                    continue
                
                self._is_speaking = True
                self._play_audio_sync(audio_data)
                self._is_speaking = False
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[TTS] Playback loop error: {e}")
                self._is_speaking = False
    
    def stop(self):
        """Stop current speech."""
        self._stop_flag = True
        
        # Clear queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except:
                break
        
        self._stop_flag = False
        self._is_speaking = False
    
    def shutdown(self):
        """Shutdown TTS system."""
        self.stop()
        print("[TTS] TTS system shutdown")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_global_tts: Optional[TTSManager] = None

def get_tts() -> TTSManager:
    """Get or create global TTS instance."""
    global _global_tts
    if _global_tts is None:
        _global_tts = TTSManager()
        _global_tts.initialize()
    return _global_tts

def speak(text: str, wait: bool = False) -> bool:
    """Convenience function to speak text."""
    return get_tts().speak(text, wait)

def stop_speaking():
    """Stop current speech."""
    get_tts().stop()
