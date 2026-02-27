"""
DigiCal Web Portal Launcher
Simple script to start the web server
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting DigiCal Web Portal...")
print("If you encounter permission errors, try running as Administrator")
print()

try:
    import api
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("\nMake sure you have installed the required dependencies:")
    print("  pip install -r requirements-web.txt")
    input("\nPress Enter to exit...")
    sys.exit(1)
except Exception as e:
    print(f"Error starting server: {e}")
    print("\nTroubleshooting:")
    print("1. Check if another application is using the port")
    print("2. Try running as Administrator")
    print("3. Check Windows Firewall settings")
    input("\nPress Enter to exit...")
    sys.exit(1)
