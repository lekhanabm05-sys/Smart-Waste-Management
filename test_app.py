try:
    from app import create_app
    app = create_app()
    print("✅ App created successfully!")
except ImportError as e:
    print(f"❌ Import Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
