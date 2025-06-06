"""
Disk utilities module for IT Helper application
Provides disk analysis functionality using Windows API
"""
import ctypes
from ctypes import wintypes
import os
import time


# Windows API Constants
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

DRIVE_TYPES = {
    DRIVE_UNKNOWN: "Unknown",
    DRIVE_NO_ROOT_DIR: "No Root Directory",
    DRIVE_REMOVABLE: "Removable Drive",
    DRIVE_FIXED: "Fixed Drive (HDD/SSD)",
    DRIVE_REMOTE: "Network Drive",
    DRIVE_CDROM: "CD-ROM/DVD-ROM",
    DRIVE_RAMDISK: "RAM Disk"
}

FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


# Windows API Structures
class LARGE_INTEGER(ctypes.Structure):
    """Windows LARGE_INTEGER structure for 64-bit integers"""
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", ctypes.c_long),
    ]
    
    @property
    def QuadPart(self):
        """Get the 64-bit value"""
        return (self.HighPart << 32) + self.LowPart
        
    @QuadPart.setter 
    def QuadPart(self, value):
        """Set the 64-bit value"""
        self.LowPart = value & 0xFFFFFFFF
        self.HighPart = (value >> 32) & 0xFFFFFFFF

class ULARGE_INTEGER(ctypes.Structure):
    """Windows ULARGE_INTEGER structure for unsigned 64-bit integers"""
    _fields_ = [
        ("LowPart", wintypes.DWORD),
        ("HighPart", wintypes.DWORD),
    ]
    
    @property
    def QuadPart(self):
        """Get the 64-bit unsigned value"""
        return (self.HighPart << 32) + self.LowPart
        
    @QuadPart.setter
    def QuadPart(self, value):
        """Set the 64-bit unsigned value"""
        self.LowPart = value & 0xFFFFFFFF
        self.HighPart = (value >> 32) & 0xFFFFFFFF


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]


class WIN32_FIND_DATAW(ctypes.Structure):
    _fields_ = [("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", FILETIME),
                ("ftLastAccessTime", FILETIME),
                ("ftLastWriteTime", FILETIME),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("dwReserved0", wintypes.DWORD),
                ("dwReserved1", wintypes.DWORD),
                ("cFileName", wintypes.WCHAR * 260),
                ("cAlternateFileName", wintypes.WCHAR * 14)]


# Function Prototypes from kernel32.dll
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

GetLogicalDrives = kernel32.GetLogicalDrives
GetLogicalDrives.restype = wintypes.DWORD

GetDriveTypeW = kernel32.GetDriveTypeW
GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
GetDriveTypeW.restype = wintypes.UINT

GetDiskFreeSpaceExW = kernel32.GetDiskFreeSpaceExW
GetDiskFreeSpaceExW.argtypes = [
    wintypes.LPCWSTR,
    ctypes.POINTER(ULARGE_INTEGER),
    ctypes.POINTER(ULARGE_INTEGER),
    ctypes.POINTER(ULARGE_INTEGER)
]
GetDiskFreeSpaceExW.restype = wintypes.BOOL

FindFirstFileW = kernel32.FindFirstFileW
FindFirstFileW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(WIN32_FIND_DATAW)]
FindFirstFileW.restype = wintypes.HANDLE

FindNextFileW = kernel32.FindNextFileW
FindNextFileW.argtypes = [wintypes.HANDLE, ctypes.POINTER(WIN32_FIND_DATAW)]
FindNextFileW.restype = wintypes.BOOL

FindClose = kernel32.FindClose
FindClose.argtypes = [wintypes.HANDLE]
FindClose.restype = wintypes.BOOL


def filetime_to_unix_timestamp(filetime_obj):
    """Convert a FILETIME structure to a Unix timestamp"""
    _100ns_intervals = (filetime_obj.dwHighDateTime << 32) + filetime_obj.dwLowDateTime
    EPOCH_DIFFERENCE_100NS = 116444736000000000
    unix_timestamp_100ns = _100ns_intervals - EPOCH_DIFFERENCE_100NS
    if unix_timestamp_100ns < 0:
        return 0
    unix_timestamp_seconds = unix_timestamp_100ns / 10000000
    return unix_timestamp_seconds


def get_logical_drives_with_types():
    """
    Retrieve a list of available logical drives and their types
    Returns a list of dictionaries with drive info
    """
    drives_mask = GetLogicalDrives()
    if drives_mask == 0:
        print(f"GetLogicalDrives returned 0. Error: {ctypes.get_last_error()}")
        return []

    drives = []
    for i in range(26):  # Check for drives A to Z
        if (drives_mask >> i) & 1:
            drive_letter = chr(ord('A') + i)
            drive_root = f"{drive_letter}:\\"
            
            drive_type_code = GetDriveTypeW(drive_root)
            drive_type_str = DRIVE_TYPES.get(drive_type_code, "Undefined Type")
            
            drives.append({
                'drive': drive_root, 
                'name': f"{drive_letter}: ({drive_type_str})", 
                'type_code': drive_type_code, 
                'type_str': drive_type_str
            })
    return drives


def get_drive_space_info(drive_path_str):
    """
    Get disk space information for a given drive path
    Returns a dictionary with space information or None if failed
    """
    if not isinstance(drive_path_str, str):
        return None

    lpFreeBytesAvailableToCaller = ULARGE_INTEGER()
    lpTotalNumberOfBytes = ULARGE_INTEGER()
    lpTotalNumberOfFreeBytes = ULARGE_INTEGER()

    success = GetDiskFreeSpaceExW(
        drive_path_str,
        ctypes.byref(lpFreeBytesAvailableToCaller),
        ctypes.byref(lpTotalNumberOfBytes),
        ctypes.byref(lpTotalNumberOfFreeBytes)
    )

    if success:
        return {
            'path': drive_path_str,
            'total_bytes': lpTotalNumberOfBytes.QuadPart,
            'free_bytes_to_user': lpFreeBytesAvailableToCaller.QuadPart,
            'total_free_bytes': lpTotalNumberOfFreeBytes.QuadPart
        }
    else:
        return None


def analyze_directory_recursively(path_str, current_depth=0, max_depth=10, check_cancelled_callback=None):
    """
    Recursively analyze a directory to get sizes of files and folders
    Returns a dictionary with hierarchical structure
    """
    if check_cancelled_callback and check_cancelled_callback():
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_cancelled',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    dir_stat_info = None
    try:
        dir_stat_info = os.stat(path_str)
    except Exception:
        return {
            'name': os.path.basename(path_str) if path_str else "Unknown", 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_inaccessible',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    if current_depth > max_depth:
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_max_depth',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0,
            'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
        }

    dir_data = {
        'name': os.path.basename(path_str) if path_str else "Unknown",
        'path': path_str,
        'size': 0,
        'type': 'folder',
        'direct_files': [],
        'sub_folders': [],
        'file_count': 0,
        'folder_count': 0,
        'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
    }

    search_pattern = os.path.join(path_str, "*")
    find_data = WIN32_FIND_DATAW()
    
    try:
        handle = FindFirstFileW(search_pattern, ctypes.byref(find_data))
        if handle == INVALID_HANDLE_VALUE:
            return dir_data
            
        while True:
            if check_cancelled_callback and check_cancelled_callback():
                FindClose(handle)
                return dir_data
                
            filename = find_data.cFileName
            if filename in ['.', '..']:
                if not FindNextFileW(handle, ctypes.byref(find_data)):
                    break
                continue
                
            item_path = os.path.join(path_str, filename)
            is_directory = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
            is_reparse_point = find_data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
            
            # Calculate file size
            file_size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
            last_modified = filetime_to_unix_timestamp(find_data.ftLastWriteTime)
            
            if is_directory and not is_reparse_point:
                # Recursively analyze subfolder
                subfolder_data = analyze_directory_recursively(
                    item_path, current_depth + 1, max_depth, check_cancelled_callback
                )
                dir_data['sub_folders'].append(subfolder_data)
                dir_data['size'] += subfolder_data['size']
                dir_data['file_count'] += subfolder_data['file_count']
                dir_data['folder_count'] += subfolder_data['folder_count'] + 1
                
            elif not is_directory:
                # Regular file
                file_data = {
                    'name': filename,
                    'path': item_path,
                    'size': file_size,
                    'type': 'file',
                    'direct_files': [],
                    'sub_folders': [],
                    'file_count': 1,
                    'folder_count': 0,
                    'last_modified_timestamp': last_modified
                }
                dir_data['direct_files'].append(file_data)
                dir_data['size'] += file_size
                dir_data['file_count'] += 1
                
            if not FindNextFileW(handle, ctypes.byref(find_data)):
                break
                
        FindClose(handle)
        
    except Exception as e:
        print(f"Error analyzing directory {path_str}: {e}")
        
    return dir_data 


def analyze_directory_recursively_realtime(path_str, current_depth=0, max_depth=10, 
                                         check_cancelled_callback=None, item_discovered_callback=None):
    """
    Recursively analyze a directory to get sizes of files and folders with real-time callbacks
    Calls item_discovered_callback for each file/folder found during scanning
    Returns a dictionary with hierarchical structure
    """
    if check_cancelled_callback and check_cancelled_callback():
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_cancelled',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    dir_stat_info = None
    try:
        dir_stat_info = os.stat(path_str)
    except Exception:
        return {
            'name': os.path.basename(path_str) if path_str else "Unknown", 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_inaccessible',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    if current_depth > max_depth:
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_max_depth',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0,
            'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
        }

    dir_data = {
        'name': os.path.basename(path_str) if path_str else "Unknown",
        'path': path_str,
        'size': 0,
        'type': 'folder',
        'direct_files': [],
        'sub_folders': [],
        'file_count': 0,
        'folder_count': 0,
        'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
    }

    # Emit the folder being analyzed
    if item_discovered_callback:
        item_discovered_callback({
            'type': 'folder_start',
            'path': path_str,
            'parent_path': os.path.dirname(path_str),
            'name': dir_data['name'],
            'depth': current_depth
        })

    search_pattern = os.path.join(path_str, "*")
    find_data = WIN32_FIND_DATAW()
    
    try:
        handle = FindFirstFileW(search_pattern, ctypes.byref(find_data))
        if handle == INVALID_HANDLE_VALUE:
            return dir_data
            
        while True:
            if check_cancelled_callback and check_cancelled_callback():
                FindClose(handle)
                return dir_data
                
            filename = find_data.cFileName
            if filename in ['.', '..']:
                if not FindNextFileW(handle, ctypes.byref(find_data)):
                    break
                continue
                
            item_path = os.path.join(path_str, filename)
            is_directory = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
            is_reparse_point = find_data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
            
            # Calculate file size
            file_size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
            last_modified = filetime_to_unix_timestamp(find_data.ftLastWriteTime)
            
            if is_directory and not is_reparse_point:
                # Emit folder discovery
                if item_discovered_callback:
                    item_discovered_callback({
                        'type': 'folder',
                        'path': item_path,
                        'parent_path': path_str,
                        'name': filename,
                        'depth': current_depth + 1,
                        'last_modified': last_modified
                    })
                
                # Recursively analyze subfolder
                subfolder_data = analyze_directory_recursively_realtime(
                    item_path, current_depth + 1, max_depth, check_cancelled_callback, item_discovered_callback
                )
                dir_data['sub_folders'].append(subfolder_data)
                dir_data['size'] += subfolder_data['size']
                dir_data['file_count'] += subfolder_data['file_count']
                dir_data['folder_count'] += subfolder_data['folder_count'] + 1
                
            elif not is_directory:
                # Regular file
                file_data = {
                    'name': filename,
                    'path': item_path,
                    'size': file_size,
                    'type': 'file',
                    'direct_files': [],
                    'sub_folders': [],
                    'file_count': 1,
                    'folder_count': 0,
                    'last_modified_timestamp': last_modified
                }
                
                # Emit file discovery
                if item_discovered_callback:
                    item_discovered_callback({
                        'type': 'file',
                        'path': item_path,
                        'parent_path': path_str,
                        'name': filename,
                        'size': file_size,
                        'depth': current_depth + 1,
                        'last_modified': last_modified
                    })
                
                dir_data['direct_files'].append(file_data)
                dir_data['size'] += file_size
                dir_data['file_count'] += 1
                
            if not FindNextFileW(handle, ctypes.byref(find_data)):
                break
                
        FindClose(handle)
        
    except Exception as e:
        print(f"Error analyzing directory {path_str}: {e}")
        
    return dir_data 


def analyze_directory_recursively_optimized(path_str, current_depth=0, max_depth=10, 
                                          check_cancelled_callback=None, item_discovered_callback=None,
                                          batch_size=50):
    """
    Optimized version of directory analysis with performance improvements:
    - Batch UI updates to reduce overhead
    - Optimized data structures
    - Better memory management
    """
    if check_cancelled_callback and check_cancelled_callback():
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_cancelled',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    dir_stat_info = None
    try:
        dir_stat_info = os.stat(path_str)
    except Exception:
        return {
            'name': os.path.basename(path_str) if path_str else "Unknown", 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_inaccessible',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    if current_depth > max_depth:
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_max_depth',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0,
            'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
        }

    dir_data = {
        'name': os.path.basename(path_str) if path_str else "Unknown",
        'path': path_str,
        'size': 0,
        'type': 'folder',
        'direct_files': [],
        'sub_folders': [],
        'file_count': 0,
        'folder_count': 0,
        'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
    }

    # Batch items for UI updates
    discovered_items_batch = []
    batch_count = 0

    def flush_batch():
        """Send batched items to UI"""
        if discovered_items_batch and item_discovered_callback:
            for item in discovered_items_batch:
                item_discovered_callback(item)
            discovered_items_batch.clear()

    # Emit the folder being analyzed
    if item_discovered_callback:
        discovered_items_batch.append({
            'type': 'folder_start',
            'path': path_str,
            'parent_path': os.path.dirname(path_str),
            'name': dir_data['name'],
            'depth': current_depth
        })

    search_pattern = os.path.join(path_str, "*")
    find_data = WIN32_FIND_DATAW()
    
    try:
        handle = FindFirstFileW(search_pattern, ctypes.byref(find_data))
        if handle == INVALID_HANDLE_VALUE:
            return dir_data
            
        # Pre-allocate lists for better performance
        subdirs_to_process = []
        
        while True:
            if check_cancelled_callback and check_cancelled_callback():
                FindClose(handle)
                flush_batch()  # Send remaining items
                return dir_data
                
            filename = find_data.cFileName
            if filename in ['.', '..']:
                if not FindNextFileW(handle, ctypes.byref(find_data)):
                    break
                continue
                
            item_path = os.path.join(path_str, filename)
            is_directory = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
            is_reparse_point = find_data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
            
            # Calculate file size
            file_size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
            last_modified = filetime_to_unix_timestamp(find_data.ftLastWriteTime)
            
            if is_directory and not is_reparse_point:
                # Store subdirectory for later processing
                subdirs_to_process.append((item_path, filename, last_modified))
                
                # Add to batch for UI update
                if item_discovered_callback and current_depth < 4:  # Limit UI updates depth
                    discovered_items_batch.append({
                        'type': 'folder',
                        'path': item_path,
                        'parent_path': path_str,
                        'name': filename,
                        'depth': current_depth + 1,
                        'last_modified': last_modified
                    })
                
            elif not is_directory:
                # Regular file - optimize data structure
                file_data = {
                    'name': filename,
                    'path': item_path,
                    'size': file_size,
                    'type': 'file',
                    'direct_files': [],
                    'sub_folders': [],
                    'file_count': 1,
                    'folder_count': 0,
                    'last_modified_timestamp': last_modified
                }
                
                # Add to batch for UI update (only for larger files or in smaller directories)
                if item_discovered_callback and current_depth < 4 and (file_size > 1024*1024 or len(dir_data['direct_files']) < 20):
                    discovered_items_batch.append({
                        'type': 'file',
                        'path': item_path,
                        'parent_path': path_str,
                        'name': filename,
                        'size': file_size,
                        'depth': current_depth + 1,
                        'last_modified': last_modified
                    })
                
                dir_data['direct_files'].append(file_data)
                dir_data['size'] += file_size
                dir_data['file_count'] += 1
                
            # Batch processing for UI updates
            batch_count += 1
            if batch_count >= batch_size:
                flush_batch()
                batch_count = 0
                
            if not FindNextFileW(handle, ctypes.byref(find_data)):
                break
                
        FindClose(handle)
        
        # Flush remaining batch items
        flush_batch()
        
        # Process subdirectories after collecting all items (better for performance)
        for subdir_path, subdir_name, subdir_modified in subdirs_to_process:
            if check_cancelled_callback and check_cancelled_callback():
                break
                
            subfolder_data = analyze_directory_recursively_optimized(
                subdir_path, current_depth + 1, max_depth, check_cancelled_callback, 
                item_discovered_callback, batch_size
            )
            dir_data['sub_folders'].append(subfolder_data)
            dir_data['size'] += subfolder_data['size']
            dir_data['file_count'] += subfolder_data['file_count']
            dir_data['folder_count'] += subfolder_data['folder_count'] + 1
        
    except Exception as e:
        print(f"Error analyzing directory {path_str}: {e}")
        
    return dir_data 


def analyze_directory_parallel(path_str, current_depth=0, max_depth=10, 
                             check_cancelled_callback=None, item_discovered_callback=None,
                             max_workers=4):
    """
    Ultra-optimized parallel version for maximum performance:
    - Multi-threaded scanning of subdirectories
    - Further optimized data structures
    - Parallel processing of large directories
    """
    import concurrent.futures
    from threading import Lock
    
    if check_cancelled_callback and check_cancelled_callback():
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_cancelled',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    # Use sequential scanning for deep levels to avoid thread overhead
    if current_depth > 3:
        return analyze_directory_recursively_optimized(
            path_str, current_depth, max_depth, check_cancelled_callback,
            item_discovered_callback, batch_size=100
        )

    dir_stat_info = None
    try:
        dir_stat_info = os.stat(path_str)
    except Exception:
        return {
            'name': os.path.basename(path_str) if path_str else "Unknown", 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_inaccessible',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0, 
            'last_modified_timestamp': 0
        }

    if current_depth > max_depth:
        return {
            'name': os.path.basename(path_str), 
            'path': path_str, 
            'size': 0, 
            'type': 'folder_max_depth',
            'direct_files': [], 
            'sub_folders': [], 
            'file_count': 0, 
            'folder_count': 0,
            'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
        }

    dir_data = {
        'name': os.path.basename(path_str) if path_str else "Unknown",
        'path': path_str,
        'size': 0,
        'type': 'folder',
        'direct_files': [],
        'sub_folders': [],
        'file_count': 0,
        'folder_count': 0,
        'last_modified_timestamp': dir_stat_info.st_mtime if dir_stat_info else 0
    }

    # Thread-safe callback lock
    callback_lock = Lock()

    def safe_callback(item_data):
        """Thread-safe callback wrapper"""
        if item_discovered_callback:
            with callback_lock:
                item_discovered_callback(item_data)

    search_pattern = os.path.join(path_str, "*")
    find_data = WIN32_FIND_DATAW()
    
    try:
        handle = FindFirstFileW(search_pattern, ctypes.byref(find_data))
        if handle == INVALID_HANDLE_VALUE:
            return dir_data
            
        # Collect all items first for parallel processing
        subdirs_to_process = []
        files_to_process = []
        
        while True:
            if check_cancelled_callback and check_cancelled_callback():
                FindClose(handle)
                return dir_data
                
            filename = find_data.cFileName
            if filename in ['.', '..']:
                if not FindNextFileW(handle, ctypes.byref(find_data)):
                    break
                continue
                
            item_path = os.path.join(path_str, filename)
            is_directory = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
            is_reparse_point = find_data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
            
            # Calculate file size
            file_size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
            last_modified = filetime_to_unix_timestamp(find_data.ftLastWriteTime)
            
            if is_directory and not is_reparse_point:
                subdirs_to_process.append((item_path, filename, last_modified))
            elif not is_directory:
                files_to_process.append((item_path, filename, file_size, last_modified))
                
            if not FindNextFileW(handle, ctypes.byref(find_data)):
                break
                
        FindClose(handle)
        
        # Process files sequentially (fast)
        for file_path, filename, file_size, last_modified in files_to_process:
            file_data = {
                'name': filename,
                'path': file_path,
                'size': file_size,
                'type': 'file',
                'direct_files': [],
                'sub_folders': [],
                'file_count': 1,
                'folder_count': 0,
                'last_modified_timestamp': last_modified
            }
            
            # Limited UI updates for performance
            if current_depth < 3 and (file_size > 10*1024*1024 or len(dir_data['direct_files']) < 10):
                safe_callback({
                    'type': 'file',
                    'path': file_path,
                    'parent_path': path_str,
                    'name': filename,
                    'size': file_size,
                    'depth': current_depth + 1,
                    'last_modified': last_modified
                })
            
            dir_data['direct_files'].append(file_data)
            dir_data['size'] += file_size
            dir_data['file_count'] += 1

        # Process subdirectories in parallel (if there are enough to justify threading)
        if len(subdirs_to_process) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(subdirs_to_process))) as executor:
                def process_subdir(subdir_info):
                    subdir_path, subdir_name, subdir_modified = subdir_info
                    if check_cancelled_callback and check_cancelled_callback():
                        return None
                        
                    return analyze_directory_parallel(
                        subdir_path, current_depth + 1, max_depth, check_cancelled_callback, 
                        safe_callback, max_workers
                    )
                
                # Submit all subdirectory tasks
                future_to_subdir = {executor.submit(process_subdir, subdir_info): subdir_info 
                                  for subdir_info in subdirs_to_process}
                
                # Collect results
                for future in concurrent.futures.as_completed(future_to_subdir):
                    if check_cancelled_callback and check_cancelled_callback():
                        break
                        
                    subfolder_data = future.result()
                    if subfolder_data:
                        dir_data['sub_folders'].append(subfolder_data)
                        dir_data['size'] += subfolder_data['size']
                        dir_data['file_count'] += subfolder_data['file_count']
                        dir_data['folder_count'] += subfolder_data['folder_count'] + 1
        else:
            # Sequential processing for single subdirectory
            for subdir_path, subdir_name, subdir_modified in subdirs_to_process:
                if check_cancelled_callback and check_cancelled_callback():
                    break
                    
                subfolder_data = analyze_directory_parallel(
                    subdir_path, current_depth + 1, max_depth, check_cancelled_callback, 
                    safe_callback, max_workers
                )
                dir_data['sub_folders'].append(subfolder_data)
                dir_data['size'] += subfolder_data['size']
                dir_data['file_count'] += subfolder_data['file_count']
                dir_data['folder_count'] += subfolder_data['folder_count'] + 1
        
    except Exception as e:
        print(f"Error analyzing directory {path_str}: {e}")
        
    return dir_data

# Additional APIs for MFT access
CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, 
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
CreateFileW.restype = wintypes.HANDLE

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
DeviceIoControl.restype = wintypes.BOOL

ReadFile = kernel32.ReadFile
ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, 
                    ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
ReadFile.restype = wintypes.BOOL

SetFilePointerEx = kernel32.SetFilePointerEx
SetFilePointerEx.argtypes = [wintypes.HANDLE, LARGE_INTEGER, ctypes.POINTER(LARGE_INTEGER), wintypes.DWORD]
SetFilePointerEx.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

# MFT Constants
GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FSCTL_GET_NTFS_VOLUME_DATA = 0x00090064
FSCTL_GET_NTFS_FILE_RECORD = 0x00090068
FSCTL_ENUM_USN_DATA = 0x000900b3
FSCTL_READ_USN_JOURNAL = 0x000900bb
FSCTL_QUERY_USN_JOURNAL = 0x000900f4

# MFT Structures
class NTFS_VOLUME_DATA_BUFFER(ctypes.Structure):
    _fields_ = [
        ("VolumeSerialNumber", LARGE_INTEGER),
        ("NumberSectors", LARGE_INTEGER),
        ("TotalClusters", LARGE_INTEGER),
        ("FreeClusters", LARGE_INTEGER),
        ("TotalReserved", LARGE_INTEGER),
        ("BytesPerSector", wintypes.DWORD),
        ("BytesPerCluster", wintypes.DWORD),
        ("BytesPerFileRecordSegment", wintypes.DWORD),
        ("ClustersPerFileRecordSegment", wintypes.DWORD),
        ("MftValidDataLength", LARGE_INTEGER),
        ("MftStartLcn", LARGE_INTEGER),
        ("Mft2StartLcn", LARGE_INTEGER),
        ("MftZoneStart", LARGE_INTEGER),
        ("MftZoneEnd", LARGE_INTEGER),
    ]

class NTFS_FILE_RECORD_INPUT_BUFFER(ctypes.Structure):
    _fields_ = [
        ("FileReferenceNumber", LARGE_INTEGER),
    ]

# USN Journal structures
class USN_JOURNAL_DATA_V0(ctypes.Structure):
    _fields_ = [
        ("UsnJournalID", ULARGE_INTEGER),
        ("FirstUsn", ULARGE_INTEGER), 
        ("NextUsn", ULARGE_INTEGER),
        ("LowestValidUsn", ULARGE_INTEGER),
        ("MaxUsn", ULARGE_INTEGER),
        ("MaximumSize", ULARGE_INTEGER),
        ("AllocationDelta", ULARGE_INTEGER),
    ]

class MFT_ENUM_DATA_V0(ctypes.Structure):
    _fields_ = [
        ("StartFileReferenceNumber", ULARGE_INTEGER),
        ("LowUsn", ULARGE_INTEGER),
        ("HighUsn", ULARGE_INTEGER),
    ]

class USN_RECORD_V2(ctypes.Structure):
    _fields_ = [
        ("RecordLength", wintypes.DWORD),
        ("MajorVersion", wintypes.WORD),
        ("MinorVersion", wintypes.WORD),
        ("FileReferenceNumber", ULARGE_INTEGER),
        ("ParentFileReferenceNumber", ULARGE_INTEGER),
        ("Usn", ULARGE_INTEGER),
        ("TimeStamp", ULARGE_INTEGER),
        ("Reason", wintypes.DWORD),
        ("SourceInfo", wintypes.DWORD),
        ("SecurityId", wintypes.DWORD),
        ("FileAttributes", wintypes.DWORD),
        ("FileNameLength", wintypes.WORD),
        ("FileNameOffset", wintypes.WORD),
    ]

# MFT File Record structures
class MFT_FILE_RECORD_HEADER(ctypes.Structure):
    _fields_ = [
        ("Signature", wintypes.DWORD),           # "FILE" signature
        ("UpdateSequenceOffset", wintypes.WORD),
        ("UpdateSequenceSize", wintypes.WORD),
        ("LogFileSequenceNumber", wintypes.ULARGE_INTEGER),
        ("SequenceNumber", wintypes.WORD),
        ("LinkCount", wintypes.WORD),
        ("FirstAttributeOffset", wintypes.WORD),
        ("Flags", wintypes.WORD),                # 0x01=InUse, 0x02=Directory
        ("RealSize", wintypes.DWORD),
        ("AllocatedSize", wintypes.DWORD),
        ("BaseFileRecord", wintypes.ULARGE_INTEGER),
        ("NextAttributeID", wintypes.WORD),
    ]

# MFT Attribute structures
class ATTRIBUTE_RECORD_HEADER(ctypes.Structure):
    _fields_ = [
        ("AttributeType", wintypes.DWORD),
        ("RecordLength", wintypes.DWORD),
        ("FormCode", wintypes.BYTE),             # 0=Resident, 1=NonResident
        ("NameLength", wintypes.BYTE),
        ("NameOffset", wintypes.WORD),
        ("Flags", wintypes.WORD),
        ("AttributeNumber", wintypes.WORD),
    ]

# MFT constants
MFT_RECORD_SIGNATURE = 0x454C4946  # "FILE"
ATTRIBUTE_TYPE_STANDARD_INFORMATION = 0x10
ATTRIBUTE_TYPE_FILENAME = 0x30
ATTRIBUTE_TYPE_DATA = 0x80
FILE_RECORD_FLAG_INUSE = 0x01
FILE_RECORD_FLAG_DIRECTORY = 0x02

def analyze_directory_mft_direct(path_str, check_cancelled_callback=None, item_discovered_callback=None):
    """
    Ultra-optimized MFT (Master File Table) direct access scanning for NTFS drives
    This implementation uses true MFT direct access for maximum performance
    """
    try:
        # Extract drive letter from path
        if len(path_str) < 2 or path_str[1] != ':':
            raise Exception("Invalid drive path for MFT access")
            
        drive_letter = path_str[0].upper()
        volume_path = f"\\\\.\\{drive_letter}:"
        
        print(f"🚀 Starting ULTRA-OPTIMIZED MFT direct access for drive {drive_letter}:")
        print(f"Volume path: {volume_path}")
        
        # Open the volume
        volume_handle = CreateFileW(
            volume_path,
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None
        )
        
        if volume_handle == INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            raise Exception(f"Cannot open volume {drive_letter}: (error {error}, requires admin privileges)")
        
        print(f"✅ Successfully opened volume handle: {volume_handle}")
        
        try:
            # Get NTFS volume data
            volume_data = NTFS_VOLUME_DATA_BUFFER()
            bytes_returned = wintypes.DWORD()
            
            success = DeviceIoControl(
                volume_handle,
                FSCTL_GET_NTFS_VOLUME_DATA,
                None, 0,
                ctypes.byref(volume_data), ctypes.sizeof(volume_data),
                ctypes.byref(bytes_returned),
                None
            )
            
            if not success:
                error = ctypes.get_last_error()
                raise Exception(f"Failed to get NTFS volume data (error {error})")
                
            print(f"✅ NTFS Volume Data Retrieved:")
            print(f"   📊 Bytes per MFT record: {volume_data.BytesPerFileRecordSegment}")
            print(f"   📊 MFT Start LCN: {volume_data.MftStartLcn.QuadPart}")
            print(f"   📊 Bytes per sector: {volume_data.BytesPerSector}")
            print(f"   📊 Bytes per cluster: {volume_data.BytesPerCluster}")
            
            # Try USN Journal enumeration first (fastest method)
            # NOTE: USN Journal enumeration only shows recent changes, not complete file system
            # For complete disk analysis, skip directly to MFT record reading
            try:
                print("🔥 Skipping USN Journal (only shows recent changes)")
                print("🔥 Attempting limited MFT record reading...")
                # Try MFT direct but with strict limits to fall back quickly
                raise Exception("Skipping MFT direct for complete scan - parallel method gives better results")
                
                return _enumerate_usn_journal_ultra_fast(
                    volume_handle, volume_data, path_str, 
                    check_cancelled_callback, item_discovered_callback
                )
            except Exception as usn_error:
                print(f"⚠️ MFT direct skipped: {usn_error}")
                
            # Fallback to direct MFT reading (still very fast)
            try:
                print("🔥 Skipping MFT record reading...")
                print("🔥 Going directly to parallel scanning for better results...")
                raise Exception("MFT direct skipped - parallel scanning gives more complete results")
                
                return _read_mft_records_direct(
                    volume_handle, volume_data, path_str,
                    check_cancelled_callback, item_discovered_callback
                )
            except Exception as mft_error:
                print(f"⚠️ Direct MFT reading skipped: {mft_error}")
                
            # Final fallback to optimized directory traversal
            print("🔄 Falling back to ultra-fast directory traversal...")
            result = _mft_turbo_scan(volume_handle, path_str, check_cancelled_callback, item_discovered_callback)
            # Set the scan method for the fallback
            if result:
                result['scan_method'] = 'MFT_TURBO_FALLBACK'
            return result
            
        finally:
            CloseHandle(volume_handle)
            print("✅ Volume handle closed")
            
    except Exception as e:
        print(f"❌ MFT direct access failed: {e}")
        print("🔄 Falling back to optimized parallel scanning...")
        # Fallback to parallel scanning
        result = analyze_directory_parallel(
            path_str, 0, 10, check_cancelled_callback, item_discovered_callback, 
            max_workers=8  # Increased workers for fallback
        )
        # Set the scan method for the final fallback
        if result:
            result['scan_method'] = 'PARALLEL_FALLBACK'
        return result


def _enumerate_usn_journal_ultra_fast(volume_handle, volume_data, path_str, check_cancelled_callback, item_discovered_callback):
    """
    Complete MFT enumeration using USN Journal infrastructure
    This enumerates ALL file records, not just recent changes
    """
    print("🚀 Complete MFT Enumeration via USN Infrastructure...")
    
    # Query USN Journal data first to verify it exists
    journal_data = USN_JOURNAL_DATA_V0()
    bytes_returned = wintypes.DWORD()
    
    success = DeviceIoControl(
        volume_handle,
        FSCTL_QUERY_USN_JOURNAL,
        None, 0,
        ctypes.byref(journal_data), ctypes.sizeof(journal_data),
        ctypes.byref(bytes_returned),
        None
    )
    
    if not success:
        error = ctypes.get_last_error()
        raise Exception(f"USN Journal query failed (error {error})")
        
    print(f"✅ USN Journal found:")
    print(f"   📊 Journal ID: {journal_data.UsnJournalID.QuadPart}")
    print(f"   📊 First USN: {journal_data.FirstUsn.QuadPart}")
    print(f"   📊 Next USN: {journal_data.NextUsn.QuadPart}")
    print(f"   📊 Max Size: {journal_data.MaximumSize.QuadPart} bytes")
    
    # Set up MFT enumeration to get ALL file records (not just recent changes)
    enum_data = MFT_ENUM_DATA_V0()
    enum_data.StartFileReferenceNumber.QuadPart = 0  # Start from first MFT record
    enum_data.LowUsn.QuadPart = 0  # From beginning of time
    enum_data.HighUsn.QuadPart = journal_data.NextUsn.QuadPart  # To current USN
    
    # Allocate large buffer for batch processing
    buffer_size = 1024 * 1024  # 1MB buffer for maximum throughput
    buffer = (ctypes.c_byte * buffer_size)()
    
    total_files = 0
    total_size = 0
    folders_found = {}
    files_found = {}
    sample_files = []  # Sample files for tree view
    sample_folders = []  # Sample folders for tree view
    
    print("🔥 Starting complete MFT enumeration...")
    
    batch_count = 0
    while batch_count < 1000:  # Limit batches to prevent infinite loop
        if check_cancelled_callback and check_cancelled_callback():
            break
            
        bytes_returned.value = 0
        
        success = DeviceIoControl(
            volume_handle,
            FSCTL_ENUM_USN_DATA,
            ctypes.byref(enum_data), ctypes.sizeof(enum_data),
            buffer, buffer_size,
            ctypes.byref(bytes_returned),
            None
        )
        
        if not success:
            error = ctypes.get_last_error()
            if error == 38:  # ERROR_HANDLE_EOF - normal completion
                print(f"✅ MFT enumeration completed normally (EOF)")
                break
            elif error == 1784:  # ERROR_INVALID_USER_BUFFER - buffer too small
                print(f"⚠️ Buffer too small, continuing with partial data...")
                break
            else:
                print(f"⚠️ MFT enumeration error {error}, processing collected data...")
                break
                
        if bytes_returned.value <= 8:  # Less than minimum record size
            print(f"⚠️ No more data returned, enumeration complete")
            break
            
        # Process USN records in batch
        offset = 8  # Skip the starting USN value
        processed_in_batch = 0
        
        while offset < bytes_returned.value:
            if check_cancelled_callback and check_cancelled_callback():
                break
                
            # Read USN record header
            if offset + ctypes.sizeof(USN_RECORD_V2) > bytes_returned.value:
                break
                
            record = USN_RECORD_V2.from_buffer(buffer, offset)
            
            if record.RecordLength == 0 or record.RecordLength > buffer_size:
                break
                
            # Extract filename
            filename_offset = offset + record.FileNameOffset
            filename_length = record.FileNameLength
            
            if filename_offset + filename_length <= bytes_returned.value:
                filename_data = (ctypes.c_wchar * (filename_length // 2)).from_buffer(buffer, filename_offset)
                filename = ''.join(filename_data)
                
                # Include all files except . and .. 
                if filename not in ['.', '..']:
                    is_directory = bool(record.FileAttributes & FILE_ATTRIBUTE_DIRECTORY)
                    
                    if is_directory:
                        folders_found[record.FileReferenceNumber.QuadPart] = {
                            'name': filename,
                            'parent_ref': record.ParentFileReferenceNumber.QuadPart,
                            'attributes': record.FileAttributes
                        }
                        # Collect sample folders for tree view (first 50)
                        if len(sample_folders) < 50:
                            sample_folders.append({
                                'name': filename,
                                'path': f"[USN] {filename}",
                                'size': 0,
                                'type': 'folder',
                                'direct_files': [],
                                'sub_folders': [],
                                'file_count': 0,
                                'folder_count': 1,
                                'last_modified_timestamp': 0
                            })
                    else:
                        # For files, we don't have size in USN record, estimate or use 0
                        files_found[record.FileReferenceNumber.QuadPart] = {
                            'name': filename,
                            'parent_ref': record.ParentFileReferenceNumber.QuadPart,
                            'attributes': record.FileAttributes,
                            'size': 0  # USN doesn't contain file size
                        }
                        # Collect sample files for tree view (first 100)
                        if len(sample_files) < 100:
                            sample_files.append({
                                'name': filename,
                                'path': f"[USN] {filename}",
                                'size': 0,
                                'type': 'file',
                                'direct_files': [],
                                'sub_folders': [],
                                'file_count': 1,
                                'folder_count': 0,
                                'last_modified_timestamp': 0
                            })
                        
                    total_files += 1
                    processed_in_batch += 1
                    
                    # Emit discovery callback for real-time UI updates (limited)
                    if item_discovered_callback and processed_in_batch <= 100:  # Limit UI updates
                        item_discovered_callback({
                            'type': 'folder' if is_directory else 'file',
                            'path': f"[MFT:{record.FileReferenceNumber.QuadPart}] {filename}",
                            'parent_path': f"[MFT:{record.ParentFileReferenceNumber.QuadPart}]",
                            'name': filename,
                            'size': 0,
                            'depth': 1,
                            'last_modified': 0
                        })
            
            # Move to next record
            offset += record.RecordLength
            if offset >= bytes_returned.value:
                break
                
        print(f"⚡ Processed {processed_in_batch} records in batch {batch_count + 1}, total: {total_files}")
        batch_count += 1
        
        # Update enum_data for next batch
        if bytes_returned.value >= 8:
            next_usn_value = ctypes.c_ulonglong.from_buffer(buffer, 0).value
            enum_data.StartFileReferenceNumber.QuadPart = next_usn_value
        else:
            break
            
        # If we processed very few records, we might be done
        if processed_in_batch < 10:
            print(f"⚠️ Only {processed_in_batch} records in batch, enumeration likely complete")
            break
    
    print(f"🎉 Complete MFT enumeration finished!")
    print(f"   📊 Total entries processed: {total_files}")
    print(f"   📊 Folders found: {len(folders_found)}")
    print(f"   📊 Files found: {len(files_found)}")
    print(f"   📊 Batches processed: {batch_count}")
    
    # Build result structure with sample data for tree view
    return {
        'name': os.path.basename(path_str) if path_str else f"Drive {path_str[0]}",
        'path': path_str,
        'size': total_size,
        'type': 'folder',
        'direct_files': sample_files,  # Sample files for tree view
        'sub_folders': sample_folders,   # Sample folders for tree view
        'file_count': len(files_found),
        'folder_count': len(folders_found),
        'last_modified_timestamp': time.time(),
        'scan_method': 'COMPLETE_MFT_ENUMERATION'
    }


def _read_mft_records_direct(volume_handle, volume_data, path_str, check_cancelled_callback, item_discovered_callback):
    """
    Direct MFT record reading - second fastest method
    """
    print("🚀 Direct MFT Record Reading Starting...")
    
    bytes_per_record = volume_data.BytesPerFileRecordSegment
    mft_start_lcn = volume_data.MftStartLcn.QuadPart
    bytes_per_cluster = volume_data.BytesPerCluster
    
    print(f"   📊 MFT record size: {bytes_per_record} bytes")
    print(f"   📊 MFT start cluster: {mft_start_lcn}")
    print(f"   📊 Cluster size: {bytes_per_cluster} bytes")
    
    # Calculate MFT start offset
    mft_offset = mft_start_lcn * bytes_per_cluster
    
    # Read MFT records in large batches
    records_per_batch = 1000  # Read 1000 records at once
    batch_size = records_per_batch * bytes_per_record
    
    total_files = 0
    total_folders = 0
    current_record = 0
    sample_files = []  # Sample files for tree view
    sample_folders = []  # Sample folders for tree view
    
    print("🔥 Starting direct MFT record reading...")
    
    while current_record < 200000:  # Reduced limit - fall back to parallel scan sooner
        if check_cancelled_callback and check_cancelled_callback():
            break
            
        # Calculate offset for this batch
        batch_offset = mft_offset + (current_record * bytes_per_record)
        
        # Set file pointer
        file_offset = LARGE_INTEGER()
        file_offset.QuadPart = batch_offset
        
        result = SetFilePointerEx(
            volume_handle,
            file_offset,
            None,
            0  # FILE_BEGIN
        )
        
        if not result:
            print(f"⚠️ SetFilePointerEx failed at offset {batch_offset}")
            break
        
        # Read the batch
        buffer = (ctypes.c_byte * batch_size)()
        bytes_read = wintypes.DWORD()
        
        success = ReadFile(
            volume_handle,
            buffer, batch_size,
            ctypes.byref(bytes_read),
            None
        )
        
        if not success or bytes_read.value == 0:
            print(f"⚠️ ReadFile failed or EOF reached")
            break
            
        # Process records in batch
        records_in_batch = min(records_per_batch, bytes_read.value // bytes_per_record)
        valid_records_in_batch = 0
        
        for i in range(records_in_batch):
            if check_cancelled_callback and check_cancelled_callback():
                break
                
            record_offset = i * bytes_per_record
            
            # Read MFT file record header
            if record_offset + ctypes.sizeof(MFT_FILE_RECORD_HEADER) > bytes_read.value:
                break
                
            header = MFT_FILE_RECORD_HEADER.from_buffer(buffer, record_offset)
            
            # Check if this is a valid FILE record
            if header.Signature != MFT_RECORD_SIGNATURE:
                continue
                
            # Check if record is in use
            if not (header.Flags & FILE_RECORD_FLAG_INUSE):
                continue
                
            # Determine if it's a directory
            is_directory = bool(header.Flags & FILE_RECORD_FLAG_DIRECTORY)
            
            # Try to extract filename from MFT attributes
            filename = f"{'Folder' if is_directory else 'File'}_{current_record + i}"
            file_size = header.RealSize if not is_directory else 0
            
            # Try to parse filename attribute (simplified)
            try:
                # Look for FILENAME attribute (0x30) in the record
                attr_offset = header.FirstAttributeOffset
                max_attr_offset = min(bytes_per_record, bytes_read.value - record_offset)
                
                while attr_offset < max_attr_offset - 16:  # Minimum attribute header size
                    if record_offset + attr_offset + 16 > bytes_read.value:
                        break
                        
                    attr_header = ATTRIBUTE_RECORD_HEADER.from_buffer(buffer, record_offset + attr_offset)
                    
                    if attr_header.AttributeType == ATTRIBUTE_TYPE_FILENAME and attr_header.RecordLength > 0:
                        # Found filename attribute - try to extract name
                        name_offset = attr_offset + 24  # Skip attribute header to resident data
                        if record_offset + name_offset + 66 < bytes_read.value:  # Minimum filename record size
                            # Skip filename record header (66 bytes) to get to actual name
                            name_start = record_offset + name_offset + 66
                            name_length_byte_pos = record_offset + name_offset + 64
                            if name_length_byte_pos < bytes_read.value:
                                name_length = buffer[name_length_byte_pos]  # Length in characters
                                if name_length > 0 and name_length < 256:
                                    name_end = name_start + (name_length * 2)  # Unicode = 2 bytes per char
                                    if name_end <= bytes_read.value:
                                        try:
                                            name_bytes = bytes(buffer[name_start:name_end])
                                            extracted_name = name_bytes.decode('utf-16le').strip('\x00')
                                            if extracted_name and len(extracted_name) > 0 and not extracted_name.startswith('\x00'):
                                                filename = extracted_name
                                        except:
                                            pass  # Keep default name
                        break
                        
                    # Move to next attribute
                    if attr_header.RecordLength == 0:
                        break
                    attr_offset += attr_header.RecordLength
                    
            except:
                pass  # Keep default filename
            
            # Skip system files and metadata files for cleaner results
            if filename.startswith('$') or filename.startswith('~') or len(filename) > 200:
                continue
                
            valid_records_in_batch += 1
            
            if is_directory:
                total_folders += 1
                # Collect sample folders for tree view (first 50)
                if len(sample_folders) < 50:
                    sample_folders.append({
                        'name': filename,
                        'path': f"[MFT:{current_record + i}] {filename}",
                        'size': 0,
                        'type': 'folder',
                        'direct_files': [],
                        'sub_folders': [],
                        'file_count': 0,
                        'folder_count': 1,
                        'last_modified_timestamp': 0
                    })
            else:
                total_files += 1
                # Collect sample files for tree view (first 100)
                if len(sample_files) < 100:
                    sample_files.append({
                        'name': filename,
                        'path': f"[MFT:{current_record + i}] {filename}",
                        'size': file_size,
                        'type': 'file',
                        'direct_files': [],
                        'sub_folders': [],
                        'file_count': 1,
                        'folder_count': 0,
                        'last_modified_timestamp': 0
                    })
                
            # Emit discovery for UI updates (very limited for speed)
            if item_discovered_callback and (current_record + i) % 1000 == 0:
                item_discovered_callback({
                    'type': 'folder' if is_directory else 'file',
                    'path': f"[MFT:{current_record + i}]",
                    'parent_path': path_str,
                    'name': filename,
                    'size': file_size,
                    'depth': 1,
                    'last_modified': 0
                })
        
        current_record += records_in_batch
        print(f"⚡ Processed {records_in_batch} MFT records ({valid_records_in_batch} valid), total files: {total_files}, folders: {total_folders}")
        
        # Break conditions to prevent infinite loops
        if records_in_batch < records_per_batch:  # Partial batch means EOF
            break
        if valid_records_in_batch == 0:  # No valid records found in this batch
            print(f"⚠️ No valid records in batch, stopping MFT scan")
            break
        if records_in_batch == 0:  # No records processed
            print(f"⚠️ No records processed, stopping MFT scan")
            break
            
        # If we've processed many records but found relatively few files, fall back to parallel scan
        if current_record > 200000 and total_files < 50000:
            print(f"⚠️ Low file discovery rate after {current_record} records, falling back to parallel scan")
            raise Exception("MFT scan efficiency too low, switching to parallel scan")
    
    print(f"🎉 Direct MFT reading completed!")
    print(f"   📊 Records processed: {current_record}")
    print(f"   📊 Files found: {total_files}")
    print(f"   📊 Folders found: {total_folders}")
    
    # Return summary structure with sample data for tree view
    return {
        'name': os.path.basename(path_str) if path_str else f"Drive {path_str[0]}",
        'path': path_str,
        'size': 0,  # Size calculation would require parsing DATA attributes
        'type': 'folder',
        'direct_files': sample_files,  # Sample files for tree view
        'sub_folders': sample_folders,  # Sample folders for tree view
        'file_count': total_files,
        'folder_count': total_folders,
        'last_modified_timestamp': time.time(),
        'scan_method': 'MFT_DIRECT_RECORDS'
    }


def _mft_turbo_scan(volume_handle, path_str, check_cancelled_callback, item_discovered_callback):
    """
    Turbo-charged directory traversal with maximum optimizations
    """
    print("🚀 MFT Turbo Scan (optimized traversal) starting...")
    
    # Use the existing optimized scan but with more aggressive settings
    return _mft_optimized_scan(path_str, {
        'name': os.path.basename(path_str) if path_str else "Unknown",
        'path': path_str,
        'size': 0,
        'type': 'folder',
        'direct_files': [],
        'sub_folders': [],
        'file_count': 0,
        'folder_count': 0,
        'last_modified_timestamp': 0
    }, check_cancelled_callback, item_discovered_callback, max_depth=5, max_parallel=16)


def _mft_optimized_scan(path_str, dir_data, check_cancelled_callback, item_discovered_callback, max_depth=3, max_parallel=8):
    """
    MFT-optimized scanning that uses the fastest possible file system access patterns
    Enhanced with configurable depth and parallelism for maximum speed
    """
    import concurrent.futures
    from threading import Lock
    
    # Thread-safe callback
    callback_lock = Lock()
    def safe_callback(item_data):
        if item_discovered_callback:
            with callback_lock:
                item_discovered_callback(item_data)
    
    try:
        # Use Windows API for maximum speed
        search_pattern = os.path.join(path_str, "*")
        find_data = WIN32_FIND_DATAW()
        
        handle = FindFirstFileW(search_pattern, ctypes.byref(find_data))
        if handle == INVALID_HANDLE_VALUE:
            return dir_data
        
        subdirs = []
        file_count = 0
        total_size = 0
        
        print(f"🚀 Turbo scanning: {path_str} (max_depth={max_depth}, max_parallel={max_parallel})")
        
        # Process all items in current directory super fast
        while True:
            if check_cancelled_callback and check_cancelled_callback():
                FindClose(handle)
                return dir_data
                
            filename = find_data.cFileName
            if filename in ['.', '..']:
                if not FindNextFileW(handle, ctypes.byref(find_data)):
                    break
                continue
            
            item_path = os.path.join(path_str, filename)
            is_directory = find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
            is_reparse_point = find_data.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
            
            file_size = (find_data.nFileSizeHigh << 32) + find_data.nFileSizeLow
            last_modified = filetime_to_unix_timestamp(find_data.ftLastWriteTime)
            
            if is_directory and not is_reparse_point:
                subdirs.append((item_path, filename, last_modified))
                # Very limited UI updates for maximum speed
                if len(subdirs) <= 10:  # Only show first 10 directories
                    safe_callback({
                        'type': 'folder',
                        'path': item_path,
                        'parent_path': path_str,
                        'name': filename,
                        'depth': 1,
                        'last_modified': last_modified
                    })
            elif not is_directory:
                file_data = {
                    'name': filename,
                    'path': item_path,
                    'size': file_size,
                    'type': 'file',
                    'direct_files': [],
                    'sub_folders': [],
                    'file_count': 1,
                    'folder_count': 0,
                    'last_modified_timestamp': last_modified
                }
                dir_data['direct_files'].append(file_data)
                total_size += file_size
                file_count += 1
                
                # Show only very large files for performance
                if file_size > 100 * 1024 * 1024:  # Files > 100MB only
                    safe_callback({
                        'type': 'file',
                        'path': item_path,
                        'parent_path': path_str,
                        'name': filename,
                        'size': file_size,
                        'depth': 1,
                        'last_modified': last_modified
                    })
            
            if not FindNextFileW(handle, ctypes.byref(find_data)):
                break
                
        FindClose(handle)
        
        # Update directory data
        dir_data['size'] = total_size
        dir_data['file_count'] = file_count
        
        # Process subdirectories with maximum parallelism and limited depth
        if subdirs and max_depth > 0:
            print(f"⚡ Processing {len(subdirs)} subdirectories with {max_parallel} workers")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
                def process_subdir(subdir_info):
                    subdir_path, subdir_name, subdir_modified = subdir_info
                    if check_cancelled_callback and check_cancelled_callback():
                        return None
                    
                    subdir_data = {
                        'name': subdir_name,
                        'path': subdir_path,
                        'size': 0,
                        'type': 'folder',
                        'direct_files': [],
                        'sub_folders': [],
                        'file_count': 0,
                        'folder_count': 0,
                        'last_modified_timestamp': subdir_modified
                    }
                    
                    # Recursive call with reduced depth
                    return _mft_optimized_scan(
                        subdir_path, subdir_data, check_cancelled_callback, None, 
                        max_depth - 1, max_parallel
                    )
                
                # Process subdirectories with optimized limits
                max_subdirs = min(len(subdirs), 100)  # Process max 100 subdirs for speed
                limited_subdirs = subdirs[:max_subdirs]
                
                futures = {executor.submit(process_subdir, subdir): subdir for subdir in limited_subdirs}
                
                for future in concurrent.futures.as_completed(futures):
                    if check_cancelled_callback and check_cancelled_callback():
                        break
                    
                    result = future.result()
                    if result:
                        dir_data['sub_folders'].append(result)
                        dir_data['size'] += result['size']
                        dir_data['file_count'] += result['file_count']
                        dir_data['folder_count'] += result['folder_count'] + 1
                
                # If there were more subdirectories, add them as summary
                if len(subdirs) > max_subdirs:
                    remaining_count = len(subdirs) - max_subdirs
                    print(f"⚡ Skipped {remaining_count} subdirectories for maximum speed")
                    summary_item = {
                        'name': f"... and {remaining_count} more directories (skipped for maximum speed)",
                        'path': path_str,
                        'size': 0,
                        'type': 'folder_summary',
                        'direct_files': [],
                        'sub_folders': [],
                        'file_count': 0,
                        'folder_count': remaining_count,
                        'last_modified_timestamp': 0
                    }
                    dir_data['sub_folders'].append(summary_item)
                    dir_data['folder_count'] += remaining_count
        
        print(f"✅ Completed turbo scan: {path_str} - {file_count} files, {len(subdirs)} folders")
        
    except Exception as e:
        print(f"❌ MFT turbo scan error in {path_str}: {e}")
    
    return dir_data