"""
SAARTHI Executor Package Main Entry Point
=========================================

Run SAARTHI production voice assistant as a module:
    python -m saarthi_executor

This forwards to production_main.py
"""

if __name__ == "__main__":
    from saarthi_executor.production_main import main
    main()
