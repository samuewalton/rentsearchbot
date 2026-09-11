-- =====================================================================
-- RentSpotBot / KeyRentBot — Canonical Database Schema (S3)
-- מקור יחיד לאמת. נטען ע"י db.init_database(), init_db.py, init_database.py
--
-- עקרונות:
--   * כל טבלה/עמודה שהקוד שואל — קיימת כאן (נאסף שיטתית מכל ה-SQL בקוד)
--   * שמות קנוניים: assets.available (לא is_available), users.telegram_id
--   * FK רופפים (ON DELETE SET NULL) כדי שמחיקה לעולם לא תיחסם
--   * UNIQUE(asset_id, keyword) — נדרש ל-ON CONFLICT ב-rank_checker
--   * settings.key הוא PK — נדרש ל-ON CONFLICT ב-db.set_setting
-- =====================================================================

-- ---------------------------------------------------------------------
-- users: משתמשי הבוט (מזוהים לפי telegram_id; id פנימי לטבלאות מקושרות)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    language_code VARCHAR(10) DEFAULT 'en',
    is_admin BOOLEAN DEFAULT FALSE,
    balance NUMERIC(15, 2) DEFAULT 0,
    preferences TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

-- ---------------------------------------------------------------------
-- proxies: פרוקסים (שמות העמודות תואמים ל-proxy_manager: ip/user/pass/type)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proxies (
    id SERIAL PRIMARY KEY,
    ip VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    "user" VARCHAR(255),
    "pass" VARCHAR(255),
    type VARCHAR(20) DEFAULT 'socks5',
    status VARCHAR(20) DEFAULT 'active',
    speed INTEGER,
    fail_count INTEGER DEFAULT 0,
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);

-- ---------------------------------------------------------------------
-- sessions: סשני טלגרם (type: clean/dirty/manager; status: active/...)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    session_string TEXT,
    type VARCHAR(20) DEFAULT 'clean',
    status VARCHAR(20) DEFAULT 'active',
    in_use BOOLEAN DEFAULT FALSE,
    api_id INTEGER,
    api_hash VARCHAR(255),
    proxy_id INTEGER REFERENCES proxies(id) ON DELETE SET NULL,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_type ON sessions(type);

-- ---------------------------------------------------------------------
-- assets: נכסים (בוטים/ערוצים/קבוצות). available הוא הדגל הקנוני.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT,
    name VARCHAR(255) NOT NULL,
    original_name VARCHAR(255),
    type VARCHAR(20),
    description TEXT,
    tags TEXT[] DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    available BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) DEFAULT 'active',
    bot_token TEXT,
    last_rank INTEGER,
    last_rank_keyword VARCHAR(255),
    last_rank_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_assets_telegram_id ON assets(telegram_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(type);
CREATE INDEX IF NOT EXISTS idx_assets_available ON assets(available);

-- ---------------------------------------------------------------------
-- rentals: השכרות (user_telegram_id הוא המזהה הקנוני בקוד)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rentals (
    id SERIAL PRIMARY KEY,
    user_telegram_id BIGINT NOT NULL,
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    keyword VARCHAR(255),
    asset_type VARCHAR(20),
    tier VARCHAR(20),
    rank INTEGER,
    price NUMERIC(10, 2),
    duration_hours INTEGER,
    status VARCHAR(20) DEFAULT 'pending',
    payment_id VARCHAR(255),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rentals_user ON rentals(user_telegram_id);
CREATE INDEX IF NOT EXISTS idx_rentals_status ON rentals(status);
CREATE INDEX IF NOT EXISTS idx_rentals_asset ON rentals(asset_id);

-- ---------------------------------------------------------------------
-- transactions: תנועות כספיות (יתרות, תשלומים, זיכויים)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    user_telegram_id BIGINT NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    transaction_type VARCHAR(50),
    rental_id INTEGER REFERENCES rentals(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_telegram_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(transaction_type);

-- ---------------------------------------------------------------------
-- rental_history: היסטוריית אירועים להשכרה (נכתב ב-S4; נקרא ב-user_manager)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rental_history (
    id SERIAL PRIMARY KEY,
    rental_id INTEGER REFERENCES rentals(id) ON DELETE SET NULL,
    user_telegram_id BIGINT,
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    keyword VARCHAR(255),
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rental_history_rental ON rental_history(rental_id);

-- ---------------------------------------------------------------------
-- rank_cache: מטמון דירוגים (UNIQUE נדרש ל-ON CONFLICT)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rank_cache (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    rank INTEGER NOT NULL,
    tier VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(asset_id, keyword)
);
CREATE INDEX IF NOT EXISTS idx_rank_cache_asset_id ON rank_cache(asset_id);
CREATE INDEX IF NOT EXISTS idx_rank_cache_keyword ON rank_cache(keyword);

-- ---------------------------------------------------------------------
-- settings: הגדרות מערכת (key הוא PK — נדרש ל-ON CONFLICT)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
