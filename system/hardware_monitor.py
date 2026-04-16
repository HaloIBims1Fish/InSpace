#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hardware_monitor.py - Advanced Hardware Monitoring and Control
"""

import os
import sys
import platform
import subprocess
import psutil
import GPUtil
import time
import threading
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import warnings

# Import utilities
from ..utils.logger import get_logger
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class HardwareType(Enum):
    """Hardware component types"""
    CPU = "cpu"
    GPU = "gpu"
    RAM = "ram"
    DISK = "disk"
    NETWORK = "network"
    SENSOR = "sensor"
    BATTERY = "battery"
    MOTHERBOARD = "motherboard"
    BIOS = "bios"
    USB = "usb"
    PCI = "pci"

@dataclass
class HardwareComponent:
    """Hardware component information"""
    type: HardwareType
    name: str
    model: Optional[str] = None
    vendor: Optional[str] = None
    serial: Optional[str] = None
    capacity: Optional[int] = None  # Bytes for storage, MB for RAM
    clock_speed: Optional[float] = None  # MHz/GHz
    temperature: Optional[float] = None  # Celsius
    usage: Optional[float] = None  # Percentage
    power_usage: Optional[float] = None  # Watts
    status: str = "unknown"
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['type'] = self.type.value
        
        # Convert capacity to human readable
        if self.capacity:
            data['capacity_human'] = self._human_size(self.capacity)
        
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
class HardwareAlert:
    """Hardware alert/event"""
    component: HardwareComponent
    alert_type: str  # 'temperature', 'usage', 'failure', 'threshold'
    severity: str  # 'info', 'warning', 'critical'
    message: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['component'] = self.component.to_dict()
        data['timestamp'] = self.timestamp.isoformat()
        return data

class HardwareMonitor:
    """Advanced Hardware Monitoring and Control"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.poll_interval = self.config.get('poll_interval', 5.0)  # seconds
        self.alerts_enabled = self.config.get('alerts_enabled', True)
        self.logging_enabled = self.config.get('logging_enabled', True)
        self.max_history = self.config.get('max_history', 1000)
        
        # Alert thresholds
        self.thresholds = {
            'cpu_temperature': self.config.get('cpu_temperature_threshold', 85.0),  # °C
            'cpu_usage': self.config.get('cpu_usage_threshold', 90.0),  # %
            'gpu_temperature': self.config.get('gpu_temperature_threshold', 90.0),  # °C
            'gpu_usage': self.config.get('gpu_usage_threshold', 95.0),  # %
            'ram_usage': self.config.get('ram_usage_threshold', 90.0),  # %
            'disk_usage': self.config.get('disk_usage_threshold', 90.0),  # %
            'disk_temperature': self.config.get('disk_temperature_threshold', 50.0),  # °C
        }
        
        # Hardware cache
        self.hardware_cache = {}
        self.history = []
        self.alerts = []
        
        # Monitoring thread
        self.monitoring = False
        self.monitor_thread = None
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'polls_performed': 0,
            'alerts_triggered': 0,
            'components_found': 0,
            'start_time': datetime.now()
        }
        
        # Initialize hardware detection
        self._detect_hardware()
        
        logger.info("Hardware Monitor initialized", module="hardware_monitor")
    
    def _detect_hardware(self):
        """Detect available hardware components"""
        components = []
        
        try:
            # CPU detection
            cpu_info = self._get_cpu_info()
            if cpu_info:
                components.append(cpu_info)
            
            # RAM detection
            ram_info = self._get_ram_info()
            if ram_info:
                components.append(ram_info)
            
            # GPU detection
            gpu_info = self._get_gpu_info()
            if gpu_info:
                components.extend(gpu_info)
            
            # Disk detection
            disk_info = self._get_disk_info()
            if disk_info:
                components.extend(disk_info)
            
            # Network interfaces
            network_info = self._get_network_info()
            if network_info:
                components.extend(network_info)
            
            # Sensors
            sensor_info = self._get_sensor_info()
            if sensor_info:
                components.extend(sensor_info)
            
            # Battery (if available)
            battery_info = self._get_battery_info()
            if battery_info:
                components.append(battery_info)
            
            # System information
            system_info = self._get_system_info()
            if system_info:
                components.append(system_info)
            
        except Exception as e:
            logger.error(f"Hardware detection error: {e}", module="hardware_monitor")
        
        with self.lock:
            self.hardware_cache = {comp.name: comp for comp in components}
            self.stats['components_found'] = len(components)
        
        logger.info(f"Detected {len(components)} hardware components", module="hardware_monitor")
    
    def _get_cpu_info(self) -> Optional[HardwareComponent]:
        """Get CPU information"""
        try:
            cpu_count = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            
            # Try to get more detailed info
            cpu_model = "Unknown"
            cpu_vendor = "Unknown"
            
            if platform.system() == 'Linux':
                try:
                    with open('/proc/cpuinfo', 'r') as f:
                        for line in f:
                            if 'model name' in line:
                                cpu_model = line.split(':')[1].strip()
                                break
                            elif 'vendor_id' in line:
                                cpu_vendor = line.split(':')[1].strip()
                except:
                    pass
            
            elif platform.system() == 'Windows':
                try:
                    import wmi
                    c = wmi.WMI()
                    for processor in c.Win32_Processor():
                        cpu_model = processor.Name
                        cpu_vendor = processor.Manufacturer
                        break
                except:
                    pass
            
            return HardwareComponent(
                type=HardwareType.CPU,
                name="CPU",
                model=cpu_model,
                vendor=cpu_vendor,
                capacity=None,
                clock_speed=cpu_freq.max if cpu_freq else None,
                temperature=None,  # Will be updated by sensors
                usage=None,  # Will be updated during polling
                power_usage=None,
                status="operational",
                driver_version=None
            )
            
        except Exception as e:
            logger.error(f"CPU info error: {e}", module="hardware_monitor")
            return None
    
    def _get_ram_info(self) -> Optional[HardwareComponent]:
        """Get RAM information"""
        try:
            virtual_memory = psutil.virtual_memory()
            
            ram_model = "System RAM"
            ram_vendor = "Unknown"
            
            if platform.system() == 'Linux':
                try:
                    # Try to get RAM info from dmidecode
                    result = subprocess.run(['sudo', 'dmidecode', '--type', 'memory'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Manufacturer:' in line:
                                ram_vendor = line.split(':')[1].strip()
                            elif 'Part Number:' in line:
                                ram_model = line.split(':')[1].strip()
                except:
                    pass
            
            return HardwareComponent(
                type=HardwareType.RAM,
                name="System RAM",
                model=ram_model,
                vendor=ram_vendor,
                capacity=virtual_memory.total,
                clock_speed=None,
                temperature=None,
                usage=virtual_memory.percent,
                power_usage=None,
                status="operational",
                driver_version=None
            )
            
        except Exception as e:
            logger.error(f"RAM info error: {e}", module="hardware_monitor")
            return None
    
    def _get_gpu_info(self) -> List[HardwareComponent]:
        """Get GPU information"""
        gpus = []
        
        try:
            # Try using GPUtil for NVIDIA/AMD GPUs
            try:
                gpu_list = GPUtil.getGPUs()
                for i, gpu in enumerate(gpu_list):
                    gpu_component = HardwareComponent(
                        type=HardwareType.GPU,
                        name=f"GPU {i}",
                        model=gpu.name,
                        vendor="NVIDIA" if 'nvidia' in gpu.name.lower() else "AMD",
                        serial=None,
                        capacity=gpu.memoryTotal * 1024 * 1024,  # Convert MB to bytes
                        clock_speed=None,
                        temperature=gpu.temperature,
                        usage=gpu.load * 100,  # Convert to percentage
                        power_usage=gpu.powerDraw if hasattr(gpu, 'powerDraw') else None,
                        status="operational",
                        driver_version=gpu.driver if hasattr(gpu, 'driver') else None
                    )
                    gpus.append(gpu_component)
            except:
                pass
            
            # Try using platform-specific methods
            if not gpus and platform.system() == 'Windows':
                try:
                    import wmi
                    c = wmi.WMI()
                    for gpu in c.Win32_VideoController():
                        gpu_component = HardwareComponent(
                            type=HardwareType.GPU,
                            name=gpu.Name,
                            model=gpu.Name,
                            vendor=gpu.AdapterCompatibility if hasattr(gpu, 'AdapterCompatibility') else "Unknown",
                            serial=None,
                            capacity=gpu.AdapterRAM if hasattr(gpu, 'AdapterRAM') else None,
                            clock_speed=None,
                            temperature=None,
                            usage=None,
                            power_usage=None,
                            status="operational",
                            driver_version=gpu.DriverVersion if hasattr(gpu, 'DriverVersion') else None
                        )
                        gpus.append(gpu_component)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"GPU info error: {e}", module="hardware_monitor")
        
        return gpus
    
    def _get_disk_info(self) -> List[HardwareComponent]:
        """Get disk information"""
        disks = []
        
        try:
            disk_partitions = psutil.disk_partitions(all=False)
            
            for partition in disk_partitions:
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    disk_model = "Unknown"
                    disk_vendor = "Unknown"
                    disk_serial = None
                    disk_temperature = None
                    
                    # Try to get more info on Linux
                    if platform.system() == 'Linux':
                        try:
                            # Get disk model from sysfs
                            device = partition.device.replace('/dev/', '')
                            if device.startswith('sd') or device.startswith('nvme'):
                                model_path = f'/sys/block/{device}/device/model'
                                if os.path.exists(model_path):
                                    with open(model_path, 'r') as f:
                                        disk_model = f.read().strip()
                            
                            # Get disk temperature with hddtemp or smartctl
                            try:
                                result = subprocess.run(['sudo', 'smartctl', '-a', partition.device], 
                                                      capture_output=True, text=True, timeout=10)
                                if result.returncode == 0:
                                    for line in result.stdout.split('\n'):
                                        if 'Temperature_Celsius' in line:
                                            parts = line.split()
                                            if len(parts) > 9:
                                                disk_temperature = float(parts[9])
                                                break
                            except:
                                pass
                        except:
                            pass
                    
                    disk_component = HardwareComponent(
                        type=HardwareType.DISK,
                        name=partition.device,
                        model=disk_model,
                        vendor=disk_vendor,
                        serial=disk_serial,
                        capacity=usage.total,
                        clock_speed=None,
                        temperature=disk_temperature,
                        usage=usage.percent,
                        power_usage=None,
                        status="operational",
                        driver_version=None
                    )
                    disks.append(disk_component)
                    
                except Exception as e:
                    logger.debug(f"Disk partition error {partition.device}: {e}", module="hardware_monitor")
                    continue
        
        except Exception as e:
            logger.error(f"Disk info error: {e}", module="hardware_monitor")
        
        return disks
    
    def _get_network_info(self) -> List[HardwareComponent]:
        """Get network interface information"""
        interfaces = []
        
        try:
            net_io = psutil.net_io_counters(pernic=True)
            net_addrs = psutil.net_if_addrs()
            
            for iface_name in net_io.keys():
                try:
                    # Get interface addresses
                    addresses = []
                    if iface_name in net_addrs:
                        for addr in net_addrs[iface_name]:
                            addresses.append(f"{addr.family.name}: {addr.address}")
                    
                    # Get interface stats
                    iface_stats = psutil.net_if_stats().get(iface_name, None)
                    
                    interface_component = HardwareComponent(
                        type=HardwareType.NETWORK,
                        name=iface_name,
                        model="Network Interface",
                        vendor="Unknown",
                        serial=None,
                        capacity=None,
                        clock_speed=None,
                        temperature=None,
                        usage=None,
                        power_usage=None,
                        status="up" if iface_stats and iface_stats.isup else "down",
                        driver_version=None
                    )
                    interfaces.append(interface_component)
                    
                except Exception as e:
                    logger.debug(f"Network interface error {iface_name}: {e}", module="hardware_monitor")
                    continue
        
        except Exception as e:
            logger.error(f"Network info error: {e}", module="hardware_monitor")
        
        return interfaces
    
    def _get_sensor_info(self) -> List[HardwareComponent]:
        """Get sensor information"""
        sensors = []
        
        try:
            # Try using psutil sensors
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:
                    for sensor_name, entries in temps.items():
                        for entry in entries:
                            sensor_component = HardwareComponent(
                                type=HardwareType.SENSOR,
                                name=f"{sensor_name} - {entry.label or 'Temperature'}",
                                model="Temperature Sensor",
                                vendor="System",
                                serial=None,
                                capacity=None,
                                clock_speed=None,
                                temperature=entry.current,
                                usage=None,
                                power_usage=None,
                                status="operational",
                                driver_version=None
                            )
                            sensors.append(sensor_component)
            
            # Try using platform-specific methods
            if platform.system() == 'Linux':
                try:
                    # Check lm-sensors
                    result = subprocess.run(['sensors'], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if ':' in line and '°C' in line:
                                parts = line.split(':')
                                sensor_name = parts[0].strip()
                                temp_str = parts[1].strip()
                                
                                # Extract temperature
                                temp_match = re.search(r'([+-]?\d+\.?\d*)°C', temp_str)
                                if temp_match:
                                    temperature = float(temp_match.group(1))
                                    
                                    sensor_component = HardwareComponent(
                                        type=HardwareType.SENSOR,
                                        name=sensor_name,
                                        model="Temperature Sensor",
                                        vendor="System",
                                        serial=None,
                                        capacity=None,
                                        clock_speed=None,
                                        temperature=temperature,
                                        usage=None,
                                        power_usage=None,
                                        status="operational",
                                        driver_version=None
                                    )
                                    sensors.append(sensor_component)
                except:
                    pass
        
        except Exception as e:
            logger.error(f"Sensor info error: {e}", module="hardware_monitor")
        
        return sensors
    
    def _get_battery_info(self) -> Optional[HardwareComponent]:
        """Get battery information"""
        try:
            if hasattr(psutil, 'sensors_battery'):
                battery = psutil.sensors_battery()
                if battery:
                    return HardwareComponent(
                        type=HardwareType.BATTERY,
                        name="System Battery",
                        model="Battery",
                        vendor="System",
                        serial=None,
                        capacity=None,
                        clock_speed=None,
                        temperature=None,
                        usage=battery.percent,
                        power_usage=None,
                        status="charging" if battery.power_plugged else "discharging",
                        driver_version=None
                    )
        
        except Exception as e:
            logger.error(f"Battery info error: {e}", module="hardware_monitor")
        
        return None
    
    def _get_system_info(self) -> Optional[HardwareComponent]:
        """Get system/motherboard information"""
        try:
            system_model = "Unknown"
            system_vendor = "Unknown"
            bios_version = "Unknown"
            
            if platform.system() == 'Linux':
                try:
                    # Get system info from dmidecode
                    result = subprocess.run(['sudo', 'dmidecode', '-t', 'system'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Product Name:' in line:
                                system_model = line.split(':')[1].strip()
                            elif 'Manufacturer:' in line:
                                system_vendor = line.split(':')[1].strip()
                    
                    # Get BIOS info
                    result = subprocess.run(['sudo', 'dmidecode', '-t', 'bios'], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'Version:' in line:
                                bios_version = line.split(':')[1].strip()
                                break
                except:
                    pass
            
            elif platform.system() == 'Windows':
                try:
                    import wmi
                    c = wmi.WMI()
                    
                    # Get system info
                    for system in c.Win32_ComputerSystem():
                        system_model = system.Model
                        system_vendor = system.Manufacturer
                    
                    # Get BIOS info
                    for bios in c.Win32_BIOS():
                        bios_version = bios.Version
                        break
                except:
                    pass
            
            return HardwareComponent(
                type=HardwareType.MOTHERBOARD,
                name="System Board",
                model=system_model,
                vendor=system_vendor,
                serial=None,
                capacity=None,
                clock_speed=None,
                temperature=None,
                usage=None,
                power_usage=None,
                status="operational",
                driver_version=bios_version,
                firmware_version=bios_version
            )
            
        except Exception as e:
            logger.error(f"System info error: {e}", module="hardware_monitor")
            return None
    
    def poll_hardware(self) -> Dict[str, HardwareComponent]:
        """Poll current hardware status"""
        try:
            current_components = {}
            
            # Update CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=False)
            if 'CPU' in self.hardware_cache:
                cpu_component = self.hardware_cache['CPU']
                cpu_component.usage = cpu_percent
                current_components['CPU'] = cpu_component
            
            # Update RAM usage
            virtual_memory = psutil.virtual_memory()
            if 'System RAM' in self.hardware_cache:
                ram_component = self.hardware_cache['System RAM']
                ram_component.usage = virtual_memory.percent
                current_components['System RAM'] = ram_component
            
            # Update GPU usage (if available)
            try:
                gpu_list = GPUtil.getGPUs()
                for i, gpu in enumerate(gpu_list):
                    gpu_name = f"GPU {i}"
                    if gpu_name in self.hardware_cache:
                        gpu_component = self.hardware_cache[gpu_name]
                        gpu_component.temperature = gpu.temperature
                        gpu_component.usage = gpu.load * 100
                        if hasattr(gpu, 'powerDraw'):
                            gpu_component.power_usage = gpu.powerDraw
                        current_components[gpu_name] = gpu_component
            except:
                pass
            
            # Update disk usage
            disk_partitions = psutil.disk_partitions(all=False)
            for partition in disk_partitions:
                if partition.device in self.hardware_cache:
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disk_component = self.hardware_cache[partition.device]
                        disk_component.usage = usage.percent
                        current_components[partition.device] = disk_component
                    except:
                        pass
            
            # Update network interfaces
            net_io = psutil.net_io_counters(pernic=True)
            for iface_name in net_io.keys():
                if iface_name in self.hardware_cache:
                    # Network interfaces don't have usage percentage in this context
                    current_components[iface_name] = self.hardware_cache[iface_name]
            
            # Update sensors
            if hasattr(psutil, 'sensors_temperatures'):
                temps = psutil.sensors_temperatures()
                if temps:
                    for sensor_name, entries in temps.items():
                        for entry in entries:
                            sensor_key = f"{sensor_name} - {entry.label or 'Temperature'}"
                            if sensor_key in self.hardware_cache:
                                sensor_component = self.hardware_cache[sensor_key]
                                sensor_component.temperature = entry.current
                                current_components[sensor_key] = sensor_component
            
            # Update battery
            if hasattr(psutil, 'sensors_battery'):
                battery = psutil.sensors_battery()
                if battery and 'System Battery' in self.hardware_cache:
                    battery_component = self.hardware_cache['System Battery']
                    battery_component.usage = battery.percent
                    battery_component.status = "charging" if battery.power_plugged else "discharging"
                    current_components['System Battery'] = battery_component
            
            # Check for alerts
            if self.alerts_enabled:
                self._check_alerts(current_components)
            
            # Update history
            with self.lock:
                self.history.append({
                    'timestamp': datetime.now(),
                    'components': {k: v.to_dict() for k, v in current_components.items()}
                })
                
                # Trim history if too long
                if len(self.history) > self.max_history:
                    self.history = self.history[-self.max_history:]
                
                self.stats['polls_performed'] += 1
            
            return current_components
            
        except Exception as e:
            logger.error(f"Hardware poll error: {e}", module="hardware_monitor")
            return {}
    
    def _check_alerts(self, components: Dict[str, HardwareComponent]):
        """Check for hardware alerts based on thresholds"""
        try:
            for component in components.values():
                alerts = []
                
                # Check temperature thresholds
                if component.temperature is not None:
                    if component.type == HardwareType.CPU:
                        if component.temperature > self.thresholds['cpu_temperature']:
                            alerts.append(('temperature', 'critical', 
                                         f"CPU temperature critical: {component.temperature}°C"))
                        elif component.temperature > self.thresholds['cpu_temperature'] - 10:
                            alerts.append(('temperature', 'warning',
                                         f"CPU temperature high: {component.temperature}°C"))
                    
                    elif component.type == HardwareType.GPU:
                        if component.temperature > self.thresholds['gpu_temperature']:
                            alerts.append(('temperature', 'critical',
                                         f"GPU temperature critical: {component.temperature}°C"))
                        elif component.temperature > self.thresholds['gpu_temperature'] - 10:
                            alerts.append(('temperature', 'warning',
                                         f"GPU temperature high: {component.temperature}°C"))
                    
                    elif component.type == HardwareType.DISK:
                        if component.temperature is not None and component.temperature > self.thresholds['disk_temperature']:
                            alerts.append(('temperature', 'warning',
                                         f"Disk temperature high: {component.temperature}°C"))
                
                # Check usage thresholds
                if component.usage is not None:
                    if component.type == HardwareType.CPU:
                        if component.usage > self.thresholds['cpu_usage']:
                            alerts.append(('usage', 'critical',
                                         f"CPU usage critical: {component.usage}%"))
                        elif component.usage > self.thresholds['cpu_usage'] - 10:
                            alerts.append(('usage', 'warning',
                                         f"CPU usage high: {component.usage}%"))
                    
                    elif component.type == HardwareType.GPU:
                        if component.usage > self.thresholds['gpu_usage']:
                            alerts.append(('usage', 'critical',
                                         f"GPU usage critical: {component.usage}%"))
                        elif component.usage > self.thresholds['gpu_usage'] - 10:
                            alerts.append(('usage', 'warning',
                                         f"GPU usage high: {component.usage}%"))
                    
                    elif component.type == HardwareType.RAM:
                        if component.usage > self.thresholds['ram_usage']:
                            alerts.append(('usage', 'critical',
                                         f"RAM usage critical: {component.usage}%"))
                        elif component.usage > self.thresholds['ram_usage'] - 10:
                            alerts.append(('usage', 'warning',
                                         f"RAM usage high: {component.usage}%"))
                    
                    elif component.type == HardwareType.DISK:
                        if component.usage > self.thresholds['disk_usage']:
                            alerts.append(('usage', 'critical',
                                         f"Disk usage critical: {component.usage}%"))
                        elif component.usage > self.thresholds['disk_usage'] - 10:
                            alerts.append(('usage', 'warning',
                                         f"Disk usage high: {component.usage}%"))
                
                # Create alert objects
                for alert_type, severity, message in alerts:
                    alert = HardwareAlert(
                        component=component,
                        alert_type=alert_type,
                        severity=severity,
                        message=message,
                        value=component.temperature if 'temperature' in alert_type else component.usage,
                        threshold=self.thresholds.get(f'{component.type.value}_{alert_type}', None)
                    )
                    
                    with self.lock:
                        self.alerts.append(alert)
                        self.stats['alerts_triggered'] += 1
                    
                    # Log alert
                    if self.logging_enabled:
                        logger.warning(f"Hardware alert: {message}", module="hardware_monitor")
                    
                    # Send to audit log
                    audit_log.log_event(
                        event_type=AuditEventType.HARDWARE_ALERT.value,
                        severity=getattr(AuditSeverity, severity.upper()).value,
                        user='system',
                        source_ip='localhost',
                        description=message,
                        details=alert.to_dict(),
                        resource='hardware_monitor',
                        action='hardware_alert'
                    )
        
        except Exception as e:
            logger.error(f"Alert check error: {e}", module="hardware_monitor")
    
    def start_monitoring(self):
        """Start continuous hardware monitoring"""
        if self.monitoring:
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    self.poll_hardware()
                    time.sleep(self.poll_interval)
                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}", module="hardware_monitor")
                    time.sleep(self.poll_interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("Hardware monitoring started", module="hardware_monitor")
    
    def stop_monitoring(self):
        """Stop hardware monitoring"""
        self.monitoring = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Hardware monitoring stopped", module="hardware_monitor")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current hardware status"""
        components = self.poll_hardware()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'components': {k: v.to_dict() for k, v in components.items()},
            'stats': self.get_statistics()
        }
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get monitoring history"""
        with self.lock:
            history = self.history[-limit:] if limit else self.history.copy()
        
        return [
            {
                'timestamp': entry['timestamp'].isoformat(),
                'components': entry['components']
            }
            for entry in history
        ]
    
    def get_alerts(self, limit: int = 50, severity: str = None) -> List[Dict[str, Any]]:
        """Get hardware alerts"""
        with self.lock:
            alerts = self.alerts.copy()
        
        # Filter by severity if specified
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        # Limit results
        alerts = alerts[-limit:] if limit else alerts
        
        return [alert.to_dict() for alert in alerts]
    
    def clear_alerts(self):
        """Clear all alerts"""
        with self.lock:
            self.alerts.clear()
        
        logger.info("Hardware alerts cleared", module="hardware_monitor")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get hardware monitor statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        with self.lock:
            return {
                **self.stats,
                'uptime_seconds': uptime,
                'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
                'monitoring_active': self.monitoring,
                'poll_interval': self.poll_interval,
                'alerts_enabled': self.alerts_enabled,
                'current_alerts': len(self.alerts),
                'history_size': len(self.history),
                'components_monitored': len(self.hardware_cache),
                'thresholds': self.thresholds
            }
    
    def export_report(self, format: str = 'json', output_file: str = None) -> Optional[str]:
        """Export hardware report"""
        try:
            data = {
                'system_info': {
                    'platform': platform.system(),
                    'platform_version': platform.version(),
                    'architecture': platform.machine(),
                    'processor': platform.processor(),
                    'python_version': platform.python_version()
                },
                'hardware_components': [c.to_dict() for c in self.hardware_cache.values()],
                'current_status': self.get_current_status(),
                'statistics': self.get_statistics(),
                'recent_alerts': self.get_alerts(limit=20),
                'timestamp': datetime.now().isoformat()
            }
            
            if format.lower() == 'json':
                output = json.dumps(data, indent=2)
            
            elif format.lower() == 'text':
                output_lines = []
                output_lines.append("HARDWARE MONITOR REPORT")
                output_lines.append("=" * 80)
                output_lines.append(f"Generated: {datetime.now().isoformat()}")
                output_lines.append(f"Platform: {platform.system()} {platform.version()}")
                output_lines.append(f"Monitoring Uptime: {self.get_statistics()['uptime_human']}")
                output_lines.append("")
                
                output_lines.append("HARDWARE COMPONENTS:")
                output_lines.append("-" * 40)
                for component in self.hardware_cache.values():
                    output_lines.append(f"{component.type.value.upper()}: {component.name}")
                    if component.model and component.model != 'Unknown':
                        output_lines.append(f"  Model: {component.model}")
                    if component.vendor and component.vendor != 'Unknown':
                        output_lines.append(f"  Vendor: {component.vendor}")
                    if component.capacity:
                        output_lines.append(f"  Capacity: {HardwareComponent._human_size(component.capacity)}")
                    if component.temperature is not None:
                        output_lines.append(f"  Temperature: {component.temperature}°C")
                    if component.usage is not None:
                        output_lines.append(f"  Usage: {component.usage}%")
                    output_lines.append("")
                
                output_lines.append("CURRENT ALERTS:")
                output_lines.append("-" * 40)
                alerts = self.get_alerts(limit=10)
                if alerts:
                    for alert in alerts:
                        output_lines.append(f"[{alert['severity'].upper()}] {alert['message']}")
                        output_lines.append(f"  Component: {alert['component']['name']}")
                        output_lines.append(f"  Time: {alert['timestamp']}")
                        output_lines.append("")
                else:
                    output_lines.append("No active alerts")
                    output_lines.append("")
                
                output_lines.append("STATISTICS:")
                output_lines.append("-" * 40)
                stats = self.get_statistics()
                output_lines.append(f"Polls Performed: {stats['polls_performed']}")
                output_lines.append(f"Alerts Triggered: {stats['alerts_triggered']}")
                output_lines.append(f"Components Found: {stats['components_found']}")
                output_lines.append(f"Monitoring Active: {stats['monitoring_active']}")
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported format: {format}", module="hardware_monitor")
                return None
            
            # Write to file if specified
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(output)
                
                logger.info(f"Hardware report exported to {output_file}", module="hardware_monitor")
            
            return output
            
        except Exception as e:
            logger.error(f"Export report error: {e}", module="hardware_monitor")
            return None
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.stop_monitoring()
        except:
            pass

# Global instance
_hardware_monitor = None

def get_hardware_monitor(config: Dict = None) -> HardwareMonitor:
    """Get or create hardware monitor instance"""
    global _hardware_monitor
    
    if _hardware_monitor is None:
        _hardware_monitor = HardwareMonitor(config)
    
    return _hardware_monitor

if __name__ == "__main__":
    print("Testing Hardware Monitor...")
    
    # Test configuration
    config = {
        'poll_interval': 2.0,
        'alerts_enabled': True,
        'logging_enabled': True,
        'max_history': 100,
        'cpu_temperature_threshold': 80.0,
        'cpu_usage_threshold': 90.0,
        'ram_usage_threshold': 90.0,
        'disk_usage_threshold': 90.0
    }
    
    hm = get_hardware_monitor(config)
    
    print("\n1. Hardware Detection:")
    print(f"Components found: {hm.stats['components_found']}")
    
    print("\n2. Current Hardware Status:")
    status = hm.get_current_status()
    print(f"Timestamp: {status['timestamp']}")
    
    print("\n3. Hardware Components:")
    for name, component in hm.hardware_cache.items():
        print(f"  {component.type.value.upper()}: {name}")
        if component.model and component.model != 'Unknown':
            print(f"    Model: {component.model}")
        if component.usage is not None:
            print(f"    Usage: {component.usage}%")
        if component.temperature is not None:
            print(f"    Temperature: {component.temperature}°C")
    
    print("\n4. Starting Monitoring (5 seconds)...")
    hm.start_monitoring()
    time.sleep(5)
    hm.stop_monitoring()
    
    print("\n5. Monitoring Statistics:")
    stats = hm.get_statistics()
    print(f"Polls performed: {stats['polls_performed']}")
    print(f"Alerts triggered: {stats['alerts_triggered']}")
    print(f"Monitoring active: {stats['monitoring_active']}")
    
    print("\n6. Getting History:")
    history = hm.get_history(limit=3)
    print(f"History entries: {len(history)}")
    
    print("\n7. Testing Report Export...")
    report = hm.export_report('text')
    if report:
        print(report[:500] + "..." if len(report)500 else report)
    
    print("\n✅ Hardware Monitor tests completed!")
