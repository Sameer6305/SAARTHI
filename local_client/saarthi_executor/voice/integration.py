"""
Voice Integration with SAARTHI Executor
========================================

Integrates the voice module with the main executor.

CRITICAL SAFETY RULES:
1. Voice input is treated IDENTICALLY to text input
2. Voice NEVER bypasses permissions or execution rules
3. Voice is a CONVENIENCE layer, not a controller
4. Ambiguous input falls back to text confirmation
5. Silence or failure never triggers actions

The voice module adds to the executor:
- Push-to-talk button in tray menu
- Voice input → text → same pipeline as typed input
- TTS output for approved responses
- Visual recording indicator
"""

import logging
import threading
from typing import Optional, Callable, Any
from pathlib import Path

from saarthi_executor.voice.config import VoiceConfig, load_voice_config, save_voice_config
from saarthi_executor.voice.pipeline import VoicePipeline, VoicePipelineState, VoiceInputResult
from saarthi_executor.voice.ui_components import (
    RecordingIndicator,
    VoiceConfirmationDialog,
    VoiceSettingsDialog,
)

logger = logging.getLogger(__name__)


class VoiceIntegration:
    """
    Integrates voice features with the SAARTHI executor.
    
    SAFETY: Voice input goes through the SAME pipeline as text.
    No special privileges, no bypass of permissions.
    """
    
    def __init__(
        self,
        config_path: Optional[Path] = None,
        on_voice_input: Optional[Callable[[str], Any]] = None,
    ):
        """
        Initialize voice integration.
        
        Args:
            config_path: Path to voice config file
            on_voice_input: Callback when voice input is ready
                           This receives PLAIN TEXT, same as typed input
        """
        self._config_path = config_path or (Path.home() / ".saarthi" / "voice_config.json")
        self._on_voice_input = on_voice_input
        
        # Load config (voice disabled by default)
        self._config = load_voice_config(self._config_path)
        
        # Components
        self._pipeline: Optional[VoicePipeline] = None
        self._indicator: Optional[RecordingIndicator] = None
        self._confirmation_dialog = VoiceConfirmationDialog()
        
        # State
        self._initialized = False
        self._push_to_talk_active = False
        
        logger.info(f"Voice integration created (enabled: {self._config.enabled})")
    
    def initialize(self) -> bool:
        """
        Initialize voice components if enabled.
        
        Returns True if successful (or if voice is disabled).
        """
        if self._initialized:
            return True
        
        if not self._config.enabled:
            logger.info("Voice is disabled, skipping initialization")
            self._initialized = True
            return True
        
        try:
            # Create pipeline
            self._pipeline = VoicePipeline(
                config=self._config,
                on_state_change=self._on_pipeline_state_change,
                on_recording_state=self._on_recording_state_change,
            )
            
            # Create recording indicator
            if self._config.show_recording_indicator:
                self._indicator = RecordingIndicator(
                    on_stop_click=self.cancel_push_to_talk,
                )
            
            self._initialized = True
            logger.info("Voice integration initialized")
            return True
            
        except Exception as e:
            logger.error(f"Voice initialization failed: {e}")
            return False
    
    def _on_pipeline_state_change(self, state: VoicePipelineState) -> None:
        """Handle pipeline state changes."""
        logger.debug(f"Voice pipeline state: {state.value}")
    
    def _on_recording_state_change(self, is_recording: bool) -> None:
        """Handle recording state changes (for indicator)."""
        if self._indicator:
            if is_recording:
                self._indicator.show_recording()
            else:
                self._indicator.hide()
    
    # ==================== PUBLIC API ====================
    
    @property
    def is_enabled(self) -> bool:
        """Whether voice features are enabled."""
        return self._config.enabled and self._pipeline is not None
    
    @property
    def is_ready(self) -> bool:
        """Whether ready for push-to-talk."""
        return self._pipeline is not None and self._pipeline.is_ready
    
    @property
    def is_recording(self) -> bool:
        """Whether currently recording."""
        return self._push_to_talk_active
    
    def enable_voice(self) -> bool:
        """
        Enable voice features.
        
        Requires explicit user action.
        """
        self._config.enabled = True
        
        if self._pipeline:
            return self._pipeline.enable()
        else:
            self._pipeline = VoicePipeline(
                config=self._config,
                on_state_change=self._on_pipeline_state_change,
                on_recording_state=self._on_recording_state_change,
            )
            
            if self._config.show_recording_indicator:
                self._indicator = RecordingIndicator(
                    on_stop_click=self.cancel_push_to_talk,
                )
            
            save_voice_config(self._config, self._config_path)
            return True
    
    def disable_voice(self) -> None:
        """Disable voice features."""
        self._config.enabled = False
        
        if self._pipeline:
            self._pipeline.disable()
        
        if self._indicator:
            self._indicator.hide()
        
        save_voice_config(self._config, self._config_path)
        logger.info("Voice features disabled")
    
    def start_push_to_talk(self) -> bool:
        """
        Start push-to-talk recording.
        
        Called when user PRESSES the talk button.
        """
        if not self.is_enabled:
            logger.warning("Voice not enabled")
            return False
        
        if self._push_to_talk_active:
            return True  # Already recording
        
        if not self._pipeline or not self._pipeline.start_listening():
            logger.error("Failed to start push-to-talk")
            return False
        
        self._push_to_talk_active = True
        logger.info("Push-to-talk started")
        return True
    
    def stop_push_to_talk(self) -> Optional[str]:
        """
        Stop push-to-talk and process voice input.
        
        Called when user RELEASES the talk button.
        
        Returns:
            Transcribed text (same as typed input) or None on failure.
            The text is passed to the SAME pipeline as typed input.
        """
        if not self._push_to_talk_active:
            return None
        
        self._push_to_talk_active = False
        
        if not self._pipeline:
            return None
        
        # Show processing indicator
        if self._indicator:
            self._indicator.show_processing()
        
        try:
            # Get transcription
            result: VoiceInputResult = self._pipeline.stop_listening()
            
            if not result.success:
                logger.warning(f"Voice input failed: {result.error}")
                return None
            
            text = result.text
            
            # Confirm if needed (low confidence)
            if result.needs_confirmation:
                logger.info(f"Voice input needs confirmation (confidence: {result.confidence:.2f})")
                
                confirmed, edited_text = self._confirmation_dialog.show(
                    text,
                    result.confidence,
                )
                
                if not confirmed:
                    logger.info("Voice input cancelled by user")
                    return None
                
                text = edited_text
            
            # Call the callback with plain text
            # THIS IS TREATED EXACTLY LIKE TYPED INPUT
            if self._on_voice_input and text:
                logger.info(f"Voice input ready: '{text[:50]}...'")
                self._on_voice_input(text)
            
            return text
            
        finally:
            if self._indicator:
                self._indicator.hide()
    
    def cancel_push_to_talk(self) -> None:
        """Cancel push-to-talk recording."""
        if self._push_to_talk_active:
            self._push_to_talk_active = False
            
            if self._pipeline:
                self._pipeline.cancel_listening()
            
            if self._indicator:
                self._indicator.hide()
            
            logger.info("Push-to-talk cancelled")
    
    def speak_response(self, text: str) -> bool:
        """
        Speak an approved response using TTS.
        
        CRITICAL: Only call this with text that has been:
        1. Generated by the Planner
        2. Approved by the Executor
        3. Shown to the user
        
        Args:
            text: Approved text to speak
            
        Returns:
            True if speech completed successfully
        """
        if not self.is_enabled or not self._pipeline:
            return False
        
        result = self._pipeline.speak(text)
        return result.success
    
    def stop_speaking(self) -> None:
        """Stop TTS output."""
        if self._pipeline:
            self._pipeline.stop_speaking()
    
    def show_settings(self) -> None:
        """Show voice settings dialog."""
        dialog = VoiceSettingsDialog(self._config)
        result = dialog.show()
        
        if result:
            # Apply settings
            self._config.enabled = result.get('enabled', self._config.enabled)
            self._config.tts_volume = result.get('tts_volume', self._config.tts_volume)
            self._config.confirm_ambiguous = result.get('confirm_ambiguous', self._config.confirm_ambiguous)
            self._config.show_recording_indicator = result.get('show_recording_indicator', self._config.show_recording_indicator)
            
            # Save
            save_voice_config(self._config, self._config_path)
            
            # Apply changes
            if self._config.enabled and not self.is_enabled:
                self.enable_voice()
            elif not self._config.enabled and self.is_enabled:
                self.disable_voice()
            
            logger.info("Voice settings updated")
    
    def preload_models(self) -> None:
        """
        Pre-load STT model to avoid first-use delay.
        
        Call this during startup if voice is enabled.
        """
        if self._pipeline and self._config.enabled:
            def load():
                logger.info("Pre-loading STT model...")
                self._pipeline.load_stt_model()
                logger.info("STT model loaded")
            
            threading.Thread(target=load, daemon=True).start()
    
    def get_status(self) -> dict:
        """Get voice status for UI."""
        if not self._pipeline:
            return {
                "enabled": False,
                "state": "disabled",
                "ready": False,
            }
        
        status = self._pipeline.get_status()
        status["push_to_talk_active"] = self._push_to_talk_active
        return status
    
    def cleanup(self) -> None:
        """Clean up voice resources."""
        self.cancel_push_to_talk()
        
        if self._pipeline:
            self._pipeline.disable()
        
        if self._indicator:
            self._indicator.hide()
        
        logger.info("Voice integration cleaned up")
