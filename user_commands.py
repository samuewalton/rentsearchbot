"""
מודול user_commands - פקודות משתמש בבוט
"""

import logging
from datetime import datetime, timedelta
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from constants import Constants
from command_router import command_router
from db import execute_query
from user_manager import user_manager
from rank_engine import rank_engine
from assets_manager import assets_manager
from notifications import notification_manager
from rental_manager import rental_manager

logger = logging.getLogger(__name__)

# פקודות משתמש
async def cmd_start(message: types.Message):
    """
    פקודת התחלה
    """
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    language_code = message.from_user.language_code or "en"
    
    # בדיקה האם המשתמש קיים או יצירת משתמש חדש
    user = user_manager.get_user_by_telegram_id(user_id)
    if not user:
        user = user_manager.create_user(user_id, username, first_name, last_name, language_code)
        logger.info(f"משתמש חדש נרשם: {user_id} - {first_name} {last_name}")
    
    await message.reply(
        f"ברוכים הבאים ל־<b>{Constants.BOT_USERNAME}</b>!\n\n"
        f"בוט זה מאפשר להשכיר נכסים טלגרמיים לקידום מילות מפתח בחיפוש הגלובלי.\n\n"
        f"לבדיקת דירוג מילת מפתח, השתמשו בפקודה: /check\n"
        f"להשכרת נכס למילת מפתח, השתמשו בפקודה: /buy\n\n"
        f"לעזרה מלאה והסבר על כל הפקודות הזמינות, השתמשו בפקודה: /help",
        parse_mode="HTML"
    )

async def cmd_help(message: types.Message):
    """
    פקודת עזרה
    """
    help_text = (
        f"<b>פקודות זמינות ב־{Constants.BOT_USERNAME}:</b>\n\n"
        f"/check - בדיקת דירוג מילת מפתח בחיפוש הגלובלי\n"
        f"/buy - השכרת נכס למילת מפתח\n"
        f"/keywords - הצגת מילות המפתח הנוכחיות שלך\n"
        f"/my_rentals - הצגת השכרות פעילות והיסטוריות\n"
        f"/alerts - הגדרת התראות לפי דירוג/תפוגה\n"
        f"/cancel_rental - ביטול השכרה פעילה\n"
        f"/extend - הארכת זמן השכרה קיימת\n"
        f"/preferences - הגדרת העדפות מחיר/סוג נכס\n"
        f"/help - הצגת הודעה זו\n\n"
        f"<b>מידע נוסף:</b>\n"
        f"כל השכרה מקבלת דירוג מדויק ומתאימה את עצמה לתנאי השוק.\n"
        f"השכרות פעילות נבדקות כל שעתיים ואתם תקבלו התראות בכל שינוי דירוג משמעותי."
    )
    
    await message.reply(help_text, parse_mode="HTML")

async def cmd_check(message: types.Message):
    """
    פקודת בדיקת דירוג עבור מילת מפתח
    """
    await message.reply(
        "אנא הזינו את מילת המפתח שברצונכם לבדוק:",
        parse_mode="HTML"
    )
    # המשך הטיפול ב-bot_core.py בממשק הקלט

async def process_check_keyword(message: types.Message, keyword: str):
    """
    עיבוד בדיקת מילת מפתח
    """
    user_id = message.from_user.id
    
    # שליחת הודעת המתנה
    wait_message = await message.reply("מחפש את הדירוג הטוב ביותר עבור המילה...", parse_mode="HTML")
    
    # חיפוש נכסים מתאימים וקבלת דירוג
    results = await rank_engine.find_best_assets_for_keyword(keyword)
    
    if not results or len(results) == 0:
        await wait_message.edit_text(
            f"לא נמצאו נכסים זמינים עבור המילה <b>{keyword}</b>.\n"
            f"אנא נסו מילת מפתח אחרת או בדקו שוב מאוחר יותר.",
            parse_mode="HTML"
        )
        return
    
    # יצירת הודעת תוצאות
    response = f"<b>תוצאות דירוג עבור המילה: {keyword}</b>\n\n"
    
    # ריבוי התוצאות למבנה מסודר
    premium_assets = []
    regular_assets = []
    
    for result in results:
        asset_data = result.get("asset", {})
        rank = result.get("rank", -1)
        tier = result.get("tier", Constants.TIER_REGULAR)
        
        if tier == Constants.TIER_PREMIUM:
            premium_assets.append((asset_data, rank))
        elif tier == Constants.TIER_REGULAR:
            regular_assets.append((asset_data, rank))
    
    # תוספת תוצאות Premium
    if premium_assets:
        response += "<b>🌟 נכסים פרימיום:</b>\n"
        for asset_data, rank in premium_assets:
            asset_name = asset_data.get("name", "")
            asset_type = asset_data.get("type", "")
            price = rental_manager.get_rental_price(rank, Constants.TIER_PREMIUM)
            
            response += f"• {asset_name} ({_get_asset_type_label(asset_type)})\n"
            response += f"  📊 דירוג: {rank} | 💰 מחיר: ${price}/24h\n"
        
        response += "\n"
    
    # תוספת תוצאות Regular
    if regular_assets:
        response += "<b>✅ נכסים רגילים:</b>\n"
        for asset_data, rank in regular_assets:
            asset_name = asset_data.get("name", "")
            asset_type = asset_data.get("type", "")
            price = rental_manager.get_rental_price(rank, Constants.TIER_REGULAR)
            
            response += f"• {asset_name} ({_get_asset_type_label(asset_type)})\n"
            response += f"  📊 דירוג: {rank} | 💰 מחיר: ${price}/24h\n"
    
    # תוספת קישור להזמנה
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🛒 להשכיר נכס למילה זו", callback_data=f"buy_{keyword}"))
    
    await wait_message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")

async def cmd_buy(message: types.Message):
    """
    פקודת רכישה/השכרה
    """
    await message.reply(
        "אנא הזינו את מילת המפתח שברצונכם להשכיר עבורה נכס:",
        parse_mode="HTML"
    )
    # המשך הטיפול ב-bot_core.py בממשק הקלט

async def process_buy_keyword(message: types.Message, keyword: str):
    """
    עיבוד תהליך רכישה/השכרה
    """
    user_id = message.from_user.id
    
    # שליחת הודעת המתנה
    wait_message = await message.reply("מחפש את הנכס הטוב ביותר עבור המילה...", parse_mode="HTML")
    
    # יצירת בקשת השכרה
    rental_data, error = rental_manager.create_rental_request(user_id, keyword)
    
    if not rental_data:
        await wait_message.edit_text(
            f"<b>לא ניתן להשכיר נכס עבור המילה:</b> {keyword}\n\n"
            f"{error}",
            parse_mode="HTML"
        )
        return
    
    # קבלת פרטי הנכס
    asset_id = rental_data.get("asset_id")
    asset_name = rental_data.get("asset_name")
    asset_type = rental_data.get("asset_type")
    rank = rental_data.get("rank")
    tier = rental_data.get("tier")
    price = rental_data.get("price")
    rental_id = rental_data.get("id")
    
    # יצירת הודעת אישור והצעת תשלום
    response = (
        f"<b>הצעת השכרה עבור המילה:</b> {keyword}\n\n"
        f"<b>פרטי הנכס:</b>\n"
        f"• שם: {asset_name}\n"
        f"• סוג: {_get_asset_type_label(asset_type)}\n"
        f"• דירוג: {rank}\n"
        f"• רמה: {_get_tier_label(tier)}\n\n"
        f"<b>אפשרויות השכרה:</b>"
    )
    
    # יצירת כפתורים עבור אפשרויות תשלום
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("24 שעות", callback_data=f"rent_{rental_id}_24"),
        InlineKeyboardButton("48 שעות", callback_data=f"rent_{rental_id}_48"),
        InlineKeyboardButton("72 שעות", callback_data=f"rent_{rental_id}_72")
    )
    
    # הוספת מחירים
    price_24h = price
    price_48h = round(price * 1.8, 2)  # 10% הנחה על יומיים
    price_72h = round(price * 2.5, 2)  # 17% הנחה על שלושה ימים
    
    response += f"\n• 24 שעות: ${price_24h}"
    response += f"\n• 48 שעות: ${price_48h} (10% הנחה)"
    response += f"\n• 72 שעות: ${price_72h} (17% הנחה)"
    
    # כפתור ביטול
    keyboard.add(InlineKeyboardButton("❌ ביטול", callback_data=f"cancel_rent_{rental_id}"))
    
    await wait_message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")

async def process_buy_duration(callback_query: types.Message, rental_id: int, duration: int):
    """
    עיבוד בחירת משך השכרה
    """
    user_id = callback_query.from_user.id
    
    # קבלת פרטי ההשכרה
    rental_data, error = rental_manager.get_rental(rental_id)
    
    if not rental_data:
        await callback_query.message.edit_text(
            "שגיאה בטעינת פרטי ההשכרה. אנא נסו שוב.",
            parse_mode="HTML"
        )
        return
    
    # עדכון משך ההשכרה
    price = rental_data.get("price", 0)
    if isinstance(rental_data, dict):
        keyword = rental_data.get("keyword", "")
    else:
        keyword = str(rental_data)
    
    # חישוב מחיר לפי משך
    total_price = price
    if duration == 48:
        total_price = round(price * 1.8, 2)
    elif duration == 72:
        total_price = round(price * 2.5, 2)
    
    # יצירת כפתור תשלום
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("💳 לתשלום", callback_data=f"pay_{rental_id}_{duration}")
    )
    
    # מידע על תפוגת ההצעה
    expiry_time = datetime.now() + timedelta(hours=4)
    expiry_str = expiry_time.strftime("%d/%m/%Y %H:%M")
    
    await callback_query.message.edit_text(
        f"<b>סיכום הזמנה:</b>\n\n"
        f"• מילת מפתח: {keyword}\n"
        f"• משך השכרה: {duration} שעות\n"
        f"• מחיר: ${total_price}\n\n"
        f"<i>⏰ הצעה זו תפוג בתאריך: {expiry_str}</i>\n\n"
        f"לחצו על כפתור התשלום להשלמת העסקה.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def process_payment(callback_query: types.Message, rental_id: int, duration: int):
    """
    עיבוד תשלום
    """
    user_id = callback_query.from_user.id
    
    # בתרחיש אמיתי כאן יש להפעיל מערכת תשלומים
    # לצורך הדוגמה נניח שהתשלום הצליח
    
    # קבלת פרטי ההשכרה
    rental_data, error = rental_manager.get_rental(rental_id)
    
    if not rental_data:
        await callback_query.message.edit_text(
            "שגיאה בטעינת פרטי ההשכרה. אנא נסו שוב.",
            parse_mode="HTML"
        )
        return
    
    # הפעלת ההשכרה
    success, error_msg = rental_manager.activate_rental(rental_id, f"payment_{rental_id}_{user_id}", duration)
    
    if not success:
        await callback_query.message.edit_text(
            f"<b>שגיאה בהפעלת ההשכרה:</b>\n{error_msg}",
            parse_mode="HTML"
        )
        return
    
    # חישוב זמן סיום
    end_time = datetime.now() + timedelta(hours=duration)
    end_time_str = end_time.strftime("%d/%m/%Y %H:%M")
    
    keyword = rental_data.get("keyword", "")
    asset_name = rental_data.get("asset_name", "")
    
    await callback_query.message.edit_text(
        f"<b>🎉 ההשכרה הופעלה בהצלחה!</b>\n\n"
        f"• מילת מפתח: {keyword}\n"
        f"• נכס: {asset_name}\n"
        f"• משך: {duration} שעות\n"
        f"• מסתיים בתאריך: {end_time_str}\n\n"
        f"<i>המערכת תנטר את דירוג הנכס ותשלח לכם התראות על כל שינוי משמעותי.</i>\n\n"
        f"לצפייה בהשכרות הפעילות שלכם, השתמשו בפקודה: /my_rentals",
        parse_mode="HTML"
    )

async def cmd_my_rentals(message: types.Message):
    """
    פקודה להצגת השכרות פעילות והיסטוריות
    """
    user_id = message.from_user.id
    
    # קבלת השכרות פעילות
    active_rentals = user_manager.get_user_rentals(user_id, 
                                       [Constants.RENTAL_STATUS_ACTIVE, Constants.RENTAL_STATUS_MONITORING, Constants.RENTAL_STATUS_EXPIRING])
    
    # קבלת השכרות היסטוריות
    historic_rentals = user_manager.get_user_rentals(user_id, 
                                        [Constants.RENTAL_STATUS_EXPIRED, Constants.RENTAL_STATUS_CANCELED, Constants.RENTAL_STATUS_ARCHIVED])
    
    if not active_rentals and not historic_rentals:
        await message.reply(
            "אין לכם השכרות פעילות או היסטוריות.\n"
            "להשכרת נכס חדש, השתמשו בפקודה: /buy",
            parse_mode="HTML"
        )
        return
    
    response = "<b>ההשכרות שלכם:</b>\n\n"
    
    # הצגת השכרות פעילות
    if active_rentals:
        response += "<b>🟢 השכרות פעילות:</b>\n\n"
        
        for rental in active_rentals:
            keyword = rental.get("keyword", "")
            asset_name = rental.get("asset_name", "")
            status = rental.get("status", "")
            expires_at = rental.get("expires_at")
            
            if expires_at:
                expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                remaining_time = expires_datetime - datetime.now()
                remaining_hours = int(remaining_time.total_seconds() / 3600)
                remaining_minutes = int((remaining_time.total_seconds() % 3600) / 60)
                remaining_str = f"{remaining_hours}h {remaining_minutes}m"
            else:
                remaining_str = "לא ידוע"
            
            response += f"📝 <b>{keyword}</b> ({_get_status_label(status)})\n"
            response += f"• נכס: {asset_name}\n"
            response += f"• זמן נותר: {remaining_str}\n"
            response += f"• מזהה השכרה: #{rental.get('id')}\n\n"
        
        # הוספת כפתורים לפעולות
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("🔄 רענון", callback_data="refresh_rentals"),
            InlineKeyboardButton("📜 היסטוריה", callback_data="show_history")
        )
    
    # הצגת השכרות היסטוריות אם אין פעילות או לפי בקשה
    elif historic_rentals:
        response += "<b>⚪️ השכרות היסטוריות:</b>\n\n"
        
        # הצגת רק 5 ההשכרות האחרונות
        for rental in historic_rentals[:5]:
            keyword = rental.get("keyword", "")
            asset_name = rental.get("asset_name", "")
            status = rental.get("status", "")
            created_at = rental.get("created_at", "")
            
            if created_at:
                created_datetime = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_str = created_datetime.strftime("%d/%m/%Y")
            else:
                created_str = "לא ידוע"
            
            response += f"📝 <b>{keyword}</b> ({_get_status_label(status)})\n"
            response += f"• נכס: {asset_name}\n"
            response += f"• תאריך: {created_str}\n"
            response += f"• מזהה השכרה: #{rental.get('id')}\n\n"
        
        # הוספת כפתורים לפעולות
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("🔄 רענון", callback_data="refresh_rentals")
        )
    
    await message.reply(response, reply_markup=keyboard, parse_mode="HTML")

async def cmd_keywords(message: types.Message):
    """
    פקודה להצגת מילות מפתח נוכחיות
    """
    user_id = message.from_user.id
    
    # קבלת השכרות פעילות
    active_rentals = user_manager.get_user_rentals(user_id, 
                                       [Constants.RENTAL_STATUS_ACTIVE, Constants.RENTAL_STATUS_MONITORING, Constants.RENTAL_STATUS_EXPIRING])
    
    if not active_rentals:
        await message.reply(
            "אין לכם מילות מפתח פעילות כרגע.\n"
            "להשכרת נכס עבור מילת מפתח, השתמשו בפקודה: /buy",
            parse_mode="HTML"
        )
        return
    
    response = "<b>מילות המפתח הפעילות שלכם:</b>\n\n"
    
    for rental in active_rentals:
        keyword = rental.get("keyword", "")
        rank = rental.get("rank", -1)
        tier = rental.get("tier", "")
        asset_name = rental.get("asset_name", "")
        expires_at = rental.get("expires_at")
        
        if expires_at:
            expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            remaining_time = expires_datetime - datetime.now()
            remaining_hours = int(remaining_time.total_seconds() / 3600)
            remaining_str = f"{remaining_hours}h"
        else:
            remaining_str = "לא ידוע"
        
        response += f"🔑 <b>{keyword}</b>\n"
        response += f"• דירוג נוכחי: {rank} ({_get_tier_label(tier)})\n"
        response += f"• נכס: {asset_name}\n"
        response += f"• זמן נותר: {remaining_str}\n\n"
    
    # הוספת כפתורים לפעולות
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🔍 לבדוק דירוג", callback_data="check_rank"),
        InlineKeyboardButton("➕ להוסיף מילה", callback_data="add_keyword")
    )
    
    await message.reply(response, reply_markup=keyboard, parse_mode="HTML")

async def cmd_cancel_rental(message: types.Message):
    """
    פקודה לביטול השכרה פעילה
    """
    user_id = message.from_user.id
    
    # קבלת השכרות פעילות
    active_rentals = user_manager.get_user_rentals(user_id, 
                                       [Constants.RENTAL_STATUS_ACTIVE, Constants.RENTAL_STATUS_MONITORING, Constants.RENTAL_STATUS_EXPIRING])
    
    if not active_rentals:
        await message.reply(
            "אין לכם השכרות פעילות שניתן לבטל.\n"
            "להשכרת נכס חדש, השתמשו בפקודה: /buy",
            parse_mode="HTML"
        )
        return
    
    response = "<b>בחרו את ההשכרה שברצונכם לבטל:</b>\n\n"
    
    # יצירת כפתורים לכל השכרה
    keyboard = InlineKeyboardMarkup()
    
    for rental in active_rentals:
        keyword = rental.get("keyword", "")
        rental_id = rental.get("id", 0)
        
        response += f"• <b>{keyword}</b> (מזהה: #{rental_id})\n"
        keyboard.add(InlineKeyboardButton(f"ביטול '{keyword}'", callback_data=f"cancel_rental_{rental_id}"))
    
    # הוספת כפתור ביטול
    keyboard.add(InlineKeyboardButton("❌ חזרה", callback_data="cancel_action"))
    
    await message.reply(response, reply_markup=keyboard, parse_mode="HTML")

async def process_cancel_rental(callback_query: types.Message, rental_id: int):
    """
    עיבוד ביטול השכרה
    """
    user_id = callback_query.from_user.id
    
    # קבלת פרטי ההשכרה
    rental_data, error = rental_manager.get_rental(rental_id)
    
    if not rental_data:
        await callback_query.message.edit_text(
            f"<b>שגיאה בטעינת פרטי ההשכרה:</b>\n{error}",
            parse_mode="HTML"
        )
        return
    
    keyword = rental_data.get("keyword", "")
    
    # בדיקת אישור סופי
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ כן, לבטל", callback_data=f"confirm_cancel_{rental_id}"),
        InlineKeyboardButton("❌ לא, להשאיר", callback_data="cancel_action")
    )
    
    await callback_query.message.edit_text(
        f"<b>אישור ביטול השכרה</b>\n\n"
        f"האם אתם בטוחים שברצונכם לבטל את ההשכרה של המילה <b>{keyword}</b>?\n\n"
        f"<i>שימו לב: בביטול מוקדם של השכרה תקבלו החזר חלקי בהתאם לזמן שנותר.</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def confirm_cancel_rental(callback_query: types.Message, rental_id: int):
    """
    אישור סופי לביטול השכרה
    """
    user_id = callback_query.from_user.id
    
    # ביטול ההשכרה
    success, error_msg = rental_manager.cancel_rental(rental_id)
    
    if not success:
        await callback_query.message.edit_text(
            f"<b>שגיאה בביטול ההשכרה:</b>\n{error_msg}",
            parse_mode="HTML"
        )
        return
    
    # קבלת פרטי ההשכרה שבוטלה
    rental_data, _ = rental_manager.get_rental(rental_id)
    
    if rental_data:
        keyword = rental_data.get("keyword", "")
        refund_amount = rental_data.get("refund_amount", 0)
        
        await callback_query.message.edit_text(
            f"<b>✅ ההשכרה בוטלה בהצלחה</b>\n\n"
            f"• מילת מפתח: {keyword}\n"
            f"• מזהה השכרה: #{rental_id}\n"
            f"• סכום להחזר: ${refund_amount}\n\n"
            f"<i>הסכום יוחזר לחשבונך בהקדם.</i>",
            parse_mode="HTML"
        )
    else:
        await callback_query.message.edit_text(
            "<b>ההשכרה בוטלה בהצלחה</b>",
            parse_mode="HTML"
        )

async def cmd_extend(message: types.Message):
    """
    פקודה להארכת השכרה קיימת
    """
    user_id = message.from_user.id
    
    # קבלת השכרות פעילות
    active_rentals = user_manager.get_user_rentals(user_id, 
                                       [Constants.RENTAL_STATUS_ACTIVE, Constants.RENTAL_STATUS_MONITORING])
    
    if not active_rentals:
        await message.reply(
            "אין לכם השכרות פעילות שניתן להאריך.\n"
            "להשכרת נכס חדש, השתמשו בפקודה: /buy",
            parse_mode="HTML"
        )
        return
    
    response = "<b>בחרו את ההשכרה שברצונכם להאריך:</b>\n\n"
    
    # יצירת כפתורים לכל השכרה
    keyboard = InlineKeyboardMarkup()
    
    for rental in active_rentals:
        keyword = rental.get("keyword", "")
        rental_id = rental.get("id", 0)
        
        response += f"• <b>{keyword}</b> (מזהה: #{rental_id})\n"
        keyboard.add(InlineKeyboardButton(f"הארכת '{keyword}'", callback_data=f"extend_rental_{rental_id}"))
    
    # הוספת כפתור ביטול
    keyboard.add(InlineKeyboardButton("❌ חזרה", callback_data="cancel_action"))
    
    await message.reply(response, reply_markup=keyboard, parse_mode="HTML")

async def process_extend_rental(callback_query: types.Message, rental_id: int):
    """
    עיבוד הארכת השכרה
    """
    user_id = callback_query.from_user.id
    
    # קבלת פרטי ההשכרה
    rental_data, error = rental_manager.get_rental(rental_id)
    
    if not rental_data:
        await callback_query.message.edit_text(
            f"<b>שגיאה בטעינת פרטי ההשכרה:</b>\n{error}",
            parse_mode="HTML"
        )
        return
    
    keyword = rental_data.get("keyword", "")
    rank = rental_data.get("rank", -1)
    tier = rental_data.get("tier", "")
    price = rental_data.get("price", 0)
    
    # יצירת כפתורים עבור אפשרויות הארכה
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.add(
        InlineKeyboardButton("24 שעות", callback_data=f"extend_{rental_id}_24"),
        InlineKeyboardButton("48 שעות", callback_data=f"extend_{rental_id}_48"),
        InlineKeyboardButton("72 שעות", callback_data=f"extend_{rental_id}_72")
    )
    
    # הוספת מחירים
    price_24h = price
    price_48h = round(price * 1.8, 2)  # 10% הנחה על יומיים
    price_72h = round(price * 2.5, 2)  # 17% הנחה על שלושה ימים
    
    # הוספת כפתור ביטול
    keyboard.add(InlineKeyboardButton("❌ ביטול", callback_data="cancel_action"))
    
    await callback_query.message.edit_text(
        f"<b>הארכת השכרה עבור המילה:</b> {keyword}\n\n"
        f"<b>פרטי הנכס:</b>\n"
        f"• דירוג נוכחי: {rank}\n"
        f"• רמה: {_get_tier_label(tier)}\n\n"
        f"<b>אפשרויות הארכה:</b>\n"
        f"• 24 שעות: ${price_24h}\n"
        f"• 48 שעות: ${price_48h} (10% הנחה)\n"
        f"• 72 שעות: ${price_72h} (17% הנחה)",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def process_extend_duration(callback_query: types.Message, rental_id: int, duration: int):
    """
    עיבוד בחירת משך הארכה
    """
    user_id = callback_query.from_user.id
    
    # קבלת פרטי ההשכרה
    rental_data, error = rental_manager.get_rental(rental_id)
    
    if not rental_data:
        await callback_query.message.edit_text(
            "שגיאה בטעינת פרטי ההשכרה. אנא נסו שוב.",
            parse_mode="HTML"
        )
        return
    
    # עדכון משך ההשכרה
    price = rental_data.get("price", 0)
    keyword = rental_data.get("keyword", "")
    
    # חישוב מחיר לפי משך
    total_price = price
    if duration == 48:
        total_price = round(price * 1.8, 2)
    elif duration == 72:
        total_price = round(price * 2.5, 2)
    
    # יצירת כפתור תשלום
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("💳 לתשלום", callback_data=f"pay_extend_{rental_id}_{duration}")
    )
    
    await callback_query.message.edit_text(
        f"<b>סיכום הארכת השכרה:</b>\n\n"
        f"• מילת מפתח: {keyword}\n"
        f"• משך הארכה: {duration} שעות\n"
        f"• מחיר: ${total_price}\n\n"
        f"לחצו על כפתור התשלום להשלמת העסקה.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

async def process_extend_payment(callback_query: types.Message, rental_id: int, duration: int):
    """
    עיבוד תשלום להארכת השכרה
    """
    user_id = callback_query.from_user.id
    
    # בתרחיש אמיתי כאן יש להפעיל מערכת תשלומים
    # לצורך הדוגמה נניח שהתשלום הצליח
    
    # קבלת פרטי ההשכרה
    rental_data, error = rental_manager.get_rental(rental_id)
    
    if not rental_data:
        await callback_query.message.edit_text(
            "שגיאה בטעינת פרטי ההשכרה. אנא נסו שוב.",
            parse_mode="HTML"
        )
        return
    
    # הארכת ההשכרה
    success, error_msg = rental_manager.extend_rental(rental_id, f"payment_extend_{rental_id}_{user_id}", duration)
    
    if not success:
        await callback_query.message.edit_text(
            f"<b>שגיאה בהארכת ההשכרה:</b>\n{error_msg}",
            parse_mode="HTML"
        )
        return
    
    # חישוב זמן סיום החדש
    end_time = datetime.now() + timedelta(hours=duration)
    end_time_str = end_time.strftime("%d/%m/%Y %H:%M")
    
    keyword = rental_data.get("keyword", "")
    
    await callback_query.message.edit_text(
        f"<b>🎉 ההשכרה הוארכה בהצלחה!</b>\n\n"
        f"• מילת מפתח: {keyword}\n"
        f"• משך הארכה: {duration} שעות\n"
        f"• תאריך סיום חדש: {end_time_str}\n\n"
        f"<i>המערכת תמשיך לנטר את דירוג הנכס ותשלח לכם התראות על כל שינוי משמעותי.</i>\n\n"
        f"לצפייה בהשכרות הפעילות שלכם, השתמשו בפקודה: /my_rentals",
        parse_mode="HTML"
    )

async def cmd_alerts(message: types.Message):
    """
    פקודה להגדרת התראות
    """
    # קבלת התראות עבור המשתמש
    user_id = message.from_user.id
    notifications = notification_manager.get_user_notifications(user_id)
    
    # יצירת כפתורי התראות
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("⚠️ התראות דירוג", callback_data="alerts_rank"),
        InlineKeyboardButton("⏰ התראות תפוגה", callback_data="alerts_expiry")
    )
    
    # אם יש התראות שלא נקראו
    unread_count = sum(1 for n in notifications if not n.get("is_read", False))
    
    response = (
        f"<b>ניהול התראות</b>\n\n"
        f"כאן תוכלו להגדיר את העדפות ההתראות שלכם במערכת.\n"
    )
    
    if unread_count > 0:
        response += f"\n<b>📬 יש לכם {unread_count} התראות שלא נקראו</b>\n"
        keyboard.add(InlineKeyboardButton("📬 הצג התראות", callback_data="show_notifications"))
    
    await message.reply(response, reply_markup=keyboard, parse_mode="HTML")

async def cmd_preferences(message: types.Message):
    """
    פקודה להגדרת העדפות משתמש
    """
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("🏷️ העדפות מחיר", callback_data="pref_price"),
        InlineKeyboardButton("📋 סוגי נכסים", callback_data="pref_asset_types")
    )
    
    await message.reply(
        "<b>הגדרות והעדפות</b>\n\n"
        "כאן תוכלו להגדיר את ההעדפות שלכם במערכת:\n"
        "• טווח מחירים מועדף\n"
        "• סוגי נכסים מועדפים (בוטים, ערוצים, קבוצות)\n"
        "• הגדרות התראות\n\n"
        "בחרו מה ברצונכם להגדיר:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# פונקציות עזר

def _get_asset_type_label(asset_type: str) -> str:
    """
    מחזיר תווית מתורגמת לסוג הנכס
    """
    if asset_type == Constants.ASSET_TYPE_BOT:
        return "בוט"
    elif asset_type == Constants.ASSET_TYPE_CHANNEL:
        return "ערוץ"
    elif asset_type == Constants.ASSET_TYPE_GROUP:
        return "קבוצה"
    return asset_type

def _get_tier_label(tier: str) -> str:
    """
    מחזיר תווית מתורגמת לרמת הנכס
    """
    if tier == Constants.TIER_PREMIUM:
        return "פרימיום"
    elif tier == Constants.TIER_REGULAR:
        return "רגיל"
    return tier

def _get_status_label(status: str) -> str:
    """
    מחזיר תווית מתורגמת לסטטוס השכרה
    """
    if status == Constants.RENTAL_STATUS_PENDING:
        return "ממתין לתשלום"
    elif status == Constants.RENTAL_STATUS_ACTIVE:
        return "פעיל"
    elif status == Constants.RENTAL_STATUS_MONITORING:
        return "במעקב"
    elif status == Constants.RENTAL_STATUS_EXPIRING:
        return "עומד לפוג"
    elif status == Constants.RENTAL_STATUS_EXPIRED:
        return "פג תוקף"
    elif status == Constants.RENTAL_STATUS_CANCELED:
        return "בוטל"
    elif status == Constants.RENTAL_STATUS_ARCHIVED:
        return "בארכיון"
    return status

# הגדרת הפקודות

def setup_user_commands():
    """
    הגדרת פקודות משתמש
    """
    command_router.register_user_command("start", cmd_start)
    command_router.register_user_command("help", cmd_help)
    command_router.register_user_command("check", cmd_check)
    command_router.register_user_command("buy", cmd_buy)
    command_router.register_user_command("my_rentals", cmd_my_rentals)
    command_router.register_user_command("keywords", cmd_keywords)
    command_router.register_user_command("cancel_rental", cmd_cancel_rental)
    command_router.register_user_command("extend", cmd_extend)
    command_router.register_user_command("alerts", cmd_alerts)
    command_router.register_user_command("preferences", cmd_preferences)
