"""
Simple logging utility for IT Helper
Replaces print statements with configurable logging for better performance
"""

import sys
import os
from datetime import datetime

# Global logging configuration
LOG_LEVEL = os.getenv('IT_HELPER_LOG_LEVEL', 'ERROR')  # Default to ERROR only
LOG_TO_FILE = os.getenv('IT_HELPER_LOG_FILE', None)

class LogLevel:
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3

LEVEL_MAP = {
    'DEBUG': LogLevel.DEBUG,
    'INFO': LogLevel.INFO,
    'WARNING': LogLevel.WARNING,
    'ERROR': LogLevel.ERROR
}

CURRENT_LEVEL = LEVEL_MAP.get(LOG_LEVEL.upper(), LogLevel.ERROR)

def log(level, message, module_name="IT_Helper"):
    """Log a message if it meets the current log level threshold"""
    if level < CURRENT_LEVEL:
        return
    
    level_names = {
        LogLevel.DEBUG: "DEBUG",
        LogLevel.INFO: "INFO", 
        LogLevel.WARNING: "WARNING",
        LogLevel.ERROR: "ERROR"
    }
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_message = f"[{timestamp}] {level_names.get(level, 'UNKNOWN')} [{module_name}]: {message}"
    
    if LOG_TO_FILE:
        try:
            with open(LOG_TO_FILE, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')
        except:
            pass  # Fail silently if can't write to file
    else:
        print(log_message)

def debug(message, module_name="IT_Helper"):
    """Log debug message"""
    log(LogLevel.DEBUG, message, module_name)

def info(message, module_name="IT_Helper"):
    """Log info message"""
    log(LogLevel.INFO, message, module_name)

def warning(message, module_name="IT_Helper"):
    """Log warning message"""
    log(LogLevel.WARNING, message, module_name)

def error(message, module_name="IT_Helper"):
    """Log error message"""
    log(LogLevel.ERROR, message, module_name)

# Compatibility function for existing debug_print calls
def debug_print(message, module_name="IT_Helper"):
    """Compatibility function for existing debug_print calls"""
    debug(message, module_name) 