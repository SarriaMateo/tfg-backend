import os
import mimetypes
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, status

# Base media directory
MEDIA_ROOT = Path("media")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)


class ItemImageHandler:
    """Handler for item image uploads and management"""
    
    # Configuration specific to item images
    UPLOAD_DIR = MEDIA_ROOT / "items"
    ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create upload directory if it doesn't exist"""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_image(cls, file_content: bytes, filename: str) -> None:
        """
        Validate image file size, extension, and MIME type.
        Raises HTTPException if validation fails.
        """
        # Check file size
        if len(file_content) > cls.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IMAGE_TOO_LARGE"
            )

        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type not in cls.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

    @classmethod
    def save_image(cls, file_content: bytes, filename: str, company_id: int) -> str:
        """
        Save image file for an item and return the relative URL path.
        Structure: items/{company_id}/{uuid}.ext
        
        Returns: Relative path to store in database (e.g., "items/1/abc123.jpg")
        """
        cls._ensure_dir()
        cls.validate_image(file_content, filename)

        # Create company-specific directory
        company_dir = cls.UPLOAD_DIR / str(company_id)
        company_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with UUID
        file_ext = Path(filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        file_path = company_dir / unique_filename

        # Save file to filesystem
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Return relative URL path for database storage
        # Remove /media prefix since MEDIA_ROOT will be prepended when reading
        relative_path = f"items/{company_id}/{unique_filename}"
        return relative_path

    @classmethod
    def delete_image(cls, image_url: str) -> None:
        """
        Delete image file from filesystem by relative URL.
        """
        if not image_url:
            return

        # Build absolute path from relative URL
        # image_url format: "/media/items/{company_id}/{filename}"
        file_path = MEDIA_ROOT / image_url.lstrip("/")

        if file_path.exists():
            file_path.unlink()

    @classmethod
    def get_absolute_path(cls, relative_url: str) -> Path:
        """
        Convert relative URL to absolute filesystem path.
        Useful for serving files in static routes.
        """
        if not relative_url:
            return None
        return MEDIA_ROOT / relative_url.lstrip("/")
