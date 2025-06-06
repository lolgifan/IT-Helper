"""
WiFi utilities module for IT Helper application
Provides WiFi scanning functionality using Windows WlanAPI
"""
import ctypes
from ctypes import wintypes
import time
import subprocess
import os
import uuid


if os.name == 'nt':
    # Load Wlanapi.dll
    wlanapi = ctypes.WinDLL('wlanapi.dll')

    # Define basic types
    DWORD = wintypes.DWORD
    HANDLE = wintypes.HANDLE
    BOOL = wintypes.BOOL
    ULONG = wintypes.ULONG
    LPCWSTR = wintypes.LPCWSTR
    WCHAR = wintypes.WCHAR

    # Constants
    WLAN_API_VERSION_2_0 = 0x00000002
    ERROR_SUCCESS = 0
    DOT11_SSID_MAX_LENGTH = 32
    WLAN_MAX_PHY_TYPE_NUMBER = 8

    class GUID(ctypes.Structure):
        _fields_ = [
            ('Data1', wintypes.ULONG),
            ('Data2', wintypes.USHORT),
            ('Data3', wintypes.USHORT),
            ('Data4', wintypes.BYTE * 8)
        ]

        def __init__(self, guid_string=None):
            if guid_string:
                u = uuid.UUID(guid_string)
                self.Data1 = u.time_low
                self.Data2 = u.time_mid
                self.Data3 = u.time_hi_version
                for i in range(8):
                    self.Data4[i] = u.node.to_bytes(6, 'big')[i] if i < 6 else 0
            super().__init__()

    WLAN_INTERFACE_STATE = DWORD

    class WLAN_INTERFACE_INFO(ctypes.Structure):
        _fields_ = [
            ('InterfaceGuid', GUID),
            ('strInterfaceDescription', WCHAR * 256),
            ('isState', WLAN_INTERFACE_STATE)
        ]

    class WLAN_INTERFACE_INFO_LIST(ctypes.Structure):
        _fields_ = [
            ('dwNumberOfItems', DWORD),
            ('dwIndex', DWORD),
            ('InterfaceInfo', WLAN_INTERFACE_INFO * 1)
        ]
    PWLAN_INTERFACE_INFO_LIST = ctypes.POINTER(WLAN_INTERFACE_INFO_LIST)

    DOT11_MAC_ADDRESS = ctypes.c_ubyte * 6

    class DOT11_SSID(ctypes.Structure):
        _fields_ = [
            ('uSSIDLength', ULONG),
            ('ucSSID', ctypes.c_char * DOT11_SSID_MAX_LENGTH)
        ]

    DOT11_BSS_TYPE = DWORD  # Enum for BSS type

    class WLAN_RATE_SET(ctypes.Structure):
         _fields_ = [
            ('uRateSetLength', ULONG),
            ('usRateSet', wintypes.USHORT * 126)
        ]

    class WLAN_BSS_ENTRY(ctypes.Structure):
        _fields_ = [
            ('dot11Ssid', DOT11_SSID),
            ('uPhyId', ULONG),
            ('dot11Bssid', DOT11_MAC_ADDRESS),
            ('dot11BssType', DOT11_BSS_TYPE),
            ('dot11BssPhyType', DWORD),
            ('lRssi', wintypes.LONG),
            ('uLinkQuality', ULONG),
            ('bInRegDomain', BOOL),
            ('usBeaconPeriod', wintypes.USHORT),
            ('ullTimestamp', ctypes.c_ulonglong),
            ('ullHostTimestamp', ctypes.c_ulonglong),
            ('usCapabilityInformation', wintypes.USHORT),
            ('ulChCenterFrequency', ULONG),
            ('wlanRateSet', WLAN_RATE_SET),
            ('ulIeOffset', ULONG),
            ('ulIeSize', ULONG)
        ]

    class WLAN_BSS_LIST(ctypes.Structure):
        _fields_ = [
            ('dwTotalSize', DWORD),
            ('dwNumberOfItems', DWORD),
            ('wlanBssEntries', WLAN_BSS_ENTRY * 1)
        ]
    PWLAN_BSS_LIST = ctypes.POINTER(WLAN_BSS_LIST)

    # Function prototypes
    WlanOpenHandle = wlanapi.WlanOpenHandle
    WlanOpenHandle.argtypes = [DWORD, ctypes.c_void_p, ctypes.POINTER(DWORD), ctypes.POINTER(HANDLE)]
    WlanOpenHandle.restype = DWORD

    WlanCloseHandle = wlanapi.WlanCloseHandle
    WlanCloseHandle.argtypes = [HANDLE, ctypes.c_void_p]
    WlanCloseHandle.restype = DWORD

    WlanEnumInterfaces = wlanapi.WlanEnumInterfaces
    WlanEnumInterfaces.argtypes = [HANDLE, ctypes.c_void_p, ctypes.POINTER(PWLAN_INTERFACE_INFO_LIST)]
    WlanEnumInterfaces.restype = DWORD

    WlanScan = wlanapi.WlanScan
    WlanScan.argtypes = [HANDLE, ctypes.POINTER(GUID), ctypes.POINTER(DOT11_SSID), ctypes.c_void_p, ctypes.c_void_p]
    WlanScan.restype = DWORD

    WlanGetNetworkBssList = wlanapi.WlanGetNetworkBssList
    WlanGetNetworkBssList.argtypes = [HANDLE, ctypes.POINTER(GUID), ctypes.POINTER(DOT11_SSID), DOT11_BSS_TYPE, BOOL, ctypes.c_void_p, ctypes.POINTER(PWLAN_BSS_LIST)]
    WlanGetNetworkBssList.restype = DWORD

    WlanFreeMemory = wlanapi.WlanFreeMemory
    WlanFreeMemory.argtypes = [ctypes.c_void_p]
    WlanFreeMemory.restype = None

    # Global WlanAPI variables
    _wlan_client_handle = None
    _wlan_interface_guid = None

    # Information Element constants
    IE_RSN_ID = 48
    IE_VENDOR_SPECIFIC_ID = 221

    # Capability Information bits
    CAP_INFO_PRIVACY = 0x0010

    # OUI definitions
    WPA_OUI_TYPE_MICROSOFT = b'\x00\x50\xf2'
    WPA_OUI_SUBTYPE_WPA = 0x01
    RSNA_OUI_TYPE_IEEE = b'\x00\x0f\xac'

    # Cipher Suite selectors
    CS_TKIP = 0x02
    CS_CCMP = 0x04

    # AKM Suite selectors
    AKM_RSNA_802_1X = 0x01
    AKM_RSNA_PSK = 0x02
    AKM_RSNA_SAE = 0x08


def freq_to_channel_band_width(freq_mhz):
    """Convert frequency (MHz) to channel, band, and channel width"""
    if freq_mhz < 2412:
        return None, None, None
    elif freq_mhz <= 2484:
        # 2.4GHz band
        if freq_mhz == 2484:
            channel = 14
        else:
            channel = (freq_mhz - 2412) // 5 + 1
        return channel, "2.4GHz", 20
    elif 5170 <= freq_mhz <= 5825:
        # 5GHz band
        channel = (freq_mhz - 5000) // 5
        return channel, "5GHz", 20
    else:
        return None, None, None


def _ensure_wlanapi_initialized():
    """Ensure WlanAPI is initialized"""
    global _wlan_client_handle, _wlan_interface_guid
    
    if _wlan_client_handle is not None and _wlan_interface_guid is not None:
        return True
        
    try:
        # Open WlanAPI handle
        negotiated_version = DWORD()
        client_handle = HANDLE()
        
        result = WlanOpenHandle(WLAN_API_VERSION_2_0, None, 
                               ctypes.byref(negotiated_version), 
                               ctypes.byref(client_handle))
        
        if result != ERROR_SUCCESS:
            print(f"WlanOpenHandle failed: {result}")
            return False
            
        _wlan_client_handle = client_handle
        print(f"WlanAPI: Handle opened. Negotiated version: {negotiated_version.value}")
        
        # Enumerate interfaces
        interfaces_list_ptr = PWLAN_INTERFACE_INFO_LIST()
        result = WlanEnumInterfaces(_wlan_client_handle, None, 
                                   ctypes.byref(interfaces_list_ptr))
        
        if result != ERROR_SUCCESS:
            print(f"WlanEnumInterfaces failed: {result}")
            WlanCloseHandle(_wlan_client_handle, None)
            _wlan_client_handle = None
            _wlan_interface_guid = None
            return False
            
        if interfaces_list_ptr.contents.dwNumberOfItems == 0:
            print("WlanAPI: No Wi-Fi interfaces found.")
            WlanFreeMemory(interfaces_list_ptr)
            WlanCloseHandle(_wlan_client_handle, None)
            _wlan_client_handle = None
            _wlan_interface_guid = None
            return False
            
        # Use the first interface - FIXED: Create new GUID instance and copy content
        first_interface = interfaces_list_ptr.contents.InterfaceInfo[0]
        _wlan_interface_guid = GUID()  # Create a new GUID instance
        ctypes.pointer(_wlan_interface_guid)[0] = first_interface.InterfaceGuid  # Copy the content
        
        print(f"WlanAPI: Using interface: {first_interface.strInterfaceDescription}")
            
        WlanFreeMemory(interfaces_list_ptr)
        return True
        
    except Exception as e:
        print(f"WlanAPI initialization error: {e}")
        if _wlan_client_handle:
            try:
                WlanCloseHandle(_wlan_client_handle, None)
            except:
                pass
        _wlan_client_handle = None
        _wlan_interface_guid = None
        return False


def _wlanapi_cleanup():
    """Cleanup WlanAPI resources"""
    global _wlan_client_handle
    
    if _wlan_client_handle is not None:
        try:
            WlanCloseHandle(_wlan_client_handle, None)
        except:
            pass
        _wlan_client_handle = None


def get_wifi_data_wlanapi():
    """Get WiFi data using WlanAPI"""
    global _wlan_client_handle, _wlan_interface_guid
    
    if not _ensure_wlanapi_initialized():
        return []
        
    if _wlan_interface_guid is None:
        print("WlanAPI not initialized or no interface.")
        return []
        
    try:
        # Trigger a scan first - IMPORTANT: This was missing!
        print("WlanAPI: Initiating scan...")
        result = WlanScan(_wlan_client_handle, ctypes.byref(_wlan_interface_guid), 
                         None, None, None)
        
        if result != ERROR_SUCCESS:
            print(f"WlanScan failed: {result}")
            if result == 1168:  # ERROR_NOT_FOUND (Element not found)
                print("WlanAPI: WlanScan error 1168, forcing re-init on next cycle.")
                _wlan_client_handle = None  # Force re-init
                _wlan_interface_guid = None
            return []
        
        print("WlanAPI: Scan initiated. Waiting for results...")
        time.sleep(0.5)  # Necessary delay for scan results to populate
        
        # Get BSS list
        bss_list_ptr = PWLAN_BSS_LIST()
        result = WlanGetNetworkBssList(_wlan_client_handle,
                                      ctypes.byref(_wlan_interface_guid),
                                      None,  # All SSIDs
                                      3,     # Any BSS type
                                      False, # Don't include security info
                                      None,
                                      ctypes.byref(bss_list_ptr))
        
        if result != ERROR_SUCCESS:
            print(f"WlanGetNetworkBssList failed: {result}")
            return []
            
        networks = []
        bss_list = bss_list_ptr.contents
        current_time = time.time()
        
        print(f"WlanAPI: Scan results retrieved. Found {bss_list.dwNumberOfItems} BSSIDs.")
        
        for i in range(bss_list.dwNumberOfItems):
            try:
                # Access the i-th BSS entry properly for variable length array
                entry_ptr_addr = ctypes.addressof(bss_list.wlanBssEntries) + i * ctypes.sizeof(WLAN_BSS_ENTRY)
                bss_entry = ctypes.cast(entry_ptr_addr, ctypes.POINTER(WLAN_BSS_ENTRY)).contents
                
                # Extract SSID
                ssid_length = bss_entry.dot11Ssid.uSSIDLength
                if ssid_length > 0:
                    ssid_bytes = bss_entry.dot11Ssid.ucSSID[:ssid_length]
                    try:
                        ssid = ssid_bytes.decode('utf-8', errors='replace')
                    except UnicodeDecodeError:
                        ssid = ssid_bytes.decode('latin-1', errors='replace')
                else:
                    ssid = ""
                    
                if not ssid.strip():
                    ssid = "<Hidden Network>"
                    
                # Extract BSSID
                bssid_bytes = bss_entry.dot11Bssid
                bssid = ":".join([f"{b:02x}" for b in bssid_bytes])
                
                # Get frequency and channel
                freq_khz = bss_entry.ulChCenterFrequency
                freq_mhz = freq_khz / 1000.0
                channel, band, width = freq_to_channel_band_width(freq_mhz)
                
                # Skip unrecognized frequencies
                if channel is None and band is None:
                    continue
                
                # Get signal strength
                signal_dbm = bss_entry.lRssi
                
                # Get encryption info
                encryption = _get_encryption_from_ies_and_cap(
                    bss_entry, bss_entry.usCapabilityInformation
                )
                
                network = {
                    'ssid': ssid,
                    'bssid': bssid,
                    'signal_dbm': signal_dbm,
                    'channel': channel or 0,
                    'frequency_mhz': int(freq_mhz),
                    'band': band or "Unknown",
                    'encryption': encryption,
                    'vendor': "Unknown",
                    'last_seen_timestamp': current_time
                }
                
                networks.append(network)
                
            except Exception as e:
                print(f"Error processing BSS entry {i}: {e}")
                continue
            
        WlanFreeMemory(bss_list_ptr)
        return networks
        
    except Exception as e:
        print(f"WiFi scan error: {e}")
        return []


def get_wifi_data():
    """Main function to get WiFi data"""
    if os.name == 'nt':
        return get_wifi_data_wlanapi()
    else:
        print("WiFi scanning only supported on Windows")
        return []


def _get_encryption_from_ies_and_cap(bss_entry, capability_info):
    """Determine encryption type from capability info"""
    if capability_info & CAP_INFO_PRIVACY:
        # Has privacy bit set - could be WEP, WPA, or WPA2
        # For simplicity, we'll just return "Encrypted"
        # In a full implementation, you'd parse the IEs to determine exact type
        return "Encrypted"
    else:
        return "Open" 