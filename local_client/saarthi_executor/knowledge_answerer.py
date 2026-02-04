"""
DIRECT KNOWLEDGE ANSWERER - STEP 3 FIX
======================================

PROBLEM: "Who is Elon Musk?" → "I don't know how to complete this"
SOLUTION: Answer knowledge questions DIRECTLY without planner/executor.

FLOW:
1. Question detected → route to knowledge system
2. Check built-in knowledge base (instant)
3. If not found, check Wikipedia (fast)
4. If offline, use generic explanation
5. NEVER say "I don't know" for general knowledge
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from .knowledge_router import get_answer, KnowledgeResult

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeAnswer:
    """Structured answer to knowledge question."""
    text: str
    confidence: float  # 0.0 to 1.0
    source: str  # built_in, wikipedia, generic, error
    success: bool
    topic: str


class DirectKnowledgeAnswerer:
    """
    Answers knowledge questions WITHOUT planner/executor.
    
    PRINCIPLE: Questions deserve answers, not "I don't know".
    """
    
    # Generic fallback explanations for common question types
    GENERIC_EXPLANATIONS = {
        "who": "I don't have specific information about that person right now. Could you ask about their role or achievements instead?",
        "what": "I don't have details on that topic at the moment. Try asking a more specific question or check online resources.",
        "when": "I don't have that date/time information. You might want to search online for accurate historical data.",
        "where": "I don't have location information. Try searching online or in maps for accurate details.",
        "why": "That's a complex question that requires context I don't have. Let me try to explain the basics...",
        "how": "That's a broad question. Could you be more specific about what aspect you want to know?",
    }
    
    def __init__(self, offline_manager=None):
        """
        Args:
            offline_manager: Optional offline manager for connectivity awareness
        """
        self._offline = offline_manager
    
    def answer(self, question: str, topic: Optional[str] = None) -> KnowledgeAnswer:
        """
        Answer a knowledge question directly.
        
        Args:
            question: The question text
            topic: Optional extracted topic (e.g., "Elon Musk" from "Who is Elon Musk?")
        
        Returns:
            KnowledgeAnswer with response
        """
        # Extract topic if not provided
        if not topic:
            topic = self._extract_topic(question)
        
        logger.info(f"Answering knowledge question: {question} (topic: {topic})")
        
        # Try knowledge router (built-in + Wikipedia)
        try:
            result = get_answer(topic, timeout=3.0)
            
            if result.confidence > 0.5:
                return KnowledgeAnswer(
                    text=result.answer,
                    confidence=result.confidence,
                    source=result.source,
                    success=True,
                    topic=topic,
                )
        except Exception as e:
            logger.warning(f"Knowledge lookup failed: {e}")
        
        # Fallback: generic helpful response based on question type
        question_type = self._detect_question_type(question)
        generic_answer = self._generate_generic_answer(question, topic, question_type)
        
        return KnowledgeAnswer(
            text=generic_answer,
            confidence=0.3,  # Low confidence but helpful
            source="generic",
            success=True,  # Still counts as success (we gave an answer)
            topic=topic,
        )
    
    def answer_explanation_request(self, topic: str) -> KnowledgeAnswer:
        """
        Answer "explain X" requests.
        
        Similar to questions but more detailed response expected.
        """
        logger.info(f"Explanation requested for: {topic}")
        
        # Try knowledge router
        try:
            result = get_answer(topic, timeout=3.0)
            
            if result.confidence > 0.5:
                # For explanations, we might want to expand the answer
                expanded = self._expand_for_explanation(result.answer, topic)
                
                return KnowledgeAnswer(
                    text=expanded,
                    confidence=result.confidence,
                    source=result.source,
                    success=True,
                    topic=topic,
                )
        except Exception as e:
            logger.warning(f"Explanation lookup failed: {e}")
        
        # Fallback
        generic = f"I don't have detailed information about {topic} right now. " \
                 f"This topic might require online research or specialized knowledge. " \
                 f"Try searching online or asking a more specific question."
        
        return KnowledgeAnswer(
            text=generic,
            confidence=0.2,
            source="generic",
            success=True,
            topic=topic,
        )
    
    def _extract_topic(self, question: str) -> str:
        """
        Extract main topic from question.
        
        Examples:
        - "Who is Elon Musk?" → "Elon Musk"
        - "What is binary search?" → "binary search"
        - "How does WiFi work?" → "WiFi"
        """
        import re
        
        # Remove common question words
        patterns = [
            r'^(who|what|when|where|why|how)\s+(is|are|was|were|does|do|did)\s+',
            r'^(tell me about|explain|define|describe)\s+',
            r'\?+$',  # Remove question marks
        ]
        
        topic = question.lower()
        for pattern in patterns:
            topic = re.sub(pattern, '', topic, flags=re.I)
        
        # Clean up
        topic = topic.strip()
        
        # If too short, use original
        if len(topic) < 3:
            return question
        
        return topic
    
    def _detect_question_type(self, question: str) -> str:
        """Detect question type (who, what, when, etc.)."""
        q_lower = question.lower()
        
        for qtype in ['who', 'what', 'when', 'where', 'why', 'how']:
            if q_lower.startswith(qtype):
                return qtype
        
        return 'general'
    
    def _generate_generic_answer(
        self, 
        question: str, 
        topic: str, 
        question_type: str
    ) -> str:
        """
        Generate helpful generic answer when we don't know specifics.
        
        PRINCIPLE: "I don't know but here's how to find out" > "I don't know"
        """
        # Check if offline
        is_offline = self._offline and self._offline.is_offline()
        
        if is_offline:
            return f"I'm currently offline and don't have information about {topic}. " \
                   f"Once you're back online, I can help you search for this."
        
        # Generic helpful response
        base = self.GENERIC_EXPLANATIONS.get(
            question_type,
            f"I don't have specific information about {topic} right now."
        )
        
        # Add helpful suggestions
        suggestions = [
            f"You could try searching online for '{topic}'",
            f"Wikipedia might have detailed information about {topic}",
            "Try asking a more specific question about what aspect interests you",
        ]
        
        import random
        suggestion = random.choice(suggestions)
        
        return f"{base} {suggestion}."
    
    def _expand_for_explanation(self, answer: str, topic: str) -> str:
        """
        Expand answer for explanation requests.
        
        Add context/structure for "explain X" requests.
        """
        # If answer is already long, return as-is
        if len(answer) > 200:
            return answer
        
        # Add explanatory prefix
        prefix = f"Let me explain {topic}: "
        
        # Check if answer already starts with topic
        if answer.lower().startswith(topic.lower()):
            return answer
        
        return prefix + answer
    
    def to_executor_result(self, answer: KnowledgeAnswer) -> Dict[str, Any]:
        """
        Convert to executor result format.
        
        Makes it compatible with existing executor return format.
        """
        return {
            "success": answer.success,
            "text": answer.text,
            "speak": True,
            "category": "answer",
            "source": answer.source,
            "topic": answer.topic,
            "confidence": answer.confidence,
        }


# =============================================================================
# FACTORY
# =============================================================================

_answerer_instance: Optional[DirectKnowledgeAnswerer] = None

def get_knowledge_answerer(offline_manager=None) -> DirectKnowledgeAnswerer:
    """Get singleton knowledge answerer."""
    global _answerer_instance
    if _answerer_instance is None:
        _answerer_instance = DirectKnowledgeAnswerer(offline_manager)
    return _answerer_instance


def answer_knowledge_question(
    question: str, 
    topic: Optional[str] = None,
    offline_manager=None
) -> KnowledgeAnswer:
    """Convenience function for answering questions."""
    answerer = get_knowledge_answerer(offline_manager)
    return answerer.answer(question, topic)
