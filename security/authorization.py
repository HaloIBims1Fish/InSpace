#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
authorization.py - Role-Based Access Control (RBAC) System
"""

import json
import os
import re
from typing import Dict, List, Optional, Set, Any, Union
from enum import Enum

# Import logger
from ..utils.logger import get_logger

logger = get_logger()

class PermissionLevel(Enum):
    """Permission levels"""
    NONE = 0
    READ = 1
    WRITE = 2
    EXECUTE = 3
    ADMIN = 4

class ResourceType(Enum):
    """Resource types for access control"""
    FILE = "file"
    COMMAND = "command"
    MODULE = "module"
    SYSTEM = "system"
    NETWORK = "network"
    DATABASE = "database"
    CONFIG = "config"

class AuthorizationSystem:
    """Role-Based Access Control (RBAC) system"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # Storage for roles and policies
        self.roles_file = self.config.get('roles_file', 'data/roles.json')
        self.policies_file = self.config.get('policies_file', 'data/policies.json')
        
        # Load or initialize data
        self.roles = self._load_data(self.roles_file, {})
        self.policies = self._load_data(self.policies_file, {})
        
        # Default roles if none exist
        if not self.roles:
            self._create_default_roles()
        
        # Default policies if none exist
        if not self.policies:
            self._create_default_policies()
        
        # Permission cache for performance
        self.permission_cache = {}
        
        logger.info("Authorization system initialized", module="authorization")
    
    def _load_data(self, filename: str, default: Any) -> Any:
        """Load JSON data from file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}", module="authorization")
        
        return default
    
    def _save_data(self, filename: str, data: Any):
        """Save JSON data to file"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving {filename}: {e}", module="authorization")
    
    def _create_default_roles(self):
        """Create default roles"""
        default_roles = {
            "guest": {
                "description": "Guest access - minimal permissions",
                "permissions": [
                    "system:info:read",
                    "module:datensammler:read"
                ],
                "inherits": []
            },
            "user": {
                "description": "Standard user access",
                "permissions": [
                    "system:*:read",
                    "module:*:read",
                    "file:user:*:read",
                    "command:basic:*:execute"
                ],
                "inherits": ["guest"]
            },
            "operator": {
                "description": "System operator",
                "permissions": [
                    "system:*:write",
                    "module:*:write",
                    "file:*:*:read",
                    "file:temp:*:write",
                    "command:*:*:execute",
                    "network:*:*:read",
                    "database:*:*:read"
                ],
                "inherits": ["user"]
            },
            "admin": {
                "description": "Full administrator access",
                "permissions": [
                    "*:*:*:*"  # Wildcard - full access
                ],
                "inherits": ["operator"]
            },
            "root": {
                "description": "Superuser - bypasses all checks",
                "permissions": ["*:*:*:*"],
                "inherits": [],
                "is_root": True
            }
        }
        
        self.roles = default_roles
        self._save_data(self.roles_file, self.roles)
        logger.info("Default roles created", module="authorization")
    
    def _create_default_policies(self):
        """Create default access control policies"""
        default_policies = {
            # Module access policies
            "modules": {
                "datensammler": {
                    "required_permission": "module:datensammler:*",
                    "min_level": PermissionLevel.EXECUTE.value
                },
                "factoryreset": {
                    "required_permission": "module:factoryreset:*",
                    "min_level": PermissionLevel.ADMIN.value,
                    "requires_confirmation": True
                },
                "files_sperren": {
                    "required_permission": "module:files_sperren:*",
                    "min_level": PermissionLevel.ADMIN.value
                },
                "geraet_sperren": {
                    "required_permission": "module:geraet_sperren:*",
                    "min_level": PermissionLevel.ADMIN.value,
                    "requires_confirmation": True
                },
                "telegram_bank_bot": {
                    "required_permission": "module:telegram_bank_bot:*",
                    "min_level": PermissionLevel.EXECUTE.value
                },
                "UltimateHardwareExploid": {
                    "required_permission": "module:UltimateHardwareExploid:*",
                    "min_level": PermissionLevel.ADMIN.value,
                    "requires_confirmation": True
                },
                "webcam_remote": {
                    "required_permission": "module:webcam_remote:*",
                    "min_level": PermissionLevel.EXECUTE.value,
                    "requires_consent": True
                }
            },
            
            # System command policies
            "commands": {
                "shutdown": {
                    "required_permission": "system:shutdown:execute",
                    "min_level": PermissionLevel.ADMIN.value
                },
                "reboot": {
                    "required_permission": "system:reboot:execute",
                    "min_level": PermissionLevel.ADMIN.value
                },
                "kill_process": {
                    "required_permission": "system:process:execute",
                    "min_level": PermissionLevel.EXECUTE.value
                },
                "delete_file": {
                    "required_permission": "file:*:write",
                    "min_level": PermissionLevel.WRITE.value
                },
                "execute_script": {
                    "required_permission": "command:script:execute",
                    "min_level": PermissionLevel.EXECUTE.value
                }
            },
            
            # File access policies
            "files": {
                "config": {
                    "path_pattern": ".*\\.(json|ini|cfg|conf)$",
                    "required_permission": "config:*:*",
                    "min_level": PermissionLevel.READ.value
                },
                "executable": {
                    "path_pattern": ".*\\.(exe|bat|sh|py)$",
                    "required_permission": "file:executable:*",
                    "min_level": PermissionLevel.EXECUTE.value
                },
                "system": {
                    "path_pattern": "/(etc|var|usr|boot|proc|sys)/.*",
                    "required_permission": "system:file:*",
                    "min_level": PermissionLevel.ADMIN.value
                }
            },
            
            # Network policies
            "network": {
                "scan": {
                    "required_permission": "network:scan:execute",
                    "min_level": PermissionLevel.EXECUTE.value
                },
                "connect": {
                    "required_permission": "network:connect:execute",
                    "min_level": PermissionLevel.EXECUTE.value
                },
                "listen": {
                    "required_permission": "network:listen:execute",
                    "min_level": PermissionLevel.EXECUTE.value
                }
            }
        }
        
        self.policies = default_policies
        self._save_data(self.policies_file, self.policies)
        logger.info("Default policies created", module="authorization")
    
    def create_role(self, role_name: str, description: str = "",
                   permissions: List[str] = None, inherits: List[str] = None,
                   is_root: bool = False) -> bool:
        """Create new role"""
        try:
            if role_name in self.roles:
                logger.warning(f"Role already exists: {role_name}", module="authorization")
                return False
            
            # Validate inherited roles exist
            valid_inherits = []
            if inherits:
                for parent_role in inherits:
                    if parent_role in self.roles:
                        valid_inherits.append(parent_role)
                    else:
                        logger.warning(f"Parent role not found: {parent_role}", module="authorization")
            
            # Create role
            self.roles[role_name] = {
                "description": description,
                "permissions": permissions or [],
                "inherits": valid_inherits,
                "is_root": is_root,
                "created_at": self._get_timestamp()
            }
            
            self._save_data(self.roles_file, self.roles)
            
            # Clear cache
            self.permission_cache.clear()
            
            logger.info(f"Role created: {role_name}", module="authorization")
            return True
            
        except Exception as e:
            logger.error(f"Role creation error: {e}", module="authorization")
            return False
    
    def delete_role(self, role_name: str) -> bool:
        """Delete role"""
        try:
            if role_name not in self.roles:
                return False
            
            # Check if role is in use
            for role in self.roles.values():
                if role_name in role.get("inherits", []):
                    logger.warning(f"Cannot delete role {role_name} - it is inherited by other roles", module="authorization")
                    return False
            
            # Delete role
            del self.roles[role_name]
            self._save_data(self.roles_file, self.roles)
            
            # Clear cache
            self.permission_cache.clear()
            
            logger.info(f"Role deleted: {role_name}", module="authorization")
            return True
            
        except Exception as e:
            logger.error(f"Role deletion error: {e}", module="authorization")
            return False
    
    def update_role_permissions(self, role_name: str, permissions: List[str]) -> bool:
        """Update role permissions"""
        try:
            if role_name not in self.roles:
                return False
            
            self.roles[role_name]["permissions"] = permissions
            self.roles[role_name]["updated_at"] = self._get_timestamp()
            
            self._save_data(self.roles_file, self.roles)
            
            # Clear cache for this role
            if role_name in self.permission_cache:
                del self.permission_cache[role_name]
            
            logger.info(f"Permissions updated for role: {role_name}", module="authorization")
            return True
            
        except Exception as e:
            logger.error(f"Role update error: {e}", module="authorization")
            return False
    
    def get_role_permissions(self, role_name: str, include_inherited: bool = True) -> Set[str]:
        """Get all permissions for a role (including inherited)"""
        try:
            # Check cache first
            cache_key = f"{role_name}:{include_inherited}"
            if cache_key in self.permission_cache:
                return self.permission_cache[cache_key]
            
            if role_name not in self.roles:
                return set()
            
            permissions = set()
            role = self.roles[role_name]
            
            # Add direct permissions
            permissions.update(role.get("permissions", []))
            
            # Add inherited permissions
            if include_inherited:
                for parent_role in role.get("inherits", []):
                    parent_permissions = self.get_role_permissions(parent_role, True)
                    permissions.update(parent_permissions)
            
            # Cache result
            self.permission_cache[cache_key] = permissions
            
            return permissions
            
        except Exception as e:
            logger.error(f"Error getting role permissions: {e}", module="authorization")
            return set()
    
    def check_permission(self, user_permissions: List[str], 
                        required_permission: str, 
                        min_level: int = PermissionLevel.READ.value) -> bool:
        """Check if user has required permission"""
        try:
            # Parse required permission
            required_parts = required_permission.split(":")
            
            # Check each user permission
            for user_perm in user_permissions:
                user_parts = user_perm.split(":")
                
                # Check if permission matches pattern
                if self._permission_matches(user_parts, required_parts):
                    # Check permission level
                    if len(user_parts) >= 4:
                        try:
                            user_level = PermissionLevel[user_parts[3].upper()].value
                            if user_level >= min_level:
                                return True
                        except (KeyError, ValueError):
                            # If no level specified, assume EXECUTE
                            if min_level <= PermissionLevel.EXECUTE.value:
                                return True
                    else:
                        # No level specified, check based on context
                        if min_level <= PermissionLevel.EXECUTE.value:
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"Permission check error: {e}", module="authorization")
            return False
    
    def _permission_matches(self, user_parts: List[str], required_parts: List[str]) -> bool:
        """Check if user permission matches required pattern"""
        if len(user_parts) != len(required_parts):
            return False
        
        for user_part, required_part in zip(user_parts, required_parts):
            if required_part == "*":
                continue
            if user_part == "*":
                return True  # User has wildcard for this part
            if user_part != required_part:
                return False
        
        return True
    
    def authorize_module_access(self, username: str, user_roles: List[str], 
                               module_name: str) -> Dict[str, Any]:
        """Authorize access to a specific module"""
        try:
            # Get all permissions for user's roles
            all_permissions = set()
            for role in user_roles:
                role_perms = self.get_role_permissions(role, True)
                all_permissions.update(role_perms)
            
            # Check if user has root access
            for role in user_roles:
                if self.roles.get(role, {}).get("is_root"):
                    return {
                        "authorized": True,
                        "level": PermissionLevel.ADMIN.value,
                        "requires_confirmation": False,
                        "requires_consent": False
                    }
            
            # Get module policy
            module_policy = self.policies.get("modules", {}).get(module_name)
            
            if not module_policy:
                # No specific policy, check generic module permission
                required_perm = f"module:{module_name}:*"
                has_access = self.check_permission(list(all_permissions), required_perm)
                
                return {
                    "authorized": has_access,
                    "level": PermissionLevel.EXECUTE.value if has_access else PermissionLevel.NONE.value,
                    "requires_confirmation": False,
                    "requires_consent": False
                }
            
            # Check against module policy
            required_perm = module_policy.get("required_permission", f"module:{module_name}:*")
            min_level = module_policy.get("min_level", PermissionLevel.EXECUTE.value)
            
            authorized = self.check_permission(list(all_permissions), required_perm, min_level)
            
            return {
                "authorized": authorized,
                "level": min_level if authorized else PermissionLevel.NONE.value,
                "requires_confirmation": module_policy.get("requires_confirmation", False),
                "requires_consent": module_policy.get("requires_consent", False)
            }
            
        except Exception as e:
            logger.error(f"Module authorization error: {e}", module="authorization")
            return {
                "authorized": False,
                "level": PermissionLevel.NONE.value,
                "error": str(e)
            }
    
    def authorize_command(self, username: str, user_roles: List[str],
                         command_name: str, args: List[str] = None) -> Dict[str, Any]:
        """Authorize execution of a command"""
        try:
            # Get all permissions for user's roles
            all_permissions = set()
            for role in user_roles:
                role_perms = self.get_role_permissions(role, True)
                all_permissions.update(role_perms)
            
            # Check if user has root access
            for role in user_roles:
                if self.roles.get(role, {}).get("is_root"):
                    return {
                        "authorized": True,
                        "level": PermissionLevel.ADMIN.value,
                        "requires_confirmation": False
                    }
            
            # Get command policy
            command_policy = self.policies.get("commands", {}).get(command_name)
            
            if not command_policy:
                # No specific policy, check generic command permission
                required_perm = f"command:{command_name}:execute"
                has_access = self.check_permission(list(all_permissions), required_perm)
                
                return {
                    "authorized": has_access,
                    "level": PermissionLevel.EXECUTE.value if has_access else PermissionLevel.NONE.value,
                    "requires_confirmation": False
                }
            
            # Check against command policy
            required_perm = command_policy.get("required_permission", f"command:{command_name}:execute")
            min_level = command_policy.get("min_level", PermissionLevel.EXECUTE.value)
            
            authorized = self.check_permission(list(all_permissions), required_perm, min_level)
            
            return {
                "authorized": authorized,
                "level": min_level if authorized else PermissionLevel.NONE.value,
                "requires_confirmation": command_policy.get("requires_confirmation", False)
            }
            
        except Exception as e:
            logger.error(f"Command authorization error: {e}", module="authorization")
            return {
                "authorized": False,
                "level": PermissionLevel.NONE.value,
                "error": str(e)
            }
    
    def authorize_file_access(self, username: str, user_roles: List[str],
                             file_path: str, access_type: str = "read") -> Dict[str, Any]:
        """Authorize access to a file"""
        try:
            # Get all permissions for user's roles
            all_permissions = set()
            for role in user_roles:
                role_perms = self.get_role_permissions(role, True)
                all_permissions.update(role_perms)
            
            # Check if user has root access
            for role in user_roles:
                if self.roles.get(role, {}).get("is_root"):
                    return {
                        "authorized": True,
                        "level": PermissionLevel.ADMIN.value
                    }
            
            # Determine required permission level
            if access_type == "read":
                required_level = PermissionLevel.READ.value
                action = "read"
            elif access_type == "write":
                required_level = PermissionLevel.WRITE.value
                action = "write"
            elif access_type == "execute":
                required_level = PermissionLevel.EXECUTE.value
                action = "execute"
            else:
                required_level = PermissionLevel.READ.value
                action = "read"
            
            # Check file policies
            file_policies = self.policies.get("files", {})
            
            for policy_name, policy in file_policies.items():
                path_pattern = policy.get("path_pattern")
                if path_pattern and re.match(path_pattern, file_path):
                    # This policy applies to the file
                    required_perm = policy.get("required_permission", f"file:{policy_name}:{action}")
                    min_level = policy.get("min_level", required_level)
                    
                    authorized = self.check_permission(list(all_permissions), required_perm, min_level)
                    
                    return {
                        "authorized": authorized,
                        "level": min_level if authorized else PermissionLevel.NONE.value,
                        "policy": policy_name
                    }
            
            # No specific policy, check generic file permission
            required_perm = f"file:*:{action}"
            authorized = self.check_permission(list(all_permissions), required_perm, required_level)
            
            return {
                "authorized": authorized,
                "level": required_level if authorized else PermissionLevel.NONE.value
            }
            
        except Exception as e:
            logger.error(f"File authorization error: {e}", module="authorization")
            return {
                "authorized": False,
                "level": PermissionLevel.NONE.value,
                "error": str(e)
            }
    
    def create_policy(self, policy_type: str, policy_name: str, 
                     policy_data: Dict[str, Any]) -> bool:
        """Create new access policy"""
        try:
            if policy_type not in self.policies:
                self.policies[policy_type] = {}
            
            self.policies[policy_type][policy_name] = policy_data
            self._save_data(self.policies_file, self.policies)
            
            logger.info(f"Policy created: {policy_type}/{policy_name}", module="authorization")
            return True
            
        except Exception as e:
            logger.error(f"Policy creation error: {e}", module="authorization")
            return False
    
    def get_user_authorization_summary(self, username: str, user_roles: List[str]) -> Dict[str, Any]:
        """Get comprehensive authorization summary for user"""
        try:
            # Get all permissions
            all_permissions = set()
            for role in user_roles:
                role_perms = self.get_role_permissions(role, True)
                all_permissions.update(role_perms)
            
            # Check root access
            is_root = False
            for role in user_roles:
                if self.roles.get(role, {}).get("is_root"):
                    is_root = True
                    break
            
            # Count permissions by type
            permission_counts = {}
            for perm in all_permissions:
                parts = perm.split(":")
                if parts:
                    perm_type = parts[0]
                    permission_counts[perm_type] = permission_counts.get(perm_type, 0) + 1
            
            # Check module access
            module_access = {}
            modules = self.policies.get("modules", {}).keys()
            
            for module in modules:
                auth_result = self.authorize_module_access(username, user_roles, module)
                module_access[module] = auth_result["authorized"]
            
            return {
                "username": username,
                "roles": user_roles,
                "is_root": is_root,
                "total_permissions": len(all_permissions),
                "permission_counts": permission_counts,
                "module_access": module_access,
                "can_execute_destructive": any([
                    module_access.get("factoryreset", False),
                    module_access.get("files_sperren", False),
                    module_access.get("geraet_sperren", False)
                ])
            }
            
        except Exception as e:
            logger.error(f"Authorization summary error: {e}", module="authorization")
            return {
                "username": username,
                "error": str(e)
            }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_status(self) -> Dict[str, Any]:
        """Get authorization system status"""
        return {
            "total_roles": len(self.roles),
            "total_policies": sum(len(policies) for policies in self.policies.values()),
            "cache_size": len(self.permission_cache),
            "default_roles": list(self.roles.keys())
        }

# Global instance
_auth_system = None

def get_authorization_system(config: Dict = None) -> AuthorizationSystem:
    """Get or create authorization system instance"""
    global _auth_system
    
    if _auth_system is None:
        _auth_system = AuthorizationSystem(config)
    
    return _auth_system

if __name__ == "__main__":
    # Test authorization system
    authz = get_authorization_system()
    
    print("Testing authorization system...")
    
    # Test role permissions
    admin_perms = authz.get_role_permissions("admin")
    print(f"Admin permissions: {len(admin_perms)} total")
    
    # Test module authorization
    auth_result = authz.authorize_module_access(
        username="testuser",
        user_roles=["user"],
        module_name="datensammler"
    )
    print(f"Module authorization (user -> datensammler): {auth_result}")
    
    # Test command authorization
    cmd_auth = authz.authorize_command(
        username="testuser",
        user_roles=["user"],
        command_name="execute_script"
    )
    print(f"Command authorization (user -> execute_script): {cmd_auth}")
    
    # Test file authorization
    file_auth = authz.authorize_file_access(
        username="testuser",
        user_roles=["user"],
        file_path="/etc/passwd",
        access_type="read"
    )
    print(f"File authorization (user -> /etc/passwd): {file_auth}")
    
    # Get user summary
    summary = authz.get_user_authorization_summary(
        username="testuser",
        user_roles=["admin"]
    )
    print(f"\nUser authorization summary: {summary}")
    
    # Show status
    status = authz.get_status()
    print(f"\n🔒 Authorization System Status: {status}")
    
    print("\n✅ Authorization tests completed!")
