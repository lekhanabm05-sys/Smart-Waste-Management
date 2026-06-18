#!/bin/bash
# Quick start script for Mac/Linux - Mobile Access

echo "========================================"
echo "Smart Waste Management - Mobile Access"
echo "========================================"
echo ""

# Get IP address
echo "Finding your IP address..."
python3 get_ip.py
echo ""

echo "========================================"
echo "Starting Flask Application..."
echo "========================================"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the Flask app
python3 app.py
