"""
Safe Desktop Actions
=====================

Secure, user-confirmed desktop interactions for SAARTHI.

SECURITY MODEL:
┌─────────────────────────────────────────────────────────────────────┐
│                        ACTION REQUEST                                │
│                             │                                        │
│                             ▼                                        │
│                    ┌─────────────────┐                              │
│                    │  SAFETY CHECK   │                              │
│                    │  - Whitelist?   │                              │
│                    │  - Risk level?  │                              │
│                    │  - Parameters?  │                              │
│                    └────────┬────────┘                              │
│                             │                                        │
│              ┌──────────────┼──────────────┐                        │
│              │              │              │                        │
│              ▼              ▼              ▼                        │
│         BLOCKED        PREVIEW        AUTO-ALLOW                    │
│         (danger)       + CONFIRM      (safe)                        │
│              │              │              │                        │
│              ▼              ▼              ▼                        │
│           REJECT      SHOW UI +        EXECUTE                      │
│                       TIMEOUT          (audit)                      │
│                          │                                          │
│                    ┌─────┴─────┐                                    │
│                    │           │                                    │
│                    ▼           ▼                                    │
│                APPROVED    REJECTED/                                │
│                    │       TIMEOUT                                  │
│                    ▼                                                │
│                EXECUTE                                              │
│                (audit)                                              │
└─────────────────────────────────────────────────────────────────────┘

ALLOWED ACTIONS (Whitelist):
✓ open_url        - Open URL in default browser
✓ open_app        - Open whitelisted applications
✓ read_file       - Read user-owned files (no system files)
✓ summarize       - Summarize content (local LLM)
✓ notify          - Show desktop notification
✓ speak           - Text-to-speech output
✓ clipboard_read  - Read clipboard (with confirmation)

FORBIDDEN ACTIONS (Blacklist):
✗ delete_file     - NEVER delete files
✗ write_file      - NEVER write to arbitrary files
✗ shell_command   - NEVER execute shell commands
✗ background_exec - NEVER execute silently
✗ system_modify   - NEVER modify system settings
✗ network_send    - NEVER send data to network
✗ keylog          - NEVER monitor input
✗ screen_capture  - NEVER capture screen silently
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List, Set
import threading
import time
import os


# =============================================================================
# ENUMS & TYPES
# =============================================================================

class ActionType(Enum):
    """Types of desktop actions."""
    # ALLOWED - Safe actions
    OPEN_URL = "open_url"
    OPEN_APP = "open_app"
    READ_FILE = "read_file"
    SUMMARIZE = "summarize"
    NOTIFY = "notify"
    SPEAK = "speak"
    CLIPBOARD_READ = "clipboard_read"
    
    # FORBIDDEN - Never allowed
    DELETE_FILE = "delete_file"
    WRITE_FILE = "write_file"
    SHELL_COMMAND = "shell_command"
    SYSTEM_MODIFY = "system_modify"
    NETWORK_SEND = "network_send"


class RiskLevel(Enum):
    """Risk level of an action."""
    SAFE = "safe"           # Auto-allow (notify, speak)
    LOW = "low"             # Brief confirmation
    MEDIUM = "medium"       # Detailed confirmation
    HIGH = "high"           # Explicit confirmation + warning
    FORBIDDEN = "forbidden" # Never allowed


class ConfirmationResult(Enum):
    """Result of user confirmation."""
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"
    MODIFIED = "modified"


# =============================================================================
# ACTION DEFINITIONS
# =============================================================================

@dataclass
class ActionDefinition:
    """Definition of an allowed action."""
    action_type: ActionType
    risk_level: RiskLevel
    description: str
    requires_confirmation: bool
    timeout_seconds: int = 30
    allowed_params: Set[str] = field(default_factory=set)
    
    # Validation function
    validate: Optional[Callable[[Dict], bool]] = None


# Whitelist of allowed actions
ALLOWED_ACTIONS: Dict[ActionType, ActionDefinition] = {
    ActionType.OPEN_URL: ActionDefinition(
        action_type=ActionType.OPEN_URL,
        risk_level=RiskLevel.LOW,
        description="Open a URL in your default browser",
        requires_confirmation=True,
        timeout_seconds=15,
        allowed_params={"url", "site_name"},
    ),
    
    ActionType.OPEN_APP: ActionDefinition(
        action_type=ActionType.OPEN_APP,
        risk_level=RiskLevel.MEDIUM,
        description="Open an application",
        requires_confirmation=True,
        timeout_seconds=15,
        allowed_params={"app_name", "app_path"},
    ),
    
    ActionType.READ_FILE: ActionDefinition(
        action_type=ActionType.READ_FILE,
        risk_level=RiskLevel.MEDIUM,
        description="Read a file from your computer",
        requires_confirmation=True,
        timeout_seconds=20,
        allowed_params={"file_path", "max_size"},
    ),
    
    ActionType.SUMMARIZE: ActionDefinition(
        action_type=ActionType.SUMMARIZE,
        risk_level=RiskLevel.SAFE,
        description="Summarize content using local AI",
        requires_confirmation=False,
        timeout_seconds=60,
        allowed_params={"content", "max_length"},
    ),
    
    ActionType.NOTIFY: ActionDefinition(
        action_type=ActionType.NOTIFY,
        risk_level=RiskLevel.SAFE,
        description="Show a desktop notification",
        requires_confirmation=False,
        timeout_seconds=5,
        allowed_params={"title", "message", "icon"},
    ),
    
    ActionType.SPEAK: ActionDefinition(
        action_type=ActionType.SPEAK,
        risk_level=RiskLevel.SAFE,
        description="Speak text aloud",
        requires_confirmation=False,
        timeout_seconds=30,
        allowed_params={"text", "voice"},
    ),
    
    ActionType.CLIPBOARD_READ: ActionDefinition(
        action_type=ActionType.CLIPBOARD_READ,
        risk_level=RiskLevel.MEDIUM,
        description="Read text from clipboard",
        requires_confirmation=True,
        timeout_seconds=10,
        allowed_params={},
    ),
}

# Explicit blacklist - NEVER ALLOWED
FORBIDDEN_ACTIONS: Set[ActionType] = {
    ActionType.DELETE_FILE,
    ActionType.WRITE_FILE,
    ActionType.SHELL_COMMAND,
    ActionType.SYSTEM_MODIFY,
    ActionType.NETWORK_SEND,
}


# =============================================================================
# ACTION REQUEST & RESULT
# =============================================================================

@dataclass
class ActionRequest:
    """A request to perform a desktop action."""
    id: str
    action_type: ActionType
    parameters: Dict[str, Any]
    source: str = "user"                    # Who requested this
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Populated by safety check
    risk_level: Optional[RiskLevel] = None
    preview_text: Optional[str] = None
    confirmation_required: bool = True


@dataclass
class ActionResult:
    """Result of an action execution."""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    
    # Confirmation info
    confirmation: ConfirmationResult = ConfirmationResult.APPROVED
    confirmed_at: Optional[datetime] = None
    
    # Execution info
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None


# =============================================================================
# SAFETY CHECKER
# =============================================================================

class SafetyChecker:
    """
    Validates actions before execution.
    
    CHECKS:
    1. Is action in whitelist?
    2. Are parameters valid?
    3. Is path safe (no system files)?
    4. Is URL safe (no data: or file:)?
    5. Is app in allowed list?
    """
    
    # Whitelisted applications (safe to open)
    ALLOWED_APPS = {
        "notepad", "notepad.exe",
        "calc", "calc.exe",
        "mspaint", "mspaint.exe",
        "explorer", "explorer.exe",
        "code", "code.exe",           # VS Code
        "chrome", "chrome.exe",
        "firefox", "firefox.exe",
        "msedge", "msedge.exe",
        "spotify", "spotify.exe",
        "slack", "slack.exe",
        "discord", "discord.exe",
        "teams", "teams.exe",
    }
    
    # Forbidden file paths (never read)
    FORBIDDEN_PATHS = {
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\$Recycle.Bin",
    }
    
    # Forbidden URL schemes
    FORBIDDEN_URL_SCHEMES = {"file:", "data:", "javascript:", "vbscript:"}
    
    def check(self, request: ActionRequest) -> Dict[str, Any]:
        """
        Check if action is safe to execute.
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "risk_level": RiskLevel,
                "preview": str,
                "requires_confirmation": bool,
            }
        """
        action_type = request.action_type
        params = request.parameters
        
        # Check 1: Is action in whitelist?
        if action_type in FORBIDDEN_ACTIONS:
            return {
                "allowed": False,
                "reason": f"Action '{action_type.value}' is forbidden",
                "risk_level": RiskLevel.FORBIDDEN,
                "preview": None,
                "requires_confirmation": False,
            }
        
        if action_type not in ALLOWED_ACTIONS:
            return {
                "allowed": False,
                "reason": f"Action '{action_type.value}' is not in whitelist",
                "risk_level": RiskLevel.FORBIDDEN,
                "preview": None,
                "requires_confirmation": False,
            }
        
        definition = ALLOWED_ACTIONS[action_type]
        
        # Check 2: Validate parameters
        param_check = self._check_parameters(action_type, params)
        if not param_check["valid"]:
            return {
                "allowed": False,
                "reason": param_check["reason"],
                "risk_level": RiskLevel.FORBIDDEN,
                "preview": None,
                "requires_confirmation": False,
            }
        
        # Check 3: Generate preview
        preview = self._generate_preview(action_type, params)
        
        return {
            "allowed": True,
            "reason": "Action is safe",
            "risk_level": definition.risk_level,
            "preview": preview,
            "requires_confirmation": definition.requires_confirmation,
            "timeout": definition.timeout_seconds,
        }
    
    def _check_parameters(self, action_type: ActionType, params: Dict) -> Dict:
        """Validate action parameters."""
        
        if action_type == ActionType.OPEN_URL:
            url = params.get("url", "")
            
            # Check for forbidden schemes
            for scheme in self.FORBIDDEN_URL_SCHEMES:
                if url.lower().startswith(scheme):
                    return {
                        "valid": False,
                        "reason": f"URL scheme '{scheme}' is not allowed",
                    }
            
            # Must be http or https
            if not url.startswith(("http://", "https://")):
                return {
                    "valid": False,
                    "reason": "Only http:// and https:// URLs are allowed",
                }
            
            return {"valid": True, "reason": ""}
        
        elif action_type == ActionType.OPEN_APP:
            app = params.get("app_name", "").lower()
            
            # Check if app is whitelisted
            if app not in self.ALLOWED_APPS:
                return {
                    "valid": False,
                    "reason": f"Application '{app}' is not in allowed list",
                }
            
            return {"valid": True, "reason": ""}
        
        elif action_type == ActionType.READ_FILE:
            file_path = params.get("file_path", "")
            
            # Normalize path
            try:
                path = Path(file_path).resolve()
            except Exception:
                return {
                    "valid": False,
                    "reason": "Invalid file path",
                }
            
            # Check for forbidden paths
            path_str = str(path)
            for forbidden in self.FORBIDDEN_PATHS:
                if path_str.startswith(forbidden):
                    return {
                        "valid": False,
                        "reason": f"Cannot read files from {forbidden}",
                    }
            
            # Check if file exists
            if not path.exists():
                return {
                    "valid": False,
                    "reason": f"File not found: {file_path}",
                }
            
            # Check file size (max 10MB)
            max_size = params.get("max_size", 10 * 1024 * 1024)
            if path.stat().st_size > max_size:
                return {
                    "valid": False,
                    "reason": f"File too large (max {max_size // 1024 // 1024}MB)",
                }
            
            return {"valid": True, "reason": ""}
        
        # Default: valid
        return {"valid": True, "reason": ""}
    
    def _generate_preview(self, action_type: ActionType, params: Dict) -> str:
        """Generate human-readable preview of action."""
        
        if action_type == ActionType.OPEN_URL:
            url = params.get("url", "")
            site = params.get("site_name", url)
            return f"Open {site} in your browser"
        
        elif action_type == ActionType.OPEN_APP:
            app = params.get("app_name", "application")
            return f"Open {app}"
        
        elif action_type == ActionType.READ_FILE:
            path = params.get("file_path", "file")
            return f"Read file: {Path(path).name}"
        
        elif action_type == ActionType.SUMMARIZE:
            content = params.get("content", "")
            length = len(content)
            return f"Summarize content ({length} characters)"
        
        elif action_type == ActionType.NOTIFY:
            title = params.get("title", "Notification")
            return f"Show notification: {title}"
        
        elif action_type == ActionType.SPEAK:
            text = params.get("text", "")
            preview = text[:50] + "..." if len(text) > 50 else text
            return f"Speak: \"{preview}\""
        
        elif action_type == ActionType.CLIPBOARD_READ:
            return "Read text from clipboard"
        
        return f"Execute {action_type.value}"


# =============================================================================
# CONFIRMATION UI
# =============================================================================

class ConfirmationUI:
    """
    UI for action confirmation.
    
    Shows a dialog with:
    - What action will be performed
    - Parameters/preview
    - Approve/Reject buttons
    - Timeout countdown
    """
    
    def __init__(self, timeout_seconds: int = 15):
        self.timeout = timeout_seconds
        self._result: Optional[ConfirmationResult] = None
        self._lock = threading.Lock()
    
    def show_confirmation(
        self,
        action_preview: str,
        risk_level: RiskLevel,
        timeout: Optional[int] = None,
    ) -> ConfirmationResult:
        """
        Show confirmation dialog and wait for response.
        
        Returns ConfirmationResult after user action or timeout.
        """
        timeout = timeout or self.timeout
        
        # Build dialog content based on risk level
        title = self._get_title(risk_level)
        icon = self._get_icon(risk_level)
        
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            # Create hidden root
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            # Result variable
            result = [ConfirmationResult.TIMEOUT]
            
            def on_yes():
                result[0] = ConfirmationResult.APPROVED
                dialog.destroy()
                root.quit()
            
            def on_no():
                result[0] = ConfirmationResult.REJECTED
                dialog.destroy()
                root.quit()
            
            def on_timeout():
                if result[0] == ConfirmationResult.TIMEOUT:
                    dialog.destroy()
                    root.quit()
            
            # Create dialog
            dialog = tk.Toplevel(root)
            dialog.title(title)
            dialog.attributes('-topmost', True)
            dialog.protocol("WM_DELETE_WINDOW", on_no)
            
            # Center on screen
            dialog.geometry("400x200")
            dialog.resizable(False, False)
            
            # Icon/warning based on risk
            if risk_level in (RiskLevel.MEDIUM, RiskLevel.HIGH):
                warning_text = "⚠️ " if risk_level == RiskLevel.MEDIUM else "🛑 "
            else:
                warning_text = "ℹ️ "
            
            # Content
            tk.Label(
                dialog,
                text=warning_text + "SAARTHI wants to:",
                font=("Segoe UI", 12),
                pady=10,
            ).pack()
            
            tk.Label(
                dialog,
                text=action_preview,
                font=("Segoe UI", 11, "bold"),
                wraplength=350,
                pady=10,
            ).pack()
            
            # Timeout countdown
            countdown_var = tk.StringVar(value=f"Auto-reject in {timeout}s")
            countdown_label = tk.Label(
                dialog,
                textvariable=countdown_var,
                font=("Segoe UI", 9),
                fg="gray",
            )
            countdown_label.pack(pady=5)
            
            # Buttons
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=15)
            
            tk.Button(
                btn_frame,
                text="✓ Allow",
                command=on_yes,
                width=10,
                bg="#4CAF50",
                fg="white",
                font=("Segoe UI", 10),
            ).pack(side=tk.LEFT, padx=10)
            
            tk.Button(
                btn_frame,
                text="✗ Deny",
                command=on_no,
                width=10,
                bg="#f44336",
                fg="white",
                font=("Segoe UI", 10),
            ).pack(side=tk.LEFT, padx=10)
            
            # Countdown timer
            remaining = [timeout]
            
            def update_countdown():
                remaining[0] -= 1
                if remaining[0] <= 0:
                    on_timeout()
                else:
                    countdown_var.set(f"Auto-reject in {remaining[0]}s")
                    dialog.after(1000, update_countdown)
            
            dialog.after(1000, update_countdown)
            
            # Set timeout
            root.after(timeout * 1000, on_timeout)
            
            # Focus dialog
            dialog.focus_force()
            dialog.lift()
            
            # Run dialog
            root.mainloop()
            root.destroy()
            
            return result[0]
            
        except ImportError:
            # Fallback to console
            print(f"\n{'='*50}")
            print(f"{title}")
            print(f"{'='*50}")
            print(f"\nSAARTHI wants to: {action_preview}")
            print(f"\nRespond within {timeout} seconds...")
            
            # Simple timeout input
            import select
            import sys
            
            if sys.platform == "win32":
                # Windows doesn't support select on stdin
                # Use simpler approach
                try:
                    response = input("\nAllow? [y/N]: ").strip().lower()
                    if response in ("y", "yes"):
                        return ConfirmationResult.APPROVED
                    return ConfirmationResult.REJECTED
                except:
                    return ConfirmationResult.TIMEOUT
            else:
                # Unix with select
                print("\nAllow? [y/N]: ", end="", flush=True)
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if ready:
                    response = sys.stdin.readline().strip().lower()
                    if response in ("y", "yes"):
                        return ConfirmationResult.APPROVED
                    return ConfirmationResult.REJECTED
                return ConfirmationResult.TIMEOUT
    
    def _get_title(self, risk_level: RiskLevel) -> str:
        """Get dialog title based on risk."""
        titles = {
            RiskLevel.SAFE: "SAARTHI Action",
            RiskLevel.LOW: "SAARTHI - Confirm Action",
            RiskLevel.MEDIUM: "SAARTHI - Action Confirmation Required",
            RiskLevel.HIGH: "⚠️ SAARTHI - Security Confirmation",
        }
        return titles.get(risk_level, "SAARTHI Confirmation")
    
    def _get_icon(self, risk_level: RiskLevel) -> str:
        """Get icon based on risk."""
        icons = {
            RiskLevel.SAFE: "info",
            RiskLevel.LOW: "info",
            RiskLevel.MEDIUM: "warning",
            RiskLevel.HIGH: "error",
        }
        return icons.get(risk_level, "info")


# =============================================================================
# ACTION EXECUTOR
# =============================================================================

class SafeDesktopExecutor:
    """
    Executes desktop actions with safety checks.
    
    FLOW:
    1. Receive action request
    2. Safety check (whitelist, parameters)
    3. Show confirmation UI (if required)
    4. Execute action (if approved)
    5. Log result (audit trail)
    """
    
    def __init__(self):
        self.safety_checker = SafetyChecker()
        self.confirmation_ui = ConfirmationUI()
        self._audit_log: List[Dict] = []
        self._handlers: Dict[ActionType, Callable] = {}
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register built-in action handlers."""
        self._handlers[ActionType.OPEN_URL] = self._handle_open_url
        self._handlers[ActionType.OPEN_APP] = self._handle_open_app
        self._handlers[ActionType.READ_FILE] = self._handle_read_file
        self._handlers[ActionType.NOTIFY] = self._handle_notify
        self._handlers[ActionType.SPEAK] = self._handle_speak
        self._handlers[ActionType.CLIPBOARD_READ] = self._handle_clipboard_read
    
    def execute(self, request: ActionRequest) -> ActionResult:
        """
        Execute a desktop action with full safety flow.
        
        1. Safety check
        2. Confirmation (if needed)
        3. Execute (if approved)
        4. Audit log
        """
        import uuid
        
        # Generate request ID if not present
        if not request.id:
            request.id = str(uuid.uuid4())[:8]
        
        # Step 1: Safety check
        check_result = self.safety_checker.check(request)
        
        if not check_result["allowed"]:
            result = ActionResult(
                request_id=request.id,
                success=False,
                error=check_result["reason"],
                confirmation=ConfirmationResult.REJECTED,
            )
            self._log_audit(request, result, "blocked_by_safety")
            return result
        
        # Update request with check results
        request.risk_level = check_result["risk_level"]
        request.preview_text = check_result["preview"]
        request.confirmation_required = check_result["requires_confirmation"]
        
        # Step 2: Confirmation (if required)
        if check_result["requires_confirmation"]:
            confirmation = self.confirmation_ui.show_confirmation(
                action_preview=check_result["preview"],
                risk_level=check_result["risk_level"],
                timeout=check_result.get("timeout", 15),
            )
            
            if confirmation != ConfirmationResult.APPROVED:
                result = ActionResult(
                    request_id=request.id,
                    success=False,
                    error=f"Action {confirmation.value} by user",
                    confirmation=confirmation,
                )
                self._log_audit(request, result, "user_rejected")
                return result
        
        # Step 3: Execute action
        start_time = datetime.now()
        
        try:
            handler = self._handlers.get(request.action_type)
            if not handler:
                raise ValueError(f"No handler for {request.action_type.value}")
            
            exec_result = handler(request.parameters)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() * 1000
            
            result = ActionResult(
                request_id=request.id,
                success=True,
                result=exec_result,
                confirmation=ConfirmationResult.APPROVED,
                confirmed_at=start_time,
                started_at=start_time,
                completed_at=end_time,
                duration_ms=duration,
            )
            
            self._log_audit(request, result, "executed")
            return result
            
        except Exception as e:
            end_time = datetime.now()
            
            result = ActionResult(
                request_id=request.id,
                success=False,
                error=str(e),
                confirmation=ConfirmationResult.APPROVED,
                started_at=start_time,
                completed_at=end_time,
            )
            
            self._log_audit(request, result, "execution_failed")
            return result
    
    # -------------------------------------------------------------------------
    # ACTION HANDLERS
    # -------------------------------------------------------------------------
    
    def _handle_open_url(self, params: Dict) -> Dict:
        """Open URL in default browser."""
        import webbrowser
        
        url = params.get("url")
        if not url:
            raise ValueError("URL is required")
        
        webbrowser.open(url)
        
        return {
            "action": "open_url",
            "url": url,
            "message": f"Opened {url}",
        }
    
    def _handle_open_app(self, params: Dict) -> Dict:
        """Open a whitelisted application."""
        import subprocess
        
        app_name = params.get("app_name", "")
        
        # Try to open via start command (Windows)
        try:
            subprocess.Popen(
                ["start", "", app_name],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {
                "action": "open_app",
                "app": app_name,
                "message": f"Opened {app_name}",
            }
        except Exception as e:
            raise ValueError(f"Could not open {app_name}: {e}")
    
    def _handle_read_file(self, params: Dict) -> Dict:
        """Read a file's contents."""
        file_path = params.get("file_path")
        if not file_path:
            raise ValueError("File path is required")
        
        path = Path(file_path)
        
        # Read file
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            
            # Truncate if too long
            max_chars = params.get("max_chars", 10000)
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n[Content truncated...]"
            
            return {
                "action": "read_file",
                "file": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "content": content,
            }
        except Exception as e:
            raise ValueError(f"Could not read file: {e}")
    
    def _handle_notify(self, params: Dict) -> Dict:
        """Show a desktop notification."""
        title = params.get("title", "SAARTHI")
        message = params.get("message", "")
        
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            # Fallback: print to console
            print(f"\n🔔 {title}: {message}")
        
        return {
            "action": "notify",
            "title": title,
            "message": message,
        }
    
    def _handle_speak(self, params: Dict) -> Dict:
        """Speak text using TTS."""
        text = params.get("text", "")
        if not text:
            raise ValueError("Text is required")
        
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text)
        except ImportError:
            print(f"🔊 {text}")
        
        return {
            "action": "speak",
            "text": text[:50] + "..." if len(text) > 50 else text,
        }
    
    def _handle_clipboard_read(self, params: Dict) -> Dict:
        """Read text from clipboard."""
        try:
            import win32clipboard
            
            win32clipboard.OpenClipboard()
            try:
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            except:
                data = ""
            finally:
                win32clipboard.CloseClipboard()
            
            return {
                "action": "clipboard_read",
                "content": data,
                "length": len(data),
            }
        except ImportError:
            # Fallback using tkinter
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                data = root.clipboard_get()
                root.destroy()
                return {
                    "action": "clipboard_read",
                    "content": data,
                    "length": len(data),
                }
            except:
                raise ValueError("Could not read clipboard")
    
    # -------------------------------------------------------------------------
    # AUDIT LOGGING
    # -------------------------------------------------------------------------
    
    def _log_audit(self, request: ActionRequest, result: ActionResult, status: str):
        """Log action for audit trail."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request.id,
            "action": request.action_type.value,
            "status": status,
            "success": result.success,
            "confirmation": result.confirmation.value,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }
        
        self._audit_log.append(entry)
        
        # Keep only last 100 entries
        if len(self._audit_log) > 100:
            self._audit_log.pop(0)
        
        # Print to console for debugging
        status_icon = "✓" if result.success else "✗"
        print(f"[AUDIT] {status_icon} {request.action_type.value}: {status}")
    
    def get_audit_log(self) -> List[Dict]:
        """Get recent audit log entries."""
        return self._audit_log.copy()


# =============================================================================
# CONVENIENCE INTERFACE
# =============================================================================

# Global executor instance
_executor: Optional[SafeDesktopExecutor] = None

def get_executor() -> SafeDesktopExecutor:
    """Get or create the global executor."""
    global _executor
    if _executor is None:
        _executor = SafeDesktopExecutor()
    return _executor


def open_url(url: str, site_name: str = "") -> ActionResult:
    """Convenience: Open a URL."""
    request = ActionRequest(
        id="",
        action_type=ActionType.OPEN_URL,
        parameters={"url": url, "site_name": site_name or url},
    )
    return get_executor().execute(request)


def open_app(app_name: str) -> ActionResult:
    """Convenience: Open an application."""
    request = ActionRequest(
        id="",
        action_type=ActionType.OPEN_APP,
        parameters={"app_name": app_name},
    )
    return get_executor().execute(request)


def read_file(file_path: str) -> ActionResult:
    """Convenience: Read a file."""
    request = ActionRequest(
        id="",
        action_type=ActionType.READ_FILE,
        parameters={"file_path": file_path},
    )
    return get_executor().execute(request)


def notify(title: str, message: str) -> ActionResult:
    """Convenience: Show notification."""
    request = ActionRequest(
        id="",
        action_type=ActionType.NOTIFY,
        parameters={"title": title, "message": message},
    )
    return get_executor().execute(request)


def speak(text: str) -> ActionResult:
    """Convenience: Speak text."""
    request = ActionRequest(
        id="",
        action_type=ActionType.SPEAK,
        parameters={"text": text},
    )
    return get_executor().execute(request)
