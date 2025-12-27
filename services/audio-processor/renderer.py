"""
Mix Renderer - Beat-aligned transitions with advanced effects
MVP: crossfade
Enhanced: echo_out, filter_sweep, backspin
"""

import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from pydub import AudioSegment
from pydub.effects import low_pass_filter, high_pass_filter
from scipy import signal


class MixRenderer:
    """
    Renders DJ mixes with beat-aligned transitions and effects
    """
    
    def __init__(self, temp_dir: str = "/tmp/audio"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Standard DJ mix parameters
        self.target_sample_rate = 44100
        self.target_channels = 2
    
    def render(
        self,
        tracks: list,  # List of TrackWithAnalysis
        target_bpm: float,
        output_format: str = "mp3",
        session_id: str = "",
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Render a complete mix from analyzed tracks
        
        Returns path to rendered mix file
        """
        if len(tracks) == 0:
            raise ValueError("No tracks provided")
        
        if len(tracks) == 1:
            # Just return the single track
            return tracks[0].file_path
        
        # Load and time-stretch all tracks to target BPM
        stretched_tracks = []
        for i, track in enumerate(tracks):
            if progress_callback:
                progress_callback(
                    "rendering",
                    int((i / len(tracks)) * 50),
                    f"Time-stretching: {track.artist} - {track.title}"
                )
            
            stretched_path = self._time_stretch(
                track.file_path,
                track.bpm,
                target_bpm,
                session_id,
                i
            )
            stretched_tracks.append({
                'path': stretched_path,
                'track': track,
                # Adjust timing based on stretch ratio
                'stretch_ratio': track.bpm / target_bpm,
            })
        
        # Build the mix with transitions
        if progress_callback:
            progress_callback("rendering", 50, "Mixing tracks...")
        
        mix = self._build_mix(stretched_tracks, progress_callback)
        
        # Export final mix
        output_filename = f"mix_{session_id or uuid.uuid4().hex[:8]}.{output_format}"
        output_path = self.temp_dir / output_filename
        
        if progress_callback:
            progress_callback("rendering", 90, "Exporting final mix...")
        
        if output_format == "mp3":
            mix.export(str(output_path), format="mp3", bitrate="320k")
        elif output_format == "wav":
            mix.export(str(output_path), format="wav")
        else:
            mix.export(str(output_path), format="mp3", bitrate="320k")
        
        # Clean up stretched files
        for st in stretched_tracks:
            if st['path'] != st['track'].file_path:
                try:
                    os.remove(st['path'])
                except:
                    pass
        
        if progress_callback:
            progress_callback("rendering", 100, "Mix complete!")
        
        return str(output_path)
    
    def _time_stretch(
        self,
        file_path: str,
        original_bpm: float,
        target_bpm: float,
        session_id: str,
        track_index: int
    ) -> str:
        """
        Time-stretch audio to target BPM using rubberband
        Only stretch if BPM difference is significant (>5% or >3 BPM)
        """
        bpm_diff = abs(original_bpm - target_bpm)
        bpm_ratio = min(original_bpm, target_bpm) / max(original_bpm, target_bpm)
        
        # Only stretch if difference is >5% AND >2 BPM (avoids micro-adjustments)
        if bpm_diff <= 2.0 or bpm_ratio > 0.95:
            print(f"Track {track_index+1}: Keeping original BPM {original_bpm:.1f} (close to target {target_bpm:.1f})")
            return file_path
        
        stretch_ratio = original_bpm / target_bpm
        
        # Limit extreme stretching (more than 20% change)
        if stretch_ratio < 0.8 or stretch_ratio > 1.25:
            print(f"Track {track_index+1}: BPM change too extreme ({original_bpm:.1f} -> {target_bpm:.1f}), keeping original")
            return file_path
        
        output_path = self.temp_dir / f"stretched_{session_id}_{track_index}.wav"
        
        # Use rubberband CLI for high-quality time stretching
        cmd = [
            "rubberband",
            "--tempo", str(stretch_ratio),
            "--pitch", "1.0",  # Preserve pitch
            "-2",  # High quality
            file_path,
            str(output_path)
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Track {track_index+1}: Stretched BPM {original_bpm:.1f} -> {target_bpm:.1f} (ratio: {stretch_ratio:.3f})")
            return str(output_path)
        except subprocess.CalledProcessError as e:
            # Fallback: return original (will be slightly off-tempo)
            print(f"Rubberband failed: {e}, using original tempo")
            return file_path
    
    def _build_mix(
        self,
        stretched_tracks: list,
        progress_callback: Optional[Callable] = None
    ) -> AudioSegment:
        """
        Build the final mix by applying transitions between tracks.
        Uses smart loop points to play only the best 45-90 seconds of each track.
        """
        # Load first track
        first_track_data = stretched_tracks[0]
        first_full = AudioSegment.from_file(first_track_data['path'])
        first_track = first_track_data['track']
        stretch_ratio = first_track_data['stretch_ratio']
        track_len = len(first_full)
        
        # Use smart loop points if available
        has_loop_points = (
            hasattr(first_track, 'best_loop_start') and 
            hasattr(first_track, 'best_loop_end') and
            first_track.best_loop_end > first_track.best_loop_start
        )
        
        if has_loop_points:
            start_ms = int(first_track.best_loop_start * 1000 * stretch_ratio)
            end_ms = int(first_track.best_loop_end * 1000 * stretch_ratio)
            # Ensure valid range
            start_ms = max(0, min(start_ms, track_len - 10000))
            end_ms = min(track_len, max(end_ms, start_ms + 30000))
            print(f"Track 1 ({first_track.title}): Playing {start_ms/1000:.1f}s - {end_ms/1000:.1f}s (best section)")
        else:
            # Fallback: play from 20% into song, for 60 seconds
            start_ms = min(int(track_len * 0.2), track_len - 60000)
            start_ms = max(0, start_ms)
            end_ms = min(track_len, start_ms + 60000)
            print(f"Track 1 ({first_track.title}): Playing {start_ms/1000:.1f}s - {end_ms/1000:.1f}s (fallback)")
        
        # Extract the section (ensure we have at least some audio)
        mix = first_full[start_ms:end_ms]
        if len(mix) < 5000:  # Less than 5 seconds
            print(f"Warning: Track 1 section too short ({len(mix)}ms), using full track")
            mix = first_full
        
        # Process remaining tracks with transitions
        for i in range(1, len(stretched_tracks)):
            current_data = stretched_tracks[i]
            current_track = current_data['track']
            transition = current_track.transition
            stretch_ratio = current_data['stretch_ratio']
            
            if progress_callback:
                progress = 50 + int((i / len(stretched_tracks)) * 40)
                progress_callback(
                    "rendering",
                    progress,
                    f"Transition {i}/{len(stretched_tracks)-1}: {current_track.artist} - {current_track.title}"
                )
            
            # Load incoming track (full)
            incoming_full = AudioSegment.from_file(current_data['path'])
            incoming_len = len(incoming_full)
            
            # Check if we have valid loop points
            has_loop_points = (
                hasattr(current_track, 'best_loop_start') and 
                hasattr(current_track, 'best_loop_end') and
                current_track.best_loop_end > current_track.best_loop_start
            )
            
            if has_loop_points:
                start_ms = int(current_track.best_loop_start * 1000 * stretch_ratio)
                end_ms = int(current_track.best_loop_end * 1000 * stretch_ratio)
                # Ensure valid range
                start_ms = max(0, min(start_ms, incoming_len - 10000))
                end_ms = min(incoming_len, max(end_ms, start_ms + 30000))
                print(f"Track {i+1} ({current_track.title}): Playing {start_ms/1000:.1f}s - {end_ms/1000:.1f}s (best section)")
            else:
                # Fallback: play from 20% into song, for 60 seconds
                start_ms = min(int(incoming_len * 0.2), incoming_len - 60000)
                start_ms = max(0, start_ms)
                end_ms = min(incoming_len, start_ms + 60000)
                print(f"Track {i+1} ({current_track.title}): Playing {start_ms/1000:.1f}s - {end_ms/1000:.1f}s (fallback)")
            
            incoming = incoming_full[start_ms:end_ms]
            if len(incoming) < 5000:  # Less than 5 seconds
                print(f"Warning: Track {i+1} section too short ({len(incoming)}ms), using full track")
                incoming = incoming_full
            
            # Calculate transition duration in ms
            bars = transition.bars if transition else 8
            beats = bars * 4
            transition_duration_ms = int(beats * 500)  # ~4 seconds for 8 bars at 120bpm
            
            # Adjust transition based on song structure if available
            if hasattr(current_track, 'sections') and current_track.sections:
                # Try to transition during a less critical section (not during chorus/drop)
                current_sections = current_track.sections
                mix_duration_so_far = len(mix) / 1000.0  # Convert to seconds
                
                # Find sections that would be playing during transition
                transition_start_time = mix_duration_so_far - (transition_duration_ms / 2000.0)  # Middle of transition
                transition_end_time = mix_duration_so_far + (transition_duration_ms / 2000.0)
                
                # Check if transition overlaps with high-energy sections
                overlaps_high_energy = any(
                    section.start <= transition_end_time and section.end >= transition_start_time
                    and (section.name in ['chorus', 'drop'] or section.energy > 0.7)
                    for section in current_sections
                )
                
                if overlaps_high_energy:
                    # Shorten transition to avoid cutting through important parts
                    transition_duration_ms = min(transition_duration_ms, 3000)  # Max 3 seconds
                    print(f"Shortened transition for {current_track.title} to avoid cutting through high-energy section")
            
            # Ensure transition duration is reasonable
            max_transition = min(len(mix) // 2, len(incoming) // 2, 8000)  # Max 8 seconds
            transition_duration_ms = min(transition_duration_ms, max_transition)
            transition_duration_ms = max(transition_duration_ms, 1000)  # Min 1 second
            
            # Apply transition based on type
            transition_type = transition.type if transition else "crossfade"
            
            if transition_type == "crossfade":
                mix = self._apply_crossfade(mix, incoming, transition_duration_ms)
            elif transition_type == "echo_out":
                mix = self._apply_echo_out(mix, incoming, transition_duration_ms)
            elif transition_type == "filter_sweep":
                direction = transition.direction if transition else "lowpass"
                mix = self._apply_filter_sweep(mix, incoming, transition_duration_ms, direction or "lowpass")
            elif transition_type == "backspin":
                mix = self._apply_backspin(mix, incoming, transition_duration_ms)
            else:
                # Default to crossfade
                mix = self._apply_crossfade(mix, incoming, transition_duration_ms)
        
        # Normalize final mix
        mix = mix.normalize()
        
        return mix
    
    def _apply_crossfade(
        self,
        outgoing: AudioSegment,
        incoming: AudioSegment,
        duration_ms: int
    ) -> AudioSegment:
        """
        Apply equal-power crossfade between tracks
        """
        # Ensure duration doesn't exceed track lengths
        max_crossfade = min(len(outgoing), len(incoming)) - 100  # Leave 100ms buffer
        if max_crossfade < 100:
            # Tracks too short for crossfade, just concatenate
            return outgoing + incoming
        
        duration_ms = min(duration_ms, max_crossfade)
        duration_ms = max(100, duration_ms)  # At least 100ms
        
        # pydub's append with crossfade
        return outgoing.append(incoming, crossfade=duration_ms)
    
    def _apply_echo_out(
        self,
        outgoing: AudioSegment,
        incoming: AudioSegment,
        duration_ms: int
    ) -> AudioSegment:
        """
        Apply echo/reverb tail on outgoing track while fading in incoming
        """
        max_duration = min(len(outgoing), len(incoming)) - 100
        if max_duration < 500:
            # Tracks too short, fall back to simple crossfade
            return self._apply_crossfade(outgoing, incoming, duration_ms)
        
        duration_ms = min(duration_ms, max_duration)
        duration_ms = max(500, duration_ms)
        
        # Split outgoing track
        main_out = outgoing[:-duration_ms]
        tail_out = outgoing[-duration_ms:]
        
        # Apply echo effect to tail (simulate with layered fades)
        # Create echo by overlaying delayed, attenuated copies
        echo_tail = tail_out.fade_out(duration_ms)
        
        # Create delayed echoes
        delay_ms = 150
        num_echoes = 4
        for i in range(1, num_echoes + 1):
            delay = delay_ms * i
            attenuation = 6 * i  # -6dB per echo
            if delay < duration_ms:
                echo_copy = tail_out[:duration_ms - delay] - attenuation
                echo_copy = echo_copy.fade_out(len(echo_copy))
                # Overlay at delay position
                silent_prefix = AudioSegment.silent(duration=delay)
                echo_with_delay = silent_prefix + echo_copy
                echo_with_delay = echo_with_delay[:len(echo_tail)]
                echo_tail = echo_tail.overlay(echo_with_delay)
        
        # Fade in incoming
        incoming_start = incoming[:duration_ms].fade_in(duration_ms)
        incoming_rest = incoming[duration_ms:]
        
        # Overlay echo tail with incoming fade-in
        transition = echo_tail.overlay(incoming_start)
        
        # Combine all parts
        return main_out + transition + incoming_rest
    
    def _apply_filter_sweep(
        self,
        outgoing: AudioSegment,
        incoming: AudioSegment,
        duration_ms: int,
        direction: str = "lowpass"
    ) -> AudioSegment:
        """
        Apply progressive filter sweep on outgoing while fading in incoming
        """
        max_duration = min(len(outgoing), len(incoming)) - 100
        if max_duration < 500:
            # Tracks too short, fall back to simple crossfade
            return self._apply_crossfade(outgoing, incoming, duration_ms)
        
        duration_ms = min(duration_ms, max_duration)
        duration_ms = max(500, duration_ms)
        
        # Split outgoing track
        main_out = outgoing[:-duration_ms]
        tail_out = outgoing[-duration_ms:]
        
        # Apply progressive filter to tail (in chunks)
        num_chunks = 8
        chunk_size = duration_ms // num_chunks
        filtered_tail = AudioSegment.empty()
        
        for i in range(num_chunks):
            chunk = tail_out[i * chunk_size:(i + 1) * chunk_size]
            
            # Calculate filter frequency based on position
            if direction == "lowpass":
                # Sweep from high to low frequency
                freq = int(8000 - (i / num_chunks) * 7500)  # 8000 -> 500 Hz
                chunk = low_pass_filter(chunk, freq)
            else:  # highpass
                # Sweep from low to high frequency
                freq = int(100 + (i / num_chunks) * 7900)  # 100 -> 8000 Hz
                chunk = high_pass_filter(chunk, freq)
            
            # Also fade out gradually
            volume_reduction = (i / num_chunks) * 12  # Up to -12dB
            chunk = chunk - volume_reduction
            
            filtered_tail += chunk
        
        # Fade in incoming
        incoming_start = incoming[:duration_ms].fade_in(duration_ms)
        incoming_rest = incoming[duration_ms:]
        
        # Overlay filtered tail with incoming
        transition = filtered_tail.overlay(incoming_start)
        
        return main_out + transition + incoming_rest
    
    def _apply_backspin(
        self,
        outgoing: AudioSegment,
        incoming: AudioSegment,
        duration_ms: int
    ) -> AudioSegment:
        """
        Apply backspin effect (reverse + pitch down) on outgoing
        """
        # Check if tracks are long enough for backspin
        if len(outgoing) < 2000 or len(incoming) < 1000:
            # Tracks too short, fall back to simple crossfade
            return self._apply_crossfade(outgoing, incoming, duration_ms)
        
        # Backspin is typically shorter
        spin_duration_ms = min(1500, duration_ms // 2, len(outgoing) - 500)  # Max 1.5 seconds for the spin
        spin_duration_ms = max(200, spin_duration_ms)  # At least 200ms
        
        # Split outgoing
        main_out = outgoing[:-spin_duration_ms]
        spin_segment = outgoing[-spin_duration_ms:]
        
        # Reverse the spin segment
        reversed_spin = spin_segment.reverse()
        
        # Apply pitch down effect by slowing down
        # pydub doesn't have native pitch shift, so we'll simulate with speed change
        # Note: This also changes tempo, which is the desired "slowing record" effect
        samples = np.array(reversed_spin.get_array_of_samples())
        
        # Slow down by stretching (simple linear interpolation)
        slow_factor = 1.5  # 50% slower
        num_samples = int(len(samples) * slow_factor)
        slowed_samples = np.interp(
            np.linspace(0, len(samples) - 1, num_samples),
            np.arange(len(samples)),
            samples
        ).astype(np.int16)
        
        # Convert back to AudioSegment
        slowed_spin = AudioSegment(
            slowed_samples.tobytes(),
            frame_rate=int(reversed_spin.frame_rate),
            sample_width=reversed_spin.sample_width,
            channels=reversed_spin.channels
        )
        
        # Fade out the spin
        slowed_spin = slowed_spin.fade_out(len(slowed_spin))
        
        # Calculate how much of incoming to use
        remaining_transition = duration_ms - spin_duration_ms
        incoming_start = incoming[:remaining_transition].fade_in(remaining_transition // 2)
        incoming_rest = incoming[remaining_transition:]
        
        # Combine
        # Brief silence after spin for impact
        gap = AudioSegment.silent(duration=50)
        
        return main_out + slowed_spin + gap + incoming_start + incoming_rest
