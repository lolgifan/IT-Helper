"""
Shared UI components used across multiple IT Helper modules
"""
import time
from collections import deque
from datetime import datetime

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem,
    QTextEdit, QFrame, QSpacerItem, QSizePolicy
)
from PySide6.QtGui import QFont, QStandardItem

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class NumericTableWidgetItem(QTableWidgetItem):
    """Table widget item that sorts numerically rather than alphabetically"""
    
    def __lt__(self, other):
        if not isinstance(other, QTableWidgetItem):
            return super().__lt__(other)

        self_data = self.data(Qt.UserRole)
        other_data = other.data(Qt.UserRole)

        try:
            return self_data < other_data
        except TypeError:
            # Fallback to text comparison if numeric comparison fails
            return self.text() < other.text()


class SortableSizeStandardItem(QStandardItem):
    """Standard item for size sorting in tree views"""
    
    def __init__(self, text=None):
        if text is not None:
            super().__init__(text)
        else:
            super().__init__()

    def __lt__(self, other):
        # Use UserRole data for numeric comparison
        self_size = self.data(Qt.UserRole)
        other_size = other.data(Qt.UserRole)

        if isinstance(self_size, (int, float)) and isinstance(other_size, (int, float)):
            return self_size < other_size
        
        # Fallback to standard comparison
        return super().__lt__(other)


class MplCanvas(FigureCanvas):
    """Matplotlib canvas widget for embedding plots in Qt applications"""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.figure.add_subplot(111)
        super().__init__(self.figure)
        self.setParent(parent)
        
        # Configure the plot
        self.figure.patch.set_facecolor('#1a1a1a')  # Dark background
        self.axes.set_facecolor('#2d2d2d')  # Slightly lighter plot area
        
        # Set text colors for dark theme
        self.axes.xaxis.label.set_color('white')
        self.axes.yaxis.label.set_color('white')
        self.axes.title.set_color('white')
        self.axes.tick_params(colors='white')
        
        # Grid styling
        self.axes.grid(True, alpha=0.3, color='white')
        
    def clear_axes(self):
        """Clear the axes and reset styling"""
        self.axes.clear()
        self.axes.set_facecolor('#2d2d2d')
        self.axes.xaxis.label.set_color('white')
        self.axes.yaxis.label.set_color('white')
        self.axes.title.set_color('white')
        self.axes.tick_params(colors='white')


class NetworkDetailDialog(QDialog):
    """Dialog for displaying detailed network information"""
    
    def __init__(self, bssid, network_info, history_data, parent=None):
        super().__init__(parent)
        self.bssid = bssid
        self.network_info = network_info
        self.history_data = history_data
        self.parent_widget = parent  # Store reference to parent widget for data updates
        
        self.setWindowTitle(f"Network Details - {network_info.get('ssid', 'Hidden Network')}")
        self.setGeometry(200, 200, 800, 600)
        
        self._init_ui()
        self._update_details_and_plot()
        
        # Set up refresh timer to update every 0.5 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_data_and_update)
        self.refresh_timer.start(500)  # 500ms = 0.5 seconds
        
    def _refresh_data_and_update(self):
        """Refresh data from parent and update display"""
        if self.parent_widget and hasattr(self.parent_widget, 'all_detected_networks') and hasattr(self.parent_widget, 'all_signal_history_data'):
            # Get updated network info and history data from parent
            self.network_info = self.parent_widget.all_detected_networks.get(self.bssid, self.network_info)
            self.history_data = list(self.parent_widget.all_signal_history_data.get(self.bssid, []))
            
            # Update the display
            self._update_details_and_plot()
        
    def _init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Title
        title = QLabel(f"Network: {self.network_info.get('ssid', 'Hidden Network')}")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #4CAF50; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Network details section
        self._create_details_section(layout)
        
        # Signal history chart section
        self._create_chart_section(layout)
        
        # Buttons
        self._create_buttons_section(layout)
        
    def _create_details_section(self, parent_layout):
        """Create the network details section"""
        details_frame = QFrame()
        details_frame.setFrameShape(QFrame.StyledPanel)
        details_layout = QVBoxLayout(details_frame)
        
        details_label = QLabel("Network Information:")
        details_label.setFont(QFont("Arial", 12, QFont.Bold))
        details_layout.addWidget(details_label)
        
        self.details_text = QTextEdit()
        self.details_text.setFixedHeight(150)
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        
        parent_layout.addWidget(details_frame)
        
    def _create_chart_section(self, parent_layout):
        """Create the signal history chart section"""
        chart_frame = QFrame()
        chart_frame.setFrameShape(QFrame.StyledPanel)
        chart_layout = QVBoxLayout(chart_frame)
        
        chart_label = QLabel("Signal History:")
        chart_label.setFont(QFont("Arial", 12, QFont.Bold))
        chart_layout.addWidget(chart_label)
        
        self.chart_canvas = MplCanvas(self, width=8, height=4, dpi=100)
        chart_layout.addWidget(self.chart_canvas)
        
        parent_layout.addWidget(chart_frame, stretch=1)
        
    def _create_buttons_section(self, parent_layout):
        """Create the buttons section"""
        buttons_layout = QHBoxLayout()
        buttons_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setMinimumWidth(80)
        buttons_layout.addWidget(close_button)
        
        parent_layout.addLayout(buttons_layout)
        
    def _update_details_and_plot(self):
        """Update the details text and plot"""
        # Update details text
        details_text = []
        details_text.append(f"BSSID: {self.bssid}")
        details_text.append(f"SSID: {self.network_info.get('ssid', 'Hidden Network')}")
        details_text.append(f"Signal Strength: {self.network_info.get('signal_dbm', 'Unknown')} dBm")
        details_text.append(f"Channel: {self.network_info.get('channel', 'Unknown')}")
        details_text.append(f"Frequency: {self.network_info.get('frequency_mhz', 'Unknown')} MHz")
        details_text.append(f"Security: {self.network_info.get('encryption', 'Unknown')}")
        details_text.append(f"Vendor: {self.network_info.get('vendor', 'Unknown')}")
        
        if self.history_data:
            details_text.append(f"History Points: {len(self.history_data)}")
            if len(self.history_data) > 0:
                latest_entry = self.history_data[-1]
                last_seen = datetime.fromtimestamp(latest_entry['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
                details_text.append(f"Last Seen: {last_seen}")
        
        self.details_text.setPlainText('\n'.join(details_text))
        
        # Update plot
        self._plot_signal_history()
        
    def _plot_signal_history(self):
        """Plot the signal history"""
        self.chart_canvas.axes.clear()
        
        if not self.history_data or len(self.history_data) < 2:
            self.chart_canvas.axes.text(0.5, 0.5, "Insufficient data for plotting", 
                                       transform=self.chart_canvas.axes.transAxes, 
                                       ha='center', va='center', fontsize=12, alpha=0.7, color='white')
        else:
            timestamps = [entry['timestamp'] for entry in self.history_data]
            signals = [entry['signal_dbm'] for entry in self.history_data]
            
            # Convert timestamps to relative times
            current_time = time.time()
            relative_times = [(ts - timestamps[0]) / 60 for ts in timestamps]  # Minutes since first measurement
            
            self.chart_canvas.axes.plot(relative_times, signals, 'b-', linewidth=2, marker='o', markersize=4)
            self.chart_canvas.axes.set_xlabel("Time (minutes since first measurement)")
            self.chart_canvas.axes.set_ylabel("Signal Strength (dBm)")
            self.chart_canvas.axes.set_title(f"Signal History - {self.network_info.get('ssid', 'Hidden Network')}")
            self.chart_canvas.axes.grid(True, alpha=0.3)
            
            # Set y-axis limits
            min_signal = min(signals)
            max_signal = max(signals)
            padding = (max_signal - min_signal) * 0.1 if max_signal != min_signal else 5
            self.chart_canvas.axes.set_ylim(min_signal - padding, max_signal + padding)
        
        # Apply dark theme styling
        self.chart_canvas.axes.set_facecolor('#2d2d2d')
        self.chart_canvas.axes.xaxis.label.set_color('white')
        self.chart_canvas.axes.yaxis.label.set_color('white')
        self.chart_canvas.axes.title.set_color('white')
        self.chart_canvas.axes.tick_params(colors='white')
        
        self.chart_canvas.draw()
        
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Stop the refresh timer when closing
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        event.accept()
        
    def accept(self):
        """Handle dialog accept"""
        # Stop the refresh timer when accepting
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().accept()
        
    def reject(self):
        """Handle dialog reject"""
        # Stop the refresh timer when rejecting
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        super().reject() 