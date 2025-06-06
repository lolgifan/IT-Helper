# 🛠️ IT Helper

<div align="center">

**A comprehensive IT toolkit with multiple utilities for network analysis and system management**

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue?logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-green?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Build](https://img.shields.io/badge/Build-Passing-brightgreen)
![Version](https://img.shields.io/badge/Version-1.1.0-blue)

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Usage](#-usage)
- [Build from Source](#-build-from-source)
- [Technical Details](#-technical-details)
- [Project Structure](#-project-structure)
- [Support](#-support)

---

## ✨ Features

### 🏠 **Modern Home Screen**

- Clean, intuitive interface with utility buttons
- **Collapsible Sidebar Navigation**: Hover-to-expand sidebar with smooth animations
- Easy navigation to all available tools
- Responsive layout with professional dark theme

### 📶 **Wi-Fi Scanner**

- **Real-time Network Discovery**: Continuously scans for available wireless networks
- **Signal Analysis**: Visual signal strength bars with detailed metrics
- **Channel Visualization**: 2.4GHz and 5GHz channel usage analysis
- **Security Information**: Encryption type and security details
- **Export Capabilities**: Save results to CSV format
- **Customizable Refresh**: Adjustable scan intervals

### 📊 **Wi-Fi Signal Charts**

- **Historical Tracking**: Plot signal strength over time
- **Multi-Network Comparison**: Compare multiple networks simultaneously
- **Interactive Selection**: Click to select/deselect networks for charting
- **Auto-Refresh**: Continuous monitoring with configurable intervals
- **Professional Graphs**: Matplotlib-powered visualization

### 💾 **Disk Space Analyzer**

- **Drive Analysis**: Complete storage space breakdown
- **Directory Tree**: Hierarchical view of folder structures
- **Sortable Results**: Sort by size, name, or file count
- **Context Operations**: Right-click for file operations
- **Progress Tracking**: Real-time scan progress for large directories
- **Performance Optimized**: Efficient scanning algorithms

### 🖥️ **System Information**

- **Hardware Details**: CPU, RAM, GPU specifications
- **Operating System**: Detailed OS information
- **Network Configuration**: IP addresses and network settings
- **Storage Overview**: All connected drives information

### 🌐 **Network Scanner**

- **Network Discovery**: Scan local network for active devices
- **Device Information**: IP addresses, MAC addresses, hostnames
- **Port Scanning**: Identify open ports and services
- **Network Mapping**: Visual representation of network topology

### 🔧 **SMART Disk Health Monitor**

- **Health Analysis**: Monitor disk health using SMART attributes
- **Temperature Monitoring**: Real-time disk temperature tracking
- **Predictive Analysis**: Early warning for potential disk failures
- **Administrator Mode**: Requires elevated privileges for full functionality
- **Professional Reports**: Detailed health status and recommendations

---

## 🚀 Installation

### Option 1: Download Executable (Recommended)

1. Download the latest release from the [Releases](../../releases) page
2. Run `IT Helper.exe` - no installation required!
3. The application is portable and self-contained

### Option 2: Run from Source

**Prerequisites:**

- Python 3.8 or higher
- Windows 10/11 (required for Wi-Fi and system analysis features)

**Installation Steps:**

```bash
# Clone the repository
git clone https://github.com/yourusername/it-helper.git
cd it-helper

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

---

## 📖 Usage

### Getting Started

1. Launch IT Helper
2. Choose a utility from the home screen
3. **Collapsible Sidebar**: Hover over the sidebar to expand and see full utility names
4. Use the sidebar to navigate between tools
5. Click the 🏠 Home button to return to the main screen

### Wi-Fi Scanner

```
1. Navigate to Wi-Fi Scanner
2. View real-time network list with signal strengths
3. Click column headers to sort results
4. Double-click networks for detailed information
5. Export results using the "Export to CSV" button
```

### Wi-Fi Charts

```
1. Open Wi-Fi Charts utility
2. Select networks from the list to monitor
3. Enable auto-refresh for continuous monitoring
4. Analyze signal patterns over time
```

### Disk Analyzer

```
1. Select Disk Space Analyzer
2. Choose a drive or browse to a specific folder
3. Click "Analyze Drive" to start scanning
4. Navigate the tree view to explore folder sizes
5. Use right-click context menu for file operations
```

### SMART Disk Health

```
1. Navigate to SMART Disk Health utility
2. Grant administrator privileges when prompted (required for full functionality)
3. View real-time disk health status and temperature
4. Monitor SMART attributes for all connected drives
5. Review health recommendations and warnings
```

### Collapsible Sidebar

```
1. The sidebar starts in collapsed mode, showing only emojis
2. Hover over the sidebar to smoothly expand and see full utility names
3. Click any utility button to navigate
4. The sidebar automatically collapses when you move the mouse away
5. Enjoy the space-efficient, modern navigation experience
```

---

## 🔧 Build from Source

### Quick Build (Windows)

```bash
# Using the build script
build.bat
```

### Manual Build

```bash
# Navigate to build tools
cd build_tools

# Run the build script
python build.py

# Or use PyInstaller directly
pyinstaller --onefile --windowed --name "IT Helper" --icon "app_icon.png" --hidden-import multiprocessing src/main.py
```

**Build Output:**

- Executable: `dist/IT Helper.exe`
- Size: ~65MB (includes all dependencies)
- Fully portable, no Python installation required

---

## 🔍 Technical Details

### Architecture

- **Framework**: PySide6 (Qt6) for modern UI
- **Charts**: Matplotlib for professional visualizations
- **Threading**: Multi-threaded for responsive UI
- **APIs**: Windows WlanAPI for Wi-Fi, WinAPI for system info
- **UI Features**: Collapsible sidebar with smooth animations, lazy loading for optimal performance

### System Requirements

- **OS**: Windows 10/11 (64-bit)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 100MB free space
- **Network**: Wi-Fi adapter for wireless scanning features

### Dependencies

```
PySide6>=6.0.0      # Modern Qt6 framework
matplotlib>=3.5.0   # Professional charting
numpy>=1.21.0       # Numerical computing
psutil>=5.8.0       # System information
```

---

## 📁 Project Structure

```
IT Helper/
├── 📂 src/                     # Source code
│   ├── 🐍 main.py             # Application entry point (with collapsible sidebar)
│   ├── 📶 wifi_scanner_module.py    # Wi-Fi network scanning
│   ├── 📊 wifi_charts_module.py     # Wi-Fi signal visualization
│   ├── 💾 disk_analyzer_module.py   # Disk space analysis
│   ├── 🖥️ system_info_module.py    # System information display
│   ├── 🌐 network_scanner_module.py # Network device discovery
│   ├── 🔧 smart_test_module.py      # SMART disk health monitoring
│   ├── 🎨 shared_components.py      # Reusable UI components
│   ├── 📡 wifi_utilities.py         # Wi-Fi helper functions
│   ├── 💿 disk_utilities.py         # Disk analysis utilities
│   └── 📝 logger.py                 # Application logging
├── 📂 build_tools/            # Build system
│   ├── 🔧 build.py            # Main build script
│   ├── ⚙️ build_config.py    # Build configuration
│   ├── 🖼️ app_icon.png       # Application icon
│   ├── 🚀 build.bat          # Windows build script
│   ├── ⚙️ IT Helper.spec     # PyInstaller spec file
│   └── 📋 BUILD_INSTRUCTIONS.md # Build documentation
├── 📂 dist/                   # Built executable output
├── 📂 build/                  # Build artifacts
├── 📋 requirements.txt        # Python dependencies
├── 🚀 build.bat              # Quick build launcher
├── 📋 SMART_FEATURE_README.md # SMART feature documentation
├── 📋 OPTIMIZATION_SUMMARY.md # Performance optimizations
└── 📖 README.md              # This file
```

---

## 🆘 Support

### 🐛 Found a Bug?

Please [open an issue](../../issues) with:

- Detailed description
- Steps to reproduce
- System information
- Screenshots (if applicable)

### 💡 Feature Request?

We'd love to hear your ideas! [Create a feature request](../../issues) and describe:

- What you'd like to see
- Why it would be useful
- How it should work
