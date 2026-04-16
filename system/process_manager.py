#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_manager.py - Advanced Process Management with Full System Control
"""

import os
import sys
import psutil
import signal
import subprocess
import threading
import time
import json
import ctypes
import win32api
import win32process
import win32con
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import platform

# Import utilities
from ..utils.logger import get_logger
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class ProcessPriority(Enum):
    """Process priority levels"""
    REALTIME = "realtime"      # Highest priority
    HIGH = "high"              # High priority
    ABOVE_NORMAL = "above_normal"
    NORMAL = "normal"
    BELOW_NORMAL = "below_normal"
    IDLE = "idle"              # Lowest priority

class ProcessState(Enum):
    """Process states"""
    RUNNING = "running"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    ZOMBIE = "zombie"
    UNKNOWN = "unknown"

@dataclass
class ProcessInfo:
    """Detailed process information"""
    pid: int
    name: str
    exe_path: Optional[str]
    cmdline: List[str]
    username: str
    cpu_percent: float
    memory_percent: float
    memory_rss: int  # Resident Set Size in bytes
    memory_vms: int  # Virtual Memory Size in bytes
    create_time: float
    threads: int
    handles: Optional[int] = None
    priority: Optional[str] = None
    state: ProcessState = ProcessState.UNKNOWN
    parent_pid: Optional[int] = None
    children: List[int] = None
    environment: Dict[str, str] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.environment is None:
            self.environment = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['state'] = self.state.value
        data['memory_rss_mb'] = self.memory_rss / 1024 / 1024
        data['memory_vms_mb'] = self.memory_vms / 1024 / 1024
        data['create_time_iso'] = datetime.fromtimestamp(self.create_time).isoformat()
        return data

class ProcessManager:
    """Advanced Process Management with Full Control"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.auto_refresh = self.config.get('auto_refresh', True)
        self.refresh_interval = self.config.get('refresh_interval', 2.0)
        self.max_processes = self.config.get('max_processes', 1000)
        self.privileged_mode = self.config.get('privileged_mode', False)
        
        # Process cache
        self.processes: Dict[int, ProcessInfo] = {}
        self.process_lock = threading.Lock()
        
        # Injection cache
        self.injected_processes = set()
        
        # Statistics
        self.stats = {
            'total_processes_scanned': 0,
            'processes_terminated': 0,
            'processes_suspended': 0,
            'processes_resumed': 0,
            'processes_injected': 0,
            'start_time': datetime.now()
        }
        
        # Refresh thread
        self.refresh_thread = None
        self.running = False
        
        # Start auto-refresh if enabled
        if self.auto_refresh:
            self.start_monitoring()
        
        logger.info("Process Manager initialized", module="process_manager")
    
    def start_monitoring(self):
        """Start process monitoring thread"""
        if self.running:
            return
        
        self.running = True
        self.refresh_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.refresh_thread.start()
        logger.info("Process monitoring started", module="process_manager")
    
    def stop_monitoring(self):
        """Stop process monitoring"""
        self.running = False
        if self.refresh_thread:
            self.refresh_thread.join(timeout=5.0)
        logger.info("Process monitoring stopped", module="process_manager")
    
    def _monitoring_loop(self):
        """Monitoring loop for process tracking"""
        while self.running:
            try:
                self.refresh_process_list()
                time.sleep(self.refresh_interval)
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}", module="process_manager")
                time.sleep(5)
    
    def refresh_process_list(self) -> Dict[int, ProcessInfo]:
        """Refresh process list from system"""
        try:
            new_processes = {}
            
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'username', 
                                           'cpu_percent', 'memory_percent', 'memory_info',
                                           'create_time', 'num_threads', 'ppid']):
                try:
                    proc_info = proc.info
                    
                    # Get memory info
                    memory_info = proc_info.get('memory_info')
                    if memory_info:
                        rss = memory_info.rss
                        vms = memory_info.vms
                    else:
                        rss = vms = 0
                    
                    # Get handles if available (Windows)
                    handles = None
                    if platform.system() == 'Windows':
                        try:
                            handles = proc.num_handles()
                        except:
                            pass
                    
                    # Get children
                    children = []
                    try:
                        for child in proc.children():
                            children.append(child.pid)
                    except:
                        pass
                    
                    # Get environment (requires elevated privileges)
                    env = {}
                    if self.privileged_mode:
                        try:
                            env = proc.environ()
                        except:
                            pass
                    
                    # Get priority
                    priority = None
                    try:
                        priority = proc.nice()
                    except:
                        pass
                    
                    # Determine state
                    state = ProcessState.UNKNOWN
                    try:
                        status = proc.status()
                        if status == psutil.STATUS_RUNNING:
                            state = ProcessState.RUNNING
                        elif status == psutil.STATUS_STOPPED:
                            state = ProcessState.SUSPENDED
                        elif status == psutil.STATUS_ZOMBIE:
                            state = ProcessState.ZOMBIE
                    except:
                        pass
                    
                    process_info = ProcessInfo(
                        pid=proc_info['pid'],
                        name=proc_info['name'],
                        exe_path=proc_info.get('exe'),
                        cmdline=proc_info.get('cmdline') or [],
                        username=proc_info.get('username', 'unknown'),
                        cpu_percent=proc_info.get('cpu_percent', 0.0),
                        memory_percent=proc_info.get('memory_percent', 0.0),
                        memory_rss=rss,
                        memory_vms=vms,
                        create_time=proc_info.get('create_time', 0),
                        threads=proc_info.get('num_threads', 0),
                        handles=handles,
                        priority=str(priority) if priority is not None else None,
                        state=state,
                        parent_pid=proc_info.get('ppid'),
                        children=children,
                        environment=env
                    )
                    
                    new_processes[proc_info['pid']] = process_info
                    
                    # Limit number of processes
                    if len(new_processes) >= self.max_processes:
                        break
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                except Exception as e:
                    logger.debug(f"Error processing process: {e}", module="process_manager")
                    continue
            
            with self.process_lock:
                self.processes = new_processes
                self.stats['total_processes_scanned'] = len(new_processes)
            
            return new_processes
            
        except Exception as e:
            logger.error(f"Refresh process list error: {e}", module="process_manager")
            return {}
    
    def get_process(self, pid: int) -> Optional[ProcessInfo]:
        """Get detailed information about a specific process"""
        try:
            with self.process_lock:
                if pid in self.processes:
                    return self.processes[pid]
            
            # Try to get fresh info if not in cache
            try:
                proc = psutil.Process(pid)
                
                # Build ProcessInfo from fresh data
                memory_info = proc.memory_info()
                
                process_info = ProcessInfo(
                    pid=pid,
                    name=proc.name(),
                    exe_path=proc.exe(),
                    cmdline=proc.cmdline(),
                    username=proc.username(),
                    cpu_percent=proc.cpu_percent(),
                    memory_percent=proc.memory_percent(),
                    memory_rss=memory_info.rss,
                    memory_vms=memory_info.vms,
                    create_time=proc.create_time(),
                    threads=proc.num_threads(),
                    handles=proc.num_handles() if hasattr(proc, 'num_handles') else None,
                    priority=str(proc.nice()),
                    parent_pid=proc.ppid(),
                    children=[c.pid for c in proc.children()],
                    environment=proc.environ() if self.privileged_mode else {}
                )
                
                with self.process_lock:
                    self.processes[pid] = process_info
                
                return process_info
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return None
                
        except Exception as e:
            logger.error(f"Get process error: {e}", module="process_manager")
            return None
    
    def get_processes_by_name(self, name: str, exact_match: bool = False) -> List[ProcessInfo]:
        """Get processes by name"""
        results = []
        
        try:
            with self.process_lock:
                for proc in self.processes.values():
                    if exact_match:
                        if proc.name.lower() == name.lower():
                            results.append(proc)
                    else:
                        if name.lower() in proc.name.lower():
                            results.append(proc)
            
            return results
            
        except Exception as e:
            logger.error(f"Get processes by name error: {e}", module="process_manager")
            return []
    
    def terminate_process(self, pid: int, force: bool = True) -> bool:
        """Terminate a process"""
        try:
            proc = psutil.Process(pid)
            
            if force:
                proc.kill()
            else:
                proc.terminate()
            
            # Wait for termination
            try:
                proc.wait(timeout=5.0)
            except:
                pass
            
            # Remove from cache
            with self.process_lock:
                if pid in self.processes:
                    del self.processes[pid]
            
            self.stats['processes_terminated'] += 1
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.PROCESS_TERMINATE.value,
                severity=AuditSeverity.WARNING.value,
                user='system',
                source_ip='localhost',
                description=f"Process terminated: PID {pid}",
                details={
                    'pid': pid,
                    'name': proc.name(),
                    'force': force,
                    'timestamp': datetime.now().isoformat()
                },
                resource='process_manager',
                action='terminate_process'
            )
            
            logger.info(f"Process {pid} terminated", module="process_manager")
            return True
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Cannot terminate process {pid}: {e}", module="process_manager")
            return False
        except Exception as e:
            logger.error(f"Terminate process error: {e}", module="process_manager")
            return False
    
    def terminate_processes_by_name(self, name: str, force: bool = True) -> int:
        """Terminate all processes with matching name"""
        terminated = 0
        
        try:
            processes = self.get_processes_by_name(name, exact_match=False)
            
            for proc in processes:
                if self.terminate_process(proc.pid, force):
                    terminated += 1
            
            logger.info(f"Terminated {terminated} processes with name containing '{name}'", 
                       module="process_manager")
            return terminated
            
        except Exception as e:
            logger.error(f"Terminate processes by name error: {e}", module="process_manager")
            return 0
    
    def suspend_process(self, pid: int) -> bool:
        """Suspend (pause) a process"""
        try:
            if platform.system() == 'Windows':
                # Windows suspend
                import ctypes
                from ctypes import wintypes
                
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
                
                if handle:
                    kernel32.SuspendThread(handle)
                    kernel32.CloseHandle(handle)
            else:
                # Unix suspend
                os.kill(pid, signal.SIGSTOP)
            
            # Update cache
            with self.process_lock:
                if pid in self.processes:
                    self.processes[pid].state = ProcessState.SUSPENDED
            
            self.stats['processes_suspended'] += 1
            
            logger.info(f"Process {pid} suspended", module="process_manager")
            return True
            
        except Exception as e:
            logger.error(f"Suspend process error: {e}", module="process_manager")
            return False
    
    def resume_process(self, pid: int) -> bool:
        """Resume a suspended process"""
        try:
            if platform.system() == 'Windows':
                # Windows resume
                import ctypes
                from ctypes import wintypes
                
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.OpenProcess(win32con.PROCESS_ALL_ACCESS, False, pid)
                
                if handle:
                    kernel32.ResumeThread(handle)
                    kernel32.CloseHandle(handle)
            else:
                # Unix resume
                os.kill(pid, signal.SIGCONT)
            
            # Update cache
            with self.process_lock:
                if pid in self.processes:
                    self.processes[pid].state = ProcessState.RUNNING
            
            self.stats['processes_resumed'] += 1
            
            logger.info(f"Process {pid} resumed", module="process_manager")
            return True
            
        except Exception as e:
            logger.error(f"Resume process error: {e}", module="process_manager")
            return False
    
    def set_process_priority(self, pid: int, priority: ProcessPriority) -> bool:
        """Set process priority"""
        try:
            proc = psutil.Process(pid)
            
            # Map priority enum to psutil values
            priority_map = {
                ProcessPriority.REALTIME: psutil.REALTIME_PRIORITY_CLASS,
                ProcessPriority.HIGH: psutil.HIGH_PRIORITY_CLASS,
                ProcessPriority.ABOVE_NORMAL: psutil.ABOVE_NORMAL_PRIORITY_CLASS,
                ProcessPriority.NORMAL: psutil.NORMAL_PRIORITY_CLASS,
                ProcessPriority.BELOW_NORMAL: psutil.BELOW_NORMAL_PRIORITY_CLASS,
                ProcessPriority.IDLE: psutil.IDLE_PRIORITY_CLASS
            }
            
            if platform.system() == 'Windows':
                proc.nice(priority_map[priority])
            else:
                # Unix uses nice values
                nice_map = {
                    ProcessPriority.REALTIME: -20,
                    ProcessPriority.HIGH: -10,
                    ProcessPriority.ABOVE_NORMAL: -5,
                    ProcessPriority.NORMAL: 0,
                    ProcessPriority.BELOW_NORMAL: 10,
                    ProcessPriority.IDLE: 19
                }
                os.nice(nice_map[priority])
            
            # Update cache
            with self.process_lock:
                if pid in self.processes:
                    self.processes[pid].priority = priority.value
            
            logger.info(f"Process {pid} priority set to {priority.value}", module="process_manager")
            return True
            
        except Exception as e:
            logger.error(f"Set process priority error: {e}", module="process_manager")
            return False
    
    def inject_dll(self, pid: int, dll_path: str, method: str = "createremotethread") -> bool:
        """Inject DLL into process (Windows only)"""
        try:
            if platform.system() != 'Windows':
                logger.error("DLL injection only supported on Windows", module="process_manager")
                return False
            
            if not os.path.exists(dll_path):
                logger.error(f"DLL not found: {dll_path}", module="process_manager")
                return False
            
            # Different injection methods
            if method == "createremotethread":
                success = self._inject_createremotethread(pid, dll_path)
            elif method == "queueuserapc":
                success = self._inject_queueuserapc(pid, dll_path)
            elif method == "setwindowshook":
                success = self._inject_setwindowshook(pid, dll_path)
            else:
                logger.error(f"Unknown injection method: {method}", module="process_manager")
                return False
            
            if success:
                self.injected_processes.add(pid)
                self.stats['processes_injected'] += 1
                
                # Log audit event
                audit_log.log_event(
                    event_type=AuditEventType.PROCESS_INJECTION.value,
                    severity=AuditSeverity.HIGH.value,
                    user='system',
                    source_ip='localhost',
                    description=f"DLL injected into process: PID {pid}",
                    details={
                        'pid': pid,
                        'dll_path': dll_path,
                        'method': method,
                        'timestamp': datetime.now().isoformat()
                    },
                    resource='process_manager',
                    action='inject_dll'
                )
                
                logger.info(f"DLL injected into process {pid} using {method}", module="process_manager")
            
            return success
            
        except Exception as e:
            logger.error(f"DLL injection error: {e}", module="process_manager")
            return False
    
    def _inject_createremotethread(self, pid: int, dll_path: str) -> bool:
        """Inject using CreateRemoteThread (standard method)"""
        try:
            import ctypes
            from ctypes import wintypes
            
            kernel32 = ctypes.windll.kernel32
            
            # Open process
            PROCESS_ALL_ACCESS = 0x1F0FFF
            process_handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            
            if not process_handle:
                return False
            
            # Allocate memory in target process
            dll_path_bytes = dll_path.encode('utf-8')
            dll_path_size = len(dll_path_bytes) + 1
            
            allocated_memory = kernel32.VirtualAllocEx(
                process_handle,
                None,
                dll_path_size,
                0x3000,  # MEM_COMMIT | MEM_RESERVE
                0x40     # PAGE_EXECUTE_READWRITE
            )
            
            if not allocated_memory:
                kernel32.CloseHandle(process_handle)
                return False
            
            # Write DLL path to allocated memory
            written = wintypes.DWORD(0)
            kernel32.WriteProcessMemory(
                process_handle,
                allocated_memory,
                dll_path_bytes,
                dll_path_size,
                ctypes.byref(written)
            )
            
            # Get LoadLibraryA address
            kernel32_handle = kernel32.GetModuleHandleA(b"kernel32.dll")
            load_library_addr = kernel32.GetProcAddress(kernel32_handle, b"LoadLibraryA")
            
            # Create remote thread
            thread_id = wintypes.DWORD(0)
            thread_handle = kernel32.CreateRemoteThread(
                process_handle,
                None,
                0,
                load_library_addr,
                allocated_memory,
                0,
                ctypes.byref(thread_id)
            )
            
            if not thread_handle:
                kernel32.VirtualFreeEx(process_handle, allocated_memory, 0, 0x8000)  # MEM_RELEASE
                kernel32.CloseHandle(process_handle)
                return False
            
            # Wait for thread to complete
            kernel32.WaitForSingleObject(thread_handle, 5000)
            
            # Cleanup
            kernel32.CloseHandle(thread_handle)
            kernel32.VirtualFreeEx(process_handle, allocated_memory, 0, 0x8000)
            kernel32.CloseHandle(process_handle)
            
            return True
            
        except Exception as e:
            logger.error(f"CreateRemoteThread injection error: {e}", module="process_manager")
            return False
    
    def _inject_queueuserapc(self, pid: int, dll_path: str) -> bool:
        """Inject using QueueUserAPC (requires alertable thread)"""
        # Implementation for APC injection
        logger.warning("APC injection not fully implemented", module="process_manager")
        return False
    
    def _inject_setwindowshook(self, pid: int, dll_path: str) -> bool:
        """Inject using SetWindowsHookEx (requires GUI thread)"""
        # Implementation for hook injection
        logger.warning("Hook injection not fully implemented", module="process_manager")
        return False
    
    def execute_command(self, command: str, wait: bool = True, 
                       shell: bool = True, **kwargs) -> Tuple[bool, str]:
        """Execute a system command"""
        try:
            if shell:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    **kwargs
                )
            else:
                proc = subprocess.Popen(
                    command.split(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    **kwargs
                )
            
            if wait:
                stdout, stderr = proc.communicate()
                return_code = proc.returncode
                
                output = stdout.decode('utf-8', errors='ignore')
                if stderr:
                    output += "\n" + stderr.decode('utf-8', errors='ignore')
                
                success = return_code == 0
                
                # Add to process cache
                with self.process_lock:
                    if proc.pid:
                        # Create minimal ProcessInfo
                        process_info = ProcessInfo(
                            pid=proc.pid,
                            name=command[:50],
                            exe_path=None,
                            cmdline=[command],
                            username='system',
                            cpu_percent=0.0,
                            memory_percent=0.0,
                            memory_rss=0,
                            memory_vms=0,
                            create_time=time.time(),
                            threads=1,
                            state=ProcessState.TERMINATED if wait else ProcessState.RUNNING
                        )
                        self.processes[proc.pid] = process_info
                
                return success, output
            else:
                # Return immediately without waiting
                return True, f"Process started with PID: {proc.pid}"
            
        except Exception as e:
            logger.error(f"Execute command error: {e}", module="process_manager")
            return False, str(e)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system-wide process statistics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1.0)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get process count by state
            process_states = {}
            with self.process_lock:
                for proc in self.processes.values():
                    state = proc.state.value
                    process_states[state] = process_states.get(state, 0) + 1
            
            return {
                'cpu_percent': cpu_percent,
                'memory_total_gb': memory.total / 1024 / 1024 / 1024,
                'memory_used_gb': memory.used / 1024 / 1024 / 1024,
                'memory_percent': memory.percent,
                'disk_total_gb': disk.total / 1024 / 1024 / 1024,
                'disk_used_gb': disk.used / 1024 / 1024 / 1024,
                'disk_percent': disk.percent,
                'process_count': len(self.processes),
                'process_states': process_states,
                'injected_processes': len(self.injected_processes),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Get system stats error: {e}", module="process_manager")
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get process manager statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
            'current_process_count': len(self.processes),
            'monitoring_active': self.running,
            'auto_refresh': self.auto_refresh,
            'privileged_mode': self.privileged_mode,
            'injected_processes_count': len(self.injected_processes)
        }
    
    def export_process_list(self, format: str = 'json', filepath: Optional[str] = None) -> Optional[str]:
        """Export process list"""
        try:
            with self.process_lock:
                processes = [p.to_dict() for p in self.processes.values()]
            
            if format.lower() == 'json':
                output = json.dumps({
                    'processes': processes,
                    'timestamp': datetime.now().isoformat(),
                    'total_processes': len(processes)
                }, indent=2)
            
            elif format.lower() == 'csv':
                import csv
                import io
                
                output_io = io.StringIO()
                writer = csv.writer(output_io)
                
                # Write header
                writer.writerow(['PID', 'Name', 'CPU%', 'Memory%', 'Memory RSS (MB)', 
                               'Username', 'State', 'Threads', 'Create Time'])
                
                # Write data
                for proc in processes:
                    writer.writerow([
                        proc['pid'],
                        proc['name'],
                        proc['cpu_percent'],
                        proc['memory_percent'],
                        proc['memory_rss_mb'],
                        proc['username'],
                        proc['state'],
                        proc['threads'],
                        proc['create_time_iso']
                    ])
                
                output = output_io.getvalue()
            
            elif format.lower() == 'text':
                output_lines = []
                output_lines.append(f"Process List - {len(processes)} processes")
                output_lines.append("=" * 80)
                
                for proc in sorted(processes, key=lambda x: x['memory_rss_mb'], reverse=True)[:50]:
                    output_lines.append(
                        f"{proc['pid']:6d} {proc['name'][:30]:30} "
                        f"{proc['cpu_percent']:5.1f}% {proc['memory_rss_mb']:7.1f}MB "
                        f"{proc['username'][:15]:15} {proc['state']}"
                    )
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported format: {format}", module="process_manager")
                return None
            
            # Write to file if specified
            if filepath:
                with open(filepath, 'w') as f:
                    f.write(output)
                logger.info(f"Process list exported to {filepath}", module="process_manager")
            
            return output
            
        except Exception as e:
            logger.error(f"Export process list error: {e}", module="process_manager")
            return None
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.stop_monitoring()
        except:
            pass

# Global instance
_process_manager = None

def get_process_manager(config: Dict = None) -> ProcessManager:
    """Get or create process manager instance"""
    global _process_manager
    
    if _process_manager is None:
        _process_manager = ProcessManager(config)
    
    return _process_manager

if __name__ == "__main__":
    print("Testing Process Manager...")
    
    # Test configuration
    config = {
        'auto_refresh': True,
        'refresh_interval': 1.0,
        'privileged_mode': False,
        'max_processes': 500
    }
    
    pm = get_process_manager(config)
    
    print("\n1. Getting process list...")
    processes = pm.refresh_process_list()
    print(f"Found {len(processes)} processes")
    
    print("\n2. Getting system stats...")
    system_stats = pm.get_system_stats()
    print(f"CPU: {system_stats.get('cpu_percent')}%")
    print(f"Memory: {system_stats.get('memory_percent')}%")
    print(f"Process count: {system_stats.get('process_count')}")
    
    print("\n3. Finding specific processes...")
    chrome_processes = pm.get_processes_by_name("chrome")
    print(f"Found {len(chrome_processes)} Chrome processes")
    
    if chrome_processes:
        sample_proc = chrome_processes[0]
        print(f"Sample Chrome process: PID {sample_proc.pid}, Memory: {sample_proc.memory_rss / 1024 / 1024:.1f}MB")
    
    print("\n4. Testing command execution...")
    success, output = pm.execute_command("echo 'Process Manager Test'", wait=True)
    print(f"Command success: {success}")
    print(f"Output: {output[:100]}...")
    
    print("\n5. Getting statistics...")
    stats = pm.get_statistics()
    print(f"Total processes scanned: {stats['total_processes_scanned']}")
    print(f"Processes terminated: {stats['processes_terminated']}")
    print(f"Monitoring active: {stats['monitoring_active']}")
    
    print("\n6. Exporting process list...")
    export_data = pm.export_process_list('text')
    if export_data:
        print(export_data[:500] + "..." if len(export_data)500 else export_data)
    
    # Stop monitoring
    pm.stop_monitoring()
    
    print("\n✅ Process Manager tests completed!")
