"""
Prompt Templates for Student Tools
===================================

Engineering-focused prompt templates for teaching, not cheating.

DESIGN PHILOSOPHY:
- Every prompt teaches first
- Reasoning comes before answers
- Questions lead to understanding
- No shortcuts to learning
"""

from typing import Dict, List, Optional
from .intelligence import Subject, DifficultyLevel, ExplanationStyle, SafetyMode


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

SYSTEM_PROMPT_BASE = """You are SAARTHI (Study Assistant with Advanced Real-Time Helpful Intelligence), an AI tutor for engineering students.

CORE VALUES:
1. TEACH, don't give answers
2. EXPLAIN the "why", not just the "what"
3. GUIDE students to discover answers
4. ENCOURAGE understanding over memorization
5. NEVER enable academic dishonesty

PERSONALITY:
- Patient and encouraging
- Clear and structured
- Uses analogies and examples
- Asks clarifying questions
- Celebrates understanding, not just correct answers

RESPONSE STYLE:
- Use markdown for structure
- Include examples
- Break complex topics into steps
- Highlight key points
- Suggest related topics to explore
"""

SYSTEM_PROMPT_STRICT = SYSTEM_PROMPT_BASE + """

STRICT MODE ACTIVATED:
- You are helping with exam preparation
- NEVER give direct answers
- Only explain concepts
- Ask the student to attempt first
- Guide with hints, not solutions
"""

SYSTEM_PROMPT_GUIDED = SYSTEM_PROMPT_BASE + """

GUIDED MODE ACTIVATED:
- Ask the student what they think first
- Provide hints, not answers
- Confirm or correct their reasoning
- Build understanding step by step
"""


# =============================================================================
# DSA PROMPTS
# =============================================================================

DSA_PROMPTS = {
    "arrays": """
Explaining Array concepts:

1. What are arrays? → Contiguous memory, fixed size, O(1) access
2. Operations → Access, Insert, Delete, Search
3. Time Complexity → O(1) access, O(n) search, O(n) insert/delete
4. Common Patterns → Two pointers, Sliding window, Prefix sum
5. Practice → Start with easy, focus on edge cases
""",
    
    "linked_lists": """
Explaining Linked List concepts:

1. What are linked lists? → Nodes with data + pointer, dynamic size
2. Types → Singly, Doubly, Circular
3. Operations → Insert O(1), Delete O(1), Search O(n)
4. vs Arrays → Dynamic size, no contiguous memory, no random access
5. Common Problems → Reverse, detect cycle, find middle
""",
    
    "trees": """
Explaining Tree concepts:

1. What are trees? → Hierarchical, root node, parent-child relations
2. Types → Binary, BST, AVL, Red-Black, B-tree
3. Traversals → Inorder, Preorder, Postorder, Level-order
4. BST → Left < Root < Right, O(log n) operations
5. Common Problems → Height, balance, LCA, path sum
""",
    
    "graphs": """
Explaining Graph concepts:

1. What are graphs? → Vertices + Edges, directed/undirected
2. Representations → Adjacency matrix, Adjacency list
3. Traversals → BFS (queue), DFS (stack/recursion)
4. Algorithms → Dijkstra, Bellman-Ford, Floyd-Warshall, Prim, Kruskal
5. Common Problems → Shortest path, cycle detection, topological sort
""",
    
    "dynamic_programming": """
Explaining Dynamic Programming:

1. What is DP? → Optimization technique, overlapping subproblems
2. Identification → Optimal substructure + Overlapping subproblems
3. Approaches → Top-down (memoization), Bottom-up (tabulation)
4. Steps → Define state, recurrence relation, base case, order of computation
5. Classic Problems → Fibonacci, Knapsack, LCS, LIS, Matrix chain
""",
}


# =============================================================================
# OS PROMPTS
# =============================================================================

OS_PROMPTS = {
    "process": """
Explaining Process concepts:

1. What is a Process? → Program in execution, has PCB
2. States → New, Ready, Running, Waiting, Terminated
3. PCB Contents → PID, state, PC, registers, memory info
4. Context Switch → Save state, load new state, overhead
5. Creation → fork() creates child, exec() replaces
""",
    
    "scheduling": """
Explaining CPU Scheduling:

1. Why Scheduling? → Multiprogramming, maximize CPU utilization
2. Criteria → Throughput, turnaround, waiting, response time
3. FCFS → Simple, convoy effect, non-preemptive
4. SJF → Optimal average wait, starvation possible
5. Round Robin → Time quantum, fair, context switch overhead
6. Priority → Can be preemptive/non-preemptive, aging prevents starvation
""",
    
    "memory": """
Explaining Memory Management:

1. Why MM? → Multiprogramming, protection, virtual memory
2. Paging → Fixed-size frames, page table, no external fragmentation
3. Segmentation → Variable-size segments, logical division
4. Virtual Memory → Larger logical space, demand paging
5. Page Replacement → FIFO, LRU, Optimal, Clock
""",
    
    "deadlock": """
Explaining Deadlock:

1. What is Deadlock? → Circular wait, processes blocked forever
2. Conditions → Mutual exclusion, Hold & wait, No preemption, Circular wait
3. Prevention → Break one condition
4. Avoidance → Banker's algorithm, safe state
5. Detection → Resource allocation graph, cycle detection
6. Recovery → Kill process, preempt resources
""",
}


# =============================================================================
# DBMS PROMPTS
# =============================================================================

DBMS_PROMPTS = {
    "normalization": """
Explaining Normalization:

1. Why Normalize? → Reduce redundancy, prevent anomalies
2. 1NF → Atomic values, no repeating groups
3. 2NF → 1NF + No partial dependencies
4. 3NF → 2NF + No transitive dependencies
5. BCNF → Every determinant is a candidate key
6. When to Denormalize? → Performance, read-heavy systems
""",
    
    "transactions": """
Explaining Transactions:

1. What is Transaction? → Logical unit of work, all-or-nothing
2. ACID Properties:
   - Atomicity: Complete or rollback
   - Consistency: Valid state to valid state
   - Isolation: Concurrent transactions independent
   - Durability: Committed changes persist
3. Serializability → Equivalent to serial execution
4. Locking → 2PL, shared/exclusive locks
5. Recovery → Log-based, checkpoints
""",
    
    "sql": """
Explaining SQL:

1. DDL → CREATE, ALTER, DROP (structure)
2. DML → SELECT, INSERT, UPDATE, DELETE (data)
3. DCL → GRANT, REVOKE (permissions)
4. Joins → INNER, LEFT, RIGHT, FULL, CROSS
5. Aggregation → GROUP BY, HAVING, COUNT, SUM, AVG
6. Subqueries → Nested SELECT, IN, EXISTS
""",
}


# =============================================================================
# CN PROMPTS
# =============================================================================

CN_PROMPTS = {
    "osi_model": """
Explaining OSI Model:

7 Layers (top to bottom):
7. Application → HTTP, FTP, SMTP (user interface)
6. Presentation → Encryption, compression (format)
5. Session → Session management (dialog control)
4. Transport → TCP/UDP (end-to-end delivery)
3. Network → IP, routing (logical addressing)
2. Data Link → MAC, framing (physical addressing)
1. Physical → Bits on wire (signals)

Remember: "All People Seem To Need Data Processing"
""",
    
    "tcp_vs_udp": """
Explaining TCP vs UDP:

TCP (Transmission Control Protocol):
- Connection-oriented (3-way handshake)
- Reliable (acknowledgments, retransmission)
- Ordered (sequence numbers)
- Flow control (sliding window)
- Use: HTTP, FTP, Email

UDP (User Datagram Protocol):
- Connectionless
- Unreliable (no guarantees)
- No ordering
- Faster, lower overhead
- Use: DNS, streaming, gaming
""",
    
    "ip_addressing": """
Explaining IP Addressing:

IPv4 → 32 bits, 4 octets (e.g., 192.168.1.1)
Classes:
- A: 1-126 (large networks)
- B: 128-191 (medium networks)
- C: 192-223 (small networks)
- D: 224-239 (multicast)
- E: 240-255 (reserved)

Subnetting:
- Divide network into smaller parts
- Subnet mask determines network/host bits
- CIDR notation: /24 = 255.255.255.0
""",
}


# =============================================================================
# PROMPT BUILDER
# =============================================================================

class PromptBuilder:
    """Builds context-aware prompts for student tools."""
    
    SUBJECT_PROMPTS = {
        Subject.DSA: DSA_PROMPTS,
        Subject.OS: OS_PROMPTS,
        Subject.DBMS: DBMS_PROMPTS,
        Subject.CN: CN_PROMPTS,
    }
    
    @classmethod
    def build_system_prompt(cls, mode: SafetyMode) -> str:
        """Get system prompt for safety mode."""
        if mode == SafetyMode.STRICT:
            return SYSTEM_PROMPT_STRICT
        elif mode == SafetyMode.GUIDED:
            return SYSTEM_PROMPT_GUIDED
        return SYSTEM_PROMPT_BASE
    
    @classmethod
    def get_topic_context(cls, subject: Subject, topic: str) -> str:
        """Get topic-specific context."""
        prompts = cls.SUBJECT_PROMPTS.get(subject, {})
        
        # Try exact match
        if topic.lower() in prompts:
            return prompts[topic.lower()]
        
        # Try partial match
        for key, value in prompts.items():
            if topic.lower() in key or key in topic.lower():
                return value
        
        return ""
    
    @classmethod
    def build_clarifying_questions(cls, query: str, subject: Subject) -> List[str]:
        """Generate clarifying questions for ambiguous queries."""
        
        questions = [
            "What specific aspect would you like me to explain?",
            f"Are you studying this for an exam or to understand the concept?",
            "What do you already know about this topic?",
            "Is there a particular part that's confusing?",
        ]
        
        # Subject-specific questions
        if subject == Subject.DSA:
            questions.append("Do you need help with the algorithm logic or the code implementation?")
            questions.append("Should I explain the time/space complexity?")
        
        elif subject == Subject.OS:
            questions.append("Are you looking for the theoretical concept or a practical example?")
        
        elif subject == Subject.DBMS:
            questions.append("Would you like to see SQL examples or understand the theory?")
        
        elif subject == Subject.CN:
            questions.append("Do you need the protocol details or just the overview?")
        
        return questions
    
    @classmethod
    def build_explanation_prompt(
        cls,
        query: str,
        subject: Subject,
        style: ExplanationStyle,
        level: DifficultyLevel,
        mode: SafetyMode,
    ) -> str:
        """Build a complete explanation prompt."""
        
        system = cls.build_system_prompt(mode)
        context = cls.get_topic_context(subject, query)
        
        style_instructions = {
            ExplanationStyle.SIMPLE: "Use simple words, avoid jargon, explain like I'm a beginner.",
            ExplanationStyle.TECHNICAL: "Use proper technical terminology and be precise.",
            ExplanationStyle.VISUAL: "Describe diagrams, use ASCII art if helpful, be visual.",
            ExplanationStyle.STEP_BY_STEP: "Number each step, be methodical and clear.",
            ExplanationStyle.ANALOGY: "Use real-world analogies and comparisons.",
        }
        
        level_instructions = {
            DifficultyLevel.BEGINNER: "Assume no prior knowledge, start from basics.",
            DifficultyLevel.INTERMEDIATE: "Assume basic knowledge, focus on core concepts.",
            DifficultyLevel.ADVANCED: "Assume strong foundation, dive into details.",
            DifficultyLevel.EXAM_LEVEL: "Focus on exam-relevant points and common questions.",
        }
        
        prompt = f"""{system}

TOPIC CONTEXT:
{context}

STUDENT'S QUESTION:
{query}

STYLE: {style_instructions[style]}
LEVEL: {level_instructions[level]}

Remember:
1. Explain BEFORE answering
2. Break into steps
3. Use examples
4. Highlight key points
5. Suggest what to study next
"""
        
        return prompt
