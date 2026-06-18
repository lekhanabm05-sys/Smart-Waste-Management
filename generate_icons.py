#!/usr/bin/env python3
"""
Generate PWA icons for Smart Waste Management App
"""
import os
from PIL import Image, ImageDraw, ImageFont

def create_icon(size, output_path):
    """Create a simple icon with recycling symbol"""
    # Create image with green gradient background
    img = Image.new('RGB', (size, size), color='#66BB6A')
    draw = ImageDraw.Draw(img)
    
    # Draw a circle background
    margin = size // 10
    draw.ellipse([margin, margin, size-margin, size-margin], fill='#81C784')
    
    # Draw recycling symbol (simplified)
    try:
        # Try to use a large font
        font_size = size // 2
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Draw the recycling symbol ♻
    text = "♻"
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    draw.text((x, y), text, fill='white', font=font)
    
    # Save the icon
    img.save(output_path, 'PNG')
    print(f"✅ Created: {output_path}")

def main():
    """Generate all required icon sizes"""
    print("=" * 60)
    print("🎨 Generating PWA Icons for Smart Waste Management")
    print("=" * 60)
    print()
    
    # Create icons directory if it doesn't exist
    icons_dir = 'static/icons'
    os.makedirs(icons_dir, exist_ok=True)
    
    # Icon sizes required for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    
    for size in sizes:
        output_path = os.path.join(icons_dir, f'icon-{size}x{size}.png')
        create_icon(size, output_path)
    
    print()
    print("=" * 60)
    print("✅ All icons generated successfully!")
    print("=" * 60)
    print()
    print("📱 Your app is now ready to be installed!")
    print()
    print("Next steps:")
    print("1. Start the app: py app.py")
    print("2. Open in browser: http://localhost:5000")
    print("3. Look for 'Install App' button in bottom-right")
    print("4. Click to install as a native app!")
    print()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Note: If PIL/Pillow is not installed, run:")
        print("  pip install Pillow")
