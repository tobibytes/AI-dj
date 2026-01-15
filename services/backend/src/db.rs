use sqlx::{PgPool, postgres::PgPoolOptions};
use std::env;
use crate::models::mix::{MixSession, MixTrack, MixTransition, CreateMixRequest, MixData};
use uuid::Uuid;
use sqlx::types::chrono::Utc;
use tracing::{debug, Level};

#[derive(Clone)]
pub struct Database {
    pool: PgPool,
}

impl Database {
    pub async fn new() -> Result<Self, sqlx::Error> {
        let database_url = env::var("DATABASE_URL")
            .unwrap_or_else(|_| "postgres://user:password@localhost/ai_dj".to_string());
        debug!("DATABASE_URL={}", database_url);

        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(&database_url)
            .await?;

        Ok(Self { pool })
    }

    pub fn pool(&self) -> &PgPool {
        &self.pool
    }

    pub async fn create_mix_session(&self, session_id: Uuid, prompt: &str) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO dj_mix_sessions (id, prompt, status, created_at) VALUES ($1, $2, $3, $4)"
        )
        .bind(session_id)
        .bind(prompt)
        .bind("generating")
        .bind(Utc::now())
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    pub async fn save_mix_data(&self, session_id: Uuid, mix_data: CreateMixRequest) -> Result<(), sqlx::Error> {
        // Update session status and metadata
        sqlx::query(
            "UPDATE dj_mix_sessions SET status = $1, completed_at = $2, estimated_duration_minutes = $3 WHERE id = $4"
        )
        .bind("completed")
        .bind(Utc::now())
        .bind(mix_data.estimated_duration_minutes)
        .bind(session_id)
        .execute(&self.pool)
        .await?;

        // Insert tracks
        for track in mix_data.tracks {
            sqlx::query(
                "INSERT INTO dj_mix_tracks (id, mix_session_id, spotify_id, title, artist, album, duration_ms, key, energy, danceability, valence, acousticness, instrumentalness, popularity, track_order)
                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)"
            )
            .bind(Uuid::new_v4())
            .bind(session_id)
            .bind(track.spotify_id)
            .bind(track.title)
            .bind(track.artist)
            .bind(track.album)
            .bind(track.duration_ms)
            .bind(track.key)
            .bind(track.energy)
            .bind(track.danceability)
            .bind(track.valence)
            .bind(track.acousticness)
            .bind(track.instrumentalness)
            .bind(track.popularity)
            .bind(track.track_order)
            .execute(&self.pool)
            .await?;
        }

        // Insert transitions
        for transition in mix_data.transitions {
            sqlx::query(
                "INSERT INTO dj_mix_transitions (id, mix_session_id, from_track_order, to_track_order, transition_type, transition_bars, transition_direction)
                 VALUES ($1, $2, $3, $4, $5, $6, $7)"
            )
            .bind(Uuid::new_v4())
            .bind(session_id)
            .bind(transition.from_track_order)
            .bind(transition.to_track_order)
            .bind(transition.transition_type)
            .bind(transition.transition_bars)
            .bind(transition.transition_direction)
            .execute(&self.pool)
            .await?;
        }

        Ok(())
    }

    pub async fn update_mix_error(&self, session_id: Uuid, error_message: &str) -> Result<(), sqlx::Error> {
        sqlx::query(
            "UPDATE dj_mix_sessions SET status = $1, error_message = $2, completed_at = $3 WHERE id = $4"
        )
        .bind("error")
        .bind(error_message)
        .bind(Utc::now())
        .bind(session_id)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    pub async fn update_mix_cdn_url(&self, session_id: Uuid, cdn_url: &str) -> Result<(), sqlx::Error> {
        sqlx::query(
            "UPDATE dj_mix_sessions SET cdn_url = $1 WHERE id = $2"
        )
        .bind(cdn_url)
        .bind(session_id)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    pub async fn update_mix_status(&self, session_id: Uuid, status: &str) -> Result<(), sqlx::Error> {
        sqlx::query(
            "UPDATE dj_mix_sessions SET status = $1, completed_at = $2 WHERE id = $3"
        )
        .bind(status)
        .bind(Utc::now())
        .bind(session_id)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    pub async fn get_mix_session(&self, session_id: Uuid) -> Result<Option<MixSession>, sqlx::Error> {
        sqlx::query_as::<_, MixSession>(
            "SELECT * FROM dj_mix_sessions WHERE id = $1"
        )
        .bind(session_id)
        .fetch_optional(&self.pool)
        .await
    }

    pub async fn get_mix_tracks(&self, session_id: Uuid) -> Result<Vec<MixTrack>, sqlx::Error> {
        sqlx::query_as::<_, MixTrack>(
            "SELECT * FROM dj_mix_tracks WHERE mix_session_id = $1 ORDER BY track_order"
        )
        .bind(session_id)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn get_mix_transitions(&self, session_id: Uuid) -> Result<Vec<MixTransition>, sqlx::Error> {
        sqlx::query_as::<_, MixTransition>(
            "SELECT * FROM dj_mix_transitions WHERE mix_session_id = $1 ORDER BY from_track_order"
        )
        .bind(session_id)
        .fetch_all(&self.pool)
        .await
    }

    pub async fn get_mix_data(&self, session_id: Uuid) -> Result<Option<MixData>, sqlx::Error> {
        let session = match self.get_mix_session(session_id).await? {
            Some(s) => s,
            None => return Ok(None),
        };

        let tracks = self.get_mix_tracks(session_id).await?;
        let transitions = self.get_mix_transitions(session_id).await?;

        Ok(Some(MixData {
            session,
            tracks,
            transitions,
        }))
    }

    pub async fn list_mix_sessions(&self, limit: i64, offset: i64) -> Result<Vec<MixSession>, sqlx::Error> {
        sqlx::query_as::<_, MixSession>(
            "SELECT * FROM dj_mix_sessions ORDER BY created_at DESC LIMIT $1 OFFSET $2"
        )
        .bind(limit)
        .bind(offset)
        .fetch_all(&self.pool)
        .await
    }
}