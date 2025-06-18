"""
מודול db - ניהול חיבור למסד נתונים PostgreSQL
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor, RealDictRow
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple, Union, cast

logger = logging.getLogger(__name__)

# מחרוזת חיבור למסד נתונים - מה-.env
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:admin@localhost:5432/rank_system"
)


# מנהל חיבורים למסד הנתונים
@contextmanager
def get_connection():
    """
    יוצר חיבור למסד הנתונים ומחזיר אותו כ-context manager

    Returns:
        חיבור למסד הנתונים
    """
    connection = None
    try:
        connection = psycopg2.connect(
            DATABASE_URL, cursor_factory=RealDictCursor
        )
        yield connection
    except psycopg2.Error as e:
        logger.error(f"שגיאה בהתחברות למסד הנתונים: {str(e)}")
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.commit()
            connection.close()


def execute_query(
    query: str, params: Optional[Tuple[Any, ...]] = None
) -> Optional[List[RealDictRow]]:
    """
    מבצע שאילתת PostgreSQL ומחזיר את התוצאות

    Args:
        query: שאילתת PostgreSQL
        params: פרמטרים לשאילתה

    Returns:
        רשימת תוצאות כ-RealDictRow (שמתנהגות כמו Dict), או None אם היתה שגיאה
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if query.strip().upper().startswith("SELECT"):
                    results = cur.fetchall()
                    # Since we're using RealDictCursor, results should be
                    # List[RealDictRow]
                    # Cast to the correct type for type checker
                    return cast(List[RealDictRow], results) if results else []
                return None
    except Exception as e:
        logger.error(f"שגיאה בביצוע שאילתה: {str(e)}")
        logger.error(f"שאילתה: {query}")
        logger.error(f"פרמטרים: {params}")
        return None


def execute_query_dict(
    query: str, params: Optional[Tuple[Any, ...]] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    מבצע שאילתת PostgreSQL ומחזיר את התוצאות כרשימת מילונים

    Args:
        query: שאילתת PostgreSQL
        params: פרמטרים לשאילתה

    Returns:
        רשימת תוצאות כמילונים רגילים, או None אם היתה שגיאה
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if query.strip().upper().startswith("SELECT"):
                    results = cur.fetchall()
                    if results:
                        # Convert RealDictRow to regular dict
                        return [dict(row) for row in results]
                    return []
                return None
    except Exception as e:
        logger.error(f"שגיאה בביצוע שאילתה: {str(e)}")
        logger.error(f"שאילתה: {query}")
        logger.error(f"פרמטרים: {params}")
        return None


def execute_single_query(
    query: str, params: Optional[Tuple[Any, ...]] = None
) -> Optional[Dict[str, Any]]:
    """
    מבצע שאילתת PostgreSQL ומחזיר תוצאה יחידה

    Args:
        query: שאילתת PostgreSQL
        params: פרמטרים לשאילתה

    Returns:
        תוצאה יחידה כמילון, או None אם לא נמצאה תוצאה או היתה שגיאה
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if query.strip().upper().startswith("SELECT"):
                    result = cur.fetchone()
                    return dict(result) if result else None
                return None
    except Exception as e:
        logger.error(f"שגיאה בביצוע שאילתה יחידה: {str(e)}")
        logger.error(f"שאילתה: {query}")
        logger.error(f"פרמטרים: {params}")
        return None


def execute_transaction(queries: List[Dict[str, Any]]) -> bool:
    """
    מבצע מספר שאילתות בטרנזקציה אחת

    Args:
        queries: רשימת מילונים עם שאילתות ופרמטרים
                כל מילון צריך להכיל את המפתחות 'query' ו-'params'

    Returns:
        האם הטרנזקציה הושלמה בהצלחה
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for query_data in queries:
                    query = query_data.get("query")
                    params = query_data.get("params")
                    if query is None:
                        logger.error("שאילתה חסרה בטרנזקציה")
                        return False
                    cur.execute(query, params)
        return True
    except Exception as e:
        logger.error(f"שגיאה בביצוע טרנזקציה: {str(e)}")
        return False


def init_database():
    """
    אתחול מסד נתונים PostgreSQL - יצירת טבלאות אם הן לא קיימות

    Returns:
        האם האתחול הצליח
    """
    try:
        # טעינת קובץ הסכמה
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        # ביצוע השאילתות
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)

        logger.info("מסד הנתונים אותחל בהצלחה")
        return True
    except Exception as e:
        logger.error(f"שגיאה באתחול מסד הנתונים: {str(e)}")
        return False


def check_connection() -> bool:
    """
    בדיקת חיבור למסד נתונים PostgreSQL

    Returns:
        האם החיבור תקין
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return True
    except Exception as e:
        logger.error(f"שגיאה בבדיקת חיבור למסד הנתונים: {str(e)}")
        return False


def get_setting(key: str, default: Any = None) -> Any:
    """
    קבלת ערך הגדרה ממסד נתונים PostgreSQL

    Args:
        key: מפתח ההגדרה
        default: ערך ברירת מחדל

    Returns:
        ערך ההגדרה
    """
    try:
        result = execute_single_query(
            "SELECT value FROM settings WHERE key = %s", (key,)
        )
        if result:
            return result["value"]
        return default
    except Exception as e:
        logger.error(f"שגיאה בקבלת הגדרה {key}: {str(e)}")
        return default


def set_setting(key: str, value: str) -> bool:
    """
    עדכון ערך הגדרה במסד נתונים PostgreSQL

    Args:
        key: מפתח ההגדרה
        value: ערך ההגדרה

    Returns:
        האם העדכון הצליח
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO settings (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE
                    SET value = %s, updated_at = NOW()
                    """,
                    (key, value, value),
                )
                return True
    except Exception as e:
        logger.error(f"שגיאה בעדכון הגדרה {key}: {str(e)}")
        return False
