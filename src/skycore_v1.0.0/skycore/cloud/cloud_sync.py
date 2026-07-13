"""
SkyCore Cloud Sync
=================
S3-compatible cloud upload for footage and logs.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from pathlib import Path
import hashlib

log = logging.getLogger(__name__)


@dataclass
class CloudConfig:
    """Cloud storage configuration."""
    bucket: str
    endpoint_url: Optional[str] = None  # None for AWS
    region: str = "us-east-1"
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    prefix: str = "skycore"
    storage_class: str = "STANDARD"


class S3Sync:
    """
    S3-compatible cloud sync for footage and logs.
    
    Supports AWS S3, MinIO, Backblaze B2, Cloudflare R2, etc.
    
    Features:
    - Multipart upload for large files
    - Presigned URLs for sharing
    - Automatic retry
    - Progress tracking
    """
    
    def __init__(self, config: CloudConfig):
        """
        Initialize S3 sync.
        
        Args:
            config: Cloud configuration
        """
        self.config = config
        self._client = None
        
        # Statistics
        self.total_uploads = 0
        self.total_bytes = 0
        self.failed_uploads = 0
        
        log.info(f"S3 sync initialized: {config.bucket}")
    
    async def connect(self):
        """Connect to S3-compatible storage."""
        try:
            import boto3
            
            client_kwargs = {
                'service_name': 's3',
                'region_name': self.config.region
            }
            
            if self.config.endpoint_url:
                client_kwargs['endpoint_url'] = self.config.endpoint_url
            
            if self.config.access_key:
                client_kwargs['aws_access_key_id'] = self.config.access_key
                client_kwargs['aws_secret_access_key'] = self.config.secret_key
            
            self._client = boto3.client(**client_kwargs)
            log.info("S3 client connected")
            
        except ImportError:
            log.warning("boto3 not installed, cloud sync unavailable")
        except Exception as e:
            log.error(f"S3 connection failed: {e}")
    
    async def upload_file(self, local_path: str, key: Optional[str] = None,
                         progress_callback: Optional[Callable] = None) -> Optional[str]:
        """
        Upload file to cloud storage.
        
        Args:
            local_path: Path to local file
            key: Optional S3 key (defaults to filename with timestamp)
            progress_callback: Optional progress callback
            
        Returns:
            S3 key of uploaded file
        """
        if not self._client:
            await self.connect()
        
        if not self._client:
            return None
        
        # Generate key if not provided
        if not key:
            filename = Path(local_path).name
            timestamp = int(asyncio.get_event_loop().time())
            key = f"{self.config.prefix}/{timestamp}/{filename}"
        
        try:
            # Calculate file size
            file_size = os.path.getsize(local_path)
            
            # Upload with progress
            self._client.upload_file(
                local_path,
                self.config.bucket,
                key,
                ExtraArgs={
                    'StorageClass': self.config.storage_class
                },
                Callback=lambda bytes_transferred: (
                    progress_callback(bytes_transferred, file_size) 
                    if progress_callback else None
                )
            )
            
            self.total_uploads += 1
            self.total_bytes += file_size
            
            log.info(f"Uploaded: {local_path} -> {key}")
            return key
            
        except Exception as e:
            self.failed_uploads += 1
            log.error(f"Upload failed: {e}")
            return None
    
    async def presigned_url(self, key: str, expires_s: int = 86400) -> Optional[str]:
        """
        Generate presigned URL for file.
        
        Args:
            key: S3 key
            expires_s: URL expiration in seconds
            
        Returns:
            Presigned URL
        """
        if not self._client:
            return None
        
        try:
            url = self._client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.config.bucket,
                    'Key': key
                },
                ExpiresIn=expires_s
            )
            return url
        except Exception as e:
            log.error(f"Presigned URL failed: {e}")
            return None
    
    async def list_files(self, prefix: Optional[str] = None) -> List[str]:
        """List files in bucket."""
        if not self._client:
            return []
        
        try:
            full_prefix = prefix or self.config.prefix
            
            response = self._client.list_objects_v2(
                Bucket=self.config.bucket,
                Prefix=full_prefix
            )
            
            keys = [obj['Key'] for obj in response.get('Contents', [])]
            return keys
            
        except Exception as e:
            log.error(f"List files failed: {e}")
            return []
    
    async def delete_file(self, key: str) -> bool:
        """Delete file from bucket."""
        if not self._client:
            return False
        
        try:
            self._client.delete_object(
                Bucket=self.config.bucket,
                Key=key
            )
            log.info(f"Deleted: {key}")
            return True
        except Exception as e:
            log.error(f"Delete failed: {e}")
            return False
    
    async def upload_folder(self, folder_path: str, prefix: Optional[str] = None,
                           progress_callback: Optional[Callable] = None) -> List[str]:
        """
        Upload all files in folder.
        
        Args:
            folder_path: Path to local folder
            prefix: Optional key prefix
            progress_callback: Optional progress callback
            
        Returns:
            List of uploaded keys
        """
        folder = Path(folder_path)
        uploaded = []
        
        for file_path in folder.rglob('*'):
            if file_path.is_file():
                rel_path = file_path.relative_to(folder)
                key = f"{prefix or self.config.prefix}/{rel_path}"
                
                result = await self.upload_file(str(file_path), key, progress_callback)
                if result:
                    uploaded.append(result)
        
        return uploaded
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get sync statistics."""
        return {
            'total_uploads': self.total_uploads,
            'total_bytes': self.total_bytes,
            'failed_uploads': self.failed_uploads,
            'bucket': self.config.bucket,
            'endpoint': self.config.endpoint_url or 'AWS'
        }


# Export
__all__ = ['S3Sync', 'CloudConfig']