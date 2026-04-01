================================================================================
 VEX SCOUT v11 - EYE TEST EDITION
 Build Instructions
================================================================================

WHAT'S IN THIS FOLDER:
----------------------
- vex_scout_v11.py   : Main application (backend)
- index.html         : User interface (frontend)  
- launcher.py        : Starts app and opens browser
- build.bat          : One-click build script
- README.txt         : This file


HOW TO BUILD THE STANDALONE APP:
--------------------------------
1. Make sure Python is installed on your computer
   - Download from https://python.org if needed
   - IMPORTANT: Check "Add Python to PATH" during installation!

2. Put all these files in ONE folder:
   - vex_scout_v11.py
   - index.html
   - launcher.py
   - build.bat

3. Double-click "build.bat"
   - Wait 2-5 minutes for it to finish
   - A folder will open when done

4. Your app is in: dist\VEX Scout\
   - Double-click "VEX Scout.exe" to run it!


SHARING WITH OTHERS:
--------------------
1. Copy the entire "dist\VEX Scout" folder
2. Send it to anyone (zip it first for easier sharing)
3. They just double-click "VEX Scout.exe"
4. NO Python installation needed on their computer!


TROUBLESHOOTING:
----------------
Q: "Python is not recognized" error
A: Reinstall Python and check "Add Python to PATH"

Q: Build fails with red errors
A: Try running build.bat as Administrator (right-click > Run as administrator)

Q: App won't start / crashes immediately  
A: Make sure index.html is in the same folder as the .exe

Q: Browser doesn't open
A: Manually go to http://localhost:5000 in your browser

Q: "Port 5000 already in use" error
A: Close any other VEX Scout windows, or restart your computer


FOR DEVELOPMENT (without building):
-----------------------------------
If you just want to run it with Python installed:

1. Open Command Prompt in this folder
2. Run: pip install flask flask-cors pandas numpy scikit-learn joblib requests
3. Run: python launcher.py
4. Browser opens automatically!


================================================================================
 Built for VEX Think Award
 Good luck at competition! 🏆
================================================================================
