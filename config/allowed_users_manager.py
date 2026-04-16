#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
allowed_users_manager.py - Manages authorized users list
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class AllowedUsersManager:
    """Manages the allowed users list"""
    
    def __init__(self, users_file="allowed_users.txt"):
        self.users_file = users_file
        self.users = []
        self.load_users()
    
    def parse_user_line(self, line: str) -> Optional[Dict]:
        """Parse a user line from the file"""
        line = line.strip()
        
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            return None
        
        # Parse the line
        # Format: UserID | Username | Role | AddedDate | Expires | Notes
        parts = [part.strip() for part in line.split('|')]
        
        if len(parts 6:
            return None
        
        user_id = int(parts[0]) if parts[0].isdigit() else 0
        username = parts[1]
        role = parts[2]
        added_date = parts[3]
        expires = parts[4]
        notes = parts[5]
        
        return {
            'user_id': user_id,
            'username': username,
            'role': role,
            'added_date': added_date,
            'expires': expires,
            'notes': notes,
            'active': self.is_user_active(expires)
        }
    
    def is_user_active(self, expires: str) -> bool:
        """Check if user is still active"""
        if expires.lower() == 'never':
            return True
        
        try:
            expire_date = datetime.strptime(expires, '%Y-%m-%d')
            return datetime.now() <= expire_date
        except ValueError:
            return False
    
    def load_users(self):
        """Load users from file"""
        self.users = []
        
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                for line in f:
                    user = self.parse_user_line(line)
                    if user:
                        self.users.append(user)
            
            print(f"👤 Loaded {len(self.users)} users from {self.users_file}")
        except FileNotFoundError:
            print(f"⚠️  Users file {self.users_file} not found, starting with empty list")
            self.users = []
        except Exception as e:
            print(f"❌ Error loading users: {e}")
    
    def save_users(self):
        """Save users to file"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                # Write header
                f.write("# ============================================\n")
                f.write("# 😈 DER BÖSE KOLLEGE - AUTORISIERTE BENUTZER\n")
                f.write("# ============================================\n")
                f.write("# Format: UserID | Username | Role | AddedDate | Expires | Notes\n")
                f.write("# ============================================\n\n")
                
                # Write users
                for user in self.users:
                    line = f"{user['user_id']} | {user['username']} | {user['role']} | "
                    line += f"{user['added_date']} | {user['expires']} | {user['notes']}\n"
                    f.write(line)
                
                # Write footer
                f.write("\n# ============================================\n")
                f.write(f"# 📅 LAST UPDATED: {datetime.now().strftime('%Y-%m-%d')}\n")
                f.write(f"# 👤 TOTAL USERS: {len(self.users)}\n")
                active_count = sum(1 for u in self.users if u['active'])
                f.write(f"# 🔒 ACTIVE USERS: {active_count}\n")
                f.write("# ============================================\n")
            
            print(f"💾 Users saved to {self.users_file}")
        except Exception as e:
            print(f"❌ Error saving users: {e}")
    
    def add_user(self, user_id: int, username: str, role: str, 
                 expires: str = "never", notes: str = "") -> bool:
        """Add a new user"""
        # Check if user already exists
        if self.get_user(user_id):
            print(f"⚠️  User {user_id} already exists")
            return False
        
        user = {
            'user_id': user_id,
            'username': username,
            'role': role,
            'added_date': datetime.now().strftime('%Y-%m-%d'),
            'expires': expires,
            'notes': notes,
            'active': self.is_user_active(expires)
        }
        
        self.users.append(user)
        self.save_users()
        print(f"✅ Added user {username} (ID: {user_id})")
        return True
    
    def remove_user(self, user_id: int) -> bool:
        """Remove a user"""
        for i, user in enumerate(self.users):
            if user['user_id'] == user_id:
                removed_user = self.users.pop(i)
                self.save_users()
                print(f"✅ Removed user {removed_user['username']} (ID: {user_id})")
                return True
        
        print(f"⚠️  User {user_id} not found")
        return False
    
    def update_user(self, user_id: int, **kwargs) -> bool:
        """Update user information"""
        for user in self.users:
            if user['user_id'] == user_id:
                for key, value in kwargs.items():
                    if key in user and key != 'user_id':
                        user[key] = value
                
                # Update active status if expires changed
                if 'expires' in kwargs:
                    user['active'] = self.is_user_active(kwargs['expires'])
                
                self.save_users()
                print(f"✅ Updated user {user['username']} (ID: {user_id})")
                return True
        
        print(f"⚠️  User {user_id} not found")
        return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        for user in self.users:
            if user['user_id'] == user_id:
                return user
        return None
    
    def is_user_allowed(self, user_id: int, required_role: str = None) -> bool:
        """Check if user is allowed and has required role"""
        user = self.get_user(user_id)
        
        if not user:
            return False
        
        if not user['active']:
            return False
        
        if required_role:
            # Check role hierarchy
            role_hierarchy = {
                'admin': 5,
                'developer': 4,
                'operator': 3,
                'tester': 2,
                'monitor': 1,
                'bot': 0
            }
            
            user_role_level = role_hierarchy.get(user['role'], 0)
            required_role_level = role_hierarchy.get(required_role, 0)
            
            return user_role_level >= required_role_level
        
        return True
    
    def get_users_by_role(self, role: str) -> List[Dict]:
        """Get all users with a specific role"""
        return [user for user in self.users if user['role'] == role and user['active']]
    
    def get_active_users(self) -> List[Dict]:
        """Get all active users"""
        return [user for user in self.users if user['active']]
    
    def get_expired_users(self) -> List[Dict]:
        """Get all expired users"""
        return [user for user in self.users if not user['active']]
    
    def cleanup_expired_users(self) -> int:
        """Remove all expired users"""
        expired_users = self.get_expired_users()
        count = len(expired_users)
        
        self.users = [user for user in self.users if user['active']]
        
        if count > 0:
            self.save_users()
            print(f"🧹 Cleaned up {count} expired users")
        
        return count
    
    def export_users_csv(self, output_file: str = "users_export.csv") -> bool:
        """Export users to CSV"""
        try:
            import csv
            
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['UserID', 'Username', 'Role', 'AddedDate', 
                                'Expires', 'Active', 'Notes'])
                
                for user in self.users:
                    writer.writerow([
                        user['user_id'],
                        user['username'],
                        user['role'],
                        user['added_date'],
                        user['expires'],
                        'Yes' if user['active'] else 'No',
                        user['notes']
                    ])
            
            print(f"📤 Users exported to {output_file}")
            return True
        except Exception as e:
            print(f"❌ Error exporting users: {e}")
            return False
    
    def print_summary(self):
        """Print user summary"""
        print("\n" + "=" * 50)
        print("👥 USER MANAGEMENT SUMMARY")
        print("=" * 50)
        
        total = len(self.users)
        active = len(self.get_active_users())
        expired = len(self.get_expired_users())
        
        print(f"Total Users: {total}")
        print(f"Active Users: {active}")
        print(f"Expired Users: {expired}")
        
        print("\n📊 By Role:")
        roles = {}
        for user in self.users:
            role = user['role']
            roles[role] = roles.get(role, 0) + 1
        
        for role, count in sorted(roles.items()):
            active_count = len(self.get_users_by_role(role))
            print(f"  {role}: {count} (Active: {active_count})")
        
        print("\n" + "=" * 50)

# Singleton instance
users_manager = AllowedUsersManager()

if __name__ == "__main__":
    # Test the users manager
    print("👤 ALLOWED USERS MANAGER")
    print("=" * 50)
    
    # Print summary
    users_manager.print_summary()
    
    # Example: Add a test user
    users_manager.add_user(
        user_id=101010101,
        username="TestUser",
        role="tester",
        expires="2024-02-28",
        notes="Test account for validation"
    )
    
    # Check if user is allowed
    test_id = 123456789
    is_allowed = users_manager.is_user_allowed(test_id, "admin")
    print(f"\n✅ User {test_id} allowed as admin: {is_allowed}")
    
    # Export to CSV
    users_manager.export_users_csv()
    
    print("\n" + "=" * 50)
    print("💀 User management system ready!")
