"""
Student Intelligence Tools
===========================

Engineering student-focused tools for SAARTHI.

TARGET USERS: Engineering students (CS, IT, ECE, etc.)

CORE PRINCIPLE: TEACH, DON'T CHEAT
- Explain concepts before giving answers
- Show reasoning, not just solutions
- Ask clarifying questions
- Promote understanding over copying

SUPPORTED SUBJECTS:
- DSA (Data Structures & Algorithms)
- OS (Operating Systems)
- DBMS (Database Management Systems)
- CN (Computer Networks)
- TOC (Theory of Computation)
- SE (Software Engineering)
- Math (Calculus, Linear Algebra, Discrete Math)

TOOLS PROVIDED:
1. AssignmentExplainer - Step-by-step breakdown
2. QuizHelper - Reasoning-first answers
3. ConceptBreakdown - Topic explanation
4. StudyPlanner - Schedule creation
5. FileQA - Document-based Q&A
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta


# =============================================================================
# ENUMS & TYPES
# =============================================================================

class Subject(Enum):
    """Supported engineering subjects."""
    DSA = "data_structures_algorithms"
    OS = "operating_systems"
    DBMS = "database_management"
    CN = "computer_networks"
    TOC = "theory_of_computation"
    SE = "software_engineering"
    MATH_CALCULUS = "calculus"
    MATH_LINEAR = "linear_algebra"
    MATH_DISCRETE = "discrete_math"
    PYTHON = "python_programming"
    JAVA = "java_programming"
    C = "c_programming"
    CPP = "cpp_programming"
    WEB = "web_development"
    ML = "machine_learning"
    GENERAL = "general"


class DifficultyLevel(Enum):
    """Question/concept difficulty."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXAM_LEVEL = "exam_level"


class ExplanationStyle(Enum):
    """How to explain things."""
    SIMPLE = "simple"           # ELI5 style
    TECHNICAL = "technical"     # Proper terminology
    VISUAL = "visual"           # With diagrams/examples
    STEP_BY_STEP = "step_by_step"  # Numbered steps
    ANALOGY = "analogy"         # Real-world comparisons


class SafetyMode(Enum):
    """Safety/ethics mode for answers."""
    LEARNING = "learning"       # Full explanation, teach concepts
    GUIDED = "guided"           # Hints only, no direct answers
    EXAM_PREP = "exam_prep"     # Practice mode, reveal after attempt
    STRICT = "strict"           # Never give direct answers


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StudentContext:
    """Context about the student for personalized help."""
    level: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    primary_subjects: List[Subject] = field(default_factory=list)
    preferred_style: ExplanationStyle = ExplanationStyle.STEP_BY_STEP
    safety_mode: SafetyMode = SafetyMode.LEARNING
    
    # Session tracking
    topics_covered: List[str] = field(default_factory=list)
    questions_asked: int = 0
    concepts_explained: int = 0


@dataclass
class ExplanationRequest:
    """Request for concept/assignment explanation."""
    query: str
    subject: Subject = Subject.GENERAL
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    style: ExplanationStyle = ExplanationStyle.STEP_BY_STEP
    include_examples: bool = True
    include_code: bool = True
    include_diagram: bool = False


@dataclass
class QuizQuestion:
    """A quiz/MCQ question."""
    question: str
    options: List[str] = field(default_factory=list)  # For MCQ
    subject: Subject = Subject.GENERAL
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    
    # Student's attempt (if any)
    student_answer: Optional[str] = None
    student_reasoning: Optional[str] = None


@dataclass
class StudyPlan:
    """A generated study plan."""
    goal: str
    subjects: List[Subject]
    duration_days: int
    daily_hours: float
    
    # Generated plan
    schedule: List[Dict[str, Any]] = field(default_factory=list)
    milestones: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)


# =============================================================================
# TOOL: ASSIGNMENT EXPLAINER
# =============================================================================

class AssignmentExplainer:
    """
    Explains assignments step-by-step.
    
    APPROACH:
    1. Understand the problem
    2. Break into sub-problems
    3. Explain each step
    4. Show implementation hints
    5. Provide testing strategy
    
    NEVER:
    - Give complete copy-paste solutions
    - Skip explanation
    - Encourage plagiarism
    """
    
    EXPLANATION_TEMPLATE = """
## Understanding the Problem

{problem_analysis}

## Breaking It Down

{breakdown}

## Step-by-Step Approach

{steps}

## Key Concepts Needed

{concepts}

## Implementation Hints

{hints}

## How to Test Your Solution

{testing}

## Common Mistakes to Avoid

{mistakes}
"""
    
    def __init__(self, llm_callback=None):
        self._llm = llm_callback
    
    def create_prompt(self, request: ExplanationRequest) -> str:
        """Create LLM prompt for assignment explanation."""
        
        return f"""You are SAARTHI, a teaching assistant for engineering students.

TASK: Explain this assignment/problem step-by-step.

PROBLEM:
{request.query}

SUBJECT: {request.subject.value}
DIFFICULTY: {request.difficulty.value}
STYLE: {request.style.value}

RULES:
1. EXPLAIN the problem first - what is being asked?
2. BREAK DOWN into smaller sub-problems
3. EXPLAIN each step with reasoning
4. Give HINTS, not complete solutions
5. Use {request.style.value} explanation style
6. {"Include code examples" if request.include_code else "No code, explain conceptually"}
7. {"Include diagram/visualization" if request.include_diagram else ""}

STRUCTURE YOUR RESPONSE:
1. Problem Analysis (what are we solving?)
2. Prerequisites (what concepts are needed?)
3. Approach (step-by-step breakdown)
4. Implementation Hints (how to code it, without full solution)
5. Testing Strategy (how to verify correctness)
6. Common Pitfalls (mistakes to avoid)

IMPORTANT:
- Teach the student, don't do homework for them
- If problem is ambiguous, list clarifying questions
- Explain WHY each step works, not just WHAT to do
"""
    
    async def explain(self, request: ExplanationRequest) -> Dict[str, Any]:
        """Generate explanation for assignment."""
        
        prompt = self.create_prompt(request)
        
        if self._llm:
            explanation = await self._llm(prompt)
            return {
                "success": True,
                "explanation": explanation,
                "subject": request.subject.value,
                "style": request.style.value,
            }
        
        return {
            "success": False,
            "error": "LLM not configured",
            "prompt": prompt,  # Return prompt for manual use
        }


# =============================================================================
# TOOL: QUIZ HELPER
# =============================================================================

class QuizHelper:
    """
    Helps with quiz questions WITH reasoning.
    
    APPROACH:
    1. Understand the question
    2. Analyze each option (for MCQ)
    3. Explain reasoning
    4. Reveal answer LAST
    
    MODES:
    - LEARNING: Full explanation + answer
    - GUIDED: Hints only, student tries first
    - EXAM_PREP: Student attempts, then reveal
    - STRICT: Never reveal, only clarify concepts
    """
    
    def __init__(self, llm_callback=None, safety_mode: SafetyMode = SafetyMode.LEARNING):
        self._llm = llm_callback
        self.safety_mode = safety_mode
    
    def create_prompt(self, question: QuizQuestion) -> str:
        """Create LLM prompt for quiz help."""
        
        options_text = ""
        if question.options:
            options_text = "\n".join(
                f"  {chr(65+i)}. {opt}" 
                for i, opt in enumerate(question.options)
            )
        
        mode_instructions = self._get_mode_instructions()
        
        return f"""You are SAARTHI, helping an engineering student understand a quiz question.

QUESTION:
{question.question}

{"OPTIONS:" + chr(10) + options_text if options_text else ""}

SUBJECT: {question.subject.value}
DIFFICULTY: {question.difficulty.value}

{mode_instructions}

STRUCTURE YOUR RESPONSE:

1. UNDERSTANDING THE QUESTION
   - What concept is being tested?
   - What are the key terms?

2. CONCEPT REVIEW
   - Brief explanation of the relevant concept
   - Key formulas or rules (if applicable)

3. ANALYZING OPTIONS (for MCQ)
   - Go through each option
   - Explain why it's correct or incorrect
   - Use process of elimination

4. REASONING
   - Step-by-step logical reasoning
   - Connect to core concepts

5. ANSWER (if allowed by mode)
   - State the correct answer
   - Explain why it's correct

6. LEARNING POINT
   - What should the student remember?
   - Related topics to study

IMPORTANT:
- ALWAYS explain reasoning BEFORE answer
- Don't just say "The answer is B" - explain WHY
- If question is ambiguous, ask for clarification
- Connect to broader concepts for learning
"""
    
    def _get_mode_instructions(self) -> str:
        """Get mode-specific instructions."""
        
        if self.safety_mode == SafetyMode.LEARNING:
            return """MODE: LEARNING
- Explain the concept fully
- Analyze all options
- Reveal the answer at the end
- Focus on teaching"""
        
        elif self.safety_mode == SafetyMode.GUIDED:
            return """MODE: GUIDED
- Give hints, not answers
- Ask the student what they think
- Guide them to discover the answer
- Only confirm if they're right"""
        
        elif self.safety_mode == SafetyMode.EXAM_PREP:
            return """MODE: EXAM PREP
- Ask the student to attempt first
- Don't reveal answer immediately
- Give hints if they're stuck
- Explain after they attempt"""
        
        else:  # STRICT
            return """MODE: STRICT
- NEVER reveal the answer
- Only explain the concept
- Help them understand, not solve
- They must find the answer themselves"""
    
    async def help_with_question(self, question: QuizQuestion) -> Dict[str, Any]:
        """Help with a quiz question."""
        
        prompt = self.create_prompt(question)
        
        # If student already attempted, acknowledge that
        if question.student_answer:
            prompt += f"\n\nSTUDENT'S ATTEMPT: {question.student_answer}"
            if question.student_reasoning:
                prompt += f"\nSTUDENT'S REASONING: {question.student_reasoning}"
            prompt += "\n\nEvaluate their attempt and provide feedback."
        
        if self._llm:
            response = await self._llm(prompt)
            return {
                "success": True,
                "response": response,
                "mode": self.safety_mode.value,
            }
        
        return {
            "success": False,
            "error": "LLM not configured",
            "prompt": prompt,
        }


# =============================================================================
# TOOL: CONCEPT BREAKDOWN
# =============================================================================

class ConceptBreakdown:
    """
    Breaks down complex engineering concepts.
    
    SUBJECTS:
    - DSA: Arrays, Trees, Graphs, Sorting, DP, etc.
    - OS: Processes, Memory, Scheduling, etc.
    - DBMS: SQL, Normalization, Transactions, etc.
    - CN: OSI, TCP/IP, Routing, etc.
    """
    
    # Concept maps for quick reference
    CONCEPT_MAPS = {
        Subject.DSA: {
            "arrays": ["1D arrays", "2D arrays", "dynamic arrays", "operations", "time complexity"],
            "linked_lists": ["singly", "doubly", "circular", "operations", "vs arrays"],
            "trees": ["binary tree", "BST", "AVL", "traversals", "applications"],
            "graphs": ["representations", "BFS", "DFS", "shortest path", "MST"],
            "sorting": ["bubble", "selection", "insertion", "merge", "quick", "heap", "complexity"],
            "dynamic_programming": ["memoization", "tabulation", "optimal substructure", "overlapping subproblems"],
            "hashing": ["hash functions", "collision handling", "applications"],
        },
        Subject.OS: {
            "process": ["states", "PCB", "context switch", "creation", "termination"],
            "scheduling": ["FCFS", "SJF", "priority", "round robin", "multilevel"],
            "memory": ["paging", "segmentation", "virtual memory", "page replacement"],
            "synchronization": ["critical section", "mutex", "semaphore", "deadlock"],
            "file_system": ["allocation", "directory structure", "free space management"],
        },
        Subject.DBMS: {
            "sql": ["DDL", "DML", "DCL", "joins", "subqueries", "aggregation"],
            "normalization": ["1NF", "2NF", "3NF", "BCNF", "functional dependencies"],
            "transactions": ["ACID", "serializability", "locking", "recovery"],
            "indexing": ["B-tree", "B+ tree", "hashing", "query optimization"],
        },
        Subject.CN: {
            "osi_model": ["layers", "functions", "protocols", "encapsulation"],
            "tcp_ip": ["layers", "IP addressing", "subnetting", "routing"],
            "transport": ["TCP", "UDP", "flow control", "congestion control"],
            "application": ["HTTP", "DNS", "SMTP", "FTP"],
        },
    }
    
    def __init__(self, llm_callback=None):
        self._llm = llm_callback
    
    def create_prompt(
        self, 
        concept: str, 
        subject: Subject,
        style: ExplanationStyle = ExplanationStyle.STEP_BY_STEP,
        level: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
    ) -> str:
        """Create prompt for concept breakdown."""
        
        # Find related concepts
        related = []
        if subject in self.CONCEPT_MAPS:
            for topic, subtopics in self.CONCEPT_MAPS[subject].items():
                if concept.lower() in topic or any(concept.lower() in s for s in subtopics):
                    related = subtopics
                    break
        
        related_text = f"Related concepts: {', '.join(related)}" if related else ""
        
        return f"""You are SAARTHI, explaining an engineering concept to a student.

CONCEPT: {concept}
SUBJECT: {subject.value}
LEVEL: {level.value}
STYLE: {style.value}

{related_text}

EXPLAIN THE CONCEPT USING THIS STRUCTURE:

## What is {concept}?
- Simple definition
- Why it matters
- Real-world analogy (if applicable)

## Core Principles
- Key ideas (3-5 points)
- Important properties

## How It Works
- Step-by-step explanation
- {"Visual/diagram description" if style == ExplanationStyle.VISUAL else ""}

## Example
- Concrete example with walkthrough
- {"Code implementation" if subject in [Subject.DSA, Subject.PYTHON, Subject.JAVA] else "Practical scenario"}

## Common Misconceptions
- What students often get wrong
- How to avoid these mistakes

## Key Points to Remember
- Summary (5-7 bullet points)
- Exam-relevant facts

## Related Topics
- What to study next
- Prerequisites to review

RULES:
- Use {style.value} style
- Target {level.value} level understanding
- Include examples and analogies
- Be concise but thorough
- Highlight exam-important points
"""
    
    async def explain_concept(
        self,
        concept: str,
        subject: Subject,
        style: ExplanationStyle = ExplanationStyle.STEP_BY_STEP,
        level: DifficultyLevel = DifficultyLevel.INTERMEDIATE,
    ) -> Dict[str, Any]:
        """Explain a concept."""
        
        prompt = self.create_prompt(concept, subject, style, level)
        
        if self._llm:
            explanation = await self._llm(prompt)
            return {
                "success": True,
                "concept": concept,
                "subject": subject.value,
                "explanation": explanation,
            }
        
        return {
            "success": False,
            "error": "LLM not configured",
            "prompt": prompt,
        }
    
    def get_concept_map(self, subject: Subject) -> Dict[str, List[str]]:
        """Get the concept map for a subject."""
        return self.CONCEPT_MAPS.get(subject, {})


# =============================================================================
# TOOL: STUDY PLANNER
# =============================================================================

class StudyPlanner:
    """
    Creates personalized study plans.
    
    FEATURES:
    - Time-based scheduling
    - Topic prioritization
    - Break recommendations
    - Milestone tracking
    """
    
    # Standard study patterns
    STUDY_PATTERNS = {
        "pomodoro": {"study": 25, "break": 5, "long_break": 15, "sessions_before_long": 4},
        "deep_work": {"study": 90, "break": 20, "long_break": 30, "sessions_before_long": 2},
        "spaced": {"study": 45, "break": 10, "long_break": 20, "sessions_before_long": 3},
    }
    
    def __init__(self, llm_callback=None):
        self._llm = llm_callback
    
    def create_prompt(
        self,
        goal: str,
        subjects: List[Subject],
        duration_days: int,
        daily_hours: float,
        exam_date: Optional[str] = None,
    ) -> str:
        """Create prompt for study plan generation."""
        
        subjects_text = ", ".join(s.value for s in subjects)
        
        return f"""You are SAARTHI, creating a study plan for an engineering student.

GOAL: {goal}
SUBJECTS: {subjects_text}
DURATION: {duration_days} days
DAILY STUDY TIME: {daily_hours} hours
{"EXAM DATE: " + exam_date if exam_date else ""}

CREATE A STUDY PLAN WITH:

## Overview
- High-level strategy
- Key milestones

## Daily Schedule
For each day, specify:
- Topics to cover
- Estimated time for each topic
- Type of study (reading, practice, revision)

## Weekly Goals
- What should be completed each week
- Self-assessment checkpoints

## Resource Recommendations
- Textbooks/chapters
- Online resources (free)
- Practice problem sources

## Study Tips
- Subject-specific strategies
- How to handle difficult topics
- Revision techniques

## Break Schedule
- When to take breaks
- Activities for mental refresh

RULES:
- Be realistic about time
- Prioritize high-weightage topics
- Include revision time
- Build in buffer for difficult topics
- Use spaced repetition principles

FORMAT:
Output as a structured plan that's easy to follow day-by-day.
"""
    
    async def create_plan(
        self,
        goal: str,
        subjects: List[Subject],
        duration_days: int,
        daily_hours: float,
        exam_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a study plan."""
        
        prompt = self.create_prompt(goal, subjects, duration_days, daily_hours, exam_date)
        
        if self._llm:
            plan = await self._llm(prompt)
            return {
                "success": True,
                "goal": goal,
                "duration": duration_days,
                "plan": plan,
            }
        
        return {
            "success": False,
            "error": "LLM not configured",
            "prompt": prompt,
        }
    
    def get_quick_schedule(
        self,
        subjects: List[Subject],
        hours: float,
        pattern: str = "pomodoro",
    ) -> List[Dict[str, Any]]:
        """Generate a quick daily schedule."""
        
        config = self.STUDY_PATTERNS.get(pattern, self.STUDY_PATTERNS["pomodoro"])
        
        total_minutes = int(hours * 60)
        study_time = config["study"]
        break_time = config["break"]
        cycle_time = study_time + break_time
        
        sessions = total_minutes // cycle_time
        
        schedule = []
        current_time = 0
        
        for i in range(sessions):
            subject = subjects[i % len(subjects)]
            
            schedule.append({
                "session": i + 1,
                "subject": subject.value,
                "duration_min": study_time,
                "type": "study",
                "start_offset_min": current_time,
            })
            current_time += study_time
            
            # Add break
            is_long_break = (i + 1) % config["sessions_before_long"] == 0
            break_duration = config["long_break"] if is_long_break else break_time
            
            schedule.append({
                "session": i + 1,
                "type": "break",
                "duration_min": break_duration,
                "start_offset_min": current_time,
            })
            current_time += break_duration
        
        return schedule


# =============================================================================
# TOOL: FILE-BASED Q&A
# =============================================================================

class FileQA:
    """
    Answer questions based on uploaded files.
    
    SUPPORTED:
    - PDF (notes, textbooks)
    - Text files (code, notes)
    - Images (diagrams, handwritten - OCR)
    
    APPROACH:
    1. Extract text from file
    2. Understand the context
    3. Answer based on file content
    4. Explain reasoning
    """
    
    def __init__(self, llm_callback=None):
        self._llm = llm_callback
    
    def create_prompt(
        self,
        question: str,
        file_content: str,
        file_name: str,
        subject: Subject = Subject.GENERAL,
    ) -> str:
        """Create prompt for file-based Q&A."""
        
        # Truncate content if too long
        max_content = 8000  # Characters
        if len(file_content) > max_content:
            file_content = file_content[:max_content] + "\n\n[Content truncated...]"
        
        return f"""You are SAARTHI, answering a question based on a document.

DOCUMENT: {file_name}
SUBJECT: {subject.value}

--- DOCUMENT CONTENT ---
{file_content}
--- END DOCUMENT ---

QUESTION: {question}

ANSWER THE QUESTION BY:

1. LOCATING RELEVANT INFORMATION
   - Quote or reference specific parts of the document
   - If information is not in the document, say so

2. EXPLAINING THE ANSWER
   - Use the document as the source
   - Add context if helpful

3. PROVIDING THE ANSWER
   - Clear, direct answer
   - With page/section reference if available

RULES:
- Base your answer on the document content
- If the document doesn't contain the answer, say so clearly
- Explain any complex concepts mentioned
- Quote relevant passages when helpful
"""
    
    async def answer_from_file(
        self,
        question: str,
        file_path: str,
        subject: Subject = Subject.GENERAL,
    ) -> Dict[str, Any]:
        """Answer a question based on file content."""
        
        from pathlib import Path
        
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }
        
        # Read file content
        try:
            content = self._read_file(path)
        except Exception as e:
            return {
                "success": False,
                "error": f"Could not read file: {e}",
            }
        
        prompt = self.create_prompt(question, content, path.name, subject)
        
        if self._llm:
            answer = await self._llm(prompt)
            return {
                "success": True,
                "question": question,
                "file": path.name,
                "answer": answer,
            }
        
        return {
            "success": False,
            "error": "LLM not configured",
            "prompt": prompt,
        }
    
    def _read_file(self, path) -> str:
        """Read file content based on type."""
        
        suffix = path.suffix.lower()
        
        if suffix == ".pdf":
            return self._read_pdf(path)
        elif suffix in [".txt", ".md", ".py", ".java", ".c", ".cpp", ".js"]:
            return path.read_text(encoding="utf-8", errors="ignore")
        else:
            return path.read_text(encoding="utf-8", errors="ignore")
    
    def _read_pdf(self, path) -> str:
        """Extract text from PDF."""
        try:
            import PyPDF2
            
            text = []
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text() or "")
            
            return "\n".join(text)
            
        except ImportError:
            return "[PDF reading requires PyPDF2: pip install PyPDF2]"
        except Exception as e:
            return f"[Error reading PDF: {e}]"


# =============================================================================
# SAFETY BOUNDARIES
# =============================================================================

class SafetyBoundaries:
    """
    Safety rules for student tools.
    
    PRINCIPLES:
    1. Teach, don't do homework
    2. Explain reasoning always
    3. No direct exam answers
    4. Encourage understanding
    5. Flag potential cheating
    """
    
    # Phrases that suggest cheating attempt
    CHEATING_INDICATORS = [
        "just give me the answer",
        "don't explain",
        "no explanation needed",
        "just the solution",
        "copy paste",
        "quick answer",
        "exam is in 5 minutes",
        "don't ask questions",
        "just tell me",
    ]
    
    # Allowed vs restricted behaviors
    ALLOWED = [
        "explain_concept",
        "break_down_problem",
        "provide_hints",
        "show_examples",
        "clarify_doubts",
        "review_student_work",
        "suggest_resources",
        "create_practice_problems",
    ]
    
    RESTRICTED = [
        "complete_homework",
        "write_assignment",
        "give_exam_answers",
        "plagiarize_content",
        "bypass_learning",
    ]
    
    @classmethod
    def check_request(cls, query: str) -> Dict[str, Any]:
        """Check if request might be a cheating attempt."""
        
        query_lower = query.lower()
        
        # Check for cheating indicators
        detected = []
        for indicator in cls.CHEATING_INDICATORS:
            if indicator in query_lower:
                detected.append(indicator)
        
        if detected:
            return {
                "is_suspicious": True,
                "indicators": detected,
                "recommendation": "Switch to GUIDED mode and ask clarifying questions",
                "suggested_response": (
                    "I'd love to help you understand this! "
                    "Could you tell me what part is confusing? "
                    "I'll explain the concept so you can solve it yourself."
                ),
            }
        
        return {
            "is_suspicious": False,
            "indicators": [],
            "recommendation": "Proceed with explanation",
        }
    
    @classmethod
    def get_mode_for_context(cls, query: str, time_of_day: int = 12) -> SafetyMode:
        """Suggest safety mode based on context."""
        
        query_lower = query.lower()
        
        # Late night + urgent = likely exam cheating
        if time_of_day >= 22 or time_of_day <= 5:
            if any(w in query_lower for w in ["urgent", "quick", "exam", "test", "hurry"]):
                return SafetyMode.STRICT
        
        # Exam-related keywords
        if any(w in query_lower for w in ["exam", "test", "quiz"]):
            return SafetyMode.GUIDED
        
        # Practice/learning keywords
        if any(w in query_lower for w in ["explain", "understand", "learn", "practice"]):
            return SafetyMode.LEARNING
        
        return SafetyMode.LEARNING
