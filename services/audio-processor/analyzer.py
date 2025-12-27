"""
Audio Analyzer - BPM detection, key detection, beat grid, phrase boundaries, and song structure
"""

import numpy as np
import librosa
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SongSection:
    """Represents a section of a song (intro, verse, chorus, etc.)"""
    name: str  # "intro", "verse", "chorus", "drop", "breakdown", "outro"
    start: float  # Start time in seconds
    end: float  # End time in seconds
    energy: float  # Average energy of this section (0-1)
    is_vocal: bool = False  # Whether vocals are likely present


@dataclass
class AnalysisResult:
    """Result of audio analysis"""
    bpm: float
    key: str
    energy: float
    beat_positions: List[float]
    phrase_boundaries: List[float]
    intro_end: float
    outro_start: float
    duration: float
    # New: song structure for smart transitions
    sections: List[SongSection] = field(default_factory=list)
    best_loop_start: float = 0.0  # Best point to start playing
    best_loop_end: float = 0.0  # Best point to transition out
    drop_time: Optional[float] = None  # Main drop/chorus hit


class AudioAnalyzer:
    """
    Analyzes audio files for DJ mixing metadata
    """
    
    # Key detection using chroma features
    # Maps pitch class to key name
    KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    
    # Camelot wheel mapping for harmonic mixing
    CAMELOT_WHEEL = {
        'C': '8B', 'Am': '8A',
        'G': '9B', 'Em': '9A',
        'D': '10B', 'Bm': '10A',
        'A': '11B', 'F#m': '11A',
        'E': '12B', 'C#m': '12A',
        'B': '1B', 'G#m': '1A',
        'F#': '2B', 'D#m': '2A',
        'Db': '3B', 'Bbm': '3A',
        'Ab': '4B', 'Fm': '4A',
        'Eb': '5B', 'Cm': '5A',
        'Bb': '6B', 'Gm': '6A',
        'F': '7B', 'Dm': '7A',
    }
    
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        # Target section length for DJ mix (60-90 seconds per track)
        self.min_section_length = 45  # seconds
        self.max_section_length = 90  # seconds
    
    def analyze(self, file_path: str) -> AnalysisResult:
        """
        Perform full analysis on an audio file
        """
        # Load audio file
        y, sr = librosa.load(file_path, sr=self.sample_rate)
        duration = librosa.get_duration(y=y, sr=sr)
        
        # Detect BPM and beat positions
        bpm, beat_positions = self._detect_bpm_and_beats(y, sr)
        
        # Detect musical key
        key = self._detect_key(y, sr)
        
        # Calculate overall energy
        energy = self._calculate_energy(y)
        
        # Detect phrase boundaries (typically 8 or 16 bar segments)
        phrase_boundaries = self._detect_phrase_boundaries(y, sr, beat_positions, bpm)
        
        # Detect intro and outro points
        intro_end, outro_start = self._detect_intro_outro(y, sr, beat_positions, bpm)
        
        # NEW: Detect song structure sections
        sections = self._detect_song_structure(y, sr, beat_positions, bpm, phrase_boundaries)
        
        # NEW: Find best loop points for DJ mix (the "money section")
        best_start, best_end, drop_time = self._find_best_loop(
            y, sr, sections, beat_positions, bpm, duration
        )
        
        return AnalysisResult(
            bpm=round(bpm, 2),
            key=key,
            energy=round(energy, 3),
            beat_positions=[round(b, 3) for b in beat_positions.tolist()],
            phrase_boundaries=[round(p, 3) for p in phrase_boundaries],
            intro_end=round(intro_end, 3),
            outro_start=round(outro_start, 3),
            duration=round(duration, 3),
            sections=sections,
            best_loop_start=round(best_start, 3),
            best_loop_end=round(best_end, 3),
            drop_time=round(drop_time, 3) if drop_time else None
        )
    
    def _detect_bpm_and_beats(self, y: np.ndarray, sr: int) -> tuple[float, np.ndarray]:
        """
        Detect BPM and beat positions using librosa
        """
        # Get tempo and beat frames
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        
        # Convert frames to time
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        # Tempo is an array in newer librosa, get scalar
        bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])
        
        return bpm, beat_times
    
    def _detect_key(self, y: np.ndarray, sr: int) -> str:
        """
        Detect musical key using chroma features
        Returns key in Camelot notation (e.g., "8B" for C major)
        """
        # Extract chroma features
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        
        # Average chroma over time
        chroma_avg = np.mean(chroma, axis=1)
        
        # Find dominant pitch class
        dominant_pitch = np.argmax(chroma_avg)
        key_name = self.KEY_NAMES[dominant_pitch]
        
        # Determine if major or minor using mode detection
        # Simple heuristic: check relative minor/major strength
        minor_third_idx = (dominant_pitch + 3) % 12
        major_third_idx = (dominant_pitch + 4) % 12
        
        is_minor = chroma_avg[minor_third_idx] > chroma_avg[major_third_idx]
        
        if is_minor:
            # Convert to relative minor
            minor_key = self.KEY_NAMES[(dominant_pitch + 9) % 12] + 'm'
            camelot = self.CAMELOT_WHEEL.get(minor_key, '1A')
        else:
            camelot = self.CAMELOT_WHEEL.get(key_name, '1B')
        
        return camelot
    
    def _calculate_energy(self, y: np.ndarray) -> float:
        """
        Calculate overall energy/intensity of the track
        Returns value between 0 and 1
        """
        # RMS energy
        rms = librosa.feature.rms(y=y)[0]
        
        # Normalize to 0-1 range
        energy = float(np.mean(rms))
        
        # Scale to more useful range (typical values are quite low)
        energy = min(1.0, energy * 10)
        
        return energy
    
    def _detect_phrase_boundaries(
        self,
        y: np.ndarray,
        sr: int,
        beat_times: np.ndarray,
        bpm: float
    ) -> List[float]:
        """
        Detect phrase boundaries (typically 8 or 16 bar segments)
        """
        if len(beat_times) < 32:  # Need at least 8 bars (32 beats)
            return [0.0]
        
        # Calculate spectral flux for change detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        # Find significant changes in energy/texture
        # Look for changes aligned to 8-bar (32 beat) boundaries
        beats_per_phrase = 32  # 8 bars * 4 beats
        
        phrase_boundaries = [0.0]  # Start with beginning
        
        for i in range(beats_per_phrase, len(beat_times), beats_per_phrase):
            if i < len(beat_times):
                phrase_boundaries.append(float(beat_times[i]))
        
        return phrase_boundaries
    
    def _detect_intro_outro(
        self,
        y: np.ndarray,
        sr: int,
        beat_times: np.ndarray,
        bpm: float
    ) -> tuple[float, float]:
        """
        Detect where intro ends and outro begins
        Based on energy levels and onset strength
        """
        if len(beat_times) < 16:  # Need reasonable number of beats
            duration = librosa.get_duration(y=y, sr=sr)
            return duration * 0.1, duration * 0.9
        
        # Calculate onset strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        # Calculate frame times
        frame_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr)
        
        # Compute moving average of onset strength
        window_size = int(sr * 4 / 512)  # ~4 second window
        if window_size < 1:
            window_size = 1
        
        onset_smooth = np.convolve(onset_env, np.ones(window_size)/window_size, mode='same')
        
        # Find energy threshold (e.g., 40% of max)
        threshold = np.max(onset_smooth) * 0.4
        
        # Find intro end (first time energy crosses threshold going up)
        above_threshold = onset_smooth > threshold
        intro_end_frame = 0
        for i in range(len(above_threshold)):
            if above_threshold[i]:
                intro_end_frame = max(0, i - window_size // 2)
                break
        
        # Snap to nearest beat
        intro_end_time = frame_times[intro_end_frame] if intro_end_frame < len(frame_times) else 0
        intro_end = self._snap_to_beat(intro_end_time, beat_times)
        
        # Find outro start (last time energy crosses threshold going down)
        outro_start_frame = len(above_threshold) - 1
        for i in range(len(above_threshold) - 1, -1, -1):
            if above_threshold[i]:
                outro_start_frame = min(len(frame_times) - 1, i + window_size // 2)
                break
        
        outro_start_time = frame_times[outro_start_frame] if outro_start_frame < len(frame_times) else frame_times[-1]
        outro_start = self._snap_to_beat(outro_start_time, beat_times)
        
        # Ensure reasonable values
        duration = librosa.get_duration(y=y, sr=sr)
        intro_end = max(beat_times[4] if len(beat_times) > 4 else duration * 0.05, intro_end)  # At least 1 bar
        outro_start = min(beat_times[-8] if len(beat_times) > 8 else duration * 0.95, outro_start)  # At least 2 bars from end
        
        return intro_end, outro_start
    
    def _detect_song_structure(
        self,
        y: np.ndarray,
        sr: int,
        beat_times: np.ndarray,
        bpm: float,
        phrase_boundaries: List[float]
    ) -> List[SongSection]:
        """
        Detect song structure by analyzing energy changes at phrase boundaries.
        Identifies intro, verse, chorus/drop, breakdown, and outro sections.
        """
        sections = []
        duration = librosa.get_duration(y=y, sr=sr)
        
        if len(phrase_boundaries) < 2:
            # Not enough structure detected, return single section
            return [SongSection(
                name="main",
                start=0.0,
                end=duration,
                energy=self._calculate_energy(y),
                is_vocal=False
            )]
        
        # Calculate energy for each phrase
        hop_length = 512
        frame_times = librosa.frames_to_time(np.arange(len(y) // hop_length), sr=sr, hop_length=hop_length)
        
        # Get RMS energy per frame
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        
        # Get spectral centroid (brightness - higher in choruses)
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
        
        # Normalize
        rms_norm = (rms - rms.min()) / (rms.max() - rms.min() + 1e-6)
        centroid_norm = (spectral_centroid - spectral_centroid.min()) / (spectral_centroid.max() - spectral_centroid.min() + 1e-6)
        
        # Combined energy metric
        combined_energy = 0.6 * rms_norm + 0.4 * centroid_norm
        
        # Analyze each phrase
        for i in range(len(phrase_boundaries)):
            start = phrase_boundaries[i]
            end = phrase_boundaries[i + 1] if i + 1 < len(phrase_boundaries) else duration
            
            # Find frames in this range
            start_frame = np.searchsorted(frame_times, start)
            end_frame = np.searchsorted(frame_times, end)
            
            if end_frame <= start_frame:
                continue
            
            # Calculate average energy for this section
            section_energy = float(np.mean(combined_energy[start_frame:end_frame]))
            
            # Determine section type based on position and energy
            relative_pos = start / duration
            
            if relative_pos < 0.1:
                section_type = "intro"
            elif relative_pos > 0.85:
                section_type = "outro"
            elif section_energy > 0.7:
                section_type = "chorus"  # High energy = chorus/drop
            elif section_energy > 0.5:
                section_type = "verse"
            else:
                section_type = "breakdown"
            
            sections.append(SongSection(
                name=section_type,
                start=float(start),
                end=float(end),
                energy=section_energy,
                is_vocal=(section_type in ["verse", "chorus"])
            ))
        
        return sections
    
    def _find_best_loop(
        self,
        y: np.ndarray,
        sr: int,
        sections: List[SongSection],
        beat_times: np.ndarray,
        bpm: float,
        duration: float
    ) -> tuple[float, float, Optional[float]]:
        """
        Find the best section to play for DJ mixing.
        Returns (start_time, end_time, drop_time)
        
        Strategy:
        1. Find the "drop" - the moment of biggest energy increase
        2. If no clear drop, use common song structure (first chorus ~45-75s)
        3. Play 60-90 seconds starting from before the drop
        """
        # Calculate energy over time with smoothing
        hop_length = 512
        rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
        frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
        
        # Smooth the energy curve
        window = min(50, len(rms) // 10)  # ~1 second window
        if window < 3:
            window = 3
        rms_smooth = np.convolve(rms, np.ones(window)/window, mode='same')
        
        # Find the "drop" - biggest energy increase over ~2 seconds
        drop_window = int(sr * 2 / hop_length)  # 2 second window
        energy_increases = []
        
        for i in range(drop_window, len(rms_smooth) - drop_window):
            before = np.mean(rms_smooth[max(0, i-drop_window):i])
            after = np.mean(rms_smooth[i:min(len(rms_smooth), i+drop_window)])
            increase = after - before
            energy_increases.append((i, increase, frame_times[i]))
        
        # Find the biggest energy increase
        drop_time = None
        if energy_increases:
            # Sort by increase amount
            energy_increases.sort(key=lambda x: x[1], reverse=True)
            
            # The drop should be significant (at least 30% of max RMS)
            max_increase = energy_increases[0][1]
            
            if max_increase > 0.1 * np.max(rms_smooth):
                drop_time = energy_increases[0][2]
                print(f"Found drop at {drop_time:.1f}s (energy increase: {max_increase:.3f})")
        
        # Calculate timing
        seconds_per_beat = 60 / bpm
        seconds_per_bar = seconds_per_beat * 4
        
        if drop_time and drop_time > 10:  # Valid drop found
            # Start 8-16 bars before the drop for buildup
            buildup_bars = 8
            start_time = max(0, drop_time - (buildup_bars * seconds_per_bar))
        else:
            # FALLBACK: Use common song structure - be more conservative
            # Most songs have intro (0-30s), then main content
            # Start after intro but before first major section
            print(f"No clear drop found, using conservative song structure heuristic")
            
            if duration > 180:  # Song longer than 3 minutes
                # Start around 30-45 seconds (after intro, before first chorus)
                start_time = min(duration * 0.15, 45)
                drop_time = min(duration * 0.25, 75)  # Guess chorus around here
            elif duration > 120:  # Song 2-3 minutes
                start_time = min(duration * 0.2, 35)
                drop_time = min(duration * 0.3, 55)
            else:  # Shorter song
                start_time = max(duration * 0.1, 10)  # At least 10 seconds in
                drop_time = duration * 0.4
        
        # Ensure we don't start too late in the song
        max_start_time = duration - self.min_section_length
        start_time = min(start_time, max_start_time)
        start_time = max(start_time, 5)  # At least 5 seconds from start
        
        # Snap start to nearest beat
        start_time = self._snap_to_beat(start_time, beat_times)
        
        # Play for 60-90 seconds from start
        target_play_time = min(self.max_section_length, max(self.min_section_length, 75))
        end_time = min(duration - 5, start_time + target_play_time)
        
        # Make sure we don't go past the song
        if end_time > duration:
            end_time = duration
            start_time = max(0, end_time - target_play_time)
        
        # Snap end to nearest beat for clean transition
        end_time = self._snap_to_beat(end_time, beat_times)
        
        # Ensure minimum play time
        if end_time - start_time < 30:
            end_time = min(duration, start_time + 45)
        
        print(f"Selected section: {start_time:.1f}s - {end_time:.1f}s ({end_time - start_time:.1f}s), drop at {drop_time:.1f}s")
        
        return start_time, end_time, drop_time
    
    def _snap_to_beat(self, time: float, beat_times: np.ndarray) -> float:
        """
        Snap a time value to the nearest beat
        """
        if len(beat_times) == 0:
            return time
        
        idx = np.abs(beat_times - time).argmin()
        return float(beat_times[idx])


def get_camelot_compatible_keys(key: str) -> List[str]:
    """
    Get compatible keys for harmonic mixing using Camelot wheel
    Compatible keys: same key, +1, -1 on wheel, and parallel major/minor
    """
    if len(key) < 2:
        return [key]
    
    number = int(key[:-1])
    mode = key[-1]  # 'A' or 'B'
    
    compatible = [key]
    
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
