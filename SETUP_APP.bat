@echo off
color 0A
title Smart Waste Management - App Setup

cls
echo.
echo ╔══════════════════════════════════════════════════════════════════╗
echo ║                                                                  ║
echo ║     📱 SMART WASTE MANAGEMENT - APP SETUP 📱                     ║
echo ║                                                                  ║
echo ╚══════════════════════════════════════════════════════════════════╝
echo.
echo.

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  STEP 1: Installing required packages...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

pip install Pillow

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  STEP 2: Generating app icons...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

py generate_icons.py

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  STEP 3: Starting the application...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo  ✅ App is starting...
echo  ✅ Open browser and go to: http://localhost:5000
echo  ✅ Look for "Install App" button in bottom-right corner
echo  ✅ Click it to install as a native app!
echo.
echo  Press Ctrl+C to stop the server
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

py app.py

pause
