"""
STUDENT MODE HANDLER - STEP 4 FIX
=================================

MAKES STUDENT MODE DISTINCT from normal conversation.

STUDENT MODE PRINCIPLES:
1. Explain BEFORE answering
2. Break down concepts step-by-step  
3. Ask level-appropriate follow-ups
4. Encourage understanding, not just answers

SUPPORTED:
- DSA (Data Structures & Algorithms)
- OS (Operating Systems)
- DBMS (Database Management)
- CN (Computer Networks)
- Assignment help
- Quiz/MCQ solving
- Resume analysis
"""

import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class StudentRequestType(Enum):
    """Types of student requests."""
    ASSIGNMENT_HELP = "assignment"
    QUIZ_MCQ = "quiz"
    CONCEPT_EXPLANATION = "concept"
    CODE_REVIEW = "code_review"
    RESUME_ANALYSIS = "resume"
    STUDY_PLAN = "study_plan"
    EXAM_PREP = "exam_prep"
    GENERAL_QUESTION = "general"


@dataclass
class StudentResponse:
    """Response in student mode."""
    text: str
    request_type: StudentRequestType
    subject: Optional[str] = None
    follow_up_questions: List[str] = None
    additional_resources: List[str] = None
    
    def __post_init__(self):
        if self.follow_up_questions is None:
            self.follow_up_questions = []
        if self.additional_resources is None:
            self.additional_resources = []


class StudentModeHandler:
    """
    Handles student-specific requests with teaching approach.
    
    DIFFERENCE from normal mode:
    - Explains concepts step-by-step
    - Asks clarifying questions
    - Encourages active learning
    - Provides resources for deeper study
    """
    
    # Subject patterns
    SUBJECT_PATTERNS = {
        'dsa': r'\b(dsa|data struct|algorithm|binary tree|linked list|graph|sorting|searching|heap|stack|queue|dp|dynamic programming)\b',
        'os': r'\b(os|operating system|process|thread|deadlock|semaphore|mutex|scheduling|memory management|paging)\b',
        'dbms': r'\b(dbms|database|sql|normalization|transaction|acid|join|index|query)\b',
        'cn': r'\b(cn|computer network|tcp|udp|ip|osi|http|dns|routing|switching)\b',
        'python': r'\b(python|pandas|numpy|django|flask)\b',
        'java': r'\b(java|spring|hibernate|servlet)\b',
        'web': r'\b(html|css|javascript|react|angular|node)\b',
    }
    
    # Assignment keywords
    ASSIGNMENT_KEYWORDS = [
        'assignment', 'homework', 'question paper',
        'solve this', 'help me with', 'stuck on'
    ]
    
    # Quiz keywords
    QUIZ_KEYWORDS = [
        'quiz', 'mcq', 'multiple choice', 'options',
        'correct answer', 'which option'
    ]
    
    def __init__(self, knowledge_base=None):
        """
        Args:
            knowledge_base: Optional knowledge base for fetching concepts
        """
        self._knowledge = knowledge_base
    
    def handle_student_request(self, text: str) -> StudentResponse:
        """
        Handle student request with teaching approach.
        
        Args:
            text: Student's request
        
        Returns:
            StudentResponse with explanation and guidance
        """
        # Detect request type
        request_type = self._detect_request_type(text)
        subject = self._detect_subject(text)
        
        logger.info(f"Student mode: {request_type.value} ({subject or 'general'})")
        
        # Route to appropriate handler
        if request_type == StudentRequestType.ASSIGNMENT_HELP:
            return self._handle_assignment(text, subject)
        
        elif request_type == StudentRequestType.QUIZ_MCQ:
            return self._handle_quiz(text, subject)
        
        elif request_type == StudentRequestType.CONCEPT_EXPLANATION:
            return self._handle_concept(text, subject)
        
        elif request_type == StudentRequestType.CODE_REVIEW:
            return self._handle_code_review(text, subject)
        
        elif request_type == StudentRequestType.RESUME_ANALYSIS:
            return self._handle_resume(text)
        
        elif request_type == StudentRequestType.STUDY_PLAN:
            return self._handle_study_plan(text, subject)
        
        else:
            return self._handle_general_student_query(text, subject)
    
    def _detect_request_type(self, text: str) -> StudentRequestType:
        """Detect what kind of help student needs."""
        text_lower = text.lower()
        
        # Assignment
        if any(kw in text_lower for kw in self.ASSIGNMENT_KEYWORDS):
            return StudentRequestType.ASSIGNMENT_HELP
        
        # Quiz/MCQ
        if any(kw in text_lower for kw in self.QUIZ_KEYWORDS):
            return StudentRequestType.QUIZ_MCQ
        
        # Code review
        if any(kw in text_lower for kw in ['review', 'check my code', 'is this correct']):
            return StudentRequestType.CODE_REVIEW
        
        # Resume
        if any(kw in text_lower for kw in ['resume', 'cv', 'curriculum vitae']):
            return StudentRequestType.RESUME_ANALYSIS
        
        # Study plan
        if any(kw in text_lower for kw in ['study plan', 'preparation', 'exam prep', 'gate', 'jee']):
            return StudentRequestType.STUDY_PLAN
        
        # Concept explanation (default for "explain", "teach", etc.)
        if any(kw in text_lower for kw in ['explain', 'teach', 'how does', 'what is']):
            return StudentRequestType.CONCEPT_EXPLANATION
        
        return StudentRequestType.GENERAL_QUESTION
    
    def _detect_subject(self, text: str) -> Optional[str]:
        """Detect subject area."""
        text_lower = text.lower()
        
        for subject, pattern in self.SUBJECT_PATTERNS.items():
            if re.search(pattern, text_lower, re.I):
                return subject.upper()
        
        return None
    
    def _handle_assignment(self, text: str, subject: Optional[str]) -> StudentResponse:
        """
        Handle assignment help.
        
        APPROACH: Guide, don't solve
        """
        response_parts = [
            "📚 **Assignment Help Mode**",
            "",
            "I'll help you UNDERSTAND this, not just give you the answer.",
            "",
            "**Let's break it down:**",
            "",
        ]
        
        # Ask clarifying questions
        questions = [
            "1. What specific part are you stuck on?",
            "2. Have you tried any approach so far?",
            "3. What concepts from class/lectures relate to this?",
        ]
        
        response_parts.extend(questions)
        response_parts.append("")
        response_parts.append("**My teaching approach:**")
        response_parts.append("• I'll explain the concept first")
        response_parts.append("• Then help you develop your own solution")
        response_parts.append("• I won't give direct answers (that's cheating!)")
        
        if subject:
            response_parts.append(f"\n**Subject detected:** {subject}")
        
        follow_ups = [
            "What part are you stuck on?",
            "Have you learned any similar concepts?",
            "Would you like me to explain the underlying concept first?",
        ]
        
        return StudentResponse(
            text="\n".join(response_parts),
            request_type=StudentRequestType.ASSIGNMENT_HELP,
            subject=subject,
            follow_up_questions=follow_ups,
        )
    
    def _handle_quiz(self, text: str, subject: Optional[str]) -> StudentResponse:
        """
        Handle quiz/MCQ help.
        
        APPROACH: Explain reasoning, don't reveal answer immediately
        """
        response = [
            "🎓 **Quiz Help Mode**",
            "",
            "I'll help you UNDERSTAND how to solve this, not just get the answer.",
            "",
            "**My approach:**",
            "1. First, let's understand what the question is asking",
            "2. I'll explain the concept behind it",
            "3. Then analyze each option together",
            "4. You tell me what YOU think is correct and why",
            "5. I'll confirm if you're right and explain",
            "",
            "**Ready?**",
            "• Share the question and options",
            "• Tell me what you already know about this topic",
        ]
        
        follow_ups = [
            "What does the question ask?",
            "What concept does this test?",
            "Have you eliminated any obviously wrong options?",
        ]
        
        return StudentResponse(
            text="\n".join(response),
            request_type=StudentRequestType.QUIZ_MCQ,
            subject=subject,
            follow_up_questions=follow_ups,
        )
    
    def _handle_concept(self, text: str, subject: Optional[str]) -> StudentResponse:
        """
        Handle concept explanation request.
        
        APPROACH: Layered explanation (simple → detailed)
        """
        # Extract concept
        concept = self._extract_concept(text)
        
        response = [
            f"🧠 **Explaining: {concept}**",
            "",
            "I'll explain this in layers:",
            "",
            "**1. Simple explanation** (ELI5)",
            "**2. Detailed explanation** (with examples)",
            "**3. Technical details** (for deep understanding)",
            "**4. Common pitfalls** (what students often miss)",
            "",
        ]
        
        # Try to get concept from knowledge base
        if self._knowledge:
            try:
                # Placeholder - would call actual knowledge base
                basic_info = f"{concept} is a fundamental concept in {subject or 'computer science'}."
                response.append(f"**Simple:** {basic_info}")
                response.append("")
            except:
                pass
        
        response.append("**Tell me your current level:**")
        response.append("• Beginner (just learning)")
        response.append("• Intermediate (have some idea)")
        response.append("• Advanced (want deep details)")
        
        follow_ups = [
            "What level are you at with this concept?",
            "Where are you learning this? (college course, self-study, etc.)",
            "Any specific aspect you want to focus on?",
        ]
        
        return StudentResponse(
            text="\n".join(response),
            request_type=StudentRequestType.CONCEPT_EXPLANATION,
            subject=subject,
            follow_up_questions=follow_ups,
            additional_resources=[
                f"Visualgo.net (for {subject} visualizations)" if subject == "DSA" else None,
                "GeeksforGeeks tutorials",
                "Practice problems",
            ]
        )
    
    def _handle_code_review(self, text: str, subject: Optional[str]) -> StudentResponse:
        """Handle code review request."""
        response = [
            "💻 **Code Review Mode**",
            "",
            "I'll review your code focusing on:",
            "• Logic correctness",
            "• Best practices",
            "• Edge cases",
            "• Optimization opportunities",
            "",
            "**Please share:**",
            "1. Your code",
            "2. What it's supposed to do",
            "3. Any errors you're getting",
        ]
        
        return StudentResponse(
            text="\n".join(response),
            request_type=StudentRequestType.CODE_REVIEW,
            subject=subject,
            follow_up_questions=["What problem is this code solving?"],
        )
    
    def _handle_resume(self, text: str) -> StudentResponse:
        """Handle resume analysis."""
        response = [
            "📄 **Resume Analysis Mode**",
            "",
            "I'll help improve your resume for tech roles.",
            "",
            "**What I'll check:**",
            "• Format and structure",
            "• Technical skills section",
            "• Project descriptions",
            "• Achievement quantification",
            "• ATS compatibility",
            "",
            "**Share your resume as:**",
            "• Text format, or",
            "• Tell me specific sections to review",
        ]
        
        return StudentResponse(
            text="\n".join(response),
            request_type=StudentRequestType.RESUME_ANALYSIS,
        )
    
    def _handle_study_plan(self, text: str, subject: Optional[str]) -> StudentResponse:
        """Handle study plan creation."""
        response = [
            "📅 **Study Plan Mode**",
            "",
            "I'll create a personalized study plan.",
            "",
            "**Tell me:**",
            "• What are you preparing for? (GATE, interview, exam)",
            "• How much time do you have?",
            "• What topics do you need to cover?",
            "• Current level (beginner/intermediate/advanced)",
        ]
        
        return StudentResponse(
            text="\n".join(response),
            request_type=StudentRequestType.STUDY_PLAN,
            subject=subject,
        )
    
    def _handle_general_student_query(self, text: str, subject: Optional[str]) -> StudentResponse:
        """Handle general student question."""
        response = [
            "👋 **Student Mode Active**",
            "",
            "I'm here to help you LEARN, not just get answers!",
            "",
            "**I can help with:**",
            "• Explaining concepts (DSA, OS, DBMS, CN)",
            "• Assignment guidance (not solutions!)",
            "• Quiz practice (with reasoning)",
            "• Code review",
            "• Resume improvement",
            "• Study plans",
            "",
            "**What would you like help with?**",
        ]
        
        return StudentResponse(
            text="\n".join(response),
            request_type=StudentRequestType.GENERAL_QUESTION,
            subject=subject,
        )
    
    def _extract_concept(self, text: str) -> str:
        """Extract concept name from explanation request."""
        # Remove question words
        concept = re.sub(r'^(explain|teach|what is|how does|tell me about)\s+', '', text, flags=re.I)
        concept = concept.replace('?', '').strip()
        
        if len(concept) < 3:
            return text
        
        return concept.title()
    
    def to_executor_result(self, response: StudentResponse) -> Dict[str, Any]:
        """Convert to executor result format."""
        return {
            "success": True,
            "text": response.text,
            "speak": False,  # Student mode responses are usually long, don't spam TTS
            "category": "student_help",
            "request_type": response.request_type.value,
            "subject": response.subject,
            "follow_up_questions": response.follow_up_questions,
        }


# =============================================================================
# FACTORY
# =============================================================================

_student_handler: Optional[StudentModeHandler] = None

def get_student_handler() -> StudentModeHandler:
    """Get singleton student mode handler."""
    global _student_handler
    if _student_handler is None:
        _student_handler = StudentModeHandler()
    return _student_handler


def handle_student_request(text: str) -> StudentResponse:
    """Convenience function."""
    return get_student_handler().handle_student_request(text)
