-- הוספת שדה bot_token לטבלה assets
ALTER TABLE assets ADD COLUMN IF NOT EXISTS bot_token TEXT;

-- הוספת שדה status לטבלה assets (נראה שגם הוא חסר)
ALTER TABLE assets ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active';

-- בדיקה
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'assets' 
ORDER BY ordinal_position;
