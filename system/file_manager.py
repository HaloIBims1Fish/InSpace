#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
file_manager.py - Advanced File System Management with Full Control
"""

import os
import sys
import stat
import shutil
import hashlib
import mimetypes
import magic
import json
import csv
import pickle
import zipfile
import tarfile
import gzip
import bz2
import lzma
import tempfile
import fnmatch
import pathlib
import time
import threading
import queue
import concurrent.futures
from typing import Dict, List, Optional, Tuple, Any, Union, BinaryIO, Generator
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field
from enum import Enum
import platform

# Import utilities
from ..utils.logger import get_logger
from ..utils.encryption import AES256Manager, RSAEncryption
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class FileType(Enum):
    """File type classification"""
    REGULAR = "regular"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    DEVICE = "device"
    FIFO = "fifo"
    SOCKET = "socket"
    UNKNOWN = "unknown"

class Permission(Enum):
    """File permissions"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ALL = "all"

@dataclass
class FileInfo:
    """Detailed file information"""
    path: str
    name: str
    size: int
    file_type: FileType
    permissions: Dict[str, bool]
    owner: Optional[str] = None
    group: Optional[str] = None
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    accessed_time: Optional[datetime] = None
    mime_type: Optional[str] = None
    hash_md5: Optional[str] = None
    hash_sha1: Optional[str] = None
    hash_sha256: Optional[str] = None
    extension: Optional[str] = None
    is_hidden: bool = False
    is_system: bool = False
    is_readonly: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['file_type'] = self.file_type.value
        data['permissions'] = self.permissions
        
        # Convert timestamps
        for time_field in ['created_time', 'modified_time', 'accessed_time']:
            if getattr(self, time_field):
                data[time_field] = getattr(self, time_field).isoformat()
        
        # Add human-readable size
        data['size_human'] = self._human_size(self.size)
        
        return data
    
    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """Convert bytes to human readable format"""
        if size_bytes == 0:
            return "0B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.2f}{units[i]}"

@dataclass
class SearchResult:
    """File search result"""
    file_info: FileInfo
    match_type: str  # 'name', 'content', 'metadata'
    match_score: float  # 0.0 to 1.0
    matched_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'file_info': self.file_info.to_dict(),
            'match_type': self.match_type,
            'match_score': self.match_score,
            'matched_text': self.matched_text
        }

class FileManager:
    """Advanced File System Management with Full Control"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.max_file_size = self.config.get('max_file_size', 100 * 1024 * 1024)  # 100MB default
        self.encryption_enabled = self.config.get('encryption_enabled', False)
        self.compression_enabled = self.config.get('compression_enabled', False)
        self.temp_dir = self.config.get('temp_dir', tempfile.gettempdir())
        self.backup_dir = self.config.get('backup_dir', os.path.join(tempfile.gettempdir(), 'file_backups'))
        self.max_workers = self.config.get('max_workers', min(32, (os.cpu_count() or 1) * 4))
        
        # Initialize encryption if enabled
        self.encryption = None
        if self.encryption_enabled:
            try:
                self.encryption = AES256Manager()
            except:
                logger.warning("Encryption initialization failed", module="file_manager")
        
        # Initialize file magic for MIME type detection
        self.magic = None
        try:
            self.magic = magic.Magic(mime=True)
        except:
            logger.warning("python-magic not available, using mimetypes fallback", module="file_manager")
        
        # Initialize mimetypes
        mimetypes.init()
        
        # Statistics
        self.stats = {
            'files_processed': 0,
            'files_copied': 0,
            'files_moved': 0,
            'files_deleted': 0,
            'files_encrypted': 0,
            'files_decrypted': 0,
            'files_compressed': 0,
            'files_decompressed': 0,
            'searches_performed': 0,
            'start_time': datetime.now()
        }
        
        # Cache for file operations
        self.file_cache = {}
        self.hash_cache = {}
        self.cache_lock = threading.Lock()
        
        # Worker pool for parallel operations
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Create backup directory
        os.makedirs(self.backup_dir, exist_ok=True)
        
        logger.info("File Manager initialized", module="file_manager")
    
    def get_file_info(self, file_path: str, calculate_hash: bool = False) -> Optional[FileInfo]:
        """Get detailed information about a file"""
        try:
            # Check cache first
            cache_key = f"info_{file_path}"
            with self.cache_lock:
                if cache_key in self.file_cache:
                    return self.file_cache[cache_key]
            
            # Get file stats
            try:
                stat_info = os.stat(file_path)
            except (OSError, IOError) as e:
                logger.error(f"File stat error for {file_path}: {e}", module="file_manager")
                return None
            
            # Determine file type
            file_type = FileType.UNKNOWN
            mode = stat_info.st_mode
            
            if stat.S_ISREG(mode):
                file_type = FileType.REGULAR
            elif stat.S_ISDIR(mode):
                file_type = FileType.DIRECTORY
            elif stat.S_ISLNK(mode):
                file_type = FileType.SYMLINK
            elif stat.S_ISCHR(mode) or stat.S_ISBLK(mode):
                file_type = FileType.DEVICE
            elif stat.S_ISFIFO(mode):
                file_type = FileType.FIFO
            elif stat.S_ISSOCK(mode):
                file_type = FileType.SOCKET
            
            # Get permissions
            permissions = {
                'owner_read': bool(mode & stat.S_IRUSR),
                'owner_write': bool(mode & stat.S_IWUSR),
                'owner_execute': bool(mode & stat.S_IXUSR),
                'group_read': bool(mode & stat.S_IRGRP),
                'group_write': bool(mode & stat.S_IWGRP),
                'group_execute': bool(mode & stat.S_IXGRP),
                'others_read': bool(mode & stat.S_IROTH),
                'others_write': bool(mode & stat.S_IWOTH),
                'others_execute': bool(mode & stat.S_IXOTH)
            }
            
            # Get owner and group (platform specific)
            owner = group = None
            try:
                if platform.system() != 'Windows':
                    import pwd
                    import grp
                    owner = pwd.getpwuid(stat_info.st_uid).pw_name
                    group = grp.getgrgid(stat_info.st_gid).gr_name
            except:
                pass
            
            # Get timestamps
            created_time = datetime.fromtimestamp(stat_info.st_ctime)
            modified_time = datetime.fromtimestamp(stat_info.st_mtime)
            accessed_time = datetime.fromtimestamp(stat_info.st_atime)
            
            # Get MIME type
            mime_type = None
            if self.magic and os.path.isfile(file_path):
                try:
                    mime_type = self.magic.from_file(file_path)
                except:
                    pass
            
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(file_path)
            
            # Calculate hashes if requested
            hash_md5 = hash_sha1 = hash_sha256 = None
            if calculate_hash and os.path.isfile(file_path):
                hash_cache_key = f"hash_{file_path}_{stat_info.st_size}_{stat_info.st_mtime}"
                with self.cache_lock:
                    if hash_cache_key in self.hash_cache:
                        hash_md5, hash_sha1, hash_sha256 = self.hash_cache[hash_cache_key]
                    else:
                        hash_md5, hash_sha1, hash_sha256 = self._calculate_file_hashes(file_path)
                        self.hash_cache[hash_cache_key] = (hash_md5, hash_sha1, hash_sha256)
            
            # Check if hidden (platform specific)
            is_hidden = False
            if platform.system() == 'Windows':
                import ctypes
                try:
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
                    is_hidden = bool(attrs & 2)  # FILE_ATTRIBUTE_HIDDEN
                except:
                    pass
            else:
                is_hidden = os.path.basename(file_path).startswith('.')
            
            # Check if system file (Windows only)
            is_system = False
            if platform.system() == 'Windows':
                import ctypes
                try:
                    attrs = ctypes.windll.kernel32.GetFileAttributesW(file_path)
                    is_system = bool(attrs & 4)  # FILE_ATTRIBUTE_SYSTEM
                except:
                    pass
            
            # Check if read-only
            is_readonly = not os.access(file_path, os.W_OK)
            
            # Get extension
            _, extension = os.path.splitext(file_path)
            extension = extension.lower() if extension else None
            
            # Create FileInfo object
            file_info = FileInfo(
                path=os.path.abspath(file_path),
                name=os.path.basename(file_path),
                size=stat_info.st_size,
                file_type=file_type,
                permissions=permissions,
                owner=owner,
                group=group,
                created_time=created_time,
                modified_time=modified_time,
                accessed_time=accessed_time,
                mime_type=mime_type,
                hash_md5=hash_md5,
                hash_sha1=hash_sha1,
                hash_sha256=hash_sha256,
                extension=extension,
                is_hidden=is_hidden,
                is_system=is_system,
                is_readonly=is_readonly
            )
            
            # Cache the result
            with self.cache_lock:
                self.file_cache[cache_key] = file_info
            
            self.stats['files_processed'] += 1
            
            return file_info
            
        except Exception as e:
            logger.error(f"Get file info error for {file_path}: {e}", module="file_manager")
            return None
    
    def _calculate_file_hashes(self, file_path: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Calculate MD5, SHA1, and SHA256 hashes for a file"""
        try:
            hash_md5 = hashlib.md5()
            hash_sha1 = hashlib.sha1()
            hash_sha256 = hashlib.sha256()
            
            with open(file_path, 'rb') as f:
                # Read in chunks to handle large files
                chunk_size = 8192
                while chunk := f.read(chunk_size):
                    hash_md5.update(chunk)
                    hash_sha1.update(chunk)
                    hash_sha256.update(chunk)
            
            return hash_md5.hexdigest(), hash_sha1.hexdigest(), hash_sha256.hexdigest()
            
        except Exception as e:
            logger.error(f"Calculate file hashes error for {file_path}: {e}", module="file_manager")
            return None, None, None
    
    def list_directory(self, directory_path: str, recursive: bool = False, 
                      include_hidden: bool = False, include_system: bool = False) -> List[FileInfo]:
        """List files in a directory"""
        try:
            if not os.path.isdir(directory_path):
                logger.error(f"Not a directory: {directory_path}", module="file_manager")
                return []
            
            results = []
            
            if recursive:
                for root, dirs, files in os.walk(directory_path):
                    # Filter hidden/system directories if needed
                    if not include_hidden:
                        dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    # Process files in current directory
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        
                        # Skip hidden/system files if needed
                        if not include_hidden and filename.startswith('.'):
                            continue
                        
                        file_info = self.get_file_info(file_path)
                        if file_info:
                            results.append(file_info)
            else:
                for entry in os.listdir(directory_path):
                    file_path = os.path.join(directory_path, entry)
                    
                    # Skip hidden/system files if needed
                    if not include_hidden and entry.startswith('.'):
                        continue
                    
                    file_info = self.get_file_info(file_path)
                    if file_info:
                        results.append(file_info)
            
            return results
            
        except Exception as e:
            logger.error(f"List directory error for {directory_path}: {e}", module="file_manager")
            return []
    
    def copy_file(self, source_path: str, destination_path: str, 
                 overwrite: bool = True, preserve_metadata: bool = True) -> bool:
        """Copy a file with advanced options"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}", module="file_manager")
                return False
            
            # Check if destination exists and overwrite is disabled
            if os.path.exists(destination_path) and not overwrite:
                logger.error(f"Destination exists and overwrite disabled: {destination_path}", module="file_manager")
                return False
            
            # Create backup if overwriting existing file
            if os.path.exists(destination_path) and self.config.get('backup_before_overwrite', True):
                backup_path = self._create_backup(destination_path)
                if backup_path:
                    logger.debug(f"Created backup: {backup_path}", module="file_manager")
            
            # Copy the file
            if preserve_metadata:
                shutil.copy2(source_path, destination_path)
            else:
                shutil.copy(source_path, destination_path)
            
            self.stats['files_copied'] += 1
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.FILE_COPY.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"File copied: {source_path} -> {destination_path}",
                details={
                    'source_path': source_path,
                    'destination_path': destination_path,
                    'overwrite': overwrite,
                    'preserve_metadata': preserve_metadata,
                    'timestamp': datetime.now().isoformat()
                },
                resource='file_manager',
                action='copy_file'
            )
            
            logger.info(f"File copied: {source_path} -> {destination_path}", module="file_manager")
            return True
            
        except Exception as e:
            logger.error(f"Copy file error: {e}", module="file_manager")
            return False
    
    def move_file(self, source_path: str, destination_path: str, 
                 overwrite: bool = True) -> bool:
        """Move a file with advanced options"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}", module="file_manager")
                return False
            
            # Check if destination exists and overwrite is disabled
            if os.path.exists(destination_path) and not overwrite:
                logger.error(f"Destination exists and overwrite disabled: {destination_path}", module="file_manager")
                return False
            
            # Create backup if overwriting existing file
            if os.path.exists(destination_path) and self.config.get('backup_before_overwrite', True):
                backup_path = self._create_backup(destination_path)
                if backup_path:
                    logger.debug(f"Created backup: {backup_path}", module="file_manager")
            
            # Move the file
            shutil.move(source_path, destination_path)
            
            self.stats['files_moved'] += 1
            
            # Clear cache for moved file
            with self.cache_lock:
                cache_key = f"info_{source_path}"
                if cache_key in self.file_cache:
                    del self.file_cache[cache_key]
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.FILE_MOVE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"File moved: {source_path} -> {destination_path}",
                details={
                    'source_path': source_path,
                    'destination_path': destination_path,
                    'overwrite': overwrite,
                    'timestamp': datetime.now().isoformat()
                },
                resource='file_manager',
                action='move_file'
            )
            
            logger.info(f"File moved: {source_path} -> {destination_path}", module="file_manager")
            return True
            
        except Exception as e:
            logger.error(f"Move file error: {e}", module="file_manager")
            return False
    
    def delete_file(self, file_path: str, secure_delete: bool = False, 
                   shred_passes: int = 3) -> bool:
        """Delete a file with optional secure deletion"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}", module="file_manager")
                return False
            
            # Create backup before deletion if configured
            if self.config.get('backup_before_delete', False):
                backup_path = self._create_backup(file_path)
                if backup_path:
                    logger.debug(f"Created backup before deletion: {backup_path}", module="file_manager")
            
            if secure_delete:
                # Secure deletion with multiple overwrite passes
                success = self._secure_delete(file_path, shred_passes)
                if not success:
                    logger.error(f"Secure deletion failed for: {file_path}", module="file_manager")
                    return False
            else:
                # Normal deletion
                if os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
            
            self.stats['files_deleted'] += 1
            
            # Clear cache for deleted file
            with self.cache_lock:
                cache_key = f"info_{file_path}"
                if cache_key in self.file_cache:
                    del self.file_cache[cache_key]
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.FILE_DELETE.value,
                severity=AuditSeverity.WARNING.value,
                user='system',
                source_ip='localhost',
                description=f"File deleted: {file_path}",
                details={
                    'file_path': file_path,
                    'secure_delete': secure_delete,
                    'shred_passes': shred_passes,
                    'timestamp': datetime.now().isoformat()
                },
                resource='file_manager',
                action='delete_file'
            )
            
            logger.info(f"File deleted: {file_path}", module="file_manager")
            return True
            
        except Exception as e:
            logger.error(f"Delete file error: {e}", module="file_manager")
            return False
    
    def _secure_delete(self, file_path: str, passes: int = 3) -> bool:
        """Securely delete a file by overwriting with random data"""
        try:
            file_size = os.path.getsize(file_path)
            
            # Open file in read-write mode
            with open(file_path, 'rb+') as f:
                for pass_num in range(passes):
                    # Generate random data for this pass
                    import random
                    random.seed(os.urandom(16))
                    
                    # Overwrite entire file with random data
                    f.seek(0)
                    remaining = file_size
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        random_data = bytes(random.getrandbits(8) for _ in range(chunk_size))
                        f.write(random_data)
                        remaining -= chunk_size
                    
                    f.flush()
                    os.fsync(f.fileno())
            
            # Final deletion
            os.remove(file_path)
            
            # Optional: overwrite filename in directory entry (platform specific)
            if platform.system() != 'Windows':
                # On Unix-like systems, we can't easily overwrite directory entries
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Secure delete error for {file_path}: {e}", module="file_manager")
            return False
    
    def _create_backup(self, file_path: str) -> Optional[str]:
        """Create a backup of a file"""
        try:
            if not os.path.exists(file_path):
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            safe_filename = filename.replace(' ', '_').replace('\\', '_').replace('/', '_')
            backup_filename = f"{safe_filename}.backup_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Copy file to backup location
            shutil.copy2(file_path, backup_path)
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Create backup error for {file_path}: {e}", module="file_manager")
            return None
    
    def encrypt_file(self, source_path: str, destination_path: str = None,
                    algorithm: str = "AES256", key: bytes = None) -> bool:
        """Encrypt a file"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}", module="file_manager")
                return False
            
            if destination_path is None:
                destination_path = source_path + ".encrypted"
            
            # Check file size limit
            file_size = os.path.getsize(source_path)
            if file_size > self.max_file_size:
                logger.error(f"File too large for encryption: {file_size} bytes", module="file_manager")
                return False
            
            # Use encryption manager if available
            if self.encryption and algorithm.upper() == "AES256":
                success = self.encryption.encrypt_file(source_path, destination_path, key)
            else:
                # Fallback to simple XOR encryption (not secure, just for demonstration)
                success = self._simple_encrypt(source_path, destination_path, key)
            
            if success:
                self.stats['files_encrypted'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.FILE_ENCRYPT.value,
                    severity=AuditSeverity.HIGH.value,
                    user='system',
                    source_ip='localhost',
                    description=f"File encrypted: {source_path}",
                    details={
                        'source_path': source_path,
                        'destination_path': destination_path,
                        'algorithm': algorithm,
                        'file_size': file_size,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='file_manager',
                    action='encrypt_file'
                )
                
                logger.info(f"File encrypted: {source_path} -> {destination_path}", module="file_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Encrypt file error: {e}", module="file_manager")
            return False
    
    def decrypt_file(self, source_path: str, destination_path: str = None,
                    algorithm: str = "AES256", key: bytes = None) -> bool:
        """Decrypt a file"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}", module="file_manager")
                return False
            
            if destination_path is None:
                if source_path.endswith(".encrypted"):
                    destination_path = source_path[:-10]  # Remove .encrypted extension
                else:
                    destination_path = source_path + ".decrypted"
            
            # Use encryption manager if available
            if self.encryption and algorithm.upper() == "AES256":
                success = self.encryption.decrypt_file(source_path, destination_path, key)
            else:
                # Fallback to simple XOR decryption
                success = self._simple_decrypt(source_path, destination_path, key)
            
            if success:
                self.stats['files_decrypted'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.FILE_DECRYPT.value,
                    severity=AuditSeverity.HIGH.value,
                    user='system',
                    source_ip='localhost',
                    description=f"File decrypted: {source_path}",
                    details={
                        'source_path': source_path,
                        'destination_path': destination_path,
                        'algorithm': algorithm,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='file_manager',
                    action='decrypt_file'
                )
                
                logger.info(f"File decrypted: {source_path} -> {destination_path}", module="file_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Decrypt file error: {e}", module="file_manager")
            return False
    
    def _simple_encrypt(self, source_path: str, destination_path: str, key: bytes = None) -> bool:
        """Simple XOR encryption (for demonstration only)"""
        try:
            if key is None:
                key = b'simple_key_for_demo'
            
            with open(source_path, 'rb') as src, open(destination_path, 'wb') as dst:
                key_len = len(key)
                key_index = 0
                
                while chunk := src.read(8192):
                    encrypted_chunk = bytearray()
                    for byte in chunk:
                        encrypted_chunk.append(byte ^ key[key_index])
                        key_index = (key_index + 1) % key_len
                    
                    dst.write(encrypted_chunk)
            
            return True
            
        except Exception as e:
            logger.error(f"Simple encrypt error: {e}", module="file_manager")
            return False
    
    def _simple_decrypt(self, source_path: str, destination_path: str, key: bytes = None) -> bool:
        """Simple XOR decryption (for demonstration only)"""
        try:
            if key is None:
                key = b'simple_key_for_demo'
            
            with open(source_path, 'rb') as src, open(destination_path, 'wb') as dst:
                key_len = len(key)
                key_index = 0
                
                while chunk := src.read(8192):
                    decrypted_chunk = bytearray()
                    for byte in chunk:
                        decrypted_chunk.append(byte ^ key[key_index])
                        key_index = (key_index + 1) % key_len
                    
                    dst.write(decrypted_chunk)
            
            return True
            
        except Exception as e:
            logger.error(f"Simple decrypt error: {e}", module="file_manager")
            return False
    
    def compress_file(self, source_path: str, destination_path: str = None,
                     format: str = "zip", compression_level: int = 6) -> bool:
        """Compress a file"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}", module="file_manager")
                return False
            
            if destination_path is None:
                ext_map = {
                    "zip": ".zip",
                    "gzip": ".gz",
                    "bzip2": ".bz2",
                    "xz": ".xz",
                    "tar": ".tar"
                }
                ext = ext_map.get(format.lower(), ".zip")
                destination_path = source_path + ext
            
            success = False
            
            if format.lower() == "zip":
                with zipfile.ZipFile(destination_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    if os.path.isdir(source_path):
                        for root, dirs, files in os.walk(source_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(source_path))
                                zipf.write(file_path, arcname)
                    else:
                        zipf.write(source_path, os.path.basename(source_path))
                success = True
            
            elif format.lower() == "gzip":
                with open(source_path, 'rb') as src, gzip.open(destination_path, 'wb', compresslevel=compression_level) as dst:
                    shutil.copyfileobj(src, dst)
                success = True
            
            elif format.lower() == "bzip2":
                with open(source_path, 'rb') as src, bz2.open(destination_path, 'wb', compresslevel=compression_level) as dst:
                    shutil.copyfileobj(src, dst)
                success = True
            
            elif format.lower() == "xz":
                with open(source_path, 'rb') as src, lzma.open(destination_path, 'wb', preset=compression_level) as dst:
                    shutil.copyfileobj(src, dst)
                success = True
            
            elif format.lower() == "tar":
                with tarfile.open(destination_path, 'w') as tar:
                    if os.path.isdir(source_path):
                        tar.add(source_path, arcname=os.path.basename(source_path))
                    else:
                        tar.add(source_path, arcname=os.path.basename(source_path))
                success = True
            
            else:
                logger.error(f"Unsupported compression format: {format}", module="file_manager")
                return False
            
            if success:
                self.stats['files_compressed'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.FILE_COMPRESS.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip='localhost',
                    description=f"File compressed: {source_path}",
                    details={
                        'source_path': source_path,
                        'destination_path': destination_path,
                        'format': format,
                        'compression_level': compression_level,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='file_manager',
                    action='compress_file'
                )
                
                logger.info(f"File compressed: {source_path} -> {destination_path}", module="file_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Compress file error: {e}", module="file_manager")
            return False
    
    def decompress_file(self, source_path: str, destination_dir: str = None) -> bool:
        """Decompress a file"""
        try:
            if not os.path.exists(source_path):
                logger.error(f"Source file not found: {source_path}", module="file_manager")
                return False
            
            if destination_dir is None:
                destination_dir = os.path.dirname(source_path)
            
            success = False
            
            # Detect format by extension
            if source_path.endswith('.zip'):
                with zipfile.ZipFile(source_path, 'r') as zipf:
                    zipf.extractall(destination_dir)
                success = True
            
            elif source_path.endswith('.gz'):
                output_path = os.path.join(destination_dir, os.path.basename(source_path)[:-3])
                with gzip.open(source_path, 'rb') as src, open(output_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                success = True
            
            elif source_path.endswith('.bz2'):
                output_path = os.path.join(destination_dir, os.path.basename(source_path)[:-4])
                with bz2.open(source_path, 'rb') as src, open(output_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                success = True
            
            elif source_path.endswith('.xz'):
                output_path = os.path.join(destination_dir, os.path.basename(source_path)[:-3])
                with lzma.open(source_path, 'rb') as src, open(output_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                success = True
            
            elif source_path.endswith('.tar') or source_path.endswith('.tar.gz') or source_path.endswith('.tgz'):
                with tarfile.open(source_path, 'r') as tar:
                    tar.extractall(destination_dir)
                success = True
            
            else:
                logger.error(f"Unsupported compression format for: {source_path}", module="file_manager")
                return False
            
            if success:
                self.stats['files_decompressed'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.FILE_DECOMPRESS.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip='localhost',
                    description=f"File decompressed: {source_path}",
                    details={
                        'source_path': source_path,
                        'destination_dir': destination_dir,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='file_manager',
                    action='decompress_file'
                )
                
                logger.info(f"File decompressed: {source_path} -> {destination_dir}", module="file_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Decompress file error: {e}", module="file_manager")
            return False
    
    def search_files(self, search_directory: str, search_pattern: str,
                    search_type: str = "name", case_sensitive: bool = False,
                    recursive: bool = True, max_results: int = 100) -> List[SearchResult]:
        """Search for files with various criteria"""
        try:
            if not os.path.isdir(search_directory):
                logger.error(f"Search directory not found: {search_directory}", module="file_manager")
                return []
            
            results = []
            
            # Prepare search pattern
            if not case_sensitive:
                search_pattern_lower = search_pattern.lower()
            
            def process_file(file_path: str) -> Optional[SearchResult]:
                """Process a single file for search"""
                try:
                    file_info = self.get_file_info(file_path)
                    if not file_info:
                        return None
                    
                    match_type = None
                    match_score = 0.0
                    matched_text = None
                    
                    if search_type == "name":
                        # Search in filename
                        filename = file_info.name
                        search_text = filename if case_sensitive else filename.lower()
                        pattern = search_pattern if case_sensitive else search_pattern_lower
                        
                        if pattern in search_text:
                            match_type = "name"
                            match_score = len(pattern) / len(search_text) if search_text else 0.0
                            matched_text = filename
                    
                    elif search_type == "content":
                        # Search in file content (text files only)
                        if file_info.size < self.max_file_size and file_info.mime_type and 'text' in file_info.mime_type:
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read(1024 * 1024)  # Read up to 1MB
                                    
                                    search_text = content if case_sensitive else content.lower()
                                    pattern = search_pattern if case_sensitive else search_pattern_lower
                                    
                                    if pattern in search_text:
                                        match_type = "content"
                                        # Find the matching line
                                        lines = content.split('\n')
                                        for line in lines:
                                            if pattern in (line if case_sensitive else line.lower()):
                                                matched_text = line[:100] + "..." if len(line) > 100 else line
                                                break
                                        match_score = 0.5  # Default score for content matches
                            except:
                                pass
                    
                    elif search_type == "extension":
                        # Search by file extension
                        if file_info.extension:
                            extension = file_info.extension[1:]  # Remove dot
                            search_text = extension if case_sensitive else extension.lower()
                            pattern = search_pattern if case_sensitive else search_pattern_lower
                            
                            if pattern == search_text:
                                match_type = "extension"
                                match_score = 1.0
                                matched_text = file_info.extension
                    
                    elif search_type == "size":
                        # Search by size (e.g., ">1MB", "<500KB")
                        try:
                            pattern_lower = search_pattern.lower()
                            size_bytes = file_info.size
                            
                            if pattern_lower.startswith('>'):
                                threshold_str = pattern_lower[1:].strip()
                                threshold_bytes = self._parse_size_string(threshold_str)
                                if threshold_bytes is not None and size_bytes > threshold_bytes:
                                    match_type = "size"
                                    match_score = 0.7
                                    matched_text = f"{size_bytes} bytes"
                            
                            elif pattern_lower.startswith('<'):
                                threshold_str = pattern_lower[1:].strip()
                                threshold_bytes = self._parse_size_string(threshold_str)
                                if threshold_bytes is not None and size_bytes < threshold_bytes:
                                    match_type = "size"
                                    match_score = 0.7
                                    matched_text = f"{size_bytes} bytes"
                            
                            elif pattern_lower.startswith('='):
                                threshold_str = pattern_lower[1:].strip()
                                threshold_bytes = self._parse_size_string(threshold_str)
                                if threshold_bytes is not None and size_bytes == threshold_bytes:
                                    match_type = "size"
                                    match_score = 1.0
                                    matched_text = f"{size_bytes} bytes"
                        
                        except:
                            pass
                    
                    if match_type and match_score > 0:
                        return SearchResult(
                            file_info=file_info,
                            match_type=match_type,
                            match_score=match_score,
                            matched_text=matched_text
                        )
                    
                    return None
                    
                except Exception as e:
                    logger.debug(f"Search processing error for {file_path}: {e}", module="file_manager")
                    return None
            
            # Collect files to process
            files_to_process = []
            
            if recursive:
                for root, dirs, files in os.walk(search_directory):
                    for filename in files:
                        files_to_process.append(os.path.join(root, filename))
                        
                        if len(files_to_process) >= max_results * 10:  # Limit for performance
                            break
                    
                    if len(files_to_process) >= max_results * 10:
                        break
            else:
                for entry in os.listdir(search_directory):
                    file_path = os.path.join(search_directory, entry)
                    if os.path.isfile(file_path):
                        files_to_process.append(file_path)
                    
                    if len(files_to_process) >= max_results * 10:
                        break
            
            # Process files in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {executor.submit(process_file, f): f for f in files_to_process}
                
                for future in concurrent.futures.as_completed(future_to_file):
                    try:
                        result = future.result(timeout=5)
                        if result:
                            results.append(result)
                            
                            if len(results) >= max_results:
                                break
                    except concurrent.futures.TimeoutError:
                        continue
                    except Exception as e:
                        logger.debug(f"Search future error: {e}", module="file_manager")
                        continue
            
            # Sort by match score (descending)
            results.sort(key=lambda x: x.match_score, reverse=True)
            
            self.stats['searches_performed'] += 1
            
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Search files error: {e}", module="file_manager")
            return []
    
    def _parse_size_string(self, size_str: str) -> Optional[int]:
        """Parse size string like '1MB', '500KB', etc."""
        try:
            size_str = size_str.strip().upper()
            
            multipliers = {
                'KB': 1024,
                'MB': 1024 * 1024,
                'GB': 1024 * 1024 * 1024,
                'TB': 1024 * 1024 * 1024 * 1024,
                'K': 1024,
                'M': 1024 * 1024,
                'G': 1024 * 1024 * 1024,
                'T': 1024 * 1024 * 1024 * 1024
            }
            
            # Find multiplier
            multiplier = 1
            for unit, mult in multipliers.items():
                if size_str.endswith(unit):
                    size_str = size_str[:-len(unit)]
                    multiplier = mult
                    break
            
            # Parse number
            number = float(size_str)
            
            return int(number * multiplier)
            
        except:
            return None
    
    def change_permissions(self, file_path: str, permissions: Dict[str, bool]) -> bool:
        """Change file permissions"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}", module="file_manager")
                return False
            
            # Get current mode
            current_mode = os.stat(file_path).st_mode
            
            # Map permission names to stat constants
            perm_map = {
                'owner_read': stat.S_IRUSR,
                'owner_write': stat.S_IWUSR,
                'owner_execute': stat.S_IXUSR,
                'group_read': stat.S_IRGRP,
                'group_write': stat.S_IWGRP,
                'group_execute': stat.S_IXGRP,
                'others_read': stat.S_IROTH,
                'others_write': stat.S_IWOTH,
                'others_execute': stat.S_IXOTH
            }
            
            # Build new mode
            new_mode = current_mode
            
            for perm_name, enabled in permissions.items():
                if perm_name in perm_map:
                    if enabled:
                        new_mode |= perm_map[perm_name]  # Add permission
                    else:
                        new_mode &= ~perm_map[perm_name]  # Remove permission
            
            # Apply new mode
            os.chmod(file_path, new_mode)
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.FILE_PERMISSION_CHANGE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"File permissions changed: {file_path}",
                details={
                    'file_path': file_path,
                    'permissions': permissions,
                    'timestamp': datetime.now().isoformat()
                },
                resource='file_manager',
                action='change_permissions'
            )
            
            logger.info(f"Permissions changed for: {file_path}", module="file_manager")
            return True
            
        except Exception as e:
            logger.error(f"Change permissions error: {e}", module="file_manager")
            return False
    
    def change_ownership(self, file_path: str, owner: str = None, group: str = None) -> bool:
        """Change file ownership (Unix only)"""
        try:
            if platform.system() == 'Windows':
                logger.error("Ownership change not supported on Windows", module="file_manager")
                return False
            
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}", module="file_manager")
                return False
            
            import pwd
            import grp
            
            uid = None
            gid = None
            
            if owner:
                try:
                    uid = pwd.getpwnam(owner).pw_uid
                except KeyError:
                    logger.error(f"User not found: {owner}", module="file_manager")
                    return False
            
            if group:
                try:
                    gid = grp.getgrnam(group).gr_gid
                except KeyError:
                    logger.error(f"Group not found: {group}", module="file_manager")
                    return False
            
            os.chown(file_path, uid if uid is not None else -1, gid if gid is not None else -1)
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.FILE_OWNERSHIP_CHANGE.value,
                severity=AuditSeverity.INFO.value,
                user='system',
                source_ip='localhost',
                description=f"File ownership changed: {file_path}",
                details={
                    'file_path': file_path,
                    'owner': owner,
                    'group': group,
                    'timestamp': datetime.now().isoformat()
                },
                resource='file_manager',
                action='change_ownership'
            )
            
            logger.info(f"Ownership changed for: {file_path} (owner={owner}, group={group})", 
                       module="file_manager")
            return True
            
        except Exception as e:
            logger.error(f"Change ownership error: {e}", module="file_manager")
            return False
    
    def get_disk_usage(self, path: str = "/") -> Dict[str, Any]:
        """Get disk usage information"""
        try:
            total, used, free = shutil.disk_usage(path)
            
            return {
                'path': path,
                'total_bytes': total,
                'used_bytes': used,
                'free_bytes': free,
                'total_human': FileInfo._human_size(total),
                'used_human': FileInfo._human_size(used),
                'free_human': FileInfo._human_size(free),
                'used_percent': (used / total) * 100 if total > 0 else 0,
                'free_percent': (free / total) * 100 if total > 0 else 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Get disk usage error: {e}", module="file_manager")
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get file manager statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        with self.cache_lock:
            cache_size = len(self.file_cache)
        
        disk_usage = self.get_disk_usage()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
            'cache_size': cache_size,
            'hash_cache_size': len(self.hash_cache),
            'encryption_enabled': self.encryption_enabled,
            'compression_enabled': self.compression_enabled,
            'max_file_size': self.max_file_size,
            'temp_dir': self.temp_dir,
            'backup_dir': self.backup_dir,
            'max_workers': self.max_workers,
            'disk_usage': disk_usage,
            'platform': platform.system()
        }
    
    def export_file_list(self, directory: str, format: str = 'json', 
                        output_file: str = None) -> Optional[str]:
        """Export file list from directory"""
        try:
            files = self.list_directory(directory, recursive=True, include_hidden=True)
            
            data = {
                'directory': directory,
                'total_files': len(files),
                'total_size': sum(f.size for f in files),
                'timestamp': datetime.now().isoformat(),
                'files': [f.to_dict() for f in files]
            }
            
            if format.lower() == 'json':
                output = json.dumps(data, indent=2)
            
            elif format.lower() == 'csv':
                import csv
                import io
                
                output_io = io.StringIO()
                writer = csv.writer(output_io)
                
                # Write header
                writer.writerow(['Path', 'Name', 'Size', 'Type', 'Modified', 'Permissions', 
                               'Owner', 'Group', 'MIME Type', 'MD5', 'SHA256'])
                
                # Write data
                for file_info in files:
                    writer.writerow([
                        file_info.path,
                        file_info.name,
                        file_info.size,
                        file_info.file_type.value,
                        file_info.modified_time.isoformat() if file_info.modified_time else '',
                        str(file_info.permissions),
                        file_info.owner or '',
                        file_info.group or '',
                        file_info.mime_type or '',
                        file_info.hash_md5 or '',
                        file_info.hash_sha256 or ''
                    ])
                
                output = output_io.getvalue()
            
            elif format.lower() == 'text':
                output_lines = []
                output_lines.append(f"File List - {directory}")
                output_lines.append(f"Total files: {len(files)}")
                output_lines.append(f"Total size: {FileInfo._human_size(sum(f.size for f in files))}")
                output_lines.append("=" * 100)
                
                for file_info in sorted(files, key=lambda x: x.size, reverse=True)[:50]:
                    output_lines.append(
                        f"{file_info.name[:40]:40} "
                        f"{FileInfo._human_size(file_info.size):>10} "
                        f"{file_info.file_type.value[:10]:10} "
                        f"{file_info.modified_time.strftime('%Y-%m-%d %H:%M') if file_info.modified_time else 'N/A':16} "
                        f"{file_info.mime_type or 'N/A'[:20]:20}"
                    )
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported format: {format}", module="file_manager")
                return None
            
            # Write to file if specified
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                
                logger.info(f"File list exported to {output_file}", module="file_manager")
            
            return output
            
        except Exception as e:
            logger.error(f"Export file list error: {e}", module="file_manager")
            return None
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.executor.shutdown(wait=False)
        except:
            pass

# Global instance
_file_manager = None

def get_file_manager(config: Dict = None) -> FileManager:
    """Get or create file manager instance"""
    global _file_manager
    
    if _file_manager is None:
        _file_manager = FileManager(config)
    
    return _file_manager

if __name__ == "__main__":
    print("Testing File Manager...")
    
    # Test configuration
    config = {
        'max_file_size': 50 * 1024 * 1024,  # 50MB
        'encryption_enabled': False,
        'compression_enabled': True,
        'temp_dir': '/tmp/file_manager_test',
        'backup_dir': '/tmp/file_manager_backups',
        'max_workers': 4,
        'backup_before_overwrite': True,
        'backup_before_delete': False
    }
    
    fm = get_file_manager(config)
    
    print("\n1. Testing current directory listing...")
    current_dir = os.getcwd()
    files = fm.list_directory(current_dir, recursive=False)
    print(f"Found {len(files)} files/directories")
    
    if files:
        print("\n2. Sample file info:")
        for i, file_info in enumerate(files[:3]):
            print(f"  {i+1}. {file_info.name}: {FileInfo._human_size(file_info.size)}, {file_info.mime_type}")
    
    print("\n3. Testing file operations...")
    
    # Create a test file
    test_file = os.path.join(config['temp_dir'], 'test_file.txt')
    test_content = "This is a test file for File Manager testing.\n" * 100
    
    os.makedirs(config['temp_dir'], exist_ok=True)
    
    with open(test_file, 'w') as f:
        f.write(test_content)
    
    print(f"Created test file: {test_file}")
    
    # Get file info
    print("\n4. Getting file info...")
    file_info = fm.get_file_info(test_file, calculate_hash=True)
    if file_info:
        print(f"Name: {file_info.name}")
        print(f"Size: {FileInfo._human_size(file_info.size)}")
        print(f"Type: {file_info.file_type.value}")
        print(f"MIME Type: {file_info.mime_type}")
        print(f"MD5: {file_info.hash_md5}")
        print(f"SHA256: {file_info.hash_sha256}")
    
    # Test copy operation
    print("\n5. Testing copy operation...")
    copy_file = os.path.join(config['temp_dir'], 'test_file_copy.txt')
    if fm.copy_file(test_file, copy_file):
        print(f"✅ File copied to: {copy_file}")
    else:
        print("❌ File copy failed")
    
    # Test search operation
    print("\n6. Testing search operation...")
    search_results = fm.search_files(config['temp_dir'], "test", search_type="name", max_results=5)
    print(f"Found {len(search_results)} matching files")
    
    for i, result in enumerate(search_results[:3]):
        print(f"  {i+1}. {result.file_info.name} (score: {result.match_score:.2f})")
    
    # Test compression
    print("\n7. Testing compression...")
    zip_file = test_file + '.zip'
    if fm.compress_file(test_file, zip_file, format="zip"):
        print(f"✅ File compressed to: {zip_file}")
        
        # Test decompression
        decompress_dir = os.path.join(config['temp_dir'], 'decompressed')
        os.makedirs(decompress_dir, exist_ok=True)
        
        if fm.decompress_file(zip_file, decompress_dir):
            print(f"✅ File decompressed to: {decompress_dir}")
        else:
            print("❌ File decompression failed")
    else:
        print("❌ File compression failed")
    
    # Test disk usage
    print("\n8. Testing disk usage...")
    disk_usage = fm.get_disk_usage('/')
    if disk_usage:
        print(f"Total: {disk_usage['total_human']}")
        print(f"Used: {disk_usage['used_human']} ({disk_usage['used_percent']:.1f}%)")
        print(f"Free: {disk_usage['free_human']} ({disk_usage['free_percent']:.1f}%)")
    
    # Test statistics
    print("\n9. Getting statistics...")
    stats = fm.get_statistics()
    print(f"Files processed: {stats['files_processed']}")
    print(f"Files copied: {stats['files_copied']}")
    print(f"Searches performed: {stats['searches_performed']}")
    
    # Test export
    print("\n10. Testing export...")
    export_data = fm.export_file_list(config['temp_dir'], format='text')
    if export_data:
        print(export_data[:500] + "..." if len(export_data)500 else export_data)
    
    # Cleanup test files
    print("\n11. Cleaning up test files...")
    for test_file_to_delete in [test_file, copy_file, zip_file]:
        if os.path.exists(test_file_to_delete):
            os.remove(test_file_to_delete)
    
    if os.path.exists(decompress_dir):
        shutil.rmtree(decompress_dir)
    
    print("\n✅ File Manager tests completed!")
