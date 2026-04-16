#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system/__init__.py - System Management Package
Centralized system control and monitoring
"""

import os
import sys
from typing import Dict, List, Optional, Any

# Import all system modules
from .process_manager import ProcessManager, get_process_manager
from .service_manager import ServiceManager, get_service_manager
from .registry_manager import RegistryManager, get_registry_manager
from .file_manager import FileManager, get_file_manager
from .privilege_escalation import PrivilegeEscalation, get_privilege_escalation

# Import future modules (will be added)
# from .hardware_monitor import HardwareMonitor, get_hardware_monitor
# from .performance_monitor import PerformanceMonitor, get_performance_monitor
# from .network_monitor import NetworkMonitor, get_network_monitor
# from .security_monitor import SecurityMonitor, get_security_monitor

__version__ = "1.0.0"
__author__ = "DerBöseKollege Framework"
__description__ = "Advanced System Management and Control"

class SystemManager:
    """Centralized System Management with all modules"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Initialize all system modules
        self.process_manager = get_process_manager(self.config.get('process', {}))
        self.service_manager = get_service_manager(self.config.get('service', {}))
        self.file_manager = get_file_manager(self.config.get('file', {}))
        self.privilege_escalation = get_privilege_escalation(self.config.get('privilege', {}))
        
        # Windows-only modules
        self.registry_manager = None
        if sys.platform == 'win32':
            self.registry_manager = get_registry_manager(self.config.get('registry', {}))
        
        # Future modules
        self.hardware_monitor = None
        self.performance_monitor = None
        self.network_monitor = None
        self.security_monitor = None
        
        # Statistics
        self.stats = {
            'modules_loaded': 4,
            'start_time': __import__('datetime').datetime.now(),
            'platform': sys.platform,
            'initialized': True
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics from all modules"""
        stats = {
            'system_manager': self.stats,
            'process_manager': self.process_manager.get_statistics() if hasattr(self.process_manager, 'get_statistics') else {},
            'service_manager': self.service_manager.get_statistics() if hasattr(self.service_manager, 'get_statistics') else {},
            'file_manager': self.file_manager.get_statistics() if hasattr(self.file_manager, 'get_statistics') else {},
            'privilege_escalation': self.privilege_escalation.get_statistics() if hasattr(self.privilege_escalation, 'get_statistics') else {},
        }
        
        if self.registry_manager:
            stats['registry_manager'] = self.registry_manager.get_statistics() if hasattr(self.registry_manager, 'get_statistics') else {}
        
        return stats
    
    def execute_command(self, module: str, command: str, **kwargs) -> Any:
        """Execute command on specific module"""
        module_map = {
            'process': self.process_manager,
            'service': self.service_manager,
            'file': self.file_manager,
            'registry': self.registry_manager,
            'privilege': self.privilege_escalation
        }
        
        target_module = module_map.get(module)
        if not target_module:
            raise ValueError(f"Unknown module: {module}")
        
        # Check if module has the method
        if not hasattr(target_module, command):
            raise AttributeError(f"Module {module} has no command {command}")
        
        method = getattr(target_module, command)
        
        # Execute with kwargs
        return method(**kwargs)
    
    def cleanup(self):
        """Cleanup all modules"""
        try:
            if hasattr(self.process_manager, '__del__'):
                self.process_manager.__del__()
            
            if hasattr(self.service_manager, '__del__'):
                self.service_manager.__del__()
            
            if hasattr(self.file_manager, '__del__'):
                self.file_manager.__del__()
            
            if self.registry_manager and hasattr(self.registry_manager, '__del__'):
                self.registry_manager.__del__()
            
            if hasattr(self.privilege_escalation, '__del__'):
                self.privilege_escalation.__del__()
        except:
            pass

# Global instance
_system_manager = None

def get_system_manager(config: Dict = None) -> SystemManager:
    """Get or create system manager instance"""
    global _system_manager
    
    if _system_manager is None:
        _system_manager = SystemManager(config)
    
    return _system_manager

# Export all public functions and classes
__all__ = [
    # Core system manager
    'SystemManager',
    'get_system_manager',
    
    # Individual modules
    'ProcessManager',
    'get_process_manager',
    
    'ServiceManager',
    'get_service_manager',
    
    'RegistryManager',
    'get_registry_manager',
    
    'FileManager',
    'get_file_manager',
    
    'PrivilegeEscalation',
    'get_privilege_escalation'
]

if __name__ == "__main__":
    print(f"System Module v{__version__}")
    print(f"Description: {__description__}")
    print(f"Platform: {sys.platform}")
    
    # Test initialization
    sm = get_system_manager()
    print(f"\nModules loaded: {sm.stats['modules_loaded']}")
    
    # Get statistics
    stats = sm.get_all_stats()
    print(f"\nSystem Manager Stats:")
    for module, data in stats.items():
        if data:
            print(f"  {module}: OK")
    
    print("\n✅ System Module initialized successfully!")
