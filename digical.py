"""
DigiCal Business Calculator
Main application entry point
"""
import tkinter as tk
import subprocess
import sys
import os
import socket
import atexit
import config
from gui import DigiCalGUI

# Global variable to track API process
api_process = None

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
        s.close()
    except Exception:
        IP = '127.0.0.1'
    return IP

def start_api_server():
    """Start the Flask API server in a separate process"""
    global api_process
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_path = os.path.join(script_dir, 'api.py')
        
        # Start api.py as a subprocess
        api_process = subprocess.Popen(
            [sys.executable, api_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )
        ip = get_local_ip()
        print(f"API server started (PID: {api_process.pid})")
        print("="*60)
        print("📱 DIGICAL WEB PORTAL IS LIVE 💻")
        print(f"Access on this PC:    http://localhost:{config.WEB_PORT}")
        print(f"Access on your Phone: http://{ip}:{config.WEB_PORT}")
        print("="*60)
    except Exception as e:
        print(f"Failed to start API server: {e}")

def cleanup_api_server():
    """Terminate the API server when the main application exits"""
    global api_process
    if api_process:
        try:
            api_process.terminate()
            api_process.wait(timeout=5)
            print("API server stopped")
        except Exception as e:
            print(f"Error stopping API server: {e}")

def main():
    # Start the API server
    start_api_server()
    
    # Register cleanup function to run on exit
    atexit.register(cleanup_api_server)
    
    # Start the GUI
    root = tk.Tk()
    app = DigiCalGUI(root)
    root.mainloop()
    
    # Cleanup when GUI closes
    cleanup_api_server()

if __name__ == "__main__":
    main()
