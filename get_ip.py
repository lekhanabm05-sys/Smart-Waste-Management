#!/usr/bin/env python3
"""
Simple script to get your computer's IP address for mobile access
"""
import socket
import platform

def get_ip_address():
    """Get the local IP address of this computer"""
    try:
        # Create a socket connection to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a public DNS server (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
        s.close()
        return ip_address
    except Exception:
        return "Unable to determine IP address"

def main():
    print("=" * 60)
    print("🌐 SMART WASTE MANAGEMENT - MOBILE ACCESS")
    print("=" * 60)
    print()
    
    # Get system info
    system = platform.system()
    print(f"Operating System: {system}")
    print(f"Computer Name: {socket.gethostname()}")
    print()
    
    # Get IP address
    ip = get_ip_address()
    print(f"📱 Your Computer's IP Address: {ip}")
    print()
    
    if ip != "Unable to determine IP address":
        print("=" * 60)
        print("🚀 HOW TO ACCESS FROM MOBILE:")
        print("=" * 60)
        print()
        print("1. Make sure your mobile device is on the SAME WiFi network")
        print("2. Start the Flask app: python app.py")
        print("3. Open mobile browser and go to:")
        print()
        print(f"   👉 http://{ip}:5000")
        print()
        print("=" * 60)
        print()
        print("💡 TIP: Bookmark this URL on your mobile device!")
        print()
        print("🔒 SECURITY NOTE:")
        print("   - This works only on your local network (secure)")
        print("   - For internet access, use ngrok or deploy to cloud")
        print()
    else:
        print("❌ Could not determine IP address")
        print()
        print("Manual steps:")
        if system == "Windows":
            print("  1. Open Command Prompt")
            print("  2. Type: ipconfig")
            print("  3. Look for 'IPv4 Address'")
        elif system == "Darwin":  # macOS
            print("  1. Open Terminal")
            print("  2. Type: ifconfig | grep 'inet '")
            print("  3. Look for your local IP (usually 192.168.x.x)")
        else:  # Linux
            print("  1. Open Terminal")
            print("  2. Type: ip addr show")
            print("  3. Look for your local IP (usually 192.168.x.x)")
        print()
    
    print("=" * 60)
    print("📖 For more details, see: MOBILE_ACCESS_GUIDE.md")
    print("=" * 60)

if __name__ == "__main__":
    main()
