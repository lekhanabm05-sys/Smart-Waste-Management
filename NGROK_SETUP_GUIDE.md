# 🚀 ngrok Setup Guide - Complete Steps

## What You Need to Do on the ngrok Setup Page

You're currently on the ngrok setup page. Here's exactly what to do:

---

## Step 1: Download ngrok for Windows

1. On the setup page, look for the **"Download for Windows"** button
2. Click it to download `ngrok-v3-stable-windows-amd64.zip`
3. The file will download to your Downloads folder

---

## Step 2: Extract ngrok

1. Go to your Downloads folder
2. Find `ngrok-v3-stable-windows-amd64.zip`
3. Right-click → **Extract All**
4. Extract to: `C:\ngrok\`
5. You should now have `C:\ngrok\ngrok.exe`

---

## Step 3: Add Your Auth Token

On the ngrok setup page, you'll see a command like:

```bash
ngrok config add-authtoken YOUR_TOKEN_HERE
```

### To run this command:

1. Open **Command Prompt** (search for "cmd" in Windows)
2. Navigate to ngrok folder:
   ```bash
   cd C:\ngrok
   ```
3. Copy the FULL command from the ngrok page (it includes your unique token)
4. Paste it in Command Prompt and press Enter
5. You should see: "Authtoken saved to configuration file"

---

## Step 4: Start Your Flask App

1. Open a NEW Command Prompt window
2. Navigate to your project folder:
   ```bash
   cd path\to\your\project
   ```
3. Start the Flask app:
   ```bash
   py app.py
   ```
4. Wait until you see: "Running on http://0.0.0.0:5000"
5. **KEEP THIS WINDOW OPEN!**

---

## Step 5: Start ngrok

1. Open ANOTHER Command Prompt window
2. Navigate to ngrok:
   ```bash
   cd C:\ngrok
   ```
3. Start ngrok tunnel:
   ```bash
   ngrok http 5000
   ```
4. You'll see output like this:

```
Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        United States (us)
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:5000
```

5. **COPY THE HTTPS URL** (e.g., `https://abc123.ngrok-free.app`)
6. **KEEP THIS WINDOW OPEN TOO!**

---

## Step 6: Use PWA Builder

1. Go to: https://www.pwabuilder.com/
2. Paste your ngrok HTTPS URL in the input box
3. Click **"Start"**
4. Wait for PWA Builder to analyze your app
5. Click **"Package For Stores"**
6. Select **"Android"**
7. Click **"Generate"**
8. Download the APK file
9. Transfer to your Android phone and install!

---

## ⚠️ Important Notes

### Keep These Running:
- ✅ Flask app (py app.py)
- ✅ ngrok tunnel (ngrok http 5000)

### ngrok URL Changes:
- Free ngrok URLs change every time you restart
- You'll need to use PWA Builder again if you restart ngrok
- Consider upgrading to ngrok paid plan for permanent URL

### Alternative: Direct PWA Install (Easier!)

Instead of creating an APK, you can install directly:

1. Start Flask app: `py app.py`
2. On your phone, open Chrome
3. Go to: `http://172.17.187.207:5000` (your local IP)
4. Click the "Install App" button that appears
5. Done! No ngrok or PWA Builder needed!

---

## 🆘 Troubleshooting

### "ngrok: command not found"
- Make sure you're in `C:\ngrok` folder
- Or add ngrok to PATH environment variable

### "Failed to complete tunnel connection"
- Check your internet connection
- Make sure auth token was added correctly
- Try restarting ngrok

### PWA Builder shows errors
- Make sure Flask app is running
- Verify ngrok URL is accessible in browser
- Check that icons were generated (`py generate_icons.py`)

### Can't access on phone
- Make sure phone and computer are on same WiFi
- Check Windows Firewall isn't blocking port 5000
- Try using ngrok URL instead of local IP

---

## 📱 Which Method Should You Use?

### Use ngrok + PWA Builder if:
- ✅ You want a traditional APK file
- ✅ You want to distribute to others
- ✅ You want it on Google Play Store

### Use Direct PWA Install if:
- ✅ Just for personal use
- ✅ Want it working NOW (faster)
- ✅ Don't want to deal with ngrok
- ✅ Phone and computer on same network

---

## 🎯 Quick Commands Summary

```bash
# 1. Extract ngrok to C:\ngrok

# 2. Add auth token (from ngrok page)
cd C:\ngrok
ngrok config add-authtoken YOUR_TOKEN

# 3. Start Flask (Terminal 1)
cd your\project\folder
py app.py

# 4. Start ngrok (Terminal 2)
cd C:\ngrok
ngrok http 5000

# 5. Copy the HTTPS URL and use in PWA Builder
```

---

## ✅ Success Checklist

- [ ] Downloaded ngrok
- [ ] Extracted to C:\ngrok
- [ ] Added auth token
- [ ] Flask app running
- [ ] ngrok tunnel running
- [ ] Copied HTTPS URL
- [ ] Used PWA Builder
- [ ] Downloaded APK
- [ ] Installed on phone

---

**Need help? Let me know which step you're stuck on!**
