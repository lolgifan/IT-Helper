import os
import sys
import socket
import threading
import subprocess
import ipaddress
import time
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSortFilterProxyModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QFrame,
    QGroupBox, QGridLayout, QComboBox, QCheckBox, QSpinBox, QMessageBox,
    QApplication, QMenu, QFileDialog
)
from PySide6.QtGui import QFont, QColor, QAction, QPixmap, QIcon
import platform


class NetworkScanWorker(QThread):
    """Worker thread for network scanning operations"""
    device_found = Signal(dict)
    scan_progress = Signal(int, int, str)  # current, total, status
    scan_complete = Signal()
    scan_error = Signal(str)
    
    def __init__(self, ip_range, scan_ports=True, timeout=1, parent=None):
        super().__init__(parent)
        self.ip_range = ip_range
        self.scan_ports = scan_ports
        self.timeout = timeout
        self.should_stop = False
        
        # Common ports to scan
        self.common_ports = {
            21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
            80: 'HTTP', 110: 'POP3', 135: 'RPC', 139: 'NetBIOS', 143: 'IMAP',
            443: 'HTTPS', 445: 'SMB', 993: 'IMAPS', 995: 'POP3S', 
            1433: 'MSSQL', 3389: 'RDP', 5432: 'PostgreSQL', 5900: 'VNC'
        }
        
        # Load MAC vendor database
        self.mac_vendors = self._load_mac_vendors()
    
    def stop(self):
        """Stop the scanning process"""
        self.should_stop = True
    
    def run(self):
        """Main scanning logic"""
        try:
            # Parse IP range
            if '/' in self.ip_range:
                network = ipaddress.IPv4Network(self.ip_range, strict=False)
                ip_list = list(network.hosts())
            elif '-' in self.ip_range:
                start_ip, end_ip = self.ip_range.split('-')
                start = ipaddress.IPv4Address(start_ip.strip())
                end = ipaddress.IPv4Address(end_ip.strip())
                ip_list = [ipaddress.IPv4Address(ip) for ip in range(int(start), int(end) + 1)]
            else:
                ip_list = [ipaddress.IPv4Address(self.ip_range)]
            
            total_ips = len(ip_list)
            self.scan_progress.emit(0, total_ips, "Starting scan...")
            
            # Use ThreadPoolExecutor for concurrent scanning
            with ThreadPoolExecutor(max_workers=50) as executor:
                future_to_ip = {
                    executor.submit(self._scan_single_ip, str(ip)): str(ip) 
                    for ip in ip_list
                }
                
                completed = 0
                for future in as_completed(future_to_ip):
                    if self.should_stop:
                        break
                        
                    completed += 1
                    ip = future_to_ip[future]
                    
                    try:
                        result = future.result()
                        if result:
                            self.device_found.emit(result)
                    except Exception as e:
                        pass  # Skip failed IPs
                    
                    self.scan_progress.emit(completed, total_ips, f"Scanning {ip}...")
            
            if not self.should_stop:
                self.scan_complete.emit()
                
        except Exception as e:
            self.scan_error.emit(f"Scan error: {str(e)}")
    
    def _scan_single_ip(self, ip):
        """Scan a single IP address"""
        if self.should_stop:
            return None
            
        device_info = {'ip': ip}
        
        # Ping test
        ping_time = self._ping_host(ip)
        if ping_time is None:
            return None  # Host not responding
        
        device_info['response_time'] = f"{ping_time:.1f}ms"
        device_info['status'] = 'Online'
        
        # Get hostname
        hostname = self._get_hostname(ip)
        device_info['hostname'] = hostname
        
        # Get MAC address
        mac_address = self._get_mac_address(ip)
        device_info['mac_address'] = mac_address
        
        # Get manufacturer from MAC
        if mac_address and mac_address != 'Unknown':
            manufacturer = self._get_mac_manufacturer(mac_address)
            device_info['manufacturer'] = manufacturer
        else:
            device_info['manufacturer'] = 'Unknown'
        
        # Port scanning
        if self.scan_ports:
            open_ports = self._scan_ports(ip)
            device_info['open_ports'] = open_ports
            device_info['services'] = ', '.join([f"{port}({service})" for port, service in open_ports.items()])
        else:
            device_info['services'] = 'Not scanned'
        
        return device_info
    
    def _ping_host(self, ip, timeout=1):
        """Ping a host and return response time in ms"""
        try:
            if platform.system().lower() == 'windows':
                cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), ip]
            else:
                cmd = ['ping', '-c', '1', '-W', str(timeout), ip]
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
            end_time = time.time()
            
            if result.returncode == 0:
                return (end_time - start_time) * 1000
            return None
        except:
            return None
    
    def _get_hostname(self, ip):
        """Get hostname for IP address"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except:
            return 'Unknown'
    
    def _get_mac_address(self, ip):
        """Get MAC address using ARP"""
        try:
            if platform.system().lower() == 'windows':
                # Use arp command on Windows
                result = subprocess.run(['arp', '-a', ip], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ip in line and 'dynamic' in line.lower():
                            parts = line.split()
                            for part in parts:
                                if '-' in part and len(part) == 17:  # MAC format xx-xx-xx-xx-xx-xx
                                    return part.replace('-', ':').upper()
            else:
                # Use arp command on Linux/Mac
                result = subprocess.run(['arp', '-n', ip], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ip in line:
                            parts = line.split()
                            for part in parts:
                                if ':' in part and len(part) == 17:  # MAC format xx:xx:xx:xx:xx:xx
                                    return part.upper()
        except:
            pass
        return 'Unknown'
    
    def _scan_ports(self, ip):
        """Scan common ports on the host"""
        open_ports = {}
        
        for port, service in self.common_ports.items():
            if self.should_stop:
                break
                
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, port))
                sock.close()
                
                if result == 0:
                    open_ports[port] = service
            except:
                pass
        
        return open_ports
    
    def _load_mac_vendors(self):
        """Load MAC vendor database (simplified version)"""
        # Simplified MAC vendor database - in a real implementation, 
        # you might load this from a file or API
        vendors = {
            '00:1B:63': 'Apple',
            '00:03:93': 'Apple', 
            '00:05:02': 'Apple',
            '00:16:CB': 'Apple',
            '00:17:F2': 'Apple',
            '00:1C:B3': 'Apple',
            '00:1E:C2': 'Apple',
            '00:21:E9': 'Apple',
            '00:23:12': 'Apple',
            '00:25:00': 'Apple',
            '00:26:4A': 'Apple',
            '00:50:56': 'VMware',
            '00:0C:29': 'VMware',
            '00:15:5D': 'Microsoft',
            '00:03:FF': 'Microsoft',
            '08:00:27': 'VirtualBox',
            '52:54:00': 'QEMU',
            '00:E0:4C': 'Realtek',
            '00:01:97': 'Realtek',
            '00:E0:4B': 'Realtek',
            '70:85:C2': 'Realtek',
            '10:BF:48': 'Intel',
            '00:15:17': 'Intel',
            '00:1B:21': 'Intel',
            '00:1E:67': 'Intel',
            '00:24:D7': 'Intel',
            '68:05:CA': 'Intel',
            '30:5A:3A': 'Intel',
            'AC:220B': 'Intel',
        }
        return vendors
    
    def _get_mac_manufacturer(self, mac_address):
        """Get manufacturer from MAC address"""
        if not mac_address or mac_address == 'Unknown':
            return 'Unknown'
        
        # Extract first 3 octets (OUI)
        try:
            oui = ':'.join(mac_address.split(':')[:3])
            return self.mac_vendors.get(oui, 'Unknown')
        except:
            return 'Unknown'


class NetworkScannerWidget(QWidget):
    """Network Scanner utility widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scan_worker = None
        self.scan_results = []
        self._init_ui()
        self._detect_network_range()
        
    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title and controls
        top_layout = QHBoxLayout()
        
        title_label = QLabel("Network Scanner")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50;")
        top_layout.addWidget(title_label)
        
        top_layout.addStretch()
        
        # Export button
        self.export_button = QPushButton("📄 Export")
        self.export_button.setFont(QFont("Arial", 10))
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.export_button.clicked.connect(self._export_results)
        self.export_button.setEnabled(False)
        top_layout.addWidget(self.export_button)
        
        layout.addLayout(top_layout)
        
        # Scan configuration
        config_frame = QGroupBox("Scan Configuration")
        config_frame.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        config_layout = QGridLayout(config_frame)
        
        # IP Range
        config_layout.addWidget(QLabel("IP Range:"), 0, 0)
        self.ip_range_edit = QLineEdit()
        self.ip_range_edit.setPlaceholderText("e.g., 192.168.1.0/24 or 192.168.1.1-192.168.1.254")
        config_layout.addWidget(self.ip_range_edit, 0, 1)
        
        # Options
        self.port_scan_checkbox = QCheckBox("Scan common ports")
        self.port_scan_checkbox.setChecked(True)
        config_layout.addWidget(self.port_scan_checkbox, 1, 0)
        
        config_layout.addWidget(QLabel("Timeout (seconds):"), 1, 1)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 10)
        self.timeout_spin.setValue(2)
        config_layout.addWidget(self.timeout_spin, 1, 2)
        
        # Scan button
        self.scan_button = QPushButton("🔍 Start Scan")
        self.scan_button.setFont(QFont("Arial", 11, QFont.Bold))
        self.scan_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        self.scan_button.clicked.connect(self._start_scan)
        config_layout.addWidget(self.scan_button, 0, 2, 2, 1)
        
        layout.addWidget(config_frame)
        
        # Progress bar
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("Ready to scan")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("color: #cccccc; font-size: 10px;")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(20)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 3px;
                text-align: center;
                background-color: #2d2d2d;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.progress_frame)
        self.progress_frame.hide()
        
        # Results table
        results_label = QLabel("Scan Results")
        results_label.setFont(QFont("Arial", 12, QFont.Bold))
        results_label.setStyleSheet("color: #ffffff; margin-top: 10px;")
        layout.addWidget(results_label)
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "IP Address", "Hostname", "MAC Address", "Manufacturer", 
            "Response Time", "Status", "Services"
        ])
        
        # Table styling
        self.results_table.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                gridline-color: #3d3d3d;
                selection-background-color: #4CAF50;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d3d3d;
            }
            QTableWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                color: white;
                padding: 8px;
                border: 1px solid #4d4d4d;
                font-weight: bold;
            }
        """)
        
        # Configure table
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # IP
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Hostname
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # MAC
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Manufacturer
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Response Time
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # Status
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # Services
        
        self.results_table.setColumnWidth(0, 120)  # IP
        self.results_table.setColumnWidth(2, 140)  # MAC
        self.results_table.setColumnWidth(4, 100)  # Response Time
        self.results_table.setColumnWidth(5, 80)   # Status
        
        self.results_table.setSortingEnabled(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.results_table)
        
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #cccccc;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        self.device_count_label = QLabel("Devices found: 0")
        self.device_count_label.setStyleSheet("color: #cccccc;")
        status_layout.addWidget(self.device_count_label)
        
        layout.addLayout(status_layout)
    
    def _detect_network_range(self):
        """Auto-detect local network range"""
        try:
            # Get local IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Convert to network range (assuming /24)
            ip_parts = local_ip.split('.')
            network_range = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
            self.ip_range_edit.setText(network_range)
            
        except Exception:
            # Fallback to common ranges
            self.ip_range_edit.setText("192.168.1.0/24")
    
    def _start_scan(self):
        """Start network scanning"""
        ip_range = self.ip_range_edit.text().strip()
        if not ip_range:
            QMessageBox.warning(self, "Input Error", "Please enter an IP range to scan.")
            return
        
        # Clear previous results
        self.results_table.setRowCount(0)
        self.scan_results.clear()
        self.device_count_label.setText("Devices found: 0")
        
        # Update UI
        self.scan_button.setText("⏹ Stop Scan")
        self.scan_button.clicked.disconnect()
        self.scan_button.clicked.connect(self._stop_scan)
        self.progress_frame.show()
        self.export_button.setEnabled(False)
        
        # Start scanning
        self.scan_worker = NetworkScanWorker(
            ip_range=ip_range,
            scan_ports=self.port_scan_checkbox.isChecked(),
            timeout=self.timeout_spin.value()
        )
        
        self.scan_worker.device_found.connect(self._on_device_found)
        self.scan_worker.scan_progress.connect(self._on_scan_progress)
        self.scan_worker.scan_complete.connect(self._on_scan_complete)
        self.scan_worker.scan_error.connect(self._on_scan_error)
        
        self.scan_worker.start()
        
    def _stop_scan(self):
        """Stop current scan"""
        if self.scan_worker:
            self.scan_worker.stop()
            self.scan_worker.wait(2000)  # Wait up to 2 seconds
        
        self._reset_scan_ui()
    
    def _reset_scan_ui(self):
        """Reset scan UI to initial state"""
        self.scan_button.setText("🔍 Start Scan")
        self.scan_button.clicked.disconnect()
        self.scan_button.clicked.connect(self._start_scan)
        self.progress_frame.hide()
        self.export_button.setEnabled(len(self.scan_results) > 0)
        self.status_label.setText("Ready")
    
    def _on_device_found(self, device_info):
        """Handle discovered device"""
        self.scan_results.append(device_info)
        
        # Add to table
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        self.results_table.setItem(row, 0, QTableWidgetItem(device_info['ip']))
        self.results_table.setItem(row, 1, QTableWidgetItem(device_info.get('hostname', 'Unknown')))
        self.results_table.setItem(row, 2, QTableWidgetItem(device_info.get('mac_address', 'Unknown')))
        self.results_table.setItem(row, 3, QTableWidgetItem(device_info.get('manufacturer', 'Unknown')))
        self.results_table.setItem(row, 4, QTableWidgetItem(device_info.get('response_time', 'N/A')))
        
        # Status with color
        status_item = QTableWidgetItem(device_info.get('status', 'Unknown'))
        if device_info.get('status') == 'Online':
            status_item.setForeground(QColor('#4CAF50'))
        self.results_table.setItem(row, 5, status_item)
        
        self.results_table.setItem(row, 6, QTableWidgetItem(device_info.get('services', 'None')))
        
        # Update count
        self.device_count_label.setText(f"Devices found: {len(self.scan_results)}")
    
    def _on_scan_progress(self, current, total, status):
        """Update scan progress"""
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(f"{status} ({current}/{total})")
        self.status_label.setText(f"Scanning... {percentage}% complete")
    
    def _on_scan_complete(self):
        """Handle scan completion"""
        self._reset_scan_ui()
        self.status_label.setText(f"Scan complete - {len(self.scan_results)} devices found")
        
        if len(self.scan_results) == 0:
            QMessageBox.information(self, "Scan Complete", "No devices found in the specified range.")
    
    def _on_scan_error(self, error_message):
        """Handle scan error"""
        self._reset_scan_ui()
        self.status_label.setText("Scan failed")
        QMessageBox.critical(self, "Scan Error", f"Scanning failed:\n{error_message}")
    
    def _export_results(self):
        """Export scan results to CSV"""
        if not self.scan_results:
            QMessageBox.information(self, "Export", "No scan results to export.")
            return
        
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Network Scan Results",
                f"network_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if filename:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['IP Address', 'Hostname', 'MAC Address', 'Manufacturer', 
                                'Response Time', 'Status', 'Services']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for device in self.scan_results:
                        writer.writerow({
                            'IP Address': device['ip'],
                            'Hostname': device.get('hostname', 'Unknown'),
                            'MAC Address': device.get('mac_address', 'Unknown'),
                            'Manufacturer': device.get('manufacturer', 'Unknown'),
                            'Response Time': device.get('response_time', 'N/A'),
                            'Status': device.get('status', 'Unknown'),
                            'Services': device.get('services', 'None')
                        })
                
                QMessageBox.information(self, "Export Complete", f"Results exported to:\n{filename}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export results:\n{str(e)}") 