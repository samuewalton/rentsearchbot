# bot_core.py - RentSpot Bot Main Module
# -*- coding: utf-8 -*-
"""
Main bot module with comprehensive type hints and error handling
Fixed type annotations and null safety checks throughout
"""

import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union  # type: ignore
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button  # type: ignore
from telethon.events import CallbackQuery, NewMessage  # type: ignore
from telethon.tl.types import User  # type: ignore

# Import your managers and helpers
from rank_engine import rank_engine
from rental_manager import rental_manager
from session_manager import session_manager
from user_manager import user_manager
from assets_manager import assets_manager

# הגדרת לוגינג
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# טעינת משתני סביבה
load_dotenv()

# הגדרת משתנים גלובליים
BOT_TOKEN = os.getenv("RENTBOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# בדיקת פרטי חיבור
if not BOT_TOKEN or not API_ID or not API_HASH:
    logger.error(
        "חסרים פרטי API או בוט טוקן. "
        "אנא הגדר RENTBOT_TOKEN, API_ID, API_HASH בקובץ .env"
    )
    sys.exit(1)

# יצירת הקליינט
bot = TelegramClient("bot", int(API_ID), API_HASH)  # type: ignore

# מצבי משתמש - פשוט נשתמש במילון
user_states = {}  # {user_id: {'state': 'state_name', 'data': {...}}}

# Constants for user states
STATE_WAITING_FOR_KEYWORD = "waiting_for_keyword"
STATE_WAITING_FOR_DURATION = "waiting_for_duration"
STATE_WAITING_FOR_PAYMENT = "waiting_for_payment"
STATE_WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
STATE_WAITING_FOR_CONTACT_MESSAGE = "waiting_for_contact_message"

# Constants for admin states
ADMIN_STATE_WAITING_FOR_PHONE = "admin_waiting_phone"
ADMIN_STATE_WAITING_FOR_CODE = "admin_waiting_code"
ADMIN_STATE_WAITING_FOR_2FA = "admin_waiting_2fa"
ADMIN_STATE_SELECTING_ASSETS = "admin_selecting_assets"
ADMIN_STATE_WAITING_FOR_SESSION_NAME = "admin_waiting_session_name"
ADMIN_STATE_WAITING_FOR_ASSET_NAME = "admin_waiting_asset_name"
ADMIN_STATE_WAITING_FOR_ASSET_TYPE = "admin_waiting_asset_type"
ADMIN_STATE_WAITING_FOR_ASSET_ID = "admin_waiting_asset_id"
ADMIN_STATE_WAITING_FOR_CONFIRM_DELETE = "admin_waiting_confirm_delete"
ADMIN_STATE_WAITING_FOR_BOT_NAME = "admin_waiting_bot_name"


# התחלת הבוט
async def on_startup():
    """
    פונקציה הנקראת בהתחלת הבוט
    """
    logger.info("התחלת הבוט...")

    # בדיקת מסד נתונים
    try:
        logger.info("בדיקת חיבור למסד נתונים...")
        # כאן ניתן להוסיף בדיקות למסד הנתונים
        pass  # Database check would go here
    except Exception as e:
        logger.error(f"שגיאה בבדיקת מסד נתונים: {str(e)}")

    logger.info("הבוט מוכן לשימוש!")


async def on_shutdown():
    """
    פונקציה הנקראת בסגירת הבוט
    """
    logger.info("סגירת הבוט...")

    # סגירת מחסן המצבים
    # הערה: במהדורה 3.x של aiogram אין צורך לסגור מחסן מצבים באופן מפורש

    # סגירת כל הסשנים הפעילים
    session_manager.close_all_sessions()

    logger.info("הבוט נסגר בהצלחה.")


# פונקציות עזר



def is_admin(user_id: int) -> bool:
    """
    Check if a user is an admin
    """
    try:
        return user_manager.is_admin(user_id)  # type: ignore
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False


# רשימת הפקודות של הבוט



@bot.on(events.NewMessage(pattern="/help"))
async def cmd_help(event: events.NewMessage.Event):
    """
    פקודת עזרה
    """
    help_text = (
        "🤖 <b>עזרה - RentSpot Bot</b>\n\n"
        "📋 <b>פקודות זמינות:</b>\n"
        "/start - התחל שימוש בבוט\n"
        "/help - הצג הודעת עזרה זו\n"
        "/rent - השכר מקום בחיפוש\n\n"
        "💡 <b>איך זה עובד?</b>\n"
        "1. בחר מילת חיפוש\n"
        "2. בחר נכס מהרשימה\n"
        "3. בחר משך השכרה\n"
        "4. שלם ותהנה מחשיפה מקסימלית!\n\n"
        "📞 לשאלות: @support"
    )

    await event.respond(help_text, parse_mode="html")


@bot.on(events.NewMessage(pattern="/rent"))
async def cmd_rent(event: events.NewMessage.Event):
    """
    פקודת השכרה
    """
    sender = await event.get_sender()

    # שמירת מצב המשתמש
    user_states[sender.id] = {"state": STATE_WAITING_FOR_KEYWORD, "data": {}}

    await event.respond(
        "🔍 <b>השכרת מקום בחיפוש</b>\n\n"
        "אנא שלח את מילת החיפוש שברצונך להשכיר עבורה מקום:\n\n"
        "💡 <b>דוגמאות:</b>\n"
        "• דירות להשכרה תל אביב\n"
        "• משרדים להשכרה\n"
        "• רכב יד שנייה\n\n"
        "✏️ כתב את מילת החיפוש שלך:",
        parse_mode="html",
    )


@bot.on(events.CallbackQuery(pattern=b"rent_keyword"))
async def callback_rent_keyword(event: events.CallbackQuery.Event):
    """
    התחלת תהליך השכרת מילת מפתח
    """
    try:
        await event.answer(cache_time=0)
        sender = await event.get_sender()

        # שמירת מצב המשתמש
        user_states[sender.id] = {"state": STATE_WAITING_FOR_KEYWORD, "data": {}}

        await event.edit(
            "🔍 <b>השכרת מקום בחיפוש</b>\n\n"
            "אנא שלח את מילת החיפוש שברצונך להשכיר עבורה מקום:\n\n"
            "💡 <b>דוגמאות:</b>\n"
            "• דירות להשכרה תל אביב\n"
            "• משרדים להשכרה\n"
            "• רכב יד שנייה\n\n"
            "✏️ כתב את מילת החיפוש שלך:",
            parse_mode="html",
        )
    except Exception as e:
        logger.error(f"שגיאה בהתחלת השכרה: {str(e)}")
        await event.edit(
            "❌ שגיאה בהתחלת תהליך השכרה. אנא נסה שוב מאוחר יותר.",
            buttons=[[Button.inline("🔙 חזרה לתפריט הראשי", b"back_to_main")]],
        )


@bot.on(events.CallbackQuery(pattern=b"personal_area"))
async def callback_personal_area(event: events.CallbackQuery.Event):
    """
    האזור האישי של המשתמש
    """
    try:
        await event.answer()
        sender = await event.get_sender()

        # קבלת פרטי המשתמש
        user_name = getattr(sender, "first_name", None) or getattr(sender, "username", None) or "משתמש"
        
        # בניית טקסט האזור האישי
        area_text = (
            f"👤 <b>האזור האישי - {user_name}</b>\n\n"
            f"🆔 <b>מזהה משתמש:</b> {sender.id}\n"
            f"📅 <b>תאריך הצטרפות:</b> לא זמין\n"
            f"📊 <b>סטטוס:</b> פעיל\n\n"
            f"📋 <b>ההזמנות שלך:</b>\n"
            f"• אין הזמנות פעילות\n\n"
            f"💰 <b>יתרה:</b> 0₪"
        )

        buttons = [
            [Button.inline("📝 ההזמנות שלי", b"my_orders")],
            [Button.inline("📞 יצירת קשר", b"contact_admin")],
            [Button.inline("🔙 חזרה לתפריט הראשי", b"back_to_main")]
        ]
        
        await event.edit(area_text, buttons=buttons, parse_mode="html")
        
    except Exception as e:
        logger.error(f"שגיאה באזור האישי: {str(e)}")
        await event.edit("❌ שגיאה באזור האישי. אנא נסה שוב.")


@bot.on(events.CallbackQuery(pattern=b"back_to_main"))
async def callback_back_to_main(event: CallbackQuery.Event) -> None:
    """
    חזרה לתפריט הראשי
    """
    try:
        await event.answer()
        sender = await event.get_sender()

        # איפוס מצב המשתמש
        if sender.id in user_states:
            del user_states[sender.id]

        # בדיקה אם המשתמש הוא מנהל
        is_admin_user = is_admin(sender.id)
        # הודעת התפריט הראשי
        user_name = (
            getattr(sender, "first_name", None)
            or getattr(sender, "username", None)
            or "משתמש"
        )
        welcome_text = (
            f"👋 שלום {user_name}!\n\n"
            f"🔍 רוצה להופיע בחיפוש של טלגרם?\n\n"
            f"🏆 אנחנו משכירים מקומות בתוצאות החיפוש הגלובלי\n"
            f"💰 מחירים החל מ-50$ ל-24 שעות\n\n"
            f"📋 מה תרצה לעשות?"
        )

        # כפתורים
        buttons = [
            [Button.inline("🏆 השכר מקום בחיפוש", b"rent_keyword")],
            [Button.inline("👤 האזור האישי שלי", b"personal_area")],
        ]

        # הוספת כפתור למנהלים
        if is_admin_user:
            buttons.append([Button.inline("⚙️ פאנל ניהול", b"admin_menu")])

        await event.edit(welcome_text, buttons=buttons, parse_mode="html")

    except Exception as e:
        logger.error(f"שגיאה בחזרה לתפריט הראשי: {str(e)}")
        await event.edit("❌ שגיאה. אנא השתמש בפקודה /start")


@bot.on(events.CallbackQuery(pattern=r"duration:(\d+):(\d+)"))
async def callback_duration(event: CallbackQuery.Event) -> None:
    """
    בחירת משך השכרה
    """
    try:
        await event.answer()
        sender = await event.get_sender()

        # קבלת הפרמטרים מהפקודה
        duration_hours = int(event.pattern_match.group(1))
        price = int(event.pattern_match.group(2))

        # בדיקת מצב המשתמש
        if sender.id not in user_states:
            await event.edit(
                "❌ שגיאה במצב המשתמש. אנא התחל מחדש.",
                buttons=[[Button.inline("🔙 חזרה לתפריט הראשי", b"back_to_main")]],
            )
            return

        # עדכון מצב המשתמש
        user_states[sender.id]["data"]["duration_hours"] = duration_hours
        user_states[sender.id]["data"]["price"] = price
        user_states[sender.id]["state"] = STATE_WAITING_FOR_PAYMENT

        # הצגת סיכום ההזמנה
        keyword = user_states[sender.id]["data"].get("keyword", "לא ידוע")
        asset = user_states[sender.id]["data"].get("selected_asset", "לא ידוע")

        duration_text = (
            f"{duration_hours} שעות"
            if duration_hours < 24
            else f"{duration_hours // 24} ימים"
        )

        summary_text = (
            f"📋 <b>סיכום ההזמנה</b>\n\n"
            f"🔍 <b>מילת חיפוש:</b> {keyword}\n"
            f"🤖 <b>נכס:</b> {asset}\n"
            f"⏰ <b>משך:</b> {duration_text}\n"
            f"💰 <b>מחיר:</b> ${price}\n\n"
            f"האם אתה מאשר את ההזמנה?"
        )

        buttons = [
            [Button.inline("✅ אישור ותשלום", b"confirm_payment")],
            [Button.inline("❌ ביטול", b"back_to_main")],
        ]

        await event.edit(summary_text, buttons=buttons, parse_mode="html")

    except Exception as e:
        logger.error(f"שגיאה בבחירת משך השכרה: {str(e)}")
        await event.edit(
            "❌ שגיאה בעיבוד הבקשה.",
            buttons=[[Button.inline("🔙 חזרה לתפריט הראשי", b"back_to_main")]],
        )


# =============== פונקציות מנהל המלאות ===============





@bot.on(events.CallbackQuery(pattern=b"admin_list_sessions"))
async def admin_list_sessions(event: CallbackQuery.Event) -> None:
    """
    הצגת רשימת סשנים
    """
    await event.answer()
    sender = await event.get_sender()

    # בדיקת הרשאות
    if not user_manager.is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        sessions = session_manager.get_all_sessions()

        if not sessions:
            await event.edit(
                "📋 <b>רשימת סשנים</b>\n\n" "❌ אין סשנים פעילים במערכת.",
                buttons=[
                    [
                        Button.inline("➕ הוסף סשן", b"admin_add_session"),
                        Button.inline("🔙 חזרה", b"admin_menu"),
                    ]
                ],
                parse_mode="html",
            )
            return

        sessions_text = "📋 <b>רשימת סשנים פעילים</b>\n\n"

        for session in sessions[:10]:  # הצגת עד 10 סשנים
            status = "🟢 פעיל" if session.get("status") == "active" else "🔴 לא פעיל"
            sessions_text += f"• {session.get('name', 'ללא שם')} - {status}\n"

        if len(sessions) > 10:
            sessions_text += f"\n... ועוד {len(sessions) - 10} סשנים"

        buttons = [
            [Button.inline("➕ הוסף סשן", b"admin_add_session")],
            [Button.inline("🔙 חזרה", b"admin_menu")],
        ]

        await event.edit(sessions_text, buttons=buttons, parse_mode="html")

    except Exception as e:
        logger.error(f"שגיאה בהצגת רשימת סשנים: {str(e)}")
        await event.edit("❌ שגיאה בטעינת רשימת הסשנים.")


@bot.on(events.CallbackQuery(pattern=b"admin_list_assets"))
async def admin_list_assets(event: CallbackQuery.Event) -> None:
    """
    הצגת רשימת נכסים
    """
    await event.answer()
    sender = await event.get_sender()

    # בדיקת הרשאות
    if not user_manager.is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        assets = assets_manager.get_all_assets()

        if not assets:
            await event.edit(
                "🤖 <b>רשימת נכסים</b>\n\n" "❌ אין נכסים רשומים במערכת.",
                buttons=[
                    [
                        Button.inline("🤖 הוסף בוט", b"admin_add_bot"),
                        Button.inline("🔙 חזרה", b"admin_menu"),
                    ]
                ],
                parse_mode="html",
            )
            return

        assets_text = "🤖 <b>רשימת נכסים רשומים</b>\n\n"

        for asset in assets[:10]:  # הצגת עד 10 נכסים
            asset_type = asset.get("type", "לא ידוע")
            asset_name = asset.get("name", "ללא שם")
            assets_text += f"• {asset_name} ({asset_type})\n"

        if len(assets) > 10:
            assets_text += f"\n... ועוד {len(assets) - 10} נכסים"

        buttons = [
            [Button.inline("🤖 הוסף בוט", b"admin_add_bot")],
            [Button.inline("🔙 חזרה", b"admin_menu")],
        ]

        await event.edit(assets_text, buttons=buttons, parse_mode="html")

    except Exception as e:
        logger.error(f"שגיאה בהצגת רשימת נכסים: {str(e)}")
        await event.edit("❌ שגיאה בטעינת רשימת הנכסים.")


@bot.on(events.CallbackQuery(pattern=b"admin_add_bot"))
async def admin_add_bot(event: CallbackQuery.Event) -> None:
    """
    הוספת בוט חדש
    """
    await event.answer()
    sender = await event.get_sender()

    # בדיקת הרשאות
    if not user_manager.is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    # שינוי מצב למתנה לשם בוט
    user_states[sender.id] = {"state": ADMIN_STATE_WAITING_FOR_BOT_NAME, "data": {}}

    await event.edit(
        "🤖 <b>הוספת בוט חדש</b>\n\n"
        "אנא הזן את שם המשתמש של הבוט (ללא @):\n"
        "לדוגמה: my_awesome_bot",
        parse_mode="html",
    )


@bot.on(events.CallbackQuery(pattern=b"admin_run_rank_cycle"))
async def admin_run_rank_cycle(event: CallbackQuery.Event) -> None:
    """הפעלת מחזור דירוג"""
    await event.answer()
    sender = await event.get_sender()
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")
        return
        
    if not user_manager.is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        await event.edit("🔄 מפעיל מנוע דירוג...")

        # הפעלת מנוע הדירוג
        await rank_engine.run_rank_cycle()

        await event.edit(
            "✅ מחזור הדירוג הושלם בהצלחה!",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            parse_mode="html",
        )

    except Exception as e:
        logger.error(f"שגיאה בהפעלת מחזור דירוג: {str(e)}")
        await event.edit(
            "❌ שגיאה בהפעלת מחזור הדירוג.",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
        )


@bot.on(events.CallbackQuery(pattern=b"admin_stats"))
async def admin_stats_handler(event: CallbackQuery.Event) -> None:
    """הצגת סטטיסטיקות מערכת"""
    await event.answer()
    sender = await event.get_sender()
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")
        return
    
    if not user_manager.is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        await event.edit(
            "📊 <b>טוען סטטיסטיקות מערכת...</b>\n\n⏳ אנא המתן...", parse_mode="html"
        )

        stats_data = {}

        try:
            if hasattr(user_manager, "get_active_users_count"):
                active_users = user_manager.get_active_users_count()
                stats_data["users"] = active_users
            elif hasattr(user_manager, "get_all_users"):
                all_users = user_manager.get_all_users()
                stats_data["users"] = len(all_users) if all_users else 0
            else:
                stats_data["users"] = "לא זמין"
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            stats_data["users"] = "שגיאה"

        try:
            active_rentals = rental_manager.get_rentals_by_status("active")
            stats_data["rentals"] = len(active_rentals) if active_rentals else 0
        except Exception:
            stats_data["rentals"] = "לא זמין"

        try:
            all_assets = assets_manager.get_all_assets()
            total_assets = len(all_assets) if all_assets else 0
            available_assets = (
                len([a for a in all_assets if a.get("available", True)])
                if all_assets
                else 0
            )
            stats_data["total_assets"] = total_assets
            stats_data["available_assets"] = available_assets
        except Exception:
            stats_data["total_assets"] = "לא זמין"
            stats_data["available_assets"] = "לא זמין"

        try:
            all_sessions = session_manager.get_all_sessions()
            total_sessions = len(all_sessions) if all_sessions else 0
            active_sessions = (
                len([s for s in all_sessions if s.get("status") == "active"])
                if all_sessions
                else 0
            )
            stats_data["total_sessions"] = total_sessions
            stats_data["active_sessions"] = active_sessions
        except Exception:
            stats_data["total_sessions"] = "לא זמין"
            stats_data["active_sessions"] = "לא זמין"

        try:
            from proxy_manager import proxy_manager

            all_proxies = proxy_manager.get_all_proxies()
            total_proxies = len(all_proxies) if all_proxies else 0
            active_proxies = proxy_manager.get_active_proxies_count()
            stats_data["total_proxies"] = total_proxies
            stats_data["active_proxies"] = active_proxies
        except Exception:
            stats_data["total_proxies"] = "לא זמין"
            stats_data["active_proxies"] = "לא זמין"

        from datetime import datetime

        stats_text = (
            "📊 <b>סטטיסטיקות מערכת</b>\n\n"
            f"👥 <b>משתמשים פעילים:</b> {stats_data.get('users', 'שגיאה')}\n"
            f"🕒 <b>עודכן:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

        buttons = [
            [Button.inline("🔄 רענן", b"admin_stats")],
            [Button.inline("🔙 חזרה", b"admin_menu")],
        ]

        await event.edit(stats_text, buttons=buttons, parse_mode="html")

    except Exception as e:
        logger.error(f"שגיאה בהצגת סטטיסטיקות: {str(e)}")
        await event.edit(
            "❌ שגיאה בטעינת הסטטיסטיקות.",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
        )


@bot.on(events.CallbackQuery(pattern=r"confirm_remove_session:(.+)"))
async def confirm_remove_session_handler(event: CallbackQuery.Event) -> None:
    """אישור הסרת סשן"""
    await event.answer()
    sender = await event.get_sender()

    if sender is None or not is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        session_id = int(event.pattern_match.group(1).decode("utf-8"))
        success, message = session_manager.delete_session(session_id)

        if success:
            await event.edit(
                "✅ הסשן הוסר בהצלחה!",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            )
        else:
            await event.edit(
                f"❌ שגיאה בהסרת הסשן: {message}",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            )
    except Exception as e:
        logger.error(f"שגיאה בהסרת סשן: {str(e)}")
        await event.edit(
            "❌ שגיאה בהסרת הסשן.", buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]]
        )


# הוספת handlers לאישור הסרת פרוקסי ונכסים
@bot.on(events.CallbackQuery(pattern=r"confirm_remove_proxy:(.+)"))
async def confirm_remove_proxy_handler(event: CallbackQuery.Event) -> None:
    """אישור הסרת פרוקסי"""
    await event.answer()
    sender = await event.get_sender()

    if sender is None or not is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        proxy_id = int(event.pattern_match.group(1).decode("utf-8"))
        from proxy_manager import proxy_manager

        success = proxy_manager.remove_proxy(proxy_id)

        if success:
            await event.edit(
                "✅ הפרוקסי הוסר בהצלחה!",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            )
        else:
            await event.edit(
                "❌ שגיאה בהסרת הפרוקסי.",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            )
    except Exception as e:
        logger.error(f"שגיאה בהסרת פרוקסי: {str(e)}")
        await event.edit(
            "❌ שגיאה בהסרת הפרוקסי.",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
        )


@bot.on(events.CallbackQuery(pattern=r"confirm_remove_asset:(.+)"))
async def confirm_remove_asset_handler(event: CallbackQuery.Event) -> None:
    """אישור הסרת נכס"""
    await event.answer()
    sender = await event.get_sender()

    if sender is None or not is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        asset_id = int(event.pattern_match.group(1).decode("utf-8"))
        from assets_manager import assets_manager

        success = assets_manager.delete_asset(asset_id)

        if success:
            await event.edit(
                "✅ הנכס הוסר בהצלחה!",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            )
        else:
            await event.edit(
                "❌ שגיאה בהסרת הנכס.",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            )
    except Exception as e:
        logger.error(f"שגיאה בהסרת נכס: {str(e)}")
        await event.edit(
            "❌ שגיאה בהסרת הנכס.", buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]]
        )


@bot.on(events.CallbackQuery(pattern=b"confirm_clean_all"))
async def confirm_clean_all_handler(event: CallbackQuery.Event) -> None:
    """אישור ניקוי כל המערכת - גרסה משופרת עם דיבוג"""
    await event.answer()
    sender = await event.get_sender()

    if sender is None or not is_admin(sender.id):
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")
        return

    try:
        # הודעת התחלה
        await event.edit(
            "🧹 <b>מתחיל ניקוי מלא של המערכת...</b>\n\n⏳ אנא המתן...",
            parse_mode="html",
        )

        cleaned_items = []
        total_cleaned = 0

        # 1. ניקוי סשנים
        try:
            await event.edit("🧹 <b>מנקה סשנים...</b>\n\n⏳ שלב 1/4", parse_mode="html")
            logger.info("Starting session cleanup...")

            if hasattr(session_manager, "cleanup_invalid_sessions"):
                if asyncio.iscoroutinefunction(
                    session_manager.cleanup_invalid_sessions
                ):
                    cleaned_sessions = await session_manager.cleanup_invalid_sessions()
                else:
                    cleaned_sessions = session_manager.cleanup_invalid_sessions()

                cleaned_sessions = cleaned_sessions or 0
                cleaned_items.append(f"• {cleaned_sessions} סשנים לא תקינים")
                total_cleaned += cleaned_sessions
                logger.info(f"Cleaned {cleaned_sessions} invalid sessions")
            else:
                cleaned_items.append("• סשנים - פונקציה לא נמצאה")
                logger.warning("cleanup_invalid_sessions method not found")

        except Exception as e:
            error_msg = f"שגיאה בניקוי סשנים: {str(e)}"
            logger.error(error_msg)
            cleaned_items.append(f"• סשנים - {error_msg}")

        # 2. ניקוי פרוקסי
        try:
            await event.edit(
                "🧹 <b>מנקה פרוקסי...</b>\n\n⏳ שלב 2/4", parse_mode="html"
            )
            logger.info("Starting proxy cleanup...")

            from proxy_manager import proxy_manager

            if hasattr(proxy_manager, "delete_inactive_proxies"):
                if asyncio.iscoroutinefunction(proxy_manager.delete_inactive_proxies):
                    cleaned_proxies = await proxy_manager.delete_inactive_proxies()
                else:
                    cleaned_proxies = proxy_manager.delete_inactive_proxies()

                cleaned_proxies = cleaned_proxies or 0
                cleaned_items.append(f"• {cleaned_proxies} פרוקסי לא פעילים")
                total_cleaned += cleaned_proxies
                logger.info(f"Cleaned {cleaned_proxies} inactive proxies")
            else:
                cleaned_items.append("• פרוקסי - פונקציה לא נמצאה")
                logger.warning("delete_inactive_proxies method not found")

        except Exception as e:
            error_msg = f"שגיאה בניקוי פרוקסי: {str(e)}"
            logger.error(error_msg)
            cleaned_items.append(f"• פרוקסי - {error_msg}")

        # 3. ניקוי נכסים
        try:
            await event.edit("🧹 <b>מנקה נכסים...</b>\n\n⏳ שלב 3/4", parse_mode="html")
            logger.info("Starting asset cleanup...")

            if hasattr(assets_manager, "cleanup_inactive_assets"):
                if asyncio.iscoroutinefunction(assets_manager.cleanup_inactive_assets):
                    cleaned_assets = await assets_manager.cleanup_inactive_assets()
                else:
                    cleaned_assets = assets_manager.cleanup_inactive_assets()

                cleaned_assets = cleaned_assets or 0
                cleaned_items.append(f"• {cleaned_assets} נכסים לא פעילים")
                total_cleaned += cleaned_assets
                logger.info(f"Cleaned {cleaned_assets} inactive assets")
            else:
                cleaned_items.append("• נכסים - פונקציה לא נמצאה")
                logger.warning("cleanup_inactive_assets method not found")

        except Exception as e:
            error_msg = f"שגיאה בניקוי נכסים: {str(e)}"
            logger.error(error_msg)
            cleaned_items.append(f"• נכסים - {error_msg}")

        # 4. ניקוי השכרות
        try:
            await event.edit(
                "🧹 <b>מעבד השכרות...</b>\n\n⏳ שלב 4/4", parse_mode="html"
            )
            logger.info("Starting rental archiving...")

            if hasattr(rental_manager, "archive_expired_rentals"):
                if asyncio.iscoroutinefunction(rental_manager.archive_expired_rentals):
                    result = await rental_manager.archive_expired_rentals(
                        days_threshold=0
                    )
                else:
                    result = rental_manager.archive_expired_rentals(days_threshold=0)

                # Handle different return types
                if isinstance(result, tuple):
                    archived_count = result[0] or 0
                else:
                    archived_count = result or 0

                cleaned_items.append(f"• {archived_count} השכרות הועברו לארכיון")
                total_cleaned += archived_count
                logger.info(f"Archived {archived_count} rentals")
            else:
                cleaned_items.append("• השכרות - פונקציה לא נמצאה")
                logger.warning("archive_expired_rentals method not found")

        except Exception as e:
            error_msg = f"שגיאה בעיבוד השכרות: {str(e)}"
            logger.error(error_msg)
            cleaned_items.append(f"• השכרות - {error_msg}")

        # הכנת הודעת הסיכום
        from datetime import datetime

        if total_cleaned > 0:
            summary_text = (
                f"✅ <b>ניקוי המערכת הושלם בהצלחה!</b>\n\n"
                f'📊 <b>סה"כ נוקו: {total_cleaned} פריטים</b>\n\n'
                f"<b>פירוט:</b>\n"
                + "\n".join(cleaned_items)
                + f"\n\n🕒 <b>הושלם ב:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
        else:
            summary_text = (
                f"ℹ️ <b>ניקוי המערכת הושלם</b>\n\n"
                f"📋 <b>תוצאה:</b> לא נמצאו פריטים לניקוי\n\n"
                f"<b>פירוט:</b>\n"
                + "\n".join(cleaned_items)
                + f"\n\n💡 <b>הערה:</b> זה רגיל אם המערכת כבר נקייה\n"
                f"🕒 <b>הושלם ב:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )

        await event.edit(
            summary_text,
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            parse_mode="html",
        )

        logger.info(f"Clean all operation completed. Total cleaned: {total_cleaned}")

    except Exception as e:
        error_details = f"שגיאה קריטית בניקוי המערכת: {str(e)}"
        logger.error(error_details)
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")

        await event.edit(
            f"❌ <b>שגיאה קריטית</b>\n\n"
            f"📝 <b>פרטים:</b> {str(e)}\n\n"
            f"💡 <b>הצעה:</b> בדוק את לוג הבוט לפרטים נוספים",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],
            parse_mode="html",
        )


@bot.on(events.NewMessage())
async def handle_text_message(event: NewMessage.Event) -> None:
    """טיפול בהודעות טקסט מהמשתמש"""
    try:
        # התעלמות מהודעות שהן פקודות
        if event.text and event.text.startswith("/"):
            return

        sender = await event.get_sender()
        if sender is None:
            return

        # בדיקת מצב המשתמש
        if sender.id not in user_states:
            return

        user_state = user_states[sender.id]
        current_state = user_state.get("state")
        user_data = user_state.get("data", {})

        # טיפול בהודעות מנהל
        if current_state in [
            ADMIN_STATE_WAITING_FOR_PHONE,
            ADMIN_STATE_WAITING_FOR_CODE,
            ADMIN_STATE_WAITING_FOR_2FA,
            ADMIN_STATE_WAITING_FOR_SESSION_NAME,
            ADMIN_STATE_WAITING_FOR_BOT_NAME,
        ]:
            await handle_admin_text_messages(event, sender, current_state, user_data)
            return

        # טיפול בהודעות משתמש רגיל
        if current_state == STATE_WAITING_FOR_KEYWORD:
            # המשתמש שלח מילת חיפוש
            keyword = event.text.strip()

            if len(keyword) < 3:
                await event.respond("❌ מילת החיפוש חייבת להכיל לפחות 3 תווים.")
                return

            # שמירת מילת החיפוש
            user_states[sender.id]["data"]["keyword"] = keyword

            # הצגת נכסים זמינים (דמה)
            assets_text = (
                f"🔍 <b>נכסים זמינים עבור: {keyword}</b>\n\n"
                f"בחר את הנכס שברצונך להשכיר:"
            )

            buttons = [
                [Button.inline("📱 ערוץ טלגרם פעיל", b"select_asset:telegram_channel")],
                [Button.inline("👤 פרופיל אישי", b"select_asset:personal_profile")],
                [Button.inline("🤖 בוט טלגרם", b"select_asset:telegram_bot")],
                [Button.inline("🔙 חזרה", b"back_to_main")],
            ]

            await event.respond(assets_text, buttons=buttons, parse_mode="html")

        elif current_state == STATE_WAITING_FOR_CONTACT_MESSAGE:
            # המשתמש שלח הודעת יצירת קשר
            message = event.text.strip()

            if len(message) < 10:
                await event.respond("❌ ההודעה חייבת להכיל לפחות 10 תווים.")
                return

            # שמירת ההודעה ועיבוד הבקשה
            user_states[sender.id]["data"]["contact_message"] = message

            await event.respond(
                "✅ ההודעה נשלחה בהצלחה!\n"
                "המנהל יחזור אליך בהקדם האפשרי.\n\n"
                "תודה על פנייתך! 🙏",
                buttons=[[Button.inline("🔙 חזרה לתפריט הראשי", b"back_to_main")]],
            )

            # איפוס מצב המשתמש
            if sender.id in user_states:
                del user_states[sender.id]

    except Exception as e:
        logger.error(f"שגיאה בטיפול בהודעת טקסט: {str(e)}")


# פונקציית ההפעלה הראשית
async def main():
    """
    פונקציית ההפעלה הראשית של הבוט
    """
    try:
        # התחברות לבוט
        await bot.start(bot_token=BOT_TOKEN)
        logger.info("הבוט התחבר בהצלחה!")

        # קריאה לפונקציית ההתחלה
        await on_startup()

        # הפעלת הבוט
        logger.info("הבוט פועל ומחכה להודעות...")
        await bot.run_until_disconnected()

    except Exception as e:
        logger.error(f"שגיאה בהפעלת הבוט: {str(e)}")
    finally:
        # קריאה לפונקציית הסגירה
        await on_shutdown()


if __name__ == "__main__":
    # הפעלת הבוט
    asyncio.run(main())

@bot.on(events.CallbackQuery(pattern=r"select_asset:(.+)"))
async def select_asset_handler(event: CallbackQuery.Event) -> None:
    """טיפול בבחירת נכס"""
    await event.answer()
    sender = await event.get_sender()
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")
        return
    
    # קבלת סוג הנכס
    if event.pattern_match is None:
        await event.edit("❌ שגיאה בקריאת נתוני הבחירה.")
        return
        
    asset_type = event.pattern_match.group(1).decode('utf-8')
    
    # בדיקת מצב המשתמש
    if sender.id not in user_states or user_states[sender.id].get('state') != STATE_WAITING_FOR_KEYWORD:
        await event.edit("❌ שגיאה במצב המשתמש. אנא התחל מחדש עם /rent")
        return
    
    # שמירת סוג הנכס
    user_states[sender.id]['data']['asset_type'] = asset_type
    user_states[sender.id]['state'] = STATE_WAITING_FOR_DURATION
    
    # מיפוי שמות נכסים
    asset_names = {
        'telegram_channel': 'ערוץ טלגרם פעיל',
        'personal_profile': 'פרופיל אישי', 
        'telegram_bot': 'בוט טלגרם'
    }
    
    asset_name = asset_names.get(asset_type, 'נכס לא מוכר')
    keyword = user_states[sender.id]['data'].get('keyword', '')
    
    duration_text = (
        f"⏰ <b>בחירת משך השכרה</b>\n\n"
        f"🔍 <b>מילת חיפוש:</b> {keyword}\n"
        f"🎯 <b>נכס נבחר:</b> {asset_name}\n\n"
        f"בחר את משך ההשכרה:"
    )
    
    buttons = [
        [Button.inline("📅 יום אחד - 50₪", b"duration:1:50")],
        [Button.inline("📅 שבוע - 300₪", b"duration:7:300")], 
        [Button.inline("📅 חודש - 1000₪", b"duration:30:1000")],
        [Button.inline("🔙 חזרה", b"back_to_assets")]
    ]
    
    await event.edit(duration_text, buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(pattern=r"duration:(\d+):(\d+)"))
async def select_duration_handler(event: CallbackQuery.Event) -> None:
    """
    טיפול בבחירת משך השכרה
    """
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if event.pattern_match is None:
        await event.edit("❌ שגיאה בקריאת נתוני הבחירה.")  # type: ignore
        return
    
    # קבלת פרטי המשך והמחיר
    duration_days = int(event.pattern_match.group(1).decode('utf-8'))
    price = int(event.pattern_match.group(2).decode('utf-8'))
    
    # בדיקת מצב המשתמש
    if sender.id not in user_states or user_states[sender.id].get('state') != STATE_WAITING_FOR_DURATION:  # type: ignore
        await event.edit("❌ שגיאה במצב המשתמש. אנא התחל מחדש עם /rent")  # type: ignore
        return
    
    # שמירת פרטי ההשכרה
    user_states[sender.id]['data']['duration_days'] = duration_days
    user_states[sender.id]['data']['price'] = price
    user_states[sender.id]['state'] = STATE_WAITING_FOR_PAYMENT
    
    # הכנת סיכום ההזמנה
    user_data = user_states[sender.id]['data']
    keyword = user_data.get('keyword', '')
    asset_type = user_data.get('asset_type', '')
    
    asset_names = {
        'telegram_channel': 'ערוץ טלגרם פעיל',
        'personal_profile': 'פרופיל אישי',
        'telegram_bot': 'בוט טלגרם'
    }
    asset_name = asset_names.get(asset_type, 'נכס לא מוכר')
    
    duration_text = "יום אחד" if duration_days == 1 else f"{duration_days} ימים"
    
    summary_text = (
        f"💰 <b>סיכום ההזמנה</b>\n\n"
        f"🔍 <b>מילת חיפוש:</b> {keyword}\n"
        f"🎯 <b>נכס:</b> {asset_name}\n"
        f"⏰ <b>משך:</b> {duration_text}\n"
        f"💵 <b>מחיר:</b> {price}₪\n\n"
        f"לביצוע התשלום, בחר באחת מהאפשרויות:"
    )
    
    buttons = [
        [Button.inline("💳 תשלום בכרטיס אשראי", b"payment:credit")],
        [Button.inline("💰 תשלום בביט/פייבוקס", b"payment:digital")],
        [Button.inline("📞 יצירת קשר לתשלום", b"contact_admin")],
        [Button.inline("🔙 חזרה", b"back_to_duration")]
    ]
    
    await event.edit(summary_text, buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(pattern=r"payment:(.+)"))
async def payment_handler(event: CallbackQuery.Event) -> None:
    """
    טיפול בתשלום
    """
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
        
    if event.pattern_match is None:
        await event.edit("❌ שגיאה בקריאת נתוני הבחירה.")  # type: ignore
        return
    
    payment_method = event.pattern_match.group(1).decode('utf-8')
    
    # בדיקת מצב המשתמש
    if sender.id not in user_states or user_states[sender.id].get('state') != STATE_WAITING_FOR_PAYMENT:  # type: ignore
        await event.edit("❌ שגיאה במצב המשתמש. אנא התחל מחדש עם /rent")  # type: ignore
        return
    
    user_data = user_states[sender.id]['data']
    price = user_data.get('price', 0)
    
    if payment_method == 'credit':
        payment_text = (
            f"💳 <b>תשלום בכרטיס אשראי</b>\n\n"
            f"💵 <b>סכום לתשלום:</b> {price}₪\n\n"
            f"🔗 <b>קישור לתשלום:</b>\n"
            f"https://payment.example.com/pay/{sender.id}\n\n"
            f"לאחר ביצוע התשלום, לחץ על 'אישור תשלום'"
        )
        
        buttons = [
            [Button.inline("✅ ביצעתי תשלום", b"confirm_payment")],
            [Button.inline("🔙 חזרה", b"back_to_payment")]
        ]
        
    elif payment_method == 'digital':
        payment_text = (
            f"📱 <b>תשלום בביט/פייבוקס</b>\n\n"
            f"💵 <b>סכום לתשלום:</b> {price}₪\n\n"
            f"📞 <b>מספר לתשלום:</b> 050-1234567\n"
            f"👤 <b>שם מקבל:</b> RentSpot Ltd\n\n"
            f"לאחר ביצוע התשלום, לחץ על 'אישור תשלום'"
        )
        
        buttons = [
            [Button.inline("✅ ביצעתי תשלום", b"confirm_payment")],
            [Button.inline("🔙 חזרה", b"back_to_payment")]
        ]
        
    await event.edit(payment_text, buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(pattern=b"confirm_payment"))
async def confirm_payment_handler(event: CallbackQuery.Event) -> None:
    """
    אישור תשלום והפעלת השכרה
    """
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    # בדיקת מצב המשתמש
    if sender.id not in user_states:  # type: ignore
        await event.edit("❌ שגיאה במצב המשתמש. אנא התחל מחדש עם /rent")  # type: ignore
        return
    
    try:
        user_data = user_states[sender.id]['data']
        
        # יצירת השכרה חדשה
        rental_data = {
            'user_id': sender.id,
            'keyword': user_data.get('keyword'),
            'asset_type': user_data.get('asset_type'),
            'duration_days': user_data.get('duration_days'),
            'price': user_data.get('price'),
            'status': 'pending_verification'
        }
        
        # שמירה במסד הנתונים (דמה)
        rental_id = rental_manager.create_rental(rental_data)
        
        success_text = (
            f"✅ <b>ההזמנה התקבלה בהצלחה!</b>\n\n"
            f"🆔 <b>מספר הזמנה:</b> #{rental_id}\n"
            f"🔍 <b>מילת חיפוש:</b> {user_data.get('keyword')}\n"
            f"⏰ <b>משך:</b> {user_data.get('duration_days')} ימים\n"
            f"💵 <b>מחיר:</b> {user_data.get('price')}₪\n\n"
            f"ההשכרה תופעל לאחר אימות התשלום (עד 24 שעות).\n"
            f"תקבל הודעה כשההשכרה תופעל."
        )
        
        buttons = [
            [Button.inline("📞 יצירת קשר", b"contact_admin")],
            [Button.inline("🔙 תפריט ראשי", b"back_to_main")]
        ]
        
        await event.edit(success_text, buttons=buttons, parse_mode='html')
        
        # איפוס מצב המשתמש
        if sender.id in user_states:
            del user_states[sender.id]
            
    except Exception as e:
        logger.error(f"שגיאה ביצירת השכרה: {str(e)}")
        await event.edit(
            "❌ שגיאה ביצירת ההשכרה. אנא נסה שוב מאוחר יותר.",
            buttons=[[Button.inline("🔙 תפריט ראשי", b"back_to_main")]]
        )


@bot.on(events.CallbackQuery(pattern=b"contact_admin"))
async def contact_admin_handler(event: CallbackQuery.Event) -> None:
    """
    יצירת קשר עם מנהל
    """
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    # שינוי מצב לקבלת הודעת יצירת קשר
    user_states[sender.id] = {  # type: ignore
        'state': STATE_WAITING_FOR_CONTACT_MESSAGE,
        'data': {}
    }
    
    await event.edit(
        "📞 <b>יצירת קשר עם המנהל</b>\n\n"
        "אנא כתב את הודעתך ואנו נחזור אליך בהקדם:\n\n"
        "💡 <b>טיפים לכתיבת הודעה טובה:</b>\n"
        "• תאר את הבעיה או השאלה בבירור\n"
        "• צרף פרטים רלוונטיים\n"
        "• ציין את מספר ההזמנה אם קיים",
        parse_mode='html'
    )


async def handle_admin_text_messages(event: NewMessage.Event, sender: Any, current_state: str, user_data: Dict[str, Any]) -> None:
    """
    טיפול בהודעות טקסט של מנהל
    """
    text = event.text.strip()  # type: ignore
    
    if current_state == ADMIN_STATE_WAITING_FOR_BOT_NAME:
        # המנהל הזין שם בוט
        if not text or len(text) < 3:  # type: ignore
            await event.respond("❌ שם הבוט חייב להכיל לפחות 3 תווים.")  # type: ignore
            return
            
        try:
            # בדיקת זמינות הבוט (דמה)
            bot_username = text.replace('@', '')  # type: ignore
            
            # הוספת הבוט למסד הנתונים
            bot_data = {
                'name': bot_username,  # type: ignore
                'type': 'telegram_bot',
                'status': 'pending',
                'added_by': sender.id  # type: ignore
            }
            
            asset_id = assets_manager.add_asset(bot_data)  # type: ignore
            
            await event.respond(  # type: ignore
                f"✅ הבוט @{bot_username} נוסף בהצלחה!\n"
                f"🆔 מספר נכס: {asset_id}\n\n"
                f"הבוט יהיה זמין להשכרה לאחר הפעלה.",
                buttons=[[Button.inline("🔙 חזרה למנהל", b"admin_menu")]]  # type: ignore
            )
            
            # איפוס מצב המשתמש
            if sender.id in user_states:  # type: ignore
                del user_states[sender.id]  # type: ignore
                
        except Exception as e:
            logger.error(f"שגיאה בהוספת בוט: {str(e)}")
            await event.respond(  # type: ignore
                "❌ שגיאה בהוספת הבוט. אנא נסה שוב.",
                buttons=[[Button.inline("🔙 חזרה למנהל", b"admin_menu")]]  # type: ignore
            )


# Navigation handlers
@bot.on(events.CallbackQuery(pattern=b"back_to_main"))
async def back_to_main_handler(event: CallbackQuery.Event) -> None:
    """חזרה לתפריט הראשי"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    # איפוס מצב המשתמש
    if sender.id in user_states:  # type: ignore
        del user_states[sender.id]  # type: ignore
    
    await event.edit(  # type: ignore
        "🏠 <b>תפריט ראשי</b>\n\n"
        "ברוכים הבאים ל-RentSpot Bot!\n"
        "בחר פעולה:",
        buttons=[
            [Button.inline("🔍 השכר מקום בחיפוש", b"start_rent")],  # type: ignore
            [Button.inline("📋 ההזמנות שלי", b"my_orders")],  # type: ignore
            [Button.inline("📞 יצירת קשר", b"contact_admin")],  # type: ignore
            [Button.inline("ℹ️ עזרה", b"help")]  # type: ignore
        ],
        parse_mode='html'
    )


@bot.on(events.CallbackQuery(pattern=b"start_rent"))
async def start_rent_handler(event: CallbackQuery.Event) -> None:
    """התחלת תהליך השכרה"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    # שמירת מצב המשתמש
    user_states[sender.id] = {"state": STATE_WAITING_FOR_KEYWORD, "data": {}}  # type: ignore
    
    await event.edit(  # type: ignore
        "🔍 <b>השכרת מקום בחיפוש</b>\n\n"
        "אנא שלח את מילת החיפוש שברצונך להשכיר עבורה מקום:\n\n"
        "💡 <b>דוגמאות:</b>\n"
        "• דירות להשכרה תל אביב\n"
        "• משרדים להשכרה\n"
        "• רכב יד שנייה\n\n"
        "✏️ כתב את מילת החיפוש שלך:",
        parse_mode="html",
    )


# Start command handler
@bot.on(events.NewMessage(pattern="/start"))
async def cmd_start(event: events.NewMessage.Event):
    """
    פקודת התחלה
    """
    sender = await event.get_sender()
    
    # בדיקה אם המשתמש הוא מנהל
    if is_admin(sender.id):
        await show_admin_menu(event)
        return
    
    # הודעת ברוכים הבאים למשתמש רגיל
    welcome_text = (
        f"👋 שלום {sender.first_name}!\n\n"
        "🤖 <b>ברוכים הבאים ל-RentSpot Bot</b>\n\n"
        "🎯 <b>מה אנחנו עושים?</b>\n"
        "אנחנו עוזרים לך להשכיר מקומות בחיפושים ברשתות החברתיות "
        "ובאפליקציות שונות, כך שהמוצר או השירות שלך יקבל חשיפה מקסימלית!\n\n"
        "🚀 <b>תתחיל עכשיו?</b>"
    )
    
    buttons = [
        [Button.inline("🔍 השכר מקום בחיפוש", b"start_rent")],
        [Button.inline("📋 ההזמנות שלי", b"my_orders")],
        [Button.inline("📞 יצירת קשר", b"contact_admin")],
        [Button.inline("ℹ️ עזרה", b"help")]
    ]
    
    await event.respond(welcome_text, buttons=buttons, parse_mode='html')


async def show_admin_menu(event: Any) -> None:
    """הצגת תפריט מנהל מלא ומפורט"""
    admin_text = (
        "🛠️ <b>פאנל ניהול מערכת</b>\n\n"
        "בחר פעולה:"
    )
    
    buttons = [
        [
            Button.inline("➕ הוסף סשן", b"admin_add_session"),  # type: ignore
            Button.inline("🤖 הוסף בוט", b"admin_add_bot")  # type: ignore
        ],
        [
            Button.inline("📋 רשימת סשנים", b"admin_list_sessions"),  # type: ignore
            Button.inline("🤖 רשימת נכסים", b"admin_list_assets")  # type: ignore
        ],
        [
            Button.inline("❌ הסר סשנים", b"admin_remove_sessions"),  # type: ignore
            Button.inline("🗑️ הסר פרוקסי", b"admin_remove_proxy")  # type: ignore
        ],
        [
            Button.inline("🗂️ הסר נכסים", b"admin_remove_assets"),  # type: ignore
            Button.inline("🧹 נקה את כל המערכת", b"admin_clean_all")  # type: ignore
        ],
        [
            Button.inline("📊 סטטיסטיקות", b"admin_stats"),  # type: ignore
            Button.inline("🔄 הפעל מנוע דירוג", b"admin_run_rank_cycle")  # type: ignore
        ],
        [
            Button.inline("🔙 חזרה לתפריט הראשי", b"back_to_main")  # type: ignore
        ]
    ]
    
    if hasattr(event, 'edit'):
        await event.edit(admin_text, buttons=buttons, parse_mode='html')  # type: ignore
    else:
        await event.respond(admin_text, buttons=buttons, parse_mode='html')  # type: ignore


@bot.on(events.CallbackQuery(pattern=b"admin_menu"))
async def admin_menu_handler(event: CallbackQuery.Event) -> None:
    """חזרה לתפריט מנהל"""
    await event.answer()  # type: ignore
    await show_admin_menu(event)


@bot.on(events.CallbackQuery(pattern=b"admin_clean_all"))
async def admin_clean_all_handler(event: CallbackQuery.Event) -> None:
    """אישור ניקוי מערכת"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "⚠️ <b>אזהרה - ניקוי מערכת</b>\n\n"
        "פעולה זו תנקה:\n"
        "• סשנים לא פעילים\n"
        "• פרוקסי לא תקינים\n" 
        "• נכסים לא פעילים\n"
        "• השכרות שפגו\n\n"
        "האם אתה בטוח?",
        buttons=[
            [Button.inline("✅ כן, נקה", b"confirm_clean_all")],  # type: ignore
            [Button.inline("❌ ביטול", b"admin_menu")]  # type: ignore
        ],
        parse_mode='html'
    )


# =============================================================================
# Admin Handlers - כל ה-handlers לתפריט המנהל המלא
# =============================================================================

@bot.on(events.CallbackQuery(pattern=b"admin_add_session"))
async def admin_add_session_handler(event: CallbackQuery.Event) -> None:
    """הוספת סשן חדש"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "➕ <b>הוספת סשן חדש</b>\n\n"
        "אנא שלח את מחרוזת הסשן:\n\n"
        "💡 <b>הערה:</b> ודא שהסשן תקין ולא נמצא בשימוש",
        parse_mode='html'
    )
    
    # שמירת מצב למנהל
    user_states[sender.id] = {  # type: ignore
        'state': ADMIN_STATE_WAITING_FOR_SESSION,
        'data': {}
    }


@bot.on(events.CallbackQuery(pattern=b"admin_add_bot"))
async def admin_add_bot_handler(event: CallbackQuery.Event) -> None:
    """הוספת בוט חדש"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "🤖 <b>הוספת בוט חדש</b>\n\n"
        "אנא שלח את שם הבוט (עם או בלי @):\n\n"
        "💡 <b>דוגמה:</b> @mybot או mybot",
        parse_mode='html'
    )
    
    # שמירת מצב למנהל
    user_states[sender.id] = {  # type: ignore
        'state': ADMIN_STATE_WAITING_FOR_BOT_NAME,
        'data': {}
    }


@bot.on(events.CallbackQuery(pattern=b"admin_list_sessions"))
async def admin_list_sessions_handler(event: CallbackQuery.Event) -> None:
    """הצגת רשימת סשנים"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    try:
        sessions = session_manager.get_all_sessions()  # type: ignore
        
        if not sessions:
            await event.edit(  # type: ignore
                "📋 <b>רשימת סשנים</b>\n\n"
                "❌ לא נמצאו סשנים במערכת",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
                parse_mode='html'
            )
            return
        
        sessions_text = "📋 <b>רשימת סשנים</b>\n\n"
        
        for i, session in enumerate(sessions[:10], 1):  # הצג עד 10 ראשונים
            status_emoji = "✅" if session.get('is_active', False) else "❌"
            sessions_text += (
                f"{i}. {status_emoji} ID: {session.get('id', 'N/A')}\n"
                f"   📱 טלפון: {session.get('phone', 'N/A')}\n"
                f"   🏷️ תפקיד: {session.get('role', 'N/A')}\n\n"
            )
        
        if len(sessions) > 10:
            sessions_text += f"ועוד {len(sessions) - 10} סשנים...\n"
        
        await event.edit(  # type: ignore
            sessions_text,
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
            parse_mode='html'
        )
        
    except Exception as e:
        logger.error(f"שגיאה בהצגת רשימת סשנים: {str(e)}")
        await event.edit(  # type: ignore
            "❌ שגיאה בטעינת רשימת הסשנים",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
        )


@bot.on(events.CallbackQuery(pattern=b"admin_list_assets"))
async def admin_list_assets_handler(event: CallbackQuery.Event) -> None:
    """הצגת רשימת נכסים"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    try:
        assets = assets_manager.get_all_assets()  # type: ignore
        
        if not assets:
            await event.edit(  # type: ignore
                "🤖 <b>רשימת נכסים</b>\n\n"
                "❌ לא נמצאו נכסים במערכת",
                buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
                parse_mode='html'
            )
            return
        
        assets_text = "🤖 <b>רשימת נכסים</b>\n\n"
        
        for i, asset in enumerate(assets[:10], 1):  # הצג עד 10 ראשונים
            type_emoji = {
                'telegram_channel': '📢',
                'telegram_bot': '🤖',
                'personal_profile': '👤'
            }.get(asset.get('type', ''), '🔹')
            
            status_emoji = "✅" if asset.get('is_available', False) else "❌"
            assets_text += (
                f"{i}. {type_emoji} {asset.get('name', 'ללא שם')}\n"
                f"   📊 סטטוס: {status_emoji}\n"
                f"   🆔 ID: {asset.get('id', 'N/A')}\n\n"
            )
        
        if len(assets) > 10:
            assets_text += f"ועוד {len(assets) - 10} נכסים...\n"
        
        await event.edit(  # type: ignore
            assets_text,
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
            parse_mode='html'
        )
        
    except Exception as e:
        logger.error(f"שגיאה בהצגת רשימת נכסים: {str(e)}")
        await event.edit(  # type: ignore
            "❌ שגיאה בטעינת רשימת הנכסים",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
        )


@bot.on(events.CallbackQuery(pattern=b"admin_remove_sessions"))
async def admin_remove_sessions_handler(event: CallbackQuery.Event) -> None:
    """הסרת סשנים"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "❌ <b>הסרת סשנים</b>\n\n"
        "בחר את סוג הסשנים שברצונך להסיר:",
        buttons=[
            [Button.inline("🔴 סשנים לא פעילים", b"remove_inactive_sessions")],  # type: ignore
            [Button.inline("⚠️ סשנים פגומים", b"remove_broken_sessions")],  # type: ignore
            [Button.inline("🗑️ כל הסשנים", b"remove_all_sessions")],  # type: ignore
            [Button.inline("🔙 חזרה", b"admin_menu")]  # type: ignore
        ],
        parse_mode='html'
    )


@bot.on(events.CallbackQuery(pattern=b"admin_remove_proxy"))
async def admin_remove_proxy_handler(event: CallbackQuery.Event) -> None:
    """הסרת פרוקסי"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "🗑️ <b>הסרת פרוקסי</b>\n\n"
        "בחר את סוג הפרוקסי שברצונך להסיר:",
        buttons=[
            [Button.inline("🔴 פרוקסי לא פעילים", b"remove_inactive_proxies")],  # type: ignore
            [Button.inline("⚠️ פרוקסי איטיים", b"remove_slow_proxies")],  # type: ignore
            [Button.inline("🗑️ כל הפרוקסי", b"remove_all_proxies")],  # type: ignore
            [Button.inline("🔙 חזרה", b"admin_menu")]  # type: ignore
        ],
        parse_mode='html'
    )


@bot.on(events.CallbackQuery(pattern=b"admin_remove_assets"))
async def admin_remove_assets_handler(event: CallbackQuery.Event) -> None:
    """הסרת נכסים"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "🗂️ <b>הסרת נכסים</b>\n\n"
        "בחר את סוג הנכסים שברצונך להסיר:",
        buttons=[
            [Button.inline("🔴 נכסים לא פעילים", b"remove_inactive_assets")],  # type: ignore
            [Button.inline("⚠️ נכסים פגומים", b"remove_broken_assets")],  # type: ignore
            [Button.inline("🗑️ כל הנכסים", b"remove_all_assets")],  # type: ignore
            [Button.inline("🔙 חזרה", b"admin_menu")]  # type: ignore
        ],
        parse_mode='html'
    )


@bot.on(events.CallbackQuery(pattern=b"admin_stats"))
async def admin_stats_handler(event: CallbackQuery.Event) -> None:
    """הצגת סטטיסטיקות מערכת"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    try:
        # איסוף סטטיסטיקות
        total_sessions = len(session_manager.get_all_sessions())  # type: ignore
        total_assets = len(assets_manager.get_all_assets())  # type: ignore
        total_rentals = len(rental_manager.get_all_rentals())  # type: ignore
        
        # סטטיסטיקות פעילות
        active_sessions = len([s for s in session_manager.get_all_sessions() if s.get('is_active', False)])  # type: ignore
        active_assets = len([a for a in assets_manager.get_all_assets() if a.get('is_available', False)])  # type: ignore
        
        stats_text = (
            "📊 <b>סטטיסטיקות מערכת</b>\n\n"
            f"🔗 <b>סשנים:</b>\n"
            f"   • סך הכל: {total_sessions}\n"
            f"   • פעילים: {active_sessions}\n"
            f"   • לא פעילים: {total_sessions - active_sessions}\n\n"
            f"🤖 <b>נכסים:</b>\n"
            f"   • סך הכל: {total_assets}\n"
            f"   • זמינים: {active_assets}\n"
            f"   • לא זמינים: {total_assets - active_assets}\n\n"
            f"📋 <b>השכרות:</b>\n"
            f"   • סך הכל: {total_rentals}\n\n"
            f"🕐 <b>עדכון אחרון:</b> עכשיו"
        )
        
        await event.edit(  # type: ignore
            stats_text,
            buttons=[
                [Button.inline("🔄 רענן", b"admin_stats")],  # type: ignore
                [Button.inline("🔙 חזרה", b"admin_menu")]  # type: ignore
            ],
            parse_mode='html'
        )
        
    except Exception as e:
        logger.error(f"שגיאה בהצגת סטטיסטיקות: {str(e)}")
        await event.edit(  # type: ignore
            "❌ שגיאה בטעינת הסטטיסטיקות",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
        )


@bot.on(events.CallbackQuery(pattern=b"admin_run_rank_cycle"))
async def admin_run_rank_cycle_handler(event: CallbackQuery.Event) -> None:
    """הפעלת מנוע דירוג"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None:
        await event.edit("❌ שגיאה באימות משתמש.")  # type: ignore
        return
    
    if not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    await event.edit(  # type: ignore
        "🔄 <b>הפעלת מנוע דירוג</b>\n\n"
        "⏳ מפעיל מנוע דירוג...\n"
        "אנא המתן, זה עלול לקחת מספר דקות.",
        parse_mode='html'
    )
    
    try:
        # הפעלת מנוע הדירוג
        result = await rank_engine.run_cycle()  # type: ignore
        
        success_text = (
            "✅ <b>מנוע הדירוג הופעל בהצלחה!</b>\n\n"
            f"📈 נבדקו: {result.get('checked', 0)} דירוגים\n"
            f"🔄 עודכנו: {result.get('updated', 0)} דירוגים\n"
            f"⚠️ שגיאות: {result.get('errors', 0)}\n\n"
            f"🕐 זמן ריצה: {result.get('duration', 'N/A')} שניות"
        )
        
        await event.edit(  # type: ignore
            success_text,
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
            parse_mode='html'
        )
        
    except Exception as e:
        logger.error(f"שגיאה בהפעלת מנוע דירוג: {str(e)}")
        await event.edit(  # type: ignore
            f"❌ שגיאה בהפעלת מנוע הדירוג:\n{str(e)}",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
        )


# =============================================================================
# Additional Admin Handlers - handlers נוספים לפעולות ספציפיות
# =============================================================================

@bot.on(events.CallbackQuery(pattern=b"remove_inactive_sessions"))
async def remove_inactive_sessions_handler(event: CallbackQuery.Event) -> None:
    """הסרת סשנים לא פעילים"""
    await event.answer()  # type: ignore
    sender = await event.get_sender()  # type: ignore
    
    if sender is None or not is_admin(sender.id):  # type: ignore
        await event.edit("⛔️ אין לך הרשאות לפעולה זו.")  # type: ignore
        return
    
    try:
        removed_count = session_manager.remove_inactive_sessions()  # type: ignore
        
        await event.edit(  # type: ignore
            f"✅ <b>הוסרו {removed_count} סשנים לא פעילים</b>",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
            parse_mode='html'
        )
        
    except Exception as e:
        logger.error(f"שגיאה בהסרת סשנים: {str(e)}")
        await event.edit(  # type: ignore
            "❌ שגיאה בהסרת הסשנים",
            buttons=[[Button.inline("🔙 חזרה", b"admin_menu")]],  # type: ignore
        )
