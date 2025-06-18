"""
מודול לאתחול מסד הנתונים
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# טעינת משתני סביבה מקובץ .env
load_dotenv()

# הגדרת לוגר
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_database():
    """
    אתחול מסד הנתונים - יצירת טבלאות אם הן לא קיימות
    
    Returns:
        האם האתחול הצליח
    """
    try:
        # קבלת מחרוזת החיבור מה-DATABASE_URL
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("DATABASE_URL לא הוגדר ב-env")
            return False
        
        logger.info(f"מתחבר למסד הנתונים: {database_url}")
            
        # טעינת קובץ הסכמה
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        logger.info(f"טוען סכמה מ: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # ביצוע השאילתות
        connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        
        try:
            with connection.cursor() as cur:
                logger.info("מבצע שאילתות יצירת טבלאות...")
                cur.execute(schema_sql)
                connection.commit()
                
                # בדיקה שהטבלאות נוצרו
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = cur.fetchall()
                
                if tables:
                    logger.info(f"נוצרו {len(tables)} טבלאות:")
                    for table in tables:
                        logger.info(f"- {table['table_name']}")
                else:
                    logger.warning("לא נמצאו טבלאות לאחר אתחול!")
                
            logger.info("מסד הנתונים אותחל בהצלחה")
            return True
        
        finally:
            connection.close()
            
    except Exception as e:
        logger.error(f"שגיאה באתחול מסד הנתונים: {str(e)}")
        return False

if __name__ == "__main__":
    print("מתחיל אתחול מסד הנתונים...")
    success = init_database()
    if success:
        print("מסד הנתונים אותחל בהצלחה!")
    else:
        print("אירעה שגיאה באתחול מסד הנתונים")
