"""Auth0 JWT token verification and user extraction."""

import json
import logging
import jwt
import httpx
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt.algorithms import RSAAlgorithm

from app.config import config
from app.common.auth.schemas import AdminUser

logger = logging.getLogger(__name__)
security = HTTPBearer()

# Cache for JWKS with TTL
_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_expires: Optional[datetime] = None
JWKS_CACHE_TTL = timedelta(hours=1)  # Cache for 1 hour


async def get_jwks() -> Dict[str, Any]:
    """Get JWKS from Auth0 with caching."""
    global _jwks_cache, _jwks_cache_expires
    
    # Check if cache is valid
    if _jwks_cache and _jwks_cache_expires and datetime.now() < _jwks_cache_expires:
        return _jwks_cache
    
    # Fetch new JWKS
    jwks_url = f"https://{config.AUTH0_DOMAIN}/.well-known/jwks.json"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            jwks = response.json()
            
            # Update cache
            _jwks_cache = jwks
            _jwks_cache_expires = datetime.now() + JWKS_CACHE_TTL
            
            return jwks
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            # If we have cached data, use it even if expired
            if _jwks_cache:
                logger.warning("Using expired JWKS cache due to fetch error")
                return _jwks_cache
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch JWKS"
            )


async def verify_auth0_token(token: str) -> dict:
    """Verify Auth0 token and return payload."""
    
    # Check configuration
    if not config.AUTH0_DOMAIN or not config.AUTH0_API_AUDIENCE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 not configured"
        )
    
    try:
        # Get token header
        unverified_header = jwt.get_unverified_header(token)
        
        # Get JWKS from cache or fetch
        jwks = await get_jwks()
        
        # Find matching key
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == unverified_header.get("kid"):
                public_key = RSAAlgorithm.from_jwk(json.dumps(key))
                break
        
        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Public key not found"
            )
        
        # Verify token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=config.AUTH0_ALGORITHMS,
            audience=config.AUTH0_API_AUDIENCE,
            issuer=f"https://{config.AUTH0_DOMAIN}/"
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )


def extract_role_from_payload(payload: dict) -> Optional[str]:
    """Extract user role from Auth0 token payload.
    
    Args:
        payload: Decoded JWT payload
        
    Returns:
        First role from the roles list or None if no roles found
    """
    # Auth0 Action sends roles in 'ai-lex.dev/roles' claim
    if "ai-lex.dev/roles" in payload:
        roles = payload["ai-lex.dev/roles"]
        if isinstance(roles, list) and roles:
            return roles[0].lower()
    return None


def extract_email_from_payload(payload: dict) -> Optional[str]:
    """Extract user email from Auth0 token payload.
    
    Args:
        payload: Decoded JWT payload
        
    Returns:
        User email from custom claim or standard claim
    """
    # Try custom claim first (set by Auth0 Action)
    if "ai-lex.dev/email" in payload:
        return payload["ai-lex.dev/email"]
    
    # Fallback to standard email claim
    if "email" in payload:
        return payload["email"]
    
    return None


async def get_user_id_from_token(token: str) -> str:
    """
    Extract user ID (email) from JWT token.
    
    This is a utility function for extracting authenticated user identity.
    Used by WebSocket, webhooks, and other endpoints that need user identification.
    
    Args:
        token: JWT token (with or without "Bearer " prefix)
        
    Returns:
        User email as user_id
        
    Raises:
        HTTPException: If token is invalid or email not found
    """
    # Remove "Bearer " prefix if present
    if token.startswith("Bearer "):
        token = token[7:]
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is required"
        )
    
    payload = await verify_auth0_token(token)
    
    email = extract_email_from_payload(payload)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not found in token"
        )
    
    return email


async def get_current_admin_auth0(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AdminUser:
    """Auth0 authorization dependency for admin users."""
    
    payload = await verify_auth0_token(credentials.credentials)
    
    # Extract role from Auth0 token
    role = extract_role_from_payload(payload)
    
    # Check if user has admin role
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No role found in token"
        )
    
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    # Extract email from token
    email = extract_email_from_payload(payload)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not found in token"
        )
    
    # Create AdminUser from Auth0 data
    return AdminUser(
        email=email,
        username=payload.get("nickname"),
        role=role,
        first_name=payload.get("given_name"),
        last_name=payload.get("family_name")
    )


# ============================================
# Anonymous User Utilities
# ============================================

ANONYMOUS_PREFIX = "anon_"


def is_anonymous_user(user_id: str) -> bool:
    """
    Check if user_id represents an anonymous user.
    
    Args:
        user_id: User identifier
        
    Returns:
        True if user_id starts with 'anon_' prefix
    """
    return user_id.startswith(ANONYMOUS_PREFIX)


def validate_anonymous_user_id(user_id: str) -> bool:
    """
    Validate anonymous user ID format.
    
    Expected format: anon_{uuid4}
    Example: anon_550e8400-e29b-41d4-a716-446655440000
    
    Args:
        user_id: User identifier to validate
        
    Returns:
        True if valid anonymous ID format
    """
    if not user_id or not user_id.startswith(ANONYMOUS_PREFIX):
        return False
    
    # Extract the UUID part
    uuid_part = user_id[len(ANONYMOUS_PREFIX):]
    
    # Basic validation: should be non-empty and reasonable length
    # UUID4 is typically 36 chars (with dashes) or 32 (without)
    if not uuid_part or len(uuid_part) < 8:
        return False
    
    return True

