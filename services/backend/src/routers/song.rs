use axum::{extract::Query, response::Response};

use crate::controllers::SONG_CONTROLLER;

pub async fn song_data_route(
    Query(query): Query<std::collections::HashMap<String, String>>,
) -> Response {
    SONG_CONTROLLER.get_song_data(query).await
}
