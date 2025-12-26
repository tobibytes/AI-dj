// Spotify routes
use axum::{routing::get, Router};

use crate::controllers::spotify::{
    spotify_auth_route, spotify_callback_route, spotify_refresh_route,
    spotify_token_route, spotify_auto_auth_route, spotify_me_route, spotify_search_route, 
    spotify_audio_features_route, spotify_recommendations_route,
};

pub fn spotify_routes() -> Router {
    Router::new()
        .route("/auth", get(spotify_auth_route))
        .route("/callback", get(spotify_callback_route))
        .route("/refresh", get(spotify_refresh_route))
        .route("/token", get(spotify_token_route))
        .route("/auto-auth", get(spotify_auto_auth_route))
        .route("/me", get(spotify_me_route))
        .route("/search", get(spotify_search_route))
        .route("/audio-features", get(spotify_audio_features_route))
        .route("/recommendations", get(spotify_recommendations_route))
}
