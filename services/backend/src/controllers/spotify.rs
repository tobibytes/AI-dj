// Spotify OAuth and API controller
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::{IntoResponse, Json, Redirect},
};
use once_cell::sync::Lazy;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{error, info};

use crate::secrets::SECRET_MANAGER;
use crate::db::Database;

/// Spotify OAuth token storage (in production, use Redis)
pub static TOKEN_STORE: Lazy<Arc<RwLock<HashMap<String, SpotifyTokens>>>> =
    Lazy::new(|| Arc::new(RwLock::new(HashMap::new())));

/// Spotify API endpoints
const SPOTIFY_AUTH_URL: &str = "https://accounts.spotify.com/authorize";
const SPOTIFY_TOKEN_URL: &str = "https://accounts.spotify.com/api/token";
const SPOTIFY_API_URL: &str = "https://api.spotify.com/v1";

/// Spotify OAuth scopes required for full functionality
const SPOTIFY_SCOPES: &str = "user-read-private user-read-email streaming user-library-read user-top-read playlist-read-private";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpotifyTokens {
    pub access_token: String,
    pub refresh_token: Option<String>,
    pub expires_in: i64,
    pub token_type: String,
    #[serde(default)]
    pub scope: String,
}

#[derive(Debug, Deserialize)]
pub struct AuthCallbackQuery {
    pub code: Option<String>,
    pub error: Option<String>,
    pub state: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct RefreshTokenQuery {
    pub session_id: String,
}

#[derive(Debug, Serialize)]
pub struct AuthUrlResponse {
    pub auth_url: String,
    pub state: String,
}

#[derive(Debug, Serialize)]
pub struct TokenResponse {
    pub access_token: String,
    pub expires_in: i64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SpotifyUser {
    pub id: String,
    pub display_name: Option<String>,
    pub email: Option<String>,
    pub images: Vec<SpotifyImage>,
    pub product: Option<String>, // "premium", "free", etc.
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SpotifyImage {
    pub url: String,
    pub height: Option<i32>,
    pub width: Option<i32>,
}

#[derive(Debug, Serialize)]
pub struct AudioFeatures {
    pub id: String,
    pub tempo: f64,
    pub key: i32,
    pub mode: i32, // 0 = minor, 1 = major
    pub energy: f64,
    pub danceability: f64,
    pub valence: f64,
    pub acousticness: f64,
    pub instrumentalness: f64,
    pub loudness: f64,
    pub speechiness: f64,
    pub duration_ms: i64,
    pub time_signature: i32,
}

#[derive(Debug, Deserialize)]
pub struct SearchQuery {
    pub q: String,
    #[serde(default = "default_search_type")]
    pub search_type: String,
    #[serde(default = "default_limit")]
    pub limit: i32,
}

fn default_search_type() -> String {
    "track".to_string()
}

fn default_limit() -> i32 {
    20
}

#[derive(Debug, Deserialize)]
pub struct AudioFeaturesQuery {
    pub ids: String, // Comma-separated track IDs
}

#[derive(Debug, Deserialize)]
pub struct RecommendationsQuery {
    pub seed_tracks: Option<String>,
    pub seed_artists: Option<String>,
    pub seed_genres: Option<String>,
    pub target_tempo: Option<f64>,
    pub target_energy: Option<f64>,
    pub limit: Option<i32>,
}

pub struct SpotifyController {
    client: Client,
}

impl SpotifyController {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
        }
    }

    /// Generate OAuth authorization URL
    pub fn get_auth_url(&self, state: &str) -> String {
        let client_id = SECRET_MANAGER.get("SPOTIFY_CLIENT_ID");
        let redirect_uri = SECRET_MANAGER.get("SPOTIFY_REDIRECT_URI");

        format!(
            "{}?client_id={}&response_type=code&redirect_uri={}&scope={}&state={}",
            SPOTIFY_AUTH_URL,
            client_id,
            urlencoding::encode(&redirect_uri),
            urlencoding::encode(SPOTIFY_SCOPES),
            state
        )
    }

    /// Exchange authorization code for tokens
    pub async fn exchange_code(&self, code: &str) -> Result<SpotifyTokens, String> {
        let client_id = SECRET_MANAGER.get("SPOTIFY_CLIENT_ID");
        let client_secret = SECRET_MANAGER.get("SPOTIFY_CLIENT_SECRET");
        let redirect_uri = SECRET_MANAGER.get("SPOTIFY_REDIRECT_URI");

        let params = [
            ("grant_type", "authorization_code"),
            ("code", code),
            ("redirect_uri", &redirect_uri),
        ];

        let response = self
            .client
            .post(SPOTIFY_TOKEN_URL)
            .basic_auth(&client_id, Some(&client_secret))
            .form(&params)
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            error!("Spotify token exchange failed: {}", error_text);
            return Err(format!("Token exchange failed: {}", error_text));
        }

        let tokens: SpotifyTokens = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse tokens: {}", e))?;

        Ok(tokens)
    }

    /// Refresh access token
    pub async fn refresh_token(&self, refresh_token: &str) -> Result<SpotifyTokens, String> {
        let client_id = SECRET_MANAGER.get("SPOTIFY_CLIENT_ID");
        let client_secret = SECRET_MANAGER.get("SPOTIFY_CLIENT_SECRET");

        let params = [
            ("grant_type", "refresh_token"),
            ("refresh_token", refresh_token),
        ];

        let response = self
            .client
            .post(SPOTIFY_TOKEN_URL)
            .basic_auth(&client_id, Some(&client_secret))
            .form(&params)
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(format!("Token refresh failed: {}", error_text));
        }

        let mut tokens: SpotifyTokens = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse tokens: {}", e))?;

        // Keep the original refresh token if not provided in response
        if tokens.refresh_token.is_none() {
            tokens.refresh_token = Some(refresh_token.to_string());
        }

        Ok(tokens)
    }

    /// Get current user's profile
    pub async fn get_current_user(&self, access_token: &str) -> Result<SpotifyUser, String> {
        let response = self
            .client
            .get(format!("{}/me", SPOTIFY_API_URL))
            .bearer_auth(access_token)
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            return Err("Failed to get user profile".to_string());
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse user: {}", e))
    }

    /// Search for tracks, artists, or albums
    pub async fn search(
        &self,
        access_token: &str,
        query: &str,
        search_type: &str,
        limit: i32,
    ) -> Result<serde_json::Value, String> {
        let response = self
            .client
            .get(format!("{}/search", SPOTIFY_API_URL))
            .bearer_auth(access_token)
            .query(&[
                ("q", query),
                ("type", search_type),
                ("limit", &limit.to_string()),
            ])
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            return Err("Search failed".to_string());
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse search results: {}", e))
    }

    /// Get audio features for multiple tracks
    pub async fn get_audio_features(
        &self,
        access_token: &str,
        track_ids: &str,
    ) -> Result<serde_json::Value, String> {
        let response = self
            .client
            .get(format!("{}/audio-features", SPOTIFY_API_URL))
            .bearer_auth(access_token)
            .query(&[("ids", track_ids)])
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            return Err("Failed to get audio features".to_string());
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse audio features: {}", e))
    }

    /// Get track recommendations
    pub async fn get_recommendations(
        &self,
        access_token: &str,
        seed_tracks: Option<&str>,
        seed_artists: Option<&str>,
        seed_genres: Option<&str>,
        target_tempo: Option<f64>,
        target_energy: Option<f64>,
        limit: Option<i32>,
    ) -> Result<serde_json::Value, String> {
        let mut query: Vec<(&str, String)> = vec![];

        if let Some(tracks) = seed_tracks {
            query.push(("seed_tracks", tracks.to_string()));
        }
        if let Some(artists) = seed_artists {
            query.push(("seed_artists", artists.to_string()));
        }
        if let Some(genres) = seed_genres {
            query.push(("seed_genres", genres.to_string()));
        }
        if let Some(tempo) = target_tempo {
            query.push(("target_tempo", tempo.to_string()));
        }
        if let Some(energy) = target_energy {
            query.push(("target_energy", energy.to_string()));
        }
        query.push(("limit", limit.unwrap_or(20).to_string()));

        let response = self
            .client
            .get(format!("{}/recommendations", SPOTIFY_API_URL))
            .bearer_auth(access_token)
            .query(&query)
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            return Err(format!("Recommendations failed: {}", error_text));
        }

        response
            .json()
            .await
            .map_err(|e| format!("Failed to parse recommendations: {}", e))
    }

    /// Get access token using Client Credentials flow (no user login needed)
    /// This works for search, recommendations, audio features - anything that doesn't need user data
    pub async fn get_client_credentials_token(&self) -> Result<SpotifyTokens, String> {
        let client_id = SECRET_MANAGER.get("SPOTIFY_CLIENT_ID");
        let client_secret = SECRET_MANAGER.get("SPOTIFY_CLIENT_SECRET");

        let params = [("grant_type", "client_credentials")];

        let response = self
            .client
            .post(SPOTIFY_TOKEN_URL)
            .basic_auth(&client_id, Some(&client_secret))
            .form(&params)
            .send()
            .await
            .map_err(|e| format!("Request failed: {}", e))?;

        if !response.status().is_success() {
            let error_text = response.text().await.unwrap_or_default();
            error!("Client credentials auth failed: {}", error_text);
            return Err(format!("Client credentials auth failed: {}", error_text));
        }

        let tokens: SpotifyTokens = response
            .json()
            .await
            .map_err(|e| format!("Failed to parse tokens: {}", e))?;

        Ok(tokens)
    }
}

// Singleton instance
pub static SPOTIFY_CONTROLLER: Lazy<SpotifyController> = Lazy::new(|| SpotifyController::new());

// OAuth state store for CSRF protection
pub static OAUTH_STATE_STORE: Lazy<Arc<RwLock<HashMap<String, i64>>>> =
    Lazy::new(|| Arc::new(RwLock::new(HashMap::new())));

// Generate a cryptographically secure random state string
fn generate_state() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    
    // Use random bytes for unpredictability + timestamp for uniqueness
    let random_bytes: [u8; 16] = rand::random();
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    
    format!("{:032x}{:x}", 
        u128::from_be_bytes(random_bytes),
        timestamp
    )
}

// Validate and consume OAuth state (one-time use)
async fn validate_state(state: &str) -> bool {
    let mut store = OAUTH_STATE_STORE.write().await;
    
    // Check if state exists and is not expired (5 minutes max)
    if let Some(created_at) = store.remove(state) {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;
        
        // State valid for 5 minutes
        return now - created_at < 300;
    }
    
    false
}

// Store OAuth state with timestamp
async fn store_state(state: &str) {
    let mut store = OAUTH_STATE_STORE.write().await;
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_secs() as i64;
    
    store.insert(state.to_string(), now);
    
    // Clean up old states (older than 10 minutes)
    store.retain(|_, created_at| now - *created_at < 600);
}

// Route handlers

/// GET /spotify/auth - Redirect to Spotify authorization
pub async fn spotify_auth_route(State(_database): State<Database>) -> impl IntoResponse {
    let state = generate_state();
    
    // Store state for validation in callback
    store_state(&state).await;
    
    let auth_url = SPOTIFY_CONTROLLER.get_auth_url(&state);

    // Redirect browser directly to Spotify
    Redirect::temporary(&auth_url)
}

/// GET /spotify/callback - OAuth callback handler
pub async fn spotify_callback_route(
    State(_database): State<Database>,
    Query(params): Query<AuthCallbackQuery>,
) -> impl IntoResponse {
    // Validate CSRF state first
    let state = params.state.as_deref().unwrap_or("");
    if !validate_state(state).await {
        error!("Invalid or expired OAuth state");
        return Redirect::temporary(&format!(
            "{}?error=invalid_state",
            SECRET_MANAGER.get("FRONTEND_URL")
        ))
        .into_response();
    }
    
    if let Some(error) = params.error {
        error!("Spotify OAuth error: {}", error);
        return Redirect::temporary(&format!(
            "{}?error={}",
            SECRET_MANAGER.get("FRONTEND_URL"),
            error
        ))
        .into_response();
    }

    let code = match params.code {
        Some(c) => c,
        None => {
            return Redirect::temporary(&format!(
                "{}?error=no_code",
                SECRET_MANAGER.get("FRONTEND_URL")
            ))
            .into_response();
        }
    };

    match SPOTIFY_CONTROLLER.exchange_code(&code).await {
        Ok(tokens) => {
            // Store tokens with a cryptographically secure session ID
            let session_id = generate_state();
            {
                let mut store = TOKEN_STORE.write().await;
                store.insert(session_id.clone(), tokens.clone());
            }

            info!("Spotify auth successful, session: {}", session_id);

            // Redirect to frontend with ONLY session ID (not the access token!)
            // Frontend will fetch the token via /spotify/token endpoint
            Redirect::temporary(&format!(
                "{}?spotify_session={}",
                SECRET_MANAGER.get("FRONTEND_URL"),
                session_id
            ))
            .into_response()
        }
        Err(e) => {
            error!("Token exchange failed: {}", e);
            Redirect::temporary(&format!(
                "{}?error=token_exchange_failed",
                SECRET_MANAGER.get("FRONTEND_URL")
            ))
            .into_response()
        }
    }
}

/// GET /spotify/refresh - Refresh access token
pub async fn spotify_refresh_route(
    State(_database): State<Database>,
    Query(params): Query<RefreshTokenQuery>,
) -> impl IntoResponse {
    let store = TOKEN_STORE.read().await;
    let tokens = match store.get(&params.session_id) {
        Some(t) => t.clone(),
        None => {
            return (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "Session not found"})))
                .into_response();
        }
    };
    drop(store);

    let refresh_token = match &tokens.refresh_token {
        Some(rt) => rt.clone(),
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"error": "No refresh token available"})),
            )
                .into_response();
        }
    };

    match SPOTIFY_CONTROLLER.refresh_token(&refresh_token).await {
        Ok(new_tokens) => {
            // Update stored tokens
            let mut store = TOKEN_STORE.write().await;
            store.insert(params.session_id, new_tokens.clone());

            Json(TokenResponse {
                access_token: new_tokens.access_token,
                expires_in: new_tokens.expires_in,
            })
            .into_response()
        }
        Err(e) => {
            error!("Token refresh failed: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": e})),
            )
                .into_response()
        }
    }
}

/// GET /spotify/token - Fetch access token for session (one-time use after OAuth)
pub async fn spotify_token_route(
    State(_database): State<Database>,
    Query(params): Query<RefreshTokenQuery>,
) -> impl IntoResponse {
    let store = TOKEN_STORE.read().await;
    let tokens = match store.get(&params.session_id) {
        Some(t) => t.clone(),
        None => {
            return (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "Session not found"})))
                .into_response();
        }
    };
    drop(store);

    Json(TokenResponse {
        access_token: tokens.access_token,
        expires_in: tokens.expires_in,
    })
    .into_response()
}

/// GET /spotify/auto-auth - Auto-authenticate using Client Credentials (no user login needed)
/// Returns an access token that works for search, recommendations, audio features
pub async fn spotify_auto_auth_route(State(_database): State<Database>) -> impl IntoResponse {
    match SPOTIFY_CONTROLLER.get_client_credentials_token().await {
        Ok(tokens) => {
            // Store tokens with a session ID
            let session_id = generate_state();
            {
                let mut store = TOKEN_STORE.write().await;
                store.insert(session_id.clone(), tokens.clone());
            }

            info!("Auto-auth successful, session: {}", session_id);

            Json(serde_json::json!({
                "access_token": tokens.access_token,
                "expires_in": tokens.expires_in,
                "session_id": session_id,
                "type": "client_credentials"
            }))
            .into_response()
        }
        Err(e) => {
            error!("Auto-auth failed: {}", e);
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": e})),
            )
                .into_response()
        }
    }
}

/// GET /spotify/me - Get current user profile
pub async fn spotify_me_route(
    State(_database): State<Database>,
    headers: axum::http::HeaderMap,
) -> impl IntoResponse {
    let access_token = match headers.get("Authorization") {
        Some(h) => h.to_str().unwrap_or("").replace("Bearer ", ""),
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "No authorization header"})),
            )
                .into_response();
        }
    };

    match SPOTIFY_CONTROLLER.get_current_user(&access_token).await {
        Ok(user) => Json(user).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": e})),
        )
            .into_response(),
    }
}

/// GET /spotify/search - Search for tracks
pub async fn spotify_search_route(
    State(_database): State<Database>,
    Query(params): Query<SearchQuery>,
    headers: axum::http::HeaderMap,
) -> impl IntoResponse {
    let access_token = match headers.get("Authorization") {
        Some(h) => h.to_str().unwrap_or("").replace("Bearer ", ""),
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "No authorization header"})),
            )
                .into_response();
        }
    };

    match SPOTIFY_CONTROLLER
        .search(&access_token, &params.q, &params.search_type, params.limit)
        .await
    {
        Ok(results) => Json(results).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": e})),
        )
            .into_response(),
    }
}

/// GET /spotify/audio-features - Get audio features for tracks
pub async fn spotify_audio_features_route(
    State(_database): State<Database>,
    Query(params): Query<AudioFeaturesQuery>,
    headers: axum::http::HeaderMap,
) -> impl IntoResponse {
    let access_token = match headers.get("Authorization") {
        Some(h) => h.to_str().unwrap_or("").replace("Bearer ", ""),
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "No authorization header"})),
            )
                .into_response();
        }
    };

    match SPOTIFY_CONTROLLER
        .get_audio_features(&access_token, &params.ids)
        .await
    {
        Ok(features) => Json(features).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": e})),
        )
            .into_response(),
    }
}

/// GET /spotify/recommendations - Get track recommendations
pub async fn spotify_recommendations_route(
    State(_database): State<Database>,
    Query(params): Query<RecommendationsQuery>,
    headers: axum::http::HeaderMap,
) -> impl IntoResponse {
    let access_token = match headers.get("Authorization") {
        Some(h) => h.to_str().unwrap_or("").replace("Bearer ", ""),
        None => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(serde_json::json!({"error": "No authorization header"})),
            )
                .into_response();
        }
    };

    match SPOTIFY_CONTROLLER
        .get_recommendations(
            &access_token,
            params.seed_tracks.as_deref(),
            params.seed_artists.as_deref(),
            params.seed_genres.as_deref(),
            params.target_tempo,
            params.target_energy,
            params.limit,
        )
        .await
    {
        Ok(recs) => Json(recs).into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({"error": e})),
        )
            .into_response(),
    }
}
