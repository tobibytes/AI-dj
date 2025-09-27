use anyhow;
use std::process::Command;

fn get_stream(video_url: &str) -> anyhow::Result<String> {
    let output = Command::new("yt-dlp")
        .arg("-f")
        .arg("bestaudio")
        .arg("-g") // get direct URL
        .arg(video_url)
        .output()?;
    
    let url = String::from_utf8(output.stdout)?.trim().to_string();
    Ok(url)
}

fn main() -> anyhow::Result<()> {
    let url = get_stream("https://youtu.be/AKdFb0ljCJ0")?;
    println!("Direct stream: {}", url);
    Ok(())
}