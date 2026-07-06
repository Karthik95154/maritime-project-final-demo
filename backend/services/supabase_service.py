import os
import re
import unicodedata
import uuid
from supabase import create_client, Client
from config import settings

class SupabaseService:
    def __init__(self):
        self.url = settings.supabase_url
        self.key = settings.supabase_key
        self.bucket_name = "maritime-assets"
        self.client: Client = create_client(self.url, self.key) if self.url and self.key else None

    def is_configured(self) -> bool:
        return self.client is not None

    def sanitize_storage_name(self, file_name: str) -> str:
        """
        Convert arbitrary uploaded filenames into a Supabase-safe storage key segment.
        """
        base_name = os.path.basename(file_name or "upload.bin")
        normalized = unicodedata.normalize("NFKD", base_name).encode("ascii", "ignore").decode("ascii")
        normalized = normalized.replace(" ", "_")
        normalized = re.sub(r"[^A-Za-z0-9._-]", "", normalized)

        if "." in normalized:
            stem, ext = normalized.rsplit(".", 1)
            stem = stem[:80] or "upload"
            ext = re.sub(r"[^A-Za-z0-9]", "", ext)[:10]
            normalized = f"{stem}.{ext}" if ext else stem
        else:
            normalized = normalized[:80]

        return normalized or "upload.bin"

    def upload_file(self, file_path: str, content_type: str = None) -> str:
        """
        Uploads a local file to Supabase Storage and returns the public URL.
        """
        if not self.is_configured():
            raise Exception("Supabase is not configured. Missing URL or Key.")

        file_name = self.sanitize_storage_name(os.path.basename(file_path))
        # Add a unique prefix to avoid collisions
        unique_id = str(uuid.uuid4())[:8]
        destination_path = f"{unique_id}_{file_name}"

        with open(file_path, "rb") as f:
            res = self.client.storage.from_(self.bucket_name).upload(
                file=f,
                path=destination_path,
                file_options={"content-type": content_type} if content_type else {}
            )
            
        # Get public URL
        public_url = self.client.storage.from_(self.bucket_name).get_public_url(destination_path)
        return public_url

    def upload_bytes(self, file_bytes: bytes, destination_path: str, content_type: str = None) -> str:
        """
        Uploads raw bytes to Supabase Storage and returns the public URL.
        """
        if not self.is_configured():
            raise Exception("Supabase is not configured. Missing URL or Key.")

        folder, file_name = os.path.split(destination_path)
        safe_file_name = self.sanitize_storage_name(file_name)
        safe_destination_path = f"{folder}/{safe_file_name}" if folder else safe_file_name

        res = self.client.storage.from_(self.bucket_name).upload(
            file=file_bytes,
            path=safe_destination_path,
            file_options={"content-type": content_type} if content_type else {}
        )
        
        # Get public URL
        public_url = self.client.storage.from_(self.bucket_name).get_public_url(safe_destination_path)
        return public_url

supabase_service = SupabaseService()
