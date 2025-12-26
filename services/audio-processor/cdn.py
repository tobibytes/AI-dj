"""
CDN Uploader - Uploads rendered mixes to user's CDN
"""

import mimetypes
from pathlib import Path

import httpx


class CDNUploader:
    """
    Uploads files to the user's CDN using their 3-step upload process
    """
    
    def __init__(
        self,
        api_url: str = "https://api.cdn.tobiolajide.com",
        app_name: str = "ai-dj"
    ):
        self.api_url = api_url.rstrip('/')
        self.app_name = app_name
    
    async def upload(self, file_path: str) -> str:
        """
        Upload a file to the CDN and return the public URL
        
        Args:
            file_path: Path to the file to upload
            
        Returns:
            Public URL of the uploaded file
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get file info
        filename = path.name
        file_size = path.stat().st_size
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        # For audio files, ensure correct MIME type
        if filename.endswith('.mp3'):
            content_type = "audio/mpeg"
        elif filename.endswith('.wav'):
            content_type = "audio/wav"
        elif filename.endswith('.flac'):
            content_type = "audio/flac"
        
        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout for large files
            # Step 1: Initialize upload
            init_response = await client.post(
                f"{self.api_url}/upload/init",
                json={
                    "filename": filename,
                    "content_type": content_type,
                    "size": file_size,
                    "app": self.app_name,
                }
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            
            upload_url = init_data["upload_url"]
            key = init_data["key"]
            public_url = init_data["public_url"]
            
            # Step 2: Upload file content using streaming to avoid OOM
            async def file_stream():
                """Generator to stream file in chunks"""
                CHUNK_SIZE = 5 * 1024 * 1024  # 5MB chunks
                with open(path, 'rb') as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        yield chunk
            
            upload_response = await client.put(
                upload_url,
                content=file_stream(),
                headers={
                    "Content-Type": content_type,
                    "Content-Length": str(file_size)
                }
            )
            upload_response.raise_for_status()
            
            # Step 3: Complete upload
            complete_response = await client.post(
                f"{self.api_url}/upload/complete",
                json={
                    "key": key,
                    "status": "success"
                }
            )
            complete_response.raise_for_status()
            
            return public_url


class LocalFileStore:
    """
    Fallback: Store files locally if CDN is unavailable
    """
    
    def __init__(self, output_dir: str = "/tmp/audio/mixes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def store(self, file_path: str) -> str:
        """
        Copy file to output directory and return local path
        """
        import shutil
        
        source = Path(file_path)
        dest = self.output_dir / source.name
        
        shutil.copy2(source, dest)
        
        return str(dest)
