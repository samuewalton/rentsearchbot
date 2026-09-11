# -*- coding: utf-8 -*-
"""Session management — DB-backed (S4).

סמנטיקה:
  * status='active' = תקין וזמין לשימוש; banned/inactive = לא בשימוש
  * in_use = תפוס כרגע (checkout). שחרור חובה בסיום (release_session)
  * cooldown: סשן שנוצל לא יוחזר שוב לפני SESSION_COOLDOWN שניות
  * checkout שנתקע (קריסה בלי release) משתחרר אוטומטית אחרי שעה
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from constants import Constants
from db import get_connection

logger = logging.getLogger(__name__)

# checkout שלא שוחרר (קריסה) נחשב פנוי אחרי שעה
STUCK_CHECKOUT_SECONDS = 3600


def _row_to_session(row: Any) -> Dict[str, Any]:
    """ממיר שורת DB למילון סשן (כולל מפתחות תאימות ל-callers)."""
    d = dict(row)
    last_used = d.get("last_used")
    if hasattr(last_used, "timestamp"):
        d["last_used"] = last_used.timestamp()
    elif last_used is None:
        d["last_used"] = 0
    d["is_active"] = d.get("status") == "active"
    d["in_use"] = bool(d.get("in_use"))
    return d


class Session:
    """ייצוג רשומת סשן."""

    @staticmethod
    def load_all() -> List[Dict[str, Any]]:
        """טוען את כל הסשנים מה-DB."""
        return get_all_sessions()


def get_all_sessions() -> List[Dict[str, Any]]:
    """מחזיר את כל הסשנים שבמערכת."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM sessions ORDER BY id ASC")
                return [_row_to_session(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"שגיאה בקבלת סשנים: {e}")
        return []


async def get_session(session_type: str) -> Optional[Dict[str, Any]]:
    """שולף סשן פנוי מהסוג המבוקש ומסמן אותו תפוס (in_use).

    פנוי = פעיל + לא תפוס (או תקוע) + עבר cooldown מאז שימוש אחרון.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM sessions
                    WHERE type = %s AND status = 'active'
                      AND (in_use = FALSE OR last_used IS NULL
                           OR last_used < NOW() - make_interval(secs => %s))
                      AND (last_used IS NULL
                           OR last_used < NOW() - make_interval(secs => %s))
                    ORDER BY last_used ASC NULLS FIRST
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """,
                    (
                        session_type,
                        STUCK_CHECKOUT_SECONDS,
                        Constants.SESSION_COOLDOWN,
                    ),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    """
                    UPDATE sessions
                    SET in_use = TRUE, last_used = NOW(), updated_at = NOW()
                    WHERE id = %s
                    """,
                    (row["id"],),
                )
                d = _row_to_session(row)
                d["in_use"] = True
                return d
    except Exception as e:
        logger.error(f"שגיאה בקבלת סשן: {e}")
        return None


def release_session(session_id: int) -> None:
    """משחרר סשן תפוס."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sessions SET in_use = FALSE WHERE id = %s",
                    (session_id,),
                )
    except Exception as e:
        logger.error(f"שגיאה בשחרור סשן {session_id}: {e}")


def delete_session(session_id: int) -> Tuple[bool, str]:
    """מוחק סשן מהמאגר."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
                if cur.rowcount > 0:
                    return True, "deleted"
                return False, "session not found"
    except Exception as e:
        logger.error(f"שגיאה במחיקת סשן {session_id}: {e}")
        return False, str(e)


def remove_inactive_sessions() -> int:
    """מוחק סשנים בסטטוס inactive. מחזיר כמות."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE status = 'inactive'")
                return cur.rowcount or 0
    except Exception as e:
        logger.error(f"שגיאה בהסרת סשנים לא פעילים: {e}")
        return 0


def cleanup_invalid_sessions() -> int:
    """מוחק סשנים בלי מחרוזת התחברות. מחזיר כמות."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions "
                    "WHERE session_string IS NULL OR session_string = ''"
                )
                return cur.rowcount or 0
    except Exception as e:
        logger.error(f"שגיאה בניקוי סשנים לא תקינים: {e}")
        return 0


def close_all_sessions() -> None:
    """משחרר את כל ה-checkouts (לקריאה בכיבוי)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE sessions SET in_use = FALSE WHERE in_use = TRUE")
    except Exception as e:
        logger.error(f"שגיאה בשחרור סשנים: {e}")


def _add_session(
    session_string: str,
    session_type: str = Constants.SESSION_TYPE_CLEAN,
    api_id: Optional[int] = None,
    api_hash: Optional[str] = None,
) -> int:
    """מוסיף סשן ל-DB. מחזיר id (0 בכשלון)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sessions
                        (session_string, type, status, api_id, api_hash)
                    VALUES (%s, %s, 'active', %s, %s)
                    RETURNING id
                    """,
                    (session_string, session_type, api_id, api_hash),
                )
                row = cur.fetchone()
                return row["id"] if row else 0
    except Exception as e:
        logger.error(f"שגיאה בהוספת סשן: {e}")
        return 0


def add_session(
    session_string: str,
    session_type: str = Constants.SESSION_TYPE_CLEAN,
    api_id: Optional[int] = None,
    api_hash: Optional[str] = None,
) -> int:
    """מוסיף סשן חדש למאגר ומחזיר את המזהה שלו."""
    if not session_string or not session_string.strip():
        raise ValueError("session_string must be a non-empty string")
    return _add_session(session_string.strip(), session_type, api_id, api_hash)


class SessionManager:
    """מעטפת מחלקתית ל-API המודולרי."""

    def __init__(self) -> None:
        pass

    def add_session(
        self,
        session_string: str,
        session_type: str = Constants.SESSION_TYPE_CLEAN,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
    ) -> int:
        return add_session(session_string, session_type, api_id, api_hash)

    async def get_session(self, session_type: str) -> Optional[Dict[str, Any]]:
        return await get_session(session_type)

    def release_session(self, session_id: int) -> None:
        release_session(session_id)

    def get_all_sessions(self) -> List[Dict[str, Any]]:
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
