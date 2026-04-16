#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
registry_manager.py - Advanced Windows Registry Management with Full Control
Windows-only module for registry manipulation and persistence
"""

import os
import sys
import json
import struct
import base64
import hashlib
import time
import threading
import platform
import subprocess
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# Import utilities
from ..utils.logger import get_logger
from ..utils.encryption import AES256Manager
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class RegistryHive(Enum):
    """Windows Registry Hives"""
    HKEY_CLASSES_ROOT = "HKEY_CLASSES_ROOT"
    HKEY_CURRENT_USER = "HKEY_CURRENT_USER"
    HKEY_LOCAL_MACHINE = "HKEY_LOCAL_MACHINE"
    HKEY_USERS = "HKEY_USERS"
    HKEY_CURRENT_CONFIG = "HKEY_CURRENT_CONFIG"
    HKEY_PERFORMANCE_DATA = "HKEY_PERFORMANCE_DATA"

class RegistryType(Enum):
    """Registry value types"""
    REG_NONE = 0                    # No type
    REG_SZ = 1                      # String
    REG_EXPAND_SZ = 2               # Expandable string
    REG_BINARY = 3                  # Binary data
    REG_DWORD = 4                   # 32-bit number
    REG_DWORD_BIG_ENDIAN = 5        # 32-bit number (big-endian)
    REG_LINK = 6                    # Symbolic link
    REG_MULTI_SZ = 7                # Multiple strings
    REG_RESOURCE_LIST = 8           # Resource list
    REG_FULL_RESOURCE_DESCRIPTOR = 9  # Full resource descriptor
    REG_RESOURCE_REQUIREMENTS_LIST = 10  # Resource requirements list
    REG_QWORD = 11                  # 64-bit number

@dataclass
class RegistryKey:
    """Registry key information"""
    hive: RegistryHive
    path: str
    full_path: str
    subkey_count: int
    value_count: int
    last_write_time: Optional[datetime] = None
    security_descriptor: Optional[str] = None
    owner: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['hive'] = self.hive.value
        if self.last_write_time:
            data['last_write_time'] = self.last_write_time.isoformat()
        return data

@dataclass
class RegistryValue:
    """Registry value information"""
    name: str
    value_type: RegistryType
    data: Any
    size: int
    last_write_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['value_type'] = self.value_type.value
        data['type_name'] = self.value_type.name
        
        # Convert data based on type
        if self.value_type == RegistryType.REG_BINARY:
            data['data_hex'] = self.data.hex() if self.data else ''
            data['data_base64'] = base64.b64encode(self.data).decode('ascii') if self.data else ''
        elif self.value_type == RegistryType.REG_MULTI_SZ:
            data['data'] = list(self.data) if self.data else []
        
        if self.last_write_time:
            data['last_write_time'] = self.last_write_time.isoformat()
        
        return data

class RegistryManager:
    """Advanced Windows Registry Management with Full Control"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Check platform
        if platform.system() != 'Windows':
            raise RuntimeError("RegistryManager only works on Windows")
        
        # Configuration
        self.privileged_mode = self.config.get('privileged_mode', False)
        self.backup_before_modify = self.config.get('backup_before_modify', True)
        self.encryption_enabled = self.config.get('encryption_enabled', False)
        self.auto_cleanup = self.config.get('auto_cleanup', False)
        
        # Import Windows registry modules
        try:
            import winreg
            self.winreg = winreg
            self.windows_available = True
        except ImportError:
            self.windows_available = False
            logger.error("winreg module not available", module="registry_manager")
            raise
        
        # Encryption for sensitive data
        self.encryption = None
        if self.encryption_enabled:
            try:
                self.encryption = AES256Manager()
            except:
                logger.warning("Encryption initialization failed", module="registry_manager")
        
        # Cache for registry operations
        self.key_cache = {}
        self.value_cache = {}
        self.cache_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'keys_created': 0,
            'keys_deleted': 0,
            'values_set': 0,
            'values_deleted': 0,
            'backups_created': 0,
            'restores_performed': 0,
            'persistence_entries_created': 0,
            'start_time': datetime.now()
        }
        
        # Persistence tracking
        self.persistence_entries = set()
        
        # Backup directory
        self.backup_dir = self.config.get('backup_dir', 'C:\\Windows\\Temp\\RegistryBackups')
        os.makedirs(self.backup_dir, exist_ok=True)
        
        logger.info("Registry Manager initialized", module="registry_manager")
    
    def _get_hive_handle(self, hive: RegistryHive, access: int = None) -> int:
        """Get registry hive handle"""
        if access is None:
            access = self.winreg.KEY_ALL_ACCESS if self.privileged_mode else self.winreg.KEY_READ
        
        hive_map = {
            RegistryHive.HKEY_CLASSES_ROOT: self.winreg.HKEY_CLASSES_ROOT,
            RegistryHive.HKEY_CURRENT_USER: self.winreg.HKEY_CURRENT_USER,
            RegistryHive.HKEY_LOCAL_MACHINE: self.winreg.HKEY_LOCAL_MACHINE,
            RegistryHive.HKEY_USERS: self.winreg.HKEY_USERS,
            RegistryHive.HKEY_CURRENT_CONFIG: self.winreg.HKEY_CURRENT_CONFIG
        }
        
        return hive_map.get(hive, self.winreg.HKEY_CURRENT_USER)
    
    def _split_registry_path(self, full_path: str) -> Tuple[RegistryHive, str]:
        """Split registry path into hive and subpath"""
        full_path = full_path.replace('/', '\\')
        
        hive_map = {
            'HKEY_CLASSES_ROOT': RegistryHive.HKEY_CLASSES_ROOT,
            'HKCR': RegistryHive.HKEY_CLASSES_ROOT,
            'HKEY_CURRENT_USER': RegistryHive.HKEY_CURRENT_USER,
            'HKCU': RegistryHive.HKEY_CURRENT_USER,
            'HKEY_LOCAL_MACHINE': RegistryHive.HKEY_LOCAL_MACHINE,
            'HKLM': RegistryHive.HKEY_LOCAL_MACHINE,
            'HKEY_USERS': RegistryHive.HKEY_USERS,
            'HKU': RegistryHive.HKEY_USERS,
            'HKEY_CURRENT_CONFIG': RegistryHive.HKEY_CURRENT_CONFIG,
            'HKCC': RegistryHive.HKEY_CURRENT_CONFIG
        }
        
        for hive_str, hive_enum in hive_map.items():
            if full_path.upper().startswith(hive_str.upper() + '\\'):
                subpath = full_path[len(hive_str) + 1:].lstrip('\\')
                return hive_enum, subpath
        
        # Default to HKEY_CURRENT_USER
        return RegistryHive.HKEY_CURRENT_USER, full_path
    
    def key_exists(self, key_path: str) -> bool:
        """Check if a registry key exists"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive, self.winreg.KEY_READ)
            
            with self.winreg.OpenKey(handle, subpath, 0, self.winreg.KEY_READ) as key:
                return True
        except WindowsError:
            return False
        except Exception as e:
            logger.error(f"Key exists check error: {e}", module="registry_manager")
            return False
    
    def value_exists(self, key_path: str, value_name: str) -> bool:
        """Check if a registry value exists"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive, self.winreg.KEY_READ)
            
            with self.winreg.OpenKey(handle, subpath, 0, self.winreg.KEY_READ) as key:
                try:
                    self.winreg.QueryValueEx(key, value_name)
                    return True
                except WindowsError:
                    return False
        except Exception as e:
            logger.error(f"Value exists check error: {e}", module="registry_manager")
            return False
    
    def create_key(self, key_path: str, recursive: bool = True) -> bool:
        """Create a registry key"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive)
            
            # Backup if enabled
            if self.backup_before_modify:
                self._backup_key(key_path, 'pre_create')
            
            # Create key
            access = self.winreg.KEY_ALL_ACCESS if self.privileged_mode else self.winreg.KEY_WRITE
            
            if recursive:
                # Create parent keys recursively
                parts = subpath.split('\\')
                current_path = ''
                
                for i, part in enumerate(parts):
                    current_path = '\\'.join(parts[:i+1]) if current_path else part
                    
                    try:
                        with self.winreg.OpenKey(handle, current_path, 0, access):
                            pass
                    except WindowsError:
                        self.winreg.CreateKey(handle, current_path)
            else:
                self.winreg.CreateKey(handle, subpath)
            
            self.stats['keys_created'] += 1
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.REGISTRY_CREATE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"Registry key created: {key_path}",
                details={
                    'key_path': key_path,
                    'recursive': recursive,
                    'timestamp': datetime.now().isoformat()
                },
                resource='registry_manager',
                action='create_key'
            )
            
            logger.info(f"Registry key created: {key_path}", module="registry_manager")
            return True
            
        except Exception as e:
            logger.error(f"Create key error: {e}", module="registry_manager")
            return False
    
    def delete_key(self, key_path: str, recursive: bool = True) -> bool:
        """Delete a registry key"""
        try:
            if not self.key_exists(key_path):
                return False
            
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive)
            
            # Backup if enabled
            if self.backup_before_modify:
                self._backup_key(key_path, 'pre_delete')
            
            # Delete key
            if recursive:
                # Delete subkeys first
                subkeys = self.list_subkeys(key_path)
                for subkey in subkeys:
                    self.delete_key(f"{key_path}\\{subkey}", recursive=True)
            
            self.winreg.DeleteKey(handle, subpath)
            
            self.stats['keys_deleted'] += 1
            
            # Clear cache
            cache_key = f"{hive.value}\\{subpath}"
            with self.cache_lock:
                if cache_key in self.key_cache:
                    del self.key_cache[cache_key]
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.REGISTRY_DELETE.value,
                severity=AuditSeverity.WARNING.value,
                user='system',
                source_ip='localhost',
                description=f"Registry key deleted: {key_path}",
                details={
                    'key_path': key_path,
                    'recursive': recursive,
                    'timestamp': datetime.now().isoformat()
                },
                resource='registry_manager',
                action='delete_key'
            )
            
            logger.info(f"Registry key deleted: {key_path}", module="registry_manager")
            return True
            
        except Exception as e:
            logger.error(f"Delete key error: {e}", module="registry_manager")
            return False
    
    def list_subkeys(self, key_path: str) -> List[str]:
        """List all subkeys under a registry key"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive, self.winreg.KEY_READ)
            
            subkeys = []
            with self.winreg.OpenKey(handle, subpath, 0, self.winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        subkey_name = self.winreg.EnumKey(key, i)
                        subkeys.append(subkey_name)
                        i += 1
                    except WindowsError:
                        break
            
            return subkeys
            
        except Exception as e:
            logger.error(f"List subkeys error: {e}", module="registry_manager")
            return []
    
    def list_values(self, key_path: str) -> List[str]:
        """List all values under a registry key"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive, self.winreg.KEY_READ)
            
            values = []
            with self.winreg.OpenKey(handle, subpath, 0, self.winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        value_name = self.winreg.EnumValue(key, i)[0]
                        values.append(value_name)
                        i += 1
                    except WindowsError:
                        break
            
            return values
            
        except Exception as e:
            logger.error(f"List values error: {e}", module="registry_manager")
            return []
    
    def get_key_info(self, key_path: str) -> Optional[RegistryKey]:
        """Get detailed information about a registry key"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive, self.winreg.KEY_READ)
            
            with self.winreg.OpenKey(handle, subpath, 0, self.winreg.KEY_READ) as key:
                # Get key info
                subkey_count, value_count, last_write_time = self.winreg.QueryInfoKey(key)
                
                # Convert Windows FILETIME to datetime
                if last_write_time:
                    # Windows FILETIME is 100-nanosecond intervals since 1601-01-01
                    epoch_start = datetime(1601, 1, 1)
                    seconds = last_write_time / 10_000_000
                    last_write_dt = epoch_start + timedelta(seconds=seconds)
                else:
                    last_write_dt = None
                
                key_info = RegistryKey(
                    hive=hive,
                    path=subpath,
                    full_path=f"{hive.value}\\{subpath}",
                    subkey_count=subkey_count,
                    value_count=value_count,
                    last_write_time=last_write_dt
                )
                
                # Cache the result
                cache_key = f"{hive.value}\\{subpath}"
                with self.cache_lock:
                    self.key_cache[cache_key] = key_info
                
                return key_info
            
        except Exception as e:
            logger.error(f"Get key info error: {e}", module="registry_manager")
            return None
    
    def get_value(self, key_path: str, value_name: str = "") -> Optional[RegistryValue]:
        """Get a registry value"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive, self.winreg.KEY_READ)
            
            with self.winreg.OpenKey(handle, subpath, 0, self.winreg.KEY_READ) as key:
                # Get value
                data, reg_type = self.winreg.QueryValueEx(key, value_name)
                
                # Get value info
                value_info = None
                try:
                    # Try to get value info (not directly available in winreg)
                    i = 0
                    while True:
                        name, data_val, type_val = self.winreg.EnumValue(key, i)
                        if name == value_name:
                            # Estimate size
                            size = len(str(data_val).encode('utf-8')) if isinstance(data_val, str) else len(data_val)
                            value_info = RegistryValue(
                                name=name,
                                value_type=RegistryType(type_val),
                                data=data_val,
                                size=size
                            )
                            break
                        i += 1
                except WindowsError:
                    # Fallback if EnumValue fails
                    size = len(str(data).encode('utf-8')) if isinstance(data, str) else len(data)
                    value_info = RegistryValue(
                        name=value_name,
                        value_type=RegistryType(reg_type),
                        data=data,
                        size=size
                    )
                
                # Cache the result
                cache_key = f"{hive.value}\\{subpath}\\{value_name}"
                with self.cache_lock:
                    self.value_cache[cache_key] = value_info
                
                return value_info
            
        except Exception as e:
            logger.error(f"Get value error: {e}", module="registry_manager")
            return None
    
    def set_value(self, key_path: str, value_name: str, value_data: Any, 
                 value_type: RegistryType = None) -> bool:
        """Set a registry value"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive)
            
            # Backup if enabled
            if self.backup_before_modify:
                self._backup_key(key_path, 'pre_set_value')
            
            # Determine value type if not specified
            if value_type is None:
                if isinstance(value_data, str):
                    value_type = RegistryType.REG_SZ
                elif isinstance(value_data, int):
                    if value_data.bit_length() <= 32:
                        value_type = RegistryType.REG_DWORD
                    else:
                        value_type = RegistryType.REG_QWORD
                elif isinstance(value_data, bytes):
                    value_type = RegistryType.REG_BINARY
                elif isinstance(value_data, list) and all(isinstance(x, str) for x in value_data):
                    value_type = RegistryType.REG_MULTI_SZ
                else:
                    value_type = RegistryType.REG_SZ
            
            # Convert data for registry
            if value_type == RegistryType.REG_MULTI_SZ:
                # Multi-string needs null termination
                reg_data = '\0'.join(value_data) + '\0\0'
            elif value_type == RegistryType.REG_BINARY and self.encryption_enabled and self.encryption:
                # Encrypt binary data
                reg_data = self.encryption.encrypt(value_data)
            else:
                reg_data = value_data
            
            # Set value
            access = self.winreg.KEY_ALL_ACCESS if self.privileged_mode else self.winreg.KEY_WRITE
            
            with self.winreg.OpenKey(handle, subpath, 0, access) as key:
                self.winreg.SetValueEx(key, value_name, 0, value_type.value, reg_data)
            
            self.stats['values_set'] += 1
            
            # Clear cache
            cache_key = f"{hive.value}\\{subpath}\\{value_name}"
            with self.cache_lock:
                if cache_key in self.value_cache:
                    del self.value_cache[cache_key]
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.REGISTRY_SET.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"Registry value set: {key_path}\\{value_name}",
                details={
                    'key_path': key_path,
                    'value_name': value_name,
                    'value_type': value_type.name,
                    'encrypted': self.encryption_enabled,
                    'timestamp': datetime.now().isoformat()
                },
                resource='registry_manager',
                action='set_value'
            )
            
            logger.info(f"Registry value set: {key_path}\\{value_name}", module="registry_manager")
            return True
            
        except Exception as e:
            logger.error(f"Set value error: {e}", module="registry_manager")
            return False
    
    def delete_value(self, key_path: str, value_name: str) -> bool:
        """Delete a registry value"""
        try:
            hive, subpath = self._split_registry_path(key_path)
            handle = self._get_hive_handle(hive)
            
            # Backup if enabled
            if self.backup_before_modify:
                self._backup_key(key_path, 'pre_delete_value')
            
            # Delete value
            access = self.winreg.KEY_ALL_ACCESS if self.privileged_mode else self.winreg.KEY_WRITE
            
            with self.winreg.OpenKey(handle, subpath, 0, access) as key:
                self.winreg.DeleteValue(key, value_name)
            
            self.stats['values_deleted'] += 1
            
            # Clear cache
            cache_key = f"{hive.value}\\{subpath}\\{value_name}"
            with self.cache_lock:
                if cache_key in self.value_cache:
                    del self.value_cache[cache_key]
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.REGISTRY_DELETE.value,
                severity=AuditSeverity.WARNING.value,
                user='system',
                source_ip='localhost',
                description=f"Registry value deleted: {key_path}\\{value_name}",
                details={
                    'key_path': key_path,
                    'value_name': value_name,
                    'timestamp': datetime.now().isoformat()
                },
                resource='registry_manager',
                action='delete_value'
            )
            
            logger.info(f"Registry value deleted: {key_path}\\{value_name}", module="registry_manager")
            return True
            
        except Exception as e:
            logger.error(f"Delete value error: {e}", module="registry_manager")
            return False
    
    def _backup_key(self, key_path: str, reason: str) -> Optional[str]:
        """Backup a registry key to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_key_path = key_path.replace('\\', '_').replace(':', '').replace('/', '_')
            backup_file = os.path.join(self.backup_dir, f"{safe_key_path}_{reason}_{timestamp}.reg")
            
            # Use reg export command
            cmd = ['reg', 'export', key_path, backup_file, '/y']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.stats['backups_created'] += 1
                logger.debug(f"Registry backup created: {backup_file}", module="registry_manager")
                return backup_file
            else:
                logger.warning(f"Registry backup failed: {result.stderr}", module="registry_manager")
                return None
            
        except Exception as e:
            logger.error(f"Backup key error: {e}", module="registry_manager")
            return None
    
    def restore_key(self, backup_file: str, key_path: str = None) -> bool:
        """Restore a registry key from backup file"""
        try:
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}", module="registry_manager")
                return False
            
            # Determine key path from backup if not provided
            if key_path is None:
                # Read first line of .reg file to get key path
                with open(backup_file, 'r', encoding='utf-16-le') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('Windows Registry Editor Version'):
                        second_line = f.readline().strip()
                        if second_line.startswith('[') and second_line.endswith(']'):
                            key_path = second_line[1:-1]
            
            if not key_path:
                logger.error("Could not determine key path from backup", module="registry_manager")
                return False
            
            # Use reg import command
            cmd = ['reg', 'import', backup_file]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.stats['restores_performed'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.REGISTRY_RESTORE.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Registry key restored: {key_path}",
                    details={
                        'key_path': key_path,
                        'backup_file': backup_file,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='registry_manager',
                    action='restore_key'
                )
                
                logger.info(f"Registry key restored: {key_path}", module="registry_manager")
                return True
            else:
                logger.error(f"Restore failed: {result.stderr}", module="registry_manager")
                return False
            
        except Exception as e:
            logger.error(f"Restore key error: {e}", module="registry_manager")
            return False
    
    def add_persistence(self, executable_path: str, 
                       persistence_method: str = "run",
                       key_name: str = None,
                       hidden: bool = True) -> bool:
        """Add persistence via registry"""
        try:
            if not os.path.exists(executable_path):
                logger.error(f"Executable not found: {executable_path}", module="registry_manager")
                return False
            
            # Common persistence locations
            persistence_locations = {
                "run": "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                "run_once": "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
                "run_services": "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                "run_services_once": "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
                "explorer": "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer\\Run",
                "winlogon": "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon\\Userinit",
                "startup": "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders\\Startup"
            }
            
            key_path = persistence_locations.get(persistence_method)
            if not key_path:
                logger.error(f"Unknown persistence method: {persistence_method}", module="registry_manager")
                return False
            
            # Generate key name if not provided
            if not key_name:
                exe_name = os.path.basename(executable_path)
                key_name = f"{exe_name}_{int(time.time())}"
            
            # Create key if it doesn't exist
            if not self.key_exists(key_path):
                self.create_key(key_path, recursive=True)
            
            # Set value for persistence
            if persistence_method == "winlogon":
                # Winlogon requires special handling
                existing_value = self.get_value(key_path, "Userinit")
                if existing_value:
                    # Append to existing Userinit
                    new_value = f"{existing_value.data},{executable_path}"
                else:
                    new_value = f"C:\\Windows\\system32\\userinit.exe,{executable_path}"
            else:
                # Standard run key
                if hidden:
                    # Use powershell to run hidden
                    new_value = f'powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "{executable_path}"'
                else:
                    new_value = executable_path
            
            success = self.set_value(key_path, key_name, new_value, RegistryType.REG_SZ)
            
            if success:
                self.stats['persistence_entries_created'] += 1
                self.persistence_entries.add(f"{key_path}\\{key_name}")
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.PERSISTENCE_ADD.value,
                    severity=AuditSeverity.HIGH.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Persistence added: {key_path}\\{key_name}",
                    details={
                        'key_path': key_path,
                        'key_name': key_name,
                        'executable_path': executable_path,
                        'persistence_method': persistence_method,
                        'hidden': hidden,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='registry_manager',
                    action='add_persistence'
                )
                
                logger.info(f"Persistence added: {key_path}\\{key_name}", module="registry_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Add persistence error: {e}", module="registry_manager")
            return False
    
    def remove_persistence(self, key_path: str, value_name: str) -> bool:
        """Remove persistence entry"""
        try:
            success = self.delete_value(key_path, value_name)
            
            if success:
                entry = f"{key_path}\\{value_name}"
                if entry in self.persistence_entries:
                    self.persistence_entries.remove(entry)
                
                logger.info(f"Persistence removed: {entry}", module="registry_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Remove persistence error: {e}", module="registry_manager")
            return False
    
    def cleanup_persistence(self) -> int:
        """Remove all persistence entries created by this manager"""
        removed = 0
        
        try:
            entries_to_remove = list(self.persistence_entries)
            
            for entry in entries_to_remove:
                # Parse entry
                if '\\' in entry:
                    last_backslash = entry.rindex('\\')
                    key_path = entry[:last_backslash]
                    value_name = entry[last_backslash + 1:]
                    
                    if self.delete_value(key_path, value_name):
                        removed += 1
                        self.persistence_entries.remove(entry)
            
            logger.info(f"Cleaned up {removed} persistence entries", module="registry_manager")
            return removed
            
        except Exception as e:
            logger.error(f"Cleanup persistence error: {e}", module="registry_manager")
            return 0
    
    def search_values(self, search_term: str, search_data: bool = False) -> List[Dict[str, Any]]:
        """Search for registry values containing search term"""
        results = []
        
        try:
            # Search in common locations
            search_paths = [
                "HKEY_CURRENT_USER\\Software",
                "HKEY_LOCAL_MACHINE\\Software",
                "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                "HKEY_LOCAL_MACHINE\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
            ]
            
            for base_path in search_paths:
                try:
                    # Get all subkeys
                    subkeys = self.list_subkeys(base_path)
                    for subkey in subkeys:
                        full_path = f"{base_path}\\{subkey}"
                        
                        # Get values
                        values = self.list_values(full_path)
                        for value_name in values:
                            try:
                                value_info = self.get_value(full_path, value_name)
                                if value_info:
                                    # Search in name
                                    if search_term.lower() in value_name.lower():
                                        results.append({
                                            'path': full_path,
                                            'value': value_info.to_dict()
                                        })
                                    
                                    # Search in data if enabled
                                    if search_data and value_info.data:
                                        if isinstance(value_info.data, str):
                                            if search_term.lower() in value_info.data.lower():
                                                results.append({
                                                    'path': full_path,
                                                    'value': value_info.to_dict()
                                                })
                                        elif isinstance(value_info.data, bytes):
                                            try:
                                                data_str = value_info.data.decode('utf-8', errors='ignore')
                                                if search_term.lower() in data_str.lower():
                                                    results.append({
                                                        'path': full_path,
                                                        'value': value_info.to_dict()
                                                    })
                                            except:
                                                pass
                            except:
                                continue
                except:
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"Search values error: {e}", module="registry_manager")
            return []
    
    def export_key(self, key_path: str, output_file: str) -> bool:
        """Export registry key to .reg file"""
        try:
            return self._backup_key(key_path, 'export') is not None
        except Exception as e:
            logger.error(f"Export key error: {e}", module="registry_manager")
            return False
    
    def import_key(self, reg_file: str) -> bool:
        """Import registry key from .reg file"""
        try:
            return self.restore_key(reg_file)
        except Exception as e:
            logger.error(f"Import key error: {e}", module="registry_manager")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry manager statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
            'persistence_entries_count': len(self.persistence_entries),
            'key_cache_size': len(self.key_cache),
            'value_cache_size': len(self.value_cache),
            'privileged_mode': self.privileged_mode,
            'encryption_enabled': self.encryption_enabled,
            'backup_directory': self.backup_dir,
            'backup_count': len([f for f in os.listdir(self.backup_dir) if f.endswith('.reg')]) if os.path.exists(self.backup_dir) else 0
        }
    
    def export_registry_snapshot(self, output_file: str = None) -> Optional[str]:
        """Export complete registry snapshot"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if output_file is None:
                output_file = os.path.join(self.backup_dir, f"registry_snapshot_{timestamp}.json")
            
            snapshot = {
                'timestamp': datetime.now().isoformat(),
                'statistics': self.get_statistics(),
                'persistence_entries': list(self.persistence_entries),
                'key_cache': {k: v.to_dict() for k, v in self.key_cache.items()},
                'value_cache': {k: v.to_dict() for k, v in self.value_cache.items()}
            }
            
            with open(output_file, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            
            logger.info(f"Registry snapshot exported to {output_file}", module="registry_manager")
            return output_file
            
        except Exception as e:
            logger.error(f"Export registry snapshot error: {e}", module="registry_manager")
            return None
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            if self.auto_cleanup:
                self.cleanup_persistence()
        except:
            pass

# Global instance
_registry_manager = None

def get_registry_manager(config: Dict = None) -> RegistryManager:
    """Get or create registry manager instance"""
    global _registry_manager
    
    if _registry_manager is None:
        _registry_manager = RegistryManager(config)
    
    return _registry_manager

if __name__ == "__main__":
    print("Testing Registry Manager (Windows only)...")
    
    if platform.system() != 'Windows':
        print("❌ This module only works on Windows")
        sys.exit(1)
    
    # Test configuration
    config = {
        'privileged_mode': False,
        'backup_before_modify': True,
        'encryption_enabled': False,
        'auto_cleanup': False,
        'backup_dir': 'C:\\Windows\\Temp\\RegistryTest'
    }
    
    try:
        rm = get_registry_manager(config)
        
        print("\n1. Testing basic operations...")
        
        # Test key creation
        test_key = "HKEY_CURRENT_USER\\Software\\TestRegistryManager"
        print(f"Creating test key: {test_key}")
        if rm.create_key(test_key):
            print("✅ Key created successfully")
        else:
            print("❌ Key creation failed")
        
        # Test value setting
        print(f"\n2. Setting test value...")
        if rm.set_value(test_key, "TestValue", "Hello Registry", RegistryType.REG_SZ):
            print("✅ Value set successfully")
        else:
            print("❌ Value setting failed")
        
        # Test value retrieval
        print(f"\n3. Retrieving test value...")
        value_info = rm.get_value(test_key, "TestValue")
        if value_info:
            print(f"✅ Value retrieved: {value_info.data}")
        else:
            print("❌ Value retrieval failed")
        
        # Test listing
        print(f"\n4. Listing values...")
        values = rm.list_values(test_key)
        print(f"Values: {values}")
        
        # Test search
        print(f"\n5. Searching for values...")
        results = rm.search_values("Test", search_data=True)
        print(f"Found {len(results)} matching values")
        
        # Test persistence (simulated)
        print(f"\n6. Testing persistence methods...")
        test_exe = "C:\\Windows\\System32\\calc.exe"
        if os.path.exists(test_exe):
            # Just test the method, don't actually add persistence
            print("Persistence methods available")
        else:
            print("Test executable not found, skipping persistence test")
        
        # Test statistics
        print(f"\n7. Getting statistics...")
        stats = rm.get_statistics()
        print(f"Keys created: {stats['keys_created']}")
        print(f"Values set: {stats['values_set']}")
        print(f"Backups created: {stats['backups_created']}")
        
        # Cleanup
        print(f"\n8. Cleaning up test key...")
        if rm.delete_key(test_key, recursive=True):
            print("✅ Test key deleted")
        else:
            print("❌ Test key deletion failed")
        
        # Export snapshot
        print(f"\n9. Exporting snapshot...")
        snapshot_file = rm.export_registry_snapshot()
        if snapshot_file:
            print(f"✅ Snapshot exported to: {snapshot_file}")
        else:
            print("❌ Snapshot export failed")
        
        print("\n✅ Registry Manager tests completed!")
        
    except Exception as e:
        print(f"❌ Registry Manager test error: {e}")
