"""
Audio Downloader - Dual path: librespot (Spotify Premium) + yt-dlp fallback
"""

import asyncio
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
    
    async def download(
        self,
        spotify_id: str,
        artist: str,
        title: str
    ) -> tuple[str, str]:
        """
        Download a track. Returns (file_path, source).
        Uses yt-dlp to search YouTube for the track.
        
        Note: librespot 0.6.0 is a Spotify Connect speaker, not a direct downloader.
        It doesn't support --oneshot or --player-uri for direct track downloading.
        """
        
        # Use yt-dlp to download from YouTube
        try:
            file_path = await self._download_youtube(artist, title)
            
            # Validate file size - must be at least 100KB for a real song
            file_size = Path(file_path).stat().st_size
            if file_size < 100 * 1024:  # Less than 100KB
                raise Exception(f"Downloaded file too small ({file_size} bytes) - likely not a valid audio file")
            
            print(f"Downloaded: {artist} - {title} ({file_size / 1024:.1f} KB)")
            return file_path, "youtube"
        except Exception as e:
            raise Exception(f"Failed to download track: {e}")
    
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
    
    async def _download_youtube(self, artist: str, title: str) -> str:
        """
        Download from YouTube using yt-dlp
        Searches for the track and downloads best audio quality
        """
        search_query = f"{artist} - {title} official audio"
        
        # Generate unique filename
        file_id = str(uuid.uuid4())[:8]
        safe_title = "".join(c for c in f"{artist}_{title}" if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title[:50]  # Limit length
        
        output_template = str(self.temp_dir / f"{file_id}_{safe_title}")
        
        yt_opts = {
            **self.yt_dlp_opts,
            'outtmpl': output_template + '.%(ext)s',
        }
        
        try:
            # Run yt-dlp in thread pool to not block
            def do_download():
                with yt_dlp.YoutubeDL(yt_opts) as ydl:
                    # Search and download
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
            raise Exception(f"YouTube download failed: {e}")
    
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
