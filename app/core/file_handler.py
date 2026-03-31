import os
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import HTTPException, status

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover - dependency-managed at runtime
    Image = None

    class UnidentifiedImageError(Exception):
        pass

try:
    from pillow_heif import register_heif_opener  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - dependency-managed at runtime
    register_heif_opener = None

# Base media directory
MEDIA_ROOT = Path("media")
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

if register_heif_opener is not None:
    register_heif_opener()


class ItemImageHandler:
    """Handler for item image uploads and management"""
    
    # Configuration specific to item images
    UPLOAD_DIR = MEDIA_ROOT / "items"
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "image/avif",
    }
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".avif"}
    CONVERT_TO_WEBP_MIME_TYPES = {"image/heic", "image/heif", "image/avif"}
    CONVERT_TO_WEBP_EXTENSIONS = {".heic", ".heif", ".avif"}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create upload directory if it doesn't exist"""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_image(cls, file_content: bytes, filename: str, content_type: Optional[str] = None) -> None:
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
        guessed_mime_type, _ = mimetypes.guess_type(filename)
        effective_mime_type = (content_type or guessed_mime_type or "").lower()
        if effective_mime_type and effective_mime_type not in cls.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

    @classmethod
    def should_convert_to_webp(cls, filename: str, content_type: Optional[str] = None) -> bool:
        file_ext = Path(filename).suffix.lower()
        effective_mime_type = (content_type or "").lower()
        return (
            file_ext in cls.CONVERT_TO_WEBP_EXTENSIONS
            or effective_mime_type in cls.CONVERT_TO_WEBP_MIME_TYPES
        )

    @classmethod
    def get_storage_filename(cls, filename: str, content_type: Optional[str] = None) -> str:
        if not cls.should_convert_to_webp(filename, content_type):
            return filename

        stem = Path(filename).stem or "unknown"
        return f"{stem}.webp"

    @classmethod
    def _convert_to_webp(cls, file_content: bytes) -> bytes:
        if Image is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

        try:
            image = Image.open(BytesIO(file_content))
            image.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_IMAGE_FORMAT"
            )

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

        output = BytesIO()
        image.save(output, format="WEBP")
        return output.getvalue()

    @classmethod
    def save_image(
        cls,
        file_content: bytes,
        filename: str,
        company_id: int,
        content_type: Optional[str] = None
    ) -> str:
        """
        Save image file for an item and return the relative URL path.
        Structure: items/{company_id}/{uuid}.ext
        
        Returns: Relative path to store in database (e.g., "items/1/abc123.jpg")
        """
        cls._ensure_dir()
        cls.validate_image(file_content, filename, content_type)

        final_file_content = file_content
        if cls.should_convert_to_webp(filename, content_type):
            final_file_content = cls._convert_to_webp(file_content)

        # Create company-specific directory
        company_dir = cls.UPLOAD_DIR / str(company_id)
        company_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with UUID
        final_filename = cls.get_storage_filename(filename, content_type)
        file_ext = Path(final_filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        file_path = company_dir / unique_filename

        # Save file to filesystem
        with open(file_path, "wb") as f:
            f.write(final_file_content)

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


class TransactionDocumentHandler:
    """Handler for transaction document uploads and management"""
    
    # Configuration specific to transaction documents
    UPLOAD_DIR = MEDIA_ROOT / "transactions"
    ALLOWED_MIME_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/csv",
        "text/plain",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
        "image/avif",
    }
    ALLOWED_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".avif"
    }
    CONVERT_TO_WEBP_MIME_TYPES = {"image/heic", "image/heif", "image/avif"}
    CONVERT_TO_WEBP_EXTENSIONS = {".heic", ".heif", ".avif"}
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    @classmethod
    def _ensure_dir(cls) -> None:
        """Create upload directory if it doesn't exist"""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_document(cls, file_content: bytes, filename: str, content_type: Optional[str] = None) -> None:
        """
        Validate document file size, extension, and MIME type.
        Raises HTTPException if validation fails.
        """
        # Check file size
        if len(file_content) > cls.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="DOCUMENT_TOO_LARGE"
            )

        # Check file extension
        file_ext = Path(filename).suffix.lower()
        if file_ext not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_DOCUMENT_FORMAT"
            )

        # Check MIME type
        guessed_mime_type, _ = mimetypes.guess_type(filename)
        effective_mime_type = (content_type or guessed_mime_type or "").lower()
        if effective_mime_type and effective_mime_type not in cls.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_DOCUMENT_FORMAT"
            )

    @classmethod
    def should_convert_to_webp(cls, filename: str, content_type: Optional[str] = None) -> bool:
        file_ext = Path(filename).suffix.lower()
        effective_mime_type = (content_type or "").lower()
        return (
            file_ext in cls.CONVERT_TO_WEBP_EXTENSIONS
            or effective_mime_type in cls.CONVERT_TO_WEBP_MIME_TYPES
        )

    @classmethod
    def get_storage_filename(cls, filename: str, content_type: Optional[str] = None) -> str:
        if not cls.should_convert_to_webp(filename, content_type):
            return filename

        stem = Path(filename).stem or "unknown"
        return f"{stem}.webp"

    @classmethod
    def _convert_to_webp(cls, file_content: bytes) -> bytes:
        if Image is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_DOCUMENT_FORMAT"
            )

        try:
            image = Image.open(BytesIO(file_content))
            image.load()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="INVALID_DOCUMENT_FORMAT"
            )

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

        output = BytesIO()
        image.save(output, format="WEBP")
        return output.getvalue()

    @classmethod
    def save_document(
        cls,
        file_content: bytes,
        filename: str,
        company_id: int,
        content_type: Optional[str] = None
    ) -> str:
        """
        Save document file for a transaction and return the relative URL path.
        Structure: transactions/{company_id}/{uuid}.ext
        
        Returns: Relative path to store in database (e.g., "transactions/1/abc123.pdf")
        """
        cls._ensure_dir()
        cls.validate_document(file_content, filename, content_type)

        final_file_content = file_content
        if cls.should_convert_to_webp(filename, content_type):
            final_file_content = cls._convert_to_webp(file_content)

        # Create company-specific directory
        company_dir = cls.UPLOAD_DIR / str(company_id)
        company_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with UUID
        final_filename = cls.get_storage_filename(filename, content_type)
        file_ext = Path(final_filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        file_path = company_dir / unique_filename

        # Save file to filesystem
        with open(file_path, "wb") as f:
            f.write(final_file_content)

        # Return relative URL path for database storage
        relative_path = f"transactions/{company_id}/{unique_filename}"
        return relative_path

    @classmethod
    def delete_document(cls, document_url: str) -> None:
        """
        Delete document file from filesystem by relative URL.
        """
        if not document_url:
            return

        # Build absolute path from relative URL
        file_path = MEDIA_ROOT / document_url.lstrip("/")

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
