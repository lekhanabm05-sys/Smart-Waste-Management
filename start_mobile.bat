@echo off
REM Quick start script for Windows - Mobile Access

echo ========================================
echo Smart Waste Management - Mobile Access
echo ========================================
echo.

REM Get IP address
echo Finding your IP address...
python get_ip.py
echo.

echo ========================================
echo Starting Flask Application...
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the Flask app
python app.py
