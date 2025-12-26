pub struct RootController;

impl RootController {
        pub async fn root() -> &'static str {
            "Hello, World!"
        }
    
        pub async fn health_check() -> &'static str {
            "OK"
        }
}