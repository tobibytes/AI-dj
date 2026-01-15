"""
Audio Processor Service - AI DJ
Handles audio downloading, analysis, and mix rendering
"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from downloader import AudioDownloader
from analyzer import AudioAnalyzer
from renderer import MixRenderer
from cdn import CDNUploader


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    spotify_username: str = ""
    spotify_password: str = ""
    temp_audio_dir: str = "/tmp/audio"
    cdn_api_url: str = "https://api.cdn.tobiolajide.com"
    cdn_app_name: str = "ai-dj"
    
    class Config:
        env_file = ".env"


settings = Settings()


# Redis connection
redis_client: redis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global redis_client
    
    # Startup
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    Path(settings.temp_audio_dir).mkdir(parents=True, exist_ok=True)
    
    yield
    
    # Shutdown
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="AI DJ Audio Processor",
    description="Audio downloading, analysis, and mix rendering service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class TrackInfo(BaseModel):
    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    

class DownloadRequest(BaseModel):
    track: TrackInfo
    session_id: str


class DownloadResponse(BaseModel):
    success: bool
    file_path: str | None
    source: str  # "librespot" or "youtube"
    error: str | None = None


class PlaylistDownloadRequest(BaseModel):
    tracks: list[TrackInfo]
    session_id: str


class PlaylistDownloadResponse(BaseModel):
    success: bool
    downloaded_tracks: list[dict]  # List of downloaded track info
    error: str | None = None


class AnalyzeRequest(BaseModel):
    file_path: str
    session_id: str


class AnalysisResult(BaseModel):
    key: str
    energy: float
    beat_positions: list[float]  # timestamps in seconds
    phrase_boundaries: list[float]
    intro_end: float  # timestamp where intro ends
    outro_start: float  # timestamp where outro begins
    duration: float


class TransitionConfig(BaseModel):
    type: str  # "crossfade", "echo_out", "filter_sweep", "backspin"
    bars: int = 8
    direction: str | None = None  # for filter_sweep: "lowpass" or "highpass"


class TrackWithAnalysis(BaseModel):
    file_path: str
    title: str
    artist: str
    key: str
    energy: float
    intro_end: float
    outro_start: float
    duration: float
    transition: TransitionConfig
    # New: smart loop points for DJ mixing
    best_loop_start: float = 0.0
    best_loop_end: float = 0.0
    drop_time: float | None = None


class RenderRequest(BaseModel):
    session_id: str
    tracks: list[TrackWithAnalysis]
    output_format: str = "mp3"  # "mp3" or "wav"


class RenderResponse(BaseModel):
    success: bool
    cdn_url: str | None = None
    duration_seconds: float | None = None
    error: str | None = None


class ProcessMixRequest(BaseModel):
    tracks: list[TrackInfo]
    transitions: list[TransitionConfig]


# Initialize services
downloader = AudioDownloader(
    temp_dir=settings.temp_audio_dir,
    spotify_username=settings.spotify_username,
    spotify_password=settings.spotify_password
)
analyzer = AudioAnalyzer()
renderer = MixRenderer(temp_dir=settings.temp_audio_dir)
cdn_uploader = CDNUploader(
    api_url=settings.cdn_api_url,
    app_name=settings.cdn_app_name
)


async def publish_progress(session_id: str, stage: str, progress: int, detail: str = "", source: str = "", current_track: str = ""):
    """Publish progress update to Redis using proper JSON serialization"""
    if redis_client:
        import json
        message = json.dumps({
            "stage": stage,
            "progress": progress,
            "detail": detail,
            "source": source,
            "current_track": current_track
        })
        await redis_client.publish(f"mix:{session_id}:progress", message)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "audio-processor"}


@app.post("/download-playlist", response_model=PlaylistDownloadResponse)
async def download_playlist(request: PlaylistDownloadRequest):
    """
    Download multiple tracks from a playlist using formatted YouTube searches.
    Avoids duplicates and uses proper "Song by Artist" search format.
    """
    try:
        await publish_progress(
            request.session_id,
            "downloading",
            0,
            f"Starting playlist download ({len(request.tracks)} tracks)",
            ""
        )
        
        # Convert TrackInfo objects to dicts for the downloader
        tracks_dict = [
            {
                'spotify_id': track.spotify_id,
                'title': track.title,
                'artist': track.artist
            }
            for track in request.tracks
        ]
        
        # Download all tracks with duplicate prevention
        downloaded_tracks = await downloader.download_playlist_tracks(
            tracks_dict,
            request.session_id
        )
        
        await publish_progress(
            request.session_id,
            "downloading",
            100,
            f"Downloaded {len(downloaded_tracks)}/{len(request.tracks)} tracks",
            "youtube"
        )
        
        return PlaylistDownloadResponse(
            success=True,
            downloaded_tracks=downloaded_tracks
        )
    except Exception as e:
        return PlaylistDownloadResponse(
            success=False,
            downloaded_tracks=[],
            error=str(e)
        )


@app.post("/analyze", response_model=AnalysisResult)
async def analyze_track(request: AnalyzeRequest):
    """
    Analyze audio file for key, beat positions, energy, etc.
    """
    try:
        await publish_progress(
            request.session_id,
            "analyzing",
            0,
            request.file_path
        )
        
        result = await asyncio.to_thread(
            analyzer.analyze,
            request.file_path
        )
        
        await publish_progress(
            request.session_id,
            "analyzing",
            100,
            request.file_path
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/render-mix", response_model=RenderResponse)
async def render_mix(request: RenderRequest, background_tasks: BackgroundTasks):
    """
    Render a complete mix from analyzed tracks with transitions
    """
    try:
        # Render the mix
        output_path = await asyncio.to_thread(
            renderer.render,
            request.tracks,
            request.output_format,
            request.session_id,
            lambda stage, progress, detail: asyncio.run(
                publish_progress(request.session_id, stage, progress, detail)
            )
        )
        
        # Upload to CDN
        await publish_progress(request.session_id, "uploading", 0, "Uploading to CDN...")
        
        cdn_url = await cdn_uploader.upload(output_path)
        
        await publish_progress(request.session_id, "uploading", 100, cdn_url)
        
        # Get duration
        from pydub import AudioSegment
        audio = AudioSegment.from_file(output_path)
        duration_seconds = len(audio) / 1000.0
        
        # Clean up local file after upload (in background)
        background_tasks.add_task(os.remove, output_path)
        
        return RenderResponse(
            success=True,
            cdn_url=cdn_url,
            duration_seconds=duration_seconds
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process-mix")
async def process_full_mix(
    session_id: str,
    request: ProcessMixRequest,
    background_tasks: BackgroundTasks
):
    """
    Full pipeline: download all tracks from playlist, analyze, render mix, upload
    Uses formatted YouTube searches to avoid duplicates and get better matches
    """
    try:
        tracks = request.tracks
        transitions = request.transitions
        processed_tracks = []
        total_tracks = len(tracks)
        
        if total_tracks == 0:
            raise HTTPException(status_code=400, detail="No tracks provided")
        
        # Convert tracks to dict format for playlist download
        tracks_dict = [
            {
                'spotify_id': track.spotify_id,
                'title': track.title,
                'artist': track.artist
            }
            for track in tracks
        ]
        
        # Download all tracks at once with duplicate prevention
        await publish_progress(
            session_id,
            "downloading",
            0,
            f"Downloading {total_tracks} tracks from playlist...",
            ""
        )
        
        downloaded_tracks = await downloader.download_playlist_tracks(
            tracks_dict,
            session_id
        )
        
        await publish_progress(
            session_id,
            "downloading",
            50,
            f"Downloaded {len(downloaded_tracks)}/{total_tracks} tracks successfully",
            "youtube"
        )
        
        # Create a mapping from spotify_id to downloaded track info
        downloaded_map = {dt['spotify_id']: dt for dt in downloaded_tracks}
        
        # Process each track that was successfully downloaded
        successful_downloads = 0
        for i, track in enumerate(tracks):
            spotify_id = track.spotify_id
            
            if spotify_id not in downloaded_map:
                print(f"Skipping track not downloaded: {track.artist} - {track.title}")
                continue
            
            downloaded_info = downloaded_map[spotify_id]
            file_path = downloaded_info['file_path']
            
            # Analyze
            await publish_progress(
                session_id,
                "analyzing",
                50 + int((successful_downloads / len(downloaded_tracks)) * 50),
                f"Analyzing {successful_downloads+1}/{len(downloaded_tracks)}: {track.artist} - {track.title}"
            )
            
            analysis = await asyncio.to_thread(analyzer.analyze, file_path)
            
            # Combine track data
            transition = transitions[successful_downloads] if successful_downloads < len(transitions) else TransitionConfig(type="crossfade", bars=8)
            
            processed_tracks.append(TrackWithAnalysis(
                file_path=file_path,
                title=track.title,
                artist=track.artist,
                key=analysis.key,
                energy=analysis.energy,
                intro_end=analysis.intro_end,
                outro_start=analysis.outro_start,
                duration=analysis.duration,
                transition=transition,
                best_loop_start=analysis.best_loop_start,
                best_loop_end=analysis.best_loop_end,
                drop_time=analysis.drop_time
            ))
            
            successful_downloads += 1
        
        # Render mix
        await publish_progress(session_id, "rendering", 0, "Starting mix render...")
        
        def progress_callback(stage, progress, detail):
            # Run in sync context
            asyncio.create_task(publish_progress(session_id, stage, progress, detail))
        
        output_path = await asyncio.to_thread(
            renderer.render,
            processed_tracks,
            "mp3",
            session_id,
            None  # Progress handled above
        )
        
        # Upload to CDN
        await publish_progress(session_id, "uploading", 0, "Uploading to CDN...")
        cdn_url = await cdn_uploader.upload(output_path)
        await publish_progress(session_id, "complete", 100, "Mix complete!")
        
        # Publish completion event with proper JSON
        if redis_client:
            import json
            await redis_client.publish(
                f"mix:{session_id}:complete",
                json.dumps({"cdn_url": cdn_url})
            )
        
        # Clean up downloaded tracks
        for track in processed_tracks:
            background_tasks.add_task(os.remove, track.file_path)
        background_tasks.add_task(os.remove, output_path)
        
        return {"success": True, "cdn_url": cdn_url}
        
    except Exception as e:
        if redis_client:
            import json
            await redis_client.publish(
                f"mix:{session_id}:error",
                json.dumps({"error": str(e)})
            )
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
