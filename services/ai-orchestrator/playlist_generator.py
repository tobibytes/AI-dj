"""
Playlist Generator - Spotify-based track discovery and harmonic ordering
"""

import asyncio
import logging
from typing import Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
from pydantic import BaseModel

from prompt_interpreter import MixIntent, PromptInterpreter


class PlaylistTrack(BaseModel):
    """Track with all metadata for mixing"""
    spotify_id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    bpm: float
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
    Generates playlists using Spotify API with harmonic mixing.
    
    Uses Client Credentials flow exclusively for reliable token management.
    The SpotifyClientCredentials auth manager handles token refresh automatically.
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None  # Kept for API compatibility but not used
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        
        # Always use Client Credentials flow - it handles token refresh automatically
        # We don't need user-specific features (like user's library), just search
        auth_manager = SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        )
        self.sp = spotipy.Spotify(auth_manager=auth_manager)
        print("PlaylistGenerator: Using Client Credentials flow (auto-refreshing token)")
    
    async def generate(
        self,
        intent: MixIntent,
        interpreter: Optional[PromptInterpreter] = None
    ) -> list[PlaylistTrack]:
        """
        Generate a playlist based on the mix intent
        """
        
        # Search for tracks based on genres and artists
        candidate_tracks = await self._search_tracks(intent)
        
        if not candidate_tracks:
            raise Exception("No tracks found matching your criteria")
        
        # Get audio features for all tracks
        tracks_with_features = await self._get_audio_features(candidate_tracks)
        
        # Filter by BPM compatibility (within 10% of target)
        bpm_min = intent.target_bpm * 0.9
        bpm_max = intent.target_bpm * 1.1
        compatible_tracks = [
            t for t in tracks_with_features
            if bpm_min <= t.bpm <= bpm_max or bpm_min <= t.bpm * 2 <= bpm_max
        ]
        
        # Sort by quality metrics: popularity, and basic energy preference
        def track_quality(track):
            popularity_score = track.popularity / 100.0
            
            # Simple energy preference: prefer tracks that match the overall energy level
            # Map energy_curve to rough energy expectations
            energy_expectation = {
                "steady": 0.6,
                "build-peak-cooldown": 0.7,
                "build-only": 0.8,
                "cooldown-only": 0.4
            }.get(intent.energy_curve, 0.6)
            
            energy_match = 1.0 - abs(track.energy - energy_expectation)
            
            return popularity_score * 0.7 + energy_match * 0.3
        
        compatible_tracks.sort(key=track_quality, reverse=True)
        
        # If not enough tracks, expand BPM range
        if len(compatible_tracks) < intent.track_count:
            bpm_min = intent.target_bpm * 0.8
            bpm_max = intent.target_bpm * 1.2
            expanded_tracks = [
                t for t in tracks_with_features
                if bpm_min <= t.bpm <= bpm_max or bpm_min <= t.bpm * 2 <= bpm_max
            ]
            expanded_tracks.sort(key=track_quality, reverse=True)
            compatible_tracks = expanded_tracks
        
        # If still not enough, use all tracks (but still sort by quality)
        if len(compatible_tracks) < intent.track_count:
            tracks_with_features.sort(key=track_quality, reverse=True)
            compatible_tracks = tracks_with_features
        
        # Order tracks harmonically
        ordered_tracks = self._order_harmonically(
            compatible_tracks,
            intent.track_count,
            intent.energy_curve
        )
        
        # Assign transitions based on energy changes
        if interpreter and intent.advanced_transitions:
            track_data = [
                {
                    "artist": t.artist,
                    "title": t.title,
                    "energy": t.energy
                }
                for t in ordered_tracks
            ]
            
            try:
                transitions = await interpreter.suggest_transitions(
                    track_data,
                    intent.energy_curve
                )
                
                for i, track in enumerate(ordered_tracks):
                    if i < len(transitions):
                        track.transition_type = transitions[i].type
                        track.transition_bars = transitions[i].bars
                        track.transition_direction = transitions[i].direction
            except Exception as e:
                print(f"Failed to get transition suggestions: {e}")
                # Fall back to rule-based transitions
                self._assign_transitions_rule_based(ordered_tracks)
        else:
            # Use rule-based transitions
            self._assign_transitions_rule_based(ordered_tracks)
        
        return ordered_tracks
    
    async def _search_tracks(self, intent: MixIntent) -> list[dict]:
        """Search Spotify for tracks matching the intent.
        
        Priority order:
        1. Search for specific tracks suggested by GPT (most accurate)
        2. Search by specific artists mentioned
        3. Fall back to genre/mood searches
        """
        
        all_tracks = []
        found_suggested_ids = set()  # Track which suggested songs we found
        
        # PRIORITY 1: Search for AI-suggested specific tracks
        if intent.suggested_tracks:
            print(f"Searching for {len(intent.suggested_tracks)} AI-suggested tracks...")
            for suggested in intent.suggested_tracks:
                try:
                    # Search for exact artist + title match
                    query = f"track:{suggested.title} artist:{suggested.artist}"
                    results = await asyncio.to_thread(
                        self.sp.search,
                        q=query,
                        type="track",
                        limit=5
                    )
                    
                    if results and "tracks" in results and results["tracks"]["items"]:
                        # Find best match
                        for track in results["tracks"]["items"]:
                            track_name = track.get("name", "").lower()
                            artists = [a["name"].lower() for a in track.get("artists", [])]
                            
                            # Check if it's a good match
                            if (suggested.title.lower() in track_name or 
                                track_name in suggested.title.lower()):
                                if any(suggested.artist.lower() in artist or 
                                      artist in suggested.artist.lower() 
                                      for artist in artists):
                                    if track["id"] not in found_suggested_ids:
                                        print(f"  ✓ Found: {suggested.artist} - {suggested.title}")
                                        all_tracks.append(track)
                                        found_suggested_ids.add(track["id"])
                                        break
                        else:
                            # No exact match, take first result if reasonable
                            first = results["tracks"]["items"][0]
                            if first["id"] not in found_suggested_ids:
                                print(f"  ~ Partial: {first['artists'][0]['name']} - {first['name']} (wanted: {suggested.artist} - {suggested.title})")
                                all_tracks.append(first)
                                found_suggested_ids.add(first["id"])
                    else:
                        print(f"  ✗ Not found: {suggested.artist} - {suggested.title}")
                except Exception as e:
                    print(f"  ✗ Error searching for {suggested.title}: {e}")
            
            print(f"Found {len(all_tracks)} of {len(intent.suggested_tracks)} suggested tracks")
        
        # If we have enough suggested tracks, we might be done
        if len(all_tracks) >= intent.track_count:
            print("Using AI-suggested tracks only (enough found)")
            return all_tracks
        
        # PRIORITY 2: Search by specific artists
        for artist in intent.artists_preference[:5]:
            try:
                query = f"artist:{artist}"
                results = await asyncio.to_thread(
                    self.sp.search,
                    q=query,
                    type="track",
                    limit=20
                )
                
                if results and "tracks" in results:
                    for track in results["tracks"]["items"]:
                        if track["id"] not in found_suggested_ids:
                            all_tracks.append(track)
                            found_suggested_ids.add(track["id"])
            except Exception as e:
                print(f"Artist search failed for '{artist}': {e}")
        
        # PRIORITY 3: Genre and mood-based searches (fallback)
        if len(all_tracks) < intent.track_count * 2:
            queries = []
            
            # Search by genre
            for genre in intent.genres[:3]:
                queries.append(f"genre:{genre}")
            
            # Add mood-based queries
            mood_queries = {
                "energetic": "upbeat party",
                "chill": "chill relaxing",
                "dark": "dark intense",
                "uplifting": "uplifting euphoric",
                "party": "party dance hit",
                "romantic": "romantic love",
                "aggressive": "intense aggressive",
                "groovy": "groove funky",
                "nostalgic": "throwback classic"
            }
            if intent.mood in mood_queries:
                queries.append(mood_queries[intent.mood])
            
            # Add era-based search
            era_years = {
                "2020s": "year:2020-2025",
                "2010s": "year:2010-2019",
                "2000s": "year:2000-2009",
                "90s": "year:1990-1999",
                "80s": "year:1980-1989",
            }
            if intent.era in era_years:
                for genre in intent.genres[:2]:
                    queries.append(f"{genre} {era_years[intent.era]}")
            
            # Execute searches
            for query in queries:
                try:
                    results = await asyncio.to_thread(
                        self.sp.search,
                        q=query,
                        type="track",
                        limit=30
                    )
                    
                    if results and "tracks" in results:
                        for track in results["tracks"]["items"]:
                            if track["id"] not in found_suggested_ids:
                                all_tracks.append(track)
                                found_suggested_ids.add(track["id"])
                except Exception as e:
                    print(f"Search failed for '{query}': {e}")
        
        print(f"Total unique tracks found: {len(all_tracks)}")
        return all_tracks
    
    async def _get_audio_features(self, tracks: list[dict]) -> list[PlaylistTrack]:
        """Get audio features for tracks from Spotify.
        
        NOTE: As of Nov 2024, Spotify's audio-features endpoint returns 403 for
        client credentials. We now create tracks with estimated values based on
        track metadata (popularity, genres inferred from search).
        """
        
        track_ids = [t["id"] for t in tracks]
        
        # Try to get audio features (may fail with 403)
        all_features = []
        features_available = False
        
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i+100]
            try:
                features = await asyncio.to_thread(
                    self.sp.audio_features,
                    batch
                )
                if features and any(f is not None for f in features):
                    all_features.extend(features or [])
                    features_available = True
                else:
                    all_features.extend([None] * len(batch))
            except Exception as e:
                logging.info(f"Audio features unavailable (expected - API deprecated): {e}")
                all_features.extend([None] * len(batch))
        
        # Combine track info with features (or estimated values)
        result = []
        for idx, (track, features) in enumerate(zip(tracks, all_features)):
            # Get artist names
            artists = ", ".join([a["name"] for a in track.get("artists", [])])
            
            if features and features_available:
                # Use real audio features
                camelot_key = get_camelot_key(
                    features.get("key", 0),
                    features.get("mode", 1)
                )
                bpm = features.get("tempo", 120)
                energy = features.get("energy", 0.5)
                danceability = features.get("danceability", 0.5)
                valence = features.get("valence", 0.5)
                acousticness = features.get("acousticness", 0.0)
                instrumentalness = features.get("instrumentalness", 0.0)
            else:
                # Estimate values from track metadata
                # Use popularity as a rough proxy for energy/danceability
                popularity = track.get("popularity", 50)
                
                # Estimate energy: popular tracks tend to be more energetic
                energy = min(0.9, 0.3 + (popularity / 100) * 0.5 + (idx % 5) * 0.05)
                danceability = min(0.9, 0.4 + (popularity / 100) * 0.4)
                valence = 0.5 + (popularity / 200)
                acousticness = 0.1
                instrumentalness = 0.1
                
                # Estimate BPM based on common genre ranges (default to 120)
                bpm = 120.0
                
                # Assign a pseudo-random but consistent key based on track ID
                key_num = (hash(track["id"]) % 12) + 1
                key_mode = 'A' if hash(track["id"]) % 2 == 0 else 'B'
                camelot_key = f"{key_num}{key_mode}"

            result.append(PlaylistTrack(
                spotify_id=track["id"],
                title=track.get("name", "Unknown"),
                artist=artists,
                album=track.get("album", {}).get("name", "Unknown"),
                duration_ms=track.get("duration_ms", 0),
                bpm=bpm,
                key=camelot_key,
                energy=energy,
                danceability=danceability,
                valence=valence,
                acousticness=acousticness,
                instrumentalness=instrumentalness,
                popularity=track.get("popularity", 50),
                preview_url=track.get("preview_url")
            ))
        
        return result
    
    def _order_harmonically(
        self,
        tracks: list[PlaylistTrack],
        count: int,
        energy_curve: str
    ) -> list[PlaylistTrack]:
        """
        Order tracks for harmonic mixing and energy flow
        """
        if len(tracks) <= 1:
            return tracks[:count]
        
        # Sort by energy based on curve
        if energy_curve == "build-peak-cooldown":
            # Start medium, build to peak at 2/3, then cool down
            low_energy = sorted([t for t in tracks if t.energy < 0.4], key=lambda x: x.energy)
            mid_energy = sorted([t for t in tracks if 0.4 <= t.energy < 0.7], key=lambda x: x.energy)
            high_energy = sorted([t for t in tracks if t.energy >= 0.7], key=lambda x: -x.energy)
            
            # Arrange: mid → high → high → mid → low
            peak_position = int(count * 0.67)
            
            ordered = []
            ordered.extend(mid_energy[:peak_position // 2])
            ordered.extend(high_energy)
            ordered.extend(mid_energy[peak_position // 2:])
            ordered.extend(low_energy)
            
        elif energy_curve == "build-only":
            ordered = sorted(tracks, key=lambda x: x.energy)
        elif energy_curve == "cooldown-only":
            ordered = sorted(tracks, key=lambda x: -x.energy)
        else:  # steady
            # Mix of energies, grouped by similarity
            ordered = sorted(tracks, key=lambda x: (round(x.energy * 3) / 3, x.danceability))
        
        # Now apply harmonic ordering within energy groups
        result = []
        remaining = ordered[:count * 2]  # Get extra candidates
        
        if not remaining:
            return tracks[:count]
        
        # Start with first track
        current = remaining.pop(0)
        result.append(current)
        
        while len(result) < count and remaining:
            # Find most compatible next track
            best_track = None
            best_score = float('inf')
            
            for track in remaining:
                # Score based on harmonic compatibility and energy similarity
                key_dist = camelot_distance(current.key, track.key)
                energy_diff = abs(current.energy - track.energy)
                
                # Prefer harmonically compatible tracks
                score = key_dist * 2 + energy_diff
                
                if score < best_score:
                    best_score = score
                    best_track = track
            
            if best_track:
                remaining.remove(best_track)
                result.append(best_track)
                current = best_track
            else:
                break
        
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
