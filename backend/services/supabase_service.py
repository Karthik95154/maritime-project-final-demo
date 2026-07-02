import os
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

    def upload_file(self, file_path: str, content_type: str = None) -> str:
        """
        Uploads a local file to Supabase Storage and returns the public URL.
        """
        if not self.is_configured():
            raise Exception("Supabase is not configured. Missing URL or Key.")

        file_name = os.path.basename(file_path)
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

        res = self.client.storage.from_(self.bucket_name).upload(
            file=file_bytes,
            path=destination_path,
            file_options={"content-type": content_type} if content_type else {}
        )
        
        # Get public URL
        public_url = self.client.storage.from_(self.bucket_name).get_public_url(destination_path)
        return public_url

supabase_service = SupabaseService()
