# SAARTHI Setup Guide

## Running the Production System

### Method 1: As a Python Module (Recommended)
```bash
cd local_client
python -m saarthi_executor.production_main
```

### Method 2: Direct Script Execution
```bash
cd local_client/saarthi_executor
python production_main.py
```

### Method 3: Using Package Main
```bash
cd local_client
python -m saarthi_executor
```

## OpenAI API Configuration

SAARTHI supports OpenAI GPT models for enhanced language understanding.

### Setting Up OpenAI API Key

**IMPORTANT: Never hardcode API keys in code. Always use environment variables or .env file.**

#### Method 1: Using .env File (Recommended)

This is the easiest method for local development.

**Step 1: Create .env file**
```bash
cd local_client
cp .env.example .env  # Copy the template
```

**Step 2: Edit .env file**
Open `.env` in any text editor and add your API key:
```
OPENAI_API_KEY=your-actual-api-key-here
```

**Step 3: Run SAARTHI**
```bash
python -m saarthi_executor.production_main
```

✅ **Advantages:**
- No need to set environment variables each session
- Easy to switch between different API keys
- Already git-ignored (won't be committed accidentally)
- Works across all operating systems

⚠️ **Security Notes:**
- Never commit your `.env` file to git
- Never share your `.env` file with others
- Keep your API key secret

#### Method 2: Environment Variables (Alternative)

If you prefer system environment variables:

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "your-api-key-here"
python -m saarthi_executor.production_main
```

For permanent setup, add to your PowerShell profile:
```powershell
notepad $PROFILE
# Add this line:
$env:OPENAI_API_KEY = "your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=your-api-key-here
python -m saarthi_executor.production_main
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY="your-api-key-here"
python -m saarthi_executor.production_main
```

For permanent setup, add to `~/.bashrc` or `~/.zshrc`:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Getting an OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create a new API key
4. Copy the key (it will only be shown once)
5. Add it to your `.env` file or set as environment variable

### Testing OpenAI Configuration

Test if your API key is properly configured:

```bash
cd local_client
python -m saarthi_executor.openai_config
```

This will:
- Load `.env` file automatically
- Check if `OPENAI_API_KEY` is set
- Validate the key format
- Verify the OpenAI client can be created
- Test a simple API call

Expected output if configured correctly:
```
Loading .env file...
Loaded .env from: C:\Users\...\local_client\.env

Validating OpenAI API key...
✓ OpenAI API key found (starts with: sk-proj...)

Testing OpenAI client creation...
✓ Successfully created OpenAI client
```

## LLM Provider Configuration

SAARTHI supports two LLM providers:

### 1. OpenAI (Recommended for Production)
- **Models**: gpt-3.5-turbo, gpt-4, gpt-4-turbo
- **Requires**: OPENAI_API_KEY environment variable
- **Cost**: Pay per token (see OpenAI pricing)
- **Quality**: Excellent

To enable OpenAI in `production_main.py`:
```python
config = ProductionConfig(
    enable_tts=True,
    enable_llm=True,
    llm_provider="openai",
    llm_model="gpt-3.5-turbo",  # or "gpt-4"
)
```

### 2. Ollama (Free, Local)
- **Models**: phi3, mistral, llama2, etc.
- **Requires**: Ollama running locally
- **Cost**: Free (runs on your hardware)
- **Quality**: Good

Install Ollama: https://ollama.ai

To enable Ollama in `production_main.py`:
```python
config = ProductionConfig(
    enable_tts=True,
    enable_llm=True,
    llm_provider="ollama",
    llm_model="phi3",
    llm_endpoint="http://localhost:11434/api/generate",
)
```

### Using Without LLM (Default)
SAARTHI works great without an LLM using:
- Pattern matching for common commands
- Built-in knowledge base for CS concepts
- Direct intent routing

```python
config = ProductionConfig(
    enable_tts=True,
    enable_llm=False,  # No LLM needed
)
```

## Dependencies

### Required
```bash
pip install numpy keyboard pyttsx3
pip install pywin32  # For Windows TTS
```

### Optional
```bash
# For OpenAI support
pip install openai

# For Ollama (local LLM)
# Install from: https://ollama.ai

# For system tray icon
pip install pystray pillow
```

### For Voice Input (Advanced)
```bash
pip install whisper torch torchaudio
# Or use faster-whisper:
pip install faster-whisper
```

## Project Structure

```
local_client/
  saarthi_executor/
    __init__.py                  # Package initialization
    __main__.py                  # Module entry point
    production_main.py           # Main application
    production_pipeline.py       # Audio processing
    production_router.py         # Intent routing
    feedback_ux.py              # User feedback
    openai_config.py            # OpenAI configuration
    bug_audit_tests.py          # Test suite
    voice/                      # Voice subsystem
      __init__.py
      audio_capture.py
      stt_whisper.py
      ...
```

## Running Tests

```bash
cd local_client/saarthi_executor
python bug_audit_tests.py
```

Expected output:
```
SAARTHI Production Bug Audit
============================================================
...
Total Tests: 27
Passed: 27
Failed: 0
Errors: 0
Status: ✅ ALL PASSED
```

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the right directory
cd local_client
python -m saarthi_executor.production_main

# Or add to PYTHONPATH
export PYTHONPATH="$PYTHONPATH:/path/to/saarthi/local_client"
```

### OpenAI API Errors
```bash
# Verify API key is set
python -c "import os; print(os.environ.get('OPENAI_API_KEY', 'NOT SET'))"

# Test OpenAI config
python -m saarthi_executor.openai_config
```

### Audio/Microphone Issues
- Ensure microphone permissions are granted
- Check Windows Privacy Settings > Microphone
- Test microphone with other applications

### Module Not Found Errors
```bash
# Verify package structure
python -c "import saarthi_executor; print(saarthi_executor.__file__)"

# Check __init__.py exists
ls local_client/saarthi_executor/__init__.py
ls local_client/saarthi_executor/voice/__init__.py
```

## Security Best Practices

1. **Never commit API keys to Git**
   - Add `.env` to `.gitignore`
   - Use environment variables only

2. **Rotate API keys regularly**
   - Generate new keys monthly
   - Delete old keys from OpenAI dashboard

3. **Monitor API usage**
   - Check OpenAI dashboard for usage
   - Set spending limits

4. **Use separate keys for dev/prod**
   - Different keys for testing vs production
   - Easier to track and revoke

## Additional Resources

- OpenAI API Documentation: https://platform.openai.com/docs
- Ollama Models: https://ollama.ai/library
- Python Environment Variables: https://docs.python.org/3/library/os.html#os.environ
