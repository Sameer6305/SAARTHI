"""
Action Handlers
===============

Implements the ALLOWLIST of actions the executor can perform.

ALLOWED ACTIONS (ONLY THESE):
1. open_browser_url - Open a URL in default browser
2. play_media_file - Play media via default application  
3. read_file_with_picker - Read a file selected by user

SECURITY INVARIANTS:
- NO shell execution
- NO subprocess spawning (except webbrowser which is safe)
- NO file deletion or modification
- NO registry access
- Only user-selected files can be read
"""

import logging
import os
import webbrowser
import tkinter as tk
from tkinter import filedialog
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Result of an action execution."""
    
    success: bool
    action_id: str
    action_type: str
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None
    executed_at: datetime = None
    
    def __post_init__(self):
        if self.executed_at is None:
            self.executed_at = datetime.utcnow()


class ActionHandler(ABC):
    """Base class for action handlers."""
    
    @property
    @abstractmethod
    def action_type(self) -> str:
        """The action type this handler handles."""
        pass
    
    @abstractmethod
    def execute(
        self,
        action_id: str,
        parameters: dict,
    ) -> ActionResult:
        """Execute the action."""
        pass
    
    def get_data_description(self, parameters: dict) -> str:
        """Get human-readable description of data being accessed."""
        return "No specific data"


# =============================================================================
# ALLOWED ACTION HANDLERS
# =============================================================================

class OpenBrowserUrlHandler(ActionHandler):
    """
    Opens a URL in the user's default browser.
    
    SECURITY:
    - Only http:// and https:// URLs
    - URL already validated by ActionValidator
    - Uses webbrowser module (safe, no shell)
    """
    
    @property
    def action_type(self) -> str:
        return "open_browser_url"
    
    def execute(
        self,
        action_id: str,
        parameters: dict,
    ) -> ActionResult:
        """Open URL in default browser."""
        url = parameters.get("url", "")
        
        if not url:
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=self.action_type,
                message="No URL provided",
                error="Missing URL parameter",
            )
        
        try:
            # webbrowser.open is safe - it only opens URLs in browser
            # It does NOT execute shell commands
            success = webbrowser.open(url, new=2)  # new=2 opens in new tab
            
            if success:
                logger.info(
                    "URL opened in browser",
                    extra={
                        "action_id": action_id,
                        "url_domain": url.split("/")[2] if "/" in url else url[:50],
                    }
                )
                
                return ActionResult(
                    success=True,
                    action_id=action_id,
                    action_type=self.action_type,
                    message=f"Opened URL in browser",
                    data={"url_opened": True},
                )
            else:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=self.action_type,
                    message="Failed to open browser",
                    error="webbrowser.open returned False",
                )
                
        except Exception as e:
            logger.error(
                "Failed to open URL",
                extra={
                    "action_id": action_id,
                    "error": str(e),
                }
            )
            
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=self.action_type,
                message="Failed to open browser",
                error=str(e),
            )
    
    def get_data_description(self, parameters: dict) -> str:
        url = parameters.get("url", "")
        if "/" in url:
            try:
                domain = url.split("/")[2]
                return f"Opening website: {domain}"
            except IndexError:
                pass
        return f"Opening URL: {url[:50]}..."


class PlayMediaFileHandler(ActionHandler):
    """
    Plays a media file using the default application.
    
    SECURITY:
    - Uses file picker for user selection
    - Only opens, does not modify
    - Uses os.startfile (Windows) which is safe for media
    """
    
    MEDIA_EXTENSIONS = {
        "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"],
        "video": [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
        "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"],
    }
    
    @property
    def action_type(self) -> str:
        return "play_media_file"
    
    def execute(
        self,
        action_id: str,
        parameters: dict,
    ) -> ActionResult:
        """Let user select and play a media file."""
        media_type = parameters.get("media_type", "audio")
        
        # Get allowed extensions for this media type
        extensions = self.MEDIA_EXTENSIONS.get(media_type, [])
        
        if not extensions:
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=self.action_type,
                message=f"Unknown media type: {media_type}",
                error="Invalid media_type parameter",
            )
        
        try:
            # Use file picker - user must select the file
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            
            # Build file type filter
            ext_pattern = " ".join(f"*{ext}" for ext in extensions)
            filetypes = [
                (f"{media_type.title()} files", ext_pattern),
                ("All files", "*.*"),
            ]
            
            file_path = filedialog.askopenfilename(
                title=f"Select {media_type} file to play",
                filetypes=filetypes,
            )
            
            root.destroy()
            
            if not file_path:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=self.action_type,
                    message="No file selected",
                    error="User cancelled file selection",
                )
            
            # Verify extension
            _, ext = os.path.splitext(file_path)
            if ext.lower() not in extensions:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=self.action_type,
                    message=f"Invalid file type: {ext}",
                    error="Selected file does not match media type",
                )
            
            # Open with default application
            # os.startfile is safe - it only opens files with associated apps
            os.startfile(file_path)
            
            logger.info(
                "Media file opened",
                extra={
                    "action_id": action_id,
                    "media_type": media_type,
                    "file_extension": ext,
                }
            )
            
            return ActionResult(
                success=True,
                action_id=action_id,
                action_type=self.action_type,
                message=f"Playing {media_type} file",
                data={"file_opened": True, "media_type": media_type},
            )
            
        except Exception as e:
            logger.error(
                "Failed to play media",
                extra={
                    "action_id": action_id,
                    "error": str(e),
                }
            )
            
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=self.action_type,
                message="Failed to play media file",
                error=str(e),
            )
    
    def get_data_description(self, parameters: dict) -> str:
        media_type = parameters.get("media_type", "media")
        return f"You will select a {media_type} file to play"


class ReadFileWithPickerHandler(ActionHandler):
    """
    Reads a file selected by the user via file picker.
    
    SECURITY:
    - User MUST select the file via picker
    - Only reads, never modifies
    - File content is read-only
    - Maximum file size enforced
    """
    
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB max
    
    @property
    def action_type(self) -> str:
        return "read_file_with_picker"
    
    def execute(
        self,
        action_id: str,
        parameters: dict,
    ) -> ActionResult:
        """Let user select a file to read."""
        file_types = parameters.get("file_types", [".txt"])
        purpose = parameters.get("purpose", "Read file contents")
        
        try:
            # Use file picker - user must select the file
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            
            # Build file type filter
            ext_pattern = " ".join(f"*{ext}" for ext in file_types)
            filetypes = [
                ("Allowed files", ext_pattern),
                ("All files", "*.*"),
            ]
            
            file_path = filedialog.askopenfilename(
                title=f"Select file to read ({purpose})",
                filetypes=filetypes,
            )
            
            root.destroy()
            
            if not file_path:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=self.action_type,
                    message="No file selected",
                    error="User cancelled file selection",
                )
            
            # Verify extension
            _, ext = os.path.splitext(file_path)
            if ext.lower() not in [t.lower() for t in file_types]:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=self.action_type,
                    message=f"Invalid file type: {ext}",
                    error="Selected file type not in allowlist",
                )
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_FILE_SIZE_BYTES:
                return ActionResult(
                    success=False,
                    action_id=action_id,
                    action_type=self.action_type,
                    message="File too large",
                    error=f"File exceeds {self.MAX_FILE_SIZE_BYTES // 1024 // 1024}MB limit",
                )
            
            # Read file (read-only!)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            
            logger.info(
                "File read successfully",
                extra={
                    "action_id": action_id,
                    "file_extension": ext,
                    "file_size": file_size,
                }
            )
            
            return ActionResult(
                success=True,
                action_id=action_id,
                action_type=self.action_type,
                message="File read successfully",
                data={
                    "content": content,
                    "file_name": os.path.basename(file_path),
                    "file_size": file_size,
                },
            )
            
        except Exception as e:
            logger.error(
                "Failed to read file",
                extra={
                    "action_id": action_id,
                    "error": str(e),
                }
            )
            
            return ActionResult(
                success=False,
                action_id=action_id,
                action_type=self.action_type,
                message="Failed to read file",
                error=str(e),
            )
    
    def get_data_description(self, parameters: dict) -> str:
        purpose = parameters.get("purpose", "Read file")
        file_types = parameters.get("file_types", [])
        return f"{purpose} ({', '.join(file_types)} files)"


# =============================================================================
# ACTION HANDLER REGISTRY
# =============================================================================

class ActionHandlerRegistry:
    """
    Registry of allowed action handlers.
    
    SECURITY: Only handlers in this registry can execute.
    """
    
    def __init__(self):
        """Initialize with allowed handlers only."""
        self._handlers: dict[str, ActionHandler] = {}
        
        # Register ONLY allowed handlers
        self._register(OpenBrowserUrlHandler())
        self._register(PlayMediaFileHandler())
        self._register(ReadFileWithPickerHandler())
    
    def _register(self, handler: ActionHandler) -> None:
        """Register a handler."""
        self._handlers[handler.action_type] = handler
    
    def get_handler(self, action_type: str) -> Optional[ActionHandler]:
        """Get handler for action type (None if not allowed)."""
        return self._handlers.get(action_type)
    
    def is_allowed(self, action_type: str) -> bool:
        """Check if action type is allowed."""
        return action_type in self._handlers
    
    def get_allowed_actions(self) -> list[str]:
        """Get list of allowed action types."""
        return list(self._handlers.keys())
