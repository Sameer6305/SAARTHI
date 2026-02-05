"""
Ollama LLM Configuration
=========================

Local Ollama backend for LLM calls - fully offline, no API keys required.

SETUP:
    1. Install Ollama: https://ollama.ai
    2. Start Ollama service
    3. Pull a model: ollama pull llama3.1

USAGE:
    from saarthi_executor.openai_config import check_ollama, call_llm
    
    # Check if Ollama is available (call once at startup)
    is_available, message = check_ollama()
    if not is_available:
        print(message)
        exit(1)
    
    # Call LLM
    response = call_llm("What is Python?")
    print(response)

FEATURES:
- Fully offline operation
- No API keys or billing
- Uses local Ollama instance (http://localhost:11434)
- Default model: llama3.1

Author: SAARTHI Team
Version: 2.0.0
"""

import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# Ollama configuration
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1"


def check_ollama(model: str = DEFAULT_MODEL) -> tuple[bool, str]:
    """
    Check if Ollama is running and the model is available.
    
    Args:
        model: Model name to check (default: llama3.1)
        
    Returns:
        Tuple of (is_available, message)
        - is_available: True if Ollama is running and model is available
        - message: Status message or error with instructions
    """
    try:
        import requests
    except ImportError:
        error_msg = (
            "❌ requests package not installed.\n\n"
            "Install with: pip install requests"
        )
        return False, error_msg
    
    # Check if Ollama is running
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        error_msg = (
            "❌ Ollama is not running.\n\n"
            "START OLLAMA:\n"
            "1. Install Ollama from https://ollama.ai\n"
            "2. Start Ollama (it runs as a service on Windows)\n"
            "3. Verify at: http://localhost:11434\n\n"
            "If Ollama is installed, try starting it manually."
        )
        return False, error_msg
    except Exception as e:
        error_msg = f"❌ Error connecting to Ollama: {e}"
        return False, error_msg
    
    # Check if model is available
    try:
        models = response.json().get("models", [])
        model_names = [m.get("name", "").split(":")[0] for m in models]
        
        if model not in model_names and not any(model in name for name in model_names):
            error_msg = (
                f"❌ Model '{model}' not found in Ollama.\n\n"
                f"AVAILABLE MODELS: {', '.join(model_names) if model_names else 'None'}\n\n"
                f"PULL MODEL:\n"
                f"  ollama pull {model}\n\n"
                f"Or use another model by changing DEFAULT_MODEL in openai_config.py"
            )
            return False, error_msg
        
        success_msg = f"✓ Ollama is running with model '{model}'"
        return True, success_msg
        
    except Exception as e:
        error_msg = f"❌ Error checking Ollama models: {e}"
        return False, error_msg


def call_llm(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.7, max_tokens: int = 500) -> str:
    """
    Call local Ollama LLM with a prompt.
    
    Args:
        prompt: Text prompt to send
        model: Model name (default: llama3.1)
        temperature: Sampling temperature (default: 0.7)
        max_tokens: Maximum tokens to generate (default: 500)
        
    Returns:
        Response text from Ollama
        
    Raises:
        RuntimeError: If Ollama is not available
    """
    try:
        import requests
    except ImportError:
        raise RuntimeError("requests package not installed. Install with: pip install requests")
    
    try:
        response = requests.post(
            OLLAMA_ENDPOINT,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("response", "I couldn't generate a response.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Ollama is not running. Start Ollama and try again.\n"
            "Install from: https://ollama.ai"
        )
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        raise RuntimeError(f"LLM call failed: {e}")


def create_ollama_llm_callback(model: str = DEFAULT_MODEL, temperature: float = 0.7) -> Callable:
    """
    Create an LLM callback function using Ollama.
    
    Args:
        model: Ollama model to use (default: llama3.1)
        temperature: Sampling temperature (default: 0.7)
        
    Returns:
        Callable that takes a prompt and returns response text
        
    Raises:
        RuntimeError: If Ollama is not available
    """
    # Verify Ollama is available
    is_available, message = check_ollama(model)
    if not is_available:
        raise RuntimeError(message)
    
    logger.info(f"LLM callback created with model: {model}")
    
    def ollama_callback(prompt: str) -> str:
        """
        Send prompt to Ollama and return response.
        
        Args:
            prompt: Text prompt to send
            
        Returns:
            Response text from Ollama
        """
        try:
            return call_llm(prompt, model=model, temperature=temperature)
        except Exception as e:
            logger.error(f"Ollama callback failed: {e}")
            return "I'm having trouble thinking right now. Please try again."
    
    return ollama_callback


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("Ollama LLM Configuration Test")
    print("=" * 60)
    print()
    
    # Check Ollama availability
    print(f"Checking Ollama with model: {DEFAULT_MODEL}...")
    is_available, message = check_ollama()
    print(message)
    print()
    
    if not is_available:
        sys.exit(1)
    
    # Test LLM call
    print("Testing LLM call...")
    try:
        response = call_llm("Say 'Hello from SAARTHI!' in a friendly way.")
        print(f"Response: {response}")
        print()
        print("✓ Ollama LLM is working correctly")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
