import time
import numpy as np
from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFrame, QCheckBox, QSpacerItem, QSizePolicy
)
from PySide6.QtGui import QFont

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

import wifi_utilities
from shared_components import MplCanvas


class WifiChartsWidget(QWidget):
    """WiFi Charts utility widget for visualizing signal history"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize data structures
        self.all_detected_networks = {}
        self.all_signal_history_data = {}
        self.is_active = False
        
        # Initialize timers but don't start them
        self.charts_refresh_timer = QTimer(self)
        self.charts_refresh_timer.timeout.connect(self._auto_refresh_charts_graph)
        
        self.data_collection_timer = QTimer(self)
        self.data_collection_timer.timeout.connect(self._collect_wifi_data_for_charts)
        
        # Initialize UI
        self._init_ui()
        
        # Don't start background data collection automatically - wait for start_data_collection() to be called
        
    def start_data_collection(self):
        """Start WiFi data collection when module becomes active"""
        if not self.is_active:
            self.is_active = True
            # Collect data immediately for faster loading
            self._collect_wifi_data_for_charts()
            self.data_collection_timer.start(5000)  # Then collect data every 5 seconds
            print("WiFi Charts: Started data collection")
            
    def stop_data_collection(self):
        """Stop WiFi data collection when module becomes inactive"""
        if self.is_active:
            self.is_active = False
            if self.data_collection_timer.isActive():
                self.data_collection_timer.stop()
            if self.charts_refresh_timer.isActive():
                self.charts_refresh_timer.stop()
            print("WiFi Charts: Stopped data collection")
        
    def _init_ui(self):
        """Initialize the WiFi charts UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Left Panel: Network Selection List
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel)
        
        # Right Panel: Chart Display
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, stretch=1)
        
    def _create_left_panel(self):
        """Create the left panel with network selection list"""
        left_panel_widget = QWidget()
        left_panel_widget.setFixedWidth(300)
        left_panel_layout = QVBoxLayout(left_panel_widget)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel("Wi-Fi Charts")
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 10px;")
        left_panel_layout.addWidget(title_label)
        
        # Network selection label
        charts_list_label = QLabel("Available Networks for Charting:")
        charts_list_label.setFont(QFont("Arial", 12, QFont.Bold))
        left_panel_layout.addWidget(charts_list_label)

        # Network list widget
        self.charts_network_list = QListWidget()
        self.charts_network_list.itemChanged.connect(self._on_chart_network_item_changed)
        left_panel_layout.addWidget(self.charts_network_list)
        
        # Controls section
        controls_layout = QHBoxLayout()
        
        # Auto-refresh checkbox
        self.auto_refresh_checkbox = QCheckBox("Auto-refresh charts")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.stateChanged.connect(self._on_auto_refresh_toggled)
        controls_layout.addWidget(self.auto_refresh_checkbox)
        
        # Show Hidden Networks checkbox
        self.show_hidden_checkbox = QCheckBox("Show Hidden Networks")
        self.show_hidden_checkbox.setChecked(False)  # Hidden by default like in WiFi scanner
        self.show_hidden_checkbox.stateChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.show_hidden_checkbox)
        
        left_panel_layout.addLayout(controls_layout)
        
        return left_panel_widget
        
    def _create_right_panel(self):
        """Create the right panel with chart display"""
        right_panel_widget = QWidget()
        right_panel_layout = QVBoxLayout(right_panel_widget)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)

        # Top Controls Bar for Charts - simplified without refresh button
        charts_top_controls_layout = QHBoxLayout()
        
        # Title
        chart_title = QLabel("Signal Strength History")
        chart_title.setFont(QFont("Arial", 16, QFont.Bold))
        charts_top_controls_layout.addWidget(chart_title)
        
        charts_top_controls_layout.addStretch(1)

        right_panel_layout.addLayout(charts_top_controls_layout)

        # Chart canvas
        self.charts_mpl_canvas = MplCanvas(self)
        right_panel_layout.addWidget(self.charts_mpl_canvas, stretch=1)
        
        # Initialize with placeholder
        self._init_chart_placeholder()
        
        return right_panel_widget
        
    def _init_chart_placeholder(self):
        """Initialize chart with placeholder content"""
        self.charts_mpl_canvas.axes.clear()
        self.charts_mpl_canvas.axes.set_title("Wi-Fi Signal History", fontsize=14, fontweight='bold')
        self.charts_mpl_canvas.axes.set_xlabel("Time")
        self.charts_mpl_canvas.axes.set_ylabel("Signal Strength (dBm)")
        
        self.charts_mpl_canvas.axes.text(0.5, 0.5, 
                                        "Select networks from the list\nto view their signal history", 
                                        transform=self.charts_mpl_canvas.axes.transAxes, 
                                        ha='center', va='center', fontsize=12, alpha=0.7)
        self.charts_mpl_canvas.draw()
        
    def _start_background_data_collection(self):
        """Start background data collection for charting"""
        # This method is no longer called automatically
        # Data collection is now started via start_data_collection()
        pass
        
    def _collect_wifi_data_for_charts(self):
        """Collect WiFi data for chart display"""
        if not self.is_active:
            return
            
        try:
            networks_from_scan = wifi_utilities.get_wifi_data()
            if networks_from_scan:
                current_time = time.time()
                
                for network in networks_from_scan:
                    bssid = network.get('bssid', 'Unknown')
                    self.all_detected_networks[bssid] = network
                    
                    # Update signal history
                    if bssid not in self.all_signal_history_data:
                        self.all_signal_history_data[bssid] = deque(maxlen=100)
                    
                    signal_strength = network.get('signal_dbm', -100)
                    self.all_signal_history_data[bssid].append({
                        'timestamp': current_time,
                        'signal_dbm': signal_strength
                    })
                
                # Update the network list
                self._update_charts_network_list()
                
                # Auto-refresh charts if enabled
                if self.auto_refresh_checkbox.isChecked():
                    self._manage_charts_refresh_timer()
                    
        except Exception as e:
            print(f"WiFi Charts: Error collecting data: {e}")
            
    def _update_charts_network_list(self):
        """Update the network list for chart selection"""
        currently_selected_bssids = set()
        
        # Store currently selected items
        for i in range(self.charts_network_list.count()):
            item = self.charts_network_list.item(i)
            if item.checkState() == Qt.Checked:
                currently_selected_bssids.add(item.data(Qt.UserRole))
        
        # Clear and rebuild list
        self.charts_network_list.clear()
        
        for bssid, network_info in self.all_detected_networks.items():
            # Show networks with history (reduced requirement from 2 to 1 for faster display)
            if bssid in self.all_signal_history_data and len(self.all_signal_history_data[bssid]) >= 1:
                ssid = network_info.get('ssid', '<Hidden Network>')
                if not ssid or ssid.strip() == '':
                    ssid = '<Hidden Network>'
                
                # Apply hidden networks filter
                if not self.show_hidden_checkbox.isChecked() and ssid == '<Hidden Network>':
                    continue  # Skip hidden networks if filter is disabled
                    
                signal_dbm = network_info.get('signal_dbm', -100)
                # Use last 5 characters of BSSID for better network identification
                bssid_suffix = bssid[-5:] if len(bssid) >= 5 else bssid
                
                display_text = f"{ssid} ({bssid_suffix}, {signal_dbm} dBm)"
                
                item = QListWidgetItem(display_text)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                
                # Restore previous selection state
                if bssid in currently_selected_bssids:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
                    
                item.setData(Qt.UserRole, bssid)
                self.charts_network_list.addItem(item)
                
    @Slot()
    def _on_chart_network_item_changed(self, item):
        """Handle changes in network selection for charts"""
        self._plot_selected_networks_history()
        self._manage_charts_refresh_timer()
        
    @Slot()
    def _on_auto_refresh_toggled(self, state):
        """Handle auto-refresh checkbox toggle"""
        self._manage_charts_refresh_timer()
        
    @Slot()
    def _on_filter_changed(self):
        """Handle filter checkbox changes"""
        # Re-apply filtering and refresh the display
        self._update_charts_network_list()
        
    def _plot_selected_networks_history(self):
        """Plot signal history for selected networks"""
        self.charts_mpl_canvas.axes.clear()
        
        selected_networks = []
        for i in range(self.charts_network_list.count()):
            item = self.charts_network_list.item(i)
            if item.checkState() == Qt.Checked:
                bssid = item.data(Qt.UserRole)
                if bssid in self.all_signal_history_data:
                    network_info = self.all_detected_networks.get(bssid, {})
                    selected_networks.append((bssid, network_info))
        
        if not selected_networks:
            self.charts_mpl_canvas.axes.set_title("Wi-Fi Signal History", fontsize=14, fontweight='bold')
            self.charts_mpl_canvas.axes.set_xlabel("Time")
            self.charts_mpl_canvas.axes.set_ylabel("Signal Strength (dBm)")
            self.charts_mpl_canvas.axes.text(0.5, 0.5, 
                                            "Select networks from the list\nto view their signal history", 
                                            transform=self.charts_mpl_canvas.axes.transAxes, 
                                            ha='center', va='center', fontsize=12, alpha=0.7)
        else:
            # Plot signal history for each selected network - Extended color palette for more networks
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                     '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
                     '#ff1493', '#00ced1', '#ff4500', '#32cd32', '#ba55d3',
                     '#cd853f', '#ff69b4', '#00ff7f', '#dda0dd', '#98fb98']
            
            current_time = time.time()
            
            for idx, (bssid, network_info) in enumerate(selected_networks):
                history = self.all_signal_history_data[bssid]
                if len(history) < 1:  # Changed from 2 to 1 to allow single data points
                    continue
                    
                timestamps = [entry['timestamp'] for entry in history]
                signals = [entry['signal_dbm'] for entry in history]
                
                # Convert timestamps to relative times (minutes ago)
                relative_times = [(current_time - ts) / 60 for ts in timestamps]
                relative_times.reverse()  # Show oldest on left
                signals.reverse()
                
                ssid = network_info.get('ssid', '<Hidden Network>')
                if not ssid or ssid.strip() == '':
                    ssid = '<Hidden Network>'
                
                # Use last 5 characters of BSSID for consistent labeling
                bssid_suffix = bssid[-5:] if len(bssid) >= 5 else bssid
                    
                color = colors[idx % len(colors)]
                
                # Handle single data point vs multiple data points
                if len(timestamps) == 1:
                    # Single point - show as scatter
                    self.charts_mpl_canvas.axes.scatter(relative_times, signals, 
                                                       label=f"{ssid} ({bssid_suffix})",
                                                       color=color, s=50, alpha=0.8)
                else:
                    # Multiple points - show as line with markers
                    self.charts_mpl_canvas.axes.plot(relative_times, signals, 
                                                    label=f"{ssid} ({bssid_suffix})",
                                                    color=color, linewidth=2, marker='o', markersize=4)
            
            self.charts_mpl_canvas.axes.set_title("Wi-Fi Signal History", fontsize=14, fontweight='bold')
            self.charts_mpl_canvas.axes.set_xlabel("Time (minutes ago)")
            self.charts_mpl_canvas.axes.set_ylabel("Signal Strength (dBm)")
            self.charts_mpl_canvas.axes.set_ylim(-100, -20)
            self.charts_mpl_canvas.axes.grid(True, alpha=0.3)
            self.charts_mpl_canvas.axes.legend(loc='upper right', bbox_to_anchor=(1, 1))
            
            # Invert x-axis so recent times are on the right
            self.charts_mpl_canvas.axes.invert_xaxis()
        
        self.charts_mpl_canvas.draw()
        
    def _manage_charts_refresh_timer(self):
        """Manage the charts auto-refresh timer"""
        should_timer_be_active = (
            self.auto_refresh_checkbox.isChecked() and 
            self._has_selected_networks()
        )
        
        if should_timer_be_active and not self.charts_refresh_timer.isActive():
            self.charts_refresh_timer.start(2000)  # Refresh every 2 seconds
        elif not should_timer_be_active and self.charts_refresh_timer.isActive():
            self.charts_refresh_timer.stop()
            
    def _has_selected_networks(self):
        """Check if any networks are selected for charting"""
        for i in range(self.charts_network_list.count()):
            item = self.charts_network_list.item(i)
            if item.checkState() == Qt.Checked:
                return True
        return False
        
    @Slot()
    def _auto_refresh_charts_graph(self):
        """Auto-refresh the charts graph"""
        self._plot_selected_networks_history()
        
    def closeEvent(self, event):
        """Handle widget close event"""
        self.stop_data_collection()
        event.accept() 