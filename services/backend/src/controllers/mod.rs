pub mod root;
pub mod song;
pub mod parser;
pub mod spotify;
pub use root::RootController;
pub use song::SONG_CONTROLLER;
pub use parser::{ get_html };
pub use spotify::SPOTIFY_CONTROLLER;