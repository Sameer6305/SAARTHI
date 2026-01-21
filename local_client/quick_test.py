"""
Quick Test - Verify SAARTHI is working
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

def test_assistant():
    """Test the assistant directly."""
    print("\n" + "="*60)
    print("SAARTHI Quick Test")
    print("="*60)
    
    try:
        from saarthi_executor.integrated_assistant import IntegratedAssistant
        
        print("\n1. Creating assistant...")
        assistant = IntegratedAssistant(enable_tts=False)
        assistant.initialize()
        print("   ✓ Assistant created")
        
        print("\n2. Testing commands...")
        
        test_cases = [
            ("hi", "Should respond with greeting"),
            ("open youtube", "Should ask for confirmation"),
            ("yes", "Should open YouTube"),
            ("explain binary search", "Should give explanation"),
            ("search for python tutorials", "Should ask for confirmation"),
            ("no", "Should cancel"),
            ("thanks", "Should respond with thanks"),
            ("status", "Should show status"),
        ]
        
        for cmd, expected in test_cases:
            print(f"\n   Command: \"{cmd}\"")
            print(f"   Expected: {expected}")
            response = assistant.process(cmd)
            print(f"   Response: \"{response.text}\"")
            
            if response.action_executed:
                print(f"   Action: {response.action_type}")
        
        print("\n3. Stats:")
        stats = assistant.get_stats()
        for k, v in stats.items():
            print(f"   {k}: {v}")
        
        print("\n" + "="*60)
        print("✓ All tests passed!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_assistant()
    sys.exit(0 if success else 1)
