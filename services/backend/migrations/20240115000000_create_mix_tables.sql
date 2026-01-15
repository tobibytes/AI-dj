-- Create dj_mix_sessions table
CREATE TABLE IF NOT EXISTS dj_mix_sessions (
    id UUID PRIMARY KEY,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'generating',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    estimated_duration_minutes DOUBLE PRECISION,
    cdn_url TEXT
);

-- Create dj_mix_tracks table
CREATE TABLE IF NOT EXISTS dj_mix_tracks (
    id UUID PRIMARY KEY,
    mix_session_id UUID NOT NULL REFERENCES dj_mix_sessions(id) ON DELETE CASCADE,
    spotify_id TEXT NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    key TEXT NOT NULL,
    energy DOUBLE PRECISION NOT NULL,
    danceability DOUBLE PRECISION NOT NULL,
    valence DOUBLE PRECISION NOT NULL,
    acousticness DOUBLE PRECISION NOT NULL,
    instrumentalness DOUBLE PRECISION NOT NULL,
    popularity INTEGER NOT NULL,
    track_order INTEGER NOT NULL,
    UNIQUE(mix_session_id, track_order)
);

-- Create dj_mix_transitions table
CREATE TABLE IF NOT EXISTS dj_mix_transitions (
    id UUID PRIMARY KEY,
    mix_session_id UUID NOT NULL REFERENCES dj_mix_sessions(id) ON DELETE CASCADE,
    from_track_order INTEGER NOT NULL,
    to_track_order INTEGER NOT NULL,
    transition_type TEXT NOT NULL,
    transition_bars INTEGER NOT NULL,
    transition_direction TEXT,
    UNIQUE(mix_session_id, from_track_order, to_track_order)
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_dj_mix_sessions_created_at ON dj_mix_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dj_mix_sessions_status ON dj_mix_sessions(status);
CREATE INDEX IF NOT EXISTS idx_dj_mix_tracks_session_id ON dj_mix_tracks(mix_session_id);
CREATE INDEX IF NOT EXISTS idx_dj_mix_tracks_order ON dj_mix_tracks(mix_session_id, track_order);
CREATE INDEX IF NOT EXISTS idx_dj_mix_transitions_session_id ON dj_mix_transitions(mix_session_id);