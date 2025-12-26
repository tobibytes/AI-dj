use tokio;
use axum::{
    routing::get, Router
   };
use tracing_subscriber::{ fmt, EnvFilter};
use tracing::{ info, Level };
use tower_http::trace::TraceLayer;
use crate::{ secrets::SECRET_MANAGER};
mod models;
mod controllers;
mod routers;
use routers::{ health_check_route, root_route, song_data_route, get_html_of_url_route };
mod secrets;


   
#[tokio::main]
async fn main() {
    fmt().with_env_filter(EnvFilter::from_default_env().add_directive(Level::DEBUG.into()))
        .with_target(false)
        .init();

    let port = SECRET_MANAGER.get("PORT");
    let backend_url = SECRET_MANAGER.get("BACKEND_URL");
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();
    
    let app = Router::new()
        .route("/", get(root_route))
        .route("/health", get(health_check_route))
        .route("/song/info", get(song_data_route))
        .route("/link/text", get(get_html_of_url_route))
        .layer(TraceLayer::new_for_http());

    info!("Listening on {}", backend_url);
    axum::serve(listener, app).await.unwrap();
}

