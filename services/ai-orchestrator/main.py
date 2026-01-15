"""
AI Orchestrator Service - AI DJ
Direct Spotify playlist search and track extraction
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from playlist_generator import PlaylistGenerator, PlaylistTrack


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    spotify_token: str = ""
    audio_processor_url: str = "http://audio-processor:8001"
    backend_url: str = "http://backend:8000"
    
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
    print(f"Orchestrator connecting to Redis at: {settings.redis_url}")
    import logging
    logging.warning(f"Orchestrator connecting to Redis at: {settings.redis_url}")
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    
    yield
    
    # Shutdown
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="AI DJ Orchestrator",
    description="GPT-4o powered mix generation and orchestration",
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


# Request/Response Models
class GenerateMixRequest(BaseModel):
    prompt: str
    duration_minutes: Optional[int] = None  # Override, otherwise GPT interprets


class TransitionConfig(BaseModel):
    type: str  # "crossfade", "echo_out", "filter_sweep", "backspin"
    bars: int = 8
    direction: Optional[str] = None


class TrackInfo(BaseModel):
    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    key: str
    energy: float
    danceability: float
    transition: TransitionConfig


class GenerateMixResponse(BaseModel):
    session_id: str
    status: str
    message: str
    playlist: list[TrackInfo] = []
    estimated_duration_minutes: float = 0


# Initialize services
def get_playlist_generator(access_token: str) -> PlaylistGenerator:
    return PlaylistGenerator(access_token)


async def publish_progress(session_id: str, stage: str, progress: int, detail: str = ""):
    """Publish progress update to Redis"""
    try:
        if redis_client:
            channel = f"mix:{session_id}:progress"
            message = f'{{"stage": "{stage}", "progress": {progress}, "detail": "{detail}"}}'
            await redis_client.publish(channel, message)
            print(f"Published progress to Redis channel {channel}: {message}")
        else:
            print(f"Redis not available, skipping progress update: {stage} {progress}% - {detail}")
    except Exception as e:
        # Redis not available, continue without progress updates
        print(f"Failed to publish progress update: {e}")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-orchestrator"}


@app.post("/generate-mix", response_model=GenerateMixResponse)
async def generate_mix(request: GenerateMixRequest):
    """
    Simplified mix generation pipeline:
    1. Search Spotify for playlists using the prompt
    2. Pick the first playlist
    3. Get tracks from that playlist
    4. Send to audio processor for download and mixing
    """
    session_id = str(uuid.uuid4())

    try:
        # Create mix session in database
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.backend_url}/api/mixes/{session_id}/create",
                    json={"prompt": request.prompt}
                )
                if response.status_code != 200:
                    print(f"Warning: Failed to create mix session in database: {response.text}")
        except Exception as e:
            print(f"Warning: Could not connect to backend for session creation: {e}")

        # Small delay to allow websocket to connect and subscribe
        await asyncio.sleep(1.0)
        
        # Step 1: Search for playlists on Spotify
        await publish_progress(session_id, "searching", 0, f"Searching Spotify for playlists: '{request.prompt}'")
        await publish_progress(session_id, "searching", 10, "Connecting to Spotify API...")

        generator = get_playlist_generator(settings.spotify_token)
        await publish_progress(session_id, "searching", 25, "Querying Spotify for matching playlists...")
        
        playlist = await generator.search_playlist_and_get_tracks(request.prompt, request.duration_minutes)
        await publish_progress(session_id, "searching", 75, f"Found playlist with {len(playlist)} tracks")
        await publish_progress(session_id, "searching", 100, f"Playlist search complete")

        # Step 2: Process tracks
        await publish_progress(session_id, "processing", 0, "Processing track metadata...")
        
        # Convert to response format
        tracks = []
        transitions = []

        for i, track in enumerate(playlist):
            tracks.append(TrackInfo(
                spotify_id=track.spotify_id,
                title=track.title,
                artist=track.artist,
                duration_ms=track.duration_ms,
                key=track.key,
                energy=track.energy,
                danceability=track.danceability,
                transition=TransitionConfig(
                    type=track.transition_type,
                    bars=track.transition_bars,
                    direction=track.transition_direction
                )
            ))
            transitions.append(TransitionConfig(
                type=track.transition_type,
                bars=track.transition_bars,
                direction=track.transition_direction
            ))
            
            # Send progress update every 10 tracks
            if (i + 1) % 10 == 0:
                progress = int(20 + (i + 1) / len(playlist) * 30)  # 20-50% for processing
                await publish_progress(session_id, "processing", progress, f"Processed {i + 1}/{len(playlist)} tracks...")

        await publish_progress(session_id, "processing", 50, "Track processing complete")
        await publish_progress(session_id, "processing", 60, "Preparing audio processor request...")

        # Step 2: Trigger audio processor (async)
        
        await publish_progress(session_id, "fetching", 100, f"Found {len(playlist)} tracks")
        
        # Convert to response format
        tracks = []
        transitions = []
        
        for track in playlist:
            tracks.append(TrackInfo(
                spotify_id=track.spotify_id,
                title=track.title,
                artist=track.artist,
                duration_ms=track.duration_ms,
                key=track.key,
                energy=track.energy,
                danceability=track.danceability,
                transition=TransitionConfig(
                    type=track.transition_type,
                    bars=track.transition_bars,
                    direction=track.transition_direction
                )
            ))
            transitions.append(TransitionConfig(
                type=track.transition_type,
                bars=track.transition_bars,
                direction=track.transition_direction
            ))
        
        # Step 3: Trigger audio processor (async)
        # The frontend will connect via WebSocket to track progress
        await publish_progress(session_id, "processing", 80, "Sending tracks to audio processor...")
        
        asyncio.create_task(
            trigger_audio_processor(
                session_id,
                tracks,
                transitions
            )
        )
        
        await publish_progress(session_id, "processing", 100, "Mix generation started - connecting to audio processor...")
        
        # Calculate estimated duration
        total_duration_ms = sum(t.duration_ms for t in tracks)
        estimated_minutes = total_duration_ms / 60000
        
        return GenerateMixResponse(
            session_id=session_id,
            status="processing",
            message=f"Generating your {round(estimated_minutes, 1)} minute mix...",
            playlist=tracks,
            estimated_duration_minutes=round(estimated_minutes, 1)
        )
        
    except Exception as e:
        if redis_client:
            await redis_client.publish(
                f"mix:{session_id}:error",
                f'{{"error": "{str(e)}"}}'
            )
        raise HTTPException(status_code=500, detail=str(e))


async def trigger_audio_processor(
    session_id: str,
    tracks: list[TrackInfo],
    transitions: list[TransitionConfig]
):
    """
    Call the audio processor service to download, analyze, and render the mix
    """
    try:
        async with httpx.AsyncClient(timeout=1800.0) as client:  # 30 min timeout
            # Convert to audio processor format
            track_data = [
                {
                    "spotify_id": t.spotify_id,
                    "title": t.title,
                    "artist": t.artist,
                    "duration_ms": t.duration_ms
                }
                for t in tracks
            ]
            
            transition_data = [
                {
                    "type": t.type,
                    "bars": t.bars,
                    "direction": t.direction
                }
                for t in transitions
            ]
            
            response = await client.post(
                f"{settings.audio_processor_url}/process-mix",
                params={"session_id": session_id},
                json={
                    "tracks": track_data,
                    "transitions": transition_data
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Audio processor error: {response.text}")
                
    except Exception as e:
        if redis_client:
            await redis_client.publish(
                f"mix:{session_id}:error",
                f'{{"error": "{str(e)}"}}'
            )


@app.get("/trends")
async def get_trends():
    """
    Get current trending tracks and context
    """
    try:
        trends = await trends_fetcher.get_trending_tracks()
        context = await trends_fetcher.get_trending_context()
        
        return {
            "tracks": trends,
            "context": context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


