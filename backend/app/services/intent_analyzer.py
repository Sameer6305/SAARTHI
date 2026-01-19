"""
Intent Analyzer Service
=======================

Analyzes user input to extract intent, entities, and risk assessment.

CRITICAL SECURITY NOTES:
- This service ABSTRACTS input, never stores raw text
- Output is suitable for memory storage
- All analysis is deterministic and auditable
"""

import re
from typing import Optional

from app.logging_config import get_logger
from app.models.domain import IntentAnalysis, RiskLevel

logger = get_logger("intent_analyzer")


class IntentAnalyzer:
    """
    Analyzes user input to determine intent.
    
    ARCHITECTURE NOTES:
    - In production, this would integrate with an LLM
    - Current implementation uses pattern matching (deterministic)
    - Output is ALWAYS abstracted (no raw input stored)
    
    SECURITY INVARIANTS:
    - Never returns raw user text in analysis
    - Entities are generalized (no specific names, paths, etc.)
    - Risk assessment is conservative (defaults to higher risk)
    """
    
    # Intent category patterns
    INTENT_PATTERNS: dict[str, list[str]] = {
        "file_operation": [
            r"\b(open|close|read|write|delete|move|copy|find|search|folder|file|document)\b",
        ],
        "app_control": [
            r"\b(launch|start|run|open|close|quit|exit|switch|app|application|program)\b",
        ],
        "browser_action": [
            r"\b(browser|chrome|firefox|edge|safari|web|website|url|search|google)\b",
        ],
        "system_operation": [
            r"\b(shutdown|restart|sleep|hibernate|settings|control panel|system)\b",
        ],
        "communication": [
            r"\b(email|mail|message|send|compose|reply|slack|teams|discord)\b",
        ],
        "media_control": [
            r"\b(play|pause|stop|music|video|youtube|spotify|volume|mute)\b",
        ],
        "information_request": [
            r"\b(what|how|why|when|where|tell me|explain|show me)\b",
        ],
    }
    
    # Tool category mapping
    TOOL_MAPPING: dict[str, list[str]] = {
        "file_operation": ["file.read", "file.write", "file.list", "file.delete"],
        "app_control": ["app.launch", "app.close", "app.switch"],
        "browser_action": ["browser.open", "browser.navigate", "browser.search"],
        "system_operation": ["system.settings", "system.power"],
        "communication": ["email.compose", "email.send", "chat.send"],
        "media_control": ["media.play", "media.pause", "media.control"],
        "information_request": [],  # Informational, no tools
    }
    
    # Risk assessment rules
    RISK_RULES: dict[str, RiskLevel] = {
        "file_operation": RiskLevel.MEDIUM,  # Could modify files
        "app_control": RiskLevel.LOW,        # Generally safe
        "browser_action": RiskLevel.LOW,     # Generally safe
        "system_operation": RiskLevel.HIGH,  # System-level changes
        "communication": RiskLevel.MEDIUM,   # Sends data externally
        "media_control": RiskLevel.NONE,     # No side effects
        "information_request": RiskLevel.NONE,
    }
    
    # Keywords that escalate risk
    HIGH_RISK_KEYWORDS: list[str] = [
        "delete", "remove", "destroy", "shutdown", "restart",
        "format", "erase", "wipe", "uninstall",
    ]
    
    CRITICAL_RISK_KEYWORDS: list[str] = [
        "all files", "everything", "entire", "system32",
        "registry", "admin", "root", "sudo",
    ]
    
    def __init__(self) -> None:
        """Initialize the intent analyzer."""
        # Compile patterns for performance
        self._compiled_patterns: dict[str, list[re.Pattern]] = {
            category: [re.compile(p, re.IGNORECASE) for p in patterns]
            for category, patterns in self.INTENT_PATTERNS.items()
        }
        
        logger.info("intent_analyzer_initialized")
    
    def analyze(self, input_text: str) -> IntentAnalysis:
        """
        Analyze input text and extract structured intent.
        
        SECURITY: This method:
        - Never stores or returns raw input
        - Returns only abstracted entities
        - Conservative risk assessment
        
        Args:
            input_text: The user's input (will NOT be stored)
        
        Returns:
            IntentAnalysis with abstracted intent information
        """
        # Normalize input for analysis
        normalized = input_text.lower().strip()
        
        # Detect intent category
        category, confidence = self._detect_category(normalized)
        
        # Generate abstracted summary (NO raw text)
        summary = self._generate_abstract_summary(category, normalized)
        
        # Detect abstracted entities
        entities = self._detect_entities(normalized)
        
        # Determine required tools
        required_tools = self.TOOL_MAPPING.get(category, [])
        
        # Assess risk
        risk = self._assess_risk(category, normalized)
        
        # Check if clarification is needed
        clarification_needed, questions = self._check_clarification(
            category, normalized, confidence
        )
        
        analysis = IntentAnalysis(
            intent_category=category,
            intent_summary=summary,
            confidence_score=confidence,
            detected_entities=entities,
            requires_tools=required_tools,
            estimated_risk=risk,
            clarification_needed=clarification_needed,
            clarification_questions=questions,
        )
        
        logger.info(
            "intent_analyzed",
            category=category,
            confidence=confidence,
            risk=risk.value,
            requires_clarification=clarification_needed,
        )
        
        return analysis
    
    def _detect_category(self, text: str) -> tuple[str, float]:
        """
        Detect the intent category from text.
        
        Returns (category, confidence_score).
        """
        scores: dict[str, int] = {}
        
        for category, patterns in self._compiled_patterns.items():
            match_count = sum(
                1 for pattern in patterns
                if pattern.search(text)
            )
            if match_count > 0:
                scores[category] = match_count
        
        if not scores:
            # Default to information request with low confidence
            return "information_request", 0.3
        
        # Get category with highest matches
        best_category = max(scores, key=scores.get)  # type: ignore
        
        # Calculate confidence (normalized by pattern count)
        max_patterns = len(self._compiled_patterns[best_category])
        confidence = min(0.95, 0.5 + (scores[best_category] / max_patterns) * 0.5)
        
        return best_category, confidence
    
    def _generate_abstract_summary(self, category: str, text: str) -> str:
        """
        Generate an abstracted summary of the intent.
        
        CRITICAL: This NEVER includes raw user text.
        """
        # Category-specific abstract summaries
        summaries = {
            "file_operation": "File system operation request",
            "app_control": "Application control request",
            "browser_action": "Web browser navigation request",
            "system_operation": "System settings or control request",
            "communication": "Communication or messaging request",
            "media_control": "Media playback control request",
            "information_request": "Information or help request",
        }
        
        base_summary = summaries.get(category, "General request")
        
        # Add abstracted modifiers based on detected patterns
        modifiers = []
        
        if any(kw in text for kw in ["find", "search", "locate"]):
            modifiers.append("search operation")
        if any(kw in text for kw in ["create", "new", "make"]):
            modifiers.append("creation operation")
        if any(kw in text for kw in ["delete", "remove"]):
            modifiers.append("deletion operation")
        if any(kw in text for kw in ["open", "launch", "start"]):
            modifiers.append("open/launch operation")
        
        if modifiers:
            return f"{base_summary}: {', '.join(modifiers)}"
        
        return base_summary
    
    def _detect_entities(self, text: str) -> list[str]:
        """
        Detect and ABSTRACT entities from text.
        
        CRITICAL: Returns generalized entity types, NOT specific values.
        """
        entities = []
        
        # Detect entity TYPES (abstracted)
        entity_patterns = {
            "document_reference": r"\b(document|file|pdf|doc|spreadsheet|report)\b",
            "folder_reference": r"\b(folder|directory|path)\b",
            "application_reference": r"\b(app|application|program|software)\b",
            "web_reference": r"\b(website|page|url|link)\b",
            "time_reference": r"\b(today|tomorrow|yesterday|morning|evening|week)\b",
            "person_reference": r"\b(contact|person|someone|user)\b",
        }
        
        for entity_type, pattern in entity_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                entities.append(entity_type)
        
        return entities
    
    def _assess_risk(self, category: str, text: str) -> RiskLevel:
        """
        Assess the risk level of the request.
        
        Conservative approach: escalates risk if uncertain.
        """
        # Start with category base risk
        base_risk = self.RISK_RULES.get(category, RiskLevel.MEDIUM)
        
        # Check for risk escalation keywords
        if any(kw in text for kw in self.CRITICAL_RISK_KEYWORDS):
            return RiskLevel.CRITICAL
        
        if any(kw in text for kw in self.HIGH_RISK_KEYWORDS):
            # Escalate by one level
            risk_order = [RiskLevel.NONE, RiskLevel.LOW, RiskLevel.MEDIUM, 
                         RiskLevel.HIGH, RiskLevel.CRITICAL]
            current_idx = risk_order.index(base_risk)
            return risk_order[min(current_idx + 1, len(risk_order) - 1)]
        
        return base_risk
    
    def _check_clarification(
        self,
        category: str,
        text: str,
        confidence: float,
    ) -> tuple[bool, list[str]]:
        """
        Check if clarification is needed from the user.
        
        Returns (needs_clarification, list_of_questions).
        """
        questions = []
        
        # Low confidence needs clarification
        if confidence < 0.5:
            questions.append(
                "I'm not sure I understood your request correctly. "
                "Could you please clarify what you'd like me to do?"
            )
        
        # Ambiguous scope needs clarification
        ambiguous_patterns = [
            (r"\b(some|a few|several)\b", "How many items should I work with?"),
            (r"\b(files?)\b(?!.*\b(specific|this|that)\b)", 
             "Which specific file(s) are you referring to?"),
            (r"\b(later|soon|sometime)\b", 
             "When would you like this to happen?"),
        ]
        
        for pattern, question in ambiguous_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                questions.append(question)
        
        # High-risk operations always need confirmation (but not clarification per se)
        # That's handled at the confirmation stage
        
        return len(questions) > 0, questions[:3]  # Limit to 3 questions


# Singleton instance
_intent_analyzer: Optional[IntentAnalyzer] = None


def get_intent_analyzer() -> IntentAnalyzer:
    """Get the singleton intent analyzer instance."""
    global _intent_analyzer
    if _intent_analyzer is None:
        _intent_analyzer = IntentAnalyzer()
    return _intent_analyzer
