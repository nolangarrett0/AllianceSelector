@echo off
REM ============================================================================
REM  VEX SCOUT v11 - BUILD SCRIPT
REM  This script packages VEX Scout into a standalone Windows application.
REM  
REM  REQUIREMENTS:
REM  - Python installed on this computer
REM  - Internet connection (to download dependencies first time)
REM
REM  HOW TO USE:
REM  1. Double-click this file (build.bat)
REM  2. Wait for it to finish (may take a few minutes)
REM  3. Find your app in the "dist\VEX Scout" folder
REM  4. Share that folder with anyone!
REM ============================================================================

echo.
echo ============================================================
echo   VEX SCOUT v11 - BUILD SCRIPT
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/4] Python found! Installing required packages...
echo.

REM Install required packages
python -m pip install flask flask-cors pandas numpy scikit-learn joblib requests pyinstaller --quiet

if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages!
    echo Try running this as Administrator.
    pause
    exit /b 1
)

echo.
echo [2/4] Packages installed! Building executable...
echo       (This may take 2-5 minutes)
echo.

REM Build the executable with PyInstaller
REM Using "python -m PyInstaller" instead of just "pyinstaller" to avoid PATH issues
python -m PyInstaller ^
    --onedir ^
    --name "VEX Scout" ^
    --add-data "index.html;." ^
    --add-data "vex_scout_v11.py;." ^
    --hidden-import=sklearn.ensemble._forest ^
    --hidden-import=sklearn.tree._tree ^
    --hidden-import=sklearn.neighbors._typedefs ^
    --hidden-import=sklearn.neighbors._quad_tree ^
    --hidden-import=sklearn.utils._typedefs ^
    --hidden-import=sklearn.utils._cython_blas ^
    --hidden-import=numpy ^
    --hidden-import=pandas ^
    --hidden-import=flask ^
    --hidden-import=flask_cors ^
    --collect-submodules sklearn ^
    --noconfirm ^
    launcher.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed!
    echo Check the error messages above.
    pause
    exit /b 1
)

echo.
echo [3/4] Build complete! Cleaning up...
echo.

REM Rename the exe inside the folder for clarity
if exist "dist\VEX Scout\launcher.exe" (
    move "dist\VEX Scout\launcher.exe" "dist\VEX Scout\VEX Scout.exe" >nul 2>&1
)

REM Create a simple readme in the output folder
echo VEX SCOUT v11 - EYE TEST EDITION > "dist\VEX Scout\README.txt"
echo ================================= >> "dist\VEX Scout\README.txt"
echo. >> "dist\VEX Scout\README.txt"
echo HOW TO USE: >> "dist\VEX Scout\README.txt"
echo 1. Double-click "VEX Scout.exe" >> "dist\VEX Scout\README.txt"
echo 2. Your browser will open automatically >> "dist\VEX Scout\README.txt"
echo 3. Enter your event SKU and analyze! >> "dist\VEX Scout\README.txt"
echo. >> "dist\VEX Scout\README.txt"
echo Keep the black window open while using the app. >> "dist\VEX Scout\README.txt"
echo Close it when you're done. >> "dist\VEX Scout\README.txt"
echo. >> "dist\VEX Scout\README.txt"
echo Built for VEX Think Award >> "dist\VEX Scout\README.txt"

echo.
echo [4/4] Done!
echo.
echo ============================================================
echo   SUCCESS! Your app is ready!
echo ============================================================
echo.
echo   Location: dist\VEX Scout\
echo.
echo   To use:
echo   1. Go to the "dist\VEX Scout" folder
echo   2. Double-click "VEX Scout.exe"
echo   3. Browser opens automatically!
echo.
echo   To share:
echo   - Copy the entire "VEX Scout" folder
echo   - Send it to anyone (no Python needed!)
echo.
echo ============================================================
echo.

REM Open the output folder
explorer "dist\VEX Scout"

pause
