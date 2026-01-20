"""
Voice Configuration
===================

Configuration for the voice module with safe defaults.
All settings prioritize privacy and user control.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class TTSEngine(Enum):
    """Available TTS engines (all local)."""
    WINDOWS_SAPI = "windows_sapi"  # Windows built-in
    PIPER = "piper"                # Open-source local TTS


class WhisperModel(Enum):
    """Whisper model sizes (smaller = faster, less accurate)."""
    TINY = "tiny"       # ~39M params, fastest
    BASE = "base"       # ~74M params, good balance
    SMALL = "small"     # ~244M params, better accuracy
    MEDIUM = "medium"   # ~769M params, high accuracy (slow)


@dataclass
class VoiceConfig:
    """
    Voice module configuration.
    
    DEFAULTS ARE CONSERVATIVE:
    - Voice disabled by default
    - Smallest/fastest models
    - Short timeouts
    - Strict confidence thresholds
    """
    
    # ==================== MASTER SWITCH ====================
    # Voice is OFF by default - user must explicitly enable
    enabled: bool = False
    
    # ==================== STT SETTINGS ====================
    # Whisper model (tiny is fastest, works on CPU)
    whisper_model: WhisperModel = WhisperModel.TINY
    
    # Path to Whisper model (None = download on first use)
    whisper_model_path: Optional[Path] = None
    
    # Maximum recording duration (seconds) - prevents accidental long recordings
    max_recording_seconds: float = 30.0
    
    # Minimum recording duration (seconds) - prevents accidental triggers
    min_recording_seconds: float = 0.5
    
    # STT timeout (seconds) - how long to wait for transcription
    stt_timeout_seconds: float = 30.0
    
    # Minimum confidence threshold (0.0-1.0) - below this, reject
    min_confidence: float = 0.3
    
    # Audio sample rate (Whisper expects 16kHz)
    sample_rate: int = 16000
    
    # ==================== TTS SETTINGS ====================
    # TTS engine to use
    tts_engine: TTSEngine = TTSEngine.WINDOWS_SAPI
    
    # Path to Piper model (if using Piper)
    piper_model_path: Optional[Path] = None
    
    # TTS voice name (for Windows SAPI)
    tts_voice_name: Optional[str] = None
    
    # TTS speech rate (words per minute, 0 = default)
    tts_rate: int = 0
    
    # TTS volume (0-100)
    tts_volume: int = 80
    
    # ==================== UI SETTINGS ====================
    # Hotkey for push-to-talk (None = button only)
    push_to_talk_hotkey: Optional[str] = None  # e.g., "ctrl+shift+space"
    
    # Show floating indicator when recording
    show_recording_indicator: bool = True
    
    # Play sound on recording start/stop
    play_feedback_sounds: bool = True
    
    # ==================== SAFETY SETTINGS ====================
    # Require text confirmation for ambiguous speech
    confirm_ambiguous: bool = True
    
    # Low confidence threshold - below this, require confirmation
    ambiguous_confidence: float = 0.6
    
    # Auto-disable voice after N consecutive failures
    max_consecutive_failures: int = 5
    
    # Re-enable after user action only
    auto_reenable: bool = False


# Default configuration
DEFAULT_VOICE_CONFIG = VoiceConfig()


def load_voice_config(config_path: Optional[Path] = None) -> VoiceConfig:
    """
    Load voice configuration from file or return defaults.
    
    Voice is disabled by default - explicit user action required.
    """
    if config_path and config_path.exists():
        import json
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            # Only load allowed fields
            allowed_fields = {f.name for f in VoiceConfig.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in allowed_fields}
            
            return VoiceConfig(**filtered)
        except Exception:
            pass
    
    return DEFAULT_VOICE_CONFIG


def save_voice_config(config: VoiceConfig, config_path: Path) -> bool:
    """Save voice configuration to file."""
    import json
    from dataclasses import asdict
    
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable dict
        data = asdict(config)
        
        # Convert enums to strings
        data['whisper_model'] = config.whisper_model.value
        data['tts_engine'] = config.tts_engine.value
        
        # Convert paths to strings
        if data['whisper_model_path']:
            data['whisper_model_path'] = str(data['whisper_model_path'])
        if data['piper_model_path']:
            data['piper_model_path'] = str(data['piper_model_path'])
        
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception:
        return False
