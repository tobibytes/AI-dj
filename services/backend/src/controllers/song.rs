use std::process::Command;

use axum::{
    extract::Json,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use once_cell::sync::Lazy;
use serde_json::from_str;
use tracing::{info, error};

use crate::{
    models::song::{Track, TrackValueResponse},
    secrets::SECRET_MANAGER,
};

pub struct SongController {
    api_key: String,
    url: String,
}

impl SongController {
    pub fn new() -> Self {
        let key = SECRET_MANAGER.get("YOUTUBE_API_KEY");
        let url = SECRET_MANAGER.get("YOUTUBE_API_URL");
        SongController { api_key: key, url }
    }
    
    async fn _search_song(
        self: &Self,
        search_q: &String,
    ) -> Result<TrackValueResponse, anyhow::Error> {
        // URL-encode the search query
        let encoded_q = urlencoding::encode(search_q);
        let full_url = format!(
            "{}?part=snippet&maxResults=2&q={}&key={}",
            self.url, encoded_q, self.api_key
        );
        
        let res = reqwest::Client::new()
            .get(&full_url)
            .send()
            .await
            .map_err(|e| anyhow::anyhow!("HTTP request failed: {}", e))?;
        
        if !res.status().is_success() {
            return Err(anyhow::anyhow!("YouTube API returned status: {}", res.status()));
        }
        
        let data: serde_json::Value = res
            .json()
            .await
            .map_err(|e| anyhow::anyhow!("Failed to parse JSON: {}", e))?;
        
        // Safely access nested JSON fields
        let items = data.get("items")
            .and_then(|i| i.as_array())
            .ok_or_else(|| anyhow::anyhow!("No 'items' array in response"))?;
        
        if items.is_empty() {
            return Err(anyhow::anyhow!("No search results found"));
        }
        
        let first_item = &items[0];
        
        let video_id = first_item
            .get("id")
            .and_then(|i| i.get("videoId"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow::anyhow!("Missing videoId"))?
            .to_string();
        
        let snippet = first_item
            .get("snippet")
            .ok_or_else(|| anyhow::anyhow!("Missing snippet"))?;
        
        let thumbnail = snippet
            .get("thumbnails")
            .and_then(|t| t.get("default"))
            .and_then(|d| d.get("url"))
            .and_then(|u| u.as_str())
            .unwrap_or("")
            .to_string();
        
        let artist = snippet
            .get("channelTitle")
            .and_then(|c| c.as_str())
            .unwrap_or("Unknown")
            .to_string();
        
        let title = snippet
            .get("title")
            .and_then(|t| t.as_str())
            .unwrap_or("Unknown")
            .to_string();
        
        Ok(TrackValueResponse {
            video_id,
            thumbnail,
            artist,
            title,
        })
    }

    fn _get_song_stream(self: &Self, track: TrackValueResponse) -> Result<Track, anyhow::Error> {
        info!("Getting stream for: {:?}", track);
        let stream_url = self._get_stream(format!(
            "https://www.youtube.com/watch?v={}",
            &track.video_id
        ))?;
        
        Ok(Track {
            id: track.video_id,
            title: track.title,
            thumbnail: track.thumbnail,
            artist: track.artist,
            stream_url,
        })
    }
    
    pub async fn get_song_data(
        self: &Self,
        queries: std::collections::HashMap<String, String>,
    ) -> Response {
        let r_search_q = queries.get("q");
        match r_search_q {
            Some(search_q) => {
                let t_r_v = self._search_song(search_q).await;
                match t_r_v {
                    Ok(track_v_res) => {
                        // Use spawn_blocking for the synchronous yt-dlp call
                        let track_v_res_clone = track_v_res.clone();
                        let video_id = track_v_res_clone.video_id.clone();
                        
                        match tokio::task::spawn_blocking(move || {
                            SongController::_get_stream_static(format!(
                                "https://www.youtube.com/watch?v={}",
                                video_id
                            ))
                        }).await {
                            Ok(Ok(stream_url)) => {
                                let track = Track {
                                    id: track_v_res.video_id,
                                    title: track_v_res.title,
                                    thumbnail: track_v_res.thumbnail,
                                    artist: track_v_res.artist,
                                    stream_url,
                                };
                                (StatusCode::OK, Json(track)).into_response()
                            }
                            Ok(Err(e)) => {
                                error!("yt-dlp error: {}", e);
                                (
                                    StatusCode::INTERNAL_SERVER_ERROR,
                                    Json(serde_json::json!({"error": format!("Could not get stream: {}", e)})),
                                ).into_response()
                            }
                            Err(e) => {
                                error!("Task join error: {}", e);
                                (
                                    StatusCode::INTERNAL_SERVER_ERROR,
                                    Json(serde_json::json!({"error": "Internal server error"})),
                                ).into_response()
                            }
                        }
                    }
                    Err(e) => {
                        error!("YouTube search error: {}", e);
                        (
                            StatusCode::BAD_REQUEST,
                            Json(serde_json::json!({"error": format!("Could not get song data: {}", e)})),
                        ).into_response()
                    }
                }
            }
            None => {
                (
                    StatusCode::BAD_REQUEST,
                    Json(serde_json::json!({"error": "Did not receive query params"})),
                ).into_response()
            }
        }
    }
    
    fn _get_stream(self: &Self, video_url: String) -> anyhow::Result<String> {
        Self::_get_stream_static(video_url)
    }
    
    // Static version for use in spawn_blocking
    fn _get_stream_static(video_url: String) -> anyhow::Result<String> {
        let output = Command::new("yt-dlp")
            .arg("-f")
            .arg("bestaudio")
            .arg("-g") // get direct URL
            .arg(&video_url)
            .output()
            .map_err(|e| anyhow::anyhow!("Failed to execute yt-dlp: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(anyhow::anyhow!("yt-dlp failed: {}", stderr));
        }
        
        let url = String::from_utf8(output.stdout)
            .map_err(|e| anyhow::anyhow!("Invalid UTF-8 output: {}", e))?
            .trim()
            .to_string();
        
        if url.is_empty() {
            return Err(anyhow::anyhow!("yt-dlp returned empty URL"));
        }
        
        Ok(url)
    }
}

pub static SONG_CONTROLLER: Lazy<SongController> = Lazy::new(|| SongController::new());
