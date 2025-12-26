"""
Trends Fetcher - Get trending tracks and context from various sources
"""

from typing import Optional
import asyncio

import httpx


class TrendsFetcher:
    """
    Fetches trending music data from various sources
    """
    
    def __init__(self):
        self.spotify_charts_url = "https://api.spotify.com/v1/playlists"
        
        # Spotify's official viral and top charts playlist IDs
        self.chart_playlists = {
            "viral_global": "37i9dQZEVXbLiRSasKsNU9",  # Viral 50 Global
            "top_global": "37i9dQZEVXbMDoHDwVN2tF",    # Top 50 Global
            "viral_us": "37i9dQZEVXbKuaTI1Z1Afx",      # Viral 50 USA
            "top_us": "37i9dQZEVXbLRQDuF5jeBp",        # Top 50 USA
        }
    
    async def get_trending_tracks(
        self,
        access_token: Optional[str] = None
    ) -> list[dict]:
        """
        Get currently trending tracks from Spotify charts
        """
        
        if not access_token:
            # Return mock data if no token
            return self._get_mock_trending()
        
        trending = []
        
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}"}
            
            for chart_name, playlist_id in self.chart_playlists.items():
                try:
                    response = await client.get(
                        f"{self.spotify_charts_url}/{playlist_id}/tracks",
                        headers=headers,
                        params={"limit": 20}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("items", []):
                            track = item.get("track", {})
                            if track:
                                trending.append({
                                    "id": track.get("id"),
                                    "name": track.get("name"),
                                    "artist": ", ".join([a["name"] for a in track.get("artists", [])]),
                                    "chart": chart_name,
                                    "popularity": track.get("popularity", 0)
                                })
                except Exception as e:
                    print(f"Failed to fetch {chart_name}: {e}")
        
        # Deduplicate
        seen_ids = set()
        unique_trending = []
        for track in trending:
            if track["id"] not in seen_ids:
                seen_ids.add(track["id"])
                unique_trending.append(track)
        
        # Sort by popularity
        unique_trending.sort(key=lambda x: -x.get("popularity", 0))
        
        return unique_trending[:50]
    
    async def get_trending_context(self) -> str:
        """
        Get a text summary of current trends for GPT context
        """
        
        # For now, return general trend context
        # In production, this would fetch from Spotify, TikTok, etc.
        
        context = """
CURRENT MUSIC TRENDS (December 2024):

HOT GENRES:
- Afrobeats continues global dominance (Burna Boy, Rema, Ayra Starr, Asake)
- Amapiano crossover hits (Tyler ICU, Kabza De Small)
- Latin/Reggaeton resurgence (Bad Bunny, Feid, Karol G)
- UK Drill/Garage revival
- Hyperpop and experimental electronic

TRENDING SOUNDS:
- 808 bass patterns
- Afrobeats log drums
- Amapiano piano stabs
- Drill hi-hats
- Y2K/nostalgic 2000s revival

VIRAL TRACKS/ARTISTS:
- Tyla with Afrobeats/Amapiano fusion
- Ayra Starr's melodic Afrobeats
- Ice Spice's drill influence
- Peso Pluma's regional Mexican crossover

MIXING NOTES:
- Afrobeats: 95-105 BPM, log drum patterns
- Amapiano: 110-115 BPM, distinctive basslines
- Drill: 140 BPM (or 70 half-time)
- Reggaeton: 90-100 BPM, dembow rhythm
"""
        
        return context
    
    def _get_mock_trending(self) -> list[dict]:
        """Return mock trending data when no Spotify access"""
        
        return [
            {"id": "mock1", "name": "Water", "artist": "Tyla", "chart": "viral_global", "popularity": 95},
            {"id": "mock2", "name": "Last Last", "artist": "Burna Boy", "chart": "top_global", "popularity": 92},
            {"id": "mock3", "name": "Calm Down", "artist": "Rema", "chart": "top_global", "popularity": 91},
            {"id": "mock4", "name": "Rush", "artist": "Ayra Starr", "chart": "viral_global", "popularity": 88},
            {"id": "mock5", "name": "Unavailable", "artist": "Davido, Musa Keys", "chart": "viral_global", "popularity": 85},
        ]


class TikTokTrendsFetcher:
    """
    Fetches trending sounds from TikTok Creative Center
    Note: Requires TikTok API access
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://business-api.tiktok.com/open_api/v1.3"
    
    async def get_trending_sounds(self) -> list[dict]:
        """
        Get trending sounds from TikTok
        
        Note: This requires TikTok Business API access.
        For now, returns empty list if no API key.
        """
        
        if not self.api_key:
            return []
        
        # TikTok Creative Center API integration would go here
        # This requires business API registration
        
        return []


class TwitterTrendsFetcher:
    """
    Fetches music-related trends from Twitter/X
    Note: Requires Twitter API v2 access
    """
    
    def __init__(self, bearer_token: Optional[str] = None):
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"
    
    async def get_music_trends(self) -> list[str]:
        """
        Get music-related trending topics
        
        Note: Requires Twitter API v2 access (paid tier)
        """
        
        if not self.bearer_token:
            return []
        
        # Twitter API integration would go here
        # Requires API access subscription
        
        return []
