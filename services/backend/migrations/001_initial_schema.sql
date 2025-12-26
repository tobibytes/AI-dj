-- AI DJ Database Schema
-- All tables prefixed with spotify_ as per requirements
-- Run this on your Neon database

-- ===========================================
-- OAuth Token Storage (replaces in-memory HashMap)
-- ===========================================
CREATE TABLE IF NOT EXISTS spotify_tokens (
    session_id VARCHAR(255) PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_in INTEGER DEFAULT 3600,
    expires_at TIMESTAMPTZ,
    user_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups and cleanup
CREATE INDEX IF NOT EXISTS idx_spotify_tokens_expires_at ON spotify_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_spotify_tokens_user_id ON spotify_tokens(user_id);

-- ===========================================
-- OAuth State Storage (for CSRF protection)
-- ===========================================
CREATE TABLE IF NOT EXISTS spotify_oauth_states (
    state VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Index for cleanup of expired states
CREATE INDEX IF NOT EXISTS idx_spotify_oauth_states_expires ON spotify_oauth_states(expires_at);

-- ===========================================
-- User Profiles (cached from Spotify API)
-- ===========================================
CREATE TABLE IF NOT EXISTS spotify_users (
    id VARCHAR(255) PRIMARY KEY,
    display_name VARCHAR(255),
    email VARCHAR(255),
    product VARCHAR(50), -- 'premium', 'free', etc.
    profile_image_url TEXT,
    country VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ===========================================
-- Mix History (track generated mixes)
-- ===========================================
CREATE TABLE IF NOT EXISTS spotify_mixes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) REFERENCES spotify_users(id),
    prompt TEXT NOT NULL,
    target_bpm REAL,
    duration_minutes INTEGER,
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, complete, error
    cdn_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Index for user mix history
CREATE INDEX IF NOT EXISTS idx_spotify_mixes_user ON spotify_mixes(user_id);
CREATE INDEX IF NOT EXISTS idx_spotify_mixes_session ON spotify_mixes(session_id);
CREATE INDEX IF NOT EXISTS idx_spotify_mixes_status ON spotify_mixes(status);

-- ===========================================
-- Mix Tracks (tracks included in each mix)
-- ===========================================
CREATE TABLE IF NOT EXISTS spotify_mix_tracks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mix_id UUID NOT NULL REFERENCES spotify_mixes(id) ON DELETE CASCADE,
    track_position INTEGER NOT NULL,
    spotify_track_id VARCHAR(255),
    title VARCHAR(500) NOT NULL,
    artist VARCHAR(500) NOT NULL,
    album VARCHAR(500),
    duration_ms INTEGER,
    bpm REAL,
    energy REAL,
    danceability REAL,
    key INTEGER,
    mode INTEGER, -- 0 = minor, 1 = major
    transition_type VARCHAR(50), -- 'crossfade', 'cut', 'beatmatch', etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for mix track lookups
CREATE INDEX IF NOT EXISTS idx_spotify_mix_tracks_mix ON spotify_mix_tracks(mix_id);

-- ===========================================
-- Cleanup function for expired tokens/states
-- ===========================================
CREATE OR REPLACE FUNCTION cleanup_expired_spotify_data() RETURNS void AS $$
BEGIN
    -- Delete expired OAuth states
    DELETE FROM spotify_oauth_states WHERE expires_at < NOW();
    
    -- Delete expired tokens (keep for 7 days after expiry for refresh attempts)
    DELETE FROM spotify_tokens WHERE expires_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Optional: Create a trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_spotify_tokens_updated_at
    BEFORE UPDATE ON spotify_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_spotify_users_updated_at
    BEFORE UPDATE ON spotify_users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
