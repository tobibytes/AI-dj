// secrets
use once_cell::sync::Lazy;
use std::collections::HashMap;
use std::env;
use tracing::debug;
pub static SECRET_MANAGER: Lazy<SecretManager> = Lazy::new(|| SecretManager::new());

enum MODE {
    DEV,
    PROD,
}

pub struct SecretManager {
    secrets: HashMap<String, String>,
}
impl SecretManager {
    fn new() -> Self {
        let mut secrets: HashMap<String, String> = HashMap::new();
        let mode = match env::var("MODE") {
            Ok(mode) if mode.to_lowercase() == "prod" => MODE::PROD,
            _ => MODE::DEV,
        };
        match mode {
            MODE::DEV => {
                secrets.insert(
                    "DB_URI".to_string(),
                    "postgresql://:@postgres:5432/".to_string(),
                );
                secrets.insert("PORT".to_string(), "8000".to_string());
                secrets.insert(
                    "FRONTEND_URL".to_string(),
                    "http://localhost:3000".to_string(),
                );
                secrets.insert(
                    "BACKEND_URL".to_string(),
                    "http://localhost:8000".to_string(),
                );
                secrets.insert("BACKEND_DOMAIN".to_string(), "localhost".to_string());
            }
            MODE::PROD => {
                secrets.insert("DB_URI".to_string(), env::var("DB_URI").unwrap_or_default());
                secrets.insert("PORT".to_string(), env::var("PORT").unwrap_or_default());
                secrets.insert(
                    "FRONTEND_URL".to_string(),
                    env::var("FRONTEND_URL").unwrap_or_default(),
                );
                secrets.insert(
                    "BACKEND_URL".to_string(),
                    env::var("BACKEND_URL").unwrap_or_default(),
                );
            }
        }
        secrets.insert("JWT_SECRET".to_string(), "secret".to_string());
        secrets.insert(
            "GOOGLE_CLIENT_ID".to_string(),
            env::var("GOOGLE_CLIENT_ID").unwrap_or_default(),
        );
        secrets.insert(
            "GOOGLE_CLIENT_SECRET".to_string(),
            env::var("GOOGLE_CLIENT_SECRET").unwrap_or_default(),
        );
        secrets.insert(
            "GOOGLE_REDIRECT_URL".to_string(),
            env::var("GOOGLE_REDIRECT_URL").unwrap_or_default(),
        );
        secrets.insert(
            "YOUTUBE_API_URL".to_string(),
            "https://www.googleapis.com/youtube/v3/search".to_string(),
        );
        secrets.insert(
            "YOUTUBE_API_KEY".to_string(),
            env::var("YOUTUBE_API_KEY").unwrap_or_default(),
        );
        debug!("Secrets loaded: {:?}", secrets);
        SecretManager { secrets }
    }

    pub fn get(&self, key: &str) -> String {
        self.secrets.get(key).cloned().unwrap_or_default()
    }
}
