"""
Prompt Interpreter - GPT-4o powered natural language understanding
"""

import json
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel


class TransitionSuggestion(BaseModel):
    """Per-track transition suggestion from GPT"""
    type: str  # "crossfade", "echo_out", "filter_sweep", "backspin"
    bars: int = 8
    direction: Optional[str] = None  # for filter_sweep: "lowpass" or "highpass"


class MixIntent(BaseModel):
    """Extracted intent from user prompt"""
    genres: list[str]
    mood: str
    energy_curve: str  # "steady", "build-peak-cooldown", "build-only", "cooldown-only"
    era: str  # "2020s", "2010s", "2000s", "90s", "80s", "classic", "any"
    artists_preference: list[str]
    duration_minutes: int
    track_count: int
    advanced_transitions: bool  # Whether to use varied transition types
    transition_suggestions: list[TransitionSuggestion]
    additional_context: str  # Any other relevant extracted info



class PromptInterpreter:
    """
    Interprets natural language prompts using GPT-4o
    """
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Use gpt-4o as the latest stable model
    
    async def interpret(
        self,
        prompt: str,
        trends_context: Optional[str] = None
    ) -> MixIntent:
        """
        Interpret a user prompt and extract mix parameters
        """
        
        system_prompt = self._build_system_prompt(trends_context)
        
        # 🚀 OPENAI PROMPT: Log the full prompt being sent to OpenAI
        print("🚀 OPENAI PROMPT:")
        print(f"System: {system_prompt}")
        print(f"User: {prompt}")
        print("🚀 END OPENAI PROMPT")
        
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
        
        current_year = datetime.now().year
        
        prompt = f"""You are an expert DJ assistant. Your job is to interpret user requests for DJ mixes and extract structured parameters for Spotify search.

Given a user's request for a DJ mix, extract the following information and return as JSON:

{{
  "genres": ["list", "of", "genres"],  // Main genres/styles
  "mood": "energetic|chill|dark|uplifting|nostalgic|party|romantic|aggressive|groovy",
  "energy_curve": "steady|build-peak-cooldown|build-only|cooldown-only",
  "era": "2020s|2010s|2000s|90s|80s|classic|any",
  "artists_preference": ["specific", "artists", "mentioned"],
  "duration_minutes": 30,  // Default 30 if not specified
  "track_count": 8,  // Estimate based on duration (~3-4 min per track)
  "advanced_transitions": true,  // Whether to vary transition types
  "transition_suggestions": [
    {{"type": "crossfade", "bars": 8}},
    {{"type": "echo_out", "bars": 4}},
    {{"type": "filter_sweep", "bars": 8, "direction": "lowpass"}},
    {{"type": "backspin", "bars": 2}}
  ],
  "additional_context": "any other relevant notes"
}}

Focus on extracting the user's intent for Spotify search. Don't suggest specific tracks - let Spotify handle that based on these parameters.

TRANSITION TYPES:
- "crossfade": Standard DJ crossfade (default, use for smooth transitions)
- "echo_out": Echo/reverb tail on outgoing track (use for dramatic drops)
- "filter_sweep": Progressive lowpass/highpass filter (use for builds)
- "backspin": Vinyl backspin effect (use sparingly for surprise/impact)

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

Current year: {current_year}. Use this for era calculations.

{f"CURRENT TRENDS (use for context):{chr(10)}{trends_context}" if trends_context else ""}

Always return valid JSON."""

        return prompt
    
    def _process_result(self, result: dict) -> MixIntent:
        """Process and validate the GPT response"""
        
        # Ensure required fields
        genres = result.get("genres", ["pop"])
        if not genres:
            genres = ["pop"]
        
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
            track_count=track_count,
            advanced_transitions=result.get("advanced_transitions", True),
            transition_suggestions=transition_suggestions,
            additional_context=result.get("additional_context", "")
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
