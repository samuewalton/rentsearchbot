import json
import os
import logging
from typing import Dict, Tuple, List, Any, Optional
import random

from constants import Constants

logger = logging.getLogger(__name__)

class APIManager:
    """
    מנהל מפתחות API של טלגרם
    """
    
    # מפתחות API מחולקים לקבוצות לפי שימוש
    API_GROUPS = {
        'clean_sessions': [],      # סשנים נקיים לבדיקת דירוג
        'dirty_sessions': [],      # סשנים לשינוי שמות
        'manager_sessions': [],    # סשנים עם הרשאות ניהול
        'default': []              # ברירת מחדל
    }
    
    @classmethod
    def initialize(cls) -> None:
        """
        טוען מפתחות API מקובץ קונפיגורציה
        """
        try:
            config_path = os.path.join(Constants.DATA_DIR, 'api_keys.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    
                    for group_name, keys in data.items():
                        if group_name in cls.API_GROUPS:
                            cls.API_GROUPS[group_name] = keys
                
                logger.info(f"נטענו {sum(len(keys) for keys in cls.API_GROUPS.values())} מפתחות API")
            else:
                # יצירת קובץ ברירת מחדל עם מפתחות לדוגמה
                default_keys = {
                    'clean_sessions': [
                        {"api_id": 1234567, "api_hash": "0123456789abcdef0123456789abcdef"}
                    ],
                    'dirty_sessions': [
                        {"api_id": 2345678, "api_hash": "abcdef0123456789abcdef0123456789"}
                    ],
                    'manager_sessions': [
                        {"api_id": 3456789, "api_hash": "cdef0123456789abcdef0123456789ab"}
                    ],
                    'default': [
                        {"api_id": 4567890, "api_hash": "def0123456789abcdef0123456789abc"}
                    ]
                }
                
                os.makedirs(Constants.DATA_DIR, exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump(default_keys, f, indent=2)
                
                for group_name, keys in default_keys.items():
                    if group_name in cls.API_GROUPS:
                        cls.API_GROUPS[group_name] = keys
                
                logger.warning("נוצר קובץ מפתחות API לדוגמה. יש להחליפם במפתחות אמיתיים.")
        except Exception as e:
            logger.error(f"שגיאה בטעינת מפתחות API: {str(e)}")
    
    @classmethod
    def get_api_credentials(cls, group: str = 'default') -> Tuple[int, str]:
        """
        מחזיר מפתחות API אקראיים מקבוצה מסוימת
        
        Args:
            group: שם הקבוצה ('clean_sessions', 'dirty_sessions', 'manager_sessions', 'default')
            
        Returns:
            (api_id, api_hash)
        """
        # וודא שיש מפתחות זמינים
        if not any(cls.API_GROUPS.values()):
            cls.initialize()
        
        # אם הקבוצה ריקה, השתמש בברירת מחדל
        api_keys = cls.API_GROUPS.get(group, [])
        if not api_keys:
            api_keys = cls.API_GROUPS.get('default', [])
        
        if not api_keys:
            # אם אין מפתחות בכלל, השתמש במפתחות לדוגמה
            logger.warning("אין מפתחות API זמינים, משתמש במפתחות לדוגמה")
            return 12345678, "0123456789abcdef0123456789abcdef"
        
        # בחר מפתח אקראי
        key = random.choice(api_keys)
        return key["api_id"], key["api_hash"]
    
    @classmethod
    def add_api_key(cls, group: str, api_id: int, api_hash: str) -> bool:
        """
        מוסיף מפתח API חדש לקבוצה
        
        Args:
            group: שם הקבוצה
            api_id: מזהה API
            api_hash: מפתח API
            
        Returns:
            True אם ההוספה הצליחה, False אחרת
        """
        try:
            if group not in cls.API_GROUPS:
                logger.error(f"קבוצה לא קיימת: {group}")
                return False
            
            # בדוק אם המפתח כבר קיים
            for key in cls.API_GROUPS[group]:
                if key["api_id"] == api_id and key["api_hash"] == api_hash:
                    logger.warning(f"מפתח API כבר קיים בקבוצה {group}")
                    return True
            
            # הוסף את המפתח
            cls.API_GROUPS[group].append({"api_id": api_id, "api_hash": api_hash})
            
            # שמור לקובץ
            config_path = os.path.join(Constants.DATA_DIR, 'api_keys.json')
            with open(config_path, 'w') as f:
                json.dump(cls.API_GROUPS, f, indent=2)
            
            logger.info(f"נוסף מפתח API חדש לקבוצה {group}")
            return True
        except Exception as e:
            logger.error(f"שגיאה בהוספת מפתח API: {str(e)}")
            return False
    
    @classmethod
    def remove_api_key(cls, group: str, api_id: int) -> bool:
        """
        מסיר מפתח API מקבוצה
        """
        try:
            if group not in cls.API_GROUPS:
                logger.error(f"קבוצה לא קיימת: {group}")
                return False
            
            # מצא את המפתח לפי api_id
            keys = cls.API_GROUPS[group]
            for i, key in enumerate(keys):
                if key["api_id"] == api_id:
                    # הסר את המפתח
                    cls.API_GROUPS[group].pop(i)
                    
                    # שמור לקובץ
                    config_path = os.path.join(Constants.DATA_DIR, 'api_keys.json')
                    with open(config_path, 'w') as f:
                        json.dump(cls.API_GROUPS, f, indent=2)
                    
                    logger.info(f"הוסר מפתח API מקבוצה {group}")
                    return True
            
            logger.warning(f"מפתח API עם מזהה {api_id} לא נמצא בקבוצה {group}")
            return False
        except Exception as e:
            logger.error(f"שגיאה בהסרת מפתח API: {str(e)}")
            return False
    
    @classmethod
    def get_all_api_keys(cls) -> Dict[str, List[Dict[str, Any]]]:
        """
        מחזיר את כל מפתחות ה-API
        """
        # וודא שיש מפתחות זמינים
        if not any(cls.API_GROUPS.values()):
            cls.initialize()
            
        return cls.API_GROUPS


# אתחול בטעינת המודול
if os.path.exists(os.path.join(Constants.DATA_DIR, 'api_keys.json')):
    APIManager.initialize()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("API Manager module loaded successfully")
