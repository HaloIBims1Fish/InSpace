#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
service_manager.py - Advanced Service Management with Full System Control
"""

import os
import sys
import subprocess
import json
import time
import platform
import threading
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

# Import utilities
from ..utils.logger import get_logger
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class ServiceState(Enum):
    """Service states"""
    RUNNING = "running"
    STOPPED = "stopped"
    START_PENDING = "start_pending"
    STOP_PENDING = "stop_pending"
    PAUSED = "paused"
    CONTINUE_PENDING = "continue_pending"
    PAUSE_PENDING = "pause_pending"
    UNKNOWN = "unknown"

class ServiceStartType(Enum):
    """Service start types"""
    BOOT = "boot"          # Started by OS loader
    SYSTEM = "system"      # Started during kernel initialization
    AUTO = "auto"          # Automatic start
    DEMAND = "demand"      # Manual start
    DISABLED = "disabled"  # Disabled
    DELAYED_AUTO = "delayed_auto"  # Delayed automatic start

@dataclass
class ServiceInfo:
    """Detailed service information"""
    name: str
    display_name: str
    state: ServiceState
    start_type: ServiceStartType
    binary_path: Optional[str]
    description: Optional[str]
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    dependencies: List[str] = None
    depends_on: List[str] = None
    username: Optional[str] = None
    log_on_as: Optional[str] = None
    error_control: Optional[str] = None
    service_type: Optional[str] = None
    last_start_time: Optional[datetime] = None
    last_stop_time: Optional[datetime] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.depends_on is None:
            self.depends_on = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['state'] = self.state.value
        data['start_type'] = self.start_type.value
        if self.last_start_time:
            data['last_start_time'] = self.last_start_time.isoformat()
        if self.last_stop_time:
            data['last_stop_time'] = self.last_stop_time.isoformat()
        return data

class ServiceManager:
    """Advanced Service Management with Full Control"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.auto_refresh = self.config.get('auto_refresh', True)
        self.refresh_interval = self.config.get('refresh_interval', 10.0)
        self.privileged_mode = self.config.get('privileged_mode', False)
        
        # Service cache
        self.services: Dict[str, ServiceInfo] = {}
        self.service_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'services_managed': 0,
            'services_started': 0,
            'services_stopped': 0,
            'services_restarted': 0,
            'services_created': 0,
            'services_deleted': 0,
            'start_time': datetime.now()
        }
        
        # Refresh thread
        self.refresh_thread = None
        self.running = False
        
        # Platform-specific initialization
        self.system = platform.system()
        self._init_platform_specific()
        
        # Start auto-refresh if enabled
        if self.auto_refresh:
            self.start_monitoring()
        
        logger.info("Service Manager initialized", module="service_manager")
    
    def _init_platform_specific(self):
        """Initialize platform-specific components"""
        if self.system == 'Windows':
            self._init_windows()
        elif self.system == 'Linux':
            self._init_linux()
        elif self.system == 'Darwin':  # macOS
            self._init_darwin()
    
    def _init_windows(self):
        """Windows-specific initialization"""
        try:
            import win32service
            import win32serviceutil
            self.win32service = win32service
            self.win32serviceutil = win32serviceutil
            self.windows_available = True
        except ImportError:
            self.windows_available = False
            logger.warning("pywin32 not available, Windows service management limited", 
                          module="service_manager")
    
    def _init_linux(self):
        """Linux-specific initialization"""
        self.systemctl_available = self._check_command('systemctl')
        self.service_available = self._check_command('service')
        
        if not self.systemctl_available and not self.service_available:
            logger.warning("Neither systemctl nor service command available", 
                          module="service_manager")
    
    def _init_darwin(self):
        """macOS-specific initialization"""
        self.launchctl_available = self._check_command('launchctl')
        
        if not self.launchctl_available:
            logger.warning("launchctl command not available", module="service_manager")
    
    def _check_command(self, command: str) -> bool:
        """Check if a command is available"""
        try:
            subprocess.run([command, '--version'], 
                          stdout=subprocess.DEVNULL, 
                          stderr=subprocess.DEVNULL,
                          timeout=2)
            return True
        except:
            return False
    
    def start_monitoring(self):
        """Start service monitoring thread"""
        if self.running:
            return
        
        self.running = True
        self.refresh_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.refresh_thread.start()
        logger.info("Service monitoring started", module="service_manager")
    
    def stop_monitoring(self):
        """Stop service monitoring"""
        self.running = False
        if self.refresh_thread:
            self.refresh_thread.join(timeout=5.0)
        logger.info("Service monitoring stopped", module="service_manager")
    
    def _monitoring_loop(self):
        """Monitoring loop for service tracking"""
        while self.running:
            try:
                self.refresh_service_list()
                time.sleep(self.refresh_interval)
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}", module="service_manager")
                time.sleep(10)
    
    def refresh_service_list(self) -> Dict[str, ServiceInfo]:
        """Refresh service list from system"""
        try:
            if self.system == 'Windows':
                return self._refresh_windows_services()
            elif self.system == 'Linux':
                return self._refresh_linux_services()
            elif self.system == 'Darwin':
                return self._refresh_darwin_services()
            else:
                logger.error(f"Unsupported platform: {self.system}", module="service_manager")
                return {}
                
        except Exception as e:
            logger.error(f"Refresh service list error: {e}", module="service_manager")
            return {}
    
    def _refresh_windows_services(self) -> Dict[str, ServiceInfo]:
        """Refresh Windows services"""
        services = {}
        
        try:
            if self.windows_available:
                # Use pywin32 for detailed service info
                import win32service
                
                scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ENUMERATE_SERVICE)
                
                service_types = win32service.SERVICE_WIN32
                service_state = win32service.SERVICE_STATE_ALL
                
                services_list = win32service.EnumServicesStatus(scm, service_types, service_state)
                
                for service_name, display_name, status in services_list:
                    try:
                        # Get detailed service info
                        service_handle = win32service.OpenService(
                            scm, 
                            service_name, 
                            win32service.SERVICE_QUERY_CONFIG | win32service.SERVICE_QUERY_STATUS
                        )
                        
                        # Get service config
                        config = win32service.QueryServiceConfig(service_handle)
                        
                        # Get service status
                        status_info = win32service.QueryServiceStatus(service_handle)
                        
                        # Map state
                        state_map = {
                            win32service.SERVICE_STOPPED: ServiceState.STOPPED,
                            win32service.SERVICE_START_PENDING: ServiceState.START_PENDING,
                            win32service.SERVICE_STOP_PENDING: ServiceState.STOP_PENDING,
                            win32service.SERVICE_RUNNING: ServiceState.RUNNING,
                            win32service.SERVICE_CONTINUE_PENDING: ServiceState.CONTINUE_PENDING,
                            win32service.SERVICE_PAUSE_PENDING: ServiceState.PAUSE_PENDING,
                            win32service.SERVICE_PAUSED: ServiceState.PAUSED
                        }
                        state = state_map.get(status_info[1], ServiceState.UNKNOWN)
                        
                        # Map start type
                        start_type_map = {
                            0: ServiceStartType.BOOT,
                            1: ServiceStartType.SYSTEM,
                            2: ServiceStartType.AUTO,
                            3: ServiceStartType.DEMAND,
                            4: ServiceStartType.DISABLED,
                            5: ServiceStartType.DELAYED_AUTO
                        }
                        start_type = start_type_map.get(config[1], ServiceStartType.UNKNOWN)
                        
                        # Create service info
                        service_info = ServiceInfo(
                            name=service_name,
                            display_name=display_name,
                            state=state,
                            start_type=start_type,
                            binary_path=config[7],  # Binary path
                            description=config[8] if len(config) > 8 else None,
                            pid=status_info[3] if status_info[3] != 0 else None,
                            dependencies=config[5] if len(config) > 5 else [],
                            username=config[6] if len(config) > 6 else None,
                            service_type=self._get_service_type(config[0])
                        )
                        
                        services[service_name] = service_info
                        
                        win32service.CloseServiceHandle(service_handle)
                        
                    except Exception as e:
                        logger.debug(f"Error processing service {service_name}: {e}", 
                                    module="service_manager")
                        continue
                
                win32service.CloseServiceHandle(scm)
                
            else:
                # Fallback to sc command
                services = self._refresh_windows_sc()
            
            with self.service_lock:
                self.services = services
                self.stats['services_managed'] = len(services)
            
            return services
            
        except Exception as e:
            logger.error(f"Windows service refresh error: {e}", module="service_manager")
            return {}
    
    def _refresh_windows_sc(self) -> Dict[str, ServiceInfo]:
        """Refresh Windows services using sc command"""
        services = {}
        
        try:
            # Get service list using sc query
            result = subprocess.run(
                ['sc', 'query', 'type=', 'service', 'state=', 'all'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return services
            
            lines = result.stdout.split('\n')
            current_service = None
            
            for line in lines:
                line = line.strip()
                
                if line.startswith('SERVICE_NAME:'):
                    if current_service:
                        services[current_service['name']] = ServiceInfo(**current_service)
                    
                    service_name = line.split(':', 1)[1].strip()
                    current_service = {
                        'name': service_name,
                        'display_name': service_name,
                        'state': ServiceState.UNKNOWN,
                        'start_type': ServiceStartType.UNKNOWN,
                        'binary_path': None,
                        'description': None
                    }
                
                elif current_service:
                    if line.startswith('DISPLAY_NAME:'):
                        current_service['display_name'] = line.split(':', 1)[1].strip()
                    elif line.startswith('STATE:'):
                        state_str = line.split(':', 1)[1].strip()
                        if 'RUNNING' in state_str:
                            current_service['state'] = ServiceState.RUNNING
                        elif 'STOPPED' in state_str:
                            current_service['state'] = ServiceState.STOPPED
                    elif line.startswith('BINARY_PATH_NAME:'):
                        current_service['binary_path'] = line.split(':', 1)[1].strip()
            
            # Add last service
            if current_service:
                services[current_service['name']] = ServiceInfo(**current_service)
            
            return services
            
        except Exception as e:
            logger.error(f"Windows sc refresh error: {e}", module="service_manager")
            return {}
    
    def _refresh_linux_services(self) -> Dict[str, ServiceInfo]:
        """Refresh Linux services"""
        services = {}
        
        try:
            if self.systemctl_available:
                # Use systemctl for systemd systems
                services = self._refresh_systemd_services()
            elif self.service_available:
                # Use service command for SysV systems
                services = self._refresh_sysv_services()
            else:
                # Check /etc/init.d directory
                services = self._refresh_initd_services()
            
            with self.service_lock:
                self.services = services
                self.stats['services_managed'] = len(services)
            
            return services
            
        except Exception as e:
            logger.error(f"Linux service refresh error: {e}", module="service_manager")
            return {}
    
    def _refresh_systemd_services(self) -> Dict[str, ServiceInfo]:
        """Refresh systemd services"""
        services = {}
        
        try:
            # Get all services
            result = subprocess.run(
                ['systemctl', 'list-units', '--type=service', '--all', '--no-pager', '--no-legend'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return services
            
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    service_name = parts[0]
                    state_str = parts[3]
                    
                    # Get detailed info
                    try:
                        # Get service file info
                        show_result = subprocess.run(
                            ['systemctl', 'show', service_name, '--no-pager'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if show_result.returncode == 0:
                            details = {}
                            for detail_line in show_result.stdout.strip().split('\n'):
                                if '=' in detail_line:
                                    key, value = detail_line.split('=', 1)
                                    details[key] = value
                            
                            # Map state
                            state_map = {
                                'active': ServiceState.RUNNING,
                                'inactive': ServiceState.STOPPED,
                                'activating': ServiceState.START_PENDING,
                                'deactivating': ServiceState.STOP_PENDING,
                                'failed': ServiceState.STOPPED
                            }
                            state = state_map.get(details.get('ActiveState', '').lower(), ServiceState.UNKNOWN)
                            
                            # Map start type
                            start_type_map = {
                                'enabled': ServiceStartType.AUTO,
                                'disabled': ServiceStartType.DISABLED,
                                'static': ServiceStartType.SYSTEM,
                                'masked': ServiceStartType.DISABLED
                            }
                            start_type = start_type_map.get(details.get('UnitFileState', '').lower(), ServiceStartType.UNKNOWN)
                            
                            service_info = ServiceInfo(
                                name=service_name,
                                display_name=details.get('Description', service_name),
                                state=state,
                                start_type=start_type,
                                binary_path=details.get('ExecStart', ''),
                                description=details.get('Description'),
                                pid=int(details.get('MainPID', 0)) if details.get('MainPID', '0').isdigit() else None
                            )
                            
                            services[service_name] = service_info
                            
                    except Exception as e:
                        logger.debug(f"Error processing systemd service {service_name}: {e}", 
                                    module="service_manager")
                        continue
            
            return services
            
        except Exception as e:
            logger.error(f"Systemd refresh error: {e}", module="service_manager")
            return {}
    
    def _refresh_sysv_services(self) -> Dict[str, ServiceInfo]:
        """Refresh SysV services"""
        services = {}
        
        try:
            # Check /etc/init.d directory
            initd_path = '/etc/init.d'
            if os.path.exists(initd_path):
                for service_file in os.listdir(initd_path):
                    service_path = os.path.join(initd_path, service_file)
                    if os.path.isfile(service_path) and os.access(service_path, os.X_OK):
                        
                        # Check status
                        try:
                            result = subprocess.run(
                                ['service', service_file, 'status'],
                                capture_output=True,
                                text=True,
                                timeout=5
                            )
                            
                            state = ServiceState.UNKNOWN
                            if result.returncode == 0:
                                if 'running' in result.stdout.lower():
                                    state = ServiceState.RUNNING
                                elif 'stopped' in result.stdout.lower():
                                    state = ServiceState.STOPPED
                            
                            service_info = ServiceInfo(
                                name=service_file,
                                display_name=service_file,
                                state=state,
                                start_type=ServiceStartType.UNKNOWN,
                                binary_path=service_path,
                                description=f"SysV service: {service_file}"
                            )
                            
                            services[service_file] = service_info
                            
                        except Exception as e:
                            continue
            
            return services
            
        except Exception as e:
            logger.error(f"SysV refresh error: {e}", module="service_manager")
            return {}
    
    def _refresh_initd_services(self) -> Dict[str, ServiceInfo]:
        """Refresh init.d services directly"""
        services = {}
        
        try:
            initd_path = '/etc/init.d'
            if os.path.exists(initd_path):
                for service_file in os.listdir(initd_path):
                    service_path = os.path.join(initd_path, service_file)
                    if os.path.isfile(service_path):
                        service_info = ServiceInfo(
                            name=service_file,
                            display_name=service_file,
                            state=ServiceState.UNKNOWN,
                            start_type=ServiceStartType.UNKNOWN,
                            binary_path=service_path,
                            description=f"Init.d service: {service_file}"
                        )
                        services[service_file] = service_info
            
            return services
            
        except Exception as e:
            logger.error(f"Init.d refresh error: {e}", module="service_manager")
            return {}
    
    def _refresh_darwin_services(self) -> Dict[str, ServiceInfo]:
        """Refresh macOS (Darwin) services"""
        services = {}
        
        try:
            if self.launchctl_available:
                # Get all launchd services
                result = subprocess.run(
                    ['launchctl', 'list'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    
                    for line in lines[1:]:  # Skip header
                        parts = line.split()
                        if len(parts) >= 3:
                            pid_str = parts[0]
                            status_str = parts[1]
                            service_name = parts[2]
                            
                            state = ServiceState.UNKNOWN
                            if status_str == '-':
                                state = ServiceState.STOPPED
                            elif pid_str != '-':
                                state = ServiceState.RUNNING
                            
                            service_info = ServiceInfo(
                                name=service_name,
                                display_name=service_name,
                                state=state,
                                start_type=ServiceStartType.UNKNOWN,
                                binary_path=None,
                                description=f"Launchd service: {service_name}",
                                pid=int(pid_str) if pid_str.isdigit() else None
                            )
                            
                            services[service_name] = service_info
            
            return services
            
        except Exception as e:
            logger.error(f"Darwin service refresh error: {e}", module="service_manager")
            return {}
    
    def _get_service_type(self, service_type_int: int) -> str:
        """Get service type string from integer"""
        if self.system != 'Windows':
            return "unknown"
        
        type_map = {
            1: "kernel_driver",
            2: "file_system_driver",
            4: "adapter",
            8: "recognizer_driver",
            16: "win32_own_process",
            32: "win32_share_process",
            256: "interactive_process"
        }
        
        for key, value in type_map.items():
            if service_type_int & key:
                return value
        
        return "unknown"
    
    def get_service(self, service_name: str) -> Optional[ServiceInfo]:
        """Get detailed information about a specific service"""
        try:
            with self.service_lock:
                if service_name in self.services:
                    return self.services[service_name]
            
            # Try to get fresh info
            self.refresh_service_list()
            
            with self.service_lock:
                return self.services.get(service_name)
            
        except Exception as e:
            logger.error(f"Get service error: {e}", module="service_manager")
            return None
    
    def get_services_by_state(self, state: ServiceState) -> List[ServiceInfo]:
        """Get services by state"""
        results = []
        
        try:
            with self.service_lock:
                for service in self.services.values():
                    if service.state == state:
                        results.append(service)
            
            return results
            
        except Exception as e:
            logger.error(f"Get services by state error: {e}", module="service_manager")
            return []
    
    def start_service(self, service_name: str, wait: bool = True) -> bool:
        """Start a service"""
        try:
            if self.system == 'Windows':
                success = self._start_windows_service(service_name, wait)
            elif self.system == 'Linux':
                success = self._start_linux_service(service_name, wait)
            elif self.system == 'Darwin':
                success = self._start_darwin_service(service_name, wait)
            else:
                logger.error(f"Unsupported platform: {self.system}", module="service_manager")
                return False
            
            if success:
                self.stats['services_started'] += 1
                
                # Update cache
                with self.service_lock:
                    if service_name in self.services:
                        self.services[service_name].state = ServiceState.RUNNING
                        self.services[service_name].last_start_time = datetime.now()
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.SERVICE_START.value,
                    severity=AuditSeverity.INFO.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Service started: {service_name}",
                    details={
                        'service_name': service_name,
                        'platform': self.system,
                        'wait': wait,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='service_manager',
                    action='start_service'
                )
                
                logger.info(f"Service {service_name} started", module="service_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Start service error: {e}", module="service_manager")
            return False
    
    def _start_windows_service(self, service_name: str, wait: bool) -> bool:
        """Start Windows service"""
        try:
            if self.windows_available:
                import win32service
                import win32serviceutil
                
                win32serviceutil.StartService(service_name)
                
                if wait:
                    time.sleep(5)  # Wait for service to start
                
                return True
            else:
                # Use sc command
                result = subprocess.run(
                    ['sc', 'start', service_name],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                return result.returncode == 0
                
        except Exception as e:
            logger.error(f"Start Windows service error: {e}", module="service_manager")
            return False
    
    def _start_linux_service(self, service_name: str, wait: bool) -> bool:
        """Start Linux service"""
        try:
            if self.systemctl_available:
                cmd = ['systemctl', 'start', service_name]
            elif self.service_available:
                cmd = ['service', service_name, 'start']
            else:
                cmd = [os.path.join('/etc/init.d', service_name), 'start']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if wait:
                time.sleep(3)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Start Linux service error: {e}", module="service_manager")
            return False
    
    def _start_darwin_service(self, service_name: str, wait: bool) -> bool:
        """Start macOS service"""
        try:
            result = subprocess.run(
                ['launchctl', 'load', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if wait:
                time.sleep(3)
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Start Darwin service error: {e}", module="service_manager")
            return False
    
    def stop_service(self, service_name: str, force: bool = False) -> bool:
        """Stop a service"""
        try:
            if self.system == 'Windows':
                success = self._stop_windows_service(service_name, force)
            elif self.system == 'Linux':
                success = self._stop_linux_service(service_name, force)
            elif self.system == 'Darwin':
                success = self._stop_darwin_service(service_name, force)
            else:
                logger.error(f"Unsupported platform: {self.system}", module="service_manager")
                return False
            
            if success:
                self.stats['services_stopped'] += 1
                
                # Update cache
                with self.service_lock:
                    if service_name in self.services:
                        self.services[service_name].state = ServiceState.STOPPED
                        self.services[service_name].last_stop_time = datetime.now()
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.SERVICE_STOP.value,
                    severity=AuditSeverity.WARNING.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Service stopped: {service_name}",
                    details={
                        'service_name': service_name,
                        'platform': self.system,
                        'force': force,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='service_manager',
                    action='stop_service'
                )
                
                logger.info(f"Service {service_name} stopped", module="service_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Stop service error: {e}", module="service_manager")
            return False
    
    def _stop_windows_service(self, service_name: str, force: bool) -> bool:
        """Stop Windows service"""
        try:
            if self.windows_available:
                import win32service
                import win32serviceutil
                
                if force:
                    win32serviceutil.StopServiceWithDeps(service_name)
                else:
                    win32serviceutil.StopService(service_name)
                
                return True
            else:
                # Use sc command
                cmd = ['sc', 'stop', service_name]
                if force:
                    cmd = ['sc', 'stop', service_name, '/force']
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                return result.returncode == 0
                
        except Exception as e:
            logger.error(f"Stop Windows service error: {e}", module="service_manager")
            return False
    
    def _stop_linux_service(self, service_name: str, force: bool) -> bool:
        """Stop Linux service"""
        try:
            if self.systemctl_available:
                cmd = ['systemctl', 'stop', service_name]
                if force:
                    cmd = ['systemctl', 'kill', service_name, '--signal=SIGKILL']
            elif self.service_available:
                cmd = ['service', service_name, 'stop']
                if force:
                    cmd = ['service', service_name, 'force-stop']
            else:
                cmd = [os.path.join('/etc/init.d', service_name), 'stop']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Stop Linux service error: {e}", module="service_manager")
            return False
    
    def _stop_darwin_service(self, service_name: str, force: bool) -> bool:
        """Stop macOS service"""
        try:
            cmd = ['launchctl', 'unload', service_name]
            if force:
                cmd = ['launchctl', 'bootout', 'system', service_name]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Stop Darwin service error: {e}", module="service_manager")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        try:
            # Stop first
            if not self.stop_service(service_name):
                return False
            
            # Wait a moment
            time.sleep(2)
            
            # Start again
            success = self.start_service(service_name)
            
            if success:
                self.stats['services_restarted'] += 1
                logger.info(f"Service {service_name} restarted", module="service_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Restart service error: {e}", module="service_manager")
            return False
    
    def create_service(self, service_config: Dict[str, Any]) -> bool:
        """Create a new service"""
        try:
            if self.system == 'Windows':
                success = self._create_windows_service(service_config)
            elif self.system == 'Linux':
                success = self._create_linux_service(service_config)
            elif self.system == 'Darwin':
                success = self._create_darwin_service(service_config)
            else:
                logger.error(f"Unsupported platform: {self.system}", module="service_manager")
                return False
            
            if success:
                self.stats['services_created'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.SERVICE_CREATE.value,
                    severity=AuditSeverity.HIGH.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Service created: {service_config.get('name')}",
                    details={
                        'service_config': service_config,
                        'platform': self.system,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='service_manager',
                    action='create_service'
                )
                
                logger.info(f"Service {service_config.get('name')} created", module="service_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Create service error: {e}", module="service_manager")
            return False
    
    def _create_windows_service(self, config: Dict[str, Any]) -> bool:
        """Create Windows service"""
        try:
            name = config.get('name')
            display_name = config.get('display_name', name)
            binary_path = config.get('binary_path')
            start_type = config.get('start_type', 'demand')
            
            if not name or not binary_path:
                return False
            
            # Use sc command to create service
            cmd = [
                'sc', 'create', name,
                f'DisplayName= "{display_name}"',
                f'binpath= "{binary_path}"',
                f'start= {start_type}'
            ]
            
            if config.get('description'):
                cmd.append(f'Description= "{config["description"]}"')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Create Windows service error: {e}", module="service_manager")
            return False
    
    def _create_linux_service(self, config: Dict[str, Any]) -> bool:
        """Create Linux service"""
        try:
            name = config.get('name')
            binary_path = config.get('binary_path')
            description = config.get('description', f"Custom service: {name}")
            
            if not name or not binary_path:
                return False
            
            # Create systemd service file
            service_content = f"""[Unit]
Description={description}

[Service]
ExecStart={binary_path}
Restart=always
User=root

[Install]
WantedBy=multi-user.target
"""
            
            service_file = f"/etc/systemd/system/{name}.service"
            
            # Write service file
            with open(service_file, 'w') as f:
                f.write(service_content)
            
            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], timeout=10)
            
            # Enable if requested
            if config.get('auto_start', False):
                subprocess.run(['systemctl', 'enable', name], timeout=10)
            
            return True
            
        except Exception as e:
            logger.error(f"Create Linux service error: {e}", module="service_manager")
            return False
    
    def _create_darwin_service(self, config: Dict[str, Any]) -> bool:
        """Create macOS service"""
        try:
            name = config.get('name')
            binary_path = config.get('binary_path')
            
            if not name or not binary_path:
                return False
            
            # Create launchd plist
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtdplist version="1.0">
<dict>
    <key>Label</key>
    <string>{name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{binarystring>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <truedict>
</plist>
"""
            
            plist_file = f"/Library/LaunchDaemons/{name}.plist"
            
            # Write plist file
            with open(plist_file, 'w') as f:
                f.write(plist_content)
            
            # Load service
            subprocess.run(['launchctl', 'load', plist_file], timeout=10)
            
            return True
            
        except Exception as e:
            logger.error(f"Create Darwin service error: {e}", module="service_manager")
            return False
    
    def delete_service(self, service_name: str, remove_files: bool = True) -> bool:
        """Delete a service"""
        try:
            # Stop service first
            self.stop_service(service_name, force=True)
            
            if self.system == 'Windows':
                success = self._delete_windows_service(service_name, remove_files)
            elif self.system == 'Linux':
                success = self._delete_linux_service(service_name, remove_files)
            elif self.system == 'Darwin':
                success = self._delete_darwin_service(service_name, remove_files)
            else:
                logger.error(f"Unsupported platform: {self.system}", module="service_manager")
                return False
            
            if success:
                self.stats['services_deleted'] += 1
                
                # Remove from cache
                with self.service_lock:
                    if service_name in self.services:
                        del self.services[service_name]
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.SERVICE_DELETE.value,
                    severity=AuditSeverity.HIGH.value,
                    user='system',
                    source_ip='localhost',
                    description=f"Service deleted: {service_name}",
                    details={
                        'service_name': service_name,
                        'platform': self.system,
                        'remove_files': remove_files,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='service_manager',
                    action='delete_service'
                )
                
                logger.info(f"Service {service_name} deleted", module="service_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"Delete service error: {e}", module="service_manager")
            return False
    
    def _delete_windows_service(self, service_name: str, remove_files: bool) -> bool:
        """Delete Windows service"""
        try:
            # Use sc command to delete service
            result = subprocess.run(
                ['sc', 'delete', service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Delete Windows service error: {e}", module="service_manager")
            return False
    
    def _delete_linux_service(self, service_name: str, remove_files: bool) -> bool:
        """Delete Linux service"""
        try:
            if self.systemctl_available:
                # Disable service
                subprocess.run(['systemctl', 'disable', service_name], timeout=10)
                
                # Remove service file
                if remove_files:
                    service_file = f"/etc/systemd/system/{service_name}.service"
                    if os.path.exists(service_file):
                        os.remove(service_file)
                
                # Reload systemd
                subprocess.run(['systemctl', 'daemon-reload'], timeout=10)
            
            return True
            
        except Exception as e:
            logger.error(f"Delete Linux service error: {e}", module="service_manager")
            return False
    
    def _delete_darwin_service(self, service_name: str, remove_files: bool) -> bool:
        """Delete macOS service"""
        try:
            # Unload service
            subprocess.run(['launchctl', 'unload', service_name], timeout=10)
            
            # Remove plist file
            if remove_files:
                plist_file = f"/Library/LaunchDaemons/{service_name}.plist"
                if os.path.exists(plist_file):
                    os.remove(plist_file)
            
            return True
            
        except Exception as e:
            logger.error(f"Delete Darwin service error: {e}", module="service_manager")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get service manager statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        with self.service_lock:
            service_count = len(self.services)
            running_count = sum(1 for s in self.services.values() 
                              if s.state == ServiceState.RUNNING)
            stopped_count = sum(1 for s in self.services.values() 
                              if s.state == ServiceState.STOPPED)
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
            'current_service_count': service_count,
            'running_services': running_count,
            'stopped_services': stopped_count,
            'monitoring_active': self.running,
            'platform': self.system,
            'privileged_mode': self.privileged_mode
        }
    
    def export_service_list(self, format: str = 'json', filepath: Optional[str] = None) -> Optional[str]:
        """Export service list"""
        try:
            with self.service_lock:
                services = [s.to_dict() for s in self.services.values()]
            
            if format.lower() == 'json':
                output = json.dumps({
                    'services': services,
                    'timestamp': datetime.now().isoformat(),
                    'total_services': len(services),
                    'platform': self.system
                }, indent=2)
            
            elif format.lower() == 'csv':
                import csv
                import io
                
                output_io = io.StringIO()
                writer = csv.writer(output_io)
                
                # Write header
                writer.writerow(['Name', 'Display Name', 'State', 'Start Type', 
                               'Binary Path', 'PID', 'Description'])
                
                # Write data
                for svc in services:
                    writer.writerow([
                        svc['name'],
                        svc['display_name'],
                        svc['state'],
                        svc['start_type'],
                        svc['binary_path'] or '',
                        svc['pid'] or '',
                        svc['description'] or ''
                    ])
                
                output = output_io.getvalue()
            
            elif format.lower() == 'text':
                output_lines = []
                output_lines.append(f"Service List - {len(services)} services ({self.system})")
                output_lines.append("=" * 100)
                
                for svc in sorted(services, key=lambda x: x['name'])[:50]:
                    state_symbol = '🟢' if svc['state'] == 'running' else '🔴'
                    output_lines.append(
                        f"{state_symbol} {svc['name'][:30]:30} "
                        f"{svc['display_name'][:30]:30} "
                        f"{svc['state']:15} {svc['start_type']}"
                    )
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported format: {format}", module="service_manager")
                return None
            
            # Write to file if specified
            if filepath:
                with open(filepath, 'w') as f:
                    f.write(output)
                logger.info(f"Service list exported to {filepath}", module="service_manager")
            
            return output
            
        except Exception as e:
            logger.error(f"Export service list error: {e}", module="service_manager")
            return None
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.stop_monitoring()
        except:
            pass

# Global instance
_service_manager = None

def get_service_manager(config: Dict = None) -> ServiceManager:
    """Get or create service manager instance"""
    global _service_manager
    
    if _service_manager is None:
        _service_manager = ServiceManager(config)
    
    return _service_manager

if __name__ == "__main__":
    print("Testing Service Manager...")
    
    # Test configuration
    config = {
        'auto_refresh': True,
        'refresh_interval': 5.0,
        'privileged_mode': False
    }
    
    sm = get_service_manager(config)
    
    print(f"\n1. Platform: {sm.system}")
    print("2. Refreshing service list...")
    services = sm.refresh_service_list()
    print(f"Found {len(services)} services")
    
    print("\n3. Getting service statistics...")
    stats = sm.get_statistics()
    print(f"Services managed: {stats['services_managed']}")
    print(f"Services started: {stats['services_started']}")
    print(f"Services stopped: {stats['services_stopped']}")
    
    if services:
        print("\n4. Sample services:")
        for i, (name, service) in enumerate(list(services.items())[:5]):
            print(f"  {i+1}. {name}: {service.state.value}")
    
    print("\n5. Exporting service list...")
    export_data = sm.export_service_list('text')
    if export_data:
        print(export_data[:500] + "..." if len(export_data)500 else export_data)
    
    # Stop monitoring
    sm.stop_monitoring()
    
    print("\n✅ Service Manager tests completed!")
