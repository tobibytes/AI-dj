use tokio;
use axum::{
    routing::get,
    routing::post,
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    extract::Path,
    response::IntoResponse,
    Router,
};
use futures_util::{SinkExt, StreamExt};
use tracing_subscriber::{fmt, EnvFilter};
use tracing::{info, error, debug, Level};
use tower_http::trace::TraceLayer;
use tower_http::cors::{CorsLayer, Any};
use redis::AsyncCommands;
use crate::secrets::SECRET_MANAGER;
mod models;
mod controllers;
mod routers;
use routers::{health_check_route, root_route, song_data_route, get_html_of_url_route, spotify_routes};
mod secrets;

/// WebSocket handler for mix progress updates
async fn ws_mix_handler(
    ws: WebSocketUpgrade,
    Path(session_id): Path<String>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_mix_socket(socket, session_id))
}

async fn handle_mix_socket(mut socket: WebSocket, session_id: String) {
    info!("WebSocket connected for session: {}", session_id);
    
    // Connect to Redis and subscribe to progress channel
    let redis_url = SECRET_MANAGER.get("REDIS_URL");
    
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
    let progress_channel = format!("mix:{}:progress", session_id);
    let complete_channel = format!("mix:{}:complete", session_id);
    let error_channel = format!("mix:{}:error", session_id);
    
    if let Err(e) = pubsub.subscribe(&progress_channel).await {
        error!("Failed to subscribe to progress channel: {}", e);
        return;
    }
    if let Err(e) = pubsub.subscribe(&complete_channel).await {
        error!("Failed to subscribe to complete channel: {}", e);
        return;
    }
    if let Err(e) = pubsub.subscribe(&error_channel).await {
        error!("Failed to subscribe to error channel: {}", e);
        return;
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
                
                debug!("Redis message on {}: {}", channel, payload);
                
                // Determine message type based on channel
                let message_type = if channel.contains(":complete") {
                    "complete"
                } else if channel.contains(":error") {
                    "error"
                } else {
                    "progress"
                };
                
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
                        let _ = ws_sender.send(Message::Pong(data)).await;
                    }
                    Some(Ok(Message::Close(_))) => {
                        info!("WebSocket closed by client for session: {}", session_id);
                        break;
                    }
                    Some(Err(_)) | None => {
                        break;
                    }
                    _ => {}
                }
            }
            
            else => break,
        }
    }
    
    info!("WebSocket disconnected for session: {}", session_id);
}

/// SSE (Server-Sent Events) fallback for mix progress
async fn sse_mix_handler(Path(session_id): Path<String>) -> impl IntoResponse {
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
    headers: axum::http::HeaderMap,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    let orchestrator_url = SECRET_MANAGER.get("ORCHESTRATOR_URL");
    
    let client = reqwest::Client::new();
    
    let mut request = client
        .post(format!("{}/generate-mix", orchestrator_url))
        .header("Content-Type", "application/json")
        .body(body.to_vec());
    
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
            let body = response.text().await.unwrap_or_default();
            
            (
                axum::http::StatusCode::from_u16(status.as_u16()).unwrap_or(axum::http::StatusCode::INTERNAL_SERVER_ERROR),
                axum::Json(serde_json::from_str::<serde_json::Value>(&body).unwrap_or(serde_json::json!({"error": body})))
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

#[tokio::main]
async fn main() {
    fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive(Level::DEBUG.into()))
        .with_target(false)
        .init();

    let port = SECRET_MANAGER.get("PORT");
    let backend_url = SECRET_MANAGER.get("BACKEND_URL");
    let listener = tokio::net::TcpListener::bind(format!("0.0.0.0:{}", port)).await.unwrap();
    
    // CORS configuration
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);
    
    let app = Router::new()
        // Core routes
        .route("/", get(root_route))
        .route("/health", get(health_check_route))
        .route("/song/info", get(song_data_route))
        .route("/link/text", get(get_html_of_url_route))
        // Spotify OAuth routes
        .nest("/spotify", spotify_routes())
        // Mix generation and progress
        .route("/mix/generate", post(generate_mix_handler))
        .route("/ws/mix/{session_id}", get(ws_mix_handler))
        .route("/sse/mix/{session_id}", get(sse_mix_handler))
        // Middleware
        .layer(cors)
        .layer(TraceLayer::new_for_http());

    info!("🎧 AI DJ Backend listening on {}", backend_url);
    info!("📡 WebSocket endpoint: /ws/mix/{{session_id}}");
    info!("📡 SSE endpoint: /sse/mix/{{session_id}}");
    
    axum::serve(listener, app).await.unwrap();
}

