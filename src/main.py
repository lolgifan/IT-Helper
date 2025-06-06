import sys
import os
import argparse
import subprocess
import ctypes
from PySide6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame, QGridLayout, QSpacerItem, QSizePolicy, QMessageBox
)
from PySide6.QtGui import QFont, QPalette, QColor

# Import utility modules
from wifi_scanner_module import WifiScannerWidget
from wifi_charts_module import WifiChartsWidget  
from disk_analyzer_module import DiskAnalyzerWidget
from system_info_module import SystemInfoWidget
from network_scanner_module import NetworkScannerWidget
from smart_test_module import SMARTTestWidget
from logger import debug, info, warning, error


class CollapsibleSidebar(QFrame):
    """Collapsible sidebar that shows only emojis when collapsed and full names when expanded"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_app = parent
        self.collapsed_width = 70
        self.expanded_width = 250
        self.is_expanded = False
        
        self.setFixedWidth(self.collapsed_width)
        self.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-right: 1px solid #3d3d3d;
            }
        """)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 10, 5, 10)
        self.layout.setSpacing(5)
        
        self.buttons = []
        # Create smoother animation by animating both min and max width
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(350)  # Longer duration for smoother animation
        self.animation.setEasingCurve(QEasingCurve.InOutQuart)  # Smoother easing curve
        
        self.max_width_animation = QPropertyAnimation(self, b"maximumWidth")
        self.max_width_animation.setDuration(350)
        self.max_width_animation.setEasingCurve(QEasingCurve.InOutQuart)
        
        self._create_buttons()
        
    def _create_buttons(self):
        """Create sidebar buttons"""
        # Home button
        home_btn = self._create_sidebar_button("🏠", "Home", self.parent_app._show_home if self.parent_app else None)
        home_btn.setStyleSheet("""
            QPushButton {
                text-align: center;
                padding: 8px;
                background-color: #1e1e1e;
                border: 1px solid #2d2d2d;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        self.layout.addWidget(home_btn)
        self.buttons.append(home_btn)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("color: #3d3d3d; margin: 5px 0px;")
        self.layout.addWidget(separator)
        
        # Utility buttons
        utilities = [
            ("📶", "Wi-Fi Scanner", self.parent_app._show_wifi_scanner if self.parent_app else None),
            ("📊", "Wi-Fi Charts", self.parent_app._show_wifi_charts if self.parent_app else None),
            ("💾", "Disk Space Analyzer", self.parent_app._show_disk_analyzer if self.parent_app else None),
            ("🖥", "System Info", self.parent_app._show_system_info if self.parent_app else None),
            ("🌐", "Network Scanner", self.parent_app._show_network_scanner if self.parent_app else None),
            ("🔧", "SMART Disk Health", self.parent_app._show_smart_test if self.parent_app else None)
        ]
        
        for emoji, title, callback in utilities:
            btn = self._create_sidebar_button(emoji, title, callback)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: center;
                    padding: 8px;
                    background-color: transparent;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                }
            """)
            self.layout.addWidget(btn)
            self.buttons.append(btn)
            
        # Add spacer to push buttons to top
        self.layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
    def _create_sidebar_button(self, emoji, title, callback):
        """Create a sidebar button with emoji and title"""
        btn = QPushButton(emoji)
        btn.setFont(QFont("Segoe UI Emoji", 20))  # Even bigger emoji font for better visibility
        btn.setFixedHeight(50)  # Slightly taller buttons to accommodate larger emojis
        btn.emoji = emoji
        btn.title = title
        if callback:
            btn.clicked.connect(callback)
        return btn
        
    def enterEvent(self, event):
        """Handle mouse enter event - expand sidebar"""
        self._expand()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """Handle mouse leave event - collapse sidebar"""
        self._collapse()
        super().leaveEvent(event)
        
    def _expand(self):
        """Expand the sidebar to show full names"""
        if not self.is_expanded:
            self.is_expanded = True
            # Animate both minimum and maximum width for smoother animation
            self.animation.setStartValue(self.collapsed_width)
            self.animation.setEndValue(self.expanded_width)
            self.max_width_animation.setStartValue(self.collapsed_width)
            self.max_width_animation.setEndValue(self.expanded_width)
            
            self.animation.start()
            self.max_width_animation.start()
            
            # Update button text to show full names
            for btn in self.buttons:
                if hasattr(btn, 'emoji') and hasattr(btn, 'title'):
                    btn.setText(f"{btn.emoji} {btn.title}")
                    btn.setStyleSheet(btn.styleSheet().replace("text-align: center", "text-align: left") + 
                                    " padding-left: 15px;")
                    
    def _collapse(self):
        """Collapse the sidebar to show only emojis"""
        if self.is_expanded:
            self.is_expanded = False
            # Animate both minimum and maximum width for smoother animation
            self.animation.setStartValue(self.expanded_width)
            self.animation.setEndValue(self.collapsed_width)
            self.max_width_animation.setStartValue(self.expanded_width)
            self.max_width_animation.setEndValue(self.collapsed_width)
            
            self.animation.start()
            self.max_width_animation.start()
            
            # Update button text to show only emojis
            for btn in self.buttons:
                if hasattr(btn, 'emoji'):
                    btn.setText(btn.emoji)
                    btn.setStyleSheet(btn.styleSheet().replace("text-align: left", "text-align: center").replace(" padding-left: 15px;", ""))


class ITHelperApp(QMainWindow):
    """Main IT Helper application with home screen and utilities"""
    
    def __init__(self, args=None):
        super().__init__()
        
        # Check if running as administrator
        admin_status = self._is_running_as_admin()
        title = "IT Helper"
        if admin_status:
            title += " (Administrator)"
            
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 1400, 900)
        
        # Store command line arguments for auto-navigation
        self.args = args
        
        # Track current screen for WiFi scanning management
        self.current_screen = None
        
        # Lazy loading - create widgets only when needed
        self.wifi_scanner_widget = None
        self.wifi_charts_widget = None
        self.disk_analyzer_widget = None
        self.system_info_widget = None
        self.network_scanner_widget = None
        self.smart_test_widget = None
        
        # Track screens to avoid recreating them
        self.wifi_scanner_screen = None
        self.wifi_charts_screen = None
        self.disk_analyzer_screen = None
        self.system_info_screen = None
        self.network_scanner_screen = None
        self.smart_test_screen = None
        
        # Initialize the UI
        self._init_style()
        self._init_ui()
        
        # Handle auto-navigation after UI is ready
        if self.args:
            QTimer.singleShot(100, self._handle_auto_navigation)
        
    def _init_style(self):
        """Set the application's dark theme styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: white;
            }
            QWidget {
                background-color: #1a1a1a;
                color: white;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                padding: 15px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border: 1px solid #4d4d4d;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
            }
        """)
        
    def _init_ui(self):
        """Initialize the main UI with stacked widget for navigation"""
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        
        # Create main layout
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create stacked widget for different screens
        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)
        
        # Create home screen
        self._create_home_screen()
        
        # Create utility screens  
        self._create_utility_screens()
        
        # Show home screen by default
        self._show_home()
        
    def _create_home_screen(self):
        """Create the main home screen with utility buttons"""
        self.home_screen = QWidget()
        home_layout = QVBoxLayout(self.home_screen)
        home_layout.setContentsMargins(50, 50, 50, 50)
        home_layout.setSpacing(30)
        
        # Title
        title_label = QLabel("IT Helper")
        title_label.setFont(QFont("Arial", 36, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 20px;")
        home_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Your comprehensive IT toolkit")
        subtitle_label.setFont(QFont("Arial", 16))
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #cccccc; margin-bottom: 40px;")
        home_layout.addWidget(subtitle_label)
        
        # Utility buttons grid - 3 columns layout
        buttons_frame = QFrame()
        buttons_layout = QGridLayout(buttons_frame)
        buttons_layout.setSpacing(15)  # Reduced spacing for tighter layout
        
        # WiFi Scanner button
        wifi_scanner_btn = self._create_utility_button(
            "📶", "Wi-Fi Scanner", 
            "Scan and analyze wireless networks in your area"
        )
        wifi_scanner_btn.clicked.connect(self._show_wifi_scanner)
        buttons_layout.addWidget(wifi_scanner_btn, 0, 0)
        
        # WiFi Charts button  
        wifi_charts_btn = self._create_utility_button(
            "📊", "Wi-Fi Charts",
            "Visualize Wi-Fi signal strength over time"
        )
        wifi_charts_btn.clicked.connect(self._show_wifi_charts)
        buttons_layout.addWidget(wifi_charts_btn, 0, 1)
        
        # Disk Analyzer button
        disk_analyzer_btn = self._create_utility_button(
            "💾", "Disk Space Analyzer",
            "Analyze disk usage and find large files"
        )
        disk_analyzer_btn.clicked.connect(self._show_disk_analyzer)
        buttons_layout.addWidget(disk_analyzer_btn, 0, 2)
        
        # System Info button
        system_info_btn = self._create_utility_button(
            "🖥", "System Info",
            "Get system information and hardware details"
        )
        system_info_btn.clicked.connect(self._show_system_info)
        buttons_layout.addWidget(system_info_btn, 1, 0)
        
        # Network Scanner button
        network_scanner_btn = self._create_utility_button(
            "🌐", "Network Scanner",
            "Discover devices on your network with port scanning"
        )
        network_scanner_btn.clicked.connect(self._show_network_scanner)
        buttons_layout.addWidget(network_scanner_btn, 1, 1)
        
        # SMART Disk Health Monitor button
        smart_test_btn = self._create_utility_button(
            "🔧", "SMART Disk Health",
            "Monitor disk health with SMART attributes (Requires Admin)"
        )
        smart_test_btn.clicked.connect(self._show_smart_test)
        buttons_layout.addWidget(smart_test_btn, 1, 2)
        
        home_layout.addWidget(buttons_frame)
        
        # Add bottom spacer
        home_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        self.stacked_widget.addWidget(self.home_screen)
        
    def _create_utility_button(self, emoji, title, description):
        """Create a styled utility button"""
        button = QPushButton()
        button.setFixedSize(250, 160)  # Reduced from 300x200 to fit 3 in a row
        button.setCursor(Qt.PointingHandCursor)
        
        # Create button layout
        button_layout = QVBoxLayout(button)
        button_layout.setSpacing(8)  # Reduced spacing
        
        # Emoji icon
        icon_label = QLabel(emoji)
        icon_label.setFont(QFont("Segoe UI Emoji", 36))  # Reduced from 48
        icon_label.setAlignment(Qt.AlignCenter)
        button_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Arial", 14, QFont.Bold))  # Reduced from 16
        title_label.setAlignment(Qt.AlignCenter)
        button_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 9))  # Reduced from 10
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #cccccc;")
        button_layout.addWidget(desc_label)
        
        return button
        
    def _create_utility_screens(self):
        """Create the utility screens with navigation - using lazy loading"""
        # Don't create any widgets here - they will be created when first needed
        # This ensures no WiFi scanning starts until user navigates to those screens
        pass
        
    def _create_utility_screen(self, utility_widget, emoji, title):
        """Create a utility screen with sidebar navigation"""
        screen = QWidget()
        screen_layout = QHBoxLayout(screen)
        screen_layout.setContentsMargins(0, 0, 0, 0)
        screen_layout.setSpacing(0)
        
        # Create collapsible sidebar
        sidebar = CollapsibleSidebar(self)
        screen_layout.addWidget(sidebar)
        
        # Add utility widget
        screen_layout.addWidget(utility_widget, stretch=1)
        
        return screen
        

        
    def _show_home(self):
        """Navigate to home screen"""
        self._stop_wifi_scanning()
        self.current_screen = "home"
        self.stacked_widget.setCurrentWidget(self.home_screen)
        
    def _show_wifi_scanner(self):
        """Navigate to WiFi Scanner utility"""
        self._stop_wifi_scanning()
        self.current_screen = "wifi_scanner"
        
        # Lazy loading - create widget only when first needed
        if self.wifi_scanner_widget is None:
            debug("Creating WiFi Scanner widget for first time...", "MainApp")
            self.wifi_scanner_widget = WifiScannerWidget()
            self.wifi_scanner_screen = self._create_utility_screen(
                self.wifi_scanner_widget, "📶", "Wi-Fi Scanner"
            )
            self.stacked_widget.addWidget(self.wifi_scanner_screen)
        
        self.stacked_widget.setCurrentWidget(self.wifi_scanner_screen)
        
        # Start scanning only after navigating to the screen
        if self.wifi_scanner_widget:
            self.wifi_scanner_widget.start_scanning()
        
    def _show_wifi_charts(self):
        """Navigate to WiFi Charts utility"""  
        self._stop_wifi_scanning()
        self.current_screen = "wifi_charts"
        
        # Lazy loading - create widget only when first needed
        if self.wifi_charts_widget is None:
            debug("Creating WiFi Charts widget for first time...", "MainApp")
            self.wifi_charts_widget = WifiChartsWidget()
            self.wifi_charts_screen = self._create_utility_screen(
                self.wifi_charts_widget, "📊", "Wi-Fi Charts"
            )
            self.stacked_widget.addWidget(self.wifi_charts_screen)
        
        self.stacked_widget.setCurrentWidget(self.wifi_charts_screen)
        
        # Start data collection only after navigating to the screen
        if self.wifi_charts_widget:
            self.wifi_charts_widget.start_data_collection()
        
    def _show_disk_analyzer(self):
        """Navigate to Disk Analyzer utility"""
        self._stop_wifi_scanning()
        self.current_screen = "disk_analyzer"
        
        # Lazy loading - create widget only when first needed
        if self.disk_analyzer_widget is None:
            debug("Creating Disk Analyzer widget for first time...", "MainApp")
            self.disk_analyzer_widget = DiskAnalyzerWidget()
            self.disk_analyzer_screen = self._create_utility_screen(
                self.disk_analyzer_widget, "💾", "Disk Space Analyzer"
            )
            self.stacked_widget.addWidget(self.disk_analyzer_screen)
        
        self.stacked_widget.setCurrentWidget(self.disk_analyzer_screen)
        
    def _show_system_info(self):
        """Navigate to System Info utility"""
        self._stop_wifi_scanning()
        self.current_screen = "system_info"
        
        # Lazy loading - create widget only when first needed
        if self.system_info_widget is None:
            debug("Creating System Info widget for first time...", "MainApp")
            self.system_info_widget = SystemInfoWidget()
            self.system_info_screen = self._create_utility_screen(
                self.system_info_widget, "🖥", "System Info"
            )
            self.stacked_widget.addWidget(self.system_info_screen)
        
        self.stacked_widget.setCurrentWidget(self.system_info_screen)
        
    def _show_network_scanner(self):
        """Navigate to Network Scanner utility"""
        self._stop_wifi_scanning()
        self.current_screen = "network_scanner"
        
        # Lazy loading - create widget only when first needed
        if self.network_scanner_widget is None:
            debug("Creating Network Scanner widget for first time...", "MainApp")
            self.network_scanner_widget = NetworkScannerWidget()
            self.network_scanner_screen = self._create_utility_screen(
                self.network_scanner_widget, "🌐", "Network Scanner"
            )
            self.stacked_widget.addWidget(self.network_scanner_screen)
        
        self.stacked_widget.setCurrentWidget(self.network_scanner_screen)
        
    def _show_smart_test(self):
        """Navigate to SMART Test utility - requires admin privileges"""
        # Check if running as admin
        if not self._is_running_as_admin():
            reply = QMessageBox.question(
                self, "Administrator Required",
                "SMART disk health monitoring requires administrator privileges for full functionality.\n\n"
                "Would you like to restart the application as administrator?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                try:
                    # Get current script path
                    script_path = os.path.abspath(sys.argv[0])
                    
                    # Restart as admin with SMART argument
                    ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, 
                        f'"{script_path}" --open-smart-test', None, 1
                    )
                    
                    # Close current instance
                    QApplication.quit()
                    return
                    
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error",
                        f"Failed to restart as administrator: {e}\n\n"
                        f"Please manually run the application as administrator."
                    )
                    return
            else:
                return
        
        self._stop_wifi_scanning()
        self.current_screen = "smart_test"
        
        # Lazy loading - create widget only when first needed
        if self.smart_test_widget is None:
            debug("Creating SMART Test widget for first time...", "MainApp")
            self.smart_test_widget = SMARTTestWidget()
            self.smart_test_screen = self._create_utility_screen(
                self.smart_test_widget, "🔧", "SMART Disk Health"
            )
            self.stacked_widget.addWidget(self.smart_test_screen)
        
        self.stacked_widget.setCurrentWidget(self.smart_test_screen)
        
        # Auto-start SMART scan
        if self.smart_test_widget and not hasattr(self.smart_test_widget, '_has_auto_scanned'):
            self.smart_test_widget._start_smart_scan()
            self.smart_test_widget._has_auto_scanned = True
        
    def _stop_wifi_scanning(self):
        """Stop all WiFi scanning activities"""
        if self.wifi_scanner_widget:
            self.wifi_scanner_widget.stop_scanning()
        if self.wifi_charts_widget:
            self.wifi_charts_widget.stop_data_collection()
            
    def closeEvent(self, event):
        """Handle application close event"""
        debug("Application closing - stopping all WiFi scanning...", "MainApp")
        self._stop_wifi_scanning()
        event.accept()
        
    def _handle_auto_navigation(self):
        """Handle automatic navigation based on command line arguments"""
        if not self.args:
            return
            
        if self.args.open_smart_test:
            debug("Auto-opening SMART Test due to admin restart...", "MainApp")
            # Navigate directly to SMART test (admin should already be granted)
            self._show_smart_test()
            
        elif self.args.open_disk_analyzer:
            debug("Auto-opening Disk Analyzer due to admin restart...", "MainApp")
            
            # Navigate to disk analyzer first
            self._show_disk_analyzer()
            
            # Set up the folder/drive after the widget is created
            if self.disk_analyzer_widget:
                if self.args.folder:
                    debug(f"Auto-selecting folder: {self.args.folder}", "MainApp")
                    # Set the custom folder path
                    self.disk_analyzer_widget.current_custom_folder_path = self.args.folder
                    self.disk_analyzer_widget.custom_folder_label.setText(self.args.folder)
                    self.disk_analyzer_widget.custom_folder_label_prefix.show()
                    self.disk_analyzer_widget.custom_folder_label.show()
                    self.disk_analyzer_widget.scan_path_button.setText("🔍 Analyze Folder")
                    # Clear drive selection
                    self.disk_analyzer_widget.drive_select_combo.setCurrentIndex(-1)
                    
                elif self.args.drive:
                    debug(f"Auto-selecting drive: {self.args.drive}", "MainApp")
                    # Find and select the drive in the combo box
                    for i in range(self.disk_analyzer_widget.drive_select_combo.count()):
                        if self.disk_analyzer_widget.drive_select_combo.itemData(i) == self.args.drive:
                            self.disk_analyzer_widget.drive_select_combo.setCurrentIndex(i)
                            break
                            
    def _is_running_as_admin(self):
        """Check if the application is running with administrator privileges"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='IT Helper - Comprehensive IT toolkit')
    parser.add_argument('--open-disk-analyzer', action='store_true',
                       help='Automatically open the disk analyzer utility')
    parser.add_argument('--open-smart-test', action='store_true',
                       help='Automatically open the SMART disk health monitor')
    parser.add_argument('--folder', type=str,
                       help='Folder path to analyze (used with --open-disk-analyzer)')
    parser.add_argument('--drive', type=str,
                       help='Drive path to analyze (used with --open-disk-analyzer)')
    
    return parser.parse_args()


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("IT Helper")
    app.setOrganizationName("IT Helper")
    
    # Parse command line arguments
    args = parse_arguments()
    
    window = ITHelperApp(args)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main() 