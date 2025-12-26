import os
import time
import logging
from typing import Optional, Dict, Tuple

import requests
from flask import Request

logger = logging.getLogger(__name__)


_URL_PLACEHOLDERS = {"your_supabase_url_here"}
_KEY_PLACEHOLDERS = {
    "your_supabase_anon_key_here",
    "your_supabase_service_role_key_here",
}


def _is_missing_or_placeholder(value: str, placeholders: set[str]) -> bool:
    if not value:
        return True
    return value.strip() in placeholders


def is_supabase_auth_enabled() -> bool:
    supabase_disabled = os.getenv("SUPABASE_DISABLED", "").lower() in {"1", "true", "yes"}
    if supabase_disabled:
        return False
    supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
    supabase_anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    return not (
        _is_missing_or_placeholder(supabase_url, _URL_PLACEHOLDERS)
        or _is_missing_or_placeholder(supabase_anon_key, _KEY_PLACEHOLDERS)
    )


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme != "bearer" or not token:
        return None
    return token


_TOKEN_CACHE: Dict[str, Tuple[float, Optional[str]]] = {}
_TOKEN_CACHE_TTL_SECONDS = 60


def _get_cached_user_id(token: str) -> Optional[str]:
    now = time.time()
    cached = _TOKEN_CACHE.get(token)
    if not cached:
        return None
    expires_at, user_id = cached
    if expires_at <= now:
        _TOKEN_CACHE.pop(token, None)
        return None
    return user_id


def _set_cached_user_id(token: str, user_id: Optional[str]) -> None:
    _TOKEN_CACHE[token] = (time.time() + _TOKEN_CACHE_TTL_SECONDS, user_id)


def verify_supabase_access_token(access_token: str) -> Optional[str]:
    cached_user_id = _get_cached_user_id(access_token)
    if cached_user_id is not None:
        return cached_user_id

    supabase_url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    supabase_anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
    if not supabase_url or not supabase_anon_key:
        _set_cached_user_id(access_token, None)
        return None

    try:
        resp = requests.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": supabase_anon_key,
            },
            timeout=10,
        )
        if not resp.ok:
            _set_cached_user_id(access_token, None)
            return None
        data = resp.json() or {}
        user_id = data.get("id")
        if not isinstance(user_id, str) or not user_id:
            _set_cached_user_id(access_token, None)
            return None
        _set_cached_user_id(access_token, user_id)
        return user_id
    except Exception as e:
        logger.warning(f"Supabase token verification failed: {e}")
        _set_cached_user_id(access_token, None)
        return None


def get_request_user_id(request: Request) -> Optional[str]:
    """Returns authenticated user id based on environment.

    - If Supabase auth is enabled: require Authorization: Bearer <access_token>
    - Otherwise: use X-User-ID (local mode)
    """
    if is_supabase_auth_enabled():
        token = _extract_bearer_token(request)
        if not token:
            return None
        return verify_supabase_access_token(token)

    user_id = (request.headers.get("X-User-ID") or "").strip()
    return user_id or None
