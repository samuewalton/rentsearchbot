import logging
import threading
import time
import datetime
import asyncio
from typing import List, Dict, Any, Optional, Union

from db import get_connection
from constants import Constants
from rank_checker import rank_checker
from rental_manager import rental_manager
from notifications import notification_manager
from utils import AsyncHelper

logger = logging.getLogger(__name__)

class Watchdog:
    """
    מנגנון מעקב אחר השכרות פעילות ובדיקת דירוגים בזמן אמת
    """
    
    def __init__(self):
        # מילון של השכרות במעקב
        self.monitored_rentals = {}  # {rental_id: rental}
        
        # מידע על בדיקה אחרונה לכל השכרה
        self.last_check = {}  # {rental_id: {"rank": X, "tier": Y, "time": datetime}}
        
        # קצב בדיקות (בשניות)
        self.check_interval = Constants.WATCHDOG_INTERVAL
        
        # מצב ריצה
        self.is_running = False
        
        # האם להמשיך לרוץ
        self.should_continue = True
        
        # חוט ריצה
        self.thread = None
    
    def get_active_rentals(self) -> List[Dict[str, Any]]:
        """
        מקבל את כל ההשכרות הפעילות שצריך לנטר
        
        Returns:
            רשימת השכרות פעילות
        """
        # Get all rentals with active statuses
        active_rentals = []
        
        # Collect rentals for each status
        active_rentals.extend(rental_manager.get_rentals_by_status(Constants.RENTAL_STATUS_ACTIVE))
        active_rentals.extend(rental_manager.get_rentals_by_status(Constants.RENTAL_STATUS_MONITORING))
        active_rentals.extend(rental_manager.get_rentals_by_status(Constants.RENTAL_STATUS_EXPIRING))
        
        return active_rentals
    
    def update_monitored_rentals(self):
        """
        מעדכן את רשימת ההשכרות במעקב
        """
        # קבל את כל ההשכרות הפעילות
        active_rentals = self.get_active_rentals()
        active_rental_ids = [rental['id'] for rental in active_rentals]
        
        # עדכן את המילון
        self.monitored_rentals = {rental['id']: rental for rental in active_rentals}
        
        # הסר השכרות שהסתיימו
        for rental_id in list(self.last_check.keys()):
            if rental_id not in active_rental_ids:
                del self.last_check[rental_id]
    
    def check_monitored_rentals(self):
        """
        בודק את הדירוג של כל ההשכרות במעקב
        """
        rentals_to_check = []
        now = datetime.datetime.now()
        
        # צור רשימה של השכרות לבדיקה
        for rental_id, rental in self.monitored_rentals.items():
            # בדוק אם חלף זמן מספיק מהבדיקה האחרונה
            last_check_time = self.last_check.get(rental_id, {}).get('time')
            
            # אם אין בדיקה קודמת או חלף מספיק זמן
            if not last_check_time or (now - last_check_time).total_seconds() >= self.check_interval:
                rentals_to_check.append(rental_id)
        
        # עבור כל השכרה, בצע בדיקת דירוג
        for rental_id in rentals_to_check:
            # קורא לפונקציה אסינכרונית מתוך קוד סינכרוני באמצעות AsyncHelper
            try:
                # יוצר קורוטינה ומעביר אותה ל-AsyncHelper
                coro = self._check_rental_rank(rental_id)
                AsyncHelper.run_async(coro)
            except Exception as e:
                logger.error(f"שגיאה בבדיקת דירוג להשכרה {rental_id}: {str(e)}")
        
        # בדוק השכרות שעומדות לפוג בקרוב
        self.check_expiring_rentals()
    
    async def _check_rental_rank(self, rental_id: int):
        """
        בודק את הדירוג של השכרה ספציפית
        
        Args:
            rental_id: מזהה ההשכרה
        """
        try:
            # קבל את ההשכרה
            rental = rental_manager.get_rental(rental_id)
            if not rental:
                logger.warning(f"לא נמצאה השכרה עם מזהה {rental_id}")
                return
            
            # בדוק את הדירוג הנוכחי של הנכס
            rank, tier, error = await rank_checker.check_asset_rank(
                asset_id=rental['asset_id'],
                keyword=rental['keyword']
            )
            
            if error:
                logger.error(f"שגיאה בבדיקת דירוג להשכרה {rental_id}: {error}")
                return
            
            # קבל מידע על הבדיקה הקודמת (אם יש)
            previous = self.last_check.get(rental_id, {})
            previous_rank = previous.get('rank')
            previous_tier = previous.get('tier')
            
            # עדכן את זמן הבדיקה האחרונה
            self.last_check[rental_id] = {
                'rank': rank,
                'tier': tier,
                'time': datetime.datetime.now()
            }
            
            # אם הדירוג ירד משמעותית (שינוי Tier), טפל בזה
            if previous_rank and previous_tier:
                if (tier != previous_tier and previous_tier == Constants.TIER_PREMIUM) or \
                   (rank > previous_rank and (rank > Constants.RANK_REGULAR_MAX or previous_rank <= Constants.RANK_REGULAR_MAX)):
                    await self._handle_rank_drop(rental, previous_rank, previous_tier, rank, tier)
            
        except Exception as e:
            logger.error(f"שגיאה בבדיקת דירוג להשכרה {rental_id}: {str(e)}")
    
    async def _handle_rank_drop(self, rental: Dict[str, Any], previous_rank: int, previous_tier: str, new_rank: int, new_tier: str):
        """
        מטפל בירידת דירוג משמעותית
        
        Args:
            rental: פרטי ההשכרה
            previous_rank: דירוג קודם
            previous_tier: Tier קודם
            new_rank: דירוג חדש
            new_tier: Tier חדש
        """
        try:
            # הוסף התראה למשתמש
            notification_manager.add_notification(
                user_id=rental['user_id'],
                notification_type="rank_dropped",
                title="ירידה בדירוג השכרה",
                message=(
                    f"הדירוג של ההשכרה שלך עבור המילה '{rental['keyword']}' ירד "
                    f"מדירוג {previous_rank} ({previous_tier}) לדירוג {new_rank} ({new_tier})"
                )
            )
            
                # אם הדירוג ירד אבל עדיין בטווח תקין, עדכן את סטטוס ההשכרה
            if new_tier != Constants.TIER_UNAVAILABLE:
                # עדכן את סטטוס ההשכרה ל-MONITORING
                # update_rental_status אינה פונקציה אסינכרונית - נקרא לה ישירות
                success, _ = rental_manager.update_rental_status(
                    rental_id=rental['id'],
                    new_status=Constants.RENTAL_STATUS_MONITORING
                )
                
                if not success:
                    logger.warning(f"לא הצלחנו לעדכן את סטטוס ההשכרה {rental['id']}")
            
            else:
                # נסה למצוא נכס חלופי
                replacement_asset = await self._find_replacement_asset(rental)
                
                if replacement_asset:
                    # נמצא נכס חלופי, נחליף את הנכס
                    success, error = await rental_manager.replace_rental_asset(
                        rental_id=rental['id'],
                        new_asset_id=replacement_asset['asset']['id'],
                        rank=replacement_asset['rank'],
                        tier=replacement_asset['tier']
                    )
                    
                    if not success:
                        logger.error(f"שגיאה בהחלפת נכס להשכרה {rental['id']}: {error}")
                        
                        # נודיע למשתמש על הבעיה
                        notification_manager.add_notification(
                            user_id=rental['user_id'],
                            notification_type="replacement_failed",
                            title="שגיאה בהחלפת נכס",
                            message=(
                                f"לא הצלחנו להחליף את הנכס בהשכרה שלך עבור המילה '{rental['keyword']}'. "
                                f"נבצע ניסיון נוסף בבדיקה הבאה."
                            )
                        )
                
                else:
                    # אין נכס חלופי, צריך להציע זיכוי או ביטול
                    notification_manager.add_notification(
                        user_id=rental['user_id'],
                        notification_type="refund_offer",
                        title="הצעת זיכוי להשכרה",
                        message=(
                            f"הדירוג של ההשכרה שלך עבור המילה '{rental['keyword']}' ירד משמעותית "
                            f"ולא נמצא נכס חלופי. ניתן לקבל זיכוי יחסי או להמשיך עם הנכס הקיים."
                        )
                    )
                    
                    # כרגע נמשיך עם הנכס הקיים
                    # update_rental_status אינה פונקציה אסינכרונית - נקרא לה ישירות
                    rental_manager.update_rental_status(
                        rental_id=rental['id'],
                        new_status=Constants.RENTAL_STATUS_MONITORING
                    )
        
        except Exception as e:
            logger.error(f"שגיאה בטיפול בירידת דירוג להשכרה {rental['id']}: {str(e)}")
    
    async def _find_replacement_asset(self, rental: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        מחפש נכס חלופי מתאים להחלפה
        
        Args:
            rental: פרטי ההשכרה
            
        Returns:
            פרטי הנכס החלופי או None אם לא נמצא
        """
        try:
            asset_data, _ = await rental_manager.get_suitable_asset_for_keyword(rental['keyword'])
            return asset_data
        except Exception as e:
            logger.error(f"שגיאה בחיפוש נכס חלופי להשכרה {rental['id']}: {str(e)}")
            return None
    
    def check_expiring_rentals(self):
        """
        בודק השכרות שעומדות לפוג בקרוב ושולח התראות
        """
        try:
            # בדוק השכרות שנגמרות תוך 3 שעות
            expiring_rentals = rental_manager.get_rentals_expiring_soon(Constants.EXPIRY_REMINDER_HOURS)
            
            for rental in expiring_rentals:
                # אם ההשכרה לא במצב EXPIRING, עדכן את הסטטוס
                if rental['status'] != Constants.RENTAL_STATUS_EXPIRING:
                    # עדכן את סטטוס ההשכרה
                    try:
                        # update_rental_status אינה פונקציה אסינכרונית - נקרא לה ישירות
                        success, _ = rental_manager.update_rental_status(
                            rental_id=rental['id'],
                            new_status=Constants.RENTAL_STATUS_EXPIRING
                        )
                    except Exception as e:
                        logger.error(f"שגיאה בעדכון סטטוס השכרה {rental['id']}: {str(e)}")
                        success = False
                    
                    if not success:
                        logger.warning(f"לא הצלחנו לעדכן את סטטוס ההשכרה {rental['id']} ל-EXPIRING")
                    
                    # חשב כמה שעות נותרו
                    end_time = rental.get('end_time')
                    if end_time:
                        now = datetime.datetime.now()
                        hours_left = (end_time - now).total_seconds() / 3600
                        
                        # שלח התראה למשתמש
                        notification_manager.add_notification(
                            user_id=rental['user_id'],
                            notification_type="rental_expiring",
                            title="השכרה עומדת להסתיים",
                            message=(
                                f"ההשכרה שלך עבור המילה '{rental['keyword']}' עומדת להסתיים בעוד {hours_left:.1f} שעות. "
                                f"האם ברצונך להאריך את ההשכרה?"
                            )
                        )
            
            # בדוק השכרות שנגמרות תוך 15 דקות
            very_soon_rentals = rental_manager.get_rentals_expiring_soon(int(Constants.FINAL_REMINDER_MINUTES / 60))
            
            for rental in very_soon_rentals:
                # אם ההשכרה במצב EXPIRING, שלח תזכורת אחרונה
                if rental['status'] == Constants.RENTAL_STATUS_EXPIRING:
                    # חשב כמה דקות נותרו
                    end_time = rental.get('end_time')
                    if end_time:
                        now = datetime.datetime.now()
                        minutes_left = (end_time - now).total_seconds() / 60
                        
                        # שלח התראה למשתמש
                        notification_manager.add_notification(
                            user_id=rental['user_id'],
                            notification_type="final_reminder",
                            title="תזכורת אחרונה להשכרה",
                            message=(
                                f"תזכורת אחרונה: ההשכרה שלך עבור המילה '{rental['keyword']}' "
                                f"עומדת להסתיים בעוד {minutes_left:.0f} דקות."
                            )
                        )
        except Exception as e:
            logger.error(f"שגיאה בבדיקת השכרות שעומדות לפוג: {str(e)}")
    
    def check_expired_rentals(self):
        """
        בודק השכרות שפג תוקפן ומסיים אותן
        """
        try:
            now = datetime.datetime.now()
            
            # שאילתה ישירה לבסיס הנתונים לקבלת השכרות שפג תוקפן
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT r.*, a.name as asset_name 
                        FROM rentals r
                        JOIN assets a ON r.asset_id = a.id
                        WHERE r.status IN (%s, %s, %s)
                        AND r.end_time < %s
                        ORDER BY r.end_time ASC
                    """, (
                        Constants.RENTAL_STATUS_ACTIVE,
                        Constants.RENTAL_STATUS_MONITORING,
                        Constants.RENTAL_STATUS_EXPIRING,
                        now
                    ))
                    
                    expired_rentals = [dict(row) for row in cur.fetchall()]
            
            # עבור על כל ההשכרות שפג תוקפן
            for rental in expired_rentals:
                # סיים את ההשכרה
                rental_id = rental['id']
                # הרץ את הפונקציה האסינכרונית באמצעות AsyncHelper
                try:
                    # יוצר קורוטינה ומעביר אותה ל-AsyncHelper
                    coro = rental_manager.expire_rental(rental_id)
                    success, error = AsyncHelper.run_async(coro)
                except Exception as e:
                    logger.error(f"שגיאה בהפעלת expire_rental: {str(e)}")
                    success, error = False, str(e)
                
                if not success:
                    logger.error(f"שגיאה בסיום השכרה {rental_id}: {error}")
                else:
                    logger.info(f"השכרה {rental_id} הסתיימה בהצלחה")
        
        except Exception as e:
            logger.error(f"שגיאה בבדיקת השכרות שפג תוקפן: {str(e)}")
    
    def archive_old_rentals(self, days_old: Optional[int] = None):
        """
        מעביר השכרות ישנות לארכיון
        
        Args:
            days_old: כמה ימים אחורה לארכב (ברירת מחדל לפי קבוע מערכת)
        """
        try:
            # Use the constant value if None was provided
            archive_days = Constants.ARCHIVE_DAYS if days_old is None else days_old
                
            # העבר לארכיון
            archived_count = rental_manager.archive_expired_rentals(archive_days)
            
            # Check if any rentals were archived
            if isinstance(archived_count, int) and archived_count > 0:
                logger.info(f"{archived_count} השכרות הועברו לארכיון")
        
        except Exception as e:
            logger.error(f"שגיאה בארכוב השכרות ישנות: {str(e)}")
    
    def start(self):
        """
        מתחיל את התהליך הרקעי של מעקב אחר השכרות
        """
        if self.is_running:
            logger.warning("Watchdog כבר רץ!")
            return
        
        self.should_continue = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        self.is_running = True
        
        logger.info("Watchdog החל לרוץ בהצלחה")
    
    def stop(self):
        """
        מפסיק את התהליך הרקעי
        """
        if not self.is_running:
            logger.warning("Watchdog לא רץ!")
            return
        
        self.should_continue = False
        if self.thread:
            self.thread.join(timeout=2.0)  # חכה עד 2 שניות לסיום החוט
        
        self.is_running = False
        logger.info("Watchdog נעצר בהצלחה")
    
    def run(self):
        """
        הלולאה המרכזית של התהליך הרקעי
        """
        logger.info("התחלת לולאת Watchdog")
        
        while self.should_continue:
            try:
                # עדכן את רשימת ההשכרות במעקב
                self.update_monitored_rentals()
                
                # בדוק דירוגים
                self.check_monitored_rentals()
                
                # בדוק השכרות שפג תוקפן
                self.check_expired_rentals()
                
                # בדוק ארכוב פעם ב-24 שעות (כל 12 מחזורים של שעתיים)
                if datetime.datetime.now().hour == 3:  # רץ בשעה 3 בלילה
                    self.archive_old_rentals()
                
            except Exception as e:
                logger.error(f"שגיאה בלולאת Watchdog: {str(e)}")
            
            # המתן לפני המחזור הבא
            sleep_interval = 60  # שינה של דקה בין בדיקות קטנות
            for _ in range(int(self.check_interval / sleep_interval)):
                if not self.should_continue:
                    break
                time.sleep(sleep_interval)
    
    def get_status(self) -> Dict[str, Any]:
        """
        מחזיר את הסטטוס הנוכחי של ה-Watchdog
        
        Returns:
            מילון עם נתוני סטטוס
        """
        return {
            "is_running": self.is_running,
            "monitored_rentals_count": len(self.monitored_rentals),
            "check_interval_seconds": self.check_interval,
            "last_checks": self.last_check
        }


# יצירת אינסטנס לשימוש מחוץ למודול
watchdog = Watchdog()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Watchdog module loaded successfully")
