import os
import json
import asyncio
from typing import Any, Callable, Coroutine, TypeVar, Optional
from concurrent.futures import ThreadPoolExecutor


def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path)


def load_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def print_banner(msg: str):
    print("\n" + "=" * 60)
    print(f"{msg.center(60)}")
    print("=" * 60 + "\n")


# TypeVar for generic return type
T = TypeVar('T')

class AsyncHelper:
    """
    עוזר להריץ פונקציות אסינכרוניות מהקשר סינכרוני
    ולהפך - לנהל תקשורת בין קוד סינכרוני ואסינכרוני
    """
    
    @staticmethod
    def run_async(coro: Coroutine) -> Any:
        """
        מריץ coroutine מהקשר סינכרוני
        
        Args:
            coro: הקורוטינה להרצה
            
        Returns:
            התוצאה מהקורוטינה
        """
        try:
            # נסה לקבל event loop קיים
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # אם יש כבר loop רץ, נשתמש ב-Future
                return asyncio.run_coroutine_threadsafe(coro, loop).result()
            else:
                # אם הלופ לא רץ, נריץ את הקורוטינה עד שתסתיים
                return loop.run_until_complete(coro)
        except RuntimeError:
            # אם אין event loop, ניצור אחד חדש
            return asyncio.run(coro)
    
    @staticmethod
    def run_in_thread(func: Callable, *args, **kwargs) -> Any:
        """
        מריץ פונקציה בלוקינג בthread נפרד
        
        Args:
            func: הפונקציה להרצה
            *args, **kwargs: פרמטרים לפונקציה
            
        Returns:
            התוצאה מהפונקציה
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result()
    
    @staticmethod
    async def run_sync_in_async(func: Callable, *args, **kwargs) -> Any:
        """
        מריץ פונקציה בלוקינג מתוך קוד אסינכרוני
        
        Args:
            func: הפונקציה להרצה
            *args, **kwargs: פרמטרים לפונקציה
            
        Returns:
            התוצאה מהפונקציה
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    
    @staticmethod
    def create_task(coro: Coroutine) -> Optional[asyncio.Task]:
        """
        יוצר משימה אסינכרונית שתרוץ ברקע
        
        Args:
            coro: הקורוטינה להרצה
            
        Returns:
            Task object או None אם נכשל
        """
        try:
            loop = asyncio.get_event_loop()
            return loop.create_task(coro)
        except RuntimeError:
            # אם אין event loop, פשוט מחזיר None
            return None


if __name__ == "__main__":
    print("[INFO] Utilities module ready.")
