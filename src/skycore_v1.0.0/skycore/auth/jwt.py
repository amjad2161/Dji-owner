"""
SkyCore Auth - JWT Authentication Module
Secure authentication for GCS web interface
"""

import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from functools import wraps
import logging

logger = logging.getLogger(__name__)


@dataclass
class User:
    """User account"""
    username: str
    password_hash: str
    role: str  # 'admin', 'operator', 'viewer'
    permissions: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None


class JWTManager:
    """JWT token management"""
    
    def __init__(self, secret: str = None, algorithm: str = "HS256",
                 token_expiry_hours: int = 24):
        self.secret = secret or secrets.token_hex(32)
        self.algorithm = algorithm
        self.token_expiry = timedelta(hours=token_expiry_hours)
        self.refresh_expiry = timedelta(days=7)
        self.blacklist = set()  # Token blacklist for logout
        
        logger.info("JWT Manager initialized")
    
    def create_token(self, user_id: str, role: str, permissions: List[str]) -> Dict[str, str]:
        """Create access and refresh tokens"""
        now = datetime.utcnow()
        
        # Access token
        access_payload = {
            'sub': user_id,
            'role': role,
            'permissions': permissions,
            'type': 'access',
            'iat': now,
            'exp': now + self.token_expiry
        }
        access_token = jwt.encode(access_payload, self.secret, algorithm=self.algorithm)
        
        # Refresh token
        refresh_payload = {
            'sub': user_id,
            'type': 'refresh',
            'iat': now,
            'exp': now + self.refresh_expiry
        }
        refresh_token = jwt.encode(refresh_payload, self.secret, algorithm=self.algorithm)
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': int(self.token_expiry.total_seconds())
        }
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify and decode token"""
        if token in self.blacklist:
            return None
        
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Create new access token from refresh token"""
        payload = self.verify_token(refresh_token)
        
        if payload is None or payload.get('type') != 'refresh':
            return None
        
        # Create new access token
        now = datetime.utcnow()
        new_payload = {
            'sub': payload['sub'],
            'type': 'access',
            'iat': now,
            'exp': now + self.token_expiry
        }
        
        new_access = jwt.encode(new_payload, self.secret, algorithm=self.algorithm)
        
        return {
            'access_token': new_access,
            'token_type': 'Bearer',
            'expires_in': int(self.token_expiry.total_seconds())
        }
    
    def revoke_token(self, token: str):
        """Add token to blacklist (logout)"""
        self.blacklist.add(token)
        logger.info("Token revoked")


class UserManager:
    """User management and authentication"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.jwt_manager = JWTManager()
        
        # Default users (in production, use database)
        self._create_default_users()
        
        logger.info(f"User manager initialized with {len(self.users)} users")
    
    def _create_default_users(self):
        """Create default users for testing"""
        default_users = [
            ('admin', 'admin123', 'admin', ['all']),
            ('operator', 'operator123', 'operator', ['read', 'write', 'execute']),
            ('viewer', 'viewer123', 'viewer', ['read']),
            ('demo', 'demo', 'operator', ['read', 'write', 'execute'])
        ]
        
        for username, password, role, permissions in default_users:
            self.create_user(username, password, role, permissions)
    
    @staticmethod
    def hash_password(password: str, salt: str = None) -> Tuple[str, str]:
        """Hash password with salt"""
        salt = salt or secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return password_hash.hex(), salt
    
    def create_user(self, username: str, password: str, role: str = 'viewer',
                    permissions: List[str] = None) -> User:
        """Create new user"""
        password_hash, salt = self.hash_password(password)
        
        user = User(
            username=username,
            password_hash=f"{password_hash}:{salt}",
            role=role,
            permissions=permissions or ['read'],
            created_at=datetime.utcnow()
        )
        
        self.users[username] = user
        logger.info(f"User created: {username} ({role})")
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user and return tokens"""
        user = self.users.get(username)
        
        if user is None:
            logger.warning(f"Login attempt for unknown user: {username}")
            return None
        
        # Verify password
        stored_hash, salt = user.password_hash.split(':')
        password_hash, _ = self.hash_password(password, salt)
        
        if password_hash != stored_hash:
            logger.warning(f"Failed login for user: {username}")
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        # Create tokens
        tokens = self.jwt_manager.create_token(username, user.role, user.permissions)
        
        logger.info(f"User logged in: {username}")
        return {
            'user': {
                'username': username,
                'role': user.role,
                'permissions': user.permissions
            },
            **tokens
        }
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify token and return user info"""
        payload = self.jwt_manager.verify_token(token)
        
        if payload is None:
            return None
        
        user = self.users.get(payload['sub'])
        if user is None:
            return None
        
        return {
            'user_id': payload['sub'],
            'role': payload.get('role', user.role),
            'permissions': payload.get('permissions', user.permissions)
        }
    
    def has_permission(self, token: str, permission: str) -> bool:
        """Check if user has specific permission"""
        user_info = self.verify_token(token)
        
        if user_info is None:
            return False
        
        permissions = user_info.get('permissions', [])
        return 'all' in permissions or permission in permissions
    
    def get_user_info(self, username: str) -> Optional[Dict]:
        """Get user information"""
        user = self.users.get(username)
        
        if user is None:
            return None
        
        return {
            'username': user.username,
            'role': user.role,
            'permissions': user.permissions,
            'created_at': user.created_at.isoformat(),
            'last_login': user.last_login.isoformat() if user.last_login else None
        }


def require_auth(func):
    """Decorator to require authentication"""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return {'error': 'Missing authorization'}, 401
        
        token = auth_header[7:]
        
        # Verify token (simplified - use actual request context)
        # In real implementation, access global user manager
        return func(request, *args, **kwargs)
    
    return wrapper


def require_role(role: str):
    """Decorator to require specific role"""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Check role (simplified)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Check permission (simplified)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# Global instances
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """Get or create global user manager"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager


def get_jwt_manager() -> JWTManager:
    """Get JWT manager"""
    return get_user_manager().jwt_manager


def create_auth_module(secret: str = None) -> Tuple[UserManager, JWTManager]:
    """Factory function"""
    global _user_manager
    _user_manager = UserManager()
    return _user_manager, _user_manager.jwt_manager