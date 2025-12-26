use serde_json::{ from_str };
use scraper::{Html, Selector};
use tracing::debug;

fn get_lyrics(html: &str) -> String {
    let fragment = Html::parse_fragment(html);
    let mut chunks: Vec<String> = Vec::new();

    // Try modern and legacy Genius lyrics containers
    let selectors = [
        r#"div[data-lyrics-container="true"]"#,
        r#".Lyrics__Container-sc-1ynbvzw-6"#,
    ];

    for sel in selectors {
        if let Ok(selector) = Selector::parse(sel) {
            for element in fragment.select(&selector) {
                let text = element.text().collect::<String>().trim().to_string();
                if !text.is_empty() {
                    chunks.push(text);
                }
            }
        }
        if !chunks.is_empty() {
            break;
        }
    }

    chunks.join("\n\n")
}

pub async fn get_html(link: &String) -> Result<String, anyhow::Error> {
    let client = reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (compatible; ai-dj/1.0; +https://example.com)")
        .build()?;

    let resp = client
        .get(link)
        .send()
        .await?;

    let data = resp.text().await?;

    // Page may be delivered as a JSON-encoded HTML string; fall back to raw text if parsing fails
    let html = from_str::<String>(data.trim()).unwrap_or_else(|_| data);

    let lyrics = get_lyrics(&html);
    debug!("extracted_lyrics_len={}", lyrics.len());
    Ok(lyrics)
}