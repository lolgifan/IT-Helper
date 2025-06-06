import os
import ctypes
import shutil
import time
import sys
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal, Slot, QPoint, QModelIndex, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel,
    QTreeView, QGroupBox, QFormLayout, QCheckBox, QFileDialog, QMessageBox,
    QInputDialog, QMenu, QApplication, QSpacerItem, QSizePolicy, QProgressBar
)
from PySide6.QtGui import QFont, QStandardItemModel, QStandardItem

import disk_utilities
from shared_components import SortableSizeStandardItem

# Compile-time optimization: disable debug prints in release builds
DEBUG_MODE = getattr(sys, '_called_from_test', False) or __debug__

def debug_print(msg):
    """Print debug messages only in debug mode"""
    if DEBUG_MODE:
        print(msg)

# Constants for file grouping
FILES_GROUP_DATA_ROLE = Qt.UserRole + 10  # Custom role to store direct_files list for a files_group node
PARENT_FOLDER_PATH_ROLE = Qt.UserRole + 11  # Store parent folder path for state tracking
RAW_FOLDER_DATA_ROLE = Qt.UserRole + 12  # Store raw folder data for dynamic expansion
FOLDER_EXPANDED_ROLE = Qt.UserRole + 13  # Track if folder has been dynamically expanded


class DiskAnalyzerWorker(QThread):
    """Worker thread for disk analysis"""
    analysis_complete = Signal(dict)
    analysis_error = Signal(str)
    analysis_progress = Signal(str)
    # New signal for real-time file/folder discovery
    item_discovered = Signal(dict)  # Emits individual files/folders as they're found
    # New signals for progress tracking
    progress_update = Signal(int, int, str)  # folders_scanned, files_scanned, current_path
    progress_percentage = Signal(int)  # overall progress percentage (0-100)

    def __init__(self, path_to_analyze, use_fast_scan=True, ultra_fast=False, mft_direct=False, parent=None):
        super().__init__(parent)
        self.path_to_analyze = path_to_analyze
        self.use_fast_scan = use_fast_scan
        self.ultra_fast = ultra_fast
        self.mft_direct = mft_direct
        self._cancelled = False
        
        # Progress tracking
        self.folders_scanned = 0
        self.files_scanned = 0
        self.last_progress_time = 0
        self.start_time = 0
        self.current_path = ""
        
        # Final result tracking for realistic estimates
        self.estimated_total_files = 0
        self.estimated_total_folders = 0
        self.scanning_complete = False

    def run(self):
        """Run the disk analysis"""
        try:
            debug_print(f"DiskAnalyzerWorker: Starting analysis of {self.path_to_analyze}")
            debug_print(f"Using MFT Direct scanning (falls back to optimized scanning if not admin)")
            
            # Initialize tracking
            self.start_time = time.time()
            self.last_progress_time = self.start_time
            
            def progress_callback(current_path):
                if not self._cancelled:
                    self.analysis_progress.emit(f"Analyzing: {current_path}")
                    
            def cancel_check():
                return self._cancelled
                
            def item_callback(item_data):
                """Callback for when individual items are discovered"""
                if not self._cancelled:
                    self.item_discovered.emit(item_data)
                    
                    # Update counters based on item type
                    item_type = item_data.get('type', '')
                    if item_type == 'folder' or item_type == 'folder_start':
                        self.folders_scanned += 1
                    elif item_type == 'file':
                        self.files_scanned += 1
                    
                    # Always update current path for better tracking
                    new_path = item_data.get('path', '')
                    if new_path:
                        self.current_path = new_path
                    
                    # Emit progress update every 0.5 seconds (keep existing logic)
                    current_time = time.time()
                    if current_time - self.last_progress_time >= 0.5:
                        self.last_progress_time = current_time
                        
                        # Calculate simulated progress percentage
                        elapsed_time = current_time - self.start_time
                        
                        # Get estimated counts for more realistic display
                        estimated_files, estimated_folders = self.get_estimated_counts(elapsed_time)
                        progress_percentage = self._calculate_progress_percentage(elapsed_time, 0)
                        
                        self.progress_update.emit(estimated_folders, estimated_files, self.current_path)
                        self.progress_percentage.emit(progress_percentage)
                
            # Use MFT direct access for maximum speed, with fallbacks
            if self.mft_direct:
                # Use MFT direct access for maximum speed
                result = disk_utilities.analyze_directory_mft_direct(
                    self.path_to_analyze,
                    check_cancelled_callback=cancel_check,
                    item_discovered_callback=item_callback
                )
            elif self.ultra_fast:
                # Use ultra-fast parallel processing as fallback
                result = disk_utilities.analyze_directory_parallel(
                    self.path_to_analyze,
                    current_depth=0,
                    max_depth=10,
                    check_cancelled_callback=cancel_check,
                    item_discovered_callback=item_callback,
                    max_workers=4
                )
            elif self.use_fast_scan:
                # Use optimized scanning as fallback
                result = disk_utilities.analyze_directory_recursively_optimized(
                    self.path_to_analyze,
                    current_depth=0,
                    max_depth=10,
                    check_cancelled_callback=cancel_check,
                    item_discovered_callback=item_callback,
                    batch_size=50
                )
            else:
                # Use basic real-time scanning as final fallback
                result = disk_utilities.analyze_directory_recursively_realtime(
                    self.path_to_analyze,
                    current_depth=0,
                    max_depth=10,
                    check_cancelled_callback=cancel_check,
                    item_discovered_callback=item_callback
                )
            
            if not self._cancelled:
                # Extract final totals from result for accurate reporting
                if result:
                    self.estimated_total_files = result.get('file_count', 0)
                    self.estimated_total_folders = result.get('folder_count', 0)
                    self.scanning_complete = True
                    debug_print(f"✅ Scan completed: {self.estimated_total_files:,} files, {self.estimated_total_folders:,} folders")
                
                # Final progress update with real totals
                self.progress_update.emit(self.estimated_total_files, self.estimated_total_folders, "Analysis complete")
                self.progress_percentage.emit(100)
                self.analysis_complete.emit(result)
            else:
                debug_print("DiskAnalyzerWorker: Analysis was cancelled")
                
        except Exception as e:
            error_msg = f"Analysis failed: {e}"
            debug_print(f"DiskAnalyzerWorker error: {error_msg}")
            self.analysis_error.emit(error_msg)

    def stop(self):
        """Stop the analysis"""
        debug_print("DiskAnalyzerWorker: Stop requested")
        self._cancelled = True

    def is_cancelled(self):
        """Check if analysis is cancelled"""
        return self._cancelled

    def _calculate_progress_percentage(self, elapsed_time, total_items):
        """Calculate simulated progress percentage based on time and items"""
        # Use a logarithmic curve to simulate realistic progress
        # Start fast, then slow down, then speed up at the end
        
        if elapsed_time < 1:
            # First second: 0-15%
            return min(15, elapsed_time * 15)
        elif elapsed_time < 5:
            # Next 4 seconds: 15-60%
            return min(60, 15 + (elapsed_time - 1) * 11.25)
        elif elapsed_time < 10:
            # Next 5 seconds: 60-85%
            return min(85, 60 + (elapsed_time - 5) * 5)
        else:
            # After 10 seconds: 85-95% (slow down)
            return min(95, 85 + (elapsed_time - 10) * 1)
            
        # Note: Final jump to 100% happens when analysis completes

    def get_estimated_counts(self, elapsed_time):
        """Get estimated file and folder counts based on scanning progress"""
        if self.scanning_complete:
            return self.estimated_total_files, self.estimated_total_folders
            
        # If we have some real data from callbacks, use that as a base
        base_files = max(self.files_scanned, 1)
        base_folders = max(self.folders_scanned, 1)
        
        # For typical drives, estimate based on time progression
        # Most MFT scans complete in 1-10 seconds
        if elapsed_time < 1:
            # Early stage: show some progress
            estimated_files = min(1000, base_files * 100)
            estimated_folders = min(500, base_folders * 50)
        elif elapsed_time < 3:
            # Mid stage: ramp up estimates
            estimated_files = min(20000, base_files * 500)
            estimated_folders = min(5000, base_folders * 200)
        elif elapsed_time < 8:
            # Late stage: approach realistic numbers
            estimated_files = min(50000, base_files * 1000)
            estimated_folders = min(20000, base_folders * 500)
        else:
            # Very late stage: high estimates
            estimated_files = min(100000, base_files * 2000)
            estimated_folders = min(50000, base_folders * 1000)
            
        return estimated_files, estimated_folders


class DiskAnalyzerWidget(QWidget):
    """Disk Analyzer utility widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize data structures
        self.raw_analysis_root_node = None
        self.current_custom_folder_path = None
        self.analysis_worker = None
        self.manually_expanded_folders_paths = set()  # Track manually expanded file groups
        self.scan_start_time = None  # Track scan duration
        
        # Initialize progress tracking (no popup dialog)
        self.progress_timer = None
        
        # Initialize UI
        self._init_ui()
        self._setup_disk_analyzer_page_components()
        
    def _init_ui(self):
        """Initialize the disk analyzer UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel("Disk Space Analyzer (Admin Required)")
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Controls section
        self._create_controls_section(layout)
        
        # Drive info section
        self._create_drive_info_section(layout)
        
        # Results tree section
        self._create_results_section(layout)
        
    def _create_controls_section(self, parent_layout):
        """Create the controls section"""
        controls_layout = QHBoxLayout()
        
        # Drive selection
        controls_layout.addWidget(QLabel("Target:"))
        
        self.drive_select_combo = QComboBox()
        self.drive_select_combo.setPlaceholderText("Select a Drive")
        self.drive_select_combo.setMinimumWidth(150)
        self.drive_select_combo.currentIndexChanged.connect(self._on_disk_analyzer_drive_selected)
        controls_layout.addWidget(self.drive_select_combo)

        # Analyze button (moved to first position)
        self.scan_path_button = QPushButton("🔍 Analyze Drive")
        self.scan_path_button.clicked.connect(self._start_disk_analysis)
        controls_layout.addWidget(self.scan_path_button)

        # Cancel button (moved to second position)
        self.cancel_scan_button = QPushButton("❌ Cancel Scan")
        self.cancel_scan_button.setEnabled(False)
        self.cancel_scan_button.clicked.connect(self._cancel_disk_analysis)
        controls_layout.addWidget(self.cancel_scan_button)

        # Select folder button (moved to third position, removed dots)
        self.select_folder_button = QPushButton("📁 Select Folder")
        self.select_folder_button.clicked.connect(self._on_select_folder_clicked)
        controls_layout.addWidget(self.select_folder_button)

        # Open as Admin button (new)
        self.open_as_admin_button = QPushButton("🔐 Open as Admin")
        self.open_as_admin_button.clicked.connect(self._on_open_as_admin_clicked)
        self.open_as_admin_button.setToolTip("Restart application with administrator privileges for maximum performance")
        
        # Check if already running as admin
        if self._is_running_as_admin():
            self.open_as_admin_button.setText("🔐 Running as Admin")
            self.open_as_admin_button.setEnabled(False)
            self.open_as_admin_button.setToolTip("Application is already running with administrator privileges")
            
        controls_layout.addWidget(self.open_as_admin_button)

        # Group files checkbox (renamed)
        self.group_files_checkbox = QCheckBox("Group files")
        self.group_files_checkbox.setChecked(True)
        self.group_files_checkbox.stateChanged.connect(self._on_group_files_toggled)
        self.group_files_checkbox.setEnabled(False)
        controls_layout.addWidget(self.group_files_checkbox)

        # Show columns checkbox (updated to only control Path column)
        self.show_columns_checkbox = QCheckBox("Show Path")
        self.show_columns_checkbox.setChecked(False)  # Disabled by default
        self.show_columns_checkbox.stateChanged.connect(self._on_show_columns_toggled)
        controls_layout.addWidget(self.show_columns_checkbox)

        controls_layout.addStretch(1)
        parent_layout.addLayout(controls_layout)

        # Custom folder display
        self.custom_folder_display_layout = QHBoxLayout()
        self.custom_folder_label_prefix = QLabel("Scanning Folder:")
        self.custom_folder_label = QLabel("None selected (Uses drive if blank)")
        self.custom_folder_label.setStyleSheet("font-style: italic; color: #aaa;")
        self.custom_folder_display_layout.addWidget(self.custom_folder_label_prefix)
        self.custom_folder_display_layout.addWidget(self.custom_folder_label, 1)
        self.custom_folder_label_prefix.hide()
        self.custom_folder_label.hide()
        parent_layout.addLayout(self.custom_folder_display_layout)
        
    def _create_drive_info_section(self, parent_layout):
        """Create the drive information section"""
        # Create horizontal layout to place Information and Progress side by side
        info_progress_layout = QHBoxLayout()
        
        # Drive info group (left side)
        drive_info_group = QGroupBox("Information")
        drive_info_form_layout = QFormLayout(drive_info_group)
        
        self.total_space_label = QLabel("N/A")
        self.free_space_label = QLabel("N/A")
        self.occupied_space_label = QLabel("N/A")
        self.scan_time_label = QLabel("N/A")
        
        drive_info_form_layout.addRow("Total Space:", self.total_space_label)
        drive_info_form_layout.addRow("Free Space (Overall):", self.free_space_label)
        drive_info_form_layout.addRow("Occupied Space:", self.occupied_space_label)
        drive_info_form_layout.addRow("Last Scan Time:", self.scan_time_label)
        
        info_progress_layout.addWidget(drive_info_group)
        
        # Progress group (right side)
        self.progress_group = QGroupBox("Scanning Progress")
        progress_form_layout = QFormLayout(self.progress_group)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 4px;
                text-align: center;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        # Progress labels
        self.progress_status_label = QLabel("Ready to scan")
        self.progress_status_label.setStyleSheet("color: #666; font-style: italic;")
        
        self.progress_folders_label = QLabel("Folders: 0")
        self.progress_files_label = QLabel("Files: 0")
        self.progress_scan_status_label = QLabel("Not scanning")
        self.progress_scan_status_label.setStyleSheet("color: #888; font-size: 11px;")
        
        # Add to form layout
        progress_form_layout.addRow("Status:", self.progress_status_label)
        progress_form_layout.addRow("Progress:", self.progress_bar)
        progress_form_layout.addRow("📁 Folders:", self.progress_folders_label)
        progress_form_layout.addRow("📄 Files:", self.progress_files_label)
        progress_form_layout.addRow("Scan Status:", self.progress_scan_status_label)
        
        # Initially hide the progress group
        self.progress_group.setVisible(False)
        
        info_progress_layout.addWidget(self.progress_group)
        
        # Make both groups the same width
        info_progress_layout.setStretch(0, 1)  # Information group
        info_progress_layout.setStretch(1, 1)  # Progress group
        
        parent_layout.addLayout(info_progress_layout)
        
    def _create_results_section(self, parent_layout):
        """Create the results tree section"""
        # Results tree
        self.disk_results_tree = QTreeView()
        self.disk_tree_model = QStandardItemModel()
        
        # Set up tree headers (removed Type column)
        self.disk_tree_column_headers = ['Name', '% of Parent', 'Size', 'Files', 'Folders', 'Last Modification', 'Path']
        self.disk_tree_model.setHorizontalHeaderLabels(self.disk_tree_column_headers)
        
        # Column indexes (adjusted after removing Type column)
        self.disk_tree_name_col_idx = 0
        self.disk_tree_percent_col_idx = 1
        self.disk_tree_size_col_idx = 2
        self.disk_tree_files_col_idx = 3
        self.disk_tree_folders_col_idx = 4
        self.disk_tree_last_mod_col_idx = 5
        self.disk_tree_path_col_idx = 6
        
        self.disk_results_tree.setModel(self.disk_tree_model)
        self.disk_results_tree.header().setSortIndicatorShown(True)
        self.disk_results_tree.setSortingEnabled(True)
        self.disk_results_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.disk_results_tree.customContextMenuRequested.connect(self._show_disk_tree_context_menu)
        
        # Connect tree expansion/collapse signals
        self.disk_results_tree.expanded.connect(self._on_disk_item_expanded)
        self.disk_results_tree.collapsed.connect(self._on_disk_item_collapsed)
        
        parent_layout.addWidget(self.disk_results_tree, stretch=1)
        
    def _setup_disk_analyzer_page_components(self):
        """Setup disk analyzer components"""
        # Populate drive selection combo box
        try:
            drives = disk_utilities.get_logical_drives_with_types()
            self.drive_select_combo.clear()
            
            for drive_info in drives:
                drive_path = drive_info['drive']
                drive_name = drive_info['name']
                self.drive_select_combo.addItem(drive_name, userData=drive_path)
            
            # Automatically select the first drive to populate space information
            if drives:
                self.drive_select_combo.setCurrentIndex(0)
                
        except Exception as e:
            debug_print(f"Error populating drives: {e}")
            
        # Set initial column visibility - Path column is hidden by default
        self.disk_results_tree.setColumnHidden(self.disk_tree_path_col_idx, True)
        
    @Slot(int)
    def _on_disk_analyzer_drive_selected(self, index):
        """Handle drive selection change"""
        if index >= 0:
            # Clear custom folder path when drive is selected
            self.current_custom_folder_path = None
            self.custom_folder_label_prefix.hide()
            self.custom_folder_label.hide()
            
            # Update button text back to drive analysis
            self.scan_path_button.setText("🔍 Analyze Drive")
            
            drive_path = self.drive_select_combo.itemData(index)
            if drive_path:
                try:
                    space_info = disk_utilities.get_drive_space_info(drive_path)
                    if space_info:
                        total_bytes = space_info['total_bytes']
                        total_free_bytes = space_info['total_free_bytes']
                        occupied_bytes = total_bytes - total_free_bytes  # Calculate occupied space
                        
                        self.total_space_label.setText(self._format_bytes_for_display(total_bytes))
                        self.free_space_label.setText(self._format_bytes_for_display(total_free_bytes))
                        self.occupied_space_label.setText(self._format_bytes_for_display(occupied_bytes))
                    else:
                        self.total_space_label.setText("N/A")
                        self.free_space_label.setText("N/A")
                        self.occupied_space_label.setText("N/A")
                except Exception as e:
                    debug_print(f"Error getting drive space info: {e}")
                    self.total_space_label.setText("N/A")
                    self.free_space_label.setText("N/A")
                    self.occupied_space_label.setText("N/A")
                    
    def _start_disk_analysis(self, path_override=None):
        """Start disk analysis"""
        if self.analysis_worker and self.analysis_worker.isRunning():
            QMessageBox.warning(self, "Analysis Running", "An analysis is already in progress.")
            return
            
        # Determine path to analyze
        if path_override:
            target_path = path_override
        elif self.current_custom_folder_path:
            target_path = self.current_custom_folder_path
        else:
            drive_index = self.drive_select_combo.currentIndex()
            if drive_index < 0:
                QMessageBox.warning(self, "No Selection", "Please select a drive or folder to analyze.")
                return
            target_path = self.drive_select_combo.itemData(drive_index)
            
        if not target_path or not os.path.exists(target_path):
            QMessageBox.warning(self, "Invalid Path", "The selected path does not exist.")
            return
            
        # Clear previous results
        self.disk_tree_model.clear()
        self.disk_tree_model.setHorizontalHeaderLabels(self.disk_tree_column_headers)
        
        # Show and initialize embedded progress display
        self.progress_group.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_status_label.setText("Initializing scan...")
        self.progress_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.progress_folders_label.setText("Folders: 0")
        self.progress_files_label.setText("Files: 0")
        self.progress_scan_status_label.setText("Starting scan...")
        
        # Create progress timer to ensure regular updates
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress_from_timer)
        self.progress_timer.start(500)  # Update every 0.5 seconds
        
        # Always use MFT direct scanning for maximum performance
        use_fast_scan = True  # Keep as fallback
        ultra_fast = False    # Keep as fallback  
        mft_direct = True     # Always use MFT direct
        
        # Create and start worker
        self.analysis_worker = DiskAnalyzerWorker(target_path, use_fast_scan, ultra_fast, mft_direct, self)
        self.analysis_worker.analysis_complete.connect(self._handle_analysis_completion)
        self.analysis_worker.analysis_error.connect(self._on_disk_analysis_error)
        self.analysis_worker.analysis_progress.connect(self._on_disk_analysis_progress)
        self.analysis_worker.item_discovered.connect(self._handle_item_discovered)
        self.analysis_worker.progress_update.connect(self._handle_progress_update)
        self.analysis_worker.progress_percentage.connect(self._handle_progress_percentage)
        self.analysis_worker.finished.connect(self._on_disk_analysis_finished)
        
        # Initialize real-time tracking state
        self.realtime_items = {}  # path -> tree item mapping
        self.realtime_pending_folders = {}  # folders waiting for children
        
        # Start scan timer
        self.scan_start_time = time.time()
        self.scan_time_label.setText("Scanning...")
        
        # Update UI state
        self.scan_path_button.setEnabled(False)
        self.cancel_scan_button.setEnabled(True)
        self.group_files_checkbox.setEnabled(False)
        
        # Start analysis
        self.analysis_worker.start()
        debug_print(f"Started disk analysis of: {target_path} (Using MFT Direct scanning)")
        
        # Send initial progress update to embedded display
        self._update_progress_display(0, 0, "Initializing...", 0)
        
    @Slot(dict)
    def _handle_analysis_completion(self, raw_analysis_root_node):
        """Handle completion of disk analysis"""
        self.raw_analysis_root_node = raw_analysis_root_node
        
        # Update embedded progress display to show completion with real totals
        if raw_analysis_root_node:
            real_files = raw_analysis_root_node.get('file_count', 0)
            real_folders = raw_analysis_root_node.get('folder_count', 0)
            debug_print(f"🎉 Showing final totals: {real_files:,} files, {real_folders:,} folders")
            
            # Update the embedded display with real final counts
            self._update_progress_display(real_folders, real_files, "Scan completed successfully!", 100)
            self.progress_status_label.setText("✅ Completed")
            self.progress_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        
        # Calculate and display scan time
        if self.scan_start_time:
            elapsed_time = time.time() - self.scan_start_time
            scan_time_str = self._format_scan_time(elapsed_time)
            self.scan_time_label.setText(scan_time_str)
        
        self._build_tree_model_from_raw_data()
        
    def _format_scan_time(self, elapsed_seconds):
        """Format elapsed time for display"""
        if elapsed_seconds < 1:
            return f"{elapsed_seconds*1000:.0f} ms"
        elif elapsed_seconds < 60:
            return f"{elapsed_seconds:.1f} seconds"
        elif elapsed_seconds < 3600:
            minutes = int(elapsed_seconds // 60)
            seconds = elapsed_seconds % 60
            return f"{minutes}m {seconds:.1f}s"
        else:
            hours = int(elapsed_seconds // 3600)
            minutes = int((elapsed_seconds % 3600) // 60)
            seconds = elapsed_seconds % 60
            return f"{hours}h {minutes}m {seconds:.0f}s"
        
    def _build_tree_model_from_raw_data(self):
        """Build the tree model from raw analysis data"""
        if not self.raw_analysis_root_node:
            debug_print("ERROR: No raw analysis root node data available")
            return
            
        debug_print(f"DEBUG: Building tree from root node:")
        debug_print(f"   - Name: {self.raw_analysis_root_node.get('name', 'Unknown')}")
        debug_print(f"   - Path: {self.raw_analysis_root_node.get('path', 'Unknown')}")
        debug_print(f"   - Type: {self.raw_analysis_root_node.get('type', 'Unknown')}")
        debug_print(f"   - Size: {self.raw_analysis_root_node.get('size', 0)}")
        debug_print(f"   - File count: {self.raw_analysis_root_node.get('file_count', 0)}")
        debug_print(f"   - Folder count: {self.raw_analysis_root_node.get('folder_count', 0)}")
        debug_print(f"   - Direct files: {len(self.raw_analysis_root_node.get('direct_files', []))}")
        debug_print(f"   - Sub folders: {len(self.raw_analysis_root_node.get('sub_folders', []))}")
        debug_print(f"   - Scan method: {self.raw_analysis_root_node.get('scan_method', 'Unknown')}")
            
        self.disk_tree_model.clear()
        self.disk_tree_model.setHorizontalHeaderLabels(self.disk_tree_column_headers)
        
        root_item = self.disk_tree_model.invisibleRootItem()
        
        # Add the root node data with initial shallow depth, but enable dynamic expansion
        self._add_items_recursively_from_raw_node(
            root_item, 
            self.raw_analysis_root_node, 
            current_display_depth=0, 
            max_display_depth=2,  # Start with 2 levels, then expand dynamically
            root_scan_total_size=self.raw_analysis_root_node.get('size', 1),
            enable_dynamic_expansion=True
        )
        
        debug_print(f"DEBUG: Tree model built, root item has {root_item.rowCount()} children")
        
        # Expand first level
        self.disk_results_tree.expandToDepth(0)
        
        # Resize columns to content
        for i in range(self.disk_tree_model.columnCount()):
            self.disk_results_tree.resizeColumnToContents(i)
            
        # Set default sorting to Size column (index 2) in descending order (biggest to smallest)
        # This is done after data is loaded to ensure proper sorting
        self.disk_results_tree.sortByColumn(self.disk_tree_size_col_idx, Qt.DescendingOrder)
        
        # Ensure Path column visibility matches checkbox state after rebuilding
        show_path = self.show_columns_checkbox.isChecked()
        self.disk_results_tree.setColumnHidden(self.disk_tree_path_col_idx, not show_path)
            
    def _add_items_recursively_from_raw_node(self, parent_qt_item, current_raw_node_data, 
                                           current_display_depth, max_display_depth, root_scan_total_size,
                                           enable_dynamic_expansion=False):
        """Recursively add items to the tree model"""
        if current_display_depth > max_display_depth and not enable_dynamic_expansion:
            return
            
        node_name = current_raw_node_data.get('name', 'Unknown')
        node_size = current_raw_node_data.get('size', 0)
        node_type = current_raw_node_data.get('type', 'unknown')
        node_path = current_raw_node_data.get('path', '')
        node_file_count = current_raw_node_data.get('file_count', 0)
        node_folder_count = current_raw_node_data.get('folder_count', 0)
        node_last_modified = current_raw_node_data.get('last_modified_timestamp', 0)
        
        # Calculate percentage of parent
        parent_size = getattr(parent_qt_item, '_node_size', root_scan_total_size)
        if parent_size > 0:
            percentage = (node_size / parent_size) * 100
        else:
            percentage = 0
            
        # Create row items
        row_items = []
        
        # Name column
        name_item = QStandardItem(f"📁 {node_name}")  # Add folder icon
        name_item._node_size = node_size  # Store for percentage calculations
        
        # Store raw folder data for dynamic expansion
        name_item.setData(current_raw_node_data, RAW_FOLDER_DATA_ROLE)
        name_item.setData(False, FOLDER_EXPANDED_ROLE)  # Mark as not dynamically expanded yet
        
        row_items.append(name_item)
        
        # Percentage column
        percent_item = QStandardItem(self._create_percentage_bar(percentage))
        percent_item.setData(percentage)
        row_items.append(percent_item)
        
        # Size column (sortable)
        size_item = SortableSizeStandardItem(self._format_bytes_for_display(node_size))
        size_item.setData(node_size, Qt.UserRole)
        row_items.append(size_item)
        
        # Files column
        files_item = QStandardItem(str(node_file_count))
        files_item.setData(node_file_count)
        row_items.append(files_item)
        
        # Folders column
        folders_item = QStandardItem(str(node_folder_count))
        folders_item.setData(node_folder_count)
        row_items.append(folders_item)
        
        # Last modification column
        if node_last_modified > 0:
            mod_time = datetime.fromtimestamp(node_last_modified).strftime("%Y-%m-%d %H:%M")
        else:
            mod_time = "Unknown"
        mod_item = QStandardItem(mod_time)
        mod_item.setData(node_last_modified)
        row_items.append(mod_item)
        
        # Path column
        path_item = QStandardItem(node_path)
        row_items.append(path_item)
        
        # Add row to parent
        parent_qt_item.appendRow(row_items)
        
        # Get subfolders and files
        sub_folders = current_raw_node_data.get('sub_folders', [])
        direct_files_data = current_raw_node_data.get('direct_files', [])
        
        # SORT BY SIZE: Sort subfolders and files by size (largest first) before adding to tree
        sub_folders_sorted = sorted(sub_folders, key=lambda x: x.get('size', 0), reverse=True)
        direct_files_sorted = sorted(direct_files_data, key=lambda x: x.get('size', 0), reverse=True)
        
        # Add children if within display depth OR if this is the initial load
        should_add_children = (current_display_depth < max_display_depth)
        
        if should_add_children:
            # Add subfolders first (now sorted by size)
            for subfolder in sub_folders_sorted:
                self._add_items_recursively_from_raw_node(
                    name_item, subfolder, current_display_depth + 1, 
                    max_display_depth, root_scan_total_size, enable_dynamic_expansion
                )
                
            # Handle direct files based on grouping setting
            # Check if this folder was manually expanded for file display
            show_individual_files = False
            if not self.group_files_checkbox.isChecked():
                # Global override: if checkbox is OFF, always show individual files
                show_individual_files = True
            elif node_path in self.manually_expanded_folders_paths:
                # This folder was manually expanded, so show individual files
                show_individual_files = True
                
            if show_individual_files and direct_files_sorted:
                # Show individual files (now sorted by size)
                for file_data in direct_files_sorted:
                    self._add_individual_file_item(name_item, file_data, root_scan_total_size)
            elif direct_files_sorted and self.group_files_checkbox.isChecked():
                # Group files into a "[N File(s)]" item (files are already sorted)
                self._create_files_group_item(name_item, direct_files_sorted, node_path, root_scan_total_size)
        else:
            # We're at max depth but have children - add placeholder for dynamic expansion
            if sub_folders or direct_files_data:
                # Add placeholder child to make the expander arrow appear
                placeholder_child = QStandardItem("Loading...")
                placeholder_child.setSelectable(False)
                placeholder_child.setEnabled(False)
                placeholder_child.setData(True, Qt.UserRole + 20)  # Mark as placeholder
                name_item.appendRow(placeholder_child)

    def _create_files_group_item(self, parent_item, direct_files_data, parent_folder_path, root_scan_total_size):
        """Create a grouped files item that can be expanded"""
        files_group_size = sum(f.get('size', 0) for f in direct_files_data)
        files_group_count = len(direct_files_data)
        files_group_mod_time = 0
        
        if direct_files_data:
            files_group_mod_time = max(f.get('last_modified_timestamp', 0) for f in direct_files_data)
        
        group_name_str = f"📄 [{files_group_count} File(s)]"  # Add file icon to group
        group_name_item = QStandardItem(group_name_str)
        group_name_item.setEditable(False)
        
        # Store the actual list of files and parent folder path for expansion
        group_name_item.setData(direct_files_data, FILES_GROUP_DATA_ROLE)
        group_name_item.setData(parent_folder_path, PARENT_FOLDER_PATH_ROLE)
        
        # Add placeholder child to make the expander arrow appear
        if files_group_count > 0:
            placeholder_child = QStandardItem()
            placeholder_child.setSelectable(False)
            placeholder_child.setEnabled(False)
            group_name_item.appendRow(placeholder_child)
        else:
            group_name_item.setEnabled(False)
        
        # Calculate group percentage relative to root_scan_total_size
        group_perc_val = (files_group_size / root_scan_total_size * 100) if root_scan_total_size > 0 else 0
        
        # Create group row items
        group_percentage_item = QStandardItem(self._create_percentage_bar(group_perc_val))
        group_percentage_item.setData(group_perc_val, Qt.UserRole)
        
        group_size_item = SortableSizeStandardItem(self._format_bytes_for_display(files_group_size))
        group_size_item.setData(int(files_group_size), Qt.UserRole)
        
        group_files_item = QStandardItem(str(files_group_count))
        group_files_item.setData(int(files_group_count), Qt.UserRole)
        
        group_folders_item = QStandardItem("-")  # Files group contains 0 folders
        group_folders_item.setData(0, Qt.UserRole)
        
        group_mod_item = QStandardItem(
            datetime.fromtimestamp(files_group_mod_time).strftime('%Y-%m-%d %H:%M') 
            if files_group_mod_time > 0 else "N/A"
        )
        group_mod_item.setData(files_group_mod_time, Qt.UserRole)
        
        group_path_item = QStandardItem(parent_folder_path)
        
        # Add the group row (removed Type column)
        parent_item.appendRow([
            group_name_item, group_percentage_item, group_size_item,
            group_files_item, group_folders_item, group_mod_item,
            group_path_item
        ])

    def _format_bytes_for_display(self, b):
        """Format bytes for display"""
        if b is None:
            return "0 B"
            
        try:
            b = int(b)
        except (ValueError, TypeError):
            return "0 B"
            
        if b == 0:
            return "0 B"
        elif b < 1024:
            return f"{b} B"
        elif b < 1024**2:
            return f"{b/1024:.1f} KB"
        elif b < 1024**3:
            return f"{b/(1024**2):.1f} MB"
        elif b < 1024**4:
            return f"{b/(1024**3):.1f} GB"
        else:
            return f"{b/(1024**4):.1f} TB"
            
    def _create_percentage_bar(self, percentage, bar_length=20):
        """Create a visual percentage bar that fills from left to right"""
        if not isinstance(percentage, (int, float)) or percentage < 0:
            percentage = 0
        elif percentage > 100:
            percentage = 100
            
        filled_chars = int(round((percentage / 100) * bar_length))
        empty_chars = bar_length - filled_chars
        
        # Use block characters for the bar
        bar = '█' * filled_chars + '░' * empty_chars
        return f"[{bar}] {percentage:.1f}%"

    @Slot()
    def _cancel_disk_analysis(self):
        """Cancel the current disk analysis"""
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.stop()
            self.analysis_worker.wait(3000)  # Wait up to 3 seconds
            
        # Stop progress timer
        if self.progress_timer:
            self.progress_timer.stop()
            self.progress_timer = None
            
        # Update progress display to show cancellation
        self.progress_status_label.setText("❌ Cancelled")
        self.progress_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.progress_scan_status_label.setText("Scan was cancelled")
        
        # Hide progress display after delay
        QTimer.singleShot(2000, lambda: self.progress_group.setVisible(False))
            
        # Update scan time on cancellation
        if self.scan_start_time:
            elapsed_time = time.time() - self.scan_start_time
            scan_time_str = f"{self._format_scan_time(elapsed_time)} (Cancelled)"
            self.scan_time_label.setText(scan_time_str)
            
        self.scan_path_button.setEnabled(True)
        self.cancel_scan_button.setEnabled(False)
        
    @Slot()
    def _on_select_folder_clicked(self):
        """Handle select folder button click"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Analyze", ""
        )
        
        if folder_path:
            self.current_custom_folder_path = folder_path
            self.custom_folder_label.setText(folder_path)
            self.custom_folder_label_prefix.show()
            self.custom_folder_label.show()
            
            # Clear drive selection and update button text
            self.drive_select_combo.setCurrentIndex(-1)
            self.scan_path_button.setText("🔍 Analyze Folder")
            
            # Automatically start analysis of the selected folder
            debug_print(f"Auto-starting analysis of selected folder: {folder_path}")
            self._start_disk_analysis()
            
    @Slot()
    def _on_open_as_admin_clicked(self):
        """Handle open as admin button click"""
        try:
            # Get the current script path
            if getattr(sys, 'frozen', False):
                # If running as compiled executable
                script_path = sys.executable
            else:
                # If running as Python script
                script_path = os.path.abspath(sys.argv[0])
                
            # Get current working directory
            cwd = os.getcwd()
            
            # Prepare command arguments to restart with same state
            cmd_args = []
            
            if not getattr(sys, 'frozen', False):
                # If Python script, include Python executable
                cmd_args = [sys.executable, script_path]
            else:
                cmd_args = [script_path]
                
            # Add argument to automatically open disk analyzer
            cmd_args.extend(['--open-disk-analyzer'])
            
            # If there's a custom folder selected, pass it as argument
            if self.current_custom_folder_path:
                cmd_args.extend(['--folder', self.current_custom_folder_path])
            elif self.drive_select_combo.currentIndex() >= 0:
                drive_path = self.drive_select_combo.itemData(self.drive_select_combo.currentIndex())
                if drive_path:
                    cmd_args.extend(['--drive', drive_path])
            
            debug_print(f"Restarting as admin with command: {cmd_args}")
            
            # Use ShellExecuteW to run as administrator
            import ctypes.wintypes
            SW_SHOWNORMAL = 1
            
            # Join arguments for ShellExecuteW
            if len(cmd_args) > 1:
                executable = cmd_args[0]
                parameters = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cmd_args[1:])
            else:
                executable = cmd_args[0]
                parameters = ""
                
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",  # Run as administrator
                executable,
                parameters,
                cwd,
                SW_SHOWNORMAL
            )
            
            if result > 32:  # Success
                debug_print("Successfully started elevated process, closing current instance...")
                # Close current application
                QApplication.instance().quit()
            else:
                QMessageBox.warning(
                    self, 
                    "Admin Restart Failed", 
                    f"Failed to restart as administrator (error code: {result}). "
                    f"You can manually run the application as administrator for better performance."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to restart as administrator: {e}\n\n"
                f"You can manually run the application as administrator for better performance."
            )
            
    def _is_running_as_admin(self):
        """Check if the application is running with administrator privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    @Slot()
    def _on_group_files_toggled(self, state):
        """Handle group files checkbox toggle"""
        # Clear manually expanded folders when toggling grouping
        self.manually_expanded_folders_paths.clear()
        
        if self.raw_analysis_root_node:
            # Rebuild tree with new grouping settings and dynamic expansion enabled
            self._build_tree_model_from_raw_data()
            
    @Slot()
    def _on_show_columns_toggled(self, state):
        """Handle show columns checkbox toggle"""
        show_path = (state == Qt.Checked.value) or (state == Qt.Checked) or (state == 2)
        self.disk_results_tree.setColumnHidden(self.disk_tree_path_col_idx, not show_path)
        debug_print(f"Path column visibility toggled: show_path={show_path}, state={state}")
        
    @Slot(QModelIndex)
    def _on_disk_item_expanded(self, index):
        """Handle disk tree item expansion"""
        item = self.disk_tree_model.itemFromIndex(index)
        if not item:
            return
            
        # Check if this is a files group with placeholder (existing logic)
        stored_files_data = item.data(FILES_GROUP_DATA_ROLE)
        parent_folder_path = item.data(PARENT_FOLDER_PATH_ROLE)
        
        # Check if this is a files group with placeholder
        is_files_group_placeholder = False
        if item.rowCount() == 1:
            placeholder_candidate = item.child(0, 0)
            if placeholder_candidate and not placeholder_candidate.isSelectable() and not placeholder_candidate.isEnabled():
                is_files_group_placeholder = True
                
        if stored_files_data and is_files_group_placeholder:
            # Handle files group expansion (existing logic)
            debug_print(f"Expanding files for group: '{item.text()}' in folder '{parent_folder_path}'")
            
            # Remove placeholder
            item.removeRows(0, item.rowCount())
            
            # Get root size for percentage calculations
            root_scan_total_size = 1
            if self.raw_analysis_root_node:
                root_scan_total_size = self.raw_analysis_root_node.get('size', 1)
            if root_scan_total_size == 0:
                root_scan_total_size = 1
                
            # SORT BY SIZE: Sort files by size (largest first) before expanding
            stored_files_sorted = sorted(stored_files_data, key=lambda x: x.get('size', 0), reverse=True)
                
            # Add individual files (now sorted by size)
            for file_node_data in stored_files_sorted:
                self._add_individual_file_item(item, file_node_data, root_scan_total_size)
                
            # Mark this folder as manually expanded
            if parent_folder_path:
                self.manually_expanded_folders_paths.add(parent_folder_path)
                
            return  # Exit early for files group
            
        # Check if this is a folder with dynamic expansion placeholder
        raw_folder_data = item.data(RAW_FOLDER_DATA_ROLE)
        already_expanded = item.data(FOLDER_EXPANDED_ROLE)
        
        if raw_folder_data and not already_expanded:
            # Check if we have a placeholder child that needs to be replaced
            has_placeholder = False
            if item.rowCount() == 1:
                placeholder_candidate = item.child(0, 0)
                if placeholder_candidate and placeholder_candidate.data(Qt.UserRole + 20):  # Check placeholder marker
                    has_placeholder = True
                    
            if has_placeholder:
                debug_print(f"Dynamic expansion: Loading children for folder '{item.text()}'")
                
                # Remove placeholder
                item.removeRows(0, item.rowCount())
                
                # Get root size for percentage calculations
                root_scan_total_size = 1
                if self.raw_analysis_root_node:
                    root_scan_total_size = self.raw_analysis_root_node.get('size', 1)
                if root_scan_total_size == 0:
                    root_scan_total_size = 1
                    
                # Load children dynamically
                sub_folders = raw_folder_data.get('sub_folders', [])
                direct_files_data = raw_folder_data.get('direct_files', [])
                folder_path = raw_folder_data.get('path', '')
                
                # SORT BY SIZE: Sort subfolders and files by size (largest first) for dynamic expansion
                sub_folders_sorted = sorted(sub_folders, key=lambda x: x.get('size', 0), reverse=True)
                direct_files_sorted = sorted(direct_files_data, key=lambda x: x.get('size', 0), reverse=True)
                
                # Add subfolders with one more level of depth (now sorted by size)
                for subfolder in sub_folders_sorted:
                    self._add_items_recursively_from_raw_node(
                        item, subfolder, 
                        current_display_depth=0,  # Reset depth counter for dynamic expansion
                        max_display_depth=1,  # Add one more level
                        root_scan_total_size=root_scan_total_size, 
                        enable_dynamic_expansion=True
                    )
                    
                # Handle direct files based on grouping setting
                show_individual_files = False
                if not self.group_files_checkbox.isChecked():
                    show_individual_files = True
                elif folder_path in self.manually_expanded_folders_paths:
                    show_individual_files = True
                    
                if show_individual_files and direct_files_sorted:
                    # Show individual files (now sorted by size)
                    for file_data in direct_files_sorted:
                        self._add_individual_file_item(item, file_data, root_scan_total_size)
                elif direct_files_sorted and self.group_files_checkbox.isChecked():
                    # Group files into a "[N File(s)]" item (files are already sorted)
                    self._create_files_group_item(item, direct_files_sorted, folder_path, root_scan_total_size)
                
                # Mark as dynamically expanded
                item.setData(True, FOLDER_EXPANDED_ROLE)
                
                debug_print(f"Dynamic expansion completed: Added {len(sub_folders_sorted)} subfolders and {len(direct_files_sorted)} files")

    def _add_individual_file_item(self, parent_item, file_node_data, root_scan_total_size):
        """Add an individual file item to the tree"""
        file_name = file_node_data.get('name', 'N/A')
        file_size_bytes = file_node_data.get('size', 0)
        file_path = file_node_data.get('path', 'N/A')
        file_mod_time = file_node_data.get('last_modified_timestamp', 0)
        
        # Format modification time
        if file_mod_time > 0:
            try:
                file_mod_str = datetime.fromtimestamp(file_mod_time).strftime('%Y-%m-%d %H:%M')
            except ValueError:
                file_mod_str = "Invalid Date"
        else:
            file_mod_str = "N/A"
            
        # Create file items
        file_name_item = QStandardItem(f"📄 {str(file_name)}")  # Add file icon
        file_name_item.setEditable(False)
        
        # Calculate percentage
        file_perc_val = (file_size_bytes / root_scan_total_size * 100) if root_scan_total_size > 0 else 0.0
        file_percentage_item = QStandardItem(self._create_percentage_bar(file_perc_val))
        file_percentage_item.setData(file_perc_val, Qt.UserRole)
        
        file_size_item = SortableSizeStandardItem(self._format_bytes_for_display(file_size_bytes))
        file_size_item.setData(int(file_size_bytes), Qt.UserRole)
        
        file_files_item = QStandardItem("-")
        file_files_item.setData(1, Qt.UserRole)  # Represents 1 file
        
        file_folders_item = QStandardItem("-")
        file_folders_item.setData(0, Qt.UserRole)
        
        file_mod_item = QStandardItem(file_mod_str)
        file_mod_item.setData(file_mod_time, Qt.UserRole)
        
        file_path_item = QStandardItem(file_path)
        
        parent_item.appendRow([
            file_name_item, file_percentage_item, file_size_item,
            file_files_item, file_folders_item, file_mod_item,
            file_path_item
        ])

    @Slot(QModelIndex)
    def _on_disk_item_collapsed(self, index):
        """Handle disk tree item collapse"""
        item = self.disk_tree_model.itemFromIndex(index)
        if not item:
            return
            
        # Handle files group collapse (existing logic)
        stored_files_data = item.data(FILES_GROUP_DATA_ROLE)
        parent_folder_path = item.data(PARENT_FOLDER_PATH_ROLE)
        
        # Check if this is a files group that was expanded with real files
        if stored_files_data and item.rowCount() > 0:
            is_expanded_with_real_files = False
            
            # Check if it has real files (not placeholder)
            if item.rowCount() > 1:
                is_expanded_with_real_files = True
            elif item.rowCount() == 1:
                child_item = item.child(0, 0)
                if child_item and child_item.isSelectable():
                    is_expanded_with_real_files = True
                    
            if is_expanded_with_real_files:
                debug_print(f"Collapsing files for group: '{item.text()}' in folder '{parent_folder_path}'")
                
                # Remove all children (the actual files)
                item.removeRows(0, item.rowCount())
                
                # Remove from manually expanded set
                if parent_folder_path:
                    self.manually_expanded_folders_paths.discard(parent_folder_path)
                    
                # Add placeholder back if grouping is still enabled
                if self.group_files_checkbox.isChecked() and len(stored_files_data) > 0:
                    placeholder_child = QStandardItem()
                    placeholder_child.setSelectable(False)
                    placeholder_child.setEnabled(False)
                    item.appendRow(placeholder_child)
                    
                return  # Exit early for files group
                
        # Handle dynamic folder collapse
        raw_folder_data = item.data(RAW_FOLDER_DATA_ROLE)
        already_expanded = item.data(FOLDER_EXPANDED_ROLE)
        
        if raw_folder_data and already_expanded:
            # This folder was dynamically expanded - we can optionally reset it to save memory
            # For now, we'll leave it expanded since collapsing and re-expanding should be fast
            # But we could implement a "lazy collapse" here if memory becomes an issue
            debug_print(f"Collapsing dynamically expanded folder: '{item.text()}'")
            
            # Optional: Reset to placeholder to save memory (uncomment if needed)
            # self._reset_folder_to_placeholder(item)
            
    def _reset_folder_to_placeholder(self, folder_item):
        """Reset a dynamically expanded folder back to placeholder state (optional optimization)"""
        raw_folder_data = folder_item.data(RAW_FOLDER_DATA_ROLE)
        if not raw_folder_data:
            return
            
        # Check if folder has children to warrant a placeholder
        sub_folders = raw_folder_data.get('sub_folders', [])
        direct_files_data = raw_folder_data.get('direct_files', [])
        
        if sub_folders or direct_files_data:
            # Remove all children
            folder_item.removeRows(0, folder_item.rowCount())
            
            # Add placeholder back
            placeholder_child = QStandardItem("Loading...")
            placeholder_child.setSelectable(False)
            placeholder_child.setEnabled(False)
            placeholder_child.setData(True, Qt.UserRole + 20)  # Mark as placeholder
            folder_item.appendRow(placeholder_child)
            
            # Reset expansion state
            folder_item.setData(False, FOLDER_EXPANDED_ROLE)
            
            debug_print(f"Reset folder '{folder_item.text()}' to placeholder state")

    def closeEvent(self, event):
        """Handle widget close event"""
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.stop()
            self.analysis_worker.wait()
        event.accept()

    @Slot(dict)
    def _handle_item_discovered(self, item_data):
        """Handle real-time item discovery"""
        try:
            item_type = item_data.get('type')
            item_path = item_data.get('path')
            parent_path = item_data.get('parent_path')
            item_name = item_data.get('name')
            item_depth = item_data.get('depth', 0)
            
            # Skip very deep items to avoid UI clutter during scanning
            if item_depth > 4:
                return
                
            # Get or create parent item
            parent_item = self._get_or_create_parent_item(parent_path, item_depth - 1)
            if not parent_item:
                return
                
            if item_type == 'folder_start':
                # A folder is being scanned - create placeholder
                self._create_realtime_folder_item(parent_item, item_data)
            elif item_type == 'folder':
                # A subfolder was discovered
                self._create_realtime_folder_item(parent_item, item_data)
            elif item_type == 'file':
                # A file was discovered
                self._create_realtime_file_item(parent_item, item_data)
                
        except Exception as e:
            debug_print(f"Error handling item discovery: {e}")
            
    def _get_or_create_parent_item(self, parent_path, depth):
        """Get or create parent item for the given path"""
        if not parent_path:
            return self.disk_tree_model.invisibleRootItem()
            
        # Check if parent already exists
        if parent_path in self.realtime_items:
            return self.realtime_items[parent_path]
            
        # For root level, return root item
        if depth <= 0:
            return self.disk_tree_model.invisibleRootItem()
            
        # Create placeholder parent if needed
        grandparent_path = os.path.dirname(parent_path)
        grandparent_item = self._get_or_create_parent_item(grandparent_path, depth - 1)
        
        if grandparent_item:
            parent_name = os.path.basename(parent_path)
            parent_item = self._create_placeholder_folder_item(grandparent_item, parent_name, parent_path)
            self.realtime_items[parent_path] = parent_item
            return parent_item
            
        return None
        
    def _create_placeholder_folder_item(self, parent_item, name, path):
        """Create a placeholder folder item"""
        row_items = []
        
        # Name column
        name_item = QStandardItem(f"📁 {name} (scanning...)")
        name_item._node_size = 0
        row_items.append(name_item)
        
        # Percentage column
        percent_item = QStandardItem("...")
        row_items.append(percent_item)
        
        # Size column
        size_item = SortableSizeStandardItem("Calculating...")
        row_items.append(size_item)
        
        # Files column
        files_item = QStandardItem("0")
        row_items.append(files_item)
        
        # Folders column
        folders_item = QStandardItem("0")
        row_items.append(folders_item)
        
        # Last modification column
        mod_item = QStandardItem("...")
        row_items.append(mod_item)
        
        # Path column
        path_item = QStandardItem(path)
        row_items.append(path_item)
        
        parent_item.appendRow(row_items)
        return name_item
        
    def _create_realtime_folder_item(self, parent_item, item_data):
        """Create a real-time folder item"""
        item_path = item_data.get('path')
        item_name = item_data.get('name')
        last_modified = item_data.get('last_modified', 0)
        
        # Check if already exists
        if item_path in self.realtime_items:
            return self.realtime_items[item_path]
            
        row_items = []
        
        # Name column
        name_item = QStandardItem(f"📁 {item_name}")
        name_item._node_size = 0
        row_items.append(name_item)
        
        # Percentage column
        percent_item = QStandardItem("...")
        row_items.append(percent_item)
        
        # Size column
        size_item = SortableSizeStandardItem("Calculating...")
        row_items.append(size_item)
        
        # Files column
        files_item = QStandardItem("0")
        row_items.append(files_item)
        
        # Folders column
        folders_item = QStandardItem("0")
        row_items.append(folders_item)
        
        # Last modification column
        if last_modified > 0:
            mod_time = datetime.fromtimestamp(last_modified).strftime("%Y-%m-%d %H:%M")
        else:
            mod_time = "..."
        mod_item = QStandardItem(mod_time)
        row_items.append(mod_item)
        
        # Path column
        path_item = QStandardItem(item_path)
        row_items.append(path_item)
        
        parent_item.appendRow(row_items)
        self.realtime_items[item_path] = name_item
        return name_item
        
    def _create_realtime_file_item(self, parent_item, item_data):
        """Create a real-time file item"""
        item_path = item_data.get('path')
        item_name = item_data.get('name')
        item_size = item_data.get('size', 0)
        last_modified = item_data.get('last_modified', 0)
        
        row_items = []
        
        # Name column
        name_item = QStandardItem(f"📄 {item_name}")
        name_item._node_size = item_size
        row_items.append(name_item)
        
        # Percentage column (will be updated later when we know parent size)
        percent_item = QStandardItem("...")
        row_items.append(percent_item)
        
        # Size column
        size_item = SortableSizeStandardItem(self._format_bytes_for_display(item_size))
        size_item.setData(item_size, Qt.UserRole)
        row_items.append(size_item)
        
        # Files column
        files_item = QStandardItem("1")
        row_items.append(files_item)
        
        # Folders column
        folders_item = QStandardItem("0")
        row_items.append(folders_item)
        
        # Last modification column
        if last_modified > 0:
            mod_time = datetime.fromtimestamp(last_modified).strftime("%Y-%m-%d %H:%M")
        else:
            mod_time = "Unknown"
        mod_item = QStandardItem(mod_time)
        row_items.append(mod_item)
        
        # Path column
        path_item = QStandardItem(item_path)
        row_items.append(path_item)
        
        parent_item.appendRow(row_items)
        return name_item

    @Slot(QPoint)
    def _show_disk_tree_context_menu(self, position):
        """Show context menu for disk tree"""
        index = self.disk_results_tree.indexAt(position)
        if not index.isValid():
            return
            
        # Get the item and path
        item = self.disk_tree_model.itemFromIndex(index)
        if not item:
            return
            
        # Get path from the path column
        path_index = self.disk_tree_model.index(index.row(), self.disk_tree_path_col_idx, index.parent())
        path = self.disk_tree_model.data(path_index)
        
        if not path or not os.path.exists(path):
            return
            
        # Create context menu
        menu = QMenu(self)
        
        # Open action
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._open_disk_item(path))
        
        # Show in Explorer action
        if os.name == 'nt':  # Windows
            explorer_action = menu.addAction("Show in Explorer")
            explorer_action.triggered.connect(lambda: os.startfile(os.path.dirname(path)))
            
        menu.addSeparator()
        
        # Properties action
        properties_action = menu.addAction("Properties")
        properties_action.triggered.connect(lambda: self._show_disk_item_properties(path, "item"))
        
        # Copy path action
        copy_path_action = menu.addAction("Copy Path")
        copy_path_action.triggered.connect(lambda: self._copy_item_as_path(path))
        
        # Show menu
        menu.exec(self.disk_results_tree.mapToGlobal(position))
        
    def _open_disk_item(self, path):
        """Open a disk item"""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(path)
            else:  # macOS/Linux
                import subprocess
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', path])
                else:  # Linux
                    subprocess.run(['xdg-open', path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open {path}: {e}")
            
    def _copy_item_as_path(self, path):
        """Copy item path to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(path)
        
    def _show_disk_item_properties(self, path, item_type_str):
        """Show native properties dialog for item"""
        try:
            if os.name == 'nt':  # Windows
                import subprocess
                subprocess.run(['powershell', '-Command', f'(Get-Item "{path}").VersionInfo'], 
                             shell=True, check=False)
        except Exception as e:
            QMessageBox.information(self, "Properties", f"Path: {path}\nType: {item_type_str}")
            
    @Slot(str)
    def _on_disk_analysis_error(self, error_message):
        """Handle disk analysis error"""
        # Stop progress timer
        if self.progress_timer:
            self.progress_timer.stop()
            self.progress_timer = None
            
        # Update progress display to show error
        self.progress_status_label.setText("❌ Error")
        self.progress_status_label.setStyleSheet("color: #f44336; font-weight: bold;")
        self.progress_scan_status_label.setText("Scan failed")
        
        # Hide progress display after delay
        QTimer.singleShot(2000, lambda: self.progress_group.setVisible(False))
            
        # Update scan time on error
        if self.scan_start_time:
            elapsed_time = time.time() - self.scan_start_time
            scan_time_str = f"{self._format_scan_time(elapsed_time)} (Error)"
            self.scan_time_label.setText(scan_time_str)
        
        QMessageBox.critical(self, "Analysis Error", error_message)
        
    @Slot(str)
    def _on_disk_analysis_progress(self, progress_message):
        """Handle analysis progress updates"""
        # Update a status label or progress bar if needed
        # For now, just print to console
        debug_print(f"Analysis progress: {progress_message}")
        
    @Slot()
    def _on_disk_analysis_finished(self):
        """Handle disk analysis finished"""
        # Stop progress timer
        if self.progress_timer:
            self.progress_timer.stop()
            self.progress_timer = None
            
        self.scan_path_button.setEnabled(True)
        self.cancel_scan_button.setEnabled(False)
        self.group_files_checkbox.setEnabled(True)

    @Slot(int, int, str)
    def _handle_progress_update(self, folders_scanned, files_scanned, current_path):
        """Handle progress updates from the worker"""
        # Show simple scanning status instead of current path
        self._update_progress_display(folders_scanned, files_scanned, "Scanning...", None)
            
    @Slot(int)
    def _handle_progress_percentage(self, percentage):
        """Handle progress percentage updates from the worker"""
        self.progress_bar.setValue(int(percentage))
        
    def _update_progress_display(self, folders_count, files_count, status_message, percentage=None):
        """Update the embedded progress display"""
        self.progress_folders_label.setText(f"📁 Folders: {folders_count:,}")
        self.progress_files_label.setText(f"📄 Files: {files_count:,}")
        self.progress_scan_status_label.setText(status_message)
        
        if percentage is not None:
            self.progress_bar.setValue(int(percentage))

    def _update_progress_from_timer(self):
        """Update progress from timer to ensure regular updates"""
        if self.analysis_worker and self.analysis_worker.isRunning():
            # Calculate elapsed time and get estimated counts
            if hasattr(self.analysis_worker, 'start_time') and self.analysis_worker.start_time > 0:
                elapsed_time = time.time() - self.analysis_worker.start_time
                progress_percentage = self.analysis_worker._calculate_progress_percentage(elapsed_time, 0)
                
                # Get realistic estimates for file and folder counts
                estimated_files, estimated_folders = self.analysis_worker.get_estimated_counts(elapsed_time)
                
                # Update embedded display with estimated counts and simple status
                self._update_progress_display(estimated_folders, estimated_files, "Scanning...", progress_percentage)

    def _close_progress_dialog(self):
        """Hide the embedded progress display"""
        if self.progress_timer:
            self.progress_timer.stop()
            self.progress_timer = None
            
        # Hide the progress group after a delay
        QTimer.singleShot(3000, lambda: self.progress_group.setVisible(False)) 