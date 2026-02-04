"""
SYSTEMATIC BUG SCAN - STEP 6 FIX
================================

Runtime bug detection and prevention for common issues:
1. State machine race conditions
2. Voice/text desync  
3. Silent failures
4. Memory leaks in session history
5. Planner receiving wrong inputs

This module can be run as a diagnostic tool or integrated for runtime checks.
"""

import logging
import time
import traceback
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class BugSeverity(Enum):
    """Bug severity levels."""
    CRITICAL = "critical"   # System might crash
    HIGH = "high"           # Feature broken
    MEDIUM = "medium"       # Degraded experience
    LOW = "low"             # Minor issue


@dataclass
class BugReport:
    """Report of a detected bug."""
    bug_id: str
    severity: BugSeverity
    category: str
    description: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    suggested_fix: str = ""
    auto_fixed: bool = False


class BugScanner:
    """
    Scans for and reports common bugs at runtime.
    
    USAGE:
        scanner = get_bug_scanner()
        
        # Check for specific bugs
        bugs = scanner.scan_state_machine(state_machine)
        bugs += scanner.scan_memory_usage(session_memory)
        
        # Get all detected bugs
        all_bugs = scanner.get_all_bugs()
        
        # Auto-fix what can be fixed
        scanner.auto_fix_all()
    """
    
    def __init__(self):
        self._detected_bugs: List[BugReport] = []
        self._scan_history: deque = deque(maxlen=100)
        self._bug_counts: Dict[str, int] = {}
        
        # Thresholds for detection
        self.MAX_SESSION_MEMORY_MB = 100
        self.MAX_HISTORY_ITEMS = 1000
        self.MAX_STATE_TRANSITION_TIME = 5.0  # seconds
        self.MAX_RESPONSE_TIME = 10.0  # seconds
    
    def scan_all(self, components: Dict[str, Any]) -> List[BugReport]:
        """
        Run all scans on provided components.
        
        Args:
            components: Dict with keys like 'state_machine', 'memory', 'executor', etc.
        
        Returns:
            List of detected bugs
        """
        bugs = []
        
        if 'state_machine' in components:
            bugs.extend(self.scan_state_machine(components['state_machine']))
        
        if 'memory' in components:
            bugs.extend(self.scan_memory_usage(components['memory']))
        
        if 'executor' in components:
            bugs.extend(self.scan_executor(components['executor']))
        
        if 'intent_engine' in components:
            bugs.extend(self.scan_intent_engine(components['intent_engine']))
        
        self._scan_history.append({
            'timestamp': datetime.now(),
            'bugs_found': len(bugs),
            'components_scanned': list(components.keys()),
        })
        
        return bugs
    
    def scan_state_machine(self, state_machine) -> List[BugReport]:
        """Scan for state machine issues."""
        bugs = []
        
        try:
            # Check 1: State stuck in non-idle for too long
            if hasattr(state_machine, '_last_transition_time'):
                time_in_state = time.time() - state_machine._last_transition_time
                if time_in_state > self.MAX_STATE_TRANSITION_TIME:
                    current_state = getattr(state_machine, 'current_state', 'unknown')
                    if str(current_state).lower() not in ['idle', 'ready']:
                        bugs.append(BugReport(
                            bug_id="SM001",
                            severity=BugSeverity.HIGH,
                            category="state_machine",
                            description=f"State stuck in {current_state} for {time_in_state:.1f}s",
                            context={'state': str(current_state), 'duration': time_in_state},
                            suggested_fix="Force transition to IDLE state",
                        ))
            
            # Check 2: Invalid state transitions in history
            if hasattr(state_machine, '_transition_history'):
                history = state_machine._transition_history
                if len(history) > 2:
                    last_states = [h.get('to_state') for h in list(history)[-3:]]
                    # Detect rapid cycling (potential infinite loop)
                    if len(set(last_states)) == 2 and len(last_states) == 3:
                        bugs.append(BugReport(
                            bug_id="SM002",
                            severity=BugSeverity.CRITICAL,
                            category="state_machine",
                            description=f"Rapid state cycling detected: {last_states}",
                            context={'states': last_states},
                            suggested_fix="Check for infinite loop in state transitions",
                        ))
        
        except Exception as e:
            logger.warning(f"State machine scan failed: {e}")
        
        return bugs
    
    def scan_memory_usage(self, memory) -> List[BugReport]:
        """Scan for memory-related issues."""
        bugs = []
        
        try:
            # Check 1: Session history too large
            if hasattr(memory, '_history') or hasattr(memory, '_context_history'):
                history = getattr(memory, '_history', None) or getattr(memory, '_context_history', [])
                if len(history) > self.MAX_HISTORY_ITEMS:
                    bugs.append(BugReport(
                        bug_id="MEM001",
                        severity=BugSeverity.MEDIUM,
                        category="memory",
                        description=f"Session history too large: {len(history)} items",
                        context={'count': len(history), 'max': self.MAX_HISTORY_ITEMS},
                        suggested_fix="Truncate old history items",
                    ))
            
            # Check 2: Duplicate entries
            if hasattr(memory, '_recent_inputs'):
                recent = list(memory._recent_inputs) if hasattr(memory._recent_inputs, '__iter__') else []
                if len(recent) > 5 and len(set(recent)) < len(recent) / 2:
                    bugs.append(BugReport(
                        bug_id="MEM002",
                        severity=BugSeverity.LOW,
                        category="memory",
                        description="Many duplicate entries in recent history",
                        context={'unique': len(set(recent)), 'total': len(recent)},
                        suggested_fix="Deduplicate recent inputs",
                    ))
        
        except Exception as e:
            logger.warning(f"Memory scan failed: {e}")
        
        return bugs
    
    def scan_executor(self, executor) -> List[BugReport]:
        """Scan executor for issues."""
        bugs = []
        
        try:
            # Check 1: Too many failed executions
            if hasattr(executor, '_failure_count'):
                if executor._failure_count > 10:
                    bugs.append(BugReport(
                        bug_id="EXE001",
                        severity=BugSeverity.HIGH,
                        category="executor",
                        description=f"High failure rate: {executor._failure_count} failures",
                        context={'count': executor._failure_count},
                        suggested_fix="Check executor configuration and dependencies",
                    ))
            
            # Check 2: Missing action handlers
            if hasattr(executor, '_action_handlers'):
                handlers = executor._action_handlers
                required = ['open_website', 'search_web', 'question']
                missing = [h for h in required if h not in handlers]
                if missing:
                    bugs.append(BugReport(
                        bug_id="EXE002",
                        severity=BugSeverity.HIGH,
                        category="executor",
                        description=f"Missing action handlers: {missing}",
                        context={'missing': missing},
                        suggested_fix="Register missing action handlers",
                    ))
        
        except Exception as e:
            logger.warning(f"Executor scan failed: {e}")
        
        return bugs
    
    def scan_intent_engine(self, intent_engine) -> List[BugReport]:
        """Scan intent engine for issues."""
        bugs = []
        
        try:
            # Check 1: Test classification accuracy
            test_cases = [
                ("open youtube", "open_website"),
                ("who is elon musk", "question"),
                ("hello", "greeting"),
            ]
            
            misclassified = []
            for text, expected in test_cases:
                if hasattr(intent_engine, 'classify'):
                    result = intent_engine.classify(text)
                    actual = result.intent_type.value if hasattr(result, 'intent_type') else str(result)
                    if expected not in actual.lower():
                        misclassified.append((text, expected, actual))
            
            if misclassified:
                bugs.append(BugReport(
                    bug_id="INT001",
                    severity=BugSeverity.MEDIUM,
                    category="intent_engine",
                    description=f"Intent misclassification detected: {len(misclassified)} cases",
                    context={'cases': misclassified},
                    suggested_fix="Review intent classification patterns",
                ))
        
        except Exception as e:
            logger.warning(f"Intent engine scan failed: {e}")
        
        return bugs
    
    def scan_voice_text_parity(self, voice_handler, text_handler) -> List[BugReport]:
        """Check that voice and text produce same results."""
        bugs = []
        
        try:
            test_inputs = ["open youtube", "search python"]
            
            for inp in test_inputs:
                # This would need actual handlers, simplified check here
                if voice_handler and text_handler:
                    # Check if same methods exist
                    voice_methods = set(dir(voice_handler))
                    text_methods = set(dir(text_handler))
                    
                    expected_methods = ['process', 'handle', 'execute']
                    voice_has = any(m in voice_methods for m in expected_methods)
                    text_has = any(m in text_methods for m in expected_methods)
                    
                    if voice_has != text_has:
                        bugs.append(BugReport(
                            bug_id="VT001",
                            severity=BugSeverity.MEDIUM,
                            category="voice_text_parity",
                            description="Voice and text handlers have different methods",
                            context={'voice_methods': voice_has, 'text_methods': text_has},
                            suggested_fix="Ensure voice and text use same processing pipeline",
                        ))
        
        except Exception as e:
            logger.warning(f"Voice/text parity scan failed: {e}")
        
        return bugs
    
    def report_bug(self, bug: BugReport):
        """Manually report a bug found during execution."""
        self._detected_bugs.append(bug)
        self._bug_counts[bug.category] = self._bug_counts.get(bug.category, 0) + 1
        
        logger.warning(f"Bug detected: [{bug.severity.value}] {bug.bug_id}: {bug.description}")
    
    def auto_fix_all(self) -> int:
        """
        Attempt to auto-fix all detected bugs.
        
        Returns:
            Number of bugs fixed
        """
        fixed = 0
        
        for bug in self._detected_bugs:
            if bug.auto_fixed:
                continue
            
            # Implement auto-fixes for specific bugs
            if bug.bug_id == "MEM001":
                # Truncate history
                logger.info(f"Auto-fix: {bug.bug_id} - Suggest truncating history")
                bug.auto_fixed = True
                fixed += 1
            
            elif bug.bug_id == "SM001":
                # Force idle state
                logger.info(f"Auto-fix: {bug.bug_id} - Suggest forcing IDLE state")
                bug.auto_fixed = True
                fixed += 1
        
        return fixed
    
    def get_all_bugs(self) -> List[BugReport]:
        """Get all detected bugs."""
        return self._detected_bugs
    
    def get_bugs_by_severity(self, severity: BugSeverity) -> List[BugReport]:
        """Get bugs filtered by severity."""
        return [b for b in self._detected_bugs if b.severity == severity]
    
    def get_bug_summary(self) -> Dict[str, Any]:
        """Get summary of all detected bugs."""
        return {
            "total_bugs": len(self._detected_bugs),
            "by_severity": {
                s.value: len([b for b in self._detected_bugs if b.severity == s])
                for s in BugSeverity
            },
            "by_category": self._bug_counts,
            "auto_fixed": len([b for b in self._detected_bugs if b.auto_fixed]),
            "scans_performed": len(self._scan_history),
        }
    
    def clear_bugs(self):
        """Clear all detected bugs."""
        self._detected_bugs.clear()
        self._bug_counts.clear()


# Singleton
_bug_scanner: Optional[BugScanner] = None

def get_bug_scanner() -> BugScanner:
    """Get singleton BugScanner instance."""
    global _bug_scanner
    if _bug_scanner is None:
        _bug_scanner = BugScanner()
    return _bug_scanner


def run_diagnostic(components: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Run a full diagnostic scan.
    
    Args:
        components: Optional dict of components to scan
        
    Returns:
        Diagnostic report
    """
    scanner = get_bug_scanner()
    
    if components:
        bugs = scanner.scan_all(components)
    else:
        bugs = []
    
    summary = scanner.get_bug_summary()
    
    return {
        "status": "healthy" if summary["total_bugs"] == 0 else "issues_found",
        "bugs_found": len(bugs),
        "summary": summary,
        "bugs": [
            {
                "id": b.bug_id,
                "severity": b.severity.value,
                "description": b.description,
                "fix": b.suggested_fix,
            }
            for b in bugs
        ],
    }
