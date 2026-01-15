"""
Audio Downloader - Dual path: librespot (Spotify Premium) + yt-dlp fallback
"""

import asyncio
import hashlib
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import yt_dlp


class AudioDownloader:
    """
    Downloads audio tracks using librespot (primary) or yt-dlp (fallback)
    """
    
    def __init__(
        self,
        temp_dir: str = "/tmp/audio",
        spotify_username: str = "",
        spotify_password: str = ""
    ):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.spotify_username = spotify_username
        self.spotify_password = spotify_password
        
        # yt-dlp options for best audio quality
        self.yt_dlp_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
            'quiet': False,  # Enable output for debugging
            'no_warnings': False,
            'extract_flat': False,
            'socket_timeout': 30,
            'retries': 3,
        }
    
    async def download_playlist_tracks(
        self,
        tracks: list[dict],  # List of track dicts with spotify_id, artist, title
        session_id: str
    ) -> list[dict]:
        """
        Download multiple tracks from a playlist, avoiding duplicates.
        Returns list of download results with file paths.
        
        Each track dict should have:
        - spotify_id: str
        - artist: str (or artists list)
        - title: str
        """
        
        downloaded_tracks = []
        downloaded_files = set()  # Track file paths to avoid duplicates
        processed_queries = set()  # Track search queries to avoid duplicates
        
        for i, track in enumerate(tracks):
            try:
                # Format artist name(s) like the JavaScript example
                if isinstance(track.get('artist'), list):
                    # Handle multiple artists
                    artist_names = [a.get('name', '') for a in track['artist']]
                    artist_str = ', '.join(artist_names)
                else:
                    artist_str = track.get('artist', '')
                
                title = track.get('title', '')
                
                # Create YouTube search query in the format shown
                search_query = f"{title} by {artist_str}"
                
                # Skip if we already processed this exact query
                if search_query.lower() in processed_queries:
                    print(f"Skipping duplicate search: {search_query}")
                    continue
                
                processed_queries.add(search_query.lower())
                
                print(f"Downloading track {i+1}/{len(tracks)}: {search_query}")
                
                # Download from YouTube
                file_path = await self._download_youtube_formatted(search_query)
                
                # Validate file size
                file_size = Path(file_path).stat().st_size
                if file_size < 100 * 1024:  # Less than 100KB
                    print(f"Downloaded file too small ({file_size} bytes), skipping")
                    continue
                
                # Check for duplicate files (same size/content)
                file_hash = self._get_file_hash(file_path)
                if file_hash in downloaded_files:
                    print(f"Duplicate file detected, skipping: {search_query}")
                    Path(file_path).unlink()  # Clean up duplicate
                    continue
                
                downloaded_files.add(file_hash)
                
                downloaded_tracks.append({
                    'spotify_id': track.get('spotify_id', ''),
                    'title': title,
                    'artist': artist_str,
                    'file_path': file_path,
                    'source': 'youtube',
                    'file_size': file_size
                })
                
                print(f"✓ Downloaded: {search_query} ({file_size / 1024:.1f} KB)")
                
            except Exception as e:
                print(f"✗ Failed to download: {track.get('title', 'Unknown')} - {e}")
                continue
        
        print(f"Downloaded {len(downloaded_tracks)}/{len(tracks)} tracks successfully")
        return downloaded_tracks
    
    async def _download_librespot(self, spotify_id: str) -> str:
        """
        Download using librespot (Spotify Premium streaming)
        Uses librespot's pipe backend and streams to file to avoid OOM
        """
        wav_path = self.temp_dir / f"{spotify_id}.wav"
        mp3_path = self.temp_dir / f"{spotify_id}.mp3"
        
        # Spotify track URI
        track_uri = f"spotify:track:{spotify_id}"
        
        # Use librespot to stream track to file
        # This uses the pipe backend to output raw audio
        cmd = [
            "librespot",
            "--username", self.spotify_username,
            "--password", self.spotify_password,
            "--backend", "pipe",
            "--disable-audio-cache",
            "--oneshot",
            "--player-uri", track_uri
        ]
        
        try:
            # Run librespot and STREAM output to file (not memory!)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Stream to file in chunks to avoid OOM on long tracks
            CHUNK_SIZE = 1024 * 1024  # 1MB chunks
            bytes_written = 0
            
            with open(wav_path, 'wb') as f:
                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            process.stdout.read(CHUNK_SIZE),
                            timeout=60  # 1 minute timeout per chunk
                        )
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_written += len(chunk)
                    except asyncio.TimeoutError:
                        # No more data coming
                        break
            
            # Wait for process to finish
            await asyncio.wait_for(process.wait(), timeout=30)
            
            if process.returncode != 0 and bytes_written == 0:
                stderr = await process.stderr.read()
                raise Exception(f"Librespot failed: {stderr.decode()}")
            
            # Convert to MP3 using ffmpeg
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-f", "s16le",  # Raw PCM format
                "-ar", "44100",  # Sample rate
                "-ac", "2",  # Stereo
                "-i", str(wav_path),
                "-b:a", "320k",
                str(mp3_path)
            ]
            
            convert_process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await convert_process.communicate()
            
            # Clean up wav file
            if wav_path.exists():
                wav_path.unlink()
            
            if mp3_path.exists():
                return str(mp3_path)
            else:
                raise Exception("Failed to create MP3 file")
                
        except asyncio.TimeoutError:
            raise Exception("Librespot download timed out")
        except Exception as e:
            # Clean up any partial files
            for path in [output_path, wav_path, mp3_path]:
                if path.exists():
                    path.unlink()
            raise e
    
    async def _download_youtube_formatted(self, search_query: str) -> str:
        """
        Download from YouTube using the formatted search query (like "Song Name by Artist")
        """
        
        # Generate unique filename
        file_id = str(uuid.uuid4())[:8]
        safe_query = "".join(c for c in search_query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_query = safe_query[:50]  # Limit length
        
        output_template = str(self.temp_dir / f"{file_id}_{safe_query}")
        
        yt_opts = {
            **self.yt_dlp_opts,
            'outtmpl': output_template + '.%(ext)s',
        }
        
        try:
            # Run yt-dlp in thread pool to not block
            def do_download():
                with yt_dlp.YoutubeDL(yt_opts) as ydl:
                    # Search and download using the formatted query
                    result = ydl.extract_info(f"ytsearch1:{search_query}", download=True)
                    
                    if result and 'entries' in result:
                        entry = result['entries'][0]
                        return entry
                    elif result:
                        return result
                    else:
                        raise Exception("No results found")
            
            await asyncio.to_thread(do_download)
            
            # Find the downloaded file (yt-dlp may change extension)
            for ext in ['mp3', 'webm', 'm4a', 'opus']:
                potential_path = Path(f"{output_template}.{ext}")
                if potential_path.exists():
                    # Convert to mp3 if needed
                    if ext != 'mp3':
                        mp3_path = Path(f"{output_template}.mp3")
                        await self._convert_to_mp3(str(potential_path), str(mp3_path))
                        potential_path.unlink()
                        return str(mp3_path)
                    return str(potential_path)
            
            raise Exception("Downloaded file not found")
            
        except Exception as e:
            raise Exception(f"YouTube download failed for '{search_query}': {e}")
    
    def _get_file_hash(self, file_path: str) -> str:
        """
        Get a simple hash of the file for duplicate detection
        Uses file size + first/last 1KB for basic content matching
        """
        try:
            path = Path(file_path)
            file_size = path.stat().st_size
            
            # Read first 1KB
            with open(path, 'rb') as f:
                first_kb = f.read(1024)
            
            # Read last 1KB
            with open(path, 'rb') as f:
                f.seek(max(0, file_size - 1024))
                last_kb = f.read(1024)
            
            # Simple hash combining size and content samples
            import hashlib
            hasher = hashlib.md5()
            hasher.update(str(file_size).encode())
            hasher.update(first_kb)
            hasher.update(last_kb)
            
            return hasher.hexdigest()
            
        except Exception:
            # Fallback to just file size if reading fails
            return str(Path(file_path).stat().st_size)
    
    async def _convert_to_mp3(self, input_path: str, output_path: str):
        """Convert audio file to MP3 using ffmpeg"""
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-b:a", "320k",
            "-ar", "44100",
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        
        if not Path(output_path).exists():
            raise Exception("FFmpeg conversion failed")
