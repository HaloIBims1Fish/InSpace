#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
processor.py - Data processing and analysis module
"""

import json
import csv
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
import hashlib
import re
import statistics
from collections import Counter, defaultdict
import threading
import queue

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class DataProcessor:
    """Processes and analyzes data from various sources"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Processing queues
        self.processing_queue = queue.Queue()
        self.results_queue = queue.Queue()
        
        # Worker threads
        self.workers = []
        self.running = False
        
        # Initialize workers
        self._start_workers()
        
        logger.info("Data processor initialized", module="processor")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('processor_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.processor_chat_id = chat_id
                logger.info("Telegram processor bot initialized", module="processor")
            except ImportError:
                logger.warning("Telegram module not available", module="processor")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="processor")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send processor notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'processor_chat_id'):
            return
        
        try:
            full_message = fb>🔧 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.processor_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram processor notification sent: {title}", module="processor")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="processor")
    
    def _start_workers(self):
        """Start worker threads for processing"""
        worker_count = self.config.get('worker_count', 4)
        
        self.running = True
        for i in range(worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                daemon=True,
                name=f"DataWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)
        
        logger.info(f"Started {worker_count} data processing workers", module="processor")
    
    def _worker_loop(self, worker_id: int):
        """Worker thread processing loop"""
        logger.debug(f"Data worker {worker_id} started", module="processor")
        
        while self.running:
            try:
                # Get task from queue with timeout
                task = self.processing_queue.get(timeout=1)
                
                if task is None:  # Poison pill
                    break
                
                # Process task
                task_type = task.get('type')
                data = task.get('data')
                task_id = task.get('id')
                
                logger.debug(f"Worker {worker_id} processing task {task_id}: {task_type}", module="processor")
                
                # Process based on type
                result = self._process_task(task_type, data)
                
                # Put result in results queue
                self.results_queue.put({
                    'task_id': task_id,
                    'worker_id': worker_id,
                    'type': task_type,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
                
                self.processing_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}", module="processor")
                self.results_queue.put({
                    'task_id': task.get('id') if task else 'unknown',
                    'worker_id': worker_id,
                    'type': task.get('type') if task else 'unknown',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
        
        logger.debug(f"Data worker {worker_id} stopped", module="processor")
    
    def _process_task(self, task_type: str, data: Any) -> Any:
        """Process individual task"""
        try:
            if task_type == 'analyze_system_info':
                return self._analyze_system_info(data)
            elif task_type == 'process_network_scan':
                return self._process_network_scan(data)
            elif task_type == 'analyze_processes':
                return self._analyze_processes(data)
            elif task_type == 'extract_credentials':
                return self._extract_credentials(data)
            elif task_type == 'analyze_logs':
                return self._analyze_logs(data)
            elif task_type == 'process_screenshots':
                return self._process_screenshots(data)
            elif task_type == 'aggregate_metrics':
                return self._aggregate_metrics(data)
            elif task_type == 'detect_anomalies':
                return self._detect_anomalies(data)
            elif task_type == 'extract_iocs':
                return self._extract_iocs(data)
            elif task_type == 'enrich_data':
                return self._enrich_data(data)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Task processing error for {task_type}: {e}", module="processor")
            return {'error': str(e)}
    
    def submit_task(self, task_type: str, data: Any, 
                   priority: int = 0) -> str:
        """Submit task for processing"""
        task_id = hashlib.md5(f"{task_type}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        task = {
            'id': task_id,
            'type': task_type,
            'data': data,
            'priority': priority,
            'submitted': datetime.now().isoformat()
        }
        
        self.processing_queue.put(task)
        
        logger.debug(f"Task submitted: {task_id} ({task_type})", module="processor")
        return task_id
    
    def get_result(self, task_id: str, timeout: float = None) -> Optional[Dict]:
        """Get result for task"""
        try:
            # Check if result is already available
            while True:
                try:
                    result = self.results_queue.get_nowait()
                    if result['task_id'] == task_id:
                        return result
                    else:
                        # Put back and continue
                        self.results_queue.put(result)
                        break
                except queue.Empty:
                    break
            
            # Wait for result with timeout
            if timeout is not None:
                start_time = time.time()
                while time.time() - start timeout:
                    try:
                        result = self.results_queue.get(timeout=0.1)
                        if result['task_id'] == task_id:
                            return result
                        else:
                            self.results_queue.put(result)
                    except queue.Empty:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting result for task {task_id}: {e}", module="processor")
            return None
    
    def _analyze_system_info(self, data: List[Dict]) -> Dict:
        """Analyze system information data"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_systems': len(data),
                'platforms': Counter(),
                'cpu_stats': [],
                'memory_stats': [],
                'disk_stats': [],
                'network_interfaces': Counter(),
                'timeline': []
            }
            
            for system in data:
                # Platform distribution
                platform = system.get('platform', 'Unknown')
                analysis['platforms'][platform] += 1
                
                # CPU stats
                cpu_cores = system.get('cpu_cores')
                if cpu_cores:
                    analysis['cpu_stats'].append(cpu_cores)
                
                # Memory stats
                memory_total = system.get('memory_total')
                if memory_total:
                    analysis['memory_stats'].append(memory_total)
                
                # Disk stats
                disk_total = system.get('disk_total')
                if disk_total:
                    analysis['disk_stats'].append(disk_total)
                
                # Network interfaces
                ip = system.get('ip_address')
                if ip:
                    # Extract network class
                    if ip.startswith('192.168.'):
                        analysis['network_interfaces']['192.168.x.x'] += 1
                    elif ip.startswith('10.'):
                        analysis['network_interfaces']['10.x.x.x'] += 1
                    elif ip.startswith('172.'):
                        analysis['network_interfaces']['172.x.x.x'] += 1
                    else:
                        analysis['network_interfaces']['other'] += 1
                
                # Timeline
                timestamp = system.get('timestamp')
                if timestamp:
                    analysis['timeline'].append(timestamp)
            
            # Calculate statistics
            if analysis['cpu_stats']:
                analysis['cpu_avg'] = statistics.mean(analysis['cpu_stats'])
                analysis['cpu_min'] = min(analysis['cpu_stats'])
                analysis['cpu_max'] = max(analysis['cpu_stats'])
            
            if analysis['memory_stats']:
                analysis['memory_avg_gb'] = statistics.mean(analysis['memory_stats']) / (1024**3)
                analysis['memory_total_gb'] = sum(analysis['memory_stats']) / (1024**3)
            
            if analysis['disk_stats']:
                analysis['disk_avg_gb'] = statistics.mean(analysis['disk_stats']) / (1024**3)
                analysis['disk_total_gb'] = sum(analysis['disk_stats']) / (1024**3)
            
            # Sort platforms by count
            analysis['platforms'] = dict(sorted(
                analysis['platforms'].items(),
                key=lambda x: x[1],
                reverse=True
            ))
            
            logger.debug(f"Analyzed {len(data)} system records", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"System info analysis error: {e}", module="processor")
            return {'error': str(e)}
    
    def _process_network_scan(self, data: List[Dict]) -> Dict:
        """Process network scan results"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_hosts': len(data),
                'open_ports': Counter(),
                'services': Counter(),
                'operating_systems': Counter(),
                'vulnerabilities': [],
                'hosts_by_network': defaultdict(int)
            }
            
            for host in data:
                ip = host.get('ip')
                if not ip:
                    continue
                
                # Network classification
                network_part = '.'.join(ip.split('.')[:3]) + '.x'
                analysis['hosts_by_network'][network_part] += 1
                
                # Ports and services
                ports = host.get('ports', [])
                for port_info in ports:
                    port = port_info.get('port')
                    service = port_info.get('service', 'unknown')
                    
                    if port:
                        analysis['open_ports'][port] += 1
                    
                    if service and service != 'unknown':
                        analysis['services'][service] += 1
                
                # OS detection
                os_info = host.get('os', '')
                if os_info:
                    analysis['operating_systems'][os_info] += 1
                
                # Vulnerabilities
                vulns = host.get('vulnerabilities', [])
                analysis['vulnerabilities'].extend(vulns)
            
            # Calculate statistics
            analysis['unique_ports'] = len(analysis['open_ports'])
            analysis['unique_services'] = len(analysis['services'])
            analysis['total_vulnerabilities'] = len(analysis['vulnerabilities'])
            
            # Most common ports and services
            analysis['top_ports'] = dict(sorted(
                analysis['open_ports'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            analysis['top_services'] = dict(sorted(
                analysis['services'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            # Most common OS
            analysis['top_os'] = dict(sorted(
                analysis['operating_systems'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5])
            
            logger.debug(f"Processed {len(data)} network hosts", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"Network scan processing error: {e}", module="processor")
            return {'error': str(e)}
    
    def _analyze_processes(self, data: List[Dict]) -> Dict:
        """Analyze process information"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_processes': len(data),
                'processes_by_user': Counter(),
                'processes_by_name': Counter(),
                'cpu_usage': [],
                'memory_usage': [],
                'suspicious_processes': [],
                'timeline': []
            }
            
            suspicious_keywords = [
                'mimikatz', 'powersploit', 'empire', 'cobalt', 'metasploit',
                'bloodhound', 'responder', 'impacket', 'psexec', 'wmiexec',
                'nc.exe', 'netcat', 'ncat', 'socat', 'plink', 'putty',
                'keylogger', 'rat', 'backdoor', 'rootkit', 'trojan'
            ]
            
            for process in data:
                # User distribution
                user = process.get('username', 'unknown')
                analysis['processes_by_user'][user] += 1
                
                # Process name distribution
                name = process.get('name', 'unknown')
                analysis['processes_by_name'][name] += 1
                
                # CPU and memory usage
                cpu = process.get('cpu_percent', 0)
                memory = process.get('memory_percent', 0)
                
                if cpu > 0:
                    analysis['cpu_usage'].append(cpu)
                if memory > 0:
                    analysis['memory_usage'].append(memory)
                
                # Check for suspicious processes
                name_lower = name.lower()
                exe_path = process.get('exe_path', '').lower()
                cmdline = ' '.join(process.get('cmdline', [])).lower()
                
                for keyword in suspicious_keywords:
                    if (keyword in name_lower or 
                        keyword in exe_path or 
                        keyword in cmdline):
                        
                        analysis['suspicious_processes'].append({
                            'pid': process.get('pid'),
                            'name': name,
                            'user': user,
                            'exe_path': process.get('exe_path'),
                            'cmdline': process.get('cmdline'),
                            'keyword': keyword,
                            'timestamp': process.get('timestamp')
                        })
                        break
                
                # Timeline
                timestamp = process.get('timestamp')
                if timestamp:
                    analysis['timeline'].append(timestamp)
            
            # Calculate statistics
            if analysis['cpu_usage']:
                analysis['cpu_avg'] = statistics.mean(analysis['cpu_usage'])
                analysis['cpu_max'] = max(analysis['cpu_usage'])
            
            if analysis['memory_usage']:
                analysis['memory_avg'] = statistics.mean(analysis['memory_usage'])
                analysis['memory_max'] = max(analysis['memory_usage'])
            
            # Most active users and processes
            analysis['top_users'] = dict(sorted(
                analysis['processes_by_user'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            analysis['top_processes'] = dict(sorted(
                analysis['processes_by_name'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            # Send Telegram notification for suspicious processes
            if analysis['suspicious_processes']:
                self.send_telegram_notification(
                    "⚠️ Suspicious Processes Detected",
                    f"Count: {len(analysis['suspicious_processes'])}\n"
                    f"Processes: {', '.join(set(p['name'] for p in analysis['suspicious_processes'][:5]))}"
                )
            
            logger.debug(f"Analyzed {len(data)} processes, found {len(analysis['suspicious_processes'])} suspicious", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"Process analysis error: {e}", module="processor")
            return {'error': str(e)}
    
    def _extract_credentials(self, data: List[Dict]) -> Dict:
        """Extract and analyze credentials"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_credentials': len(data),
                'credentials_by_source': Counter(),
                'credentials_by_application': Counter(),
                'unique_users': set(),
                'password_stats': {
                    'lengths': [],
                    'strength': {'weak': 0, 'medium': 0, 'strong': 0}
                },
                'common_passwords': Counter(),
                'compromised_credentials': []
            }
            
            for cred in data:
                # Source distribution
                source = cred.get('source', 'unknown')
                analysis['credentials_by_source'][source] += 1
                
                # Application distribution
                application = cred.get('application', 'unknown')
                analysis['credentials_by_application'][application] += 1
                
                # Unique users
                username = cred.get('username')
                if username:
                    analysis['unique_users'].add(username)
                
                # Password analysis
                password = cred.get('password', '')
                if password:
                    # Password length
                    analysis['password_stats']['lengths'].append(len(password))
                    
                    # Password strength
                    if len(password 6:
                        analysis['password_stats']['strength']['weak'] += 1
                    elif len(password 10:
                        analysis['password_stats']['strength']['medium'] += 1
                    else:
                        analysis['password_stats']['strength']['strong'] += 1
                    
                    # Common passwords
                    if password in ['password', '123456', 'admin', 'qwerty', 'letmein']:
                        analysis['common_passwords'][password] += 1
                
                # Compromised credentials
                compromised = cred.get('compromised', False)
                if compromised:
                    analysis['compromised_credentials'].append({
                        'username': username,
                        'application': application,
                        'source': source,
                        'url': cred.get('url')
                    })
            
            # Calculate statistics
            analysis['unique_user_count'] = len(analysis['unique_users'])
            
            if analysis['password_stats']['lengths']:
                analysis['password_stats']['avg_length'] = statistics.mean(analysis['password_stats']['lengths'])
                analysis['password_stats']['min_length'] = min(analysis['password_stats']['lengths'])
                analysis['password_stats']['max_length'] = max(analysis['password_stats']['lengths'])
            
            # Most common sources and applications
            analysis['top_sources'] = dict(sorted(
                analysis['credentials_by_source'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            analysis['top_applications'] = dict(sorted(
                analysis['credentials_by_application'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            # Send Telegram notification for credentials
            self.send_telegram_notification(
                "🔑 Credentials Analysis",
                f"Total: {analysis['total_credentials']}\n"
                f"Unique users: {analysis['unique_user_count']}\n"
                f"Compromised: {len(analysis['compromised_credentials'])}\n"
                f"Top source: {list(analysis['top_sources'].keys())[0] if analysis['top_sources'] else 'N/A'}"
            )
            
            logger.debug(f"Extracted {len(data)} credentials", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"Credentials extraction error: {e}", module="processor")
            return {'error': str(e)}
    
    def _analyze_logs(self, data: List[Dict]) -> Dict:
        """Analyze log data"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_logs': len(data),
                'logs_by_level': Counter(),
                'logs_by_source': Counter(),
                'error_patterns': Counter(),
                'timeline': defaultdict(int),
                'anomalies': []
            }
            
            error_patterns = [
                (r'error|exception|failed|failure', 'ERROR'),
                (r'warning|warn', 'WARNING'),
                (r'critical|fatal|panic', 'CRITICAL'),
                (r'authentication failed|login failed', 'AUTH_FAILURE'),
                (r'access denied|permission denied', 'ACCESS_DENIED'),
                (r'timeout|timed out', 'TIMEOUT'),
                (r'connection refused|cannot connect', 'CONNECTION_ISSUE')
            ]
            
            for log_entry in data:
                # Log level distribution
                level = log_entry.get('level', 'INFO').upper()
                analysis['logs_by_level'][level] += 1
                
                # Source distribution
                source = log_entry.get('source', 'unknown')
                analysis['logs_by_source'][source] += 1
                
                # Message analysis
                message = log_entry.get('message', '').lower()
                
                # Check for error patterns
                for pattern, pattern_name in error_patterns:
                    if re.search(pattern, message, re.IGNORECASE):
                        analysis['error_patterns'][pattern_name] += 1
                
                # Timeline analysis
                timestamp = log_entry.get('timestamp')
                if timestamp:
                    try:
                        # Group by hour
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        hour_key = dt.strftime('%Y-%m-%d %H:00')
                        analysis['timeline'][hour_key] += 1
                    except:
                        pass
            
            # Calculate statistics
            analysis['error_rate'] = (
                analysis['logs_by_level'].get('ERROR', 0) / 
                analysis['total_logs'] * 100 
                if analysis['total_logs'] > 0 else 0
            )
            
            analysis['warning_rate'] = (
                analysis['logs_by_level'].get('WARNING', 0) / 
                analysis['total_logs'] * 100 
                if analysis['total_logs'] > 0 else 0
            )
            
            # Most common error patterns
            analysis['top_error_patterns'] = dict(sorted(
                analysis['error_patterns'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            # Detect anomalies (spikes in error rate)
            timeline_items = sorted(analysis['timeline'].items())
            if len(timeline_items) > 1:
                values = [count for _, count in timeline_items]
                mean = statistics.mean(values)
                std = statistics.stdev(values) if len(values) > 1 else 0
                
                for hour, count in timeline_items:
                    if std > 0 and count > mean + (2 * std):  # 2 sigma threshold
                        analysis['anomalies'].append({
                            'hour': hour,
                            'count': count,
                            'mean': mean,
                            'deviation': (count - mean) / std if std > 0 else 0
                        })
            
            # Send Telegram notification for high error rates
            if analysis['error_rate'] > 10:  # More than 10% errors
                self.send_telegram_notification(
                    "⚠️ High Error Rate in Logs",
                    f"Error rate: {analysis['error_rate']:.1f}%\n"
                    f"Total logs: {analysis['total_logs']}\n"
                    f"Errors: {analysis['logs_by_level'].get('ERROR', 0)}"
                )
            
            logger.debug(f"Analyzed {len(data)} log entries", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"Log analysis error: {e}", module="processor")
            return {'error': str(e)}
    
    def _process_screenshots(self, data: List[Dict]) -> Dict:
        """Process screenshot metadata"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            analysis = {
                'total_screenshots': len(data),
                'resolutions': Counter(),
                'sizes': [],
                'timeline': defaultdict(int),
                'tags': Counter()
            }
            
            for screenshot in data:
                # Resolution distribution
                width = screenshot.get('width', 0)
                height = screenshot.get('height', 0)
                if width and height:
                    resolution = f"{width}x{height}"
                    analysis['resolutions'][resolution] += 1
                
                # Size analysis
                size = screenshot.get('size', 0)
                if size:
                    analysis['sizes'].append(size)
                
                # Timeline
                timestamp = screenshot.get('timestamp')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_key = dt.strftime('%Y-%m-%d')
                        analysis['timeline'][date_key] += 1
                    except:
                        pass
                
                # Tags
                tags_str = screenshot.get('tags', '')
                if tags_str:
                    tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
                    for tag in tags:
                        analysis['tags'][tag] += 1
            
            # Calculate statistics
            if analysis['sizes']:
                analysis['avg_size_kb'] = statistics.mean(analysis['sizes']) / 1024
                analysis['total_size_mb'] = sum(analysis['sizes']) / (1024 * 1024)
            
            # Most common resolutions
            analysis['top_resolutions'] = dict(sorted(
                analysis['resolutions'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5])
            
            # Most common tags
            analysis['top_tags'] = dict(sorted(
                analysis['tags'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:10])
            
            logger.debug(f"Processed {len(data)} screenshots", module="processor")
            return analysis
            
        except Exception as e:
            logger.error(f"Screenshot processing error: {e}", module="processor")
            return {'error': str(e)}
    
    def _aggregate_metrics(self, data: Dict[str, List]) -> Dict:
        """Aggregate metrics from multiple sources"""
        try:
            aggregated = {
                'timestamp': datetime.now().isoformat(),
                'metrics': {},
                'summary': {}
            }
            
            for metric_name, values in data.items():
                if not values:
                    continue
                
                # Convert to numeric if possible
                numeric_values = []
                for value in values:
                    try:
                        numeric_values.append(float(value))
                    except (ValueError, TypeError):
                        pass
                
                if numeric_values:
                    aggregated['metrics'][metric_name] = {
                        'count': len(numeric_values),
                        'sum': sum(numeric_values),
                        'mean': statistics.mean(numeric_values),
                        'median': statistics.median(numeric_values),
                        'min': min(numeric_values),
                        'max': max(numeric_values),
                        'std': statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0
                    }
            
            # Create summary
            total_metrics = len(aggregated['metrics'])
            if total_metrics > 0:
                aggregated['summary'] = {
                    'total_metrics': total_metrics,
                    'total_values': sum(m['count'] for m in aggregated['metrics'].values()),
                    'timestamp': datetime.now().isoformat()
                }
            
            logger.debug(f"Aggregated {total_metrics} metrics", module="processor")
            return aggregated
            
        except Exception as e:
            logger.error(f"Metrics aggregation error: {e}", module="processor")
            return {'error': str(e)}
    
    def _detect_anomalies(self, data: List[Dict]) -> Dict:
        """Detect anomalies in data"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            anomalies = {
                'total_checked': len(data),
                'anomalies_found': 0,
                'anomalies_by_type': Counter(),
                'details': []
            }
            
            # Define anomaly detection rules
            anomaly_rules = [
                {
                    'name': 'HIGH_CPU_USAGE',
                    'check': lambda x: x.get('cpu_percent', 0) > 90,
                    'message': 'CPU usage above 90%'
                },
                {
                    'name': 'HIGH_MEMORY_USAGE',
                    'check': lambda x: x.get('memory_percent', 0) > 90,
                    'message': 'Memory usage above 90%'
                },
                {
                    'name': 'UNUSUAL_PROCESS',
                    'check': lambda x: any(keyword in x.get('name', '').lower() 
                                         for keyword in ['mimikatz', 'powersploit', 'empire']),
                    'message': 'Suspicious process detected'
                },
                {
                    'name': 'UNUSUAL_PORT',
                    'check': lambda x: any(port in [4444, 31337, 6667] 
                                         for port in x.get('ports', [])),
                    'message': 'Unusual port detected'
                },
                {
                    'name': 'FAILED_AUTH',
                    'check': lambda x: 'authentication failed' in x.get('message', '').lower(),
                    'message': 'Failed authentication attempt'
                }
            ]
            
            for item in data:
                item_anomalies = []
                
                for rule in anomaly_rules:
                    try:
                        if rule['check'](item):
                            item_anomalies.append({
                                'type': rule['name'],
                                'message': rule['message'],
                                'value': item.get('value')
                            })
                            anomalies['anomalies_by_type'][rule['name']] += 1
                    except Exception as e:
                        logger.debug(f"Anomaly rule {rule['name']} failed: {e}", module="processor")
                
                if item_anomalies:
                    anomalies['anomalies_found'] += 1
                    anomalies['details'].append({
                        'item': item.get('id', 'unknown'),
                        'timestamp': item.get('timestamp'),
                        'anomalies': item_anomalies
                    })
            
            # Send Telegram notification for anomalies
            if anomalies['anomalies_found'] > 0:
                self.send_telegram_notification(
                    "🚨 Anomalies Detected",
                    f"Total: {anomalies['anomalies_found']}\n"
                    f"Types: {', '.join(anomalies['anomalies_by_type'].keys())}\n"
                    f"Checked: {anomalies['total_checked']} items"
                )
            
            logger.debug(f"Detected {anomalies['anomalies_found']} anomalies in {anomalies['total_checked']} items", module="processor")
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection error: {e}", module="processor")
            return {'error': str(e)}
    
    def _extract_iocs(self, data: List[Dict]) -> Dict:
        """Extract Indicators of Compromise (IOCs)"""
        try:
            if not data:
                return {'error': 'No data provided'}
            
            iocs = {
                'total_items': len(data),
                'ips': set(),
                'domains': set(),
                'urls': set(),
                'hashes': set(),
                'filenames': set(),
                'registry_keys': set(),
                'counts': {}
            }
            
            # Regex patterns for IOC extraction
            patterns = {
                'ip': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                'domain': r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b',
                'url': r'https?://[^\s]+',
                'md5': r'\b[a-fA-F0-9]{32}\b',
                'sha1': r'\b[a-fA-F0-9]{40}\b',
                'sha256': r'\b[a-fA-F0-9]{64}\b',
                'filename': r'\b[\w\-]+\.[a-zA-Z]{2,4}\b'
            }
            
            for item in data:
                # Convert item to string for pattern matching
                item_str = json.dumps(item)
                
                for ioc_type, pattern in patterns.items():
                    matches = re.findall(pattern, item_str)
                    if matches:
                        ioc_set = iocs.get(ioc_type + 's')
                        if ioc_set is not None:
                            ioc_set.update(matches)
            
            # Convert sets to lists for JSON serialization
            for key in ['ips', 'domains', 'urls', 'hashes', 'filenames', 'registry_keys']:
                iocs[key] = list(iocs[key])
                iocs['counts'][key] = len(iocs[key])
            
            # Send Telegram notification for IOCs
            total_iocs = sum(iocs['counts'].values())
            if total_iocs > 0:
                self.send_telegram_notification(
                    "🔍 IOCs Extracted",
                    f"Total IOCs: {total_iocs}\n"
                    f"IPs: {iocs['counts']['ips']}\n"
                    f"Domains: {iocs['counts']['domains']}\n"
                    f"Hashes: {iocs['counts']['hashes']}"
                )
            
            logger.debug(f"Extracted {total_iocs} IOCs from {len(data)} items", module="processor")
            return iocs
            
        except Exception as e:
            logger.error(f"IOC extraction error: {e}", module="processor")
            return {'error': str(e)}
    
    def _enrich_data(self, data: List[Dict]) -> List[Dict]:
        """Enrich data with additional information"""
        try:
            if not data:
                return []
            
            enriched_data = []
            
            for item in data:
                enriched = item.copy()
                
                # Add enrichment fields
                enriched['_enriched_at'] = datetime.now().isoformat()
                enriched['_hash'] = hashlib.md5(
                    json.dumps(item, sort_keys=True).encode()
                ).hexdigest()
                
                # Enrich based on data type
                if 'ip' in item:
                    # GeoIP enrichment (simulated)
                    ip = item['ip']
                    enriched['_geo'] = {
                        'country': self._get_country_from_ip(ip),
                        'asn': self._get_asn_from_ip(ip),
                        'location': 'Unknown'
                    }
                
                if 'timestamp' in item:
                    # Add time-based enrichment
                    try:
                        dt = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                        enriched['_time'] = {
                            'hour': dt.hour,
                            'day_of_week': dt.strftime('%A'),
                            'is_weekend': dt.weekday() >= 5
                        }
                    except:
                        pass
                
                enriched_data.append(enriched)
            
            logger.debug(f"Enriched {len(data)} items", module="processor")
            return enriched_data
            
        except Exception as e:
            logger.error(f"Data enrichment error: {e}", module="processor")
            return data
    
    def _get_country_from_ip(self, ip: str) -> str:
        """Simulated GeoIP lookup"""
        # In production, use a real GeoIP database
        ip_prefix = ip.split('.')[0]
        country_map = {
            '1': 'US', '2': 'FR', '3': 'DE', '4': 'UK',
            '5': 'CA', '6': 'AU', '7': 'JP', '8': 'CN',
            '9': 'RU', '10': 'BR'
        }
        return country_map.get(ip_prefix, 'Unknown')
    
    def _get_asn_from_ip(self, ip: str) -> str:
        """Simulated ASN lookup"""
        # In production, use a real ASN database
        ip_prefix = ip.split('.')[0]
        asn_map = {
            '1': 'AS7018', '2': 'AS3215', '3': 'AS3320',
            '4': 'AS3356', '5': 'AS6453', '6': 'AS1299',
            '7': 'AS2914', '8': 'AS4134', '9': 'AS8359',
            '10': 'AS27699'
        }
        return asn_map.get(ip_prefix, 'Unknown')
    
    def batch_process(self, tasks: List[Dict]) -> Dict[str, Any]:
        """Process multiple tasks in batch"""
        try:
            task_ids = []
            
            for task in tasks:
                task_id = self.submit_task(
                    task_type=task['type'],
                    data=task['data'],
                    priority=task.get('priority', 0)
                )
                task_ids.append(task_id)
            
            # Wait for all tasks to complete
            results = {}
            for task_id in task_ids:
                result = self.get_result(task_id, timeout=30)
                if result:
                    results[task_id] = result
            
            logger.info(f"Batch processed {len(tasks)} tasks, {len(results)} completed", module="processor")
            return {
                'total_tasks': len(tasks),
                'completed_tasks': len(results),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}", module="processor")
            return {'error': str(e)}
    
    def stop(self):
        """Stop data processor"""
        self.running = False
        
        # Send poison pills to workers
        for _ in range(len(self.workers)):
            self.processing_queue.put(None)
        
        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        
        logger.info("Data processor stopped", module="processor")
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status"""
        return {
            'running': self.running,
            'workers': len(self.workers),
            'queue_size': self.processing_queue.qsize(),
            'results_waiting': self.results_queue.qsize(),
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_data_processor = None

def get_data_processor(config: Dict = None) -> DataProcessor:
    """Get or create data processor instance"""
    global _data_processor
    
    if _data_processor is None:
        _data_processor = DataProcessor(config)
    
    return _data_processor

if __name__ == "__main__":
    # Test the data processor
    config = {
        'worker_count': 2,
        'telegram': {
            'bot_token': 'test_token',
            'processor_chat_id': 123456789
        }
    }
    
    processor = get_data_processor(config)
    
    print("Testing data processor...")
    
    # Test system info analysis
    system_data = [
        {
            'hostname': 'pc-001',
            'platform': 'Windows',
            'cpu_cores': 4,
            'memory_total': 8 * 1024**3,
            'disk_total': 500 * 1024**3,
            'ip_address': '192.168.1.100',
            'timestamp': '2024-01-01T10:00:00'
        },
        {
            'hostname': 'pc-002',
            'platform': 'Linux',
            'cpu_cores': 8,
            'memory_total': 16 * 1024**3,
            'disk_total': 1000 * 1024**3,
            'ip_address': '192.168.1.101',
            'timestamp': '2024-01-01T11:00:00'
        }
    ]
    
    task_id = processor.submit_task('analyze_system_info', system_data)
    print(f"Task submitted: {task_id}")
    
    # Wait for result
    import time
    time.sleep(2)
    
    result = processor.get_result(task_id)
    if result:
        print(f"Task completed by worker {result.get('worker_id')}")
        analysis = result.get('result', {})
        print(f"Systems analyzed: {analysis.get('total_systems', 0)}")
        print(f"Platforms: {analysis.get('platforms', {})}")
    else:
        print("No result yet")
    
    # Test batch processing
    batch_tasks = [
        {'type': 'analyze_system_info', 'data': system_data},
        {'type': 'aggregate_metrics', 'data': {'cpu': [10, 20, 30], 'memory': [50, 60, 70]}}
    ]
    
    batch_result = processor.batch_process(batch_tasks)
    print(f"\nBatch processing: {batch_result.get('completed_tasks', 0)}/{batch_result.get('total_tasks', 0)} completed")
    
    # Show status
    status = processor.get_status()
    print(f"\n🔧 Data Processor Status: {status}")
    
    # Stop processor
    processor.stop()
    
    print("\n✅ Data processor tests completed!")
