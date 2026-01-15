use serde::{Deserialize, Serialize};
use sqlx::types::chrono::{DateTime, Utc};
use sqlx::FromRow;
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct MixSession {
    pub id: Uuid,
    pub prompt: String,
    pub status: String, // "generating", "completed", "error"
    pub created_at: DateTime<Utc>,
    pub completed_at: Option<DateTime<Utc>>,
    pub error_message: Option<String>,
    pub estimated_duration_minutes: Option<f64>,
    pub cdn_url: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct MixTrack {
    pub id: Uuid,
    pub mix_session_id: Uuid,
    pub spotify_id: String,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub duration_ms: i32,
    pub key: String,
    pub energy: f64,
    pub danceability: f64,
    pub valence: f64,
    pub acousticness: f64,
    pub instrumentalness: f64,
    pub popularity: i32,
    pub track_order: i32,
}

#[derive(Debug, Serialize, Deserialize, FromRow)]
pub struct MixTransition {
    pub id: Uuid,
    pub mix_session_id: Uuid,
    pub from_track_order: i32,
    pub to_track_order: i32,
    pub transition_type: String,
    pub transition_bars: i32,
    pub transition_direction: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MixData {
    pub session: MixSession,
    pub tracks: Vec<MixTrack>,
    pub transitions: Vec<MixTransition>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateMixRequest {
    pub prompt: String,
    pub tracks: Vec<CreateTrackRequest>,
    pub transitions: Vec<CreateTransitionRequest>,
    pub estimated_duration_minutes: Option<f64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateTrackRequest {
    pub spotify_id: String,
    pub title: String,
    pub artist: String,
    pub album: String,
    pub duration_ms: i32,
    pub key: String,
    pub energy: f64,
    pub danceability: f64,
    pub valence: f64,
    pub acousticness: f64,
    pub instrumentalness: f64,
    pub popularity: i32,
    pub track_order: i32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CreateTransitionRequest {
    pub from_track_order: i32,
    pub to_track_order: i32,
    pub transition_type: String,
    pub transition_bars: i32,
    pub transition_direction: Option<String>,
}