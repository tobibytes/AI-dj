use std::process::Command;

use axum::{
    extract::Json,
    http::StatusCode,
    response::{IntoResponse, Response},
};
use once_cell::sync::Lazy;
use serde_json::from_str;
use tracing::info;

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
        let full_url = format!(
            "{}?part=snippet&maxResult=2&q={}&key={}",
            self.url, search_q, self.api_key
        );
        let r_res = reqwest::Client::new().get(&full_url).send().await;
        let res = match r_res {
            Ok(r) => r,
            Err(e) => panic!("{}", e.to_string()),
        };
        let data: serde_json::Value = match res.json().await {
            Ok(v) => v,
            Err(e) => panic!("{}", e.to_string()),
        };
        return Ok(TrackValueResponse {
            video_id: from_str(data["items"][0]["id"]["videoId"].to_string().as_str()).unwrap(),
            thumbnail: from_str(
                data["items"][0]["snippet"]["thumbnails"]["default"]["url"]
                    .to_string()
                    .as_str(),
            )
            .unwrap(),
            artist: from_str(
                data["items"][0]["snippet"]["channelTitle"]
                    .to_string()
                    .as_str(),
            )
            .unwrap(),
            title: from_str(data["items"][0]["snippet"]["title"].to_string().as_str()).unwrap(),
        });
    }

    fn _get_song_stream(self: &Self, track: TrackValueResponse) -> Result<Track, anyhow::Error> {
        info!("{:?}", track);
        let data = self._get_stream(format!(
            "https://www.youtube.com/watch?v={}",
            &track.video_id
        ));
        match data {
            Ok(d) => {
                return Ok(Track {
                    id: track.video_id,
                    title: track.title,
                    thumbnail: track.thumbnail,
                    artist: track.artist,
                    stream_url: d,
                });
            }
            Err(e) => {
                panic!("Could not get the stream: {}", e.to_string())
            }
        }
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
                        let res_track = self._get_song_stream(track_v_res);
                        match res_track {
                            Ok(track) => return (StatusCode::OK, Json(track)).into_response(),
                            Err(e) => {
                                return (
                                    StatusCode::BAD_REQUEST,
                                    Json(format!("Could not get song data: {}", e.to_string())),
                                )
                                    .into_response();
                            }
                        }
                    }
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(format!("Could not get song data: {}", e.to_string())),
                        )
                            .into_response();
                    }
                }
            }
            None => {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(format!("Did not recieve query params")),
                )
                    .into_response();
            }
        }
    }
    fn _get_stream(self: &Self, video_url: String) -> anyhow::Result<String> {
        let output = Command::new("yt-dlp")
            .arg("-f")
            .arg("bestaudio")
            .arg("-g") // get direct URL
            .arg(video_url)
            .output()?;

        let url = String::from_utf8(output.stdout)?.trim().to_string();
        Ok(url)
    }
}

pub static SONG_CONTROLLER: Lazy<SongController> = Lazy::new(|| SongController::new());
