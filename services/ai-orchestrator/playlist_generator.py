"""
Playlist Generator - Spotify-based track discovery and harmonic ordering
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
import requests
from pydantic import BaseModel


class PlaylistTrack(BaseModel):
    """Track with all metadata for mixing"""
    spotify_id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    key: str  # Camelot notation
    energy: float
    danceability: float
    valence: float  # Musical positivity
    acousticness: float
    instrumentalness: float
    popularity: int
    preview_url: Optional[str] = None
    # Transition to use AFTER this track
    transition_type: str = "crossfade"
    transition_bars: int = 8
    transition_direction: Optional[str] = None


# Spotify key to Camelot wheel mapping
# Spotify uses Pitch Class (0-11) and Mode (0=minor, 1=major)
SPOTIFY_KEY_TO_CAMELOT = {
    (0, 1): "8B",   # C major
    (0, 0): "5A",   # C minor
    (1, 1): "3B",   # C#/Db major
    (1, 0): "12A",  # C#/Db minor
    (2, 1): "10B",  # D major
    (2, 0): "7A",   # D minor
    (3, 1): "5B",   # D#/Eb major
    (3, 0): "2A",   # D#/Eb minor
    (4, 1): "12B",  # E major
    (4, 0): "9A",   # E minor
    (5, 1): "7B",   # F major
    (5, 0): "4A",   # F minor
    (6, 1): "2B",   # F#/Gb major
    (6, 0): "11A",  # F#/Gb minor
    (7, 1): "9B",   # G major
    (7, 0): "6A",   # G minor
    (8, 1): "4B",   # G#/Ab major
    (8, 0): "1A",   # G#/Ab minor
    (9, 1): "11B",  # A major
    (9, 0): "8A",   # A minor
    (10, 1): "6B",  # A#/Bb major
    (10, 0): "3A",  # A#/Bb minor
    (11, 1): "1B",  # B major
    (11, 0): "10A", # B minor
}


def get_camelot_key(spotify_key: int, mode: int) -> str:
    """Convert Spotify key/mode to Camelot notation"""
    return SPOTIFY_KEY_TO_CAMELOT.get((spotify_key, mode), "1A")


def get_compatible_keys(camelot: str) -> list[str]:
    """Get harmonically compatible keys for mixing"""
    if len(camelot) < 2:
        return [camelot]
    
    number = int(camelot[:-1])
    mode = camelot[-1]  # 'A' or 'B'
    
    compatible = [camelot]
    
    # Same number, different mode (parallel key)
    parallel_mode = 'A' if mode == 'B' else 'B'
    compatible.append(f"{number}{parallel_mode}")
    
    # +1 on wheel (same mode)
    next_num = (number % 12) + 1
    compatible.append(f"{next_num}{mode}")
    
    # -1 on wheel (same mode)
    prev_num = ((number - 2) % 12) + 1
    compatible.append(f"{prev_num}{mode}")
    
    return compatible


def camelot_distance(key1: str, key2: str) -> int:
    """Calculate distance on Camelot wheel (lower is more compatible)"""
    if len(key1) < 2 or len(key2) < 2:
        return 12
    
    num1 = int(key1[:-1])
    mode1 = key1[-1]
    num2 = int(key2[:-1])
    mode2 = key2[-1]
    
    # Same key
    if key1 == key2:
        return 0
    
    # Parallel key (same number, different mode)
    if num1 == num2:
        return 1
    
    # Adjacent on wheel (same mode)
    if mode1 == mode2:
        diff = abs(num1 - num2)
        wheel_diff = min(diff, 12 - diff)
        return wheel_diff
    
    # Different mode and number
    return 6


class PlaylistGenerator:
    """
    Generates playlists using Spotify Web API with direct HTTP requests.
    
    Uses Bearer token authentication from SPOTIFY_TOKEN environment variable.
    """
    
    def __init__(
        self,
        access_token: Optional[str] = None  # Kept for API compatibility but not used
    ):
        # Try to get token from environment, or get one using client credentials
        self.token = os.getenv('SPOTIFY_TOKEN')
        
        if not self.token:
            # Try to get token using client credentials flow
            self.token = self._get_client_credentials_token()
        
        if not self.token:
            raise ValueError("SPOTIFY_TOKEN environment variable is required, or SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET for automatic token retrieval")
        
        print("PlaylistGenerator: Using direct Spotify Web API with Bearer token")
    
    def _get_client_credentials_token(self) -> Optional[str]:
        """Get access token using client credentials flow"""
        import base64
        
        client_id = os.getenv('SPOTIFY_CLIENT_ID')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
        
        if not client_id or not client_secret:
            print("Missing Spotify credentials")
            return None
        
        # Encode client credentials
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        
        try:
            import requests
            response = requests.post(
                'https://accounts.spotify.com/api/token',
                headers={
                    'Authorization': f'Basic {credentials}',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                data={'grant_type': 'client_credentials'}
            )
            
            print(f"Token response status: {response.status_code}")
            if response.status_code == 200:
                token_data = response.json()
                token = token_data.get('access_token')
                return token
            else:
                print(f"Failed to get Spotify token: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Error getting Spotify token: {e}")
            return None
    
    async def _fetch_web_api(self, endpoint: str, method: str = 'GET', body: Optional[dict] = None) -> dict:
        """Make a request to the Spotify Web API"""
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=f"https://api.spotify.com/{endpoint}",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json=body
            )
            
            if response.status_code == 401:
                raise Exception("Invalid Spotify token - check SPOTIFY_TOKEN environment variable")
            elif response.status_code != 200:
                raise Exception(f"Spotify API error: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def _search_tracks_api(self, query: str, limit: int = 9) -> dict:
        """Search for tracks using Spotify Web API"""
        return await self._fetch_web_api(
            f'v1/search?q={query}&type=track&limit={limit}',
            'GET'
        )
    
    async def _get_playlist_tracks_api(self, playlist_id: str, limit: int = 9) -> dict:
        """Get tracks from a Spotify playlist"""
        return await self._fetch_web_api(
            f'v1/playlists/{playlist_id}/tracks?limit={limit}',
            'GET'
        )
    
    async def _get_audio_features_api(self, track_ids: list[str]) -> list[dict]:
        """Get audio features for tracks"""
        if not track_ids:
            return []
        
        # Spotify API limits to 100 tracks per request
        features = []
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i+100]
            ids_param = ','.join(batch)
            response = await self._fetch_web_api(f'v1/audio-features?ids={ids_param}', 'GET')
            features.extend(response.get('audio_features', []))
        
        return features
    
    async def search_playlist_and_get_tracks(self, query: str, duration_minutes: Optional[int] = None) -> list[PlaylistTrack]:
        """
        Search for playlists using the query, pick the first one, and get its tracks
        """
        # Search for playlists
        search_response = await self._fetch_web_api(f'v1/search?q={query}&type=playlist&limit=5', 'GET')
        
        playlists = search_response.get('playlists', {}).get('items', [])
        
        # Filter out None items
        valid_playlists = [p for p in playlists if p is not None]
        
        if not valid_playlists:
            raise Exception(f"No valid playlists found for query: {query}")
        
        # Get the first valid playlist
        playlist = valid_playlists[0]
        playlist_id = playlist['id']
        print(f"🎵 SPOTIFY PLAYLIST: Found playlist '{playlist['name']}' by {playlist['owner']['display_name']}")
        
        # Get tracks from the playlist
        tracks_response = await self._get_playlist_tracks_api(playlist_id, limit=50)
        tracks = tracks_response.get('items', [])
        
        if not tracks:
            raise Exception(f"No tracks found in playlist: {playlist['name']}")
        
        # Convert to our format and get audio features
        track_ids = []
        track_data = []
        
        for item in tracks:
            if item['track'] and item['track']['id']:
                track = item['track']
                track_ids.append(track['id'])
                track_data.append({
                    'id': track['id'],
                    'name': track['name'],
                    'artists': [{'name': artist['name']} for artist in track['artists']],
                    'album': {'name': track.get('album', {}).get('name', 'Unknown')},
                    'duration_ms': track['duration_ms'],
                    'popularity': track.get('popularity', 0)
                })
        
        # Limit tracks based on duration if specified
        if duration_minutes:
            target_duration_ms = duration_minutes * 60 * 1000  # Convert to milliseconds
            current_duration_ms = 0
            limited_track_data = []
            
            for track in track_data:
                if current_duration_ms + track['duration_ms'] <= target_duration_ms:
                    limited_track_data.append(track)
                    current_duration_ms += track['duration_ms']
                else:
                    break
            
            # Ensure we have at least 3 tracks minimum
            if len(limited_track_data) < 3 and len(track_data) >= 3:
                limited_track_data = track_data[:3]
            
            track_data = limited_track_data
            print(f"🎵 DURATION LIMIT: Limited to {len(track_data)} tracks for {duration_minutes} minute target")
        
        # Get audio features for tracks (estimated)
        tracks_with_features = self._estimate_audio_features(track_data)
        
        # Assign simple transitions
        self._assign_transitions_rule_based(tracks_with_features)
        
        print(f"🎵 SPOTIFY RESULTS: Retrieved {len(tracks_with_features)} tracks from playlist")
        return tracks_with_features
    
    def _generate_key_progression(self, num_tracks: int) -> list[str]:
        """Generate a musical key progression that goes low to high to low to high"""
        # Base progression pattern: low -> high -> low -> high
        # Using Camelot wheel numbers 1-12, alternating A/B modes for variety
        base_pattern = [
            "1A", "2B", "3A", "4B", "5A", "6B", "7A", "8B", "9A", "10B", "11A", "12B",  # Up
            "11B", "10A", "9B", "8A", "7B", "6A", "5B", "4A", "3B", "2A", "1B", "12A"   # Down
        ]
        
        # Repeat the pattern to cover all tracks
        progression = []
        pattern_idx = 0
        for i in range(num_tracks):
            progression.append(base_pattern[pattern_idx % len(base_pattern)])
            pattern_idx += 1
        
        return progression
    
    def _estimate_audio_features(self, tracks: list[dict]) -> list[PlaylistTrack]:
        """Estimate audio features for tracks based on metadata (simplified version)"""
        
        # Generate musical key progression
        key_progression = self._generate_key_progression(len(tracks))
        
        result = []
        for idx, track in enumerate(tracks):
            # Get artist names
            artists = ", ".join([a["name"] for a in track.get("artists", [])])
            
            # Estimate values from track metadata
            popularity = track.get("popularity", 50)
            
            # Estimate energy: popular tracks tend to be more energetic
            energy = min(0.9, 0.3 + (popularity / 100) * 0.5 + (idx % 5) * 0.05)
            danceability = min(0.9, 0.4 + (popularity / 100) * 0.4)
            valence = 0.5 + (popularity / 200)
            acousticness = 0.1
            instrumentalness = 0.1
            
            # Assign key from musical progression instead of random
            camelot_key = key_progression[idx]

            result.append(PlaylistTrack(
                spotify_id=track["id"],
                title=track.get("name", "Unknown"),
                artist=artists,
                album=track.get("album", {}).get("name", "Unknown"),
                duration_ms=track.get("duration_ms", 0),
                key=camelot_key,
                energy=energy,
                danceability=danceability,
                valence=valence,
                acousticness=acousticness,
                instrumentalness=instrumentalness,
                popularity=popularity,
                preview_url=track.get("preview_url")
            ))
        
        return result
    
    def _assign_transitions_rule_based(self, tracks: list[PlaylistTrack]):
        """Assign transitions based on energy changes (rule-based fallback)"""
        
        for i in range(len(tracks) - 1):
            current = tracks[i]
            next_track = tracks[i + 1]
            
            energy_delta = next_track.energy - current.energy
            
            if energy_delta < -0.3:
                # Big energy drop → echo out
                current.transition_type = "echo_out"
                current.transition_bars = 4
            elif energy_delta > 0.3:
                # Big energy build → filter sweep
                current.transition_type = "filter_sweep"
                current.transition_bars = 8
                current.transition_direction = "highpass"
            elif i == len(tracks) - 2:
                # Second to last → potential backspin for finale
                current.transition_type = "backspin"
                current.transition_bars = 2
            else:
                # Default smooth crossfade
                current.transition_type = "crossfade"
                current.transition_bars = 8
        
        # Last track doesn't need a transition
        if tracks:
            tracks[-1].transition_type = "crossfade"
            tracks[-1].transition_bars = 8
