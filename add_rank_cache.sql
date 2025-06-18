-- טבלת מטמון דירוגים
CREATE TABLE IF NOT EXISTS rank_cache (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    rank INTEGER NOT NULL,
    tier VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rank_cache_asset_id ON rank_cache(asset_id);
CREATE INDEX IF NOT EXISTS idx_rank_cache_keyword ON rank_cache(keyword);
