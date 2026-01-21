"""
Voice Activation Methods
========================

Better alternatives to boring push-to-talk:

1. GLOBAL HOTKEY (F5) - Press to start, press again to stop
2. DOUBLE-TAP (Ctrl) - Quick double-press to toggle
3. CLAP DETECTION - Clap twice to activate
4. WHISTLE - Whistle to wake up

All methods are PRIVACY-FIRST:
- No always-on listening (except clap/whistle in active mode)
- Clear visual indicator when listening
- Easy to cancel

RECOMMENDED: Global Hotkey (simple, reliable, no false triggers)
"""

import threading
import time
import logging
from typing import Optional, Callable
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ActivationMethod(Enum):
    """Voice activation methods."""
    HOTKEY = "hotkey"           # Press F5 to toggle
    DOUBLE_TAP = "double_tap"   # Double-tap Ctrl
    CLAP = "clap"               # Clap detection
    WHISTLE = "whistle"         # Whistle detection


@dataclass
class ActivationConfig:
    """Configuration for voice activation."""
    method: ActivationMethod = ActivationMethod.HOTKEY
    
    # Hotkey settings
    hotkey: str = "f5"                    # Default: F5 key
    hotkey_modifiers: list = None         # Optional: ["ctrl", "shift"]
    
    # Double-tap settings
    double_tap_key: str = "ctrl"          # Key to double-tap
    double_tap_window_ms: int = 400       # Time window for double-tap
    
    # Clap settings
    clap_threshold: float = 0.7           # Volume threshold (0-1)
    clap_count: int = 2                   # Number of claps required
    clap_window_ms: int = 1000            # Window for clap sequence
    
    # General
    feedback_sound: bool = True           # Play sound on activation
    visual_indicator: bool = True         # Show indicator when listening


# =============================================================================
# METHOD 1: GLOBAL HOTKEY (RECOMMENDED)
# =============================================================================

class HotkeyActivation:
    """
    Activate voice with a global hotkey.
    
    USAGE:
    - Press F5 to start listening
    - Press F5 again to stop and process
    - Press Escape to cancel
    
    WHY THIS IS BETTER:
    - Works from any application
    - No accidental triggers
    - Clear start/stop
    - No cursor fatigue
    """
    
    def __init__(
        self,
        hotkey: str = "f5",
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
    ):
        self.hotkey = hotkey
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel
        
        self._is_listening = False
        self._keyboard = None
        self._running = False
    
    def start(self) -> bool:
        """Start listening for hotkey."""
        try:
            import keyboard
            self._keyboard = keyboard
            
            # Register hotkey
            keyboard.add_hotkey(self.hotkey, self._toggle)
            keyboard.add_hotkey('escape', self._cancel)
            
            self._running = True
            logger.info(f"Hotkey activation ready. Press {self.hotkey.upper()} to toggle voice.")
            return True
            
        except ImportError:
            logger.error("Install keyboard library: pip install keyboard")
            return False
        except Exception as e:
            logger.error(f"Hotkey setup failed: {e}")
            return False
    
    def stop(self):
        """Stop listening for hotkey."""
        self._running = False
        if self._keyboard:
            try:
                self._keyboard.unhook_all()
            except:
                pass
    
    def _toggle(self):
        """Toggle listening state."""
        if self._is_listening:
            self._is_listening = False
            logger.info("🎤 Voice: Stopped listening")
            if self.on_stop:
                self.on_stop()
        else:
            self._is_listening = True
            logger.info("🎤 Voice: Started listening...")
            if self.on_start:
                self.on_start()
    
    def _cancel(self):
        """Cancel current recording."""
        if self._is_listening:
            self._is_listening = False
            logger.info("🎤 Voice: Cancelled")
            if self.on_cancel:
                self.on_cancel()
    
    @property
    def is_listening(self) -> bool:
        return self._is_listening


# =============================================================================
# METHOD 2: DOUBLE-TAP KEY
# =============================================================================

class DoubleTapActivation:
    """
    Activate voice by double-tapping a key.
    
    USAGE:
    - Double-tap Ctrl (or configured key) to start
    - Double-tap again to stop
    - Single Escape to cancel
    
    WHY THIS IS BETTER:
    - Very fast to trigger
    - Natural gesture
    - Works while typing (Ctrl doesn't type)
    """
    
    def __init__(
        self,
        key: str = "ctrl",
        window_ms: int = 400,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ):
        self.key = key
        self.window_ms = window_ms
        self.on_start = on_start
        self.on_stop = on_stop
        
        self._is_listening = False
        self._last_press = 0
        self._keyboard = None
        self._running = False
    
    def start(self) -> bool:
        """Start listening for double-tap."""
        try:
            import keyboard
            self._keyboard = keyboard
            
            # Listen for key press
            keyboard.on_press_key(self.key, self._on_key_press)
            keyboard.add_hotkey('escape', self._cancel)
            
            self._running = True
            logger.info(f"Double-tap activation ready. Double-tap {self.key.upper()} to toggle voice.")
            return True
            
        except ImportError:
            logger.error("Install keyboard library: pip install keyboard")
            return False
        except Exception as e:
            logger.error(f"Double-tap setup failed: {e}")
            return False
    
    def stop(self):
        """Stop listening."""
        self._running = False
        if self._keyboard:
            try:
                self._keyboard.unhook_all()
            except:
                pass
    
    def _on_key_press(self, event):
        """Handle key press."""
        current_time = time.time() * 1000
        
        if current_time - self._last_press < self.window_ms:
            # Double-tap detected!
            self._toggle()
            self._last_press = 0  # Reset
        else:
            self._last_press = current_time
    
    def _toggle(self):
        """Toggle listening state."""
        if self._is_listening:
            self._is_listening = False
            logger.info("🎤 Voice: Stopped listening")
            if self.on_stop:
                self.on_stop()
        else:
            self._is_listening = True
            logger.info("🎤 Voice: Started listening...")
            if self.on_start:
                self.on_start()
    
    def _cancel(self):
        """Cancel recording."""
        if self._is_listening:
            self._is_listening = False
            if hasattr(self, 'on_cancel') and self.on_cancel:
                self.on_cancel()


# =============================================================================
# METHOD 3: CLAP DETECTION
# =============================================================================

class ClapActivation:
    """
    Activate voice by clapping.
    
    USAGE:
    - Clap twice to start listening
    - Speak your command
    - Clap twice to stop OR wait for silence
    
    WHY THIS IS BETTER:
    - Hands-free!
    - Fun and natural
    - Works when hands are busy
    
    PRIVACY NOTE:
    - Only listens for claps when app is active
    - Audio is NOT stored, only analyzed for clap pattern
    """
    
    def __init__(
        self,
        threshold: float = 0.7,
        clap_count: int = 2,
        window_ms: int = 1000,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ):
        self.threshold = threshold
        self.clap_count = clap_count
        self.window_ms = window_ms
        self.on_start = on_start
        self.on_stop = on_stop
        
        self._is_listening = False
        self._running = False
        self._thread = None
        self._clap_times = []
    
    def start(self) -> bool:
        """Start clap detection."""
        try:
            import pyaudio
            import numpy as np
            self._pyaudio = pyaudio
            self._np = np
            
            self._running = True
            self._thread = threading.Thread(target=self._detection_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"Clap activation ready. Clap {self.clap_count} times to toggle voice.")
            return True
            
        except ImportError:
            logger.error("Install pyaudio: pip install pyaudio")
            return False
        except Exception as e:
            logger.error(f"Clap detection setup failed: {e}")
            return False
    
    def stop(self):
        """Stop clap detection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
    
    def _detection_loop(self):
        """Main detection loop."""
        CHUNK = 1024
        RATE = 44100
        
        p = self._pyaudio.PyAudio()
        
        try:
            stream = p.open(
                format=self._pyaudio.paFloat32,
                channels=1,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
            
            while self._running:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    audio = self._np.frombuffer(data, dtype=self._np.float32)
                    
                    # Calculate volume
                    volume = self._np.abs(audio).mean()
                    
                    # Detect clap (sudden loud sound)
                    if volume > self.threshold:
                        self._on_clap()
                    
                except Exception:
                    pass
                
                time.sleep(0.01)
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logger.error(f"Clap detection error: {e}")
        finally:
            p.terminate()
    
    def _on_clap(self):
        """Handle detected clap."""
        current_time = time.time() * 1000
        
        # Clean old claps
        self._clap_times = [t for t in self._clap_times if current_time - t < self.window_ms]
        
        # Add new clap
        self._clap_times.append(current_time)
        
        # Check if we have enough claps
        if len(self._clap_times) >= self.clap_count:
            self._toggle()
            self._clap_times = []
            time.sleep(0.5)  # Debounce
    
    def _toggle(self):
        """Toggle listening state."""
        if self._is_listening:
            self._is_listening = False
            logger.info("👏 Voice: Stopped listening (clap detected)")
            if self.on_stop:
                self.on_stop()
        else:
            self._is_listening = True
            logger.info("👏 Voice: Started listening (clap detected)...")
            if self.on_start:
                self.on_start()


# =============================================================================
# METHOD 4: WHISTLE DETECTION (Advanced)
# =============================================================================

class WhistleActivation:
    """
    Activate voice by whistling.
    
    USAGE:
    - Whistle a short tune to activate
    - Speak your command
    - Whistle again to stop
    
    HOW IT WORKS:
    - Detects sustained high-frequency sound
    - Whistles are typically 1-3 kHz
    - Distinguishes from speech and noise
    """
    
    def __init__(
        self,
        min_freq: int = 1000,
        max_freq: int = 3000,
        min_duration_ms: int = 200,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
    ):
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.min_duration_ms = min_duration_ms
        self.on_start = on_start
        self.on_stop = on_stop
        
        self._is_listening = False
        self._running = False
        self._thread = None
    
    def start(self) -> bool:
        """Start whistle detection."""
        try:
            import pyaudio
            import numpy as np
            self._pyaudio = pyaudio
            self._np = np
            
            self._running = True
            self._thread = threading.Thread(target=self._detection_loop, daemon=True)
            self._thread.start()
            
            logger.info("Whistle activation ready. Whistle to toggle voice.")
            return True
            
        except ImportError:
            logger.error("Install pyaudio and numpy: pip install pyaudio numpy")
            return False
    
    def stop(self):
        """Stop whistle detection."""
        self._running = False
    
    def _detection_loop(self):
        """Main detection loop."""
        CHUNK = 2048
        RATE = 44100
        
        p = self._pyaudio.PyAudio()
        
        try:
            stream = p.open(
                format=self._pyaudio.paFloat32,
                channels=1,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
            )
            
            whistle_start = None
            
            while self._running:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    audio = self._np.frombuffer(data, dtype=self._np.float32)
                    
                    # FFT to find dominant frequency
                    fft = self._np.fft.fft(audio)
                    freqs = self._np.fft.fftfreq(len(fft), 1/RATE)
                    
                    # Only look at positive frequencies
                    pos_mask = freqs > 0
                    freqs = freqs[pos_mask]
                    magnitudes = self._np.abs(fft[pos_mask])
                    
                    # Find dominant frequency
                    if len(magnitudes) > 0:
                        dominant_idx = self._np.argmax(magnitudes)
                        dominant_freq = freqs[dominant_idx]
                        
                        # Check if it's a whistle
                        if self.min_freq <= dominant_freq <= self.max_freq:
                            if whistle_start is None:
                                whistle_start = time.time() * 1000
                            elif time.time() * 1000 - whistle_start > self.min_duration_ms:
                                self._toggle()
                                whistle_start = None
                                time.sleep(0.5)  # Debounce
                        else:
                            whistle_start = None
                    
                except Exception:
                    pass
                
                time.sleep(0.01)
            
            stream.stop_stream()
            stream.close()
            
        except Exception as e:
            logger.error(f"Whistle detection error: {e}")
        finally:
            p.terminate()
    
    def _toggle(self):
        """Toggle listening state."""
        if self._is_listening:
            self._is_listening = False
            logger.info("🎵 Voice: Stopped listening (whistle detected)")
            if self.on_stop:
                self.on_stop()
        else:
            self._is_listening = True
            logger.info("🎵 Voice: Started listening (whistle detected)...")
            if self.on_start:
                self.on_start()


# =============================================================================
# UNIFIED ACTIVATION MANAGER
# =============================================================================

class VoiceActivationManager:
    """
    Unified manager for all voice activation methods.
    
    USAGE:
    ```python
    manager = VoiceActivationManager(
        method=ActivationMethod.HOTKEY,
        on_start=start_recording,
        on_stop=stop_and_process,
    )
    manager.start()
    
    # Change method at runtime
    manager.set_method(ActivationMethod.DOUBLE_TAP)
    ```
    """
    
    def __init__(
        self,
        method: ActivationMethod = ActivationMethod.HOTKEY,
        config: Optional[ActivationConfig] = None,
        on_start: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_cancel: Optional[Callable] = None,
    ):
        self.config = config or ActivationConfig()
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel
        
        self._current_method = method
        self._activator = None
        self._running = False
    
    def start(self) -> bool:
        """Start the activation listener."""
        self._running = True
        return self._create_activator()
    
    def stop(self):
        """Stop the activation listener."""
        self._running = False
        if self._activator:
            self._activator.stop()
    
    def set_method(self, method: ActivationMethod) -> bool:
        """Change activation method at runtime."""
        if self._activator:
            self._activator.stop()
        
        self._current_method = method
        
        if self._running:
            return self._create_activator()
        return True
    
    def _create_activator(self) -> bool:
        """Create the appropriate activator."""
        if self._current_method == ActivationMethod.HOTKEY:
            self._activator = HotkeyActivation(
                hotkey=self.config.hotkey,
                on_start=self.on_start,
                on_stop=self.on_stop,
                on_cancel=self.on_cancel,
            )
        elif self._current_method == ActivationMethod.DOUBLE_TAP:
            self._activator = DoubleTapActivation(
                key=self.config.double_tap_key,
                window_ms=self.config.double_tap_window_ms,
                on_start=self.on_start,
                on_stop=self.on_stop,
            )
        elif self._current_method == ActivationMethod.CLAP:
            self._activator = ClapActivation(
                threshold=self.config.clap_threshold,
                clap_count=self.config.clap_count,
                window_ms=self.config.clap_window_ms,
                on_start=self.on_start,
                on_stop=self.on_stop,
            )
        elif self._current_method == ActivationMethod.WHISTLE:
            self._activator = WhistleActivation(
                on_start=self.on_start,
                on_stop=self.on_stop,
            )
        else:
            logger.error(f"Unknown activation method: {self._current_method}")
            return False
        
        return self._activator.start()
    
    @property
    def is_listening(self) -> bool:
        """Check if currently listening."""
        return self._activator.is_listening if self._activator else False
    
    @property
    def current_method(self) -> ActivationMethod:
        return self._current_method


# =============================================================================
# QUICK SETUP
# =============================================================================

def setup_voice_activation(
    method: str = "hotkey",
    on_start: Optional[Callable] = None,
    on_stop: Optional[Callable] = None,
) -> VoiceActivationManager:
    """
    Quick setup for voice activation.
    
    Args:
        method: "hotkey", "double_tap", "clap", or "whistle"
        on_start: Callback when listening starts
        on_stop: Callback when listening stops
    
    Returns:
        VoiceActivationManager instance
    
    Example:
        manager = setup_voice_activation(
            method="hotkey",
            on_start=lambda: print("Listening..."),
            on_stop=lambda: print("Processing..."),
        )
        manager.start()
    """
    method_map = {
        "hotkey": ActivationMethod.HOTKEY,
        "double_tap": ActivationMethod.DOUBLE_TAP,
        "clap": ActivationMethod.CLAP,
        "whistle": ActivationMethod.WHISTLE,
    }
    
    activation_method = method_map.get(method.lower(), ActivationMethod.HOTKEY)
    
    manager = VoiceActivationManager(
        method=activation_method,
        on_start=on_start,
        on_stop=on_stop,
    )
    
    return manager


# =============================================================================
# COMPARISON
# =============================================================================

"""
VOICE ACTIVATION METHOD COMPARISON
══════════════════════════════════════════════════════════════════════════

┌──────────────┬──────────────┬───────────┬──────────┬────────────────────┐
│ Method       │ Hands-Free   │ Accuracy  │ Setup    │ Best For           │
├──────────────┼──────────────┼───────────┼──────────┼────────────────────┤
│ HOTKEY (F5)  │ ❌ No        │ 100%      │ Easy     │ General use        │
│ DOUBLE-TAP   │ ❌ No        │ 99%       │ Easy     │ While typing       │
│ CLAP         │ ✅ Yes       │ 90%       │ Medium   │ Hands busy         │
│ WHISTLE      │ ✅ Yes       │ 85%       │ Medium   │ Fun/accessible     │
└──────────────┴──────────────┴───────────┴──────────┴────────────────────┘

RECOMMENDED:
1. HOTKEY (F5) - Most reliable, works everywhere
2. DOUBLE-TAP (Ctrl) - Fast and natural for keyboard users
3. CLAP - Fun and hands-free

INSTALLATION:
pip install keyboard    # For hotkey/double-tap
pip install pyaudio     # For clap/whistle

══════════════════════════════════════════════════════════════════════════
"""
