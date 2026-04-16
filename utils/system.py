#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system.py - System helper with Telegram integration
"""

import os
import sys
import platform
import psutil
import cpuinfo
import GPUtil
import wmi
import winreg
import subprocess
import shutil
import tempfile
import time
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from pathlib import Path

# Import logger
from .logger import get_logger

logger = get_logger()

class SystemManager:
    """Manages system operations with Telegram notifications"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system_info = self.get_system_info()
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Monitoring
        self.monitoring = False
        self.monitor_thread = None
        self.performance_history = []
        
        # Cache
        self.cache = {
            'processes': [],
            'services': [],
            'drives': [],
            'last_update': None
        }
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('system_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.system_chat_id = chat_id
                logger.info("Telegram system bot initialized", module="system")
            except ImportError:
                logger.warning("Telegram module not available", module="system")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="system")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send system notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'system_chat_id'):
            return
        
        try:
            full_message = fb>🖥️ {title}</b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.system_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram system notification sent: {title}", module="system")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="system")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        try:
            info = {
                'platform': {
                    'system': platform.system(),
                    'release': platform.release(),
                    'version': platform.version(),
                    'machine': platform.machine(),
                    'processor': platform.processor(),
                    'architecture': platform.architecture()[0]
                },
                'python': {
                    'version': platform.python_version(),
                    'implementation': platform.python_implementation(),
                    'compiler': platform.python_compiler()
                },
                'host': {
                    'node': platform.node(),
                    'username': os.getlogin() if hasattr(os, 'getlogin') else 'Unknown'
                },
                'cpu': self.get_cpu_info(),
                'memory': self.get_memory_info(),
                'disk': self.get_disk_info(),
                'gpu': self.get_gpu_info(),
                'network': self.get_network_info(),
                'bios': self.get_bios_info() if platform.system() == 'Windows' else {},
                'timestamp': datetime.now().isoformat()
            }
            
            logger.debug("System information collected", module="system")
            return info
            
        except Exception as e:
            logger.error(f"Error getting system info: {e}", module="system")
            return {}
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        try:
            info = cpuinfo.get_cpu_info()
            
            cpu_info = {
                'brand': info.get('brand_raw', 'Unknown'),
                'cores_physical': psutil.cpu_count(logical=False),
                'cores_logical': psutil.cpu_count(logical=True),
                'frequency': {
                    'current': psutil.cpu_freq().current if psutil.cpu_freq() else None,
                    'min': psutil.cpu_freq().min if psutil.cpu_freq() else None,
                    'max': psutil.cpu_freq().max if psutil.cpu_freq() else None
                },
                'architecture': info.get('arch', 'Unknown'),
                'bits': info.get('bits', 64),
                'vendor': info.get('vendor_id_raw', 'Unknown'),
                'flags': info.get('flags', [])[:10]  # First 10 flags
            }
            
            return cpu_info
            
        except Exception as e:
            logger.error(f"Error getting CPU info: {e}", module="system")
            return {}
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        try:
            virtual = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            memory_info = {
                'physical': {
                    'total': virtual.total,
                    'available': virtual.available,
                    'used': virtual.used,
                    'percent': virtual.percent,
                    'free': virtual.free
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent
                }
            }
            
            return memory_info
            
        except Exception as e:
            logger.error(f"Error getting memory info: {e}", module="system")
            return {}
    
    def get_disk_info(self) -> List[Dict[str, Any]]:
        """Get disk information for all partitions"""
        try:
            disks = []
            
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    disk_info = {
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'opts': partition.opts,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                    
                    disks.append(disk_info)
                    
                except PermissionError:
                    continue
                except Exception as e:
                    logger.debug(f"Error getting disk info for {partition.mountpoint}: {e}", module="system")
            
            # Update cache
            self.cache['drives'] = disks
            
            return disks
            
        except Exception as e:
            logger.error(f"Error getting disk info: {e}", module="system")
            return []
    
    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information"""
        try:
            gpus = []
            
            # Try GPUtil for NVIDIA/AMD
            try:
                gpu_list = GPUtil.getGPUs()
                for gpu in gpu_list:
                    gpu_info = {
                        'id': gpu.id,
                        'name': gpu.name,
                        'load': gpu.load * 100,
                        'memory_total': gpu.memoryTotal,
                        'memory_used': gpu.memoryUsed,
                        'memory_free': gpu.memoryFree,
                        'temperature': gpu.temperature,
                        'driver': gpu.driver
                    }
                    gpus.append(gpu_info)
            except:
                pass
            
            # Windows WMI fallback
            if platform.system() == 'Windows' and len(gpus) == 0:
                try:
                    c = wmi.WMI()
                    for gpu in c.Win32_VideoController():
                        gpu_info = {
                            'name': gpu.Name,
                            'adapter_ram': getattr(gpu, 'AdapterRAM', 0),
                            'driver_version': getattr(gpu, 'DriverVersion', 'Unknown'),
                            'video_processor': getattr(gpu, 'VideoProcessor', 'Unknown')
                        }
                        gpus.append(gpu_info)
                except:
                    pass
            
            return gpus
            
        except Exception as e:
            logger.error(f"Error getting GPU info: {e}", module="system")
            return []
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information"""
        try:
            net_io = psutil.net_io_counters()
            net_if = psutil.net_if_addrs()
            net_stats = psutil.net_if_stats()
            
            network_info = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv,
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv,
                'interfaces': {}
            }
            
            for iface, addrs in net_if.items():
                interface_info = {
                    'addresses': [],
                    'stats': {}
                }
                
                for addr in addrs:
                    addr_info = {
                        'family': str(addr.family),
                        'address': addr.address,
                        'netmask': addr.netmask if hasattr(addr, 'netmask') else None,
                        'broadcast': addr.broadcast if hasattr(addr, 'broadcast') else None
                    }
                    interface_info['addresses'].append(addr_info)
                
                if iface in net_stats:
                    stats = net_stats[iface]
                    interface_info['stats'] = {
                        'isup': stats.isup,
                        'duplex': str(stats.duplex),
                        'speed': stats.speed,
                        'mtu': stats.mtu
                    }
                
                network_info['interfaces'][iface] = interface_info
            
            return network_info
            
        except Exception as e:
            logger.error(f"Error getting network info: {e}", module="system")
            return {}
    
    def get_bios_info(self) -> Dict[str, Any]:
        """Get BIOS information (Windows only)"""
        try:
            if platform.system() != 'Windows':
                return {}
            
            c = wmi.WMI()
            bios = c.Win32_BIOS()[0]
            
            bios_info = {
                'manufacturer': bios.Manufacturer,
                'version': bios.Version,
                'serial_number': bios.SerialNumber,
                'release_date': bios.ReleaseDate if hasattr(bios, 'ReleaseDate') else None,
                'smbios_version': bios.SMBIOSBIOSVersion if hasattr(bios, 'SMBIOSBIOSVersion') else None
            }
            
            return bios_info
            
        except Exception as e:
            logger.debug(f"Error getting BIOS info: {e}", module="system")
            return {}
    
    def get_processes(self, filter_str: str = None) -> List[Dict[str, Any]]:
        """Get running processes"""
        try:
            processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 
                                           'memory_percent', 'create_time', 'status']):
                try:
                    proc_info = proc.info
                    proc_info['exe'] = proc.exe() if hasattr(proc, 'exe') else ''
                    proc_info['cmdline'] = proc.cmdline() if hasattr(proc, 'cmdline') else []
                    proc_info['threads'] = proc.num_threads()
                    proc_info['open_files'] = len(proc.open_files()) if hasattr(proc, 'open_files') else 0
                    
                    # Filter if specified
                    if filter_str:
                        if (filter_str.lower() in proc_info['name'].lower() or
                            filter_str in str(proc_info['pid'])):
                            processes.append(proc_info)
                    else:
                        processes.append(proc_info)
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            # Sort by CPU usage
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            
            # Update cache
            self.cache['processes'] = processes
            self.cache['last_update'] = datetime.now().isoformat()
            
            return processes[:100]  # Return top 100
            
        except Exception as e:
            logger.error(f"Error getting processes: {e}", module="system")
            return []
    
    def get_services(self) -> List[Dict[str, Any]]:
        """Get system services"""
        try:
            services = []
            
            if platform.system() == 'Windows':
                # Windows services
                try:
                    c = wmi.WMI()
                    for service in c.Win32_Service():
                        service_info = {
                            'name': service.Name,
                            'display_name': service.DisplayName,
                            'state': service.State,
                            'start_mode': service.StartMode,
                            'path': service.PathName,
                            'pid': service.ProcessId
                        }
                        services.append(service_info)
                except:
                    pass
            else:
                # Linux/Unix services (systemd)
                try:
                    result = subprocess.run(
                        ['systemctl', 'list-units', '--type=service', '--no-pager'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines[1:]:  # Skip header
                            if line.strip():
                                parts = line.split()
                                if len(parts) >= 5:
                                    service_info = {
                                        'name': parts[0],
                                        'load': parts[1],
                                        'active': parts[2],
                                        'sub': parts[3],
                                        'description': ' '.join(parts[4:])
                                    }
                                    services.append(service_info)
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
            
            # Update cache
            self.cache['services'] = services
            
            return services
            
        except Exception as e:
            logger.error(f"Error getting services: {e}", module="system")
            return []
    
    def kill_process(self, pid: int, force: bool = False) -> bool:
        """Kill a process by PID"""
        try:
            proc = psutil.Process(pid)
            
            if force:
                proc.kill()
                method = 'killed'
            else:
                proc.terminate()
                method = 'terminated'
            
            # Wait for process to end
            gone, alive = psutil.wait_procs([proc], timeout=3)
            
            if pid in [p.pid for p in alive]:
                # Force kill if still alive
                proc.kill()
                method = 'force killed'
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Process Killed",
                f"PID: {pid}\n"
                f"Name: {proc.name()}\n"
                f"Method: {method}\n"
                f"User: {proc.username()}"
            )
            
            logger.info(f"Process {pid} ({proc.name()}) {method}", module="system")
            return True
            
        except psutil.NoSuchProcess:
            logger.error(f"Process {pid} not found", module="system")
            return False
        except psutil.AccessDenied:
            logger.error(f"Access denied to process {pid}", module="system")
            return False
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}", module="system")
            return False
    
    def start_process(self, command: str, args: List[str] = None, 
                     working_dir: str = None) -> Tuple[bool, int]:
        """Start a new process"""
        try:
            cmd_list = [command]
            if args:
                cmd_list.extend(args)
            
            process = subprocess.Popen(
                cmd_list,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True if platform.system() == 'Windows' else False
            )
            
            pid = process.pid
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Process Started",
                f"Command: {command}\n"
                f"Args: {args}\n"
                f"PID: {pid}\n"
                f"Working Dir: {working_dir or 'Current'}"
            )
            
            logger.info(f"Process started: {command} (PID: {pid})", module="system")
            return True, pid
            
        except Exception as e:
            logger.error(f"Error starting process: {e}", module="system")
            return False, -1
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'percent': psutil.cpu_percent(interval=1),
                    'percent_per_core': psutil.cpu_percent(interval=1, percpu=True),
                    'frequency': psutil.cpu_freq().current if psutil.cpu_freq() else None
                },
                'memory': dict(psutil.virtual_memory()._asdict()),
                'disk': {},
                'network': dict(psutil.net_io_counters()._asdict()),
                'sensors': self.get_sensor_data()
            }
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                metrics['disk']['io'] = dict(disk_io._asdict())
            
            # Per-disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    metrics['disk'][partition.mountpoint] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                except:
                    continue
            
            # Add to history (keep last 100 entries)
            self.performance_history.append(metrics)
            if len(self.performance_history) > 100:
                self.performance_history.pop(0)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}", module="system")
            return {}
    
    def get_sensor_data(self) -> Dict[str, Any]:
        """Get sensor data (temperatures, fans, battery)"""
        try:
            sensors = {}
            
            # Temperatures
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    sensors['temperatures'] = {}
                    for name, entries in temps.items():
                        sensors['temperatures'][name] = [
                            {'label': entry.label or f'Sensor {i}', 
                             'current': entry.current,
                             'high': entry.high,
                             'critical': entry.critical}
                            for i, entry in enumerate(entries)
                        ]
            except AttributeError:
                pass  # sensors_temperatures not available
            
            # Fans
            try:
                fans = psutil.sensors_fans()
                if fans:
                    sensors['fans'] = {}
                    for name, entries in fans.items():
                        sensors['fans'][name] = [
                            {'label': entry.label or f'Fan {i}', 
                             'current': entry.current}
                            for i, entry in enumerate(entries)
                        ]
            except AttributeError:
                pass  # sensors_fans not available
            
            # Battery
            try:
                battery = psutil.sensors_battery()
                if battery:
                    sensors['battery'] = {
                        'percent': battery.percent,
                        'secsleft': battery.secsleft,
                        'power_plugged': battery.power_plugged
                    }
            except AttributeError:
                pass  # sensors_battery not available
            
            return sensors
            
        except Exception as e:
            logger.debug(f"Error getting sensor data: {e}", module="system")
            return {}
    
    def start_monitoring(self, interval: int = 60):
        """Start system monitoring"""
        if self.monitoring:
            logger.warning("Monitoring already running", module="system")
            return
        
        self.monitoring = True
        
        def monitor_loop():
            alert_thresholds = {
                'cpu': 90,  # 90% CPU usage
                'memory': 90,  # 90% memory usage
                'disk': 90,  # 90% disk usage
                'temperature': 80  # 80°C
            }
            
            last_alert_time = {}
            
            while self.monitoring:
                try:
                    metrics = self.get_performance_metrics()
                    
                    # Check for alerts
                    current_time = time.time()
                    
                    # CPU alert
                    if metrics.get('cpu', {}).get('percent', 0) > alert_thresholds['cpu']:
                        if current_time - last_alert_time.get('cpu', 0) > 300:  # 5 minutes cooldown
                            self.send_telegram_notification(
                                "⚠️ High CPU Usage",
                                f"CPU: {metrics['cpu']['percent']}%\n"
                                f"Threshold: {alert_thresholds['cpu']}%"
                            )
                            last_alert_time['cpu'] = current_time
                    
                    # Memory alert
                    if metrics.get('memory', {}).get('percent', 0) > alert_thresholds['memory']:
                        if current_time - last_alert_time.get('memory', 0) > 300:
                            self.send_telegram_notification(
                                "⚠️ High Memory Usage",
                                f"Memory: {metrics['memory']['percent']}%\n"
                                f"Threshold: {alert_thresholds['memory']}%"
                            )
                            last_alert_time['memory'] = current_time
                    
                    # Disk alert (check each partition)
                    for mountpoint, disk_info in metrics.get('disk', {}).items():
                        if mountpoint != 'io' and disk_info.get('percent', 0) > alert_thresholds['disk']:
                            if current_time - last_alert_time.get(f'disk_{mountpoint}', 0) > 600:  # 10 minutes
                                self.send_telegram_notification(
                                    "⚠️ High Disk Usage",
                                    f"Disk: {mountpoint}\n"
                                    f"Usage: {disk_info['percent']}%\n"
                                    f"Threshold: {alert_thresholds['disk']}%"
                                )
                                last_alert_time[f'disk_{mountpoint}'] = current_time
                    
                    # Temperature alert
                    temps = metrics.get('sensors', {}).get('temperatures', {})
                    for sensor_name, sensor_data in temps.items():
                        for sensor in sensor_data:
                            if sensor.get('current', 0) > alert_thresholds['temperature']:
                                if current_time - last_alert_time.get(f'temp_{sensor_name}', 0) > 300:
                                    self.send_telegram_notification(
                                        "🌡️ High Temperature",
                                        f"Sensor: {sensor_name} - {sensor.get('label', '')}\n"
                                        f"Temperature: {sensor['current']}°C\n"
                                        f"Threshold: {alert_thresholds['temperature']}°C"
                                    )
                                    last_alert_time[f'temp_{sensor_name}'] = current_time
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Monitoring error: {e}", module="system")
                    time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info(f"System monitoring started (interval: {interval}s)", module="system")
        self.send_telegram_notification(
            "System Monitoring Started",
            f"Monitoring interval: {interval} seconds"
        )
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("System monitoring stopped", module="system")
        self.send_telegram_notification(
            "System Monitoring Stopped",
            "Monitoring has been stopped"
        )
    
    def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute system command and return result"""
        try:
            logger.info(f"Executing command: {command}", module="system")
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return_code = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                return_code = -1
            
            result = {
                'success': return_code == 0,
                'return_code': return_code,
                'stdout': stdout,
                'stderr': stderr,
                'command': command
            }
            
            # Send Telegram notification for important commands
            if len(stdout) > 1000 or return_code != 0:
                self.send_telegram_notification(
                    "Command Executed",
                    f"Command: {command}\n"
                    f"Return Code: {return_code}\n"
                    f"Output length: {len(stdout)} chars"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing command: {e}", module="system")
            return {
                'success': False,
                'error': str(e),
                'command': command
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get system manager status"""
        return {
            'system': self.system_info.get('platform', {}).get('system', 'Unknown'),
            'hostname': self.system_info.get('host', {}).get('node', 'Unknown'),
            'cpu_cores': self.system_info.get('cpu', {}).get('cores_logical', 0),
            'memory_total': self.system_info.get('memory', {}).get('physical', {}).get('total', 0),
            'disk_count': len(self.cache['drives']),
            'process_count': len(self.cache['processes']),
            'service_count': len(self.cache['services']),
            'monitoring': self.monitoring,
            'performance_history': len(self.performance_history)
        }

# Global instance
_system_manager = None

def get_system_manager(config: Dict = None) -> SystemManager:
    """Get or create system manager instance"""
    global _system_manager
    
    if _system_manager is None:
        _system_manager = SystemManager(config)
    
    return _system_manager

if __name__ == "__main__":
    # Test the system manager
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'system_chat_id': 123456789
        }
    }
    
    manager = get_system_manager(config)
    
    # Test basic functions
    print(f"System: {manager.system_info.get('platform', {}).get('system', 'Unknown')}")
    print(f"CPU: {manager.system_info.get('cpu', {}).get('brand', 'Unknown')}")
    print(f"Memory: {manager.system_info.get('memory', {}).get('physical', {}).get('total', 0) / (1024**3):.2f} GB")
    
    # Test processes
    processes = manager.get_processes()
    print(f"Running processes: {len(processes)}")
    
    # Test performance metrics
    metrics = manager.get_performance_metrics()
    print(f"CPU Usage: {metrics.get('cpu', {}).get('percent', 0)}%")
    
    # Show status
    status = manager.get_status()
    print(f"\n🖥️ System Manager Status: {status}")
    
    print("\n✅ System tests completed!")
