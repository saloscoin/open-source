#!/usr/bin/env python3
"""
SALOCOIN Setup Script
Sets up SALOCOIN CLI tools for your system.

Usage:
    python setup.py install    Install CLI tools to PATH (Windows/Linux/Mac)
    python setup.py check      Check if dependencies are installed
"""

import sys
import os
import shutil
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS = ['salocoin-wallet', 'salocoin-miner', 'salocoind']


def check_python():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required (found {version.major}.{version.minor})")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    required = ['ecdsa', 'requests']
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✓ {pkg}")
        except ImportError:
            print(f"❌ {pkg} - not installed")
            missing.append(pkg)
    
    return missing


def install_dependencies(missing):
    """Install missing dependencies."""
    if not missing:
        return True
    
    print(f"\nInstalling missing packages: {', '.join(missing)}")
    import subprocess
    result = subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing)
    return result.returncode == 0


def setup_windows():
    """Setup for Windows - add to PATH or create shortcuts."""
    print("\n📦 Windows Setup")
    print("═" * 50)
    
    # Option 1: Add to PATH
    print("\nOption 1: Add SALOCOIN folder to your PATH")
    print(f"  Add this to your PATH environment variable:")
    print(f"  {SCRIPT_DIR}")
    print("\n  Then you can run:")
    print("    salocoin-wallet.bat create my_wallet")
    print("    salocoin-miner.bat start")
    
    # Option 2: Create aliases in PowerShell profile
    print("\nOption 2: Add aliases to PowerShell profile")
    print("  Run in PowerShell as Admin:")
    print(f'    Add-Content $PROFILE "function salocoin-wallet {{ python \\"{SCRIPT_DIR}\\salocoin-wallet.py\\" @args }}"')
    print(f'    Add-Content $PROFILE "function salocoin-miner {{ python \\"{SCRIPT_DIR}\\salocoin-miner.py\\" @args }}"')
    print(f'    Add-Content $PROFILE "function salocoind {{ python \\"{SCRIPT_DIR}\\salocoind-cli.py\\" @args }}"')
    
    # Option 3: Direct Python usage
    print("\nOption 3: Run directly with Python")
    print(f"    python {SCRIPT_DIR}\\salocoin-wallet.py create my_wallet")
    print(f"    python {SCRIPT_DIR}\\salocoin-miner.py start")


def setup_unix():
    """Setup for Linux/Mac."""
    print("\n📦 Unix/Mac Setup")
    print("═" * 50)
    
    # Make scripts executable
    for tool in TOOLS:
        script = os.path.join(SCRIPT_DIR, tool)
        if os.path.exists(script):
            os.chmod(script, 0o755)
            print(f"✓ Made {tool} executable")
    
    # Symlink to /usr/local/bin
    print("\nTo install system-wide (requires sudo):")
    for tool in TOOLS:
        print(f"  sudo ln -sf {SCRIPT_DIR}/{tool} /usr/local/bin/{tool}")
    
    # Alternative: add to PATH
    print("\nOr add to your shell profile (~/.bashrc or ~/.zshrc):")
    print(f'  export PATH="$PATH:{SCRIPT_DIR}"')


def cmd_install(args):
    """Install CLI tools."""
    print("\n🚀 SALOCOIN CLI Setup")
    print("═" * 50)
    
    # Check Python
    if not check_python():
        return
    
    # Check dependencies
    print("\n📋 Checking dependencies...")
    missing = check_dependencies()
    
    if missing:
        response = input(f"\nInstall missing packages? [Y/n]: ").strip().lower()
        if response != 'n':
            if not install_dependencies(missing):
                print("❌ Failed to install dependencies")
                return
    
    # Platform-specific setup
    if platform.system() == 'Windows':
        setup_windows()
    else:
        setup_unix()
    
    print("\n✓ Setup complete!\n")


def cmd_check(args):
    """Check installation."""
    print("\n🔍 SALOCOIN Installation Check")
    print("═" * 50)
    
    # Check Python
    print("\n📋 Python:")
    check_python()
    
    # Check dependencies
    print("\n📋 Dependencies:")
    missing = check_dependencies()
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print(f"   Install with: pip install {' '.join(missing)}")
    else:
        print("\n✓ All dependencies installed!")
    
    # Check if tools exist
    print("\n📋 CLI Tools:")
    for tool in TOOLS:
        py_script = os.path.join(SCRIPT_DIR, f"{tool}.py")
        if tool == 'salocoind':
            py_script = os.path.join(SCRIPT_DIR, "salocoind-cli.py")
        
        if os.path.exists(py_script):
            print(f"✓ {tool}")
        else:
            print(f"❌ {tool} - not found")
    
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='SALOCOIN Setup')
    subparsers = parser.add_subparsers(dest='command')
    
    subparsers.add_parser('install', help='Install CLI tools')
    subparsers.add_parser('check', help='Check installation')
    
    args = parser.parse_args()
    
    if args.command == 'install':
        cmd_install(args)
    elif args.command == 'check':
        cmd_check(args)
    else:
        parser.print_help()
        print("\n💡 Quick start:")
        print("   python setup.py install")


if __name__ == '__main__':
    main()
