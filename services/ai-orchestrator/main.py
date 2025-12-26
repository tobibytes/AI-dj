"""
AI Orchestrator Service - AI DJ
GPT-5.2 powered prompt interpretation, playlist generation, and mix orchestration
"""

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from prompt_interpreter import PromptInterpreter, MixIntent
from playlist_generator import PlaylistGenerator, PlaylistTrack
from trends import TrendsFetcher


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    openai_api_key: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
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
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    
    yield
    
    # Shutdown
    if redis_client:
        await redis_client.close()


app = FastAPI(
    title="AI DJ Orchestrator",
    description="GPT-5.2 powered mix generation and orchestration",
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
    spotify_access_token: str


class TransitionConfig(BaseModel):
    type: str  # "crossfade", "echo_out", "filter_sweep", "backspin"
    bars: int = 8
    direction: Optional[str] = None


class TrackInfo(BaseModel):
    spotify_id: str
    title: str
    artist: str
    duration_ms: int
    bpm: float
    key: str
    energy: float
    danceability: float
    transition: TransitionConfig


class GenerateMixResponse(BaseModel):
    session_id: str
    status: str
    message: str
    playlist: list[TrackInfo] = []
    target_bpm: float = 0
    estimated_duration_minutes: float = 0


class InterpretPromptRequest(BaseModel):
    prompt: str


class GetPlaylistRequest(BaseModel):
    intent: MixIntent
    spotify_access_token: str


class StartRenderRequest(BaseModel):
    session_id: str
    playlist: list[TrackInfo]
    target_bpm: float
    transitions: list[TransitionConfig]


# Initialize services
def get_interpreter(api_key: str) -> PromptInterpreter:
    return PromptInterpreter(api_key=api_key)


def get_playlist_generator(
    client_id: str,
    client_secret: str,
    access_token: str
) -> PlaylistGenerator:
    return PlaylistGenerator(
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token
    )


trends_fetcher = TrendsFetcher()


async def publish_progress(session_id: str, stage: str, progress: int, detail: str = ""):
    """Publish progress update to Redis"""
    if redis_client:
        await redis_client.publish(
            f"mix:{session_id}:progress",
            f'{{"stage": "{stage}", "progress": {progress}, "detail": "{detail}"}}'
        )


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-orchestrator"}


@app.post("/interpret", response_model=MixIntent)
async def interpret_prompt(
    request: InterpretPromptRequest,
    x_openai_key: str = Header(None, alias="X-OpenAI-Key")
):
    """
    Interpret a user prompt using GPT-5.2 to extract mix parameters
    """
    api_key = x_openai_key or settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key required")
    
    try:
        interpreter = get_interpreter(api_key)
        
        # Get current trends for context
        trends = await trends_fetcher.get_trending_context()
        
        intent = await interpreter.interpret(request.prompt, trends_context=trends)
        return intent
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-playlist")
async def generate_playlist(
    request: GetPlaylistRequest,
    x_openai_key: str = Header(None, alias="X-OpenAI-Key")
):
    """
    Generate a playlist based on interpreted intent
    """
    try:
        generator = get_playlist_generator(
            settings.spotify_client_id,
            settings.spotify_client_secret,
            request.spotify_access_token
        )
        
        api_key = x_openai_key or settings.openai_api_key
        interpreter = get_interpreter(api_key) if api_key else None
        
        playlist = await generator.generate(request.intent, interpreter)
        
        return {"playlist": playlist}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-mix", response_model=GenerateMixResponse)
async def generate_mix(
    request: GenerateMixRequest,
    x_openai_key: str = Header(None, alias="X-OpenAI-Key")
):
    """
    Full mix generation pipeline:
    1. Interpret prompt with GPT-5.2
    2. Generate playlist from Spotify
    3. Order by harmonic compatibility
    4. Suggest transitions
    5. Trigger audio processor to download, analyze, render
    """
    session_id = str(uuid.uuid4())
    
    api_key = x_openai_key or settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key required")
    
    try:
        # Step 1: Interpret prompt
        await publish_progress(session_id, "interpreting", 0, "Understanding your request...")
        
        interpreter = get_interpreter(api_key)
        trends = await trends_fetcher.get_trending_context()
        intent = await interpreter.interpret(request.prompt, trends_context=trends)
        
        # Override duration if specified
        if request.duration_minutes:
            intent.duration_minutes = request.duration_minutes
        
        await publish_progress(session_id, "interpreting", 100, f"Creating a {intent.duration_minutes} minute {', '.join(intent.genres)} mix")
        
        # Step 2: Generate playlist
        await publish_progress(session_id, "fetching", 0, "Finding tracks on Spotify...")
        
        generator = get_playlist_generator(
            settings.spotify_client_id,
            settings.spotify_client_secret,
            request.spotify_access_token
        )
        
        playlist = await generator.generate(intent, interpreter)
        
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
                bpm=track.bpm,
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
        asyncio.create_task(
            trigger_audio_processor(
                session_id,
                tracks,
                intent.target_bpm,
                transitions
            )
        )
        
        # Calculate estimated duration
        total_duration_ms = sum(t.duration_ms for t in tracks)
        estimated_minutes = total_duration_ms / 60000
        
        return GenerateMixResponse(
            session_id=session_id,
            status="processing",
            message=f"Generating your {intent.duration_minutes} minute mix...",
            playlist=tracks,
            target_bpm=intent.target_bpm,
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
    target_bpm: float,
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
                params={"session_id": session_id, "target_bpm": target_bpm},
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
