-- עדכון טבלת assets להוספת שדה bot_token
-- Script לעדכון מסד הנתונים PostgreSQL

-- הוסף שדה bot_token לטבלת assets
ALTER TABLE assets ADD bot_token TEXT;

-- הוסף הערה לשדה החדש  
COMMENT ON COLUMN assets.bot_token IS 'טוקן הבוט (רק לנכסים מסוג bot)';

-- הוסף אינדקס לביטחון ומהירות (אופציונלי)
CREATE INDEX IF NOT EXISTS idx_assets_bot_token ON assets(bot_token) WHERE bot_token IS NOT NULL;
