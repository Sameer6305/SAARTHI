"""
Production-Grade Intelligence Router for SAARTHI
================================================

CRITICAL ROUTING RULES:
Every user input MUST go to EXACTLY ONE path:
- (A) CONVERSATIONAL/KNOWLEDGE - Factual questions answered directly
- (B) STUDENT_ASSISTANCE - Educational help, explanations, study tools
- (C) ACTION/DESKTOP_TASK - Open apps, search, system commands
- (D) CLARIFICATION_REQUIRED - Ambiguous input needs user clarification

DESIGN PRINCIPLES:
1. Factual questions NEVER go to planner - answer directly
2. Student mode is distinct from general knowledge
3. Actions always require confirmation
4. Ambiguous input prompts for clarification instead of guessing

Author: Principal AI Systems Engineer
Version: 1.0.0
"""

import re
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from functools import lru_cache

logger = logging.getLogger(__name__)


# =============================================================================
# ROUTING CATEGORIES
# =============================================================================

class RouteCategory(Enum):
    """Strict routing categories - every input goes to exactly ONE."""
    KNOWLEDGE = auto()      # Factual questions, general info
    STUDENT = auto()        # Educational, study, explanations
    ACTION = auto()         # Desktop tasks, open apps, search
    CLARIFICATION = auto()  # Ambiguous input needs more info
    CONVERSATION = auto()   # Greetings, thanks, social
    SYSTEM = auto()         # Status, help, settings


@dataclass
class RouteDecision:
    """Immutable routing decision."""
    category: RouteCategory
    confidence: float  # 0.0 to 1.0
    intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    requires_confirmation: bool = False
    alternative_category: Optional[RouteCategory] = None


# =============================================================================
# PATTERN DEFINITIONS
# =============================================================================

class ProductionPatterns:
    """
    Comprehensive pattern library for routing.
    
    PATTERN PRIORITY:
    1. Action patterns (most specific)
    2. Student patterns
    3. Knowledge patterns
    4. Conversation patterns
    5. Fallback to clarification
    """
    
    # ACTION patterns - Desktop tasks, apps, search
    ACTION_PATTERNS = [
        # Open websites
        (r"\b(?:open|go to|launch|show|visit|navigate to)\s+(?:the\s+)?(?:website\s+)?(?P<site>youtube|google|github|gmail|spotify|netflix|twitter|facebook|instagram|linkedin|reddit|stackoverflow|amazon|wikipedia|outlook|calendar)\b", "open_url"),
        (r"\b(?:open|go to|launch|visit)\s+(?P<url>https?://\S+)", "open_url"),
        (r"\b(?:open|go to|launch|visit)\s+(?P<domain>\S+\.(?:com|org|net|io|dev|edu|gov))", "open_url"),
        
        # YouTube specific
        (r"\b(?:play|open|search|find|watch)\s+(?:on\s+)?youtube\s+(?P<query>.+)", "youtube_search"),
        (r"\bplay\s+(?P<query>.+?)\s+(?:on|in)\s+youtube\b", "youtube_search"),
        
        # Open applications
        (r"\b(?:open|launch|start|run)\s+(?:the\s+)?(?P<app>notepad|calculator|cmd|terminal|powershell|explorer|chrome|firefox|edge|word|excel|powerpoint|outlook|vscode|vs code|visual studio|code)\b", "open_app"),
        
        # Web search
        (r"\b(?:search|google|look up|find)\s+(?:for\s+)?(?:on\s+(?:the\s+)?(?:web|internet|google)\s+)?['\"]?(?P<query>.+?)['\"]?\s*$", "search_web"),
        (r"\b(?:what|where|who|when|how|why).*(?:search|google|look up)\b", "search_web"),
        
        # File operations
        (r"\b(?:open|read|show|display)\s+(?:the\s+)?file\s+(?P<path>.+)", "open_file"),
        
        # System commands
        (r"\b(?:take\s+a\s+)?screenshot\b", "screenshot"),
        (r"\b(?:set\s+)?(?:an?\s+)?(?:alarm|timer|reminder)\s+(?:for\s+)?(?P<time>.+)", "set_reminder"),
    ]
    
    # STUDENT patterns - Educational focus
    STUDENT_PATTERNS = [
        # Simple explain patterns (most common)
        (r"^explain\s+(?P<topic>.+)$", "explain_cs"),
        (r"^describe\s+(?P<topic>.+)$", "explain_cs"),
        (r"^define\s+(?P<topic>.+)$", "explain_cs"),
        
        # Explanations with CS keywords
        (r"\b(?:explain|describe|define)\s+(?:a\s+|an\s+|the\s+)?(?P<topic>(?:binary\s+search|linked\s+list|stack|queue|recursion|big\s+o|hash\s+table|tree|graph|sorting|algorithm|data\s+structure|array|pointer|memory|cpu|cache|database|sql|api|rest|http|tcp|ip|dns|encryption|ssl|tls|class|object|inheritance|polymorphism|interface|abstract|design\s+pattern|singleton|factory|observer|mvc|mvvm).*)", "explain_cs"),
        (r"\b(?:explain|describe|what\s+is|tell\s+me\s+about)\s+(?P<topic>.+?)\s+(?:in\s+(?:programming|coding|computer\s+science|software|engineering))\b", "explain_cs"),
        
        # Formula help
        (r"\b(?:formula|equation)\s+(?:for\s+)?(?P<formula>.+)", "formula_help"),
        (r"\b(?:derive|derivation\s+of|proof\s+of)\s+(?P<formula>.+)", "derivation_help"),
        
        # Quiz/exam help
        (r"\b(?:help\s+(?:me\s+)?(?:with|understand)|quiz\s+(?:me|question)|test\s+(?:me|question)|practice\s+(?:problem|question))\b.*(?P<topic>.+)?", "quiz_help"),
        (r"\bhow\s+(?:do\s+i|to)\s+(?:solve|approach|tackle)\s+(?:this|the)?\s*(?P<problem>.+)", "problem_solving"),
        
        # Study planning
        (r"\b(?:create|make|plan)\s+(?:a\s+)?study\s+(?:plan|schedule)\s+(?:for\s+)?(?P<subject>.+)?", "study_plan"),
        (r"\bhow\s+(?:should\s+i|to)\s+study\s+(?:for\s+)?(?P<subject>.+)?", "study_advice"),
        
        # Assignment help
        (r"\b(?:help\s+(?:me\s+)?with|assist\s+(?:me\s+)?with)\s+(?:my\s+)?(?P<assignment>assignment|homework|project|lab|report)\b", "assignment_help"),
        
        # Document analysis (student context)
        (r"\b(?:analyze|review|summarize|explain)\s+(?:this|my|the)\s+(?P<doc>document|pdf|paper|article|notes)\b", "document_analysis"),
    ]
    
    # KNOWLEDGE patterns - Factual questions (answer directly, no planner)
    KNOWLEDGE_PATTERNS = [
        # Direct factual questions
        (r"^(?:what\s+is|what's|what\s+are)\s+(?:the\s+)?(?P<topic>.+?)\??$", "factual_question"),
        (r"^(?:who\s+is|who's|who\s+was|who\s+are)\s+(?P<person>.+?)\??$", "person_question"),
        (r"^(?:when\s+(?:is|was|did|does))\s+(?P<event>.+?)\??$", "time_question"),
        (r"^(?:where\s+is|where's|where\s+are)\s+(?P<place>.+?)\??$", "location_question"),
        (r"^(?:how\s+(?:many|much|old|tall|long|far))\s+(?P<measure>.+?)\??$", "measurement_question"),
        (r"^(?:why\s+(?:is|does|do|did|are|was|were))\s+(?P<reason>.+?)\??$", "reason_question"),
        
        # General info requests
        (r"\btell\s+me\s+(?:about|more\s+about)\s+(?P<topic>.+)", "tell_about"),
        (r"\bi\s+want\s+to\s+know\s+(?:about\s+)?(?P<topic>.+)", "info_request"),
        (r"\bcan\s+you\s+(?:tell\s+me|explain)\s+(?P<topic>.+)", "info_request"),
        
        # Definitions (general, not CS specific)
        (r"^define\s+(?P<term>.+?)\??$", "definition"),
        (r"^meaning\s+of\s+(?P<term>.+?)\??$", "definition"),
    ]
    
    # CONVERSATION patterns - Social, greetings
    CONVERSATION_PATTERNS = [
        (r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|howdy|greetings)\b", "greeting"),
        (r"^(?:thanks|thank\s+you|thx|ty|cheers)\b", "thanks"),
        (r"^(?:bye|goodbye|see\s+you|later|cya)\b", "farewell"),
        (r"^(?:how\s+are\s+you|how're\s+you|how\s+r\s+u|what's\s+up|sup)\b", "how_are_you"),
        (r"^(?:i'm\s+(?:good|fine|okay|great)|doing\s+(?:well|good|fine))\b", "user_status"),
        (r"^(?:nice|great|awesome|cool|excellent)\b", "positive_feedback"),
        (r"^(?:sorry|oops|my\s+bad)\b", "apology"),
    ]
    
    # SYSTEM patterns
    SYSTEM_PATTERNS = [
        (r"^(?:status|how\s+are\s+things|what's\s+your\s+status)\b", "status"),
        (r"^(?:help|what\s+can\s+you\s+do|capabilities)\b", "help"),
        (r"^(?:settings|preferences|options)\b", "settings"),
        (r"^(?:stop|quit|exit|cancel|nevermind|never\s+mind)\b", "cancel"),
        (r"^(?:yes|yeah|yep|sure|ok|okay|confirm|do\s+it|proceed)\b", "confirm_yes"),
        (r"^(?:no|nope|cancel|don't|deny)\b", "confirm_no"),
    ]
    
    @classmethod
    def compile_all(cls) -> Dict[RouteCategory, List[Tuple[re.Pattern, str]]]:
        """Compile all patterns for efficient matching."""
        return {
            RouteCategory.ACTION: [(re.compile(p, re.IGNORECASE), i) for p, i in cls.ACTION_PATTERNS],
            RouteCategory.STUDENT: [(re.compile(p, re.IGNORECASE), i) for p, i in cls.STUDENT_PATTERNS],
            RouteCategory.KNOWLEDGE: [(re.compile(p, re.IGNORECASE), i) for p, i in cls.KNOWLEDGE_PATTERNS],
            RouteCategory.CONVERSATION: [(re.compile(p, re.IGNORECASE), i) for p, i in cls.CONVERSATION_PATTERNS],
            RouteCategory.SYSTEM: [(re.compile(p, re.IGNORECASE), i) for p, i in cls.SYSTEM_PATTERNS],
        }


# =============================================================================
# KNOWLEDGE BASE - Direct Answers
# =============================================================================

class KnowledgeBase:
    """
    Direct knowledge for factual questions.
    NO PLANNER - answers immediately.
    """
    
    # Quick facts for common questions
    QUICK_FACTS = {
        # Tech facts
        "python": "Python is a high-level, interpreted programming language known for its readability and versatility. Created by Guido van Rossum in 1991.",
        "javascript": "JavaScript is a dynamic programming language primarily used for web development. It runs in browsers and on servers via Node.js.",
        "java": "Java is a class-based, object-oriented programming language designed for portability. 'Write once, run anywhere' is its philosophy.",
        "c++": "C++ is a general-purpose programming language that extends C with object-oriented features. Known for performance-critical applications.",
        "rust": "Rust is a systems programming language focused on safety, speed, and concurrency. It prevents memory errors at compile time.",
        
        # OS facts
        "linux": "Linux is an open-source Unix-like operating system kernel created by Linus Torvalds in 1991. It powers servers, phones, and embedded systems.",
        "windows": "Windows is a family of proprietary operating systems developed by Microsoft. It's the most widely used desktop OS globally.",
        "macos": "macOS is Apple's proprietary operating system for Mac computers. It's based on Unix and known for its design and integration with Apple hardware.",
        
        # General tech
        "api": "An API (Application Programming Interface) is a set of rules that allows different software applications to communicate with each other.",
        "database": "A database is an organized collection of structured information stored electronically. Common types include SQL (relational) and NoSQL.",
        "cloud computing": "Cloud computing delivers computing services (servers, storage, databases, software) over the internet, allowing for scalable on-demand resources.",
        "machine learning": "Machine learning is a subset of AI that enables systems to learn from data and improve without explicit programming.",
        "artificial intelligence": "Artificial Intelligence (AI) refers to computer systems that can perform tasks typically requiring human intelligence, like reasoning and learning.",
        
        # CS concepts
        "algorithm": "An algorithm is a step-by-step procedure for solving a problem or accomplishing a task in a finite number of steps.",
        "data structure": "A data structure is a way of organizing and storing data to enable efficient access and modification. Examples: arrays, trees, graphs.",
        "recursion": "Recursion is a programming technique where a function calls itself to solve smaller instances of the same problem.",
        "object-oriented programming": "OOP is a programming paradigm based on objects containing data and code. Key concepts: encapsulation, inheritance, polymorphism.",
        "functional programming": "Functional programming is a paradigm treating computation as evaluation of mathematical functions, avoiding state changes and mutable data.",
    }
    
    # Conversational responses
    CONVERSATIONAL = {
        "greeting": ["Hello! How can I help you today?", "Hey! What can I do for you?", "Hi there! Ready to assist."],
        "thanks": ["You're welcome!", "Happy to help!", "Anytime!"],
        "farewell": ["Goodbye! Have a great day!", "See you later!", "Bye! Take care!"],
        "how_are_you": ["I'm doing well, thanks for asking! How can I help you?", "All systems running smoothly! What can I do for you?"],
        "positive_feedback": ["Great to hear!", "Glad I could help!", "Awesome!"],
    }
    
    @classmethod
    def get_fact(cls, topic: str) -> Optional[str]:
        """Get a fact about a topic."""
        topic_lower = topic.lower().strip()
        
        # Exact match
        if topic_lower in cls.QUICK_FACTS:
            return cls.QUICK_FACTS[topic_lower]
        
        # Partial match
        for key, value in cls.QUICK_FACTS.items():
            if key in topic_lower or topic_lower in key:
                return value
        
        return None
    
    @classmethod
    def get_conversational(cls, intent: str) -> Optional[str]:
        """Get a conversational response."""
        import random
        responses = cls.CONVERSATIONAL.get(intent, [])
        return random.choice(responses) if responses else None


# =============================================================================
# PRODUCTION ROUTER
# =============================================================================

class ProductionRouter:
    """
    Production-grade intent router.
    
    GUARANTEES:
    1. Every input gets EXACTLY ONE route
    2. Confidence threshold enforced
    3. Ambiguous inputs go to CLARIFICATION
    4. Audit trail for all decisions
    """
    
    def __init__(self, min_confidence: float = 0.7):
        self._patterns = ProductionPatterns.compile_all()
        self._min_confidence = min_confidence
        self._decision_log: List[Dict] = []
    
    def route(self, text: str) -> RouteDecision:
        """
        Route user input to exactly one category.
        
        ALGORITHM:
        1. Try all pattern categories
        2. Pick highest confidence match
        3. If below threshold, return CLARIFICATION
        4. Log decision for audit
        """
        text = text.strip()
        if not text:
            return RouteDecision(
                category=RouteCategory.CLARIFICATION,
                confidence=0.0,
                intent="empty_input",
                reasoning="Empty input received",
            )
        
        candidates: List[RouteDecision] = []
        
        # Try each category in priority order
        priority_order = [
            RouteCategory.SYSTEM,       # Highest priority (confirmations, cancel)
            RouteCategory.ACTION,       # Desktop tasks
            RouteCategory.STUDENT,      # Educational
            RouteCategory.KNOWLEDGE,    # Factual questions
            RouteCategory.CONVERSATION, # Social
        ]
        
        for category in priority_order:
            patterns = self._patterns.get(category, [])
            for pattern, intent in patterns:
                match = pattern.search(text)
                if match:
                    # Calculate confidence based on match quality
                    match_length = len(match.group(0))
                    text_length = len(text)
                    base_confidence = match_length / text_length
                    
                    # Boost confidence for full matches
                    if match_length == text_length:
                        base_confidence = 1.0
                    elif base_confidence > 0.8:
                        base_confidence = min(1.0, base_confidence + 0.1)
                    
                    # Extract entities from named groups
                    entities = match.groupdict()
                    
                    # Determine if confirmation required
                    requires_confirmation = category == RouteCategory.ACTION
                    
                    decision = RouteDecision(
                        category=category,
                        confidence=base_confidence,
                        intent=intent,
                        entities=entities,
                        reasoning=f"Matched pattern for {intent}",
                        requires_confirmation=requires_confirmation,
                    )
                    candidates.append(decision)
                    break  # Use first match in category
        
        # Pick best candidate
        if candidates:
            best = max(candidates, key=lambda d: d.confidence)
            
            if best.confidence >= self._min_confidence:
                self._log_decision(text, best)
                return best
            else:
                # Set alternative for low confidence
                best = RouteDecision(
                    category=RouteCategory.CLARIFICATION,
                    confidence=best.confidence,
                    intent="low_confidence",
                    reasoning=f"Best match ({best.intent}) below threshold",
                    alternative_category=best.category,
                )
        else:
            best = RouteDecision(
                category=RouteCategory.CLARIFICATION,
                confidence=0.0,
                intent="no_match",
                reasoning="No pattern matched",
            )
        
        self._log_decision(text, best)
        return best
    
    def _log_decision(self, text: str, decision: RouteDecision):
        """Log routing decision for audit."""
        import time
        self._decision_log.append({
            "timestamp": time.time(),
            "input": text[:100],  # Truncate for privacy
            "category": decision.category.name,
            "intent": decision.intent,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
        })
        
        # Keep only last 1000 decisions
        if len(self._decision_log) > 1000:
            self._decision_log = self._decision_log[-1000:]
    
    def get_audit_log(self) -> List[Dict]:
        """Get routing audit log."""
        return self._decision_log.copy()


# =============================================================================
# RESPONSE GENERATORS
# =============================================================================

class KnowledgeResponder:
    """Generate responses for knowledge queries."""
    
    def __init__(self, llm_callback: Optional[Callable] = None):
        self._llm = llm_callback
    
    def respond(self, decision: RouteDecision) -> str:
        """Generate a knowledge response."""
        entities = decision.entities
        intent = decision.intent
        
        # Extract topic from various entity keys
        topic = (
            entities.get("topic") or
            entities.get("person") or
            entities.get("event") or
            entities.get("place") or
            entities.get("measure") or
            entities.get("reason") or
            entities.get("term") or
            ""
        ).strip()
        
        if not topic:
            return "What would you like to know about?"
        
        # Try knowledge base first (instant, no LLM)
        fact = KnowledgeBase.get_fact(topic)
        if fact:
            return fact
        
        # Use LLM for complex questions
        if self._llm:
            try:
                prompt = f"Answer this factual question concisely (2-3 sentences): {topic}"
                return self._llm(prompt)
            except Exception as e:
                logger.error(f"LLM failed for knowledge: {e}")
        
        return f"I don't have specific information about '{topic}' in my knowledge base. You could try searching online for more details."


class StudentResponder:
    """Generate responses for student/educational queries."""
    
    # CS topic explanations
    CS_EXPLANATIONS = {
        "binary search": "Binary search finds an element in a sorted array by repeatedly dividing the search interval in half. Time complexity: O(log n). Start with the middle element - if it's your target, you're done. If target is smaller, search left half; if larger, search right half.",
        
        "linked list": "A linked list is a linear data structure where elements are stored in nodes, each pointing to the next. Unlike arrays, elements aren't contiguous in memory. Types: singly linked (one direction), doubly linked (both directions). Operations: insert O(1) at known position, search O(n).",
        
        "stack": "A stack is a Last-In-First-Out (LIFO) data structure. Think of a stack of plates - you add and remove from the top only. Operations: push (add), pop (remove), peek (view top). Used in: function calls, undo operations, expression evaluation.",
        
        "queue": "A queue is a First-In-First-Out (FIFO) data structure. Like a line at a store - first person in is served first. Operations: enqueue (add to back), dequeue (remove from front). Used in: BFS, print queues, process scheduling.",
        
        "recursion": "Recursion is when a function calls itself to solve smaller instances of the same problem. Every recursive function needs: (1) Base case - when to stop, (2) Recursive case - break problem into smaller subproblems. Example: factorial(n) = n × factorial(n-1).",
        
        "big o": "Big O notation describes the upper bound of an algorithm's time/space complexity as input grows. Common complexities: O(1) constant - instant, O(log n) logarithmic - binary search, O(n) linear - single loop, O(n log n) - efficient sorting, O(n²) quadratic - nested loops.",
        
        "hash table": "A hash table stores key-value pairs using a hash function to compute an index. Average case: O(1) for insert, delete, lookup. Handles collisions via: chaining (linked lists) or open addressing (probing). Python dict, Java HashMap use hash tables.",
        
        "tree": "A tree is a hierarchical data structure with a root node and child nodes. Binary trees have at most 2 children per node. Types: BST (sorted), AVL (balanced), Heap (priority). Used in: file systems, DOM, databases.",
        
        "graph": "A graph is a collection of vertices (nodes) connected by edges. Types: directed/undirected, weighted/unweighted, cyclic/acyclic. Traversals: DFS (depth-first), BFS (breadth-first). Used in: social networks, maps, dependencies.",
        
        "sorting": "Sorting arranges elements in order. Key algorithms: Bubble Sort O(n²) - simple but slow, Merge Sort O(n log n) - divide and conquer, stable, Quick Sort O(n log n) average - fast in practice. Python uses Timsort, a hybrid of merge and insertion sort.",
        
        "dynamic programming": "Dynamic programming solves complex problems by breaking them into overlapping subproblems and storing solutions. Two approaches: top-down (memoization) and bottom-up (tabulation). Examples: Fibonacci, knapsack, longest common subsequence.",
        
        "object oriented programming": "OOP is a programming paradigm based on objects. Four pillars: (1) Encapsulation - bundle data and methods, (2) Abstraction - hide complexity, (3) Inheritance - reuse code, (4) Polymorphism - same interface, different implementations.",
        
        "design pattern": "Design patterns are reusable solutions to common software design problems. Categories: Creational (Singleton, Factory), Structural (Adapter, Decorator), Behavioral (Observer, Strategy). They improve code maintainability and communication.",
    }
    
    # Engineering formulas
    ENGINEERING_FORMULAS = {
        "ohm's law": "V = I × R (Voltage = Current × Resistance). Where V is in Volts, I in Amperes, R in Ohms.",
        "power": "P = V × I or P = I²R or P = V²/R. Power in Watts.",
        "kinetic energy": "KE = ½mv² (Kinetic Energy = half × mass × velocity squared). In Joules.",
        "potential energy": "PE = mgh (Potential Energy = mass × gravity × height). In Joules.",
        "newton's second law": "F = ma (Force = mass × acceleration). Force in Newtons.",
        "frequency": "f = 1/T (Frequency = 1/Period). In Hertz.",
        "wavelength": "λ = v/f (Wavelength = velocity/frequency). In meters.",
        "quadratic formula": "x = (-b ± √(b²-4ac)) / 2a. Solves ax² + bx + c = 0.",
        "pythagorean theorem": "a² + b² = c² (for right triangles, where c is hypotenuse).",
        "area of circle": "A = πr² (Area = pi × radius squared).",
        "volume of sphere": "V = (4/3)πr³.",
    }
    
    def __init__(self, llm_callback: Optional[Callable] = None):
        self._llm = llm_callback
    
    def respond(self, decision: RouteDecision) -> str:
        """Generate an educational response."""
        intent = decision.intent
        entities = decision.entities
        
        if intent in ("explain_cs", "explain"):
            return self._explain_cs(entities.get("topic", ""))
        
        elif intent in ("formula_help", "derivation_help"):
            return self._formula_help(entities.get("formula", ""))
        
        elif intent == "quiz_help":
            return self._quiz_help(entities.get("topic", ""))
        
        elif intent == "problem_solving":
            return self._problem_solving(entities.get("problem", ""))
        
        elif intent == "study_plan":
            return self._study_plan(entities.get("subject", ""))
        
        elif intent == "study_advice":
            return self._study_advice(entities.get("subject", ""))
        
        elif intent == "assignment_help":
            return self._assignment_help(entities.get("assignment", ""))
        
        elif intent == "document_analysis":
            return self._document_analysis(entities.get("doc", ""))
        
        else:
            return "I can help with explanations, formulas, quiz preparation, and study planning. What would you like to learn about?"
    
    def _explain_cs(self, topic: str) -> str:
        """Explain a CS topic."""
        if not topic:
            return "What topic would you like me to explain? I cover data structures, algorithms, programming concepts, and more."
        
        topic_lower = topic.lower().strip()
        
        # Check CS explanations
        for key, explanation in self.CS_EXPLANATIONS.items():
            if key in topic_lower or topic_lower in key:
                return explanation
        
        # Use LLM for unknown topics
        if self._llm:
            try:
                prompt = f"Explain '{topic}' for an engineering student in 3-4 sentences. Be clear and include practical context."
                return self._llm(prompt)
            except Exception as e:
                logger.error(f"LLM failed: {e}")
        
        return f"I'd love to explain '{topic}', but I need a bit more context. Could you tell me what aspect you're interested in? For example, are you looking for a definition, how it works, or when to use it?"
    
    def _formula_help(self, formula: str) -> str:
        """Help with a formula."""
        if not formula:
            return "Which formula do you need help with? I know physics, math, and electrical engineering formulas."
        
        formula_lower = formula.lower().strip()
        
        for key, explanation in self.ENGINEERING_FORMULAS.items():
            if key in formula_lower or formula_lower in key:
                return explanation
        
        if self._llm:
            try:
                prompt = f"Provide the formula for '{formula}' and explain each variable in one sentence each."
                return self._llm(prompt)
            except Exception as e:
                logger.error(f"LLM failed: {e}")
        
        return f"I don't have '{formula}' in my quick reference. Could you be more specific about which formula you need?"
    
    def _quiz_help(self, topic: str) -> str:
        """Help with quiz/exam preparation."""
        if topic:
            return f"To help with your quiz on '{topic}', let's approach this systematically:\n1. What specific concepts does this test?\n2. What do you already understand?\n3. What part is confusing you?\n\nWould you like me to explain the underlying concepts first, or do you have a specific question?"
        
        return "I'm here to help you prepare! Share the topic or question, and I'll help you understand the concept. Remember, I'll guide your thinking rather than give direct answers."
    
    def _problem_solving(self, problem: str) -> str:
        """Help solve a problem (guide, don't solve)."""
        if not problem:
            return "Share the problem you're working on, and I'll help you think through the approach."
        
        return f"Let's break down this problem:\n1. What is being asked? Identify the goal.\n2. What information is given?\n3. What concepts/formulas apply here?\n4. Can you break it into smaller steps?\n\nWhich of these steps would you like me to help you with for '{problem[:50]}...'?"
    
    def _study_plan(self, subject: str) -> str:
        """Create a study plan."""
        if not subject:
            return "What subject would you like me to create a study plan for? Also tell me your timeline and how many hours you can study daily."
        
        return f"To create an effective study plan for {subject}, I need:\n1. What topics are covered in this subject?\n2. When is your exam/deadline?\n3. How many hours per day can you study?\n4. Which topics do you find most difficult?\n\nShare these details and I'll create a personalized plan."
    
    def _study_advice(self, subject: str) -> str:
        """Give study advice."""
        general_tips = "Effective study techniques:\n• Active recall - test yourself instead of re-reading\n• Spaced repetition - review at increasing intervals\n• Feynman technique - explain concepts simply\n• Pomodoro - 25 min focus, 5 min break"
        
        if subject:
            return f"For studying {subject}:\n{general_tips}\n\nWould you like specific tips for {subject}?"
        
        return general_tips
    
    def _assignment_help(self, assignment_type: str) -> str:
        """Help with assignment (guide, don't do it)."""
        return f"I can help guide you through your {assignment_type}. Remember, I'll help you understand and learn, not do it for you. What specific part are you stuck on? Share:\n1. The assignment requirements\n2. What you've tried so far\n3. Where you're getting confused"
    
    def _document_analysis(self, doc_type: str) -> str:
        """Help analyze a document."""
        return f"I can help you understand and analyze your {doc_type}. However, I can't directly read files. Could you:\n1. Copy the key sections you want analyzed, or\n2. Tell me the main topic and your questions about it"


class ConversationResponder:
    """Generate conversational responses."""
    
    def respond(self, decision: RouteDecision) -> str:
        """Generate a conversational response."""
        response = KnowledgeBase.get_conversational(decision.intent)
        if response:
            return response
        return "How can I help you today?"


class ClarificationResponder:
    """Generate clarification requests."""
    
    CLARIFICATION_PROMPTS = {
        "empty_input": "I didn't catch that. Could you repeat?",
        "no_match": "I'm not sure what you'd like me to do. Could you rephrase that? I can:\n• Open websites and apps\n• Search the web\n• Explain topics\n• Help with studying",
        "low_confidence": "I think I understood, but I'm not certain. Could you be more specific?",
    }
    
    def respond(self, decision: RouteDecision) -> str:
        """Generate a clarification request."""
        base_response = self.CLARIFICATION_PROMPTS.get(
            decision.intent, 
            "Could you please rephrase that?"
        )
        
        if decision.alternative_category:
            base_response += f"\n\nDid you mean something related to {decision.alternative_category.name.lower()}?"
        
        return base_response


# =============================================================================
# MAIN PRODUCTION ASSISTANT
# =============================================================================

@dataclass
class AssistantResponse:
    """Response from the assistant."""
    text: str
    speak: bool = True
    action_executed: bool = False
    action_type: Optional[str] = None
    needs_clarification: bool = False
    error: Optional[str] = None
    route_category: Optional[RouteCategory] = None
    confidence: float = 1.0


class ProductionAssistant:
    """
    Production-grade assistant with strict routing.
    
    USAGE:
    ```python
    assistant = ProductionAssistant()
    response = assistant.process("what is binary search")
    print(response.text)
    ```
    """
    
    def __init__(self, llm_callback: Optional[Callable] = None, enable_tts: bool = True):
        # Router
        self.router = ProductionRouter()
        
        # Responders
        self.knowledge_responder = KnowledgeResponder(llm_callback)
        self.student_responder = StudentResponder(llm_callback)
        self.conversation_responder = ConversationResponder()
        self.clarification_responder = ClarificationResponder()
        
        # TTS
        self._tts_enabled = enable_tts
        self._tts: Optional[Any] = None
        if enable_tts:
            try:
                from saarthi_executor.integrated_assistant import SimpleTTS
                self._tts = SimpleTTS()
                self._tts.initialize()
            except Exception as e:
                logger.warning(f"TTS initialization failed: {e}")
        
        # Pending confirmation
        self._pending_action: Optional[RouteDecision] = None
        
        # Stats
        self._stats = {
            "total_requests": 0,
            "knowledge_requests": 0,
            "student_requests": 0,
            "action_requests": 0,
            "clarification_requests": 0,
            "actions_executed": 0,
        }
    
    def process(self, text: str) -> AssistantResponse:
        """
        Process user input with strict routing.
        
        GUARANTEED: Input goes to exactly ONE handler.
        """
        self._stats["total_requests"] += 1
        
        # Handle pending confirmations first
        if self._pending_action:
            return self._handle_confirmation(text)
        
        # Route the input
        decision = self.router.route(text)
        
        # Handle based on category
        if decision.category == RouteCategory.KNOWLEDGE:
            self._stats["knowledge_requests"] += 1
            response_text = self.knowledge_responder.respond(decision)
            
        elif decision.category == RouteCategory.STUDENT:
            self._stats["student_requests"] += 1
            response_text = self.student_responder.respond(decision)
            
        elif decision.category == RouteCategory.ACTION:
            self._stats["action_requests"] += 1
            # Actions require confirmation
            self._pending_action = decision
            response_text = self._get_confirmation_prompt(decision)
            
        elif decision.category == RouteCategory.CONVERSATION:
            response_text = self.conversation_responder.respond(decision)
            
        elif decision.category == RouteCategory.SYSTEM:
            response_text = self._handle_system(decision)
            
        else:  # CLARIFICATION
            self._stats["clarification_requests"] += 1
            response_text = self.clarification_responder.respond(decision)
        
        response = AssistantResponse(
            text=response_text,
            speak=True,
            route_category=decision.category,
            confidence=decision.confidence,
            needs_clarification=decision.category == RouteCategory.CLARIFICATION,
        )
        
        self._speak(response)
        return response
    
    def _handle_confirmation(self, text: str) -> AssistantResponse:
        """Handle confirmation response."""
        text_lower = text.lower().strip()
        
        if text_lower in ["yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "do it", "proceed"]:
            # Execute the pending action
            decision = self._pending_action
            self._pending_action = None
            return self._execute_action(decision)
        
        elif text_lower in ["no", "nope", "cancel", "stop", "don't", "deny", "nevermind"]:
            self._pending_action = None
            response = AssistantResponse(text="Cancelled.", speak=True)
            self._speak(response)
            return response
        
        else:
            # Ask again
            prompt = self._get_confirmation_prompt(self._pending_action)
            response = AssistantResponse(
                text=f"{prompt}\nSay 'yes' to confirm or 'no' to cancel.",
                speak=True,
            )
            self._speak(response)
            return response
    
    def _get_confirmation_prompt(self, decision: RouteDecision) -> str:
        """Get confirmation prompt for an action."""
        intent = decision.intent
        entities = decision.entities
        
        if intent == "open_url":
            site = entities.get("site", entities.get("url", entities.get("domain", "the website")))
            return f"Should I open {site}?"
        
        elif intent == "youtube_search":
            query = entities.get("query", "")
            return f"Should I search YouTube for '{query}'?"
        
        elif intent == "open_app":
            app = entities.get("app", "the application")
            return f"Should I open {app}?"
        
        elif intent == "search_web":
            query = entities.get("query", "")
            return f"Should I search for '{query}'?"
        
        else:
            return f"Should I execute {intent}?"
    
    def _execute_action(self, decision: RouteDecision) -> AssistantResponse:
        """Execute a desktop action."""
        import subprocess
        import webbrowser
        import urllib.parse
        
        intent = decision.intent
        entities = decision.entities
        
        try:
            if intent == "open_url":
                site = entities.get("site", "").lower()
                url = entities.get("url", entities.get("domain", ""))
                
                # Map site names to URLs
                site_urls = {
                    "youtube": "https://youtube.com",
                    "google": "https://google.com",
                    "github": "https://github.com",
                    "gmail": "https://mail.google.com",
                    "spotify": "https://open.spotify.com",
                    "netflix": "https://netflix.com",
                    "twitter": "https://twitter.com",
                    "facebook": "https://facebook.com",
                    "instagram": "https://instagram.com",
                    "linkedin": "https://linkedin.com",
                    "reddit": "https://reddit.com",
                    "stackoverflow": "https://stackoverflow.com",
                    "amazon": "https://amazon.com",
                    "wikipedia": "https://wikipedia.org",
                    "outlook": "https://outlook.com",
                    "calendar": "https://calendar.google.com",
                }
                
                if site in site_urls:
                    url = site_urls[site]
                elif not url.startswith("http"):
                    url = f"https://{url}"
                
                webbrowser.open(url)
                self._stats["actions_executed"] += 1
                
                return AssistantResponse(
                    text=f"Opening {site or url}",
                    speak=False,
                    action_executed=True,
                    action_type="open_url",
                )
            
            elif intent == "youtube_search":
                query = entities.get("query", "")
                url = f"https://youtube.com/results?search_query={urllib.parse.quote(query)}"
                webbrowser.open(url)
                self._stats["actions_executed"] += 1
                
                return AssistantResponse(
                    text=f"Searching YouTube for {query}",
                    speak=False,
                    action_executed=True,
                    action_type="youtube_search",
                )
            
            elif intent == "open_app":
                app = entities.get("app", "").lower()
                app_commands = {
                    "notepad": "notepad.exe",
                    "calculator": "calc.exe",
                    "cmd": "cmd.exe",
                    "terminal": "wt.exe",
                    "powershell": "powershell.exe",
                    "explorer": "explorer.exe",
                    "chrome": "chrome",
                    "firefox": "firefox",
                    "edge": "msedge",
                    "word": "winword",
                    "excel": "excel",
                    "powerpoint": "powerpnt",
                    "outlook": "outlook",
                    "vscode": "code",
                    "vs code": "code",
                    "visual studio": "devenv",
                    "code": "code",
                }
                
                cmd = app_commands.get(app, app)
                subprocess.Popen(cmd, shell=True)
                self._stats["actions_executed"] += 1
                
                return AssistantResponse(
                    text=f"Opening {app}",
                    speak=False,
                    action_executed=True,
                    action_type="open_app",
                )
            
            elif intent == "search_web":
                query = entities.get("query", "")
                url = f"https://google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)
                self._stats["actions_executed"] += 1
                
                return AssistantResponse(
                    text=f"Searching for {query}",
                    speak=False,
                    action_executed=True,
                    action_type="search_web",
                )
            
            else:
                return AssistantResponse(
                    text=f"I don't know how to execute {intent} yet.",
                    speak=True,
                    error="Unknown action",
                )
        
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return AssistantResponse(
                text=f"Failed to execute action: {str(e)}",
                speak=True,
                error=str(e),
            )
    
    def _handle_system(self, decision: RouteDecision) -> str:
        """Handle system commands."""
        intent = decision.intent
        
        if intent == "status":
            return f"Running smoothly. Processed {self._stats['total_requests']} requests. {self._stats['actions_executed']} actions executed."
        
        elif intent == "help":
            return "I can:\n• Open websites and apps (say 'open YouTube')\n• Search the web (say 'search for...')\n• Explain topics (say 'explain binary search')\n• Help with studying (say 'help me study')\n• Answer factual questions"
        
        elif intent in ("confirm_yes", "confirm_no"):
            return "There's nothing to confirm right now."
        
        elif intent == "cancel":
            return "Okay, cancelled."
        
        else:
            return "How can I help?"
    
    def _speak(self, response: AssistantResponse):
        """Speak the response."""
        if self._tts and response.speak and response.text:
            try:
                self._tts.speak(response.text, async_mode=True)
            except Exception as e:
                logger.warning(f"TTS failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get assistant statistics."""
        return {
            **self._stats,
            "pending_action": self._pending_action is not None,
        }
    
    def get_routing_audit(self) -> List[Dict]:
        """Get routing audit log."""
        return self.router.get_audit_log()
    
    def cleanup(self):
        """Cleanup resources."""
        if self._tts:
            try:
                self._tts.stop()
            except:
                pass


# =============================================================================
# FACTORY
# =============================================================================

def create_production_assistant(
    llm_callback: Optional[Callable] = None,
    enable_tts: bool = True,
) -> ProductionAssistant:
    """Create and return a production assistant."""
    return ProductionAssistant(
        llm_callback=llm_callback,
        enable_tts=enable_tts,
    )
