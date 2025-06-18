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
    
    # Database schema
    schema_sql = '''
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username VARCHAR(255),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        language_code VARCHAR(10),
        is_bot BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Sessions table
    CREATE TABLE IF NOT EXISTS sessions (
        id SERIAL PRIMARY KEY,
        session_name VARCHAR(255) UNIQUE NOT NULL,
        api_id INTEGER,
        api_hash VARCHAR(255),
        session_data TEXT,
        status VARCHAR(50) DEFAULT 'inactive',
        user_id BIGINT REFERENCES users(user_id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Assets table  
    CREATE TABLE IF NOT EXISTS assets (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        type VARCHAR(100),
        value DECIMAL(15, 2),
        user_id BIGINT REFERENCES users(user_id),
        session_id INTEGER REFERENCES sessions(id),
        status VARCHAR(50) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Proxies table
    CREATE TABLE IF NOT EXISTS proxies (
        id SERIAL PRIMARY KEY,
        host VARCHAR(255) NOT NULL,
        port INTEGER NOT NULL,
        username VARCHAR(255),
        password VARCHAR(255),
        proxy_type VARCHAR(20) DEFAULT 'http',
        status VARCHAR(50) DEFAULT 'active',
        session_id INTEGER REFERENCES sessions(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Rentals table
    CREATE TABLE IF NOT EXISTS rentals (
        id SERIAL PRIMARY KEY,
        user_id BIGINT REFERENCES users(user_id),
        session_id INTEGER REFERENCES sessions(id),
        rental_type VARCHAR(100),
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        status VARCHAR(50) DEFAULT 'active',
        price DECIMAL(10, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
    CREATE INDEX IF NOT EXISTS idx_assets_user_id ON assets(user_id);
    CREATE INDEX IF NOT EXISTS idx_assets_session_id ON assets(session_id);
    CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);
    CREATE INDEX IF NOT EXISTS idx_rentals_user_id ON rentals(user_id);
    CREATE INDEX IF NOT EXISTS idx_rentals_status ON rentals(status);
    '''
    
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
        print('1. Run: python database_schema_check.py')
        print('2. Run: python safe_start.py')
    else:
        print('\n❌ Database initialization failed')
        print('Please check PostgreSQL is running and accessible')
