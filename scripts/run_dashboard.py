#!/usr/bin/env python3
"""
Dashboard Runner Script

Simple script to launch the Google Account Creator dashboard
with proper configuration and error handling.
"""

import sys
import subprocess
import os
from pathlib import Path
import argparse

def check_requirements():
    """Check if required packages are installed"""
    required_packages = [
        'streamlit',
        'pandas', 
        'plotly',
        'numpy'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Please install them using:")
        print(f"pip install -r dashboard/requirements.txt")
        return False
    
    return True

def run_dashboard(host="localhost", port=8501, debug=False):
    """Run the Streamlit dashboard"""
    
    # Get project root and dashboard path
    project_root = Path(__file__).parent.parent
    dashboard_path = project_root / "dashboard" / "main.py"
    
    if not dashboard_path.exists():
        print(f"Dashboard file not found: {dashboard_path}")
        return False
    
    # Check requirements
    if not check_requirements():
        return False
    
    # Prepare streamlit command
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(dashboard_path),
        "--server.address", host,
        "--server.port", str(port),
        "--server.headless", "true" if not debug else "false",
        "--theme.primaryColor", "#1f77b4",
        "--theme.backgroundColor", "#ffffff",
        "--theme.secondaryBackgroundColor", "#f0f2f6"
    ]
    
    print(f"Starting Google Account Creator Dashboard...")
    print(f"URL: http://{host}:{port}")
    print(f"Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        # Change to project root directory
        os.chdir(project_root)
        
        # Run streamlit
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\nDashboard stopped by user")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running dashboard: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run Google Account Creator Dashboard")
    parser.add_argument("--host", default="localhost", help="Host address (default: localhost)")
    parser.add_argument("--port", type=int, default=8501, help="Port number (default: 8501)")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    
    args = parser.parse_args()
    
    success = run_dashboard(args.host, args.port, args.debug)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 