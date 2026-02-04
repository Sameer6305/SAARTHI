"""
CONTEXT-PRESERVING MULTI-STEP EXECUTOR - STEP 2 FIX
===================================================

PROBLEM: "open youtube and search new songs"
- Current: Opens YouTube in tab 1, searches Google in tab 2 ❌
- Fixed: Opens YouTube, then searches WITHIN YouTube ✓

SOLUTION: Execute sub-actions sequentially while preserving context.
"""

import time
import logging
import webbrowser
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .intent_engine import ParsedIntent, IntentType

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """
    Context that carries over between sequential actions.
    
    Example: After "open youtube", context contains:
    - last_opened_url: "https://youtube.com"
    - last_opened_site: "youtube"
    - active_browser_tab: True
    """
    # Last action results
    last_action_type: Optional[str] = None
    last_opened_url: Optional[str] = None
    last_opened_site: Optional[str] = None
    last_search_query: Optional[str] = None
    
    # Browser state
    active_browser_tab: bool = False
    
    # Media state
    active_media_player: Optional[str] = None
    
    def update_from_result(self, action_type: str, result: Dict[str, Any]):
        """Update context from action result."""
        self.last_action_type = action_type
        
        if action_type == "open_website":
            self.last_opened_url = result.get("url")
            self.last_opened_site = result.get("site")
            self.active_browser_tab = True
        
        elif action_type == "search_web":
            self.last_search_query = result.get("query")
        
        elif action_type == "play_media":
            self.active_media_player = result.get("platform")


class ContextPreservingExecutor:
    """
    Executes multi-step actions while preserving context.
    
    PRINCIPLE: Each sub-action is aware of previous actions.
    """
    
    def __init__(self, base_executor):
        """
        Args:
            base_executor: The base ActionExecutorV4 instance
        """
        self._executor = base_executor
    
    def execute_multi_step(
        self, 
        intent: ParsedIntent, 
        session_context: Any
    ) -> Dict[str, Any]:
        """
        Execute multi-step command with context preservation.
        
        Args:
            intent: Multi-step intent with sub_intents
            session_context: Session memory context
        
        Returns:
            Combined result from all sub-actions
        """
        if not intent.sub_intents:
            return {
                "success": False,
                "text": "No sub-actions found.",
                "speak": True,
                "category": "error",
            }
        
        # Create execution context
        exec_context = ExecutionContext()
        
        results = []
        all_success = True
        steps_completed = 0
        
        logger.info(f"Executing {len(intent.sub_intents)} sub-actions with context preservation")
        
        for i, sub_intent in enumerate(intent.sub_intents, 1):
            logger.info(f"Step {i}/{len(intent.sub_intents)}: {sub_intent.intent_type.value}")
            
            # Apply context to sub-intent BEFORE execution
            modified_sub_intent = self._apply_context(sub_intent, exec_context)
            
            # Execute with modified intent
            result = self._executor.execute(modified_sub_intent, session_context)
            results.append(result)
            
            # Update context from result
            exec_context.update_from_result(
                sub_intent.intent_type.value,
                result
            )
            
            steps_completed += 1
            
            if not result.get("success", False):
                all_success = False
                logger.warning(f"Step {i} failed: {result.get('text', 'Unknown error')}")
                # Continue anyway - partial success is useful
            
            # Small delay between steps for browser/system to catch up
            if i < len(intent.sub_intents):
                time.sleep(0.4)
        
        # Generate summary response
        return self._generate_summary(results, steps_completed, all_success)
    
    def _apply_context(
        self, 
        sub_intent: ParsedIntent, 
        context: ExecutionContext
    ) -> ParsedIntent:
        """
        Modify sub-intent based on execution context.
        
        CRITICAL LOGIC: This is where we fix the YouTube bug.
        
        Example:
        - Previous: opened YouTube (context.last_opened_site = "youtube")
        - Current: search query "new songs"
        - Modified: search "new songs" ON YouTube
        """
        # If this is a search and we just opened a site, search ON that site
        if sub_intent.intent_type == IntentType.SEARCH_WEB:
            if context.active_browser_tab and context.last_opened_site:
                # Modify to search within the last opened site
                return self._create_site_search_intent(
                    sub_intent, 
                    context.last_opened_site,
                    context.last_opened_url
                )
        
        # If this is play media and we just opened a platform, use that platform
        elif sub_intent.intent_type == IntentType.PLAY_MEDIA:
            if context.active_browser_tab and context.last_opened_site:
                # Search on the media platform
                return self._create_platform_search_intent(
                    sub_intent,
                    context.last_opened_site,
                    context.last_opened_url
                )
        
        # No modification needed
        return sub_intent
    
    def _create_site_search_intent(
        self,
        search_intent: ParsedIntent,
        site: str,
        base_url: Optional[str]
    ) -> ParsedIntent:
        """
        Create a modified search intent for searching within a specific site.
        
        Instead of opening a new tab with Google search,
        we navigate to site's search within the SAME TAB.
        """
        query = search_intent.get_slot("query", "")
        
        # Create site-specific search URL
        search_url = self._build_site_search_url(site, query, base_url)
        
        # Convert to OPEN_WEBSITE intent (reuse existing tab)
        modified = ParsedIntent(
            intent_type=IntentType.OPEN_WEBSITE,
            confidence=search_intent.confidence,
            raw_text=f"search {query} on {site}",
            normalized_text=f"search {query} on {site}",
        )
        
        # Add slots
        from .intent_engine import Slot
        modified.slots = {
            "url": Slot("url", search_url, 1.0),
            "target": Slot("target", f"{site} search", 1.0),
            "query": Slot("query", query, 1.0),
            "site": Slot("site", site, 1.0),
        }
        
        logger.info(f"Context-aware: Searching '{query}' ON {site} (not Google)")
        
        return modified
    
    def _create_platform_search_intent(
        self,
        play_intent: ParsedIntent,
        platform: str,
        base_url: Optional[str]
    ) -> ParsedIntent:
        """
        Create modified intent for playing media on a specific platform.
        """
        query = play_intent.get_slot("query", "")
        
        # Build platform-specific search
        search_url = self._build_site_search_url(platform, query, base_url)
        
        modified = ParsedIntent(
            intent_type=IntentType.OPEN_WEBSITE,
            confidence=play_intent.confidence,
            raw_text=f"play {query} on {platform}",
            normalized_text=f"play {query} on {platform}",
        )
        
        from .intent_engine import Slot
        modified.slots = {
            "url": Slot("url", search_url, 1.0),
            "target": Slot("target", f"{platform}", 1.0),
            "query": Slot("query", query, 1.0),
        }
        
        logger.info(f"Context-aware: Playing '{query}' ON {platform}")
        
        return modified
    
    def _build_site_search_url(
        self, 
        site: str, 
        query: str, 
        base_url: Optional[str]
    ) -> str:
        """
        Build site-specific search URL.
        
        Supports common platforms with their native search.
        """
        import urllib.parse
        encoded_query = urllib.parse.quote_plus(query)
        
        site_lower = site.lower()
        
        # YouTube
        if 'youtube' in site_lower:
            return f"https://www.youtube.com/results?search_query={encoded_query}"
        
        # Spotify
        elif 'spotify' in site_lower:
            return f"https://open.spotify.com/search/{encoded_query}"
        
        # GitHub
        elif 'github' in site_lower:
            return f"https://github.com/search?q={encoded_query}"
        
        # Stack Overflow
        elif 'stackoverflow' in site_lower or 'stack overflow' in site_lower:
            return f"https://stackoverflow.com/search?q={encoded_query}"
        
        # Reddit
        elif 'reddit' in site_lower:
            return f"https://www.reddit.com/search/?q={encoded_query}"
        
        # Twitter/X
        elif 'twitter' in site_lower or site_lower == 'x':
            return f"https://twitter.com/search?q={encoded_query}"
        
        # Amazon
        elif 'amazon' in site_lower:
            return f"https://www.amazon.com/s?k={encoded_query}"
        
        # Wikipedia
        elif 'wikipedia' in site_lower:
            return f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_query}"
        
        # LinkedIn
        elif 'linkedin' in site_lower:
            return f"https://www.linkedin.com/search/results/all/?keywords={encoded_query}"
        
        # Default: use site's base URL + common search patterns
        else:
            if base_url:
                # Try common search endpoints
                for search_path in ['/search?q=', '/search?query=', '/?s=']:
                    return f"{base_url.rstrip('/')}{search_path}{encoded_query}"
            
            # Fallback: Google site search
            return f"https://www.google.com/search?q=site:{site}+{encoded_query}"
    
    def _generate_summary(
        self, 
        results: List[Dict[str, Any]], 
        steps_completed: int,
        all_success: bool
    ) -> Dict[str, Any]:
        """Generate summary response from all sub-action results."""
        
        # Count successes
        success_count = sum(1 for r in results if r.get("success", False))
        
        # Build summary text
        if all_success:
            text = f"Done! Completed all {steps_completed} steps."
        elif success_count > 0:
            text = f"Partially done. Completed {success_count}/{steps_completed} steps."
        else:
            text = "Failed to complete the task."
        
        return {
            "success": all_success,
            "text": text,
            "speak": False,  # Don't spam TTS for multi-step
            "category": "action_confirm",
            "steps_completed": steps_completed,
            "steps_total": len(results),
            "partial_results": results,
        }


# =============================================================================
# FACTORY
# =============================================================================

def create_context_executor(base_executor) -> ContextPreservingExecutor:
    """Create context-preserving executor."""
    return ContextPreservingExecutor(base_executor)
