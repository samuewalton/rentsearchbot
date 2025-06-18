import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple

from db import get_connection
from constants import Constants

logger = logging.getLogger(__name__)

class AssetsManager:
    """
    מנהל נכסים - ניהול נכסים (בוטים, קבוצות, ערוצים) במערכת
    """
    
    # סוגי נכסים
    ASSET_TYPE_BOT = 'bot'         # בוט טלגרם
    ASSET_TYPE_CHANNEL = 'channel'  # ערוץ טלגרם
    ASSET_TYPE_GROUP = 'group'      # קבוצה בטלגרם
    
    def __init__(self):
        """
        יוצר מנהל נכסים חדש
        """
        # שמות מקוריים של נכסים (לפני שינוי שם)
        self.original_names = {}  # {asset_id: original_name}
    
    def get_asset(self, asset_id: int) -> Dict[str, Any]:
        """
        מקבל מידע על נכס ספציפי
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            פרטי הנכס או None אם לא נמצא
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT *
                        FROM assets
                        WHERE id = %s
                    """, (asset_id,))
                    
                    asset = cur.fetchone()
                    if asset:
                        return dict(asset)
                    return None
                    
        except Exception as e:
            logger.error(f"שגיאה בקבלת מידע על נכס {asset_id}: {str(e)}")
            return None
    
    def get_available_assets(self, asset_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        מקבל רשימת נכסים זמינים
        
        Args:
            asset_type: סוג הנכס (אופציונלי)
            limit: מספר נכסים מקסימלי להחזרה
            
        Returns:
            רשימת נכסים זמינים
        """
        try:
            # הוסף תנאי סוג נכס אם הוגדר
            type_condition = ""
            params = [True, limit]  # נכסים זמינים + הגבלת מספר תוצאות
            
            if asset_type:
                type_condition = "AND type = %s"
                params.insert(1, asset_type)
            
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT *
                        FROM assets
                        WHERE available = %s
                        {type_condition}
                        ORDER BY name ASC
                        LIMIT %s
                    """, tuple(params))
                    
                    assets = cur.fetchall()
                    return [dict(asset) for asset in assets] if assets else {}
                    
        except Exception as e:
            logger.error(f"שגיאה בקבלת רשימת נכסים זמינים: {str(e)}")
            return {}
    
    def add_asset(self, telegram_id: int, name: str, type: str, 
                 description: str = None, tags: List[str] = None, 
                 available: bool = True, bot_token: str = None) -> int:
        """
        מוסיף נכס חדש למערכת
        
        Args:
            telegram_id: מזהה הנכס בטלגרם
            name: שם הנכס
            type: סוג הנכס (bot/channel/group)
            description: תיאור הנכס
            tags: תגיות
            available: האם הנכס זמין להשכרה
            bot_token: טוקן הבוט (רק לנכסים מסוג bot)
            
        Returns:
            מזהה הנכס החדש במערכת או 0 אם נכשל
        """
        try:
            # וידוא סוג נכס תקין
            valid_types = [self.ASSET_TYPE_BOT, self.ASSET_TYPE_CHANNEL, self.ASSET_TYPE_GROUP]
            if type not in valid_types:
                logger.error(f"סוג נכס לא חוקי: {type}")
                return 0
            
            # המרת רשימת תגיות לפורמט PostgreSQL array
            if tags:
                # PostgreSQL array format with proper escaping
                tags_array = '{' + ','.join(f'"{tag}"' for tag in tags) + '}'
            else:
                # Empty PostgreSQL array
                tags_array = '{}'
            
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO assets
                        (telegram_id, asset_id, name, original_name, type, tags, available, bot_token, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        RETURNING id
                    """, (
                        telegram_id, str(telegram_id), name, name, type, tags_array, available, bot_token
                    ))
                    
                    asset_id = cur.fetchone()['id']
                    
                    # שמור את השם המקורי
                    self.original_names[asset_id] = name
                    
                    return asset_id
                    
        except Exception as e:
            logger.error(f"שגיאה בהוספת נכס חדש: {str(e)}")
            return 0
    
    def update_asset(self, asset_id: int, **kwargs) -> bool:
        """
        מעדכן פרטי נכס קיים
        
        Args:
            asset_id: מזהה הנכס
            **kwargs: פרמטרים לעדכון (name, description, tags, priority, is_available)
            
        Returns:
            האם העדכון הצליח
        """
        try:
            # בדוק אם הנכס קיים
            asset = self.get_asset(asset_id)
            if not asset:
                logger.error(f"נכס עם מזהה {asset_id} לא נמצא")
                return False
            
            # בנה את רשימת השדות לעדכון
            fields = []
            params = []
            
            for key, value in kwargs.items():
                if key in ['name', 'description', 'type', 'priority', 'is_available', 'telegram_id']:
                    fields.append(f"{key} = %s")
                    params.append(value)
                elif key == 'tags' and isinstance(value, list):
                    fields.append("tags = %s")
                    # Convert to PostgreSQL array format
                    if value:
                        tags_array = '{' + ','.join(f'"{tag}"' for tag in value) + '}'
                    else:
                        tags_array = '{}'
                    params.append(tags_array)
            
            if not fields:
                logger.warning("לא נמצאו שדות לעדכון")
                return False
            
            # הוסף את מזהה הנכס
            params.append(asset_id)
            
            # בנה את השאילתה
            update_query = f"""
                UPDATE assets
                SET {', '.join(fields)}, updated_at = NOW()
                WHERE id = %s
            """
            
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(update_query, tuple(params))
                    
                    # אם עדכנו את השם, עדכן גם את השם המקורי
                    if 'name' in kwargs:
                        self.original_names[asset_id] = kwargs['name']
                    
                    return True
                    
        except Exception as e:
            logger.error(f"שגיאה בעדכון נכס {asset_id}: {str(e)}")
            return False
    
    def set_asset_availability(self, asset_id: int, is_available: bool) -> bool:
        """
        מעדכן זמינות של נכס
        
        Args:
            asset_id: מזהה הנכס
            is_available: האם הנכס זמין להשכרה
            
        Returns:
            האם העדכון הצליח
        """
        return self.update_asset(asset_id, is_available=is_available)
    
    def mark_asset_as_available(self, asset_id: int) -> bool:
        """
        מסמן נכס כזמין להשכרה
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            האם העדכון הצליח
        """
        return self.set_asset_availability(asset_id, True)
    
    def mark_asset_as_unavailable(self, asset_id: int) -> bool:
        """
        מסמן נכס כלא זמין להשכרה
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            האם העדכון הצליח
        """
        return self.set_asset_availability(asset_id, False)
    
    def update_asset_tags(self, asset_id: int, tags: List[str]) -> bool:
        """
        מעדכן תגיות של נכס
        
        Args:
            asset_id: מזהה הנכס
            tags: רשימת תגיות חדשה
            
        Returns:
            האם העדכון הצליח
        """
        return self.update_asset(asset_id, tags=tags)
    
    def delete_asset(self, asset_id: int) -> bool:
        """מוחק נכס מהמערכת"""
        # Implementation exists elsewhere in file
        pass
    
    def get_all_assets(self) -> List[Dict[str, Any]]:
        """
        מחזיר רשימת כל הנכסים במערכת
        """
        try:
            from db import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, telegram_id, type, status, available, created_at
                        FROM assets
                        ORDER BY created_at DESC
                    """)
                    
                    assets = []
                    for row in cur.fetchall():
                        assets.append({
                            'id': row['id'],
                            'name': row['name'],
                            'telegram_id': row['telegram_id'],
                            'type': row['type'],
                            'status': row['status'],
                            'available': bool(row['available']),
                            'created_at': row['created_at']
                        })
                    
                    return assets
                    
        except Exception as e:
            logger.error(f'Error getting all assets: {e}')
            return []

    def cleanup_inactive_assets(self) -> int:
        """
        מנקה נכסים לא פעילים
        """
        try:
            from db import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # מחיקת נכסים שלא פעילים במשך 30 יום
                    cur.execute("""
                        DELETE FROM assets
                        WHERE available = false
                        AND created_at < NOW() - INTERVAL '30 days'
                    """)
                    
                    deleted_count = cur.rowcount
                    # Commit handled by context manager
                    
                    logger.info(f'Cleaned up {deleted_count} inactive assets')
                    return deleted_count
                    
        except Exception as e:
            logger.error(f'Error cleaning inactive assets: {e}')
            return 0

        """
        מוחק נכס מהמערכת
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            האם המחיקה הצליחה
        """
        try:
            # בדוק אם הנכס קיים
            asset = self.get_asset(asset_id)
            if not asset:
                logger.error(f"נכס עם מזהה {asset_id} לא נמצא")
                return False
            
            # בדוק אם הנכס בשימוש בהשכרות פעילות
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) as count
                        FROM rentals
                        WHERE asset_id = %s
                        AND status IN ('pending', 'active', 'monitoring', 'expiring')
                    """, (asset_id,))
                    
                    result = cur.fetchone()
                    active_rentals = result['count'] if result else 0
                    
                    if active_rentals > 0:
                        logger.error(f"לא ניתן למחוק נכס {asset_id} כי הוא בשימוש ב-{active_rentals} השכרות פעילות")
                        return False
                    
                    # מחק את הנכס
                    cur.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
                    
                    # הסר מרשימת השמות המקוריים
                    if asset_id in self.original_names:
                        del self.original_names[asset_id]
                    
                    return True
                    
        except Exception as e:
            logger.error(f"שגיאה במחיקת נכס {asset_id}: {str(e)}")
            return False
    
    def search_assets(self, query: str, asset_type: str = None) -> List[Dict[str, Any]]:
        """
        מחפש נכסים לפי מילות מפתח בשם, תיאור או תגיות
        
        Args:
            query: מחרוזת חיפוש
            asset_type: סוג נכס (אופציונלי)
            
        Returns:
            רשימת נכסים תואמים
        """
        try:
            type_condition = ""
            params = [f"%{query}%", f"%{query}%"]  # עבור שם ותיאור
            
            if asset_type:
                type_condition = "AND type = %s"
                params.append(asset_type)
            
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                        SELECT *
                        FROM assets
                        WHERE (name ILIKE %s OR tags::text ILIKE %s)
                        {type_condition}
                        ORDER BY name ASC
                    """, params + [f"%{query}%"])  # הוספת פרמטר עבור tags
                    
                    assets = cur.fetchall()
                    return [dict(asset) for asset in assets] if assets else []
                    
        except Exception as e:
            logger.error(f"שגיאה בחיפוש נכסים: {str(e)}")
            return []
    
    def get_asset_original_name(self, asset_id: int) -> str:
        """
        מקבל את השם המקורי של נכס
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            השם המקורי של הנכס או None אם לא נמצא
        """
        # בדוק אם השם נמצא במטמון
        if asset_id in self.original_names:
            return self.original_names[asset_id]
        
        # אחרת, קבל מהמסד
        asset = self.get_asset(asset_id)
        if asset:
            self.original_names[asset_id] = asset['name']
            return asset['name']
        
        return None
    
    def get_asset_stats(self, asset_id: int) -> Dict[str, Any]:
        """
        מקבל סטטיסטיקות על נכס
        
        Args:
            asset_id: מזהה הנכס
            
        Returns:
            מילון עם סטטיסטיקות (מספר השכרות, זמן שימוש וכו')
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # מספר השכרות היסטוריות
                    cur.execute("""
                        SELECT COUNT(*) as total_rentals,
                               COUNT(CASE WHEN status IN ('active', 'monitoring', 'expiring') THEN 1 END) as active_rentals,
                               COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_rentals,
                               COUNT(CASE WHEN status = 'canceled' THEN 1 END) as canceled_rentals,
                               SUM(CASE WHEN status IN ('expired', 'archived') THEN duration_hours ELSE 0 END) as total_hours,
                               SUM(CASE WHEN status IN ('expired', 'archived') THEN price ELSE 0 END) as total_revenue
                        FROM rentals
                        WHERE asset_id = %s
                    """, (asset_id,))
                    
                    stats = dict(cur.fetchone() or {})
                    
                    # השכרה אחרונה
                    cur.execute("""
                        SELECT keyword, tier, rank, price, created_at
                        FROM rentals
                        WHERE asset_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (asset_id,))
                    
                    last_rental = cur.fetchone()
                    if last_rental:
                        stats['last_rental'] = dict(last_rental)
                    
                    return stats
                    
        except Exception as e:
            logger.error(f"שגיאה בקבלת סטטיסטיקות לנכס {asset_id}: {str(e)}")
            return {}

        """
        מחזיר רשימת כל הנכסים במערכת
        """
        try:
            from db import get_connection
            cur.execute("""
                SELECT id, name, telegram_id, type, status, available, created_at
                FROM assets
                ORDER BY created_at DESC
            """)
            
            assets = []
            for row in cur.fetchall():
                assets.append({
                    'id': row[0],
                    'name': row[1],
                    'telegram_id': row[2],
                    'type': row[3],
                    'status': row[4],
                    'available': bool(row[5]),
                    'created_at': row[6]
                })
            
            return assets
            
        except Exception as e:
            logger.error(f'Error getting all assets: {e}')
            return []

        """
        מנקה נכסים לא פעילים
        """
        try:
            from db import get_connection
            
            # מחיקת נכסים שלא פעילים במשך 30 יום
            cur.execute("""
                DELETE FROM assets
                WHERE available = 0
                AND last_activity < datetime('now', '-30 days')
            """)
            
            deleted_count = cur.rowcount
            # commit handled by context manager
            
            logger.info(f'Cleaned up {deleted_count} inactive assets')
            return deleted_count
            
        except Exception as e:
            logger.error(f'Error cleaning inactive assets: {e}')
            return 0
    
    def remove_asset(self, asset_id: int) -> bool:
        """
        מוחק נכס מהמערכת
        
        Args:
            asset_id: מזהה הנכס למחיקה
            
        Returns:
            True אם הנכס נמחק בהצלחה, False אחרת
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # בדיקה שהנכס קיים
                    cur.execute("SELECT id FROM assets WHERE id = %s", (asset_id,))
                    if not cur.fetchone():
                        logger.warning(f"Asset {asset_id} not found for removal")
                        return False
                    
                    # מחיקת הנכס
                    cur.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
                    
                    if cur.rowcount > 0:
                        logger.info(f"Asset {asset_id} removed successfully")
                        return True
                    else:
                        logger.warning(f"No rows affected when removing asset {asset_id}")
                        return False
                        
        except Exception as e:
            logger.error(f'Error removing asset {asset_id}: {e}')
            return False
    
    def remove_assets(self, asset_ids: List[int]) -> Tuple[int, int]:
        """
        מוחק מספר נכסים בבת אחת
        
        Args:
            asset_ids: רשימת מזהי נכסים למחיקה
            
        Returns:
            (deleted_count, failed_count) - מספר נכסים שנמחקו ונכשלו
        """
        deleted_count = 0
        failed_count = 0
        
        for asset_id in asset_ids:
            if self.remove_asset(asset_id):
                deleted_count += 1
            else:
                failed_count += 1
                
        return deleted_count, failed_count

    def remove_all_assets(self) -> Tuple[int, int]:
        """
        מוחק את כל הנכסים במערכת
        
        Returns:
            (deleted_count, failed_count) - מספר נכסים שנמחקו ונכשלו
        """
        try:
            # קבלת כל הנכסים
            assets = self.get_all_assets()
            asset_ids = [asset['id'] for asset in assets]
            
            # מחיקת כל הנכסים
            return self.remove_assets(asset_ids)
            
        except Exception as e:
            logger.error(f'Error removing all assets: {e}')
            return 0, len(self.get_all_assets())

    # ...existing code...


# יצירת אינסטנס לשימוש מחוץ למודול
assets_manager = AssetsManager()