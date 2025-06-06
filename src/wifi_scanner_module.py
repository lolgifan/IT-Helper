import time
import csv
import threading
from collections import deque
import numpy as np
import matplotlib.pyplot as plt

from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QSize, QModelIndex
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLabel, QComboBox, QFrame, QSpacerItem, 
    QSizePolicy, QFileDialog, QDialog, QMessageBox, QCheckBox, QTreeView
)
from PySide6.QtGui import QFont, QColor, QStandardItemModel, QStandardItem

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import wifi_utilities
from shared_components import NumericTableWidgetItem, MplCanvas, NetworkDetailDialog


class ScanWorker(QThread):
    """Worker thread to perform Wi-Fi scans"""
    scan_completed = Signal(list)
    scan_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.current_scan_interval = 0.1

    def run(self):
        self.running = True
        print("ScanWorker: Thread started.")
        while self.running:
            print(f"ScanWorker: Requesting Wi-Fi data (interval: {self.current_scan_interval}s)")
            try:
                networks_from_scan = wifi_utilities.get_wifi_data()
                if networks_from_scan is not None:
                    self.scan_completed.emit(networks_from_scan)
                else:
                    self.scan_completed.emit([])
            except Exception as e:
                error_msg = f"ScanWorker: Error during scan: {e}"
                print(error_msg)
                self.scan_error.emit(error_msg)
                self.scan_completed.emit([])

            # Handle sleep based on interval
            if self.current_scan_interval == 0.1:
                time.sleep(0.1)
            else:
                sleep_chunk = 0.25
                total_sleep_needed = self.current_scan_interval
                slept_time = 0
                while slept_time < total_sleep_needed and self.running:
                    time.sleep(min(sleep_chunk, total_sleep_needed - slept_time))
                    slept_time += sleep_chunk
            
            if not self.running:
                break
        print("ScanWorker: Thread stopped.")

    def stop(self):
        print("ScanWorker: Stop requested.")
        self.running = False


class WifiScannerWidget(QWidget):
    """WiFi Scanner utility widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize data structures
        self.all_detected_networks = {}
        self.network_graph_colors = {}
        self.current_scan_interval = 0.1
        self.network_display_timeout = 7
        self.all_signal_history_data = {}
        self.current_networks_for_display = []
        self.MAX_HISTORY_POINTS = 100
        
        # Table sorting state
        self.sort_column_key = "Signal"
        self.sort_order = Qt.DescendingOrder
        
        # Timing data
        self.last_data_received_time = time.time()
        self.previous_data_received_time = None
        self.scan_intervals_history = deque(maxlen=20)
        
        # Scan state
        self.scan_in_progress_event = threading.Event()
        self.is_active = False
        
        # Initialize UI
        self._init_ui()
        self._init_scan_worker()
        
        # Don't start scanning automatically - wait for start_scanning() to be called
        
        # Initialize UI update timer but don't start it
        self.ui_update_timer = QTimer(self)
        self.ui_update_timer.timeout.connect(self.update_ui_elements)
        
    def start_scanning(self):
        """Start WiFi scanning when module becomes active"""
        if not self.is_active:
            self.is_active = True
            self.start_scan_worker()
            self.ui_update_timer.start(100)
            print("WiFi Scanner: Started scanning")
            
    def stop_scanning(self):
        """Stop WiFi scanning when module becomes inactive"""
        if self.is_active:
            self.is_active = False
            if hasattr(self, 'scan_worker') and self.scan_worker.isRunning():
                self.scan_worker.stop()
                self.scan_worker.wait()
            if self.ui_update_timer.isActive():
                self.ui_update_timer.stop()
            print("WiFi Scanner: Stopped scanning")
        
    def _init_ui(self):
        """Initialize the WiFi scanner UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)  # Reduced spacing
        
        # Title
        title_label = QLabel("Wi-Fi Scanner")
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 8px;")
        layout.addWidget(title_label)
        
        # Filter checkboxes section
        self._create_filter_section(layout)
        
        # Top section: Table/Tree and Controls - Give more space to table/tree
        self.top_section_layout = QHBoxLayout()
        
        # Create table and tree widgets
        self._create_table()
        
        # Add current view widget (initially table)
        self.top_section_layout.addWidget(self.current_view_widget, stretch=5)  # Increased from 3 to 5
        
        # Create controls
        self._create_controls()
        self.top_section_layout.addWidget(self.controls_frame, stretch=1)  # Kept at 1
        
        layout.addLayout(self.top_section_layout, stretch=3)  # Give more space to top section
        
        # Bottom section: Graphs - Reduced space
        self._create_graph_area()
        layout.addWidget(self.graph_display_area_container, stretch=2)  # Reduced from 1 to 2, but with top being 3, graphs get less relative space
        
    def _create_filter_section(self, parent_layout):
        """Create filter checkboxes section"""
        filter_frame = QFrame()
        filter_frame.setStyleSheet("QFrame { border: 1px solid #3d3d3d; border-radius: 4px; }")  # Removed background color
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 8, 10, 8)
        filter_layout.setSpacing(20)
        
        # Tree View checkbox
        self.tree_view_checkbox = QCheckBox("Tree View")
        self.tree_view_checkbox.setChecked(False)  # Unchecked by default
        self.tree_view_checkbox.setFont(QFont("Arial", 10))
        self.tree_view_checkbox.stateChanged.connect(self._on_tree_view_toggled)
        filter_layout.addWidget(self.tree_view_checkbox)
        
        # Show Hidden Networks checkbox
        self.show_hidden_checkbox = QCheckBox("Show Hidden Networks")
        self.show_hidden_checkbox.setChecked(False)  # Changed to unchecked by default
        self.show_hidden_checkbox.setFont(QFont("Arial", 10))
        self.show_hidden_checkbox.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.show_hidden_checkbox)
        
        # Show Security column checkbox
        self.show_security_checkbox = QCheckBox("Show Security")
        self.show_security_checkbox.setChecked(False)  # Changed to unchecked by default
        self.show_security_checkbox.setFont(QFont("Arial", 10))
        self.show_security_checkbox.stateChanged.connect(self._on_show_security_toggled)
        filter_layout.addWidget(self.show_security_checkbox)
        
        # Show 5GHz Channel Usage checkbox
        self.show_5ghz_graph_checkbox = QCheckBox("Show 5GHz Channel Usage")
        self.show_5ghz_graph_checkbox.setChecked(False)  # Unchecked by default
        self.show_5ghz_graph_checkbox.setFont(QFont("Arial", 10))
        self.show_5ghz_graph_checkbox.stateChanged.connect(self._on_show_5ghz_graph_toggled)
        filter_layout.addWidget(self.show_5ghz_graph_checkbox)
        
        # Add spacer to push checkboxes to left
        filter_layout.addStretch()
        
        parent_layout.addWidget(filter_frame)
        
    def _create_table(self):
        """Create the networks table/tree"""
        # Create both table and tree widgets
        self.network_table = QTableWidget()
        self.network_tree = QTreeView()
        
        # Configure table widget (existing logic)
        self.network_table.setColumnCount(6)  # Reduced from 7 to 6 (removed Vendor)
        
        # Removed Vendor column from headers
        headers = ["Name", "Signal", "Channel", "Frequency", "Security", "BSSID"]
        self.network_table.setHorizontalHeaderLabels(headers)
        
        # Configure table
        header = self.network_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self.on_sort_by_column_header_click)
        
        # Set column widths - Better balanced spacing
        self.network_table.setColumnWidth(0, 140)  # Name (reduced from 150)
        self.network_table.setColumnWidth(1, 160)  # Signal (increased from 140 to 160)
        self.network_table.setColumnWidth(2, 70)   # Channel (reduced from 80)
        self.network_table.setColumnWidth(3, 90)   # Frequency (reduced from 100)
        self.network_table.setColumnWidth(4, 90)   # Security (reduced from 100)
        self.network_table.setColumnWidth(5, 130)  # BSSID (reduced from 150 to 130)
        
        # Hide Security column by default since checkbox is unchecked by default
        self.network_table.setColumnHidden(4, True)
        
        # Connect double click for network details
        self.network_table.itemDoubleClicked.connect(self._on_network_double_clicked)
        
        # Configure tree widget
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(headers)
        self.network_tree.setModel(self.tree_model)
        
        # Configure tree
        tree_header = self.network_tree.header()
        tree_header.setSectionResizeMode(QHeaderView.Interactive)
        tree_header.setStretchLastSection(True)
        tree_header.setSortIndicatorShown(True)
        
        # Make tree view content compact but readable
        tree_font = QFont("Arial", 10)  # Reduced from 12pt to 10pt
        self.network_tree.setFont(tree_font)
        
        # Compact row height for better space efficiency
        self.network_tree.setStyleSheet("""
            QTreeView::item {
                height: 22px;
                padding: 2px;
            }
            QTreeView::item:selected {
                background-color: #3d3d3d;
            }
        """)
        
        # Set tree column widths (more compact but still functional) - only set initially
        self.network_tree.setColumnWidth(0, 260)  # Name (reduced from 600 to 450)
        self.network_tree.setColumnWidth(1, 200)  # Signal (reduced from 650 to 500)  
        self.network_tree.setColumnWidth(2, 90)   # Channel (reduced from 100 to 90)
        self.network_tree.setColumnWidth(3, 120)  # Frequency (reduced from 140 to 120)
        self.network_tree.setColumnWidth(4, 100)  # Security (reduced from 120 to 100)
        self.network_tree.setColumnWidth(5, 140)  # BSSID (reduced from 150 to 140)
        
        # Hide Security column by default
        self.network_tree.setColumnHidden(4, True)
        
        # Connect double click for network details on tree
        self.network_tree.doubleClicked.connect(self._on_tree_item_double_clicked)
        
        # Initially show table (tree view unchecked by default)
        self.current_view_widget = self.network_table
        
    def _create_controls(self):
        """Create the control panel"""
        self.controls_frame = QFrame()
        self.controls_frame.setFrameShape(QFrame.StyledPanel)
        self.controls_frame.setMaximumWidth(280)  # Increased from 220 to 280 to fit button text
        self.controls_frame.setMinimumWidth(280)  # Set minimum width to ensure consistency
        self.controls_layout = QVBoxLayout(self.controls_frame)
        self.controls_layout.setContentsMargins(10, 10, 10, 10)  # Increased margins back to 10
        self.controls_layout.setSpacing(8)  # Increased spacing slightly

        # Refresh Rate
        refresh_label = QLabel("Refresh Rate (s):")
        refresh_label.setFont(QFont("Arial", 10))  # Increased from 9 to 10
        self.controls_layout.addWidget(refresh_label)

        self.refresh_rate_combo = QComboBox()
        self.refresh_rate_combo.setMaximumHeight(35)  # Increased from 30 to 35
        self.refresh_rate_combo.setMinimumHeight(35)  # Set minimum height
        self.refresh_options = {
            "Instant": 0.1, "3s": 3, "5s": 5, "7s": 7, 
            "10s": 10, "15s": 15, "30s": 30, "60s": 60
        }
        for text, val in self.refresh_options.items():
            self.refresh_rate_combo.addItem(text, userData=val)
        self.refresh_rate_combo.setCurrentText("Instant")
        self.refresh_rate_combo.currentIndexChanged.connect(self.on_update_scan_interval)
        self.controls_layout.addWidget(self.refresh_rate_combo)

        # Scan Now Button - Reduced font size
        self.scan_now_button = QPushButton("Scan Now")
        self.scan_now_button.setMinimumHeight(40)  # Increased from 32 to 40
        self.scan_now_button.setMaximumHeight(40)
        self.scan_now_button.setFont(QFont("Arial", 9))  # Reduced from 10 to 9
        # Override global padding that was causing text cutoff
        self.scan_now_button.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                text-align: center;
                font-size: 9pt;
            }
        """)
        self.scan_now_button.clicked.connect(self.trigger_manual_scan)
        self.controls_layout.addWidget(self.scan_now_button)

        # Stop/Start Refresh Buttons - Reduced font size
        self.stop_refresh_button = QPushButton("Stop Auto-Refresh")
        self.stop_refresh_button.setMinimumHeight(40)  # Increased from 32 to 40
        self.stop_refresh_button.setMaximumHeight(40)
        self.stop_refresh_button.setFont(QFont("Arial", 9))  # Reduced from 10 to 9
        # Override global padding that was causing text cutoff
        self.stop_refresh_button.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                text-align: center;
                font-size: 9pt;
            }
        """)
        self.stop_refresh_button.clicked.connect(self.on_stop_refreshing_clicked)
        self.controls_layout.addWidget(self.stop_refresh_button)

        self.start_refresh_button = QPushButton("Start Auto-Refresh")
        self.start_refresh_button.setMinimumHeight(40)  # Increased from 32 to 40
        self.start_refresh_button.setMaximumHeight(40)
        self.start_refresh_button.setFont(QFont("Arial", 9))  # Reduced from 10 to 9
        # Override global padding that was causing text cutoff
        self.start_refresh_button.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                text-align: center;
                font-size: 9pt;
            }
        """)
        self.start_refresh_button.clicked.connect(self.on_start_refreshing_clicked)
        self.start_refresh_button.setEnabled(False)
        self.controls_layout.addWidget(self.start_refresh_button)

        # Timer Labels - Made slightly larger
        scan_time_layout = QHBoxLayout()
        scan_time_layout.setSpacing(6)  # Increased spacing
        
        self.refresh_timer_label = QLabel("0.0s ago")
        self.refresh_timer_label.setAlignment(Qt.AlignCenter)
        self.refresh_timer_label.setFont(QFont("Arial", 9))  # Increased from 8 to 9
        scan_time_layout.addWidget(self.refresh_timer_label)

        self.average_scan_time_label = QLabel("Avg: N/A")
        self.average_scan_time_label.setAlignment(Qt.AlignCenter)
        self.average_scan_time_label.setFont(QFont("Arial", 9))  # Increased from 8 to 9
        scan_time_layout.addWidget(self.average_scan_time_label)
        
        self.controls_layout.addLayout(scan_time_layout)
        
        # Export button - Reduced font size
        self.export_button = QPushButton("Export to CSV")
        self.export_button.setMinimumHeight(40)  # Increased from 32 to 40
        self.export_button.setMaximumHeight(40)
        self.export_button.setFont(QFont("Arial", 9))  # Reduced from 10 to 9
        # Override global padding that was causing text cutoff
        self.export_button.setStyleSheet("""
            QPushButton {
                padding: 8px 12px;
                text-align: center;
                font-size: 9pt;
            }
        """)
        self.export_button.clicked.connect(self._export_history_to_csv)
        self.controls_layout.addWidget(self.export_button)
        
        self.controls_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
    def _create_graph_area(self):
        """Create the channel graphs area"""
        self.graph_display_area_container = QFrame()
        self.graph_display_area_container.setFrameShape(QFrame.StyledPanel)
        
        graph_layout = QVBoxLayout(self.graph_display_area_container)
        graph_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins
        
        # Graph title - Made smaller
        graph_title = QLabel("Channel Usage Analysis")
        graph_title.setFont(QFont("Arial", 14, QFont.Bold))  # Reduced from 16 to 14
        graph_title.setAlignment(Qt.AlignCenter)
        graph_layout.addWidget(graph_title)
        
        # Graph area
        self.graphs_layout = QHBoxLayout()
        
        # 2.4GHz Graph - Made smaller
        self.graph_2_4ghz = MplCanvas(self, width=5, height=3, dpi=90)  # Reduced size
        self.graphs_layout.addWidget(self.graph_2_4ghz)
        
        # 5GHz Graph - Made smaller (initially hidden)
        self.graph_5ghz = MplCanvas(self, width=5, height=3, dpi=90)  # Reduced size
        self.graphs_layout.addWidget(self.graph_5ghz)
        self.graph_5ghz.setVisible(False)  # Hidden by default
        
        graph_layout.addLayout(self.graphs_layout)
        
        # Initialize graphs with placeholders
        self._initial_graph_placeholders()
        
    def _initial_graph_placeholders(self):
        """Create initial placeholder graphs"""
        # 2.4GHz placeholder
        self.graph_2_4ghz.axes.clear()
        self.graph_2_4ghz.axes.set_title("2.4GHz Channel Usage", fontsize=12, fontweight='bold')
        self.graph_2_4ghz.axes.set_xlabel("Channel")
        self.graph_2_4ghz.axes.set_ylabel("Signal Strength (dBm)")
        self.graph_2_4ghz.axes.text(0.5, 0.5, "No networks detected", 
                                   transform=self.graph_2_4ghz.axes.transAxes, 
                                   ha='center', va='center', fontsize=10, alpha=0.7)
        self.graph_2_4ghz.draw()
        
        # 5GHz placeholder
        self.graph_5ghz.axes.clear()
        self.graph_5ghz.axes.set_title("5GHz Channel Usage", fontsize=12, fontweight='bold')
        self.graph_5ghz.axes.set_xlabel("Channel")
        self.graph_5ghz.axes.set_ylabel("Signal Strength (dBm)")
        self.graph_5ghz.axes.text(0.5, 0.5, "No networks detected", 
                                 transform=self.graph_5ghz.axes.transAxes, 
                                 ha='center', va='center', fontsize=10, alpha=0.7)
        self.graph_5ghz.draw()
        
    def _init_scan_worker(self):
        """Initialize the scan worker thread"""
        self.scan_worker = ScanWorker(self)
        self.scan_worker.scan_completed.connect(self.on_scan_data_received)
        self.scan_worker.scan_error.connect(self.on_scan_error)
        
    def start_scan_worker(self):
        """Start the scan worker thread"""
        if not self.scan_worker.isRunning():
            self.scan_worker.current_scan_interval = self.current_scan_interval
            self.scan_worker.start()
            print("WiFi Scanner: Scan worker started.")
        else:
            print("WiFi Scanner: Scan worker already running.")
            
    @Slot(list)
    def on_scan_data_received(self, new_scan_results):
        """Handle received scan data"""
        current_time = time.time()
        
        # Update timing information
        if self.previous_data_received_time is not None:
            actual_interval = current_time - self.previous_data_received_time
            self.scan_intervals_history.append(actual_interval)
        
        self.previous_data_received_time = self.last_data_received_time
        self.last_data_received_time = current_time
        
        # Update network data
        for network in new_scan_results:
            bssid = network.get('bssid', 'Unknown')
            self.all_detected_networks[bssid] = network
            
            # Update signal history
            if bssid not in self.all_signal_history_data:
                self.all_signal_history_data[bssid] = deque(maxlen=self.MAX_HISTORY_POINTS)
            
            signal_strength = network.get('signal_dbm', -100)
            self.all_signal_history_data[bssid].append({
                'timestamp': current_time,
                'signal_dbm': signal_strength
            })
            
        # Refresh UI
        self._refresh_active_display_list_and_ui()
        
    @Slot(str)
    def on_scan_error(self, error_message):
        """Handle scan errors"""
        print(f"WiFi Scanner Error: {error_message}")
        
    def _refresh_active_display_list_and_ui(self):
        """Refresh the display list and update UI"""
        current_time = time.time()
        self.current_networks_for_display = []
        
        for bssid, network_info in self.all_detected_networks.items():
            last_seen = network_info.get('last_seen_timestamp', 0)
            if current_time - last_seen <= self.network_display_timeout:
                # Apply hidden networks filter
                ssid = network_info.get('ssid', '')
                if not self.show_hidden_checkbox.isChecked() and ('<Hidden Network>' in ssid or ssid.strip() == ''):
                    continue  # Skip hidden networks if filter is disabled
                
                self.current_networks_for_display.append(network_info)
                
        # Sort networks
        def sort_key_func(net):
            if self.sort_column_key == "Signal":
                return net.get('signal_dbm', -100)
            elif self.sort_column_key == "Name":
                return net.get('ssid', '').lower()
            elif self.sort_column_key == "Channel":
                return net.get('channel', 0)
            elif self.sort_column_key == "Frequency":
                return net.get('frequency_mhz', 0)
            else:
                return 0
                
        reverse_sort = (self.sort_order == Qt.DescendingOrder)
        self.current_networks_for_display.sort(key=sort_key_func, reverse=reverse_sort)
        
        self._populate_table(self.current_networks_for_display)
        self._update_graphs()
        
    def _populate_table(self, networks_to_show):
        """Populate the networks table or tree view"""
        if self.tree_view_checkbox.isChecked():
            self._populate_tree_view(networks_to_show)
        else:
            self._populate_table_view(networks_to_show)
            
    def _populate_table_view(self, networks_to_show):
        """Populate the networks table view (original logic)"""
        self.network_table.setRowCount(len(networks_to_show))
        
        for row, network in enumerate(networks_to_show):
            bssid = network.get('bssid', 'Unknown')
            
            # Generate color for this network
            network_color = self._generate_network_color(bssid)
            
            # Name with color
            name = network.get('ssid', '<Hidden Network>')
            name_item = QTableWidgetItem(name)
            name_item.setForeground(QColor(network_color))
            # Make item non-editable but still selectable
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.network_table.setItem(row, 0, name_item)
            
            # Signal
            signal_dbm = network.get('signal_dbm', -100)
            signal_item = NumericTableWidgetItem(self._dbm_to_signal_bar_text(signal_dbm))
            signal_item.setData(Qt.UserRole, signal_dbm)
            # Make item non-editable but still selectable
            signal_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.network_table.setItem(row, 1, signal_item)
            
            # Channel
            channel = network.get('channel', 0)
            channel_item = NumericTableWidgetItem(str(channel))
            channel_item.setData(Qt.UserRole, channel)
            # Make item non-editable but still selectable
            channel_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.network_table.setItem(row, 2, channel_item)
            
            # Frequency
            freq = network.get('frequency_mhz', 0)
            freq_item = NumericTableWidgetItem(f"{freq} MHz")
            freq_item.setData(Qt.UserRole, freq)
            # Make item non-editable but still selectable
            freq_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.network_table.setItem(row, 3, freq_item)
            
            # Security
            security = network.get('encryption', 'Unknown')
            security_item = QTableWidgetItem(security)
            # Make item non-editable but still selectable
            security_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.network_table.setItem(row, 4, security_item)
            
            # BSSID (now at index 5 after removing Vendor)
            bssid_item = QTableWidgetItem(bssid)
            bssid_item.setForeground(QColor(network_color))
            # Make item non-editable but still selectable
            bssid_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.network_table.setItem(row, 5, bssid_item)
            
    def _populate_tree_view(self, networks_to_show):
        """Populate the tree view grouped by SSID"""
        # Store current column widths to preserve user adjustments
        current_widths = []
        for col in range(self.tree_model.columnCount()):
            current_widths.append(self.network_tree.columnWidth(col))
        
        # Store current scroll position to preserve user's viewing location
        scroll_position = self.network_tree.verticalScrollBar().value()
        
        # Store current expansion state of top-level items
        expanded_items = set()
        root_item = self.tree_model.invisibleRootItem()
        for row in range(root_item.rowCount()):
            index = self.tree_model.index(row, 0)
            if self.network_tree.isExpanded(index):
                # Store the SSID name to identify expanded items
                item_text = self.tree_model.data(index)
                if item_text:
                    # Extract SSID name from group text (remove " (X networks)" part)
                    ssid_name = item_text.split(' (')[0] if ' (' in item_text else item_text
                    expanded_items.add(ssid_name)
        
        # Clear existing tree model
        self.tree_model.clear()
        headers = ["Name", "Signal", "Channel", "Frequency", "Security", "BSSID"]
        self.tree_model.setHorizontalHeaderLabels(headers)
        
        # Restore column widths after clearing the model
        for col, width in enumerate(current_widths):
            if col < len(headers):  # Ensure we don't exceed column count
                self.network_tree.setColumnWidth(col, width)
        
        # Group networks by SSID
        ssid_groups = {}
        for network in networks_to_show:
            ssid = network.get('ssid', '<Hidden Network>')
            if ssid not in ssid_groups:
                ssid_groups[ssid] = []
            ssid_groups[ssid].append(network)
        
        # Add each SSID group to the tree
        root_item = self.tree_model.invisibleRootItem()
        
        for ssid, networks_in_group in ssid_groups.items():
            if len(networks_in_group) == 1:
                # Single network - add directly without grouping
                network = networks_in_group[0]
                self._add_network_to_tree(root_item, network, is_child=False)
            else:
                # Multiple networks with same SSID - create group
                group_item = self._create_ssid_group_item(ssid, networks_in_group)
                root_item.appendRow(group_item)
                
                # Add individual networks as children
                for network in networks_in_group:
                    child_items = self._add_network_to_tree(group_item[0], network, is_child=True)
        
        # Restore expansion state based on SSID names
        root_item = self.tree_model.invisibleRootItem()
        for row in range(root_item.rowCount()):
            index = self.tree_model.index(row, 0)
            item_text = self.tree_model.data(index)
            if item_text:
                # Extract SSID name from group text or use as-is for single networks
                ssid_name = item_text.split(' (')[0] if ' (' in item_text else item_text
                if ssid_name in expanded_items:
                    self.network_tree.expand(index)
                else:
                    # For new groups not previously seen, expand by default
                    if ' (' in item_text:  # This is a group
                        self.network_tree.expand(index)
        
        # Apply security column visibility after rebuilding the tree
        show_security = self.show_security_checkbox.isChecked()
        self.network_tree.setColumnHidden(4, not show_security)
        
        # Restore scroll position after tree is rebuilt - use timer to ensure it happens after layout
        def restore_scroll():
            self.network_tree.verticalScrollBar().setValue(scroll_position)
        
        # Use QTimer.singleShot to restore scroll position after Qt has finished processing
        QTimer.singleShot(0, restore_scroll)
        
    def _create_ssid_group_item(self, ssid, networks):
        """Create a group item for an SSID with multiple networks"""
        group_name = f"{ssid} ({len(networks)} networks)"
        
        # Calculate group statistics
        strongest_signal = max(net.get('signal_dbm', -100) for net in networks)
        channels = list(set(net.get('channel', 0) for net in networks))
        channels_str = ', '.join(map(str, sorted(channels))) if len(channels) <= 3 else f"{len(channels)} channels"
        frequencies = list(set(net.get('frequency_mhz', 0) for net in networks))
        freq_str = ', '.join(f"{f} MHz" for f in sorted(frequencies)) if len(frequencies) <= 2 else "Mixed"
        securities = list(set(net.get('encryption', 'Unknown') for net in networks))
        security_str = ', '.join(securities) if len(securities) <= 2 else "Mixed"
        
        # Create group row items
        group_items = []
        
        # Name
        name_item = QStandardItem(group_name)
        name_item.setEditable(False)
        group_items.append(name_item)
        
        # Signal (strongest in group)
        signal_item = QStandardItem(self._dbm_to_signal_bar_text(strongest_signal))
        signal_item.setEditable(False)
        group_items.append(signal_item)
        
        # Channels
        channel_item = QStandardItem(channels_str)
        channel_item.setEditable(False)
        group_items.append(channel_item)
        
        # Frequencies
        freq_item = QStandardItem(freq_str)
        freq_item.setEditable(False)
        group_items.append(freq_item)
        
        # Security
        security_item = QStandardItem(security_str)
        security_item.setEditable(False)
        group_items.append(security_item)
        
        # BSSID count
        bssid_item = QStandardItem(f"{len(networks)} BSSIDs")
        bssid_item.setEditable(False)
        group_items.append(bssid_item)
        
        return group_items
        
    def _add_network_to_tree(self, parent_item, network, is_child=False):
        """Add a network to the tree (as top-level item or child)"""
        bssid = network.get('bssid', 'Unknown')
        network_color = self._generate_network_color(bssid)
        
        # Create network row items
        network_items = []
        
        # Name
        name = network.get('ssid', '<Hidden Network>')
        if is_child:
            name = f"Access Point ({bssid[-8:]})"  # Show last 8 chars of BSSID for child items
        name_item = QStandardItem(name)
        name_item.setEditable(False)
        name_item.setForeground(QColor(network_color))
        network_items.append(name_item)
        
        # Signal
        signal_dbm = network.get('signal_dbm', -100)
        signal_item = QStandardItem(self._dbm_to_signal_bar_text(signal_dbm))
        signal_item.setEditable(False)
        network_items.append(signal_item)
        
        # Channel
        channel = network.get('channel', 0)
        channel_item = QStandardItem(str(channel))
        channel_item.setEditable(False)
        network_items.append(channel_item)
        
        # Frequency
        freq = network.get('frequency_mhz', 0)
        freq_item = QStandardItem(f"{freq} MHz")
        freq_item.setEditable(False)
        network_items.append(freq_item)
        
        # Security
        security = network.get('encryption', 'Unknown')
        security_item = QStandardItem(security)
        security_item.setEditable(False)
        network_items.append(security_item)
        
        # BSSID
        bssid_item = QStandardItem(bssid)
        bssid_item.setEditable(False)
        bssid_item.setForeground(QColor(network_color))
        network_items.append(bssid_item)
        
        # Add to parent
        parent_item.appendRow(network_items)
        return network_items
        
    def _dbm_to_signal_bar_text(self, dbm, bar_length=10):
        """Convert dBm to a text-based bar and append dBm value"""
        clamped_dbm = max(-100, min(dbm, -20))
        percentage = ((clamped_dbm - (-100)) / (-20 - (-100))) * 100
        percentage = max(0, min(100, percentage))
        filled_chars = int(round((percentage / 100) * bar_length))
        bar = '█' * filled_chars + '░' * (bar_length - filled_chars)
        return f"[{bar}] {dbm} dBm"
        
    def _update_graphs(self):
        """Update the channel usage graphs"""
        self._update_2_4ghz_graph_qt(self.current_networks_for_display)
        
        # Only update 5GHz graph if it's visible
        if self.show_5ghz_graph_checkbox.isChecked():
            self._update_5ghz_graph_qt(self.current_networks_for_display)
            
    def _update_2_4ghz_graph_qt(self, networks):
        """Update 2.4GHz channel graph"""
        networks_2_4 = [n for n in networks if n.get('frequency_mhz', 0) < 3000]
        
        self.graph_2_4ghz.axes.clear()
        self.graph_2_4ghz.axes.set_title("2.4GHz Channel Usage", fontsize=12, fontweight='bold')
        self.graph_2_4ghz.axes.set_xlabel("Channel")
        self.graph_2_4ghz.axes.set_ylabel("Signal Strength (dBm)")
        
        if not networks_2_4:
            self.graph_2_4ghz.axes.text(0.5, 0.5, "No 2.4GHz networks detected", 
                                       transform=self.graph_2_4ghz.axes.transAxes, 
                                       ha='center', va='center', fontsize=10, alpha=0.7)
        else:
            # Group networks by SSID for labeling
            for network in networks_2_4:
                bssid = network.get('bssid', 'Unknown')
                channel = network.get('channel', 0)
                signal = network.get('signal_dbm', -100)
                ssid = network.get('ssid', '<Hidden>')
                
                # Get network color
                color = self._generate_network_color(bssid)
                
                # Plot with color and label
                self.graph_2_4ghz.axes.scatter([channel], [signal], 
                                              color=color, alpha=0.8, s=60, 
                                              label=ssid[:15] if len(ssid) > 15 else ssid)
            
            self.graph_2_4ghz.axes.set_xlim(1, 14)
            self.graph_2_4ghz.axes.set_ylim(-100, -20)
            self.graph_2_4ghz.axes.grid(True, alpha=0.3)
            
            # Add legend if there are networks but limit entries
            if len(networks_2_4) <= 10:  # Only show legend if not too crowded
                self.graph_2_4ghz.axes.legend(fontsize=8, loc='upper right')
            
        self.graph_2_4ghz.draw()
        
    def _update_5ghz_graph_qt(self, networks):
        """Update 5GHz channel graph"""
        networks_5 = [n for n in networks if n.get('frequency_mhz', 0) >= 5000]
        
        self.graph_5ghz.axes.clear()
        self.graph_5ghz.axes.set_title("5GHz Channel Usage", fontsize=12, fontweight='bold')
        self.graph_5ghz.axes.set_xlabel("Channel")
        self.graph_5ghz.axes.set_ylabel("Signal Strength (dBm)")
        
        if not networks_5:
            self.graph_5ghz.axes.text(0.5, 0.5, "No 5GHz networks detected", 
                                     transform=self.graph_5ghz.axes.transAxes, 
                                     ha='center', va='center', fontsize=10, alpha=0.7)
        else:
            # Group networks by SSID for labeling
            for network in networks_5:
                bssid = network.get('bssid', 'Unknown')
                channel = network.get('channel', 0)
                signal = network.get('signal_dbm', -100)
                ssid = network.get('ssid', '<Hidden>')
                
                # Get network color
                color = self._generate_network_color(bssid)
                
                # Plot with color and label
                self.graph_5ghz.axes.scatter([channel], [signal], 
                                            color=color, alpha=0.8, s=60,
                                            label=ssid[:15] if len(ssid) > 15 else ssid)
            
            self.graph_5ghz.axes.set_ylim(-100, -20)
            self.graph_5ghz.axes.grid(True, alpha=0.3)
            
            # Add legend if there are networks but limit entries
            if len(networks_5) <= 10:  # Only show legend if not too crowded
                self.graph_5ghz.axes.legend(fontsize=8, loc='upper right')
            
        self.graph_5ghz.draw()
        
    @Slot(int, Qt.SortOrder)
    def on_sort_by_column_header_click(self, column_index, order):
        """Handle table column header clicks for sorting"""
        column_keys = ["Name", "Signal", "Channel", "Frequency", "Security", "BSSID"]
        if column_index < len(column_keys):
            self.sort_column_key = column_keys[column_index]
            self.sort_order = order
            self._refresh_active_display_list_and_ui()
            
    @Slot()
    def on_update_scan_interval(self):
        """Update scan interval when combo box changes"""
        selected_text = self.refresh_rate_combo.currentText()
        new_interval = self.refresh_options.get(selected_text, 0.1)
        self.current_scan_interval = new_interval
        if hasattr(self, 'scan_worker'):
            self.scan_worker.current_scan_interval = new_interval
            
    @Slot()
    def trigger_manual_scan(self):
        """Trigger a manual scan"""
        print("Manual scan triggered")
        
    @Slot()
    def on_stop_refreshing_clicked(self):
        """Stop auto-refresh"""
        if hasattr(self, 'scan_worker'):
            self.scan_worker.stop()
            self.stop_refresh_button.setEnabled(False)
            self.start_refresh_button.setEnabled(True)
            
    @Slot()
    def on_start_refreshing_clicked(self):
        """Start auto-refresh"""
        if not self.is_active:
            return
        self.start_scan_worker()
        self.stop_refresh_button.setEnabled(True)
        self.start_refresh_button.setEnabled(False)
        
    @Slot()
    def update_ui_elements(self):
        """Update UI elements like timers"""
        current_time = time.time()
        time_since_last = current_time - self.last_data_received_time
        self.refresh_timer_label.setText(f"{time_since_last:.1f}s ago")
        
        if self.scan_intervals_history:
            avg_interval = sum(self.scan_intervals_history) / len(self.scan_intervals_history)
            self.average_scan_time_label.setText(f"Avg: {avg_interval:.1f}s")
            
    def _export_history_to_csv(self):
        """Export signal history to CSV file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Signal History", "wifi_signal_history.csv", "CSV Files (*.csv)"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Timestamp', 'BSSID', 'SSID', 'Signal_dBm', 'Channel', 'Frequency_MHz'])
                    
                    for bssid, history in self.all_signal_history_data.items():
                        network_info = self.all_detected_networks.get(bssid, {})
                        ssid = network_info.get('ssid', 'Unknown')
                        channel = network_info.get('channel', 0)
                        frequency = network_info.get('frequency_mhz', 0)
                        
                        for entry in history:
                            writer.writerow([
                                entry['timestamp'], bssid, ssid, entry['signal_dbm'], 
                                channel, frequency
                            ])
                            
                QMessageBox.information(self, "Export Complete", f"Signal history exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")
                
    @Slot(QTableWidgetItem)
    def _on_network_double_clicked(self, item):
        """Handle double-click on network table item"""
        row = item.row()
        if row < len(self.current_networks_for_display):
            network = self.current_networks_for_display[row]
            bssid = network.get('bssid', '')
            history_data = self.all_signal_history_data.get(bssid, deque())
            
            dialog = NetworkDetailDialog(bssid, network, history_data, self)
            dialog.exec()

    def closeEvent(self, event):
        """Handle widget close event"""
        self.stop_scanning()
        event.accept()

    @Slot()
    def _on_filter_changed(self):
        """Handle filter checkbox changes"""
        # Re-apply filtering and refresh the display
        self._refresh_active_display_list_and_ui()
        
    @Slot()
    def _on_show_security_toggled(self):
        """Handle show security column toggle"""
        show_security = self.show_security_checkbox.isChecked()
        # Apply to both table and tree views
        self.network_table.setColumnHidden(4, not show_security)
        self.network_tree.setColumnHidden(4, not show_security)

    @Slot()
    def _on_show_5ghz_graph_toggled(self):
        """Handle show 5GHz channel usage checkbox toggle"""
        show_5ghz_graph = self.show_5ghz_graph_checkbox.isChecked()
        self.graph_5ghz.setVisible(show_5ghz_graph)
        
        # Adjust graph sizing - when 5GHz is hidden, 2.4GHz takes full width
        if show_5ghz_graph:
            # Both graphs visible - create new canvases with smaller width
            self.graph_2_4ghz.setParent(None)
            self.graph_5ghz.setParent(None)
            
            self.graph_2_4ghz = MplCanvas(self, width=5, height=3, dpi=90)
            self.graph_5ghz = MplCanvas(self, width=5, height=3, dpi=90)
            
            self.graphs_layout.addWidget(self.graph_2_4ghz)
            self.graphs_layout.addWidget(self.graph_5ghz)
        else:
            # Only 2.4GHz visible - make it wider
            self.graph_2_4ghz.setParent(None)
            self.graph_5ghz.setParent(None)
            
            self.graph_2_4ghz = MplCanvas(self, width=10, height=3, dpi=90)  # Double width
            self.graph_5ghz = MplCanvas(self, width=5, height=3, dpi=90)
            
            self.graphs_layout.addWidget(self.graph_2_4ghz)
            self.graphs_layout.addWidget(self.graph_5ghz)
            self.graph_5ghz.setVisible(False)
            
        self._update_graphs()
        
    def _generate_network_color(self, bssid):
        """Generate a consistent color for a network based on its BSSID"""
        if bssid not in self.network_graph_colors:
            # Generate a color based on BSSID hash
            import hashlib
            hash_obj = hashlib.md5(bssid.encode())
            hash_hex = hash_obj.hexdigest()
            
            # Convert hash to RGB values
            r = int(hash_hex[0:2], 16)
            g = int(hash_hex[2:4], 16) 
            b = int(hash_hex[4:6], 16)
            
            # Ensure colors are bright enough and distinct
            r = max(100, r)
            g = max(100, g) 
            b = max(100, b)
            
            # Store as hex color
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.network_graph_colors[bssid] = color
            
        return self.network_graph_colors[bssid]
        
    @Slot()
    def _on_tree_view_toggled(self):
        """Handle tree view checkbox toggle"""
        show_tree_view = self.tree_view_checkbox.isChecked()
        
        # Remove current widget from layout
        self.top_section_layout.removeWidget(self.current_view_widget)
        self.current_view_widget.setParent(None)
        
        if show_tree_view:
            self.current_view_widget = self.network_tree
        else:
            self.current_view_widget = self.network_table
            
        # Add new widget to layout
        self.top_section_layout.insertWidget(0, self.current_view_widget, stretch=5)
        
        # Apply security column visibility to new view
        show_security = self.show_security_checkbox.isChecked()
        self.current_view_widget.setColumnHidden(4, not show_security)
        
        # Refresh the display
        self._refresh_active_display_list_and_ui()

    @Slot(QModelIndex)
    def _on_tree_item_double_clicked(self, index):
        """Handle double-click on tree item"""
        if index.isValid():
            item = self.tree_model.itemFromIndex(index)
            if item:
                # Get BSSID from the item (column 5)
                bssid_index = self.tree_model.index(index.row(), 5, index.parent())
                bssid = self.tree_model.data(bssid_index)
                
                # Only show details if it's a valid BSSID (not group summary)
                if bssid and bssid != f"{len(self.all_detected_networks)} BSSIDs" and ":" in bssid:
                    network = self.all_detected_networks.get(bssid, {})
                    history_data = self.all_signal_history_data.get(bssid, deque())
                    
                    dialog = NetworkDetailDialog(bssid, network, history_data, self)
                    dialog.exec()
        