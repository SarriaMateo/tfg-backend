import os
import mimetypes
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, status

# Configuration
UPLOAD_DIR = Path("uploads/items")
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Create upload directory if it doesn't exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class FileHandler:
    """Utility class for handling file uploads"""

    @staticmethod
    def validate_image_file(file_content: bytes, filename: str) -> None:
        """
        Validate image file size, extension, and MIME type.
        Raises HTTPException if validation fails.
        """
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="IMAGE_TOO_LARGE"
            )

        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

        # Check MIME type
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

    @staticmethod
    def save_image(file_content: bytes, filename: str) -> str:
        """
        Save image file and return the relative URL path.
        """
        FileHandler.validate_image_file(file_content, filename)

        # Generate unique filename
        file_ext = Path(filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Return relative URL path
        return f"/uploads/items/{unique_filename}"

    @staticmethod
    def delete_image(image_url: str) -> None:
        """
        Delete image file from filesystem.
        """
        if not image_url:
            return

        # Extract filename from URL
        filename = Path(image_url).name
        file_path = UPLOAD_DIR / filename

        if file_path.exists():
            file_path.unlink()
