#!/usr/bin/env python3
"""
Initialize PostgreSQL database with required tables
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

def create_database_tables():
    """Create all required tables in PostgreSQL"""
    
    # הסכמה הקנונית נטענת מ-schema.sql (מקור יחיד לאמת)
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    try:
        DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:admin@localhost:5432/rank_system')
        print(f'Connecting to: {DATABASE_URL}')
        
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print('Creating database tables...')
        cur.execute(schema_sql)
        
        # Verify tables were created
        cur.execute('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        ''')
        
        tables = cur.fetchall()
        print('✅ Database tables created successfully:')
        for table in tables:
            print(f'  - {table[0]}')
            
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f'❌ Database initialization failed: {e}')
        return False

if __name__ == '__main__':
    print('🚀 Initializing PostgreSQL Database for RentSpotBot')
    print('=' * 55)
    
    if create_database_tables():
        print('\n🎉 Database initialization complete!')
        print('\nNext steps:')
        print('1. Set DATABASE_URL in .env')
        print('2. Run: ./start_bot.sh')
    else:
        print('\n❌ Database initialization failed')
        print('Please check PostgreSQL is running and accessible')
