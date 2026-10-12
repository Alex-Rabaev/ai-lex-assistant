"""Auth module for JWT/Auth0 authentication."""

from app.common.auth.auth0 import (
    get_current_admin_auth0,
    verify_auth0_token,
    get_user_id_from_token,
    extract_email_from_payload,
    # Anonymous user utilities
    ANONYMOUS_PREFIX,
    is_anonymous_user,
    validate_anonymous_user_id
)
from app.common.auth.schemas import AdminUser

__all__ = [
    "get_current_admin_auth0",
    "verify_auth0_token",
    "get_user_id_from_token",
    "extract_email_from_payload",
    "AdminUser",
    # Anonymous user utilities
    "ANONYMOUS_PREFIX",
    "is_anonymous_user",
    "validate_anonymous_user_id"
]
