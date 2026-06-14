import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile
from typing import Optional
from app.core.config import settings


class StorageService:
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        self.local_path = Path(settings.LOCAL_STORAGE_PATH)
        self.local_path.mkdir(parents=True, exist_ok=True)

    def _get_extension(self, filename: str) -> str:
        return Path(filename).suffix.lower()

    def _generate_filename(self, original: str, subfolder: str = "") -> tuple[str, str]:
        ext = self._get_extension(original)
        unique_name = f"{uuid.uuid4().hex}{ext}"
        if subfolder:
            folder = self.local_path / subfolder
            folder.mkdir(parents=True, exist_ok=True)
            file_path = folder / unique_name
            url_path = f"/storage/{subfolder}/{unique_name}"
        else:
            file_path = self.local_path / unique_name
            url_path = f"/storage/{unique_name}"
        return str(file_path), url_path

    async def upload_file(
        self,
        file: UploadFile,
        subfolder: str = "uploads",
        allowed_types: Optional[list] = None,
    ) -> dict:
        if allowed_types and file.content_type not in allowed_types:
            raise ValueError(f"File type {file.content_type} not allowed")

        file_path, url_path = self._generate_filename(file.filename or "upload", subfolder)

        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        return {
            "file_path": file_path,
            "file_url": url_path,
            "original_filename": file.filename,
            "filename": Path(file_path).name,
            "file_size": len(content),
            "mime_type": file.content_type,
            "file_type": self._classify_type(file.content_type or ""),
        }

    def _classify_type(self, mime_type: str) -> str:
        if mime_type.startswith("image/"):
            return "image"
        if mime_type.startswith("video/"):
            return "video"
        if mime_type.startswith("audio/"):
            return "audio"
        if mime_type == "application/pdf":
            return "pdf"
        if "document" in mime_type or "word" in mime_type:
            return "document"
        return "file"

    async def delete_file(self, file_path: str) -> bool:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False


storage_service = StorageService()
