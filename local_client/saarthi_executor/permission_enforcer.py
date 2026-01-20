"""
Permission Enforcement Module
=============================

STRONG PERMISSION ENFORCEMENT for SAARTHI action execution.

This module implements HARD GATE permission control:
- EVERY action MUST be approved by user before execution
- NO auto-approval under ANY circumstances
- NO remembered permissions
- Denial is ALWAYS the default

SECURITY INVARIANTS:
1. Only allowlisted actions can even reach the permission dialog
2. Any action not in allowlist is rejected WITHOUT user prompt
3. User must explicitly click "Allow" - no implicit approval
4. Window close = Deny
5. Timeout = Deny
6. Exception = Deny

ALLOWLIST (EXHAUSTIVE):
- open_browser_url: Opens URL in default browser
- play_media_file: Plays media via default application

ANY OTHER ACTION TYPE IS REJECTED IMMEDIATELY.
"""

import logging
import json
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# EXHAUSTIVE ALLOWLIST - Actions that can be shown to user for approval
# Any action NOT in this list is REJECTED without prompt
ACTION_ALLOWLIST: frozenset[str] = frozenset({
    "open_browser_url",
    "play_media_file",
})

# Actions that require EXPLICIT PROHIBITION (for defense in depth)
PROHIBITED_ACTIONS: frozenset[str] = frozenset({
    "shell_execute",
    "run_command",
    "subprocess",
    "file_delete",
    "file_write",
    "file_modify",
    "registry_write",
    "network_send",
    "download_file",
    "install_package",
    "system_config",
    "privilege_escalate",
})

# Risk level descriptions for user awareness
RISK_DESCRIPTIONS: dict[str, str] = {
    "NONE": "This action has no security implications.",
    "LOW": "This action is generally safe but will interact with your system.",
    "MEDIUM": "This action will access external resources or files.",
    "HIGH": "This action requires careful consideration before approval.",
}


# =============================================================================
# TYPES
# =============================================================================

class PermissionDecision(Enum):
    """User's permission decision."""
    ALLOW = "allow"              # User explicitly clicked Allow
    DENY = "deny"                # User explicitly clicked Deny
    TIMEOUT = "timeout"          # User didn't respond in time
    WINDOW_CLOSED = "closed"     # User closed the window
    ERROR = "error"              # An error occurred (fail closed)
    REJECTED = "rejected"        # Action rejected by allowlist policy


@dataclass
class ActionInfo:
    """
    Information about an action being requested.
    
    This is what the user sees in the permission dialog.
    """
    action_id: str
    action_type: str
    description: str
    target: str               # URL, file path, etc.
    risk_level: str
    risk_note: str           # Human-readable risk warning
    parameters: dict         # Raw parameters (for logging only)


@dataclass
class PermissionAuditEntry:
    """
    Audit log entry for a permission decision.
    
    CONTAINS NO USER DATA - only action metadata.
    """
    timestamp: str           # ISO 8601
    action_id: str
    action_type: str
    decision: str
    reason: str             # Why this decision was made
    decision_time_ms: float  # How long user took
    
    def to_json(self) -> str:
        """Convert to JSON for logging."""
        return json.dumps(asdict(self), indent=2)


# =============================================================================
# AUDIT LOGGER
# =============================================================================

class PermissionAuditLogger:
    """
    Logs all permission decisions for audit trail.
    
    SECURITY:
    - No sensitive content logged
    - No user data logged
    - Only action metadata
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize audit logger."""
        self._log_dir = log_dir or Path.home() / ".saarthi" / "audit"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "permission_audit.jsonl"
        
        logger.info(
            "Permission audit logger initialized",
            extra={"log_file": str(self._log_file)}
        )
    
    def log_decision(self, entry: PermissionAuditEntry) -> None:
        """Log a permission decision."""
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
            
            logger.info(
                "PERMISSION_AUDIT",
                extra={
                    "action_id": entry.action_id,
                    "action_type": entry.action_type,
                    "decision": entry.decision,
                    "reason": entry.reason,
                }
            )
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def log_policy_violation(
        self,
        action_id: str,
        action_type: str,
        violation: str,
    ) -> None:
        """Log a policy violation (action not in allowlist)."""
        entry = PermissionAuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            action_id=action_id,
            action_type=action_type,
            decision="POLICY_VIOLATION",
            reason=violation,
            decision_time_ms=0.0,
        )
        self.log_decision(entry)
        
        # Also log as security event
        logger.warning(
            "POLICY_VIOLATION",
            extra={
                "action_id": action_id,
                "action_type": action_type,
                "violation": violation,
            }
        )


# =============================================================================
# PERMISSION DIALOG
# =============================================================================

class PermissionDialog:
    """
    Modal permission dialog - HARD GATE for action execution.
    
    DESIGN:
    - Blocks until user responds
    - Clear display of action details
    - Only two buttons: Allow / Deny
    - Window close = Deny
    - Timeout = Deny
    - Error = Deny
    """
    
    # Dialog configuration
    WIDTH = 550
    HEIGHT = 450
    TIMEOUT_SECONDS = 60  # 1 minute timeout
    
    # Colors
    COLORS = {
        "header_bg": "#2c3e50",
        "header_fg": "white",
        "content_bg": "#ffffff",
        "risk_NONE": "#28a745",
        "risk_LOW": "#17a2b8",
        "risk_MEDIUM": "#ffc107",
        "risk_HIGH": "#dc3545",
        "allow_btn": "#28a745",
        "deny_btn": "#dc3545",
    }
    
    def __init__(self, action_info: ActionInfo):
        """Initialize the permission dialog."""
        self._action_info = action_info
        self._decision: PermissionDecision = PermissionDecision.DENY
        self._root: Optional[tk.Tk] = None
        self._dialog: Optional[tk.Toplevel] = None
    
    def show(self) -> PermissionDecision:
        """
        Show the permission dialog and block until user responds.
        
        Returns:
            PermissionDecision - ALWAYS returns a valid decision
        """
        try:
            self._create_dialog()
            self._root.mainloop()
        except Exception as e:
            logger.error(f"Permission dialog error: {e}")
            self._decision = PermissionDecision.ERROR
        
        return self._decision
    
    def _create_dialog(self) -> None:
        """Create the dialog window."""
        # Create hidden root
        self._root = tk.Tk()
        self._root.withdraw()
        
        # Create dialog
        self._dialog = tk.Toplevel(self._root)
        self._dialog.title("SAARTHI - Permission Required")
        self._dialog.resizable(False, False)
        
        # Center on screen
        screen_w = self._dialog.winfo_screenwidth()
        screen_h = self._dialog.winfo_screenheight()
        x = (screen_w - self.WIDTH) // 2
        y = (screen_h - self.HEIGHT) // 2
        self._dialog.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        
        # Make modal
        self._dialog.attributes("-topmost", True)
        self._dialog.grab_set()
        self._dialog.focus_force()
        
        # Build UI
        self._build_header()
        self._build_content()
        self._build_buttons()
        
        # Handle window close
        self._dialog.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Set timeout
        self._root.after(self.TIMEOUT_SECONDS * 1000, self._on_timeout)
    
    def _build_header(self) -> None:
        """Build the header section."""
        header = tk.Frame(
            self._dialog,
            bg=self.COLORS["header_bg"],
            height=70,
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # Warning icon and title
        tk.Label(
            header,
            text="⚠️  Permission Required",
            font=("Segoe UI", 16, "bold"),
            fg=self.COLORS["header_fg"],
            bg=self.COLORS["header_bg"],
        ).pack(pady=20)
    
    def _build_content(self) -> None:
        """Build the content section."""
        content = tk.Frame(
            self._dialog,
            bg=self.COLORS["content_bg"],
            padx=25,
            pady=20,
        )
        content.pack(fill="both", expand=True)
        
        # Action type
        self._add_field(content, "Action:", self._format_action_type())
        
        # Target (URL, file, etc.)
        self._add_field(content, "Target:", self._action_info.target)
        
        # Description
        self._add_field(content, "Description:", self._action_info.description)
        
        # Risk level with colored badge
        risk_frame = tk.Frame(content, bg=self.COLORS["content_bg"])
        risk_frame.pack(fill="x", pady=5)
        
        tk.Label(
            risk_frame,
            text="Risk Level:",
            font=("Segoe UI", 10, "bold"),
            bg=self.COLORS["content_bg"],
        ).pack(side="left")
        
        risk_color = self.COLORS.get(
            f"risk_{self._action_info.risk_level}",
            "#6c757d"
        )
        
        tk.Label(
            risk_frame,
            text=f"  {self._action_info.risk_level}  ",
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=risk_color,
            padx=10,
        ).pack(side="left", padx=10)
        
        # Risk note (warning message)
        risk_note_frame = tk.Frame(content, bg="#fff3cd", padx=15, pady=10)
        risk_note_frame.pack(fill="x", pady=15)
        
        tk.Label(
            risk_note_frame,
            text="⚠️ " + self._action_info.risk_note,
            font=("Segoe UI", 9),
            fg="#856404",
            bg="#fff3cd",
            wraplength=470,
            justify="left",
        ).pack()
    
    def _add_field(self, parent: tk.Frame, label: str, value: str) -> None:
        """Add a labeled field to the content."""
        frame = tk.Frame(parent, bg=self.COLORS["content_bg"])
        frame.pack(fill="x", pady=5)
        
        tk.Label(
            frame,
            text=label,
            font=("Segoe UI", 10, "bold"),
            bg=self.COLORS["content_bg"],
            width=12,
            anchor="w",
        ).pack(side="left")
        
        tk.Label(
            frame,
            text=value,
            font=("Segoe UI", 10),
            fg="#333",
            bg=self.COLORS["content_bg"],
            wraplength=400,
            anchor="w",
            justify="left",
        ).pack(side="left", fill="x", expand=True)
    
    def _build_buttons(self) -> None:
        """Build the button section."""
        button_frame = tk.Frame(self._dialog, pady=20, bg="#f8f9fa")
        button_frame.pack(fill="x", side="bottom")
        
        # Deny button (left, red)
        deny_btn = tk.Button(
            button_frame,
            text="❌  Deny",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg=self.COLORS["deny_btn"],
            activebackground="#c82333",
            width=15,
            height=2,
            relief="flat",
            command=self._on_deny,
        )
        deny_btn.pack(side="left", padx=40)
        
        # Allow button (right, green)
        allow_btn = tk.Button(
            button_frame,
            text="✓  Allow",
            font=("Segoe UI", 11, "bold"),
            fg="white",
            bg=self.COLORS["allow_btn"],
            activebackground="#218838",
            width=15,
            height=2,
            relief="flat",
            command=self._on_allow,
        )
        allow_btn.pack(side="right", padx=40)
    
    def _format_action_type(self) -> str:
        """Format action type for display."""
        return self._action_info.action_type.replace("_", " ").title()
    
    def _on_allow(self) -> None:
        """Handle Allow button click."""
        self._decision = PermissionDecision.ALLOW
        self._close()
    
    def _on_deny(self) -> None:
        """Handle Deny button click."""
        self._decision = PermissionDecision.DENY
        self._close()
    
    def _on_window_close(self) -> None:
        """Handle window close - DENY."""
        self._decision = PermissionDecision.WINDOW_CLOSED
        self._close()
    
    def _on_timeout(self) -> None:
        """Handle timeout - DENY."""
        if self._dialog and self._dialog.winfo_exists():
            self._decision = PermissionDecision.TIMEOUT
            self._close()
    
    def _close(self) -> None:
        """Close the dialog."""
        try:
            if self._dialog:
                self._dialog.destroy()
            if self._root:
                self._root.quit()
                self._root.destroy()
        except Exception:
            pass


# =============================================================================
# PERMISSION ENFORCER (MAIN CLASS)
# =============================================================================

class PermissionEnforcer:
    """
    HARD GATE permission enforcement for action execution.
    
    SECURITY GUARANTEES:
    1. Only allowlisted actions can request permission
    2. User must explicitly approve each action
    3. No auto-approval under any circumstances
    4. All decisions are logged for audit
    5. Fail-closed on any error
    
    USAGE:
        enforcer = PermissionEnforcer()
        
        # Check if action is allowed to be shown to user
        if not enforcer.is_action_allowed(action_type):
            # REJECT IMMEDIATELY - don't even show dialog
            return
        
        # Request permission
        decision = enforcer.request_permission(action_info)
        
        if decision == PermissionDecision.ALLOW:
            # Execute action
        else:
            # Do NOT execute
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize the permission enforcer."""
        self._audit_logger = PermissionAuditLogger(log_dir)
        
        logger.info(
            "PermissionEnforcer initialized",
            extra={"allowlist": list(ACTION_ALLOWLIST)}
        )
    
    # -------------------------------------------------------------------------
    # ALLOWLIST ENFORCEMENT
    # -------------------------------------------------------------------------
    
    def is_action_allowed(self, action_type: str) -> bool:
        """
        Check if action type is in the allowlist.
        
        Actions NOT in allowlist will NEVER be shown to user.
        They are rejected at the policy level.
        """
        return action_type in ACTION_ALLOWLIST
    
    def is_action_prohibited(self, action_type: str) -> bool:
        """
        Check if action type is explicitly prohibited.
        
        This is defense in depth - these actions are NEVER allowed.
        """
        return action_type in PROHIBITED_ACTIONS
    
    def reject_policy_violation(
        self,
        action_id: str,
        action_type: str,
    ) -> PermissionDecision:
        """
        Reject an action that violates policy (not in allowlist).
        
        This does NOT show a dialog - action is rejected immediately.
        """
        if self.is_action_prohibited(action_type):
            reason = f"Action type '{action_type}' is EXPLICITLY PROHIBITED"
        else:
            reason = f"Action type '{action_type}' is not in allowlist"
        
        self._audit_logger.log_policy_violation(
            action_id=action_id,
            action_type=action_type,
            violation=reason,
        )
        
        return PermissionDecision.REJECTED
    
    # -------------------------------------------------------------------------
    # PERMISSION REQUEST
    # -------------------------------------------------------------------------
    
    def request_permission(
        self,
        action_id: str,
        action_type: str,
        description: str,
        target: str,
        risk_level: str,
        parameters: dict,
    ) -> PermissionDecision:
        """
        Request user permission for an action.
        
        SECURITY:
        - Only called for allowlisted actions
        - Shows modal dialog
        - User must explicitly click Allow
        - Any other outcome = DENY
        
        Returns:
            PermissionDecision - the user's decision
        """
        # Safety check: verify action is allowed
        if not self.is_action_allowed(action_type):
            return self.reject_policy_violation(action_id, action_type)
        
        # Build risk note
        risk_note = self._get_risk_note(action_type, risk_level, target)
        
        # Create action info
        action_info = ActionInfo(
            action_id=action_id,
            action_type=action_type,
            description=description,
            target=target,
            risk_level=risk_level,
            risk_note=risk_note,
            parameters=parameters,
        )
        
        # Show dialog and get decision
        start_time = datetime.utcnow()
        
        dialog = PermissionDialog(action_info)
        decision = dialog.show()
        
        end_time = datetime.utcnow()
        decision_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Log the decision
        self._audit_logger.log_decision(
            PermissionAuditEntry(
                timestamp=end_time.isoformat(),
                action_id=action_id,
                action_type=action_type,
                decision=decision.value,
                reason=self._get_decision_reason(decision),
                decision_time_ms=round(decision_time_ms, 2),
            )
        )
        
        return decision
    
    def _get_risk_note(
        self,
        action_type: str,
        risk_level: str,
        target: str,
    ) -> str:
        """Generate a human-readable risk warning."""
        if action_type == "open_browser_url":
            return f"This will open your default web browser and navigate to: {target}"
        
        elif action_type == "play_media_file":
            return f"This will open a media file using your default application."
        
        else:
            return RISK_DESCRIPTIONS.get(
                risk_level,
                "Review this action carefully before approving."
            )
    
    def _get_decision_reason(self, decision: PermissionDecision) -> str:
        """Get human-readable reason for decision."""
        reasons = {
            PermissionDecision.ALLOW: "User clicked Allow",
            PermissionDecision.DENY: "User clicked Deny",
            PermissionDecision.TIMEOUT: "Permission dialog timed out",
            PermissionDecision.WINDOW_CLOSED: "User closed the dialog window",
            PermissionDecision.ERROR: "An error occurred (fail closed)",
            PermissionDecision.REJECTED: "Action rejected by policy",
        }
        return reasons.get(decision, "Unknown reason")
    
    # -------------------------------------------------------------------------
    # AUDIT
    # -------------------------------------------------------------------------
    
    def get_audit_log_path(self) -> Path:
        """Get path to the audit log file."""
        return self._audit_logger._log_file


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_permission_enforcer(log_dir: Optional[Path] = None) -> PermissionEnforcer:
    """Create a configured PermissionEnforcer instance."""
    return PermissionEnforcer(log_dir)
