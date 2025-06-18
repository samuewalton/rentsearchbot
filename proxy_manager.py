import json
import os
import logging
import time
import random
import requests
from typing import Optional, Dict, List, Any, Tuple

from db import get_connection
from constants import Constants

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    מנהל את פול הפרוקסים עבור סשנים של טלגרם
    """
    
    def __init__(self):
        self.proxies = []
        self.last_check = {}  # מעקב אחרי זמן הבדיקה האחרון לכל פרוקסי
        self.load_proxies()
    
    def load_proxies(self) -> None:
        """
        טוען את הפרוקסים מבסיס הנתונים
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM proxies
                        WHERE status = 'active'
                        ORDER BY speed ASC NULLS LAST
                    """)
                    
                    result = cur.fetchall()
                    if result:
                        self.proxies = [dict(row) for row in result]
                        logger.info(f"נטענו {len(self.proxies)} פרוקסים")
                    else:
                        # אם אין פרוקסים, טען מקובץ גיבוי
                        self._load_from_json()
        except Exception as e:
            logger.error(f"שגיאה בטעינת פרוקסים מ-DB: {str(e)}")
            # נסה לטעון מקובץ גיבוי
            self._load_from_json()
    
    def _load_from_json(self) -> None:
        """
        טוען פרוקסים מקובץ JSON
        """
        try:
            json_path = os.path.join(Constants.DATA_DIR, 'proxies.json')
            
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    self.proxies = data
                    logger.info(f"נטענו {len(self.proxies)} פרוקסים מקובץ JSON")
            else:
                # אם אין קובץ, צור רשימת ברירת מחדל ריקה
                self.proxies = []
                self._save_to_json()
                logger.warning("לא נמצאו פרוקסים. נוצר קובץ ריק.")
        except Exception as e:
            logger.error(f"שגיאה בטעינת פרוקסים מ-JSON: {str(e)}")
            self.proxies = []
    
    def _save_to_json(self) -> None:
        """
        שומר פרוקסים לקובץ JSON (לגיבוי)
        """
        try:
            json_path = os.path.join(Constants.DATA_DIR, 'proxies.json')
            os.makedirs(Constants.DATA_DIR, exist_ok=True)
            
            with open(json_path, 'w') as f:
                json.dump(self.proxies, f, indent=2)
                
            logger.info(f"נשמרו {len(self.proxies)} פרוקסים לקובץ JSON")
        except Exception as e:
            logger.error(f"שגיאה בשמירת פרוקסים ל-JSON: {str(e)}")
    
    def get_proxy(self, dc_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        מחזיר פרוקסי זמין
        
        Args:
            dc_id: אופציונלי, DC מועדף
            
        Returns:
            מילון עם נתוני פרוקסי או None אם אין זמין
        """
        if not self.proxies:
            self.load_proxies()
            if not self.proxies:
                logger.error("אין פרוקסים זמינים")
                return None
        
        # אם יש dc_id, נסה למצוא פרוקסי מתאים
        if dc_id:
            suitable_proxies = [p for p in self.proxies if p.get('dc_id') == dc_id and p.get('status') == 'active']
            if suitable_proxies:
                return random.choice(suitable_proxies)
        
        # אחרת בחר פרוקסי אקראי מהפעילים
        active_proxies = [p for p in self.proxies if p.get('status') == 'active']
        if active_proxies:
            return random.choice(active_proxies)
        
        # אם אין פעילים, נסה לרענן את המצב ובחר אחד כלשהו
        self.check_all_proxies()
        return random.choice(self.proxies) if self.proxies else None
    
    def format_proxy(self, proxy_data: Dict[str, Any]) -> Dict[str, str]:
        """
        מפרמט פרוקסי לפורמט שטלגרם מצפה לו
        
        Returns:
            {
                'proxy_type': 'socks5',
                'addr': '1.2.3.4',
                'port': 1234,
                'username': 'user',
                'password': 'pass'
            }
        """
        proxy_type = proxy_data.get('type', 'socks5')  # ברירת מחדל לסוג socks5
        
        formatted = {
            'proxy_type': proxy_type,
            'addr': proxy_data['ip'],
            'port': proxy_data['port']
        }
        
        # הוסף פרטי אימות אם יש
        if proxy_data.get('user'):
            formatted['username'] = proxy_data['user']
        if proxy_data.get('pass'):
            formatted['password'] = proxy_data['pass']
            
        return formatted
    
    def add_proxy(self, ip: str, port: int, proxy_type: str = 'socks5', 
                 username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        מוסיף פרוקסי חדש
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # בדוק אם כבר קיים
                    cur.execute("""
                        SELECT id FROM proxies
                        WHERE ip = %s AND port = %s
                    """, (ip, port))
                    
                    if cur.fetchone():
                        logger.warning(f"פרוקסי {ip}:{port} כבר קיים")
                        return False
                    
                    # הוסף את הפרוקסי
                    cur.execute("""
                        INSERT INTO proxies (ip, port, "user", "pass", type, status)
                        VALUES (%s, %s, %s, %s, %s, 'active')
                        RETURNING id
                    """, (ip, port, username, password, proxy_type))
                    
                    proxy_id = cur.fetchone()['id']
                    
                    # הוסף לרשימה בזיכרון
                    self.proxies.append({
                        'id': proxy_id,
                        'ip': ip,
                        'port': port,
                        'user': username,
                        'pass': password,
                        'type': proxy_type,
                        'status': 'active'
                    })
                    
                    # בדוק את הפרוקסי החדש
                    self.check_proxy_speed(proxy_id)
                    
                    # שמור למקרה של קריסה
                    self._save_to_json()
                    
                    return True
        except Exception as e:
            logger.error(f"שגיאה בהוספת פרוקסי: {str(e)}")
            return False
    
    def remove_proxy(self, proxy_id: int) -> bool:
        """
        מסיר פרוקסי
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE proxies
                        SET status = 'removed'
                        WHERE id = %s
                    """, (proxy_id,))
                    
                    # הסר מהרשימה בזיכרון
                    self.proxies = [p for p in self.proxies if p.get('id') != proxy_id]
                    
                    # שמור למקרה של קריסה
                    self._save_to_json()
                    
                    return True
        except Exception as e:
            logger.error(f"שגיאה בהסרת פרוקסי: {str(e)}")
            return False
    
    def check_proxy_speed(self, proxy_id: int) -> Optional[int]:
        """
        בודק מהירות של פרוקסי ספציפי
        
        Returns:
            מהירות במילישניות או None אם נכשל
        """
        try:
            # מצא את הפרוקסי ברשימה
            proxy = next((p for p in self.proxies if p.get('id') == proxy_id), None)
            if not proxy:
                logger.error(f"פרוקסי עם מזהה {proxy_id} לא נמצא")
                return None
            
            # בנה את מחרוזת הפרוקסי לפי הסוג
            proxy_type = proxy.get('type', 'socks5')
            proxy_auth = ''
            if proxy.get('user') and proxy.get('pass'):
                proxy_auth = f"{proxy['user']}:{proxy['pass']}@"
            
            proxy_str = f"{proxy_type}://{proxy_auth}{proxy['ip']}:{proxy['port']}"
            
            # בדוק מהירות
            proxies = {
                'http': proxy_str,
                'https': proxy_str
            }
            
            start_time = time.time()
            try:
                # בדוק מהירות באמצעות בקשת HTTP לאתר אמין
                r = requests.get('https://www.google.com', proxies=proxies, timeout=10)
                if r.status_code == 200:
                    speed_ms = int((time.time() - start_time) * 1000)
                    
                    # עדכן בבסיס נתונים
                    with get_connection() as conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE proxies
                                SET speed = %s, status = 'active', last_check = NOW(), fail_count = 0
                                WHERE id = %s
                            """, (speed_ms, proxy_id))
                    
                    # עדכן ברשימה בזיכרון
                    proxy['speed'] = speed_ms
                    proxy['status'] = 'active'
                    proxy['fail_count'] = 0
                    
                    logger.info(f"פרוקסי {proxy['ip']}:{proxy['port']} פעיל. מהירות: {speed_ms}ms")
                    return speed_ms
                else:
                    raise Exception(f"סטטוס לא תקין: {r.status_code}")
            except Exception as e:
                # עדכן שגיאה
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE proxies
                            SET status = 'error', last_check = NOW(), fail_count = fail_count + 1
                            WHERE id = %s
                        """, (proxy_id,))
                
                # עדכן ברשימה בזיכרון
                proxy['status'] = 'error'
                proxy['fail_count'] = proxy.get('fail_count', 0) + 1
                
                logger.warning(f"פרוקסי {proxy['ip']}:{proxy['port']} נכשל: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"שגיאה בבדיקת מהירות פרוקסי: {str(e)}")
            return None
    
    def check_all_proxies(self) -> Tuple[int, int]:
        """
        בודק את כל הפרוקסים
        
        Returns:
            (מספר פרוקסים פעילים, מספר פרוקסים שנכשלו)
        """
        active_count = 0
        failed_count = 0
        
        for proxy in self.proxies:
            proxy_id = proxy.get('id')
            if proxy_id:
                result = self.check_proxy_speed(proxy_id)
                if result is not None:
                    active_count += 1
                else:
                    failed_count += 1
        
        # עדכן את הקובץ
        self._save_to_json()
        
        return active_count, failed_count
    
    def get_all_proxies(self) -> List[Dict[str, Any]]:
        """
        מחזיר את כל הפרוקסים
        """
        return self.proxies
    
    def get_active_proxies_count(self) -> int:
        """
        מחזיר את מספר הפרוקסים הפעילים
        """
        return len([p for p in self.proxies if p.get('status') == 'active'])
        
    def get_proxy_for_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        מחזיר פרוקסי המתאים לסשן מסוים
        
        Args:
            session_id: מזהה הסשן
            
        Returns:
            מילון עם נתוני פרוקסי או None אם אין מתאים
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # קבל את פרטי הפרוקסי המשויך לסשן
                    cur.execute("""
                        SELECT p.* FROM proxies p
                        JOIN sessions s ON s.proxy_id = p.id
                        WHERE s.id = %s AND p.status = 'active'
                    """, (session_id,))
                    
                    proxy_data = cur.fetchone()
                    if proxy_data:
                        # השתמש בשמות העמודות החדשים
                        return {
                            'id': proxy_data['id'],
                            'ip': proxy_data['ip'],
                            'port': proxy_data['port'],
                            'type': proxy_data['type'],
                            'user': proxy_data['user'],
                            'pass': proxy_data['pass'],
                            'status': proxy_data['status']
                        }
            
            # אם לא נמצא פרוקסי ספציפי, החזר פרוקסי אקראי
            return self.get_proxy()
            
        except Exception as e:
            logger.error(f"שגיאה בקבלת פרוקסי לסשן {session_id}: {str(e)}")
            return None

    def delete_inactive_proxies(self) -> int:
        """
        מוחק פרוקסיים לא פעילים
        """
        try:
            deleted_count = 0
            
            # בדיקת פרוקסיים וסמן אלו שלא עובדים
            for i, proxy_data in enumerate(self.proxies):
                if not self._test_proxy_connection(proxy_data):
                    self.proxies.remove(proxy_data)
                    deleted_count += 1
            
            # שמירת השינויים (handled by database)
            
            logger.info(f'Deleted {deleted_count} inactive proxies')
            return deleted_count
            
        except Exception as e:
            logger.error(f'Error deleting inactive proxies: {e}')
            return 0

    def cleanup_dead_proxies(self) -> int:
        """
        מנקה פרוקסיים מתים
        """
        try:
            deleted_count = 0
            
            # בדיקת כל הפרוקסיים
            for proxy_id, proxy_data in list(self.proxies.items()):
                # אם הפרוקסי לא עבד במשך זמן רב
                if (proxy_data.get('failed_attempts', 0) > 5 or
                    proxy_data.get('status') == 'dead'):
                    del self.proxies[proxy_id]
                    deleted_count += 1
            
            # שמירת השינויים
            self._save_proxies()
            
            logger.info(f'Cleaned up {deleted_count} dead proxies')
            return deleted_count
            
        except Exception as e:
            logger.error(f'Error cleaning dead proxies: {e}')
            return 0

    def _test_proxy_connection(self, proxy_data: Dict[str, Any]) -> bool:
        """
        בודק אם פרוקסי עובד
        """
        try:
            import requests
            import socket
            
            proxy_url = f"http://{proxy_data.get('ip')}:{proxy_data.get('port')}"
            proxies = {'http': proxy_url, 'https': proxy_url}
            
            # בדיקה מהירה
            response = requests.get('http://httpbin.org/ip', 
                                  proxies=proxies, timeout=5)
            return response.status_code == 200
            
        except Exception:
            return False



# יצירת אינסטנס לשימוש מחוץ למודול
proxy_manager = ProxyManager()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Proxy Manager module loaded successfully")