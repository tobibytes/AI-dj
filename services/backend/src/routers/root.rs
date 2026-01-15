use axum::extract::State;
use crate::controllers::RootController;
use crate::db::Database;

pub async fn root_route(State(_database): State<Database>) -> impl axum::response::IntoResponse {
    RootController::root().await
}

pub async fn health_check_route(State(_database): State<Database>) -> impl axum::response::IntoResponse {
    RootController::health_check().await
}