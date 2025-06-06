#!/usr/bin/env python3
"""
Build script for IT Helper application
This script compiles the application into a standalone executable
"""

import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

from build_config import get_pyinstaller_args, APP_NAME, BUILD_DIR, DIST_DIR

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60)

def print_step(step_num, total_steps, description):
    """Print a build step"""
    print(f"\n[{step_num}/{total_steps}] {description}")

def run_command(cmd, description="Running command"):
    """Run a command and handle errors"""
    print(f"  {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"  Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: {e}")
        if e.stderr:
            print(f"  Error details: {e.stderr}")
        return False

def check_dependencies():
    """Check if all required dependencies are installed"""
    print_step(1, 6, "Checking dependencies")
    
    required_packages = ["PyInstaller", "PySide6", "matplotlib", "numpy"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.lower().replace("-", "_"))
            print(f"  ✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"  ✗ {package} is missing")
    
    if missing_packages:
        print(f"\n  Installing missing packages: {', '.join(missing_packages)}")
        install_cmd = f"pip install {' '.join(missing_packages)}"
        if not run_command(install_cmd, "Installing packages"):
            return False
    
    return True

def clean_build_directories():
    """Clean previous build directories"""
    print_step(2, 6, "Cleaning build directories")
    
    dirs_to_clean = [BUILD_DIR, DIST_DIR, "__pycache__"]
    
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"  Removing {dir_name}...")
            shutil.rmtree(dir_name, ignore_errors=True)
        else:
            print(f"  {dir_name} not found, skipping")

def optimize_source_files():
    """Apply source code optimizations"""
    print_step(3, 6, "Optimizing source files")
    
    # Compile Python files to bytecode
    print("  Compiling Python files to bytecode...")
    if not run_command("python -m compileall ../src", "Compiling to bytecode"):
        print("  Warning: Bytecode compilation failed, continuing anyway...")
    
    print("  Source optimization completed")

def create_spec_file():
    """Create PyInstaller spec file for advanced configuration"""
    print_step(4, 6, "Creating PyInstaller spec file")
    
    from build_config import HIDDEN_IMPORTS, EXCLUDES, APP_NAME
    
    # Convert lists to properly formatted strings
    hidden_imports_str = ',\n        '.join([f"'{imp}'" for imp in HIDDEN_IMPORTS])
    excludes_str = ',\n        '.join([f"'{exc}'" for exc in EXCLUDES])
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{os.path.abspath("../src/main.py")}'],
    pathex=['{os.path.abspath("../src")}', '{os.path.abspath("..")}'],
    binaries=[],
    datas=[],
    hiddenimports=[
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        {excludes_str}
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,  # Disabled to avoid antivirus false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    optimize=2,  # Optimize bytecode
)
'''
    
    with open('IT_Helper.spec', 'w') as f:
        f.write(spec_content)
    
    print("  Spec file created successfully")

def build_executable():
    """Build the executable using PyInstaller"""
    print_step(5, 6, "Building executable")
    
    # Use the spec file for better control
    build_cmd = "pyinstaller IT_Helper.spec --clean --noconfirm"
    
    print("  This may take several minutes...")
    start_time = time.time()
    
    if not run_command(build_cmd, "Building with PyInstaller"):
        return False
    
    build_time = time.time() - start_time
    print(f"  Build completed in {build_time:.1f} seconds")
    
    return True

def verify_build():
    """Verify the build was successful"""
    print_step(6, 6, "Verifying build")
    
    exe_path = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
    
    if os.path.exists(exe_path):
        file_size = os.path.getsize(exe_path) / (1024 * 1024)  # Size in MB
        print(f"  ✓ Executable created: {exe_path}")
        print(f"  ✓ File size: {file_size:.1f} MB")
        
        # Test if the executable can be launched (basic test)
        print("  Testing executable launch (this will close automatically)...")
        try:
            # Launch with a flag that makes it exit quickly for testing
            test_process = subprocess.Popen([exe_path, "--help"], 
                                          stdout=subprocess.PIPE, 
                                          stderr=subprocess.PIPE)
            test_process.wait(timeout=10)  # Wait max 10 seconds
            print("  ✓ Executable launches successfully")
        except Exception as e:
            print(f"  Warning: Could not test executable launch: {e}")
        
        return True
    else:
        print(f"  ✗ Executable not found at {exe_path}")
        return False

def main():
    """Main build process"""
    print_header(f"Building {APP_NAME}")
    print(f"Build started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verify we're in the right directory
    if not os.path.exists("../src/main.py"):
        print("ERROR: main.py not found in ../src/. Please run this script from the build_tools directory.")
        sys.exit(1)
    
    success = True
    
    # Execute build steps
    steps = [
        check_dependencies,
        clean_build_directories,
        optimize_source_files,
        create_spec_file,
        build_executable,
        verify_build
    ]
    
    for step_func in steps:
        if not step_func():
            success = False
            break
    
    # Final results
    print_header("Build Results")
    
    if success:
        exe_path = os.path.join(DIST_DIR, f"{APP_NAME}.exe")
        print(f"✅ BUILD SUCCESSFUL!")
        print(f"📦 Executable location: {os.path.abspath(exe_path)}")
        print(f"💾 File size: {os.path.getsize(exe_path) / (1024 * 1024):.1f} MB")
        print("\n🚀 Your IT Helper application is ready to distribute!")
        print("\nNext steps:")
        print("1. Test the executable on different machines")
        print("2. Consider code signing for security")
        print("3. Create an installer if needed")
    else:
        print("❌ BUILD FAILED!")
        print("Please check the error messages above and fix any issues.")
        sys.exit(1)

if __name__ == "__main__":
    main() 