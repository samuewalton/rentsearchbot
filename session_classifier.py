# -*- coding: utf-8 -*-
"""Session classification helpers."""

from constants import Constants


class SessionClassifier:
    """Very light session classifier used for placeholder operations."""

    @staticmethod
    def is_clean(session_string: str) -> bool:
        """Determine if the given session can be considered clean.

        The placeholder implementation simply checks for a keyword in the
        session string. Real implementations would inspect the Telegram
        account's history via Telethon.
        """
        return "clean" in session_string.lower()

    @staticmethod
    def classify(session_string: str) -> str:
        """Return the detected session type."""
        if SessionClassifier.is_clean(session_string):
            return Constants.SESSION_TYPE_CLEAN
        return Constants.SESSION_TYPE_DIRTY

