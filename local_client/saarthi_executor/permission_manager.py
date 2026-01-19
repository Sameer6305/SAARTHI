"""
Permission Manager
==================

Handles user permission requests for all actions.

SECURITY INVARIANTS:
- EVERY action requires explicit user confirmation
- No remembered permissions (each action asks anew)
- No auto-approved permissions
- User can always deny
- All permission decisions are logged
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Callable
import threading

logger = logging.getLogger(__name__)


class PermissionDecision(Enum):
    """User's permission decision."""
    
    ALLOW = "allow"
    DENY = "deny"
    TIMEOUT = "timeout"  # User didn't respond in time


@dataclass
class PermissionRequest:
    """A request for user permission."""
    
    action_id: str
    action_type: str
    description: str
    data_accessed: str
    risk_level: str
    timestamp: datetime


@dataclass
class PermissionRecord:
    """Record of a permission decision for audit."""
    
    request: PermissionRequest
    decision: PermissionDecision
    decided_at: datetime
    decision_time_ms: float  # How long user took to decide


class PermissionManager:
    """
    Manages permission requests to the user.
    
    SECURITY:
    - Every action requires fresh permission
    - No caching of permissions
    - No auto-approval
    - Denial is the default if anything goes wrong
    """
    
    # Timeout for permission dialog (seconds)
    PERMISSION_TIMEOUT_SECONDS: int = 60
    
    def __init__(self):
        """Initialize the permission manager."""
        self._permission_history: list[PermissionRecord] = []
        self._pending_request: Optional[PermissionRequest] = None
    
    def request_permission(
        self,
        action_id: str,
        action_type: str,
        description: str,
        data_accessed: str,
        risk_level: str,
    ) -> PermissionDecision:
        """
        Request user permission for an action.
        
        ALWAYS asks the user. NEVER auto-approves.
        
        Returns:
            PermissionDecision: User's decision (ALLOW, DENY, or TIMEOUT)
        """
        request = PermissionRequest(
            action_id=action_id,
            action_type=action_type,
            description=description,
            data_accessed=data_accessed,
            risk_level=risk_level,
            timestamp=datetime.utcnow(),
        )
        
        self._pending_request = request
        
        logger.info(
            "Permission requested",
            extra={
                "action_id": action_id,
                "action_type": action_type,
                "risk_level": risk_level,
            }
        )
        
        start_time = datetime.utcnow()
        
        # Show permission dialog (blocks until user responds)
        decision = self._show_permission_dialog(request)
        
        end_time = datetime.utcnow()
        decision_time_ms = (end_time - start_time).total_seconds() * 1000
        
        # Record the decision
        record = PermissionRecord(
            request=request,
            decision=decision,
            decided_at=end_time,
            decision_time_ms=decision_time_ms,
        )
        self._permission_history.append(record)
        
        logger.info(
            "Permission decision",
            extra={
                "action_id": action_id,
                "decision": decision.value,
                "decision_time_ms": round(decision_time_ms, 2),
            }
        )
        
        self._pending_request = None
        
        return decision
    
    def _show_permission_dialog(self, request: PermissionRequest) -> PermissionDecision:
        """
        Show the permission dialog to the user.
        
        This runs in a separate thread-safe way.
        """
        result = [PermissionDecision.DENY]  # Default to deny
        
        def show_dialog():
            """Create and show the dialog."""
            try:
                # Create root window (hidden)
                root = tk.Tk()
                root.withdraw()
                
                # Create dialog window
                dialog = tk.Toplevel(root)
                dialog.title("SAARTHI - Permission Required")
                dialog.geometry("500x400")
                dialog.resizable(False, False)
                
                # Make it stay on top
                dialog.attributes("-topmost", True)
                dialog.lift()
                dialog.focus_force()
                
                # Center on screen
                dialog.update_idletasks()
                x = (dialog.winfo_screenwidth() - 500) // 2
                y = (dialog.winfo_screenheight() - 400) // 2
                dialog.geometry(f"500x400+{x}+{y}")
                
                # Risk level colors
                risk_colors = {
                    "NONE": "#28a745",    # Green
                    "LOW": "#17a2b8",     # Blue
                    "MEDIUM": "#ffc107",  # Yellow
                    "HIGH": "#dc3545",    # Red
                }
                
                # Header
                header_frame = tk.Frame(dialog, bg="#2c3e50", height=60)
                header_frame.pack(fill="x")
                header_frame.pack_propagate(False)
                
                header_label = tk.Label(
                    header_frame,
                    text="⚠️ Permission Required",
                    font=("Segoe UI", 14, "bold"),
                    fg="white",
                    bg="#2c3e50"
                )
                header_label.pack(pady=15)
                
                # Content
                content_frame = tk.Frame(dialog, padx=20, pady=15)
                content_frame.pack(fill="both", expand=True)
                
                # Action type
                tk.Label(
                    content_frame,
                    text="Action:",
                    font=("Segoe UI", 10, "bold"),
                    anchor="w"
                ).pack(fill="x")
                
                tk.Label(
                    content_frame,
                    text=request.action_type.replace("_", " ").title(),
                    font=("Segoe UI", 10),
                    anchor="w",
                    fg="#555"
                ).pack(fill="x", pady=(0, 10))
                
                # Description
                tk.Label(
                    content_frame,
                    text="Description:",
                    font=("Segoe UI", 10, "bold"),
                    anchor="w"
                ).pack(fill="x")
                
                desc_text = tk.Text(
                    content_frame,
                    height=3,
                    font=("Segoe UI", 9),
                    wrap="word",
                    bg="#f8f9fa",
                    relief="flat"
                )
                desc_text.insert("1.0", request.description or "No description provided")
                desc_text.config(state="disabled")
                desc_text.pack(fill="x", pady=(0, 10))
                
                # Data accessed
                tk.Label(
                    content_frame,
                    text="Data Being Accessed:",
                    font=("Segoe UI", 10, "bold"),
                    anchor="w"
                ).pack(fill="x")
                
                tk.Label(
                    content_frame,
                    text=request.data_accessed or "None specified",
                    font=("Segoe UI", 9),
                    anchor="w",
                    fg="#555"
                ).pack(fill="x", pady=(0, 10))
                
                # Risk level
                risk_frame = tk.Frame(content_frame)
                risk_frame.pack(fill="x", pady=10)
                
                tk.Label(
                    risk_frame,
                    text="Risk Level:",
                    font=("Segoe UI", 10, "bold")
                ).pack(side="left")
                
                risk_label = tk.Label(
                    risk_frame,
                    text=f"  {request.risk_level}  ",
                    font=("Segoe UI", 10, "bold"),
                    fg="white",
                    bg=risk_colors.get(request.risk_level, "#6c757d")
                )
                risk_label.pack(side="left", padx=10)
                
                # Buttons
                button_frame = tk.Frame(dialog, pady=15)
                button_frame.pack(fill="x", side="bottom")
                
                def on_allow():
                    result[0] = PermissionDecision.ALLOW
                    dialog.destroy()
                    root.destroy()
                
                def on_deny():
                    result[0] = PermissionDecision.DENY
                    dialog.destroy()
                    root.destroy()
                
                # Deny button (left, less prominent)
                deny_btn = tk.Button(
                    button_frame,
                    text="Deny",
                    command=on_deny,
                    font=("Segoe UI", 10),
                    width=15,
                    bg="#6c757d",
                    fg="white",
                    relief="flat"
                )
                deny_btn.pack(side="left", padx=40)
                
                # Allow button (right, prominent)
                allow_btn = tk.Button(
                    button_frame,
                    text="Allow",
                    command=on_allow,
                    font=("Segoe UI", 10, "bold"),
                    width=15,
                    bg="#28a745",
                    fg="white",
                    relief="flat"
                )
                allow_btn.pack(side="right", padx=40)
                
                # Handle window close as deny
                def on_close():
                    result[0] = PermissionDecision.DENY
                    dialog.destroy()
                    root.destroy()
                
                dialog.protocol("WM_DELETE_WINDOW", on_close)
                
                # Timeout handling
                def on_timeout():
                    if dialog.winfo_exists():
                        result[0] = PermissionDecision.TIMEOUT
                        dialog.destroy()
                        root.destroy()
                
                root.after(self.PERMISSION_TIMEOUT_SECONDS * 1000, on_timeout)
                
                # Run dialog
                root.mainloop()
                
            except Exception as e:
                logger.error(f"Permission dialog error: {e}")
                result[0] = PermissionDecision.DENY  # Fail closed
        
        # Run in main thread (tkinter requirement)
        show_dialog()
        
        return result[0]
    
    def get_permission_history(
        self, 
        limit: int = 50
    ) -> list[PermissionRecord]:
        """Get recent permission decisions for audit."""
        return self._permission_history[-limit:]
    
    def get_approval_rate(self) -> float:
        """Get the percentage of allowed permissions."""
        if not self._permission_history:
            return 0.0
        
        allowed = sum(
            1 for r in self._permission_history 
            if r.decision == PermissionDecision.ALLOW
        )
        return (allowed / len(self._permission_history)) * 100
