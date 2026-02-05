"""
Development script with auto-reload.
Restarts main.py whenever Python files change.
"""

import subprocess
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class RestartHandler(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.start_process()

    def start_process(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
        print("\n🔄 Starting bot...\n")
        self.process = subprocess.Popen([sys.executable, "main.py"])

    def on_modified(self, event):
        if event.src_path.endswith(".py"):
            print(f"\n📝 {Path(event.src_path).name} changed, restarting...")
            self.start_process()


if __name__ == "__main__":
    handler = RestartHandler()
    observer = Observer()

    # Watch current directory and subdirectories
    observer.schedule(handler, ".", recursive=True)
    observer.start()

    print("👀 Watching for file changes... (Ctrl+C to stop)\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        observer.stop()
        if handler.process:
            handler.process.terminate()

    observer.join()
