"""
Piper TTS Setup Script
======================

Downloads and configures Piper TTS for SAARTHI.

PIPER TTS:
- Open source neural TTS
- Runs 100% locally
- Very fast (~50ms latency)
- Multiple voice models available

RECOMMENDED VOICES FOR DEEP/ROBOTIC:
1. en_US-ryan-medium   - Deep male, clear (RECOMMENDED)
2. en_US-joe-medium    - Very deep male
3. en_GB-alan-medium   - British, authoritative

RUN THIS SCRIPT:
    python setup_piper.py

This will:
1. Download piper.exe
2. Download recommended voice model
3. Test the installation
"""

import os
import sys
import urllib.request
import zipfile
import json
from pathlib import Path

# Configuration
PIPER_DIR = Path.home() / ".saarthi" / "piper"
PIPER_VERSION = "2023.11.14-2"  # Latest stable

# Download URLs
PIPER_RELEASES = "https://github.com/rhasspy/piper/releases/download"
PIPER_WINDOWS_URL = f"{PIPER_RELEASES}/{PIPER_VERSION}/piper_windows_amd64.zip"

# Voice models (from Hugging Face)
VOICE_MODELS = {
    "en_US-ryan-medium": {
        "description": "Deep male voice, clear articulation (RECOMMENDED)",
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium/en_US-ryan-medium.onnx.json",
        "size_mb": 63,
    },
    "en_US-joe-medium": {
        "description": "Very deep male voice",
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/joe/medium/en_US-joe-medium.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/joe/medium/en_US-joe-medium.onnx.json",
        "size_mb": 63,
    },
    "en_GB-alan-medium": {
        "description": "British male, authoritative",
        "model": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        "config": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json",
        "size_mb": 63,
    },
}

DEFAULT_VOICE = "en_US-ryan-medium"


def download_file(url: str, dest: Path, description: str = "") -> bool:
    """Download a file with progress."""
    print(f"Downloading {description or url}...")
    
    try:
        def progress_hook(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size) if total_size > 0 else 0
            sys.stdout.write(f"\r  Progress: {percent}%")
            sys.stdout.flush()
        
        urllib.request.urlretrieve(url, dest, progress_hook)
        print()  # New line after progress
        return True
        
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def setup_piper():
    """Download and set up Piper TTS."""
    print("=" * 60)
    print("SAARTHI - Piper TTS Setup")
    print("=" * 60)
    print()
    
    # Create directory
    PIPER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Installation directory: {PIPER_DIR}")
    print()
    
    # Check if already installed
    piper_exe = PIPER_DIR / "piper.exe"
    if piper_exe.exists():
        print("[✓] Piper already installed")
    else:
        # Download Piper
        print("[1/3] Downloading Piper TTS...")
        zip_path = PIPER_DIR / "piper.zip"
        
        if not download_file(PIPER_WINDOWS_URL, zip_path, "Piper Windows"):
            print("Failed to download Piper. Please download manually from:")
            print(f"  {PIPER_WINDOWS_URL}")
            return False
        
        # Extract
        print("  Extracting...")
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(PIPER_DIR)
            
            # Move files from nested folder if needed
            nested = PIPER_DIR / "piper"
            if nested.exists():
                for f in nested.iterdir():
                    f.rename(PIPER_DIR / f.name)
                nested.rmdir()
            
            zip_path.unlink()  # Delete zip
            print("  [✓] Piper extracted")
            
        except Exception as e:
            print(f"  ERROR extracting: {e}")
            return False
    
    # Download voice model
    print()
    print("[2/3] Voice Model Selection")
    print()
    print("Available voices for deep/robotic effect:")
    for i, (name, info) in enumerate(VOICE_MODELS.items(), 1):
        marker = " (RECOMMENDED)" if name == DEFAULT_VOICE else ""
        print(f"  {i}. {name}{marker}")
        print(f"     {info['description']} ({info['size_mb']} MB)")
    
    print()
    choice = input(f"Select voice [1-{len(VOICE_MODELS)}] (default=1): ").strip()
    
    try:
        idx = int(choice) - 1 if choice else 0
        voice_name = list(VOICE_MODELS.keys())[idx]
    except:
        voice_name = DEFAULT_VOICE
    
    voice_info = VOICE_MODELS[voice_name]
    model_path = PIPER_DIR / f"{voice_name}.onnx"
    config_path = PIPER_DIR / f"{voice_name}.onnx.json"
    
    if model_path.exists():
        print(f"[✓] Voice model already downloaded: {voice_name}")
    else:
        print(f"\nDownloading voice: {voice_name}...")
        
        if not download_file(voice_info["model"], model_path, "voice model"):
            return False
        
        if not download_file(voice_info["config"], config_path, "voice config"):
            return False
        
        print(f"[✓] Voice model installed: {voice_name}")
    
    # Test installation
    print()
    print("[3/3] Testing installation...")
    
    import subprocess
    test_text = "Hello, I am SAARTHI, your study assistant."
    test_output = PIPER_DIR / "test_output.wav"
    
    try:
        result = subprocess.run(
            [str(piper_exe), "--model", str(model_path), "--output_file", str(test_output)],
            input=test_text,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0 and test_output.exists():
            print("[✓] Piper TTS working!")
            
            # Play test audio
            try:
                import winsound
                print("\nPlaying test audio...")
                winsound.PlaySound(str(test_output), winsound.SND_FILENAME)
            except:
                print("(Could not play audio - install pywin32 for playback)")
            
            test_output.unlink()  # Cleanup
        else:
            print(f"[!] Test failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"[!] Test failed: {e}")
        return False
    
    # Save configuration
    config = {
        "piper_path": str(PIPER_DIR),
        "voice_model": voice_name,
        "engine": "piper",
    }
    
    config_file = Path.home() / ".saarthi" / "tts_config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    
    print()
    print("=" * 60)
    print("SETUP COMPLETE!")
    print("=" * 60)
    print()
    print(f"Piper installed at: {PIPER_DIR}")
    print(f"Voice model: {voice_name}")
    print(f"Config saved: {config_file}")
    print()
    print("SAARTHI TTS is ready to use!")
    print()
    
    return True


def setup_sapi_fallback():
    """Configure Windows SAPI as fallback."""
    print()
    print("Setting up Windows SAPI fallback...")
    
    try:
        import win32com.client
        engine = win32com.client.Dispatch("SAPI.SpVoice")
        voices = engine.GetVoices()
        
        print(f"[✓] SAPI available with {voices.Count} voices:")
        for i in range(voices.Count):
            voice = voices.Item(i)
            print(f"    - {voice.GetDescription()}")
        
        return True
        
    except ImportError:
        print("[!] pywin32 not installed")
        print("    Run: pip install pywin32")
        return False
    except Exception as e:
        print(f"[!] SAPI error: {e}")
        return False


if __name__ == "__main__":
    print()
    print("This script will set up Piper TTS for SAARTHI")
    print("This requires ~130 MB of downloads")
    print()
    
    proceed = input("Continue? [Y/n]: ").strip().lower()
    if proceed and proceed != 'y':
        print("Cancelled.")
        sys.exit(0)
    
    print()
    
    # Setup Piper (primary)
    piper_ok = setup_piper()
    
    # Setup SAPI (fallback)
    sapi_ok = setup_sapi_fallback()
    
    if not piper_ok and not sapi_ok:
        print("\n[!] No TTS engine available!")
        sys.exit(1)
    
    print("\n[✓] TTS setup complete!")
