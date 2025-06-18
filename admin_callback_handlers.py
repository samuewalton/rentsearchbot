from aiogram import types, Dispatcher, F
from aiogram.types import CallbackQuery
from settings import Settings
from session_manager import Session
from rank_alerts import load_alerts


def register_admin_callbacks(dp: Dispatcher):

    @dp.callback_query(F.data == "view_sessions")
    async def cb_view_sessions(callback_query: CallbackQuery):
        sessions = Session.load_all()
        if not sessions:
            await callback_query.message.edit_text("\u26a0\ufe0f אין סשנים זמינים.")
            return
        session_list = "\n".join([f"- {s['asset_name']}" for s in sessions])
        await callback_query.message.edit_text(f"\U0001F5C3\ufe0f רשימת הסשנים:\n{session_list}")

    @dp.callback_query(F.data == "run_cycle")
    async def cb_run_cycle(callback_query: CallbackQuery):
        await callback_query.message.edit_text("\u23f3 מריץ סייקל דירוג...")
        from subprocess import run, CalledProcessError
        try:
            result = run(["python", "rank_engine.py"], capture_output=True, text=True, check=True)
            await callback_query.message.answer("\u2705 סייקל הסתיים בהצלחה:\n" + result.stdout)
        except CalledProcessError as e:
            await callback_query.message.answer(f"\u274c שגיאה:\n{e.stderr or e.stdout}")

    @dp.callback_query(F.data == "upload_asset")
    async def cb_upload_asset(callback_query: CallbackQuery):
        await callback_query.message.edit_text("\ud83d\udcc2 העלאת נכס חדש: שלח כעת את קובץ הסשן בפורמט JSON")

    @dp.callback_query(F.data == "manage_proxies")
    async def cb_manage_proxies(callback_query: CallbackQuery):
        await callback_query.message.edit_text("\ud83d\udec0 ניהול פרוקסים: שלח קובץ proxies.json לעדכון")

    @dp.callback_query(F.data == "view_alerts")
    async def cb_view_alerts(callback_query: CallbackQuery):
        alerts = load_alerts()
        if not alerts:
            await callback_query.message.edit_text("\u26a0\ufe0f אין התראות פעילות.")
            return
        alert_list = "\n".join([
            f"- {a['asset_name']} ירד למקום {a['new_rank']} עבור '{a['keyword']}'"
            for a in alerts
        ])
        await callback_query.message.edit_text(f"\ud83d\udce2 התראות פעילות:\n{alert_list}")
