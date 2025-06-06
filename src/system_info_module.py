import os
import sys
import platform
import psutil
import subprocess
import socket
import uuid
import json
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, 
    QGroupBox, QGridLayout, QTextEdit, QPushButton, QTabWidget, 
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QSpacerItem, QSizePolicy,
    QSplitter, QTreeWidget, QTreeWidgetItem, QApplication
)
from PySide6.QtGui import QFont, QClipboard
import time


class SystemInfoWorker(QThread):
    """Worker thread for gathering system information"""
    info_gathered = Signal(dict)
    info_error = Signal(str)
    progress_update = Signal(str, int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def run_powershell(self, command, timeout=30):
        """Run PowerShell command and return result"""
        try:
            full_command = ['powershell', '-Command', command]
            result = subprocess.run(full_command, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
        except Exception as e:
            print(f"Error running PowerShell command: {e}")
            return None
        
    def run(self):
        """Gather comprehensive system information"""
        try:
            system_info = {}
            
            # Basic System Information
            self.progress_update.emit("Gathering basic system information...", 10)
            system_info['basic'] = self._get_basic_info()
            
            # CPU Information
            self.progress_update.emit("Gathering CPU information...", 20)
            system_info['cpu'] = self._get_cpu_info()
            
            # Memory Information
            self.progress_update.emit("Gathering memory information...", 30)
            system_info['memory'] = self._get_memory_info()
            
            # Storage Information
            self.progress_update.emit("Gathering storage information...", 40)
            system_info['storage'] = self._get_storage_info()
            
            # Network Information
            self.progress_update.emit("Gathering network information...", 50)
            system_info['network'] = self._get_network_info()
            
            # Hardware Information
            self.progress_update.emit("Gathering hardware information...", 60)
            system_info['hardware'] = self._get_hardware_info()
            
            # Graphics Information
            self.progress_update.emit("Gathering graphics information...", 70)
            system_info['graphics'] = self._get_graphics_info()
            
            # Display Information
            self.progress_update.emit("Gathering display information...", 75)
            system_info['display'] = self._get_display_info()
            
            # Environment Variables
            self.progress_update.emit("Gathering environment information...", 90)
            system_info['environment'] = self._get_environment_info()
            
            self.progress_update.emit("Finalizing...", 100)
            self.info_gathered.emit(system_info)
            
        except Exception as e:
            self.info_error.emit(f"Failed to gather system information: {str(e)}")
    
    def _get_basic_info(self):
        """Get basic system information"""
        info = {}
        try:
            info['computer_name'] = socket.gethostname()
            info['username'] = os.getlogin()
            info['platform'] = platform.platform()
            info['system'] = platform.system()
            info['release'] = platform.release()
            info['version'] = platform.version()
            info['machine'] = platform.machine()
            info['processor'] = platform.processor()
            info['architecture'] = platform.architecture()
            info['boot_time'] = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')
            
            # Uptime
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            uptime_str = str(timedelta(seconds=int(uptime_seconds)))
            info['uptime'] = uptime_str
            
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _get_cpu_info(self):
        """Get CPU information"""
        info = {}
        try:
            info['physical_cores'] = psutil.cpu_count(logical=False)
            info['total_cores'] = psutil.cpu_count(logical=True)
            info['max_frequency'] = f"{psutil.cpu_freq().max:.2f} MHz" if psutil.cpu_freq() else "N/A"
            info['current_frequency'] = f"{psutil.cpu_freq().current:.2f} MHz" if psutil.cpu_freq() else "N/A"
            
            # Get CPU name from Windows registry if available
            if platform.system() == "Windows":
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                       r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                    cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                    info['cpu_name'] = cpu_name.strip()
                    winreg.CloseKey(key)
                except:
                    info['cpu_name'] = platform.processor()
            else:
                info['cpu_name'] = platform.processor()
                
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _get_memory_info(self):
        """Get detailed memory module information using PowerShell"""
        info = {}
        try:
            virtual_memory = psutil.virtual_memory()
            info['total_ram'] = self._format_bytes(virtual_memory.total)
            
            # Get detailed memory modules using PowerShell
            ps_command = '''
            Get-WmiObject -Class Win32_PhysicalMemory | ForEach-Object {
                [PSCustomObject]@{
                    BankLabel = $_.BankLabel
                    Capacity = $_.Capacity
                    DeviceLocator = $_.DeviceLocator
                    FormFactor = $_.FormFactor
                    Manufacturer = $_.Manufacturer
                    MemoryType = $_.MemoryType
                    PartNumber = $_.PartNumber
                    SerialNumber = $_.SerialNumber
                    Speed = $_.Speed
                    Voltage = $_.ConfiguredVoltage
                    DataWidth = $_.DataWidth
                    TotalWidth = $_.TotalWidth
                    TypeDetail = $_.TypeDetail
                }
            } | ConvertTo-Json
            '''
            
            result = self.run_powershell(ps_command)
            if result:
                try:
                    data = json.loads(result)
                    if isinstance(data, list):
                        modules = data
                    elif isinstance(data, dict):
                        modules = [data]
                    else:
                        modules = []
                    
                    memory_modules = []
                    for module in modules:
                        formatted_module = {
                            'slot_location': module.get('DeviceLocator', 'N/A'),
                            'size': self._format_bytes(int(module['Capacity'])) if module.get('Capacity') and str(module['Capacity']).isdigit() else 'N/A',
                            'speed': f"{module['Speed']} MHz" if module.get('Speed') and str(module['Speed']).isdigit() else 'N/A',
                            'manufacturer': module.get('Manufacturer', 'N/A'),
                            'part_number': module.get('PartNumber', 'N/A'),
                            'memory_type': self._decode_memory_type(str(module.get('MemoryType', ''))),
                            'form_factor': self._decode_form_factor(str(module.get('FormFactor', ''))),
                            'voltage': f"{int(module['Voltage'])/1000:.1f}V" if module.get('Voltage') and str(module['Voltage']).isdigit() else 'N/A',
                            'serial_number': module.get('SerialNumber', 'N/A'),
                            'data_width': f"{module['DataWidth']} bits" if module.get('DataWidth') and str(module['DataWidth']).isdigit() else 'N/A',
                            'total_width': f"{module['TotalWidth']} bits" if module.get('TotalWidth') and str(module['TotalWidth']).isdigit() else 'N/A'
                        }
                        memory_modules.append(formatted_module)
                    
                    info['memory_modules'] = memory_modules
                    
                except json.JSONDecodeError:
                    info['memory_modules'] = []
            else:
                info['memory_modules'] = []
                    
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _decode_memory_type(self, value):
        """Decode memory type"""
        if not value or not value.isdigit():
            return 'Unknown'
        memory_types = {
            '20': 'DDR', '21': 'DDR2', '24': 'DDR3', '26': 'DDR4', '34': 'DDR5',
            '0': 'Unknown'
        }
        return memory_types.get(value, f'Unknown ({value})')
    
    def _decode_form_factor(self, value):
        """Decode memory form factor"""
        if not value or not value.isdigit():
            return 'Unknown'
        form_factors = {
            '8': 'DIMM', '12': 'SO-DIMM', '13': 'Micro-DIMM'
        }
        return form_factors.get(value, f'Unknown ({value})')
    
    def _get_storage_info(self):
        """Get storage information"""
        info = {}
        try:
            partitions = psutil.disk_partitions()
            drives = []
            
            for partition in partitions:
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    drives.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'file_system': partition.fstype,
                        'total_size': self._format_bytes(partition_usage.total),
                        'used': self._format_bytes(partition_usage.used),
                        'free': self._format_bytes(partition_usage.free),
                        'percentage': f"{(partition_usage.used / partition_usage.total) * 100:.1f}%"
                    })
                except PermissionError:
                    drives.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'file_system': partition.fstype,
                        'total_size': 'Access Denied',
                        'used': 'Access Denied',
                        'free': 'Access Denied',
                        'percentage': 'Access Denied'
                    })
            
            info['drives'] = drives
            
            # Disk I/O statistics
            disk_io = psutil.disk_io_counters()
            if disk_io:
                info['disk_io'] = {
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count,
                    'read_bytes': self._format_bytes(disk_io.read_bytes),
                    'write_bytes': self._format_bytes(disk_io.write_bytes)
                }
                    
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _get_network_info(self):
        """Get detailed network adapter information using PowerShell"""
        info = {}
        try:
            info['hostname'] = socket.gethostname()
            info['ip_address'] = socket.gethostbyname(socket.gethostname())
            
            # Get network adapter information using PowerShell
            ps_command = '''
            Get-WmiObject -Class Win32_NetworkAdapter | Where-Object {$_.NetConnectionStatus -eq 2} | ForEach-Object {
                [PSCustomObject]@{
                    Name = $_.Name
                    Speed = $_.Speed
                    MACAddress = $_.MACAddress
                    AdapterType = $_.AdapterType
                    Manufacturer = $_.Manufacturer
                    NetConnectionID = $_.NetConnectionID
                    PNPDeviceID = $_.PNPDeviceID
                }
            } | ConvertTo-Json
            '''
            
            result = self.run_powershell(ps_command)
            if result:
                try:
                    data = json.loads(result)
                    if isinstance(data, list):
                        adapters = data
                    elif isinstance(data, dict):
                        adapters = [data]
                    else:
                        adapters = []
                    
                    network_adapters = []
                    for adapter in adapters:
                        adapter_info = {
                            'network_card': adapter.get('Name', 'N/A'),
                            'manufacturer': adapter.get('Manufacturer', 'N/A'),
                            'mac_address': adapter.get('MACAddress', 'N/A'),
                            'adapter_type': adapter.get('AdapterType', 'N/A'),
                            'connection_name': adapter.get('NetConnectionID', 'N/A'),
                            'device_id': adapter.get('PNPDeviceID', 'N/A')
                        }
                        
                        # Format speed
                        if adapter.get('Speed') and str(adapter['Speed']).isdigit():
                            speed_bps = int(adapter['Speed'])
                            if speed_bps >= 1000000000:
                                adapter_info['maximum_speed'] = f"{speed_bps // 1000000000} Gbps"
                            elif speed_bps >= 1000000:
                                adapter_info['maximum_speed'] = f"{speed_bps // 1000000} Mbps"
                            else:
                                adapter_info['maximum_speed'] = f"{speed_bps} bps"
                        else:
                            adapter_info['maximum_speed'] = 'N/A'
                        
                        network_adapters.append(adapter_info)
                    
                    info['network_adapters'] = network_adapters
                    
                except json.JSONDecodeError:
                    info['network_adapters'] = []
            
            # Basic network interfaces (fallback)
            try:
                interfaces = psutil.net_if_addrs()
                network_interfaces = {}
                for interface_name, interface_addresses in interfaces.items():
                    interface_info = []
                    for address in interface_addresses:
                        interface_info.append({
                            'family': str(address.family),
                            'address': address.address,
                            'netmask': address.netmask,
                            'broadcast': address.broadcast
                        })
                    network_interfaces[interface_name] = interface_info
                info['basic_interfaces'] = network_interfaces
            except:
                pass
            
            # Network I/O statistics
            net_io = psutil.net_io_counters()
            if net_io:
                info['network_io'] = {
                    'bytes_sent': self._format_bytes(net_io.bytes_sent),
                    'bytes_recv': self._format_bytes(net_io.bytes_recv),
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                }
            
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _get_hardware_info(self):
        """Get hardware information including service tag using PowerShell"""
        info = {}
        try:
            # Machine UUID
            info['machine_uuid'] = str(uuid.uuid1())
            
            if platform.system() == "Windows":
                # BIOS Information using PowerShell
                ps_command = '''
                Get-WmiObject -Class Win32_BIOS | ForEach-Object {
                    [PSCustomObject]@{
                        Manufacturer = $_.Manufacturer
                        ReleaseDate = $_.ReleaseDate
                        SerialNumber = $_.SerialNumber
                        SMBIOSBIOSVersion = $_.SMBIOSBIOSVersion
                    }
                } | ConvertTo-Json
                '''
                
                result = self.run_powershell(ps_command)
                if result:
                    try:
                        data = json.loads(result)
                        if isinstance(data, dict):
                            info['bios_manufacturer'] = data.get('Manufacturer', 'N/A')
                            info['bios_date'] = data.get('ReleaseDate', 'N/A')
                            info['service_tag'] = data.get('SerialNumber', 'N/A')
                            info['bios_version'] = data.get('SMBIOSBIOSVersion', 'N/A')
                    except:
                        pass
                
                # System Information using PowerShell
                ps_command = '''
                Get-WmiObject -Class Win32_ComputerSystem | ForEach-Object {
                    [PSCustomObject]@{
                        Manufacturer = $_.Manufacturer
                        Model = $_.Model
                        TotalPhysicalMemory = $_.TotalPhysicalMemory
                    }
                } | ConvertTo-Json
                '''
                
                result = self.run_powershell(ps_command)
                if result:
                    try:
                        data = json.loads(result)
                        if isinstance(data, dict):
                            info['system_manufacturer'] = data.get('Manufacturer', 'N/A')
                            info['system_model'] = data.get('Model', 'N/A')
                            total_memory = data.get('TotalPhysicalMemory', '0')
                            if total_memory and str(total_memory).isdigit():
                                info['total_physical_memory'] = self._format_bytes(int(total_memory))
                            else:
                                info['total_physical_memory'] = 'N/A'
                    except:
                        pass
                    
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _get_graphics_info(self):
        """Get comprehensive graphics card information using PowerShell"""
        info = {}
        try:
            if platform.system() == "Windows":
                ps_command = '''
                Get-WmiObject -Class Win32_VideoController | ForEach-Object {
                    [PSCustomObject]@{
                        Name = $_.Name
                        AdapterRAM = $_.AdapterRAM
                        DriverVersion = $_.DriverVersion
                        DriverDate = $_.DriverDate
                        VideoProcessor = $_.VideoProcessor
                        VideoArchitecture = $_.VideoArchitecture
                        VideoMemoryType = $_.VideoMemoryType
                        CurrentBitsPerPixel = $_.CurrentBitsPerPixel
                        CurrentHorizontalResolution = $_.CurrentHorizontalResolution
                        CurrentVerticalResolution = $_.CurrentVerticalResolution
                        CurrentRefreshRate = $_.CurrentRefreshRate
                        MaxRefreshRate = $_.MaxRefreshRate
                        MinRefreshRate = $_.MinRefreshRate
                        PNPDeviceID = $_.PNPDeviceID
                        AdapterCompatibility = $_.AdapterCompatibility
                    }
                } | ConvertTo-Json
                '''
                
                result = self.run_powershell(ps_command)
                if result:
                    try:
                        data = json.loads(result)
                        if isinstance(data, list):
                            controllers = data
                        elif isinstance(data, dict):
                            controllers = [data]
                        else:
                            controllers = []
                        
                        graphics_cards = []
                        for gpu in controllers:
                            card_info = {
                                'graphics_card': gpu.get('Name', 'N/A'),
                                'graphics_chipset': self._extract_chipset(gpu.get('Name', '')),
                                'vram_memory': self._format_bytes(int(gpu['AdapterRAM'])) if gpu.get('AdapterRAM') and str(gpu['AdapterRAM']).isdigit() else 'N/A',
                                'controller_manufacturer': gpu.get('AdapterCompatibility', 'N/A'),
                                'driver_description': gpu.get('Name', 'N/A'),
                                'driver_version': gpu.get('DriverVersion', 'N/A'),
                                'driver_date': gpu.get('DriverDate', 'N/A'),
                                'hardware_id': gpu.get('PNPDeviceID', 'N/A'),
                                'video_memory_type': gpu.get('VideoMemoryType', 'N/A'),
                                'max_refresh_rate': f"{gpu['MaxRefreshRate']} Hz" if gpu.get('MaxRefreshRate') and str(gpu['MaxRefreshRate']).isdigit() else 'N/A',
                                'min_refresh_rate': f"{gpu['MinRefreshRate']} Hz" if gpu.get('MinRefreshRate') and str(gpu['MinRefreshRate']).isdigit() else 'N/A',
                                'current_resolution': f"{gpu['CurrentHorizontalResolution']}x{gpu['CurrentVerticalResolution']}" if gpu.get('CurrentHorizontalResolution') and gpu.get('CurrentVerticalResolution') else 'N/A'
                            }
                            
                            graphics_cards.append(card_info)
                        
                        info['graphics_cards'] = graphics_cards
                        
                    except json.JSONDecodeError:
                        info['graphics_cards'] = []
                        
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _extract_chipset(self, gpu_name):
        """Extract chipset from GPU name"""
        if not gpu_name or gpu_name == 'N/A':
            return 'N/A'
        
        # Common chipset extraction patterns
        gpu_name_lower = gpu_name.lower()
        
        # NVIDIA patterns
        if 'nvidia' in gpu_name_lower or 'geforce' in gpu_name_lower:
            if 'rtx' in gpu_name_lower:
                import re
                match = re.search(r'rtx\s*(\d+)', gpu_name_lower)
                return f"RTX {match.group(1)}" if match else 'NVIDIA RTX'
            elif 'gtx' in gpu_name_lower:
                import re
                match = re.search(r'gtx\s*(\d+)', gpu_name_lower)
                return f"GTX {match.group(1)}" if match else 'NVIDIA GTX'
        
        # AMD patterns
        elif 'amd' in gpu_name_lower or 'radeon' in gpu_name_lower:
            if 'rx' in gpu_name_lower:
                import re
                match = re.search(r'rx\s*(\d+)', gpu_name_lower)
                return f"RX {match.group(1)}" if match else 'AMD RX'
        
        # Intel patterns
        elif 'intel' in gpu_name_lower:
            if 'iris' in gpu_name_lower:
                return 'Intel Iris'
            elif 'uhd' in gpu_name_lower:
                return 'Intel UHD'
        
        return gpu_name  # Return full name if no pattern matches
    
    def _get_display_info(self):
        """Get display/monitor information"""
        info = {}
        try:
            if platform.system() == "Windows":
                # Try to get EDID data from registry
                try:
                    info['edid_data'] = self._get_edid_from_registry()
                except Exception as e:
                    info['edid_error'] = str(e)
                    
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _get_edid_from_registry(self):
        """Get EDID data from Windows Registry"""
        edid_info = {}
        
        try:
            import winreg
            # EDID data is stored in the registry under DISPLAY
            display_path = r"SYSTEM\CurrentControlSet\Enum\DISPLAY"
            
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, display_path) as key:
                i = 0
                while True:
                    try:
                        monitor_key = winreg.EnumKey(key, i)
                        monitor_path = f"{display_path}\\{monitor_key}"
                        
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, monitor_path) as monitor_reg:
                            j = 0
                            while True:
                                try:
                                    instance_key = winreg.EnumKey(monitor_reg, j)
                                    instance_path = f"{monitor_path}\\{instance_key}\\Device Parameters"
                                    
                                    try:
                                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, instance_path) as instance_reg:
                                            edid_data, _ = winreg.QueryValueEx(instance_reg, "EDID")
                                            if edid_data:
                                                edid_info[f'monitor_{i}_{j}'] = {
                                                    'parsed': self._parse_edid_basic(edid_data)
                                                }
                                    except:
                                        pass
                                    j += 1
                                except OSError:
                                    break
                        i += 1
                    except OSError:
                        break
        except Exception as e:
            edid_info['error'] = str(e)
            
        return edid_info
    
    def _parse_edid_basic(self, edid_data):
        """Basic EDID parsing"""
        try:
            if len(edid_data) < 128:
                return {'error': 'EDID data too short'}
            
            import struct
            # Basic EDID structure parsing
            manufacturer_id = (edid_data[8] << 8) | edid_data[9]
            product_code = (edid_data[10] << 8) | edid_data[11]
            serial_number = struct.unpack('<I', edid_data[12:16])[0]
            
            # Week and year of manufacture
            week = edid_data[16]
            year = edid_data[17] + 1990
            
            # Display size
            max_h_size = edid_data[21]  # cm
            max_v_size = edid_data[22]  # cm
            
            return {
                'manufacturer_id': f"{manufacturer_id:04X}",
                'product_code': f"{product_code:04X}",
                'serial_number': serial_number,
                'manufacture_week': week,
                'manufacture_year': year,
                'max_horizontal_size_cm': max_h_size,
                'max_vertical_size_cm': max_v_size
            }
        except Exception as e:
            return {'parse_error': str(e)}
    
    def _get_environment_info(self):
        """Get environment information"""
        info = {}
        try:
            # Important environment variables
            important_vars = ['PATH', 'USERPROFILE', 'SYSTEMROOT', 'TEMP', 'TMP', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS']
            env_vars = {}
            for var in important_vars:
                env_vars[var] = os.environ.get(var, 'Not Set')
            info['environment_variables'] = env_vars
            
            # Python information
            info['python_version'] = sys.version
            info['python_executable'] = sys.executable
            
        except Exception as e:
            info['error'] = str(e)
        return info
    
    def _format_bytes(self, bytes_value):
        """Format bytes to human readable format"""
        try:
            bytes_value = int(bytes_value)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_value < 1024.0:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024.0
            return f"{bytes_value:.1f} PB"
        except:
            return "N/A"


class SystemInfoWidget(QWidget):
    """System Information utility widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.system_info_data = {}
        self.worker = None
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI with tree view layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Top section with title and controls
        top_layout = QHBoxLayout()
        
        # Title in top-left corner (like Disk Space Analyzer)
        title_label = QLabel("System Information")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 5px;")
        top_layout.addWidget(title_label)
        
        # Subtitle with computer name
        self.subtitle_label = QLabel("Gathering system information...")
        self.subtitle_label.setFont(QFont("Arial", 10))
        self.subtitle_label.setStyleSheet("color: #cccccc; margin-left: 15px;")
        top_layout.addWidget(self.subtitle_label)
        
        # Spacer to push controls to the right
        top_layout.addStretch()
        
        # Control buttons
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.setFont(QFont("Arial", 10))
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.refresh_button.clicked.connect(self._gather_system_info)
        top_layout.addWidget(self.refresh_button)
        
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
        self.export_button.clicked.connect(self._export_to_text)
        self.export_button.setEnabled(False)
        top_layout.addWidget(self.export_button)
        
        self.copy_button = QPushButton("📋 Copy")
        self.copy_button.setFont(QFont("Arial", 10))
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.copy_button.setEnabled(False)
        top_layout.addWidget(self.copy_button)
        
        layout.addLayout(top_layout)
        
        # Progress bar
        self.progress_frame = QFrame()
        progress_layout = QVBoxLayout(self.progress_frame)
        
        self.progress_label = QLabel("Initializing...")
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
                font-size: 10px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addWidget(self.progress_frame)
        
        # Main content area with splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3d3d3d;
                width: 2px;
            }
        """)
        
        # Left side - Tree view
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabel("Hardware Components")
        self.tree_widget.setFixedWidth(300)
        self.tree_widget.setStyleSheet("""
            QTreeWidget {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                font-size: 11px;
                selection-background-color: #4CAF50;
            }
            QTreeWidget::item {
                height: 24px;
                padding: 2px;
            }
            QTreeWidget::item:selected {
                background-color: #4CAF50;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #3d3d3d;
            }
            QTreeWidget::branch:closed:has-children {
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAJCAYAAADgkQYQAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABYSURBVBiVpY4xDsAgCAVBZ+Mm3v+yzQn6E0xsGp/yEt4jHwCQUkoHVFXMzN1d5u4ys8w8z/s+Yoy1VVVmllJKZhZjjBBC7/sPY4y1VVVjjM8xxnPOOedaa+t9XzCzmdmcc875H/gCDiglMgAAAABJRU5ErkJggg==);
            }
            QTreeWidget::branch:open:has-children {
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAJCAYAAADgkQYQAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABYSURBVBiVpY4xDsAgCAVBZ+Mm3v+yzQn6E0xsGp/yEt4jHwCQUkoHVFXMzN1d5u4ys8w8z/s+Yoy1VVVmllJKZhZjjBBC7/sPY4y1VVVjjM8xxnPOOedaa+t9XzCzmdmcc875H/gCDiglMgAAAABJRU5ErkJggg==);
            }
        """)
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)
        splitter.addWidget(self.tree_widget)
        
        # Right side - Information panel
        self.info_scroll = QScrollArea()
        self.info_scroll.setWidgetResizable(True)
        self.info_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border: 1px solid #3d3d3d;
            }
        """)
        
        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout(self.info_widget)
        self.info_layout.setContentsMargins(15, 15, 15, 15)
        self.info_layout.setSpacing(10)
        
        # Default info display
        welcome_label = QLabel("Select a component from the tree to view detailed information")
        welcome_label.setAlignment(Qt.AlignCenter)
        welcome_label.setStyleSheet("color: #888888; font-size: 12px; font-style: italic;")
        self.info_layout.addWidget(welcome_label)
        self.info_layout.addStretch()
        
        self.info_scroll.setWidget(self.info_widget)
        splitter.addWidget(self.info_scroll)
        
        # Set splitter proportions
        splitter.setSizes([300, 800])
        layout.addWidget(splitter)
        
        # Start gathering system info
        self._gather_system_info()
        
    def _gather_system_info(self):
        """Start gathering system information"""
        self.refresh_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.copy_button.setEnabled(False)
        self.progress_frame.show()
        self.tree_widget.clear()
        
        # Start worker thread
        self.worker = SystemInfoWorker()
        self.worker.info_gathered.connect(self._on_info_gathered)
        self.worker.info_error.connect(self._on_info_error)
        self.worker.progress_update.connect(self._on_progress_update)
        self.worker.start()
        
    def _on_progress_update(self, message, percentage):
        """Update progress display"""
        self.progress_label.setText(message)
        self.progress_bar.setValue(percentage)
        
    def _on_info_gathered(self, system_info):
        """Handle gathered system information"""
        self.system_info_data = system_info
        self.progress_frame.hide()
        self.refresh_button.setEnabled(True)
        self.export_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        
        # Update subtitle with computer name
        computer_name = system_info.get('basic', {}).get('computer_name', 'Unknown Computer')
        self.subtitle_label.setText(f"System information for: {computer_name}")
        
        # Create tree items
        self._create_info_tabs(system_info)
        
    def _on_info_error(self, error_message):
        """Handle information gathering error"""
        self.progress_frame.hide()
        self.refresh_button.setEnabled(True)
        self.subtitle_label.setText(f"Error: {error_message}")
        
    def _create_info_tabs(self, system_info):
        """Build the hardware tree structure"""
        self.tree_widget.clear()
        self.system_info_data = system_info
        
        # Create main tree structure
        root = self.tree_widget.invisibleRootItem()
        
        # System Overview
        system_item = QTreeWidgetItem(["💻 Computer"])
        system_item.setData(0, Qt.UserRole, {'type': 'basic', 'data': system_info.get('basic', {})})
        root.addChild(system_item)
        
        # Central Processor Unit
        if 'cpu' in system_info:
            cpu_item = QTreeWidgetItem(["🔧 Central Processor Unit"])
            cpu_item.setData(0, Qt.UserRole, {'type': 'cpu', 'data': system_info['cpu']})
            root.addChild(cpu_item)
        
        # Memory
        if 'memory' in system_info and 'memory_modules' in system_info['memory']:
            memory_root = QTreeWidgetItem(["🧠 Memory"])
            root.addChild(memory_root)
            
            for i, module in enumerate(system_info['memory']['memory_modules']):
                module_name = f"Module #{i+1}"
                if module.get('slot_location', 'N/A') != 'N/A':
                    module_name = f"Slot {module['slot_location']}"
                elif module.get('size', 'N/A') != 'N/A':
                    module_name = f"Module #{i+1} ({module['size']})"
                
                module_item = QTreeWidgetItem([f"📦 {module_name}"])
                module_item.setData(0, Qt.UserRole, {'type': 'memory_module', 'data': module})
                memory_root.addChild(module_item)
        
        # Graphics
        if 'graphics' in system_info and 'graphics_cards' in system_info['graphics']:
            graphics_root = QTreeWidgetItem(["🎮 Graphics"])
            root.addChild(graphics_root)
            
            for i, card in enumerate(system_info['graphics']['graphics_cards']):
                card_name = card.get('graphics_card', f'Graphics Card #{i+1}')
                if len(card_name) > 40:
                    card_name = card_name[:37] + "..."
                
                card_item = QTreeWidgetItem([f"🖥️ {card_name}"])
                card_item.setData(0, Qt.UserRole, {'type': 'graphics_card', 'data': card})
                graphics_root.addChild(card_item)
        
        # Storage
        if 'storage' in system_info:
            storage_root = QTreeWidgetItem(["💾 Storage"])
            root.addChild(storage_root)
            
            if 'drives' in system_info['storage']:
                for drive in system_info['storage']['drives']:
                    drive_name = f"{drive.get('device', 'Drive')} ({drive.get('total_size', 'N/A')})"
                    drive_item = QTreeWidgetItem([f"💿 {drive_name}"])
                    drive_item.setData(0, Qt.UserRole, {'type': 'drive', 'data': drive})
                    storage_root.addChild(drive_item)
            
            if 'physical_drives' in system_info['storage']:
                for i, drive in enumerate(system_info['storage']['physical_drives']):
                    drive_name = drive.get('model', f'Physical Drive #{i+1}')
                    drive_item = QTreeWidgetItem([f"🔧 {drive_name}"])
                    drive_item.setData(0, Qt.UserRole, {'type': 'physical_drive', 'data': drive})
                    storage_root.addChild(drive_item)
        
        # Network
        if 'network' in system_info:
            network_root = QTreeWidgetItem(["🌐 Network"])
            root.addChild(network_root)
            
            if 'network_adapters' in system_info['network']:
                for adapter in system_info['network']['network_adapters']:
                    adapter_name = adapter.get('network_card', 'Network Adapter')
                    if len(adapter_name) > 35:
                        adapter_name = adapter_name[:32] + "..."
                    adapter_item = QTreeWidgetItem([f"🔌 {adapter_name}"])
                    adapter_item.setData(0, Qt.UserRole, {'type': 'network_adapter', 'data': adapter})
                    network_root.addChild(adapter_item)
        
        # Hardware Information
        if 'hardware' in system_info:
            hardware_item = QTreeWidgetItem(["⚙️ Motherboard"])
            hardware_item.setData(0, Qt.UserRole, {'type': 'hardware', 'data': system_info['hardware']})
            root.addChild(hardware_item)
        
        # Expand main categories
        for i in range(root.childCount()):
            item = root.child(i)
            item.setExpanded(True)
        
    def _on_tree_item_clicked(self, item, column):
        """Handle tree item click to show detailed information"""
        data = item.data(0, Qt.UserRole)
        if data:
            self._display_component_info(data['type'], data['data'])
    
    def _display_component_info(self, component_type, component_data):
        """Display detailed information for the selected component"""
        # Clear current info layout completely
        while self.info_layout.count():
            child = self.info_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Create title
        title_map = {
            'basic': 'Computer Information',
            'cpu': 'Central Processor Unit',
            'memory_module': 'Memory Module',
            'graphics_card': 'Graphics Card',
            'monitor': 'Monitor',
            'pnp_monitor': 'Monitor (PnP)',
            'drive': 'Disk Drive',
            'physical_drive': 'Physical Drive',
            'network_adapter': 'Network Adapter',
            'hardware': 'Motherboard'
        }
        
        title_label = QLabel(title_map.get(component_type, 'Component Information'))
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50;")
        self.info_layout.addWidget(title_label)
        
        # Create information table
        if isinstance(component_data, dict):
            self._create_info_table(component_data)
        else:
            error_label = QLabel("No data available")
            error_label.setStyleSheet("color: #888888; font-style: italic;")
            self.info_layout.addWidget(error_label)
        
        # Add stretch at the end to push content to top
        self.info_layout.addStretch()
    
    def _create_info_table(self, data):
        """Create a table displaying component information"""
        table_frame = QFrame()
        table_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 5px;
            }
        """)
        table_layout = QGridLayout(table_frame)
        table_layout.setContentsMargins(15, 15, 15, 15)
        table_layout.setSpacing(8)
        
        row = 0
        for key, value in data.items():
            if key == 'error':
                continue
            
            # Skip entries that show "Not available via WMI" or similar
            if isinstance(value, str) and ('not available' in value.lower() or 'not exposed' in value.lower()):
                continue
            
            # Format key
            display_key = key.replace('_', ' ').title()
            key_label = QLabel(f"{display_key}:")
            key_label.setFont(QFont("Arial", 10, QFont.Bold))
            key_label.setStyleSheet("color: #ffffff; min-width: 150px; padding: 5px;")
            key_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            
            # Format value
            if isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    # Handle list of dictionaries
                    value_text = ""
                    for i, item in enumerate(value):
                        value_text += f"Item {i+1}:\n"
                        for k, v in item.items():
                            # Skip unavailable entries in nested dictionaries too
                            if isinstance(v, str) and ('not available' in v.lower() or 'not exposed' in v.lower()):
                                continue
                            value_text += f"  {k.replace('_', ' ').title()}: {v}\n"
                        value_text += "\n"
                else:
                    # Handle simple list
                    value_text = "\n".join([f"• {item}" for item in value])
            else:
                value_text = str(value)
            
            # Skip if the final value is empty or just whitespace
            if not value_text.strip():
                continue
            
            value_label = QLabel(value_text)
            value_label.setFont(QFont("Arial", 10))
            value_label.setStyleSheet("color: #cccccc; padding: 5px;")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            
            # Add alternating row colors with consistent alignment
            if row % 2 == 0:
                key_label.setStyleSheet(key_label.styleSheet() + " background-color: #333333;")
                value_label.setStyleSheet(value_label.styleSheet() + " background-color: #333333;")
            
            table_layout.addWidget(key_label, row, 0)
            table_layout.addWidget(value_label, row, 1)
            row += 1
        
        # Set column stretch
        table_layout.setColumnStretch(0, 0)
        table_layout.setColumnStretch(1, 1)
        
        self.info_layout.addWidget(table_frame)
        
    def _export_to_text(self):
        """Export system information to text file"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            filename, _ = QFileDialog.getSaveFileName(
                self, 
                "Export System Information", 
                f"system_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self._format_info_as_text())
                
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Export Complete", f"System information exported to:\n{filename}")
                
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Export Error", f"Failed to export system information:\n{str(e)}")
            
    def _copy_to_clipboard(self):
        """Copy system information to clipboard"""
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self._format_info_as_text())
            
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Copied", "System information copied to clipboard!")
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Copy Error", f"Failed to copy to clipboard:\n{str(e)}")
            
    def _format_info_as_text(self):
        """Format system information as plain text"""
        text = "SYSTEM INFORMATION REPORT\n"
        text += "=" * 50 + "\n"
        text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for category, info in self.system_info_data.items():
            text += f"{category.upper().replace('_', ' ')}\n"
            text += "-" * 30 + "\n"
            
            if isinstance(info, dict):
                for key, value in info.items():
                    if key == 'error':
                        continue
                    
                    display_key = key.replace('_', ' ').title()
                    
                    if isinstance(value, list):
                        if all(isinstance(item, dict) for item in value):
                            text += f"{display_key}:\n"
                            for i, item in enumerate(value):
                                text += f"  Item {i+1}:\n"
                                for k, v in item.items():
                                    text += f"    {k.replace('_', ' ').title()}: {v}\n"
                        else:
                            text += f"{display_key}:\n"
                            for item in value:
                                text += f"  • {item}\n"
                    else:
                        text += f"{display_key}: {value}\n"
            else:
                text += f"Data: {info}\n"
            
            text += "\n"
        
        return text 