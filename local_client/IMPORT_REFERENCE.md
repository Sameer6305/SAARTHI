# SAARTHI Import Structure Reference

## Verified Module Structure

```
saarthi_executor/
├── __init__.py                 ✓ Package root
├── __main__.py                 ✓ Module entry (python -m saarthi_executor)
├── production_main.py          ✓ Main application
├── production_pipeline.py      ✓ Audio pipeline
├── production_router.py        ✓ Intent router
├── feedback_ux.py             ✓ User feedback
├── openai_config.py           ✓ OpenAI API config
├── integrated_assistant.py     ✓ Assistant logic
├── audio_capture.py           ✓ Audio capture (legacy)
└── voice/                     ✓ Voice subsystem
    ├── __init__.py
    ├── audio_capture.py       ✓ Push-to-talk capture
    ├── stt_whisper.py         ✓ Whisper STT
    └── config.py              ✓ Voice config
```

## Correct Import Patterns

### From production_main.py
```python
# ✓ CORRECT
from saarthi_executor.feedback_ux import get_feedback_manager
from saarthi_executor.voice.stt_whisper import LocalWhisperSTT
from saarthi_executor.production_pipeline import ProductionVoicePipeline
from saarthi_executor.production_router import create_production_assistant
from saarthi_executor.openai_config import create_openai_llm_callback

# ✗ WRONG
from feedback_ux import get_feedback_manager  # Relative import fails
from voice.stt_whisper import LocalWhisperSTT  # Relative import fails
```

### From production_pipeline.py
```python
# ✓ CORRECT
from saarthi_executor.voice.audio_capture import PushToTalkCapture
from saarthi_executor.voice.stt_whisper import LocalWhisperSTT
from saarthi_executor.voice.config import WhisperModel

# ✗ WRONG
from voice.audio_capture import PushToTalkCapture  # Relative fails in module context
```

### From production_router.py
```python
# ✓ CORRECT
from saarthi_executor.integrated_assistant import SimpleTTS

# ✗ WRONG
from integrated_assistant import SimpleTTS  # Relative fails
```

## Verified Class Names

### voice/audio_capture.py
- `AudioBuffer` - Audio data container (has `.data`, `.sample_rate`, `.duration_seconds`)
- `CaptureResult` - Capture result (has `.success`, `.audio`, `.error`, `.duration_seconds`)
- `PushToTalkCapture` - Main capture class

**CRITICAL**: Use `result.audio` NOT `result.audio_data` (the latter doesn't exist)

### voice/stt_whisper.py
- `LocalWhisperSTT` - Whisper STT engine
- Method: `transcribe(audio: AudioBuffer)` - Returns transcript with `.text`, `.confidence`, `.language`

### voice/config.py
- `WhisperModel` (Enum) - Model sizes (TINY, BASE, SMALL, MEDIUM, LARGE)

### integrated_assistant.py
- `SimpleTTS` - Simple TTS wrapper

### production_pipeline.py
- `PipelineState` (Enum) - IDLE, RECORDING, VALIDATING, TRANSCRIBING, ERROR
- `AudioValidation` - Validation result dataclass
- `ProductionVoicePipeline` - Main pipeline class

### production_router.py
- `RouteCategory` (Enum) - KNOWLEDGE, STUDENT, ACTION, CLARIFICATION, CONVERSATION, SYSTEM
- `RouteDecision` - Routing decision dataclass
- `ProductionRouter` - Intent router
- `ProductionAssistant` - Main assistant class
- `create_production_assistant()` - Factory function

### feedback_ux.py
- `FeedbackState` (Enum) - IDLE, LISTENING, PROCESSING, SPEAKING, ERROR, SUCCESS, CONFIRMING
- `FeedbackMessage` - Message dataclass
- `FeedbackManager` - Main feedback manager
- `get_feedback_manager()` - Singleton factory

### openai_config.py
- `get_openai_key()` - Get API key from env
- `get_openai_client()` - Create OpenAI client
- `load_openai_config()` - Load full config
- `create_openai_llm_callback()` - Create LLM callback

## Running the Application

### As Module (Recommended)
```bash
cd local_client
python -m saarthi_executor.production_main
```

### Direct Script
```bash
cd local_client/saarthi_executor
python production_main.py
```

### Via Package Main
```bash
cd local_client
python -m saarthi_executor
```

## Common Import Errors and Fixes

### Error: `ModuleNotFoundError: No module named 'saarthi_executor'`
**Fix**: Run from `local_client/` directory, not from inside `saarthi_executor/`
```bash
cd local_client  # ← Must be here
python -m saarthi_executor.production_main
```

### Error: `AttributeError: 'CaptureResult' object has no attribute 'audio_data'`
**Fix**: Use `.audio` not `.audio_data`
```python
# ✓ CORRECT
audio_buffer = result.audio

# ✗ WRONG
audio_buffer = result.audio_data  # Does not exist!
```

### Error: `ImportError: attempted relative import with no known parent package`
**Fix**: Use absolute imports with `saarthi_executor.` prefix
```python
# ✓ CORRECT
from saarthi_executor.voice.stt_whisper import LocalWhisperSTT

# ✗ WRONG
from voice.stt_whisper import LocalWhisperSTT  # Relative import
```

### Error: `ValueError: OpenAI API key not found`
**Fix**: Set `OPENAI_API_KEY` environment variable
```bash
# PowerShell
$env:OPENAI_API_KEY = "your-key-here"

# CMD
set OPENAI_API_KEY=your-key-here

# Linux/Mac
export OPENAI_API_KEY="your-key-here"
```

## Environment Setup Checklist

- [ ] Python 3.10+ installed
- [ ] In correct directory (`local_client/`)
- [ ] `__init__.py` exists in `saarthi_executor/`
- [ ] `__init__.py` exists in `saarthi_executor/voice/`
- [ ] Dependencies installed: `pip install numpy keyboard pyttsx3 pywin32`
- [ ] (Optional) OpenAI installed: `pip install openai`
- [ ] (Optional) `OPENAI_API_KEY` environment variable set
- [ ] Microphone permissions granted (Windows Settings > Privacy)

## Verification Commands

```bash
# Test all imports
python -c "from saarthi_executor.production_main import main; print('✓ Imports OK')"

# Test OpenAI config
python -m saarthi_executor.openai_config

# Run bug audit
python -m saarthi_executor.bug_audit_tests

# Check package structure
python -c "import saarthi_executor; print(saarthi_executor.__version__)"
```

## Reference: Correct Usage Examples

### Initialize Production Pipeline
```python
from saarthi_executor.production_pipeline import ProductionVoicePipeline
from saarthi_executor.voice.stt_whisper import LocalWhisperSTT

stt = LocalWhisperSTT()
pipeline = ProductionVoicePipeline(
    stt=stt,
    on_transcription=lambda text, conf: print(f"Got: {text}"),
    on_error=lambda err: print(f"Error: {err}"),
)
pipeline.initialize()
```

### Use Production Router
```python
from saarthi_executor.production_router import ProductionRouter

router = ProductionRouter()
decision = router.route("open youtube")
print(f"Category: {decision.category.name}")
print(f"Intent: {decision.intent}")
```

### Access Audio Data Correctly
```python
from saarthi_executor.voice.audio_capture import PushToTalkCapture

capture = PushToTalkCapture()
result = capture.stop_recording()

if result.success:
    audio = result.audio  # ✓ CORRECT
    samples = audio.data  # ✓ Access raw samples
    rate = audio.sample_rate
    duration = audio.duration_seconds
```

### Use OpenAI (Optional)
```python
from saarthi_executor.openai_config import get_openai_client, create_openai_llm_callback

# Check if API key is set
try:
    client = get_openai_client()
    print("✓ OpenAI configured")
    
    # Create LLM callback
    llm = create_openai_llm_callback(model="gpt-3.5-turbo")
    response = llm("What is Python?")
    print(response)
    
except ValueError:
    print("OpenAI API key not set")
```

---

**Last Verified**: All imports tested and working as of production stabilization v1.0.0
