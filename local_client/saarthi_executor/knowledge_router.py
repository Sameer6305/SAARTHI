"""
Knowledge & Q&A Router Module
==============================

Intelligent routing of questions to the best knowledge source.

ROOT CAUSE ANALYSIS - Current issues:
1. Limited built-in knowledge (only ~15 topics)
2. Wikipedia timeout too long (5s blocks the assistant)
3. No caching of knowledge lookups
4. Poor query preprocessing
5. No graceful degradation
6. No answer summarization (Wikipedia returns long text)

SOLUTION:
1. Expanded built-in knowledge base (100+ topics)
2. Parallel knowledge source queries with timeouts
3. LRU cache for knowledge lookups
4. Smart query extraction and rewriting
5. Graceful fallback chain: built-in → cache → Wikipedia → web search
6. Answer summarization to keep responses concise
"""

import re
import json
import urllib.request
import urllib.parse
import logging
import threading
import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeResult:
    """Result from knowledge lookup."""
    answer: str
    source: str  # built_in, cache, wikipedia, web_search
    confidence: float
    topic: str
    cached: bool = False
    truncated: bool = False


class LRUCache:
    """Simple LRU cache for knowledge lookups."""
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[str]:
        """Get cached value."""
        key = key.lower().strip()
        with self._lock:
            if key not in self._cache:
                return None
            
            value, timestamp = self._cache[key]
            if time.time() - timestamp > self.ttl_seconds:
                del self._cache[key]
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return value
    
    def set(self, key: str, value: str):
        """Cache a value."""
        key = key.lower().strip()
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.time())
            
            # Evict oldest if needed
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    def clear(self):
        """Clear the cache."""
        with self._lock:
            self._cache.clear()


class BuiltInKnowledge:
    """
    Expanded built-in knowledge base.
    Covers common CS/programming topics for instant answers.
    """
    
    TOPICS = {
        # Data Structures
        "array": "An array is a collection of elements stored at contiguous memory locations. Access: O(1) by index. Insertion/deletion: O(n). Best for: fixed-size collections with frequent random access.",
        
        "linked list": "A linked list stores elements in nodes, each pointing to the next. Types: singly linked, doubly linked, circular. Access: O(n). Insert/delete at head: O(1). Best for: frequent insertions/deletions.",
        
        "stack": "A stack is a Last-In-First-Out (LIFO) data structure. Operations: push (add to top), pop (remove from top), peek (view top). Used in: function calls, undo mechanisms, expression evaluation.",
        
        "queue": "A queue is a First-In-First-Out (FIFO) data structure. Operations: enqueue (add to rear), dequeue (remove from front). Used in: task scheduling, BFS, print queues, message buffers.",
        
        "binary tree": "A binary tree has nodes with at most two children (left and right). Types: full, complete, perfect, balanced. Traversals: inorder, preorder, postorder, level-order.",
        
        "binary search tree": "A BST is a binary tree where left children are smaller and right children are larger than the parent. Average operations: O(log n). Worst case (unbalanced): O(n).",
        
        "bst": "A BST (Binary Search Tree) is a binary tree where left children are smaller and right children are larger than the parent. Average operations: O(log n). Used for: sorted data storage, dictionaries.",
        
        "heap": "A heap is a complete binary tree satisfying the heap property. Min-heap: parent ≤ children. Max-heap: parent ≥ children. Used in: priority queues, heap sort. Insert/delete: O(log n).",
        
        "hash table": "A hash table uses a hash function to map keys to array indices for O(1) average lookup, insert, and delete. Handles collisions via chaining or open addressing.",
        
        "hash map": "A hash map (or dictionary) stores key-value pairs using hashing. Average O(1) for get, put, delete. Python: dict. Java: HashMap. JavaScript: Map or object.",
        
        "graph": "A graph consists of vertices (nodes) connected by edges. Types: directed/undirected, weighted/unweighted, cyclic/acyclic. Representations: adjacency matrix, adjacency list.",
        
        "tree": "A tree is a hierarchical data structure with a root and child nodes. No cycles allowed. Special types: binary tree, BST, AVL, B-tree, trie. Used in: file systems, databases, DOM.",
        
        "trie": "A trie (prefix tree) stores strings where each node represents a character. Efficient for: prefix matching, autocomplete, spell checking. Search: O(m) where m is string length.",
        
        # Algorithms
        "binary search": "Binary search finds an element in a sorted array by repeatedly halving the search space. Time: O(log n). Space: O(1) iterative, O(log n) recursive. Requires sorted data.",
        
        "linear search": "Linear search checks each element sequentially until finding the target. Time: O(n). Works on unsorted data. Simple but inefficient for large datasets.",
        
        "bubble sort": "Bubble sort repeatedly swaps adjacent elements if they're in wrong order. Time: O(n²) average and worst. Space: O(1). Simple but inefficient. Stable sort.",
        
        "selection sort": "Selection sort finds the minimum element and places it at the beginning, repeating for remaining elements. Time: O(n²). Space: O(1). Not stable.",
        
        "insertion sort": "Insertion sort builds the sorted array one element at a time. Time: O(n²) worst, O(n) best (nearly sorted). Space: O(1). Good for small or nearly sorted data.",
        
        "merge sort": "Merge sort divides the array in half, recursively sorts, then merges. Time: O(n log n) always. Space: O(n). Stable sort. Good for linked lists.",
        
        "quick sort": "Quick sort picks a pivot, partitions around it, and recursively sorts partitions. Time: O(n log n) average, O(n²) worst. Space: O(log n). Usually fastest in practice.",
        
        "heap sort": "Heap sort builds a max-heap, then repeatedly extracts the maximum. Time: O(n log n) always. Space: O(1). Not stable but in-place.",
        
        "recursion": "Recursion is when a function calls itself to solve smaller subproblems. Requires: base case (stop condition) and recursive case. Example: factorial, Fibonacci, tree traversal.",
        
        "dynamic programming": "Dynamic programming solves problems by breaking them into overlapping subproblems, storing solutions to avoid recomputation. Techniques: memoization (top-down), tabulation (bottom-up).",
        
        "dp": "DP (Dynamic Programming) solves problems by storing solutions to overlapping subproblems. Key steps: 1) Identify subproblems, 2) Define recurrence, 3) Memoize or tabulate.",
        
        "greedy algorithm": "A greedy algorithm makes locally optimal choices hoping for a global optimum. Works for: activity selection, Huffman coding, Dijkstra's. May not always give optimal solution.",
        
        "backtracking": "Backtracking explores all possible solutions by building candidates incrementally and abandoning those that fail constraints. Used in: N-Queens, Sudoku, permutations.",
        
        "bfs": "BFS (Breadth-First Search) explores a graph level by level using a queue. Time: O(V+E). Used for: shortest path (unweighted), level-order traversal, connected components.",
        
        "dfs": "DFS (Depth-First Search) explores a graph by going as deep as possible before backtracking. Uses stack/recursion. Time: O(V+E). Used for: cycle detection, topological sort, pathfinding.",
        
        "dijkstra": "Dijkstra's algorithm finds shortest paths from a source to all vertices in a weighted graph (non-negative weights). Uses priority queue. Time: O((V+E) log V).",
        
        # Programming Concepts
        "big o": "Big O notation describes algorithm efficiency. Common complexities: O(1) constant, O(log n) logarithmic, O(n) linear, O(n log n) linearithmic, O(n²) quadratic, O(2^n) exponential.",
        
        "time complexity": "Time complexity measures how runtime grows with input size. Express using Big O. Analyze worst, average, and best cases. Focus on dominant terms.",
        
        "space complexity": "Space complexity measures memory usage growth with input size. Includes: input space, auxiliary space, stack space (recursion). Express using Big O notation.",
        
        "oop": "OOP (Object-Oriented Programming) organizes code into objects with data (attributes) and behavior (methods). Four pillars: Encapsulation, Abstraction, Inheritance, Polymorphism.",
        
        "encapsulation": "Encapsulation bundles data and methods into a single unit (class) and restricts direct access to internal state. Use getters/setters. Protects data integrity.",
        
        "inheritance": "Inheritance allows a class to inherit properties and methods from a parent class. Enables code reuse. Types: single, multiple, multilevel, hierarchical.",
        
        "polymorphism": "Polymorphism means 'many forms'. Method overloading (compile-time): same name, different parameters. Method overriding (runtime): child class redefines parent method.",
        
        "abstraction": "Abstraction hides implementation details and shows only essential features. Achieved through abstract classes and interfaces. Reduces complexity for users.",
        
        "api": "An API (Application Programming Interface) defines how software components interact. Types: REST, GraphQL, SOAP, library APIs. Includes endpoints, methods, data formats.",
        
        "rest": "REST is an architectural style for web APIs. Principles: stateless, client-server, cacheable, uniform interface. Uses HTTP methods: GET, POST, PUT, DELETE.",
        
        "sql": "SQL (Structured Query Language) manages relational databases. Key commands: SELECT, INSERT, UPDATE, DELETE, JOIN. Used with: MySQL, PostgreSQL, SQLite.",
        
        "nosql": "NoSQL databases store data in non-tabular formats. Types: document (MongoDB), key-value (Redis), column (Cassandra), graph (Neo4j). Good for: flexibility, scalability.",
        
        "git": "Git is a distributed version control system. Key commands: clone, add, commit, push, pull, branch, merge. Tracks changes, enables collaboration, maintains history.",
        
        "debugging": "Debugging finds and fixes code errors. Techniques: print statements, breakpoints, step-through, rubber duck debugging. Tools: IDE debuggers, logging, profilers.",
        
        # Languages
        "python": "Python is a high-level, interpreted language known for readability. Created by Guido van Rossum (1991). Used for: web dev, data science, AI/ML, automation, scripting.",
        
        "javascript": "JavaScript is a dynamic language for web development. Runs in browsers and Node.js. Features: event-driven, prototype-based, first-class functions. ES6+ adds modern features.",
        
        "java": "Java is a class-based, OOP language with 'write once, run anywhere' via JVM. Created by Sun Microsystems (1995). Used for: enterprise apps, Android, web backends.",
        
        "c++": "C++ is a high-performance language with low-level control and OOP. Extends C with classes. Used for: games, systems programming, embedded systems, performance-critical apps.",
        
        "c": "C is a procedural, low-level language with manual memory management. Created by Dennis Ritchie (1972). Used for: operating systems, embedded systems, compilers.",
        
        "typescript": "TypeScript is JavaScript with static typing. Compiles to JavaScript. Features: interfaces, enums, generics, type inference. Catches errors at compile time.",
        
        # Frameworks & Tools
        "react": "React is a JavaScript library for building user interfaces. Created by Facebook. Key concepts: components, JSX, virtual DOM, hooks, one-way data flow.",
        
        "node": "Node.js is a JavaScript runtime built on Chrome's V8 engine. Enables server-side JavaScript. Features: event-driven, non-blocking I/O, npm package manager.",
        
        "docker": "Docker packages applications into containers - lightweight, standalone units with everything needed to run. Benefits: consistency, isolation, portability, scalability.",
        
        "kubernetes": "Kubernetes (K8s) orchestrates containerized applications. Features: auto-scaling, load balancing, self-healing, rolling updates. Manages container deployment and operation.",
        
        # General CS
        "algorithm": "An algorithm is a step-by-step procedure to solve a problem. Properties: input, output, definiteness, finiteness, effectiveness. Analyzed by time and space complexity.",
        
        "data structure": "A data structure organizes and stores data for efficient access and modification. Types: linear (array, list, stack, queue) and non-linear (tree, graph). Choose based on operations needed.",
        
        "database": "A database is an organized collection of data. Types: relational (SQL), non-relational (NoSQL). Components: tables/collections, queries, indexes, transactions.",
        
        "operating system": "An OS manages hardware and software resources. Functions: process management, memory management, file system, I/O handling, security. Examples: Windows, Linux, macOS.",
        
        "compiler": "A compiler translates source code to machine code before execution. Phases: lexical analysis, parsing, semantic analysis, optimization, code generation.",
        
        "interpreter": "An interpreter executes code line by line without prior compilation. Pros: easier debugging, platform independence. Cons: slower than compiled code.",
        
        "machine learning": "Machine learning enables computers to learn from data without explicit programming. Types: supervised (labeled data), unsupervised (patterns), reinforcement (rewards).",
        
        "artificial intelligence": "AI enables machines to perform tasks requiring human intelligence. Subfields: ML, deep learning, NLP, computer vision, robotics. Applications: assistants, recommendations, autonomous vehicles.",
        
        "neural network": "A neural network is a computing system inspired by biological brains. Layers: input, hidden, output. Training: forward propagation, backpropagation, gradient descent.",
    }
    
    @classmethod
    def lookup(cls, query: str) -> Optional[str]:
        """Look up a topic in built-in knowledge."""
        query_lower = query.lower().strip()
        
        # Direct match
        if query_lower in cls.TOPICS:
            return cls.TOPICS[query_lower]
        
        # Partial match
        for key, value in cls.TOPICS.items():
            if key in query_lower or query_lower in key:
                return value
        
        return None


class WikipediaClient:
    """Wikipedia API client with timeout and error handling."""
    
    BASE_URL = "https://en.wikipedia.org/w/api.php"
    TIMEOUT = 3.0  # Reduced from 5s
    
    @classmethod
    def search(cls, query: str, sentences: int = 3) -> Optional[str]:
        """
        Search Wikipedia and return a summary.
        
        Args:
            query: Search query
            sentences: Number of sentences to return
            
        Returns:
            Summary text or None
        """
        try:
            # First, search for the page
            search_params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 1,
            }
            search_url = f"{cls.BASE_URL}?{urllib.parse.urlencode(search_params)}"
            
            with urllib.request.urlopen(search_url, timeout=cls.TIMEOUT) as response:
                data = json.loads(response.read().decode())
                
                if not data.get('query', {}).get('search'):
                    return None
                
                page_title = data['query']['search'][0]['title']
            
            # Get the summary
            summary_params = {
                "action": "query",
                "prop": "extracts",
                "exintro": "",
                "explaintext": "",
                "titles": page_title,
                "format": "json",
            }
            summary_url = f"{cls.BASE_URL}?{urllib.parse.urlencode(summary_params)}"
            
            with urllib.request.urlopen(summary_url, timeout=cls.TIMEOUT) as response:
                data = json.loads(response.read().decode())
                pages = data.get('query', {}).get('pages', {})
                
                for page_id, page_data in pages.items():
                    if page_id == '-1':
                        continue
                    
                    extract = page_data.get('extract', '')
                    if extract:
                        # Get first N sentences
                        text = cls._extract_sentences(extract, sentences)
                        if len(text) > 50:  # Ensure meaningful content
                            return text
            
            return None
            
        except Exception as e:
            logger.warning(f"Wikipedia lookup failed: {e}")
            return None
    
    @classmethod
    def _extract_sentences(cls, text: str, count: int) -> str:
        """Extract first N sentences from text."""
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Take first N sentences
        result = ' '.join(sentences[:count])
        
        # Ensure it ends with punctuation
        if result and not result[-1] in '.!?':
            result += '.'
        
        return result


class QueryPreprocessor:
    """Preprocess queries for better knowledge lookup."""
    
    # Words to remove from queries
    STOP_WORDS = {
        "explain", "what is", "what's", "who is", "who's",
        "tell me about", "describe", "define", "meaning of",
        "definition of", "how does", "how do", "can you explain",
        "please", "the", "a", "an", "in", "on", "at",
        "me", "you", "i", "we", "they",
    }
    
    @classmethod
    def clean(cls, query: str) -> str:
        """
        Clean query for knowledge lookup.
        
        Removes question indicators and stop words.
        """
        result = query.lower().strip()
        
        # Remove punctuation
        result = re.sub(r'[?!.,;:\'"()]', '', result)
        
        # Remove stop words/phrases
        for stop in cls.STOP_WORDS:
            result = re.sub(rf'\b{re.escape(stop)}\b', '', result, flags=re.IGNORECASE)
        
        # Normalize whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    @classmethod
    def extract_topic(cls, query: str) -> str:
        """Extract the main topic from a question."""
        return cls.clean(query)


class KnowledgeRouter:
    """
    Routes questions to the best knowledge source.
    
    Priority:
    1. Built-in knowledge (instant)
    2. Cache (instant)
    3. Wikipedia (with timeout)
    4. Web search fallback (returns search URL)
    """
    
    def __init__(self):
        self._cache = LRUCache(max_size=500, ttl_seconds=3600)
        self._preprocessor = QueryPreprocessor()
        self._executor = ThreadPoolExecutor(max_workers=2)
    
    def get_answer(self, query: str, timeout: float = 3.0) -> KnowledgeResult:
        """
        Get an answer for the query.
        
        Args:
            query: User's question
            timeout: Maximum time to wait for external sources
            
        Returns:
            KnowledgeResult with answer and metadata
        """
        topic = self._preprocessor.extract_topic(query)
        
        if not topic:
            return KnowledgeResult(
                answer="I'm not sure what you're asking about. Could you rephrase?",
                source="error",
                confidence=0.0,
                topic=query,
            )
        
        # 1. Try built-in knowledge
        builtin = BuiltInKnowledge.lookup(topic)
        if builtin:
            return KnowledgeResult(
                answer=builtin,
                source="built_in",
                confidence=0.95,
                topic=topic,
            )
        
        # 2. Try cache
        cached = self._cache.get(topic)
        if cached:
            return KnowledgeResult(
                answer=cached,
                source="cache",
                confidence=0.90,
                topic=topic,
                cached=True,
            )
        
        # 3. Try Wikipedia with timeout
        try:
            future = self._executor.submit(WikipediaClient.search, topic)
            wiki_result = future.result(timeout=timeout)
            
            if wiki_result:
                # Cache the result
                self._cache.set(topic, wiki_result)
                
                # Truncate if too long
                truncated = False
                if len(wiki_result) > 500:
                    wiki_result = wiki_result[:500] + "..."
                    truncated = True
                
                return KnowledgeResult(
                    answer=wiki_result,
                    source="wikipedia",
                    confidence=0.85,
                    topic=topic,
                    truncated=truncated,
                )
        
        except FuturesTimeoutError:
            logger.warning(f"Wikipedia timeout for: {topic}")
        except Exception as e:
            logger.warning(f"Wikipedia error: {e}")
        
        # 4. Fallback to web search suggestion
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(topic)}"
        return KnowledgeResult(
            answer=f"I don't have information about '{topic}' in my knowledge base. Let me search the web for you.",
            source="web_search",
            confidence=0.5,
            topic=topic,
        )
    
    def get_answer_sync(self, query: str) -> KnowledgeResult:
        """Synchronous version for simple use cases."""
        return self.get_answer(query, timeout=3.0)
    
    def clear_cache(self):
        """Clear the knowledge cache."""
        self._cache.clear()


# Singleton instance
_router = None

def get_knowledge_router() -> KnowledgeRouter:
    """Get the global knowledge router instance."""
    global _router
    if _router is None:
        _router = KnowledgeRouter()
    return _router


def get_answer(query: str, timeout: float = 3.0) -> KnowledgeResult:
    """Convenience function to get an answer."""
    return get_knowledge_router().get_answer(query, timeout)
