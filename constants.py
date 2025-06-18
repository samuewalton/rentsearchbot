"""
מודול constants - קבועים גלובליים עבור המערכת
"""

import os
from enum import Enum

class Constants:
    """
    קבועים גלובליים
    """
    # טיפוסי נכסים
    ASSET_TYPE_BOT = "bot"
    ASSET_TYPE_CHANNEL = "channel"
    ASSET_TYPE_GROUP = "group"
    
    # סטטוסים של השכרה
    RENTAL_STATUS_PENDING = "pending"
    RENTAL_STATUS_ACTIVE = "active"
    RENTAL_STATUS_MONITORING = "monitoring"
    RENTAL_STATUS_EXPIRING = "expiring"
    RENTAL_STATUS_EXPIRED = "expired"
    RENTAL_STATUS_CANCELED = "canceled"
    RENTAL_STATUS_ARCHIVED = "archived"
    
    # רמות נכסים
    TIER_PREMIUM = "premium"
    TIER_REGULAR = "regular"
    TIER_UNAVAILABLE = "unavailable"
    
    # סיומת מיוחדת לאינדוקס מהיר בטלגרם
    SPECIAL_SUFFIX = "@@@@@@"
    
    # תיקיות מערכת
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    SESSION_DIR = os.path.join(DATA_DIR, "session")
    LOGS_DIR = os.path.join(BASE_DIR, "logs")
    
    # סוגי סשנים
    SESSION_TYPE_CLEAN = "clean"
    SESSION_TYPE_DIRTY = "dirty"
    SESSION_TYPE_MANAGER = "manager"
    
    # זמנים (בשניות)
    SESSION_COOLDOWN = 600  # 10 דקות בין שימושים
    RANK_CACHE_TTL = 86400  # 24 שעות לשמירת דירוג ב-cache
    EXPIRY_REMINDER_HOURS = 3  # שעות לפני פקיעת תוקף לשלוח תזכורת
    LAST_MINUTE_REMINDER = 900  # 15 דקות לפני פקיעת תוקף
    PAYMENT_EXPIRY_HOURS = 4  # שעות עד לביטול הזמנה ללא תשלום
    ARCHIVE_DAYS = 30  # ימים עד לארכוב השכרות שהסתיימו
    WATCHDOG_INTERVAL = 7200  # בדיקת watchdog כל שעתיים (7200 שניות)
    FINAL_REMINDER_MINUTES = 15  # דקות לפני סיום להודעה אחרונה
    
    # טיימאאוט
    API_TIMEOUT = 30  # שניות לפני timeout בקריאת API
    
    # מחירים
    PRICE_TIER_PREMIUM = {
        1: 150,  # דירוג 1 - $150
        2: 125,  # דירוג 2 - $125
        3: 100   # דירוג 3 - $100
    }
    PRICE_TIER_REGULAR = 50  # דירוג 4-7 - $50
    
    # כללי מערכת
    MAX_RETRIES = 3  # מספר נסיונות מקסימלי לפעולות API
    MIN_SESSIONS_REQUIRED = 5  # מינימום סשנים נדרשים לפעילות תקינה
    DEFAULT_REFUND_PERCENT = 70  # החזר כספי ברירת מחדל באחוזים (70%)
    RANK_REGULAR_MAX = 7  # דירוג מקסימלי לרמה רגילה
    
    # API טלגרם
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    
    # רשימת מנהלים (מזהי טלגרם)
    ADMIN_IDS = [6771760911]  # מזהה האדמין האמיתי
    
    # סוגי התראות
    NOTIFICATION_TYPE_RENTAL_EXPIRING = "rental_expiring"
    NOTIFICATION_TYPE_RENTAL_EXPIRED = "rental_expired"
    NOTIFICATION_TYPE_RANK_DROP = "rank_drop"
    NOTIFICATION_TYPE_SYSTEM = "system"
    
    # הגדרות בוט
    BOT_USERNAME = "RentSpotBot"
    BOT_COMMAND_PREFIX = "/"
    
    @staticmethod
    def get_tier_for_rank(rank):
        """מחזיר את רמת הנכס לפי הדירוג"""
        if 1 <= rank <= 3:
            return Constants.TIER_PREMIUM
        elif 4 <= rank <= Constants.RANK_REGULAR_MAX:
            return Constants.TIER_REGULAR
        else:
            return Constants.TIER_UNAVAILABLE
    
    @staticmethod
    def get_price_for_rank(rank):
        """מחזיר את המחיר לפי הדירוג"""
        if 1 <= rank <= 3:
            return Constants.PRICE_TIER_PREMIUM.get(rank, 100)
        elif 4 <= rank <= Constants.RANK_REGULAR_MAX:
            return Constants.PRICE_TIER_REGULAR
        else:
            return 0
