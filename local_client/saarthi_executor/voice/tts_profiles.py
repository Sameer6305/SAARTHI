"""
TTS Voice Profiles
==================

Pre-configured voice profiles for different moods/contexts.

PROFILES:
- ROBOTIC_DEEP: Deep, robotic, cinematic (default)
- ROBOTIC_LIGHT: Lighter robotic effect
- NATURAL_DEEP: Deep but more natural
- FAST_RESPONSE: Minimal effects for speed
- DRAMATIC: Heavy effects for emphasis
"""

from .tts_engine import VoiceProfile, TTSConfig


# =============================================================================
# ROBOTIC DEEP (DEFAULT)
# =============================================================================

ROBOTIC_DEEP = VoiceProfile(
    name="SAARTHI_Robotic",
    pitch=-8,                    # Deep voice
    rate=0.85,                   # Slightly slow for drama
    volume=0.9,
    
    # Robotic effects
    robotize=True,
    robot_freq=30.0,             # Low frequency modulation
    robot_depth=0.3,             # Moderate effect
    
    # Cinematic
    reverb=True,
    reverb_room=0.3,
    reverb_damp=0.5,
    
    # Model
    piper_model="en_US-ryan-medium",
)


# =============================================================================
# ROBOTIC LIGHT
# =============================================================================

ROBOTIC_LIGHT = VoiceProfile(
    name="SAARTHI_Light",
    pitch=-4,                    # Less deep
    rate=0.95,                   # Near normal
    volume=0.9,
    
    # Light robotic
    robotize=True,
    robot_freq=40.0,             # Higher frequency
    robot_depth=0.15,            # Subtle effect
    
    # Minimal reverb
    reverb=True,
    reverb_room=0.15,
    reverb_damp=0.7,
    
    piper_model="en_US-ryan-medium",
)


# =============================================================================
# NATURAL DEEP
# =============================================================================

NATURAL_DEEP = VoiceProfile(
    name="SAARTHI_Natural",
    pitch=-10,                   # Very deep
    rate=0.9,
    volume=0.9,
    
    # No robotic effect
    robotize=False,
    robot_freq=0,
    robot_depth=0,
    
    # Subtle reverb only
    reverb=True,
    reverb_room=0.2,
    reverb_damp=0.6,
    
    piper_model="en_US-joe-medium",  # Deeper voice model
)


# =============================================================================
# FAST RESPONSE
# =============================================================================

FAST_RESPONSE = VoiceProfile(
    name="SAARTHI_Fast",
    pitch=-6,
    rate=1.1,                    # Faster
    volume=0.9,
    
    # No effects (fastest)
    robotize=False,
    robot_freq=0,
    robot_depth=0,
    reverb=False,
    reverb_room=0,
    reverb_damp=0,
    
    piper_model="en_US-ryan-medium",
)


# =============================================================================
# DRAMATIC
# =============================================================================

DRAMATIC = VoiceProfile(
    name="SAARTHI_Dramatic",
    pitch=-12,                   # Very deep
    rate=0.75,                   # Slow, dramatic
    volume=0.95,
    
    # Heavy robotic
    robotize=True,
    robot_freq=25.0,             # Low frequency
    robot_depth=0.4,             # Strong effect
    
    # Heavy reverb
    reverb=True,
    reverb_room=0.5,             # Large room
    reverb_damp=0.3,             # Long decay
    
    piper_model="en_US-joe-medium",
)


# =============================================================================
# CONTEXT-BASED PROFILE SELECTION
# =============================================================================

def get_profile_for_context(context: str) -> VoiceProfile:
    """
    Select voice profile based on context.
    
    Args:
        context: "greeting", "error", "success", "question", "action", "default"
    
    Returns:
        Appropriate VoiceProfile
    """
    context_map = {
        "greeting": ROBOTIC_DEEP,
        "error": DRAMATIC,
        "success": ROBOTIC_LIGHT,
        "question": NATURAL_DEEP,
        "action": FAST_RESPONSE,
        "default": ROBOTIC_DEEP,
    }
    
    return context_map.get(context, ROBOTIC_DEEP)


def create_config(profile: VoiceProfile = ROBOTIC_DEEP) -> TTSConfig:
    """Create TTS config with specified profile."""
    return TTSConfig(voice=profile)


# Default profile
DEFAULT_PROFILE = ROBOTIC_DEEP
