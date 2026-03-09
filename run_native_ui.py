import os
import sys

# Ensure backend can be imported safely
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from frontend_pyqt.main import BaseTuneMainWindow
from PyQt6.QtWidgets import QApplication

def exception_hook(exctype, value, traceback):
    print(f"CRITICAL ERROR: {exctype.__name__}: {value}")
    import traceback as tb
    tb.print_tb(traceback)
    sys.exit(1)

def main():
    sys.excepthook = exception_hook
    print("Starting BaseTune Architect Native UI...")
    
    try:
        try:
            import qasync
        except ImportError:
            print("Installing qasync...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "qasync"])
            import qasync
            
        import asyncio
        app = QApplication(sys.argv)
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
        
        # Pre-flight check
        print("Initializing UI Components...")
        window = BaseTuneMainWindow()
        window.show()
        print("Main Window Visible. Entering event loop.")
        with loop:
            loop.run_forever()
    except Exception as e:
        print(f"Startup Crash: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
