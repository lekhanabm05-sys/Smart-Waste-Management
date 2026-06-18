@echo off
color 0A
title Smart Waste Management - Mobile Access

cls
echo.
echo ╔══════════════════════════════════════════════════════════════════╗
echo ║                                                                  ║
echo ║     📱 SMART WASTE MANAGEMENT - MOBILE ACCESS READY 📱           ║
echo ║                                                                  ║
echo ╚══════════════════════════════════════════════════════════════════╝
echo.
echo.

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  STEP 1: Finding your IP address...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

py get_ip.py

echo.
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo  STEP 2: Starting Flask Application...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo  ✅ Application is starting...
echo  ✅ Keep this window OPEN
echo  ✅ Open the URL shown above on your mobile browser
echo.
echo  Press Ctrl+C to stop the server
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

py app.py

pause
