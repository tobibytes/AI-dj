use axum::extract::Query;
use axum::response::IntoResponse;
use axum::Json;
use reqwest::StatusCode;

use crate::controllers::RootController;
use crate::controllers::get_html;

pub async fn root_route() -> impl axum::response::IntoResponse {
    RootController::root().await
}

pub async fn health_check_route() -> impl axum::response::IntoResponse {
    RootController::health_check().await
}

pub async fn get_html_of_url_route(Query(queries): Query<std::collections::HashMap<String, String>>) -> impl axum::response::IntoResponse {
    let r_link = queries.get("link");
    match r_link {
    Some(link) => {
        match get_html(link).await {
            Ok(data) => return Json(data).into_response(),
            Err(e) => return (StatusCode::BAD_REQUEST, Json(format!("Could not get text from link: {}", e.to_string()))).into_response()
        }
    }
    None => {
        return (StatusCode::BAD_REQUEST, Json("Could not get link from query")).into_response()
    }
}
}