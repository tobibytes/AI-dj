"""
Prompt Interpreter - GPT-5.2 powered natural language understanding
"""

import json
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel


class TransitionSuggestion(BaseModel):
    """Per-track transition suggestion from GPT"""
    type: str  # "crossfade", "echo_out", "filter_sweep", "backspin"
    bars: int = 8
    direction: Optional[str] = None  # for filter_sweep: "lowpass" or "highpass"


class SuggestedTrack(BaseModel):
    """A specific track suggested by GPT"""
    title: str
    artist: str
    reason: str  # Why this track fits the vibe


class MixIntent(BaseModel):
    """Extracted intent from user prompt"""
    genres: list[str]
    mood: str
    energy_curve: str  # "steady", "build-peak-cooldown", "build-only", "cooldown-only"
    era: str  # "2020s", "2010s", "2000s", "90s", "80s", "classic", "any"
    artists_preference: list[str]
    duration_minutes: int
    target_bpm: float
    track_count: int
    advanced_transitions: bool  # Whether to use varied transition types
    transition_suggestions: list[TransitionSuggestion]
    additional_context: str  # Any other relevant extracted info
    suggested_tracks: list[SuggestedTrack] = []  # Specific tracks AI suggests


# Genre to typical BPM mapping
GENRE_BPM_NORMS = {
    "afrobeats": 100,
    "afrobeat": 100,
    "amapiano": 113,
    "house": 128,
    "deep house": 122,
    "tech house": 126,
    "techno": 135,
    "hip-hop": 90,
    "hip hop": 90,
    "rap": 90,
    "trap": 140,
    "r&b": 85,
    "rnb": 85,
    "dancehall": 95,
    "drill": 140,
    "uk drill": 140,
    "reggaeton": 95,
    "latin": 100,
    "edm": 128,
    "dubstep": 140,
    "drum and bass": 174,
    "dnb": 174,
    "jungle": 160,
    "garage": 130,
    "uk garage": 130,
    "grime": 140,
    "pop": 120,
    "disco": 120,
    "funk": 110,
    "soul": 95,
    "jazz": 120,
    "reggae": 80,
    "rock": 120,
    "indie": 120,
    "electronic": 128,
    "trance": 138,
    "progressive house": 126,
    "minimal": 125,
    "lo-fi": 85,
    "lofi": 85,
    "chill": 90,
    "ambient": 80,
}


class PromptInterpreter:
    """
    Interprets natural language prompts using GPT-5.2
    """
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Use gpt-4o as the latest stable model
        # Note: Update to "gpt-5.2" when available
    
    async def interpret(
        self,
        prompt: str,
        trends_context: Optional[str] = None
    ) -> MixIntent:
        """
        Interpret a user prompt and extract mix parameters
        """
        
        system_prompt = self._build_system_prompt(trends_context)
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Post-process and validate
        intent = self._process_result(result)
        
        return intent
    
    def _build_system_prompt(self, trends_context: Optional[str] = None) -> str:
        """Build the system prompt for GPT"""
        
        genre_bpm_info = "\n".join([f"- {genre}: {bpm} BPM" for genre, bpm in GENRE_BPM_NORMS.items()])
        
        prompt = f"""You are an expert DJ assistant with encyclopedic knowledge of music. Your job is to interpret user requests for DJ mixes and extract structured parameters, INCLUDING suggesting specific real songs that fit the vibe.

Given a user's request for a DJ mix, extract the following information and return as JSON:

{{
  "genres": ["list", "of", "genres"],  // Main genres/styles
  "mood": "energetic|chill|dark|uplifting|nostalgic|party|romantic|aggressive|groovy",
  "energy_curve": "steady|build-peak-cooldown|build-only|cooldown-only",
  "era": "2020s|2010s|2000s|90s|80s|classic|any",
  "artists_preference": ["specific", "artists", "mentioned"],
  "duration_minutes": 30,  // Default 30 if not specified
  "target_bpm": 100,  // Based on genre norms below
  "track_count": 8,  // Estimate based on duration (~3-4 min per track)
  "advanced_transitions": true,  // Whether to vary transition types
  "transition_suggestions": [
    {{"type": "crossfade", "bars": 8}},
    {{"type": "echo_out", "bars": 4}},
    {{"type": "filter_sweep", "bars": 8, "direction": "lowpass"}},
    {{"type": "backspin", "bars": 2}}
  ],
  "suggested_tracks": [
    {{"title": "Exact Song Name", "artist": "Artist Name", "reason": "Why this fits"}},
    {{"title": "Another Song", "artist": "Another Artist", "reason": "Perfect for the vibe because..."}}
  ],
  "additional_context": "any other relevant notes"
}}

CRITICAL: The "suggested_tracks" array is VERY IMPORTANT. You must suggest REAL, EXISTING songs that:
1. Match the user's described mood/vibe
2. Work well together in a DJ mix (similar BPM, compatible keys)
3. Are actually available on Spotify
4. Suggest 2x the track_count to give options (e.g., if track_count is 8, suggest 16 tracks)

Be specific! Don't suggest generic or made-up songs. Suggest real tracks from real artists that fit the prompt.

GENRE BPM NORMS (use these to set target_bpm):
{genre_bpm_info}

TRANSITION TYPES:
- "crossfade": Standard DJ crossfade (default, use for smooth transitions)
- "echo_out": Echo/reverb tail on outgoing track (use for dramatic drops)
- "filter_sweep": Progressive lowpass/highpass filter (use for builds)
- "backspin": Vinyl backspin effect (use sparingly for surprise/impact)

TRANSITION LOGIC:
- Use "crossfade" for most transitions (default)
- Use "echo_out" when energy is about to DROP significantly
- Use "filter_sweep" when energy is BUILDING UP
- Use "backspin" occasionally for dramatic effect (max 1-2 per set)
- Suggest 8 bars for normal transitions, 4 bars for quick cuts, 16 bars for long blends

DURATION INTERPRETATION:
- "quick mix" → 15 minutes
- Default → 30 minutes
- "long set" → 45-60 minutes
- "party set" or "full set" → 60+ minutes
- If user specifies time, use that

ENERGY CURVES:
- "steady": Maintain consistent energy throughout
- "build-peak-cooldown": Start medium, build to peak around 2/3, then cool down
- "build-only": Start low, continuously build energy
- "cooldown-only": Start high, gradually reduce energy

{f"CURRENT TRENDS (use for context):{chr(10)}{trends_context}" if trends_context else ""}

Always return valid JSON. Be creative but practical. Most importantly, suggest REAL songs that actually exist!"""

        return prompt
    
    def _process_result(self, result: dict) -> MixIntent:
        """Process and validate the GPT response"""
        
        # Ensure required fields
        genres = result.get("genres", ["pop"])
        if not genres:
            genres = ["pop"]
        
        # Calculate target BPM if not provided or seems off
        target_bpm = result.get("target_bpm", 0)
        if target_bpm <= 0:
            # Average BPM based on genres
            bpms = [GENRE_BPM_NORMS.get(g.lower(), 120) for g in genres]
            target_bpm = sum(bpms) / len(bpms)
        
        # Ensure reasonable duration
        duration = result.get("duration_minutes", 30)
        duration = max(10, min(120, duration))  # 10 min to 2 hours
        
        # Calculate track count based on duration
        track_count = result.get("track_count", 0)
        if track_count <= 0:
            # Assume ~3.5 minutes per track average
            track_count = max(4, int(duration / 3.5))
        
        # Process transitions
        transition_suggestions = []
        raw_transitions = result.get("transition_suggestions", [])
        
        for i in range(track_count):
            if i < len(raw_transitions):
                t = raw_transitions[i]
                transition_suggestions.append(TransitionSuggestion(
                    type=t.get("type", "crossfade"),
                    bars=t.get("bars", 8),
                    direction=t.get("direction")
                ))
            else:
                # Default to crossfade
                transition_suggestions.append(TransitionSuggestion(
                    type="crossfade",
                    bars=8
                ))
        
        return MixIntent(
            genres=genres,
            mood=result.get("mood", "energetic"),
            energy_curve=result.get("energy_curve", "build-peak-cooldown"),
            era=result.get("era", "any"),
            artists_preference=result.get("artists_preference", []),
            duration_minutes=duration,
            target_bpm=round(target_bpm, 1),
            track_count=track_count,
            advanced_transitions=result.get("advanced_transitions", True),
            transition_suggestions=transition_suggestions,
            additional_context=result.get("additional_context", ""),
            suggested_tracks=[
                SuggestedTrack(
                    title=t.get("title", ""),
                    artist=t.get("artist", ""),
                    reason=t.get("reason", "")
                )
                for t in result.get("suggested_tracks", [])
                if t.get("title") and t.get("artist")
            ]
        )
    
    async def suggest_transitions(
        self,
        tracks: list[dict],  # List of track info with energy levels
        energy_curve: str
    ) -> list[TransitionSuggestion]:
        """
        Suggest transition types for a list of tracks based on their energy levels
        """
        
        system_prompt = """You are an expert DJ. Given a list of tracks with their energy levels (0-1), 
suggest the best transition type for each track-to-track transition.

Return a JSON object with a "transitions" array:
{
  "transitions": [
    {"type": "crossfade", "bars": 8},
    {"type": "echo_out", "bars": 4},
    ...
  ]
}

RULES:
- Use "crossfade" (8 bars) for smooth, similar-energy transitions
- Use "echo_out" (4 bars) when energy drops significantly (>0.2 decrease)
- Use "filter_sweep" (8 bars, direction based on energy change) for builds
- Use "backspin" (2 bars) sparingly for dramatic moments (max 1-2 per set)
- Match transition intensity to energy change magnitude"""

        track_info = "\n".join([
            f"Track {i+1}: {t.get('artist', 'Unknown')} - {t.get('title', 'Unknown')} (energy: {t.get('energy', 0.5):.2f})"
            for i, t in enumerate(tracks)
        ])
        
        user_prompt = f"Energy curve: {energy_curve}\n\nTracks:\n{track_info}\n\nSuggest transitions between each pair of tracks."
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Handle both array and object response formats
        transitions = result.get("transitions", [])
        if not transitions and isinstance(result, list):
            transitions = result
        
        return [
            TransitionSuggestion(
                type=t.get("type", "crossfade"),
                bars=t.get("bars", 8),
                direction=t.get("direction")
            )
            for t in transitions
        ]
