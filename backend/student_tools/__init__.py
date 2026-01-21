"""
Student Tools Package
=====================

Engineering student-focused intelligence for SAARTHI.

PRINCIPLE: Teach, Don't Cheat

TOOLS:
- AssignmentExplainer: Step-by-step problem breakdown
- QuizHelper: Reasoning-first quiz assistance
- ConceptBreakdown: Topic explanations
- StudyPlanner: Personalized study schedules
- FileQA: Document-based Q&A

SUBJECTS:
- DSA (Data Structures & Algorithms)
- OS (Operating Systems)
- DBMS (Database Management)
- CN (Computer Networks)
- And more...

USAGE:
```python
from student_tools import QuizHelper, SafetyMode

# Create helper in guided mode
helper = QuizHelper(llm_callback=my_llm, safety_mode=SafetyMode.GUIDED)

# Get help with a question
result = await helper.help_with_question(question)
```
"""

from .intelligence import (
    # Enums
    Subject,
    DifficultyLevel,
    ExplanationStyle,
    SafetyMode,
    
    # Data classes
    StudentContext,
    ExplanationRequest,
    QuizQuestion,
    StudyPlan,
    
    # Tools
    AssignmentExplainer,
    QuizHelper,
    ConceptBreakdown,
    StudyPlanner,
    FileQA,
    
    # Safety
    SafetyBoundaries,
)

from .prompts import (
    PromptBuilder,
    SYSTEM_PROMPT_BASE,
    SYSTEM_PROMPT_STRICT,
    SYSTEM_PROMPT_GUIDED,
    DSA_PROMPTS,
    OS_PROMPTS,
    DBMS_PROMPTS,
    CN_PROMPTS,
)

__all__ = [
    # Enums
    "Subject",
    "DifficultyLevel",
    "ExplanationStyle",
    "SafetyMode",
    
    # Data classes
    "StudentContext",
    "ExplanationRequest",
    "QuizQuestion",
    "StudyPlan",
    
    # Tools
    "AssignmentExplainer",
    "QuizHelper",
    "ConceptBreakdown",
    "StudyPlanner",
    "FileQA",
    
    # Safety
    "SafetyBoundaries",
    
    # Prompts
    "PromptBuilder",
    "SYSTEM_PROMPT_BASE",
    "SYSTEM_PROMPT_STRICT",
    "SYSTEM_PROMPT_GUIDED",
    "DSA_PROMPTS",
    "OS_PROMPTS",
    "DBMS_PROMPTS",
    "CN_PROMPTS",
]


# =============================================================================
# QUICK USAGE EXAMPLES
# =============================================================================

"""
EXAMPLE 1: Explain an assignment

```python
from student_tools import AssignmentExplainer, ExplanationRequest, Subject

explainer = AssignmentExplainer(llm_callback=my_llm)

request = ExplanationRequest(
    query="Implement a function to find the longest common subsequence of two strings",
    subject=Subject.DSA,
    style=ExplanationStyle.STEP_BY_STEP,
    include_code=True,
)

result = await explainer.explain(request)
print(result["explanation"])
```


EXAMPLE 2: Quiz help in guided mode

```python
from student_tools import QuizHelper, QuizQuestion, SafetyMode

helper = QuizHelper(llm_callback=my_llm, safety_mode=SafetyMode.GUIDED)

question = QuizQuestion(
    question="Which scheduling algorithm can cause starvation?",
    options=["FCFS", "SJF", "Round Robin", "All of the above"],
    subject=Subject.OS,
)

result = await helper.help_with_question(question)
# Will give hints, not direct answer
```


EXAMPLE 3: Concept breakdown

```python
from student_tools import ConceptBreakdown, Subject

breakdown = ConceptBreakdown(llm_callback=my_llm)

result = await breakdown.explain_concept(
    concept="Deadlock",
    subject=Subject.OS,
    style=ExplanationStyle.VISUAL,
)
```


EXAMPLE 4: Study plan

```python
from student_tools import StudyPlanner, Subject

planner = StudyPlanner(llm_callback=my_llm)

result = await planner.create_plan(
    goal="Prepare for GATE CS",
    subjects=[Subject.DSA, Subject.OS, Subject.DBMS, Subject.CN],
    duration_days=90,
    daily_hours=4,
)
```


EXAMPLE 5: Safety check

```python
from student_tools import SafetyBoundaries

check = SafetyBoundaries.check_request("just give me the answer")
if check["is_suspicious"]:
    print(check["suggested_response"])
    # "I'd love to help you understand this! ..."
```
"""
