"""
מודול user_manager - ניהול משתמשים במערכת
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from constants import Constants

logger = logging.getLogger(__name__)

# זיכרון זמני למשתמשים כשאין DB
temp_users = {}

def get_user_by_telegram_id(telegram_id: int) -> Dict[str, Any]:
    """
    קבלת משתמש לפי מזהה טלגרם
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        
    Returns:
        פרטי המשתמש או None אם לא נמצא
    """
    try:
        from db import execute_query
        query = """
        SELECT * FROM users WHERE telegram_id = %s
        """
        
        result = execute_query(query, (telegram_id,))
        
        if result and len(result) > 0:
            return result[0]
    except Exception as e:
        logger.warning(f"DB לא זמין, משתמש בזיכרון זמני: {e}")
        # fallback לזיכרון זמני
        return temp_users.get(telegram_id)
    
    return None

def create_user(telegram_id: int, username: str, first_name: str, 
               last_name: str = "", language_code: str = "en") -> Dict[str, Any]:
    """
    יצירת משתמש חדש
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        username: שם משתמש בטלגרם
        first_name: שם פרטי
        last_name: שם משפחה
        language_code: קוד שפה
        
    Returns:
        פרטי המשתמש החדש
    """
    # בדיקה אם המשתמש כבר קיים
    existing_user = get_user_by_telegram_id(telegram_id)
    if existing_user:
        return existing_user
    
    try:
        from db import execute_query
        # יצירת משתמש חדש בDB
        query = """
        INSERT INTO users (telegram_id, username, first_name, last_name, language_code)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """
        
        params = (telegram_id, username or "", first_name or "", last_name or "", language_code or "en")
        result = execute_query(query, params)
        
        if result and len(result) > 0:
            logger.info(f"נוצר משתמש חדש בDB: {telegram_id} - {first_name} {last_name}")
            return result[0]
    except Exception as e:
        logger.warning(f"DB לא זמין, יוצר משתמש בזיכרון זמני: {e}")
        # fallback לזיכרון זמני
        from datetime import datetime
        user_data = {
            'telegram_id': telegram_id,
            'username': username or "",
            'first_name': first_name or "",
            'last_name': last_name or "",
            'language_code': language_code or "en",
            'balance': 0.0,
            'is_admin': telegram_id in Constants.ADMIN_IDS,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        temp_users[telegram_id] = user_data
        logger.info(f"נוצר משתמש חדש בזיכרון: {telegram_id} - {first_name} {last_name}")
        return user_data
    
    logger.error(f"שגיאה ביצירת משתמש: {telegram_id}")
    return None

def update_user(telegram_id: int, **kwargs) -> bool:
    """
    עדכון פרטי משתמש
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        **kwargs: פרמטרים לעדכון
        
    Returns:
        האם העדכון הצליח
    """
    if not kwargs:
        return False
    
    try:
        from db import execute_query
        # יצירת חלקי השאילתה
        set_parts = []
        params = []
        
        for key, value in kwargs.items():
            if key in ['username', 'first_name', 'last_name', 'language_code', 'balance', 'is_admin']:
                set_parts.append(f"{key} = %s")
                params.append(value)
        
        if not set_parts:
            return False
        
        # השלמת השאילתה
        query = f"""
        UPDATE users SET {', '.join(set_parts)}, updated_at = NOW()
        WHERE telegram_id = %s
        """
        
        params.append(telegram_id)
        result = execute_query(query, tuple(params))
        
        return result is not None
    except Exception as e:
        logger.warning(f"DB לא זמין, מעדכן בזיכרון זמני: {e}")
        # fallback לזיכרון זמני
        if telegram_id in temp_users:
            for key, value in kwargs.items():
                if key in ['username', 'first_name', 'last_name', 'language_code', 'balance', 'is_admin']:
                    temp_users[telegram_id][key] = value
            from datetime import datetime
            temp_users[telegram_id]['updated_at'] = datetime.now()
            return True
        return False

def get_user_balance(telegram_id: int) -> float:
    """
    קבלת יתרת משתמש
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        
    Returns:
        יתרת המשתמש
    """
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        return 0.0
    
    return float(user['balance']) if user['balance'] is not None else 0.0

def update_user_balance(telegram_id: int, amount: float, transaction_type: str = 'manual_adjustment', 
                        rental_id: int = None, notes: str = "") -> Tuple[bool, float]:
    """
    עדכון יתרת משתמש ותיעוד עסקה
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        amount: סכום לעדכון (חיובי להפקדה, שלילי למשיכה)
        transaction_type: סוג העסקה ('payment', 'refund', 'manual_adjustment')
        rental_id: מזהה השכרה (אם רלוונטי)
        notes: הערות
        
    Returns:
        האם העדכון הצליח ויתרה חדשה
    """
    # קבלת פרטי המשתמש
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        logger.error(f"ניסיון לעדכן יתרה של משתמש לא קיים: {telegram_id}")
        return False, 0.0
    
    # חישוב יתרה חדשה
    current_balance = float(user['balance']) if user['balance'] is not None else 0.0
    new_balance = current_balance + amount
    
    try:
        from db import execute_transaction
        # עדכון יתרה ותיעוד העסקה
        queries = [
            {
                'query': """
                UPDATE users SET balance = %s, updated_at = NOW()
                WHERE telegram_id = %s
                """,
                'params': (new_balance, telegram_id)
            },
            {
                'query': """
                INSERT INTO transactions 
                (user_id, user_telegram_id, amount, transaction_type, rental_id, notes)
                VALUES 
                ((SELECT id FROM users WHERE telegram_id = %s), %s, %s, %s, %s, %s)
                """,
                'params': (telegram_id, telegram_id, amount, transaction_type, rental_id, notes)
            }
        ]
        
        success = execute_transaction(queries)
        
        if success:
            logger.info(f"עודכנה יתרת משתמש {telegram_id}: {current_balance} -> {new_balance}, סכום: {amount}")
            return True, new_balance
    except Exception as e:
        logger.warning(f"DB לא זמין, מעדכן יתרה בזיכרון זמני: {e}")
        # fallback לזיכרון זמני
        if telegram_id in temp_users:
            temp_users[telegram_id]['balance'] = new_balance
            from datetime import datetime
            temp_users[telegram_id]['updated_at'] = datetime.now()
            logger.info(f"עודכנה יתרת משתמש בזיכרון {telegram_id}: {current_balance} -> {new_balance}, סכום: {amount}")
            return True, new_balance
    
    logger.error(f"שגיאה בעדכון יתרת משתמש {telegram_id}")
    return False, current_balance

def get_user_transactions(telegram_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    קבלת היסטוריית עסקאות משתמש
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        limit: מספר עסקאות מקסימלי להחזרה
        
    Returns:
        רשימת עסקאות
    """
    try:
        from db import execute_query
        query = """
        SELECT * FROM transactions 
        WHERE user_telegram_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        
        result = execute_query(query, (telegram_id, limit))
        
        if result:
            return result
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל עסקאות: {e}")
    
    return []

def get_user_rentals(user_id: int, statuses: List[str] = None) -> List[Dict[str, Any]]:
    """
    קבלת השכרות של משתמש
    
    Args:
        user_id: מזהה טלגרם של המשתמש
        statuses: סטטוסים לסינון (אופציונלי)
        
    Returns:
        רשימת השכרות
    """
    try:
        from db import execute_query
        params = [user_id]
        
        # בניית שאילתה בהתאם לסינון סטטוסים
        if statuses and len(statuses) > 0:
            status_placeholders = ', '.join(['%s'] * len(statuses))
            query = f"""
            SELECT * FROM rentals 
            WHERE user_telegram_id = %s AND status IN ({status_placeholders})
            ORDER BY created_at DESC
            """
            params.extend(statuses)
        else:
            query = """
            SELECT * FROM rentals 
            WHERE user_telegram_id = %s
            ORDER BY created_at DESC
            """
        
        result = execute_query(query, tuple(params))
        
        if result:
            return result
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל השכרות: {e}")
    
    return []

def get_user_rental_history(user_id: int, rental_id: int = None) -> List[Dict[str, Any]]:
    """
    קבלת היסטוריית השכרות של משתמש
    
    Args:
        user_id: מזהה טלגרם של המשתמש
        rental_id: מזהה השכרה (אופציונלי לפילטור)
        
    Returns:
        רשימת היסטוריית השכרות
    """
    try:
        from db import execute_query
        params = [user_id]
        
        if rental_id:
            query = """
            SELECT rh.* FROM rental_history rh
            JOIN rentals r ON rh.rental_id = r.id
            WHERE r.user_telegram_id = %s AND r.id = %s
            ORDER BY rh.created_at DESC
            """
            params.append(rental_id)
        else:
            query = """
            SELECT rh.* FROM rental_history rh
            JOIN rentals r ON rh.rental_id = r.id
            WHERE r.user_telegram_id = %s
            ORDER BY rh.created_at DESC
            """
        
        result = execute_query(query, tuple(params))
        
        if result:
            return result
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל היסטוריית השכרות: {e}")
    
    return []

def user_exists(telegram_id: int) -> bool:
    """
    בדיקה האם משתמש קיים
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        
    Returns:
        האם המשתמש קיים
    """
    try:
        from db import execute_query
        query = """
        SELECT COUNT(*) as count FROM users WHERE telegram_id = %s
        """
        
        result = execute_query(query, (telegram_id,))
        
        if result and result[0]['count'] > 0:
            return True
    except Exception as e:
        logger.warning(f"DB לא זמין, בודק בזיכרון זמני: {e}")
        return telegram_id in temp_users
    
    return False

def is_admin(telegram_id: int) -> bool:
    """
    בדיקה האם משתמש הוא מנהל
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        
    Returns:
        האם המשתמש הוא מנהל
    """
    # בדיקה אם המשתמש בתוך רשימת המנהלים הקבועה
    if telegram_id in Constants.ADMIN_IDS:
        return True
    
    try:
        from db import execute_query
        # בדיקה בדטאבייס
        query = """
        SELECT is_admin FROM users WHERE telegram_id = %s
        """
        
        result = execute_query(query, (telegram_id,))
        
        if result and result[0]['is_admin']:
            return True
    except Exception as e:
        logger.warning(f"DB לא זמין, בודק מזיכרון זמני: {e}")
        # fallback לזיכרון זמני
        user = temp_users.get(telegram_id)
        if user and user.get('is_admin', False):
            return True
    
    return False

def get_all_users() -> List[Dict[str, Any]]:
    """
    קבלת כל המשתמשים
    
    Returns:
        רשימת כל המשתמשים
    """
    try:
        from db import execute_query
        query = """
        SELECT * FROM users ORDER BY created_at DESC
        """
        
        result = execute_query(query)
        
        if result:
            return result
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל רשימת משתמשים: {e}")
    
    return []

def get_active_users_count() -> int:
    """
    קבלת מספר משתמשים פעילים (עם השכרות פעילות)
    
    Returns:
        מספר משתמשים פעילים
    """
    try:
        from db import execute_query
        query = """
        SELECT COUNT(DISTINCT user_telegram_id) as count
        FROM rentals
        WHERE status IN ('pending', 'active', 'monitoring', 'expiring')
        """
        
        result = execute_query(query)
        
        if result:
            return result[0]['count']
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל מספר משתמשים פעילים: {e}")
    
    return 0

def get_user_spending_statistics(telegram_id: int) -> Dict[str, Any]:
    """
    קבלת סטטיסטיקות הוצאות משתמש
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        
    Returns:
        סטטיסטיקות הוצאות
    """
    try:
        from db import execute_query
        query = """
        SELECT 
            SUM(CASE WHEN t.transaction_type = 'payment' THEN t.amount ELSE 0 END) as total_spent,
            COUNT(DISTINCT r.id) as total_rentals,
            COUNT(DISTINCT r.keyword) as unique_keywords
        FROM transactions t
        LEFT JOIN rentals r ON t.rental_id = r.id
        WHERE t.user_telegram_id = %s
        """
        
        result = execute_query(query, (telegram_id,))
        
        if result:
            stats = result[0]
            # המרה לערכים ברירת מחדל אם אין תוצאות
            stats['total_spent'] = float(stats['total_spent']) if stats['total_spent'] else 0
            stats['total_rentals'] = int(stats['total_rentals']) if stats['total_rentals'] else 0
            stats['unique_keywords'] = int(stats['unique_keywords']) if stats['unique_keywords'] else 0
            return stats
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל סטטיסטיקות: {e}")
    
    return {
        'total_spent': 0,
        'total_rentals': 0,
        'unique_keywords': 0
    }

def get_total_system_revenue() -> float:
    """
    קבלת סך הכנסות המערכת
    
    Returns:
        סך הכנסות
    """
    try:
        from db import execute_query
        query = """
        SELECT SUM(amount) as total FROM transactions 
        WHERE transaction_type = 'payment'
        """
        
        result = execute_query(query)
        
        if result and result[0]['total']:
            return float(result[0]['total'])
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל הכנסות: {e}")
    
    return 0.0

def get_daily_revenue() -> Dict[str, float]:
    """
    קבלת הכנסות יומיות ב-7 ימים אחרונים
    
    Returns:
        מילון של תאריך -> הכנסה
    """
    try:
        from db import execute_query
        query = """
        SELECT 
            DATE(created_at) as day,
            SUM(amount) as revenue
        FROM transactions
        WHERE 
            transaction_type = 'payment' 
            AND created_at >= NOW() - INTERVAL '7 days'
        GROUP BY day
        ORDER BY day
        """
        
        result = execute_query(query)
        
        daily_revenue = {}
        
        if result:
            for row in result:
                day_str = row['day'].strftime('%Y-%m-%d')
                daily_revenue[day_str] = float(row['revenue'])
        
        return daily_revenue
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לקבל הכנסות יומיות: {e}")
    
    return {}

def update_user_preferences(telegram_id: int, preferences: Dict[str, Any]) -> bool:
    """
    עדכון העדפות משתמש
    
    Args:
        telegram_id: מזהה טלגרם של המשתמש
        preferences: מילון העדפות לעדכון
        
    Returns:
        האם העדכון הצליח
    """
    try:
        from db import execute_query
        # המרת העדפות ל-JSON
        import json
        prefs_json = json.dumps(preferences)
        
        query = """
        UPDATE users SET preferences = %s, updated_at = NOW()
        WHERE telegram_id = %s
        """
        
        result = execute_query(query, (prefs_json, telegram_id))
        
        return result is not None
    except Exception as e:
        logger.warning(f"DB לא זמין, לא ניתן לעדכן העדפות: {e}")
        return False

# יצירת מופע סינגלטון של מנהל המשתמשים
class UserManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_user(self, telegram_id):
        return get_user_by_telegram_id(telegram_id)
    
    def create_user(self, **kwargs):
        return create_user(**kwargs)
    
    def update_user(self, telegram_id, **kwargs):
        return update_user(telegram_id, **kwargs)
    
    def get_user_balance(self, telegram_id):
        return get_user_balance(telegram_id)
    
    def update_user_balance(self, telegram_id, amount, **kwargs):
        return update_user_balance(telegram_id, amount, **kwargs)
    
    def get_user_rentals(self, telegram_id, **kwargs):
        return get_user_rentals(telegram_id, **kwargs)
    
    def get_user_stats(self, telegram_id):
        return get_user_spending_statistics(telegram_id)
    
    def is_admin(self, telegram_id):
        return is_admin(telegram_id)
    
    def get_admin_users(self):
        try:
            from db import execute_query
            query = """
            SELECT * FROM users WHERE is_admin = TRUE
            """
            return execute_query(query) or []
        except Exception as e:
            logger.warning(f"DB לא זמין, לא ניתן לקבל רשימת מנהלים: {e}")
            return []

user_manager = UserManager()
