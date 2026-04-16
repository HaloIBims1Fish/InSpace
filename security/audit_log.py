#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_log.py - Comprehensive Audit Logging System
"""

import os
import sys
import json
import sqlite3
import threading
import queue
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

# Import logger and encryption
from ..utils.logger import get_logger
from .encryption_manager import get_encryption_manager

logger = get_logger()

class AuditEventType(Enum):
    """Audit event types"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    COMMAND_EXECUTION = "command_execution"
    FILE_ACCESS = "file_access"
    NETWORK_ACCESS = "network_access"
    SYSTEM_CHANGE = "system_change"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"
    ERROR = "error"
    INFO = "info"

class AuditSeverity(Enum):
    """Audit severity levels"""
    DEBUG = 0
    INFO = 1
    NOTICE = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5
    ALERT = 6
    EMERGENCY = 7

class AuditLogEntry:
    """Audit log entry"""
    
    def __init__(self, 
                 event_type: str,
                 severity: int,
                 user: str,
                 source_ip: str,
                 description: str,
                 details: Dict[str, Any] = None,
                 resource: str = None,
                 action: str = None,
                 outcome: str = "unknown"):
        self.timestamp = datetime.now().isoformat()
        self.event_id = self._generate_event_id()
        self.event_type = event_type
        self.severity = severity
        self.user = user
        self.source_ip = source_ip
        self.description = description
        self.details = details or {}
        self.resource = resource
        self.action = action
        self.outcome = outcome
        self.hash = self._calculate_hash()
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        timestamp = int(datetime.now().timestamp() * 1000)
        random_part = os.urandom(4).hex()
        return f"EVT_{timestamp}_{random_part}"
    
    def _calculate_hash(self) -> str:
        """Calculate hash for integrity verification"""
        data = f"{self.timestamp}{self.event_type}{self.user}{self.description}{json.dumps(self.details, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'severity': self.severity,
            'user': self.user,
            'source_ip': self.source_ip,
            'description': self.description,
            'details': self.details,
            'resource': self.resource,
            'action': self.action,
            'outcome': self.outcome,
            'hash': self.hash
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)

class AuditLogManager:
    """Comprehensive audit logging system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Storage configuration
        self.log_dir = self.config.get('log_dir', 'logs/audit')
        self.database_file = os.path.join(self.log_dir, 'audit.db')
        self.archive_dir = os.path.join(self.log_dir, 'archive')
        self.max_log_size_mb = self.config.get('max_log_size_mb', 100)
        self.retention_days = self.config.get('retention_days', 365)
        
        # Create directories
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
        
        # Initialize database
        self.db_conn = self._init_database()
        
        # Queue for async logging
        self.log_queue = queue.Queue(maxsize=1000)
        self.worker_thread = None
        self.running = False
        
        # Encryption for sensitive logs
        self.encryption_manager = get_encryption_manager()
        self.encryption_key_id = None
        self._setup_encryption()
        
        # Start worker thread
        self.start_worker()
        
        logger.info("Audit log manager initialized", module="audit_log")
    
    def _init_database(self) -> sqlite3.Connection:
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.database_file, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            
            # Create tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    timestamp DATETIME NOT NULL,
                    event_type TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    user TEXT NOT NULL,
                    source_ip TEXT,
                    description TEXT NOT NULL,
                    details TEXT,
                    resource TEXT,
                    action TEXT,
                    outcome TEXT,
                    hash TEXT NOT NULL,
                    encrypted INTEGER DEFAULT 0,
                    archived INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON audit_events(user)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_severity ON audit_events(severity)")
            
            # Create statistics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_statistics (
                    date DATE PRIMARY KEY,
                    total_events INTEGER DEFAULT 0,
                    auth_events INTEGER DEFAULT 0,
                    security_events INTEGER DEFAULT 0,
                    error_events INTEGER DEFAULT 0,
                    unique_users INTEGER DEFAULT 0,
                    avg_severity REAL DEFAULT 0
                )
            """)
            
            conn.commit()
            return conn
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}", module="audit_log")
            raise
    
    def _setup_encryption(self):
        """Setup encryption for sensitive logs"""
        try:
            # Generate or get encryption key
            key_id = self.config.get('audit_encryption_key_id')
            
            if not key_id:
                # Generate new key
                key_id = self.encryption_manager.generate_symmetric_key(
                    key_type='audit_log',
                    key_size=32,
                    metadata={'purpose': 'audit_log_encryption'}
                )
            
            if key_id:
                self.encryption_key_id = key_id
                logger.info(f"Audit log encryption key: {key_id}", module="audit_log")
            else:
                logger.warning("No encryption key available for audit logs", module="audit_log")
                
        except Exception as e:
            logger.error(f"Encryption setup error: {e}", module="audit_log")
    
    def start_worker(self):
        """Start background worker thread"""
        if self.worker_thread and self.worker_thread.is_alive():
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        logger.debug("Audit log worker thread started", module="audit_log")
    
    def stop_worker(self):
        """Stop background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            logger.debug("Audit log worker thread stopped", module="audit_log")
    
    def _worker_loop(self):
        """Background worker loop"""
        while self.running:
            try:
                # Process queue with timeout
                try:
                    entry = self.log_queue.get(timeout=1)
                    self._process_entry(entry)
                    self.log_queue.task_done()
                except queue.Empty:
                    continue
                
                # Periodic maintenance
                if time.time() % 300 1:  # Every 5 minutes
                    self._perform_maintenance()
                    
            except Exception as e:
                logger.error(f"Audi log worker error: {e}", module="audit_log")
                time.sleep(1)
    
    def _process_entry(self, entry: AuditLogEntry):
        """Process audit log entry"""
        try:
            # Convert to dict
            entry_dict = entry.to_dict()
            
            # Encrypt sensitive details if needed
            encrypted = 0
            details_json = json.dumps(entry_dict['details'], default=str)
            
            if self.encryption_key_id and self._contains_sensitive_data(entry_dict):
                encrypted_details = self.encryption_manager.encrypt_data(
                    details_json.encode(),
                    self.encryption_key_id
                )
                
                if encrypted_details:
                    entry_dict['details'] = base64.b64encode(encrypted_details).decode()
                    encrypted = 1
            
            # Insert into database
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT INTO audit_events 
                (event_id, timestamp, event_type, severity, user, source_ip, 
                 description, details, resource, action, outcome, hash, encrypted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_dict['event_id'],
                entry_dict['timestamp'],
                entry_dict['event_type'],
                entry_dict['severity'],
                entry_dict['user'],
                entry_dict['source_ip'],
                entry_dict['description'],
                entry_dict['details'] if isinstance(entry_dict['details'], str) else json.dumps(entry_dict['details']),
                entry_dict['resource'],
                entry_dict['action'],
                entry_dict['outcome'],
                entry_dict['hash'],
                encrypted
            ))
            
            self.db_conn.commit()
            
            # Update statistics
            self._update_statistics(entry_dict)
            
            # Log to file for redundancy
            self._log_to_file(entry_dict)
            
            # Check for security alerts
            self._check_security_alerts(entry_dict)
            
            logger.debug(f"Audit event logged: {entry_dict['event_id']}", module="audit_log")
            
        except Exception as e:
            logger.error(f"Error processing audit entry: {e}", module="audit_log")
    
    def _contains_sensitive_data(self, entry_dict: Dict[str, Any]) -> bool:
        """Check if entry contains sensitive data"""
        sensitive_keywords = [
            'password', 'token', 'key', 'secret', 'credential',
            'private', 'ssh', 'pem', 'certificate', 'wallet'
        ]
        
        # Check description
        description = entry_dict['description'].lower()
        if any(keyword in description for keyword in sensitive_keywords):
            return True
        
        # Check details
        details_str = json.dumps(entry_dict['details']).lower()
        if any(keyword in details_str for keyword in sensitive_keywords):
            return True
        
        # Check resource
        resource = (entry_dict.get('resource') or '').lower()
        if any(keyword in resource for keyword in sensitive_keywords):
            return True
        
        return False
    
    def _update_statistics(self, entry_dict: Dict[str, Any]):
        """Update daily statistics"""
        try:
            date = datetime.fromisoformat(entry_dict['timestamp']).date().isoformat()
            
            cursor = self.db_conn.cursor()
            
            # Get current stats
            cursor.execute("""
                SELECT total_events, auth_events, security_events, error_events, unique_users, avg_severity
                FROM audit_statistics WHERE date = ?
            """, (date,))
            
            row = cursor.fetchone()
            
            if row:
                total, auth, security, errors, unique_users, avg_sev = row
                total += 1
                
                # Update counters
                if entry_dict['event_type'] == AuditEventType.AUTHENTICATION.value:
                    auth += 1
                elif entry_dict['event_type'] == AuditEventType.SECURITY_EVENT.value:
                    security += 1
                elif entry_dict['severity'] >= AuditSeverity.ERROR.value:
                    errors += 1
                
                # Update average severity
                avg_sev = ((avg_sev * (total - 1)) + entry_dict['severity']) / total
                
                cursor.execute("""
                    UPDATE audit_statistics 
                    SET total_events = ?, auth_events = ?, security_events = ?, 
                        error_events = ?, avg_severity = ?
                    WHERE date = ?
                """, (total, auth, security, errors, avg_sev, date))
            else:
                # Create new entry
                total = 1
                auth = 1 if entry_dict['event_type'] == AuditEventType.AUTHENTICATION.value else 0
                security = 1 if entry_dict['event_type'] == AuditEventType.SECURITY_EVENT.value else 0
                errors = 1 if entry_dict['severity'] >= AuditSeverity.ERROR.value else 0
                
                # Count unique users for today
                cursor.execute("""
                    SELECT COUNT(DISTINCT user) FROM audit_events 
                    WHERE DATE(timestamp) = DATE(?)
                """, (entry_dict['timestamp'],))
                unique_users = cursor.fetchone()[0] or 1
                
                cursor.execute("""
                    INSERT INTO audit_statistics 
                    (date, total_events, auth_events, security_events, error_events, unique_users, avg_severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (date, total, auth, security, errors, unique_users, entry_dict['severity']))
            
            self.db_conn.commit()
            
        except Exception as e:
            logger.error(f"Statistics update error: {e}", module="audit_log")
    
    def _log_to_file(self, entry_dict: Dict[str, Any]):
        """Log to JSON file for redundancy"""
        try:
            date = datetime.fromisoformat(entry_dict['timestamp']).strftime('%Y-%m-%d')
            log_file = os.path.join(self.log_dir, f"audit_{date}.json")
            
            # Read existing logs
            logs = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
            
            # Add new entry
            logs.append(entry_dict)
            
            # Write back
            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2, default=str)
            
        except Exception as e:
            logger.error(f"File logging error: {e}", module="audit_log")
    
    def _check_security_alerts(self, entry_dict: Dict[str, Any]):
        """Check for security alerts based on audit events"""
        try:
            # Check for failed authentication attempts
            if (entry_dict['event_type'] == AuditEventType.AUTHENTICATION.value and 
                entry_dict['outcome'] == 'failure'):
                
                # Count failures for this user in last 5 minutes
                cursor = self.db_conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM audit_events 
                    WHERE user = ? AND event_type = ? AND outcome = 'failure'
                    AND timestamp >= datetime('now', '-5 minutes')
                """, (entry_dict['user'], AuditEventType.AUTHENTICATION.value))
                
                failures = cursor.fetchone()[0]
                
                if failures >= 5:
                    # Create security alert
                    alert_entry = AuditLogEntry(
                        event_type=AuditEventType.SECURITY_EVENT.value,
                        severity=AuditSeverity.WARNING.value,
                        user='system',
                        source_ip=entry_dict['source_ip'],
                        description=f"Multiple failed authentication attempts for user {entry_dict['user']}",
                        details={
                            'user': entry_dict['user'],
                            'failures': failures,
                            'time_window': '5 minutes',
                            'recommendation': 'Consider locking account or increasing security'
                        },
                        resource='authentication_system',
                        action='failed_login_detection',
                        outcome='alert_generated'
                    )
                    
                    # Log alert
                    self.log_queue.put(alert_entry)
            
            # Check for privilege escalation attempts
            if (entry_dict['event_type'] == AuditEventType.AUTHORIZATION.value and 
                entry_dict['outcome'] == 'failure' and
                'admin' in (entry_dict.get('resource') or '').lower()):
                
                alert_entry = AuditLogEntry(
                    event_type=AuditEventType.SECURITY_EVENT.value,
                    severity=AuditSeverity.WARNING.value,
                    user=entry_dict['user'],
                    source_ip=entry_dict['source_ip'],
                    description=f"Privilege escalation attempt detected for user {entry_dict['user']}",
                    details={
                        'user': entry_dict['user'],
                        'resource': entry_dict.get('resource'),
                        'action': entry_dict.get('action'),
                        'recommendation': 'Review user permissions and monitor activity'
                    },
                    resource='authorization_system',
                    action='privilege_escalation_attempt',
                    outcome='alert_generated'
                )
                
                self.log_queue.put(alert_entry)
            
            # Check for critical system changes
            if (entry_dict['event_type'] == AuditEventType.SYSTEM_CHANGE.value and 
                entry_dict['severity'] >= AuditSeverity.CRITICAL.value):
                
                alert_entry = AuditLogEntry(
                    event_type=AuditEventType.SECURITY_EVENT.value,
                    severity=AuditSeverity.ALERT.value,
                    user=entry_dict['user'],
                    source_ip=entry_dict['source_ip'],
                    description=f"Critical system change performed by {entry_dict['user']}",
                    details=entry_dict['details'],
                    resource=entry_dict.get('resource'),
                    action=entry_dict.get('action'),
                    outcome='alert_generated'
                )
                
                self.log_queue.put(alert_entry)
                
        except Exception as e:
            logger.error(f"Security alert check error: {e}", module="audit_log")
    
    def log_event(self, 
                  event_type: str,
                  severity: int,
                  user: str,
                  source_ip: str,
                  description: str,
                  details: Dict[str, Any] = None,
                  resource: str = None,
                  action: str = None,
                  outcome: str = "success") -> str:
        """Log an audit event"""
        try:
            entry = AuditLogEntry(
                event_type=event_type,
                severity=severity,
                user=user,
                source_ip=source_ip,
                description=description,
                details=details,
                resource=resource,
                action=action,
                outcome=outcome
            )
            
            # Add to queue for async processing
            self.log_queue.put(entry)
            
            return entry.event_id
            
        except Exception as e:
            logger.error(f"Error creating audit entry: {e}", module="audit_log")
            return None
    
    def log_auth_event(self, 
                       user: str,
                       source_ip: str,
                       description: str,
                       success: bool,
                       details: Dict[str, Any] = None) -> str:
        """Log authentication event"""
        return self.log_event(
            event_type=AuditEventType.AUTHENTICATION.value,
            severity=AuditSeverity.INFO.value if success else AuditSeverity.WARNING.value,
            user=user,
            source_ip=source_ip,
            description=description,
            details=details,
            resource='authentication_system',
            action='authenticate',
            outcome='success' if success else 'failure'
        )
    
    def log_authz_event(self,
                        user: str,
                        source_ip: str,
                        description: str,
                        authorized: bool,
                        resource: str,
                        action: str,
                        details: Dict[str, Any] = None) -> str:
        """Log authorization event"""
        return self.log_event(
            event_type=AuditEventType.AUTHORIZATION.value,
            severity=AuditSeverity.INFO.value if authorized else AuditSeverity.WARNING.value,
            user=user,
            source_ip=source_ip,
            description=description,
            details=details,
            resource=resource,
            action=action,
            outcome='authorized' if authorized else 'denied'
        )
    
    def log_command_event(self,
                          user: str,
                          source_ip: str,
                          command: str,
                          success: bool,
                          output: str = None,
                          details: Dict[str, Any] = None) -> str:
        """Log command execution event"""
        return self.log_event(
            event_type=AuditEventType.COMMAND_EXECUTION.value,
            severity=AuditSeverity.INFO.value if success else AuditSeverity.ERROR.value,
            user=user,
            source_ip=source_ip,
            description=f"Command executed: {command}",
            details={
                'command': command,
                'output': output[:500] if output else None,  # Limit output size
                **(details or {})
            },
            resource='command_shell',
            action='execute',
            outcome='success' if success else 'failure'
        )
    
    def log_security_event(self,
                           user: str,
                           source_ip: str,
                           description: str,
                           severity: int,
                           details: Dict[str, Any] = None) -> str:
        """Log security event"""
        return self.log_event(
            event_type=AuditEventType.SECURITY_EVENT.value,
            severity=severity,
            user=user,
            source_ip=source_ip,
            description=description,
            details=details,
            resource='security_system',
            action='security_incident',
            outcome='detected'
        )
    
    def query_events(self,
                     start_time: str = None,
                     end_time: str = None,
                     event_type: str = None,
                     user: str = None,
                     severity_min: int = None,
                     severity_max: int = None,
                     limit: int = 100,
                     offset: int = 0) -> List[Dict[str, Any]]:
        """Query audit events"""
        try:
            cursor = self.db_conn.cursor()
            
            # Build query
            query = "SELECT * FROM audit_events WHERE 1=1"
            params = []
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)
            
            if user:
                query += " AND user = ?"
                params.append(user)
            
            if severity_min is not None:
                query += " AND severity >= ?"
                params.append(severity_min)
            
            if severity_max is not None:
                query += " AND severity <= ?"
                params.append(severity_max)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Get column names
            column_names = [description[0] for description in cursor.description]
            
            # Convert to dict
            events = []
            for row in rows:
                event_dict = dict(zip(column_names, row))
                
                # Parse details JSON
                if event_dict['details']:
                    try:
                        details = json.loads(event_dict['details'])
                        
                        # Decrypt if needed
                        if event_dict.get('encrypted') and self.encryption_key_id:
                            encrypted_data = base64.b64decode(details)
                            decrypted = self.encryption_manager.decrypt_data(
                                encrypted_data,
                                self.encryption_key_id
                            )
                            if decrypted:
                                details = json.loads(decrypted.decode())
                        
                        event_dict['details'] = details
                    except:
                        event_dict['details'] = {}
                
                events.append(event_dict)
            
            return events
            
        except Exception as e:
            logger.error(f"Query error: {e}", module="audit_log")
            return []
    
    def get_statistics(self, 
                       start_date: str = None,
                       end_date: str = None) -> Dict[str, Any]:
        """Get audit statistics"""
        try:
            cursor = self.db_conn.cursor()
            
            query = "SELECT * FROM audit_statistics WHERE 1=1"
            params = []
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            column_names = [description[0] for description in cursor.description]
            statistics = [dict(zip(column_names, row)) for row in rows]
            
            # Calculate totals
            totals = {
                'total_events': sum(s['total_events'] for s in statistics),
                'auth_events': sum(s['auth_events'] for s in statistics),
                'security_events': sum(s['security_events'] for s in statistics),
                'error_events': sum(s['error_events'] for s in statistics),
                'days': len(statistics)
            }
            
            if statistics:
                totals['avg_events_per_day'] = totals['total_events'] / len(statistics)
                totals['avg_severity'] = sum(s['avg_severity'] for s in statistics) / len(statistics)
            
            return {
                'statistics': statistics,
                'totals': totals
            }
            
        except Exception as e:
            logger.error(f"Statistics error: {e}", module="audit_log")
            return {'statistics': [], 'totals': {}}
    
    def export_events(self, 
                      format: str = 'json',
                      start_time: str = None,
                      end_time: str = None) -> Optional[str]:
        """Export audit events"""
        try:
            # Get events
            events = self.query_events(
                start_time=start_time,
                end_time=end_time,
                limit=10000  # Reasonable limit for export
            )
            
            if format == 'json':
                export_data = {
                    'export_timestamp': datetime.now().isoformat(),
                    'event_count': len(events),
                    'events': events
                }
                return json.dumps(export_data, indent=2, default=str)
            
            elif format == 'csv':
                import csv
                import io
                
                if not events:
                    return ""
                
                # Get all field names
                fieldnames = set()
                for event in events:
                    fieldnames.update(event.keys())
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=sorted(fieldnames))
                writer.writeheader()
                
                for event in events:
                    # Flatten details
                    if 'details' in event and isinstance(event['details'], dict):
                        event['details'] = json.dumps(event['details'])
                    
                    writer.writerow(event)
                
                return output.getvalue()
            
            else:
                logger.error(f"Unsupported export format: {format}", module="audit_log")
                return None
                
        except Exception as e:
            logger.error(f"Export error: {e}", module="audit_log")
            return None
    
    def _perform_maintenance(self):
        """Perform maintenance tasks"""
        try:
            # Archive old logs
            self._archive_old_logs()
            
            # Cleanup expired data
            self._cleanup_expired_data()
            
            # Check database size
            self._check_database_size()
            
            # Update encryption key if needed
            self._rotate_encryption_key()
            
        except Exception as e:
            logger.error(f"Maintenance error: {e}", module="audit_log")
    
    def _archive_old_logs(self):
        """Archive logs older than retention period"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=self.retention_days)).isoformat()
            
            cursor = self.db_conn.cursor()
            
            # Mark old events as archived
            cursor.execute("""
                UPDATE audit_events 
                SET archived = 1 
                WHERE timestamp < ? AND archived = 0
            """, (cutoff_date,))
            
            archived_count = cursor.rowcount
            self.db_conn.commit()
            
            if archived_count > 0:
                logger.info(f"Archived {archived_count} old audit events", module="audit_log")
                
        except Exception as e:
            logger.error(f"Archive error: {e}", module="audit_log")
    
    def _cleanup_expired_data(self):
        """Cleanup expired audit data"""
        try:
            # Delete events archived more than 30 days ago
            cleanup_date = (datetime.now() - timedelta(days=30)).isoformat()
            
            cursor = self.db_conn.cursor()
            cursor.execute("""
                DELETE FROM audit_events 
                WHERE archived = 1 AND ?
            """, (cleanup_date,))
            
            deleted_count = cursor.rowcount
            self.db_conn.commit()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired audit events", module="audit_log")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}", module="audit_log")
    
    def _check_database_size(self):
        """Check database size and rotate if needed"""
        try:
            db_size_mb = os.path.getsize(self.database_file) / (1024 * 1024)
            
            if db_size_mb > self.max_log_size_mb:
                logger.warning(f"Database size ({db_size_mb:.2f} MB) exceeds limit, rotating...", 
                             module="audit_log")
                self._rotate_database()
                
        except Exception as e:
            logger.error(f"Database size check error: {e}", module="audit_log")
    
    def _rotate_database(self):
        """Rotate database file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(self.archive_dir, f"audit_backup_{timestamp}.db")
            
            # Close current connection
            self.db_conn.close()
            
            # Copy database to backup
            import shutil
            shutil.copy2(self.database_file, backup_file)
            
            # Remove old database
            os.remove(self.database_file)
            
            # Reinitialize
            self.db_conn = self._init_database()
            
            logger.info(f"Database rotated: {backup_file}", module="audit_log")
            
        except Exception as e:
            logger.error(f"Database rotation error: {e}", module="audit_log")
            # Try to reconnect
            try:
                self.db_conn = sqlite3.connect(self.database_file, check_same_thread=False)
            except:
                logger.critical("Failed to reconnect to audit database", module="audit_log")
    
    def _rotate_encryption_key(self):
        """Rotate encryption key if needed"""
        try:
            if not self.encryption_key_id:
                return
            
            # Get key status
            key_status = self.encryption_manager.get_key_status(self.encryption_key_id)
            
            if key_status and key_status.get('rotation_needed'):
                # Generate new key
                new_key_id = self.encryption_manager.generate_symmetric_key(
                    key_type='audit_log',
                    key_size=32,
                    metadata={'purpose': 'audit_log_encryption'}
                )
                
                if new_key_id:
                    # Re-encrypt existing encrypted logs (in production)
                    logger.info(f"Audit encryption key rotated: {new_key_id}", module="audit_log")
                    self.encryption_key_id = new_key_id
                    
        except Exception as e:
            logger.error(f"Encryption key rotation error: {e}", module="audit_log")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get audit system status"""
        try:
            cursor = self.db_conn.cursor()
            
            # Get event counts
            cursor.execute("SELECT COUNT(*) FROM audit_events")
            total_events = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE archived = 1")
            archived_events = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT user) FROM audit_events")
            unique_users = cursor.fetchone()[0]
            
            # Get database size
            db_size_mb = os.path.getsize(self.database_file) / (1024 * 1024) if os.path.exists(self.database_file) else 0
            
            # Get queue status
            queue_size = self.log_queue.qsize()
            
            return {
                'total_events': total_events,
                'archived_events': archived_events,
                'unique_users': unique_users,
                'database_size_mb': round(db_size_mb, 2),
                'queue_size': queue_size,
                'worker_running': self.worker_thread.is_alive() if self.worker_thread else False,
                'encryption_enabled': self.encryption_key_id is not None,
                'retention_days': self.retention_days,
                'max_log_size_mb': self.max_log_size_mb
            }
            
        except Exception as e:
            logger.error(f"Status error: {e}", module="audit_log")
            return {}

# Global instance
_audit_log_manager = None

def get_audit_log_manager(config: Dict = None) -> AuditLogManager:
    """Get or create audit log manager instance"""
    global _audit_log_manager
    
    if _audit_log_manager is None:
        _audit_log_manager = AuditLogManager(config)
    
    return _audit_log_manager

if __name__ == "__main__":
    # Test audit log manager
    audit = get_audit_log_manager()
    
    print("Testing audit log manager...")
    
    # Log various events
    auth_event_id = audit.log_auth_event(
        user="testuser",
        source_ip="192.168.1.100",
        description="User login attempt",
        success=True,
        details={'method': 'password', 'mfa': False}
    )
    print(f"Auth event logged: {auth_event_id}")
    
    authz_event_id = audit.log_authz_event(
        user="testuser",
        source_ip="192.168.1.100",
        description="Access to admin panel",
        authorized=True,
        resource="/admin",
        action="access"
    )
    print(f"Authz event logged: {authz_event_id}")
    
    cmd_event_id = audit.log_command_event(
        user="testuser",
        source_ip="192.168.1.100",
        command="rm -rf /tmp/*",
        success=True,
        output="Files deleted successfully"
    )
    print(f"Command event logged: {cmd_event_id}")
    
    security_event_id = audit.log_security_event(
        user="intruder",
        source_ip="10.0.0.1",
        description="Multiple failed login attempts",
        severity=AuditSeverity.WARNING.value,
        details={'attempts': 15, 'timeframe': '2 minutes'}
    )
    print(f"Security event logged: {security_event_id}")
    
    # Wait for processing
    time.sleep(2)
    
    # Query events
    events = audit.query_events(limit=5)
    print(f"\nRecent events ({len(events)}):")
    for event in events:
        print(f"  [{event['timestamp']}] {event['event_type']}: {event['description']}")
    
    # Get statistics
    stats = audit.get_statistics()
    print(f"\nStatistics:")
    print(f"  Total events: {stats['totals'].get('total_events', 0)}")
    print(f"  Auth events: {stats['totals'].get('auth_events', 0)}")
    print(f"  Security events: {stats['totals'].get('security_events', 0)}")
    
    # Export events
    export_json = audit.export_events(format='json', limit=3)
    print(f"\nExport (JSON, first 3 events):")
    print(export_json[:500] + "..." if len(export_json) > 500 else export_json)
    
    # Get system status
    status = audit.get_system_status()
    print(f"\n📜 Audit System Status:")
    print(f"  Total events: {status['total_events']}")
    print(f"  Database size: {status['database_size_mb']} MB")
    print(f"  Queue size: {status['queue_size']}")
    print(f"  Encryption: {'Enabled' if status['encryption_enabled'] else 'Disabled'}")
    
    # Stop worker
    audit.stop_worker()
    
    print("\n✅ Audit log tests completed!")
