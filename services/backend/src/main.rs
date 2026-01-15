use tokio;
use axum::{
    routing::get,
    routing::post,
    extract::{ws::{Message, WebSocket, WebSocketUpgrade}, Path, State},
    response::IntoResponse,
    Router,
    body::Bytes,
    Json,
};
use futures_util::{SinkExt, StreamExt};
use tracing_subscriber::{fmt, EnvFilter};
use tracing::{info, error, debug, warn, Level};
use tower_http::trace::TraceLayer;
use tower_http::cors::{CorsLayer, Any};
use crate::secrets::SECRET_MANAGER;
mod models;
mod controllers;
mod routers;
mod db;
use routers::{health_check_route, root_route, spotify_routes};
use db::Database;
use uuid::Uuid;
mod secrets;

/// WebSocket handler for mix progress updates
async fn ws_mix_handler(
    State(_database): State<Database>,
    ws: WebSocketUpgrade,
    Path(session_id): Path<String>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_mix_socket(socket, session_id))
}

async fn handle_mix_socket(mut socket: WebSocket, session_id: String) {
    info!("WebSocket connected for session: {}", session_id);

    // Initialize database connection
    let database = match Database::new().await {
        Ok(db) => db,
        Err(e) => {
            error!("Failed to connect to database: {}", e);
            let _ = socket.send(Message::Text(
                format!("{{\"error\": \"Database connection failed: {}\"}}", e).into()
            )).await;
            return;
        }
    };

    // Connect to Redis and subscribe to progress channel
    let redis_url = SECRET_MANAGER.get("REDIS_URL");
    info!("Backend connecting to Redis at: {}", redis_url);
    
    let client = match redis::Client::open(redis_url.as_str()) {
        Ok(c) => c,
        Err(e) => {
            error!("Failed to connect to Redis: {}", e);
            let _ = socket.send(Message::Text(
                format!("{{\"error\": \"Failed to connect to progress stream: {}\"}}", e).into()
            )).await;
            return;
        }
    };
    
    let mut pubsub = match client.get_async_pubsub().await {
        Ok(ps) => ps,
        Err(e) => {
            error!("Failed to get pubsub connection: {}", e);
            let _ = socket.send(Message::Text(
                format!("{{\"error\": \"Failed to subscribe to progress: {}\"}}", e).into()
            )).await;
            return;
        }
    };
    
    // Subscribe to multiple channels for this session
    let _progress_channel = format!("mix:{}:progress", session_id);
    let _complete_channel = format!("mix:{}:complete", session_id);
    let _error_channel = format!("mix:{}:error", session_id);
    
    // Also subscribe to a wildcard pattern to catch all messages
    let wildcard_pattern = "mix:*:*".to_string();
    
    if let Err(e) = pubsub.psubscribe(&wildcard_pattern).await {
        error!("Failed to subscribe to wildcard pattern: {}", e);
    }
    
    info!("Subscribed to Redis channels for session: {}", session_id);
    
    // Send initial connection confirmation
    let _ = socket.send(Message::Text(
        format!("{{\"type\": \"connected\", \"session_id\": \"{}\"}}", session_id).into()
    )).await;
    
    // Split the WebSocket for concurrent read/write
    let (mut ws_sender, mut ws_receiver) = socket.split();
    
    // Handle incoming Redis messages
    let mut pubsub_stream = pubsub.on_message();
    
    // Heartbeat interval (30 seconds)
    let mut heartbeat_interval = tokio::time::interval(std::time::Duration::from_secs(30));
    heartbeat_interval.tick().await; // Skip first immediate tick
    
    loop {
        tokio::select! {
            // Handle Redis pubsub messages
            msg_opt = pubsub_stream.next() => {
                let msg: redis::Msg = match msg_opt {
                    Some(m) => m,
                    None => break,
                };
                
                let payload: String = match msg.get_payload() {
                    Ok(p) => p,
                    Err(_) => continue,
                };
                
                let channel: String = msg.get_channel_name().to_string();
                
                info!("Received Redis message on channel {}: {}", channel, payload);
                
                // Determine message type based on channel suffix
                let message_type = if channel.ends_with(":complete") {
                    "complete"
                } else if channel.ends_with(":error") {
                    "error"
                } else if channel.ends_with(":progress") {
                    "progress"
                } else {
                    warn!("Unknown channel type: {}", channel);
                    continue;
                };
                
                debug!("Forwarding {} message to websocket: {}", message_type, payload);
                
                // Save mix data to database for completion messages
                if message_type == "complete" {
                    if let Ok(data) = serde_json::from_str::<serde_json::Value>(&payload) {
                        let session_uuid = match Uuid::parse_str(&session_id) {
                            Ok(uuid) => uuid,
                            Err(e) => {
                                warn!("Invalid session ID format: {}", e);
                                return;
                            }
                        };

                        // Only update CDN URL and status for completion
                        if let Some(cdn_url) = data.get("cdn_url").and_then(|u| u.as_str()) {
                            if let Err(e) = database.update_mix_cdn_url(session_uuid, cdn_url).await {
                                error!("Failed to update CDN URL: {}", e);
                            } else {
                                info!("Successfully updated CDN URL for session: {}", session_id);
                            }
                        }

                        // Update session status to completed
                        if let Err(e) = database.update_mix_status(session_uuid, "completed").await {
                            error!("Failed to update mix status: {}", e);
                        }
                    }
                } else if message_type == "error" {
                    // Save error information
                    let session_uuid = match Uuid::parse_str(&session_id) {
                        Ok(uuid) => uuid,
                        Err(e) => {
                            warn!("Invalid session ID format: {}", e);
                            return;
                        }
                    };

                    let error_msg = if let Ok(data) = serde_json::from_str::<serde_json::Value>(&payload) {
                        data.get("error").and_then(|e| e.as_str()).unwrap_or("Unknown error").to_string()
                    } else {
                        "Unknown error".to_string()
                    };

                    if let Err(e) = database.update_mix_error(session_uuid, &error_msg).await {
                        error!("Failed to save error to database: {}", e);
                    }
                }
                
                // Forward to WebSocket client using proper JSON serialization
                // Parse the payload to ensure it's valid JSON, then wrap it
                let ws_message = match serde_json::from_str::<serde_json::Value>(&payload) {
                    Ok(data) => {
                        serde_json::json!({
                            "type": message_type,
                            "data": data
                        }).to_string()
                    }
                    Err(_) => {
                        // Fallback: wrap as string if not valid JSON
                        serde_json::json!({
                            "type": message_type,
                            "data": {"raw": payload}
                        }).to_string()
                    }
                };
                
                if ws_sender.send(Message::Text(ws_message.into())).await.is_err() {
                    break;
                }
                
                // Close connection on completion or error
                if message_type == "complete" || message_type == "error" {
                    break;
                }
            }
            
            // Handle WebSocket messages from client (ping/pong, close)
            ws_msg = ws_receiver.next() => {
                match ws_msg {
                    Some(Ok(Message::Ping(data))) => {
                        debug!("Received ping from client for session: {}", session_id);
                        let _ = ws_sender.send(Message::Pong(data)).await;
                    }
                    Some(Ok(Message::Pong(_))) => {
                        debug!("Received pong from client for session: {}", session_id);
                    }
                    Some(Ok(Message::Close(_))) => {
                        info!("WebSocket closed by client for session: {}", session_id);
                        break;
                    }
                    Some(Err(e)) => {
                        error!("WebSocket error for session {}: {}", session_id, e);
                        break;
                    }
                    None => {
                        info!("WebSocket receiver closed for session: {}", session_id);
                        break;
                    }
                    _ => {}
                }
            }
            
            // Send heartbeat ping to keep connection alive
            _ = heartbeat_interval.tick() => {
                debug!("Sending heartbeat ping to client for session: {}", session_id);
                if ws_sender.send(Message::Ping(Bytes::new())).await.is_err() {
                    error!("Failed to send heartbeat ping for session: {}", session_id);
                    break;
                }
            }
        }
    }
    
    info!("WebSocket disconnected for session: {}", session_id);
}

/// SSE (Server-Sent Events) fallback for mix progress
async fn sse_mix_handler(
    State(_database): State<Database>,
    Path(session_id): Path<String>,
) -> impl IntoResponse {
    use axum::response::sse::{Event, KeepAlive, Sse};
    use std::convert::Infallible;
    
    let redis_url = SECRET_MANAGER.get("REDIS_URL");
    
    let stream = async_stream::stream! {
        let client = match redis::Client::open(redis_url.as_str()) {
            Ok(c) => c,
            Err(e) => {
                yield Ok::<_, Infallible>(Event::default().data(
                    format!("{{\"error\": \"Redis connection failed: {}\"}}", e)
                ));
                return;
            }
        };
        
        let mut pubsub = match client.get_async_pubsub().await {
            Ok(ps) => ps,
            Err(e) => {
                yield Ok::<_, Infallible>(Event::default().data(
                    format!("{{\"error\": \"Pubsub failed: {}\"}}", e)
                ));
                return;
            }
        };
        
        let progress_channel = format!("mix:{}:progress", session_id);
        let complete_channel = format!("mix:{}:complete", session_id);
        let error_channel = format!("mix:{}:error", session_id);
        
        let _ = pubsub.subscribe(&progress_channel).await;
        let _ = pubsub.subscribe(&complete_channel).await;
        let _ = pubsub.subscribe(&error_channel).await;
        
        yield Ok::<_, Infallible>(Event::default().data(
            format!("{{\"type\": \"connected\", \"session_id\": \"{}\"}}", session_id)
        ));
        
        let mut pubsub_stream = pubsub.on_message();
        
        while let Some(msg) = pubsub_stream.next().await {
            let payload: String = match msg.get_payload() {
                Ok(p) => p,
                Err(_) => continue,
            };
            
            let channel: String = msg.get_channel_name().to_string();
            let message_type = if channel.contains(":complete") {
                "complete"
            } else if channel.contains(":error") {
                "error"
            } else {
                "progress"
            };
            
            yield Ok::<_, Infallible>(Event::default().data(
                format!("{{\"type\": \"{}\", \"data\": {}}}", message_type, payload)
            ));
            
            if message_type == "complete" || message_type == "error" {
                break;
            }
        }
    };
    
    Sse::new(stream).keep_alive(KeepAlive::default())
}

/// Proxy endpoint to forward mix generation requests to orchestrator
async fn generate_mix_handler(
    State(database): State<Database>,
    headers: axum::http::HeaderMap,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    let orchestrator_url = SECRET_MANAGER.get("ORCHESTRATOR_URL");

    let client = reqwest::Client::new();

    let mut request = client
        .post(format!("{}/generate-mix", orchestrator_url))
        .header("Content-Type", "application/json")
        .body(body.clone());

    // Forward OpenAI key header if present
    if let Some(key) = headers.get("X-OpenAI-Key") {
        request = request.header("X-OpenAI-Key", key.to_str().unwrap_or(""));
    }

    // Forward Authorization header if present
    if let Some(auth) = headers.get("Authorization") {
        request = request.header("Authorization", auth.to_str().unwrap_or(""));
    }

    match request.send().await {
        Ok(response) => {
            let status = response.status();
            let body_text = response.text().await.unwrap_or_default();

            // If the orchestrator response is successful, try to save the initial mix data
            if status.is_success() {
                if let Ok(data) = serde_json::from_str::<serde_json::Value>(&body_text) {
                    if let Some(session_id_str) = data.get("session_id").and_then(|s| s.as_str()) {
                        if let Ok(session_uuid) = Uuid::parse_str(session_id_str) {
                            // Extract playlist data from the initial response
                            if let Some(playlist) = data.get("playlist").and_then(|p| p.as_array()) {
                                let mut tracks = Vec::new();
                                let mut transitions = Vec::new();

                                for (i, track) in playlist.iter().enumerate() {
                                    if let (Some(spotify_id), Some(title), Some(artist)) = (
                                        track.get("spotify_id").and_then(|s| s.as_str()),
                                        track.get("title").and_then(|t| t.as_str()),
                                        track.get("artist").and_then(|a| a.as_str()),
                                    ) {
                                        tracks.push(crate::models::mix::CreateTrackRequest {
                                            spotify_id: spotify_id.to_string(),
                                            title: title.to_string(),
                                            artist: artist.to_string(),
                                            album: track.get("album").and_then(|a| a.as_str()).unwrap_or("Unknown").to_string(),
                                            duration_ms: track.get("duration_ms").and_then(|d| d.as_i64()).unwrap_or(0) as i32,
                                            key: track.get("key").and_then(|k| k.as_str()).unwrap_or("Unknown").to_string(),
                                            energy: track.get("energy").and_then(|e| e.as_f64()).unwrap_or(0.5),
                                            danceability: track.get("danceability").and_then(|d| d.as_f64()).unwrap_or(0.5),
                                            valence: track.get("valence").and_then(|v| v.as_f64()).unwrap_or(0.5),
                                            acousticness: track.get("acousticness").and_then(|a| a.as_f64()).unwrap_or(0.1),
                                            instrumentalness: track.get("instrumentalness").and_then(|i| i.as_f64()).unwrap_or(0.1),
                                            popularity: track.get("popularity").and_then(|p| p.as_i64()).unwrap_or(50) as i32,
                                            track_order: i as i32,
                                        });
                                    }

                                    // Extract transition data
                                    if let Some(transition) = track.get("transition") {
                                        if let (Some(trans_type), Some(bars)) = (
                                            transition.get("type").and_then(|t| t.as_str()),
                                            transition.get("bars").and_then(|b| b.as_i64()),
                                        ) {
                                            transitions.push(crate::models::mix::CreateTransitionRequest {
                                                from_track_order: i as i32,
                                                to_track_order: (i + 1) as i32,
                                                transition_type: trans_type.to_string(),
                                                transition_bars: bars as i32,
                                                transition_direction: transition.get("direction").and_then(|d| d.as_str()).map(|s| s.to_string()),
                                            });
                                        }
                                    }
                                }

                                let prompt = data.get("prompt").and_then(|p| p.as_str()).unwrap_or("").to_string();
                                let mix_request = crate::models::mix::CreateMixRequest {
                                    prompt,
                                    tracks,
                                    transitions,
                                    estimated_duration_minutes: data.get("estimated_duration_minutes").and_then(|d| d.as_f64()),
                                };

                                // Create the mix session first
                                if let Err(e) = database.create_mix_session(session_uuid, &mix_request.prompt).await {
                                    error!("Failed to create mix session: {}", e);
                                }

                                // Then save the mix data
                                if let Err(e) = database.save_mix_data(session_uuid, mix_request).await {
                                    error!("Failed to save initial mix data: {}", e);
                                } else {
                                    info!("Successfully saved initial mix data for session: {}", session_id_str);
                                }
                            }
                        }
                    }
                }
            }

            (
                axum::http::StatusCode::from_u16(status.as_u16()).unwrap_or(axum::http::StatusCode::INTERNAL_SERVER_ERROR),
                axum::Json(serde_json::from_str::<serde_json::Value>(&body_text).unwrap_or(serde_json::json!({"error": body_text})))
            ).into_response()
        }
        Err(e) => {
            (
                axum::http::StatusCode::BAD_GATEWAY,
                axum::Json(serde_json::json!({"error": format!("Orchestrator request failed: {}", e)}))
            ).into_response()
        }
    }
}

async fn list_mixes_handler(
    State(database): State<Database>,
) -> impl IntoResponse {
    match database.list_mix_sessions(50, 0).await {
        Ok(sessions) => Json(sessions).into_response(),
        Err(e) => {
            error!("Failed to list mix sessions: {}", e);
            (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": "Failed to retrieve mix sessions"}))
            ).into_response()
        }
    }
}

async fn get_mix_handler(
    State(database): State<Database>,
    Path(session_id): Path<String>,
) -> impl IntoResponse {
    let session_uuid = match Uuid::parse_str(&session_id) {
        Ok(uuid) => uuid,
        Err(_) => {
            return (
                axum::http::StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"error": "Invalid session ID format"}))
            ).into_response();
        }
    };

    match database.get_mix_data(session_uuid).await {
        Ok(Some(mix_data)) => Json(mix_data).into_response(),
        Ok(None) => {
            (
                axum::http::StatusCode::NOT_FOUND,
                Json(serde_json::json!({"error": "Mix session not found"}))
            ).into_response()
        }
        Err(e) => {
            error!("Failed to get mix data: {}", e);
            (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": "Failed to retrieve mix data"}))
            ).into_response()
        }
    }
}

async fn create_mix_session_handler(
    State(database): State<Database>,
    Path(session_id): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> impl IntoResponse {
    let session_uuid = match Uuid::parse_str(&session_id) {
        Ok(uuid) => uuid,
        Err(_) => {
            return (
                axum::http::StatusCode::BAD_REQUEST,
                Json(serde_json::json!({"error": "Invalid session ID format"}))
            ).into_response();
        }
    };

    let prompt = payload.get("prompt")
        .and_then(|p| p.as_str())
        .unwrap_or("")
        .to_string();

    match database.create_mix_session(session_uuid, &prompt).await {
        Ok(_) => {
            info!("Created mix session: {}", session_id);
            Json(serde_json::json!({"status": "created", "session_id": session_id})).into_response()
        }
        Err(e) => {
            error!("Failed to create mix session: {}", e);
            (
                axum::http::StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({"error": "Failed to create mix session"}))
            ).into_response()
        }
    }
}

#[tokio::main]
async fn main() {
    fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive(Level::DEBUG.into()))
        .with_target(false)
        .init();

    // Initialize database
    let database = match Database::new().await {
        Ok(db) => {
            info!("📊 Connected to PostgreSQL database");
            db
        }
        Err(e) => {
            error!("❌ Failed to connect to database: {}", e);
            panic!("Database connection required");
        }
    };

    // Run migrations
    if let Err(e) = sqlx::migrate!("./migrations").run(database.pool()).await {
        error!("❌ Failed to run database migrations: {}", e);
        panic!("Database migrations failed");
    }
    info!("📊 Database migrations completed");

    let port = SECRET_MANAGER.get("PORT");
    let backend_url = SECRET_MANAGER.get("BACKEND_URL");
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();

    // CORS configuration
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app: Router = Router::new()
        // Core routes
        .route("/", get(root_route))
        .route("/health", get(health_check_route))
        // Spotify OAuth routes
        .nest("/spotify", spotify_routes())
        // Mix generation and progress
        .route("/mix/generate", post(generate_mix_handler))
        .route("/ws/mix/{session_id}", get(ws_mix_handler))
        .route("/sse/mix/{session_id}", get(sse_mix_handler))
        // Mix data API
        .route("/api/mixes", get(list_mixes_handler))
        .route("/api/mixes/{session_id}", get(get_mix_handler))
        .route("/api/mixes/{session_id}/create", post(create_mix_session_handler))
        // Middleware
        .layer(cors)
        .layer(TraceLayer::new_for_http())
        // Add database to request extensions
        .with_state(database);

    info!("🎧 AI DJ Backend listening on {}", backend_url);
    info!("📡 WebSocket endpoint: /ws/mix/{{session_id}}");
    info!("📡 SSE endpoint: /sse/mix/{{session_id}}");
    info!("📊 Mix API endpoints: /api/mixes/*");

    axum::serve(listener, app).await.unwrap();
}

