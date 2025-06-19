# -*- coding: utf-8 -*-
"""Simple session management placeholder."""

import logging
import time
from typing import Dict, List, Optional, Tuple

from constants import Constants

logger = logging.getLogger(__name__)

# In memory session storage for placeholder purposes
_sessions: List[Dict[str, any]] = []
_next_id = 1


class Session:
    """Represents a Telegram session entry."""

    @staticmethod
    def load_all() -> List[Dict[str, any]]:
        """Load all sessions from storage if possible."""
        try:
            from db import execute_query

            result = execute_query("SELECT * FROM sessions")
            return [dict(row) for row in result] if result else []
        except Exception:
            # fallback to in-memory store
            return list(_sessions)


def get_all_sessions() -> List[Dict[str, any]]:
    """Return all known sessions."""
    return list(_sessions)


async def get_session(session_type: str) -> Optional[Dict[str, any]]:
    """Retrieve an available session of the requested type."""
    for sess in _sessions:
        if sess.get("type") == session_type and not sess.get("is_active"):
            sess["is_active"] = True
            sess["last_used"] = time.time()
            return sess
    return None


def release_session(session_id: int) -> None:
    """Mark a session as no longer active."""
    for sess in _sessions:
        if sess.get("id") == session_id:
            sess["is_active"] = False
            break


def delete_session(session_id: int) -> Tuple[bool, str]:
    """Remove a session from storage."""
    global _sessions
    count_before = len(_sessions)
    _sessions = [s for s in _sessions if s.get("id") != session_id]
    if len(_sessions) < count_before:
        return True, "deleted"
    return False, "session not found"


def remove_inactive_sessions() -> int:
    """Remove sessions that are not active."""
    global _sessions
    inactive = [s for s in _sessions if not s.get("is_active")]
    _sessions = [s for s in _sessions if s.get("is_active")]
    return len(inactive)


def cleanup_invalid_sessions() -> int:
    """Placeholder for cleaning invalid sessions."""
    # In this simplified implementation we have nothing to do
    return 0


def close_all_sessions() -> None:
    """Mark all sessions as inactive."""
    for sess in _sessions:
        sess["is_active"] = False


# simple API to add sessions for placeholder/demo usage
def _add_session(session_string: str, session_type: str = Constants.SESSION_TYPE_CLEAN) -> int:
    global _next_id
    sess = {
        "id": _next_id,
        "session_string": session_string,
        "type": session_type,
        "is_active": False,
        "last_used": 0,
    }
    _next_id += 1
    _sessions.append(sess)
    return sess["id"]


# expose a singleton-like accessor for external modules
class SessionManager:
    def __init__(self) -> None:
        pass

    async def get_session(self, session_type: str) -> Optional[Dict[str, any]]:
        return await get_session(session_type)

    def release_session(self, session_id: int) -> None:
        release_session(session_id)

    def get_all_sessions(self) -> List[Dict[str, any]]:
        return get_all_sessions()

    def delete_session(self, session_id: int) -> Tuple[bool, str]:
        return delete_session(session_id)

    def remove_inactive_sessions(self) -> int:
        return remove_inactive_sessions()

    def cleanup_invalid_sessions(self) -> int:
        return cleanup_invalid_sessions()

    def close_all_sessions(self) -> None:
        close_all_sessions()


session_manager = SessionManager()

