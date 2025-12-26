use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct Track {
    pub id: String,
    pub artist: String,
    pub thumbnail: String,
    pub title: String,
    pub stream_url: String
}
#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct TrackValueResponse {
    pub video_id: String,
    pub artist: String,
    pub thumbnail: String,
    pub title: String
}
