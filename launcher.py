"""
================================================================================
 VEX SCOUT v11 - LAUNCHER
 This file starts the web server and automatically opens the browser.
 This is what gets packaged into the .exe file.
================================================================================
"""

import os
import sys
import threading
import webbrowser
import time

# When packaged with PyInstaller, files are in a temp folder
# This function finds the correct path to our files
def get_resource_path(filename):
    """Get the path to a resource file, works both in dev and when packaged."""
    if hasattr(sys, '_MEIPASS'):
        # Running as packaged exe - files are in temp folder
        return os.path.join(sys._MEIPASS, filename)
    else:
        # Running as script - files are in same directory
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

# Change to the directory where our files are
if hasattr(sys, '_MEIPASS'):
    os.chdir(sys._MEIPASS)
else:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Now import our main app
# We need to do this AFTER changing directory so it can find index.html
from vex_scout_v11 import app

def open_browser():
    """Wait for server to start, then open browser."""
    time.sleep(1.5)  # Give server time to start
    webbrowser.open('http://localhost:5000')
    print("\n" + "="*50)
    print("🌐 Browser opened to http://localhost:5000")
    print("="*50)
    print("\n⚠️  Keep this window open while using VEX Scout!")
    print("    Close this window to stop the app.\n")

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🤖 VEX SCOUT v11 - EYE TEST EDITION")
    print("="*50)
    print("Starting server...")
    
    # Open browser in a separate thread
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    # Start the Flask server
    # use_reloader=False is important for PyInstaller
    # threaded=True allows multiple requests at once
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
