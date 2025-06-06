"""
Build configuration for IT Helper application
This file contains all the settings needed for PyInstaller compilation
"""

import os
import sys

# Application metadata
APP_NAME = "IT Helper"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Comprehensive IT toolkit with disk analyzer and WiFi scanner"
APP_AUTHOR = "IT Helper Team"

# Build settings
MAIN_SCRIPT = "../src/main.py"
ICON_FILE = "icon.ico"  # Optional: add an icon file
BUILD_DIR = "../build"
DIST_DIR = "../dist"

# PyInstaller options
PYINSTALLER_OPTIONS = [
    "--name", APP_NAME,
    "--onefile",  # Create single executable
    "--windowed",  # No console window (for GUI apps)
    "--optimize", "2",  # Optimize bytecode
    "--strip",  # Strip debug symbols
    "--noupx",  # Don't use UPX compression (can cause antivirus issues)
]

# Hidden imports (modules that PyInstaller might miss)
HIDDEN_IMPORTS = [
    "PySide6.QtCore",
    "PySide6.QtWidgets", 
    "PySide6.QtGui",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.figure",
    "numpy",
    "ctypes.wintypes",
    "subprocess",
    "threading",
    "queue",
    "json",
    "sqlite3",
    "uuid",
    "multiprocessing",
    "pickle",
    "concurrent.futures",
    "time",
    "datetime",
    "os",
    "sys",
    "argparse",
]

# Data files to include
DATA_FILES = [
    # Add any data files here if needed
    # ("source_path", "dest_path_in_exe"),
]

# Exclude unnecessary modules to reduce size (be careful not to exclude needed modules)
EXCLUDES = [
    "tkinter",
    "unittest", 
    "test",
    "pydoc",
    "doctest",
    # "pickle",  # REMOVED - needed by multiprocessing
    # "email",   # REMOVED - might be needed
    # "http",    # REMOVED - might be needed
    # "urllib",  # REMOVED - might be needed
    "xml",
    "html",
    "distutils",
    "setuptools",
    "pip",
]

# Collect all options
def get_pyinstaller_args():
    """Get complete PyInstaller arguments"""
    args = PYINSTALLER_OPTIONS.copy()
    
    # Add hidden imports
    for module in HIDDEN_IMPORTS:
        args.extend(["--hidden-import", module])
    
    # Add excludes
    for module in EXCLUDES:
        args.extend(["--exclude-module", module])
    
    # Add data files
    for src, dst in DATA_FILES:
        args.extend(["--add-data", f"{src};{dst}"])
    
    # Add build directories
    args.extend(["--distpath", DIST_DIR])
    args.extend(["--workpath", BUILD_DIR])
    
    # Add icon if exists
    if os.path.exists(ICON_FILE):
        args.extend(["--icon", ICON_FILE])
    
    # Add main script
    args.append(MAIN_SCRIPT)
    
    return args

# Runtime optimization settings
RUNTIME_OPTIMIZATIONS = {
    "disable_debug": True,
    "optimize_imports": True,
    "precompile_ui": True,
    "minimize_memory": True,
} 