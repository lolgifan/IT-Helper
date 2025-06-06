# IT Helper

A comprehensive IT toolkit with multiple utilities for network analysis and system management.

## Features

### 🏠 Home Screen

- Clean, modern interface with utility buttons
- Easy navigation to all available tools
- Sidebar hidden on home screen for maximum visibility

### 📶 Wi-Fi Scanner

- Real-time wireless network scanning
- Signal strength analysis with visual bars
- Channel usage visualization (2.4GHz and 5GHz)
- Network details with encryption information
- Export functionality to CSV
- Configurable refresh rates

### 📊 Wi-Fi Charts

- Historical signal strength plotting
- Multi-network comparison
- Auto-refresh capabilities
- Interactive network selection
- Time-based analysis

### 💾 Disk Space Analyzer

- Drive space information display
- Recursive directory analysis
- Tree view with sortable columns
- Context menu operations (Open, Properties, Copy Path)
- File grouping options
- Progress tracking for large scans

## File Structure

```
IT Helper/
├── src/                    # Source code directory
│   ├── main.py             # Main application entry point
│   ├── wifi_scanner_module.py  # Wi-Fi scanning functionality
│   ├── wifi_charts_module.py   # Wi-Fi signal history charts
│   ├── disk_analyzer_module.py # Disk space analysis
│   ├── system_info_module.py   # System information utility
│   ├── network_scanner_module.py # Network scanning utility
│   ├── shared_components.py    # Common UI components
│   ├── wifi_utilities.py       # Wi-Fi scanning backend
│   ├── disk_utilities.py       # Disk analysis backend
│   └── logger.py               # Logging utility
├── build_tools/            # Build and compilation tools
│   ├── build.py            # Main build script
│   ├── build.bat           # Windows build batch file
│   ├── build_config.py     # Build configuration
│   ├── IT Helper.spec      # PyInstaller specification
│   └── BUILD_INSTRUCTIONS.md # Build documentation
├── dist/                   # Distribution directory (generated)
├── build.bat               # Quick build launcher
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Requirements

- Python 3.8 or higher
- PySide6
- matplotlib
- numpy
- Windows 10/11 (for WiFi scanning and disk analysis)

## Installation

1. Install Python dependencies:

```bash
pip install PySide6 matplotlib numpy
```

2. Run the application:

```bash
python src/main.py
```

Or build the standalone executable:

```bash
# Quick build (Windows)
build.bat

# Manual build
cd build_tools
python build.py
```

## Navigation

- **Home Screen**: No sidebar visible, clean interface with utility buttons
- **Utility Screens**: Sidebar visible with navigation options
- **🏠 Home Button**: Returns to home screen from any utility
- **Direct Navigation**: Click utility buttons in sidebar to switch between tools

## Key Improvements

- **Modular Architecture**: Each utility is in its own module for better organization
- **Shared Components**: Common UI elements are reused across modules
- **Clean Code Structure**: Removed unused code and comments
- **Better File Names**: More descriptive and readable file names
- **Consistent UI**: Dark theme throughout with consistent styling
- **Proper Documentation**: Clear code comments and structure
- **Organized File Structure**: Source code separated from build tools
- **Optimized Logging**: Configurable logging system replaces print statements
- **Performance Optimizations**: Lazy loading and efficient resource management

## Usage

### Wi-Fi Scanner

1. Navigate to Wi-Fi Scanner from home screen
2. Networks are automatically scanned in real-time
3. Click on column headers to sort networks
4. Double-click networks for detailed information
5. Use controls panel to adjust refresh rate or export data

### Wi-Fi Charts

1. Navigate to Wi-Fi Charts from home screen
2. Select networks from the list to chart their signal history
3. Charts update automatically when auto-refresh is enabled
4. Use manual refresh button to update data immediately

### Disk Analyzer

1. Navigate to Disk Space Analyzer from home screen
2. Select a drive or choose a custom folder
3. Click "Analyze Drive" to start analysis
4. View results in the tree structure
5. Right-click items for context menu options

## Technical Notes

- Uses Windows WlanAPI for Wi-Fi scanning
- Uses Windows API for disk analysis
- Threaded operations for non-blocking UI
- Matplotlib integration for charts and graphs
- Qt-based modern UI framework
