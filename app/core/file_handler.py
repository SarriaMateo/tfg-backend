import os
import mimetypes
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import uuid4
from fastapi import HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import settings

try:
    from google.cloud import storage  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - dependency-managed at runtime
    storage = None

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


def _is_cloud_storage_enabled() -> bool:
    return settings.env == "cloud"


def _normalize_storage_key(relative_url: str) -> str:
    normalized = relative_url.lstrip("/")
    if normalized.startswith("media/"):
        normalized = normalized[len("media/"):]
    return normalized


def _build_download_name(source_name: Optional[str], storage_key: str) -> str:
    if source_name:
        return source_name

    extension = Path(storage_key).suffix.lower()
    return f"unknown{extension}" if extension else "unknown"


def _resolve_media_type(storage_key: str, content_type: Optional[str] = None) -> str:
    if content_type:
        return content_type

    media_type, _ = mimetypes.guess_type(storage_key)
    return media_type or "application/octet-stream"


def _get_bucket():
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLOUD_STORAGE_UNAVAILABLE"
        )

    if not settings.gcs_bucket:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GCS_BUCKET_NOT_CONFIGURED"
        )

    client = storage.Client()
    return client.bucket(settings.gcs_bucket)

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

        # Generate unique filename with UUID
        final_filename = cls.get_storage_filename(filename, content_type)
        file_ext = Path(final_filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        relative_path = f"items/{company_id}/{unique_filename}"

        if _is_cloud_storage_enabled():
            blob = _get_bucket().blob(relative_path)
            blob.upload_from_string(
                final_file_content,
                content_type=_resolve_media_type(relative_path, "image/webp" if file_ext == ".webp" else content_type or mimetypes.guess_type(final_filename)[0])
            )
        else:
            # Create company-specific directory
            company_dir = cls.UPLOAD_DIR / str(company_id)
            company_dir.mkdir(parents=True, exist_ok=True)
            file_path = company_dir / unique_filename

            # Save file to filesystem
            with open(file_path, "wb") as f:
                f.write(final_file_content)

        # Return relative URL path for database storage
        return relative_path

    @classmethod
    def delete_image(cls, image_url: str) -> None:
        """
        Delete image file from filesystem by relative URL.
        """
        if not image_url:
            return

        storage_key = _normalize_storage_key(image_url)

        if _is_cloud_storage_enabled():
            blob = _get_bucket().blob(storage_key)
            if blob.exists():
                blob.delete()
            return

        # Build absolute path from relative URL
        file_path = MEDIA_ROOT / storage_key

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
        if _is_cloud_storage_enabled():
            return None
        return MEDIA_ROOT / _normalize_storage_key(relative_url)

    @classmethod
    def build_download_response(
        cls,
        relative_url: str,
        download_name: Optional[str] = None
    ):
        if not relative_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IMAGE_NOT_FOUND"
            )

        storage_key = _normalize_storage_key(relative_url)

        if _is_cloud_storage_enabled():
            blob = _get_bucket().blob(storage_key)
            if not blob.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="IMAGE_NOT_FOUND"
                )

            blob_bytes = blob.download_as_bytes()
            media_type = _resolve_media_type(storage_key, blob.content_type)
            final_download_name = _build_download_name(download_name, storage_key)
            return StreamingResponse(
                iter([blob_bytes]),
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{final_download_name}"'}
            )

        file_path = MEDIA_ROOT / storage_key
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IMAGE_NOT_FOUND"
            )

        media_type, _ = mimetypes.guess_type(str(file_path))
        final_download_name = _build_download_name(download_name, storage_key)
        return FileResponse(
            path=file_path,
            media_type=media_type or "application/octet-stream",
            filename=final_download_name,
        )


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

        # Generate unique filename with UUID
        final_filename = cls.get_storage_filename(filename, content_type)
        file_ext = Path(final_filename).suffix.lower()
        unique_filename = f"{uuid4()}{file_ext}"
        relative_path = f"transactions/{company_id}/{unique_filename}"

        if _is_cloud_storage_enabled():
            blob = _get_bucket().blob(relative_path)
            blob.upload_from_string(
                final_file_content,
                content_type=_resolve_media_type(relative_path, "image/webp" if file_ext == ".webp" else content_type or mimetypes.guess_type(final_filename)[0])
            )
        else:
            # Create company-specific directory
            company_dir = cls.UPLOAD_DIR / str(company_id)
            company_dir.mkdir(parents=True, exist_ok=True)
            file_path = company_dir / unique_filename

            # Save file to filesystem
            with open(file_path, "wb") as f:
                f.write(final_file_content)

        # Return relative URL path for database storage
        return relative_path

    @classmethod
    def delete_document(cls, document_url: str) -> None:
        """
        Delete document file from filesystem by relative URL.
        """
        if not document_url:
            return

        storage_key = _normalize_storage_key(document_url)

        if _is_cloud_storage_enabled():
            blob = _get_bucket().blob(storage_key)
            if blob.exists():
                blob.delete()
            return

        # Build absolute path from relative URL
        file_path = MEDIA_ROOT / storage_key

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
        if _is_cloud_storage_enabled():
            return None
        return MEDIA_ROOT / _normalize_storage_key(relative_url)

    @classmethod
    def build_download_response(
        cls,
        relative_url: str,
        download_name: Optional[str] = None
    ):
        if not relative_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DOCUMENT_NOT_FOUND"
            )

        storage_key = _normalize_storage_key(relative_url)

        if _is_cloud_storage_enabled():
            blob = _get_bucket().blob(storage_key)
            if not blob.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="DOCUMENT_NOT_FOUND"
                )

            blob_bytes = blob.download_as_bytes()
            media_type = _resolve_media_type(storage_key, blob.content_type)
            final_download_name = _build_download_name(download_name, storage_key)
            return StreamingResponse(
                iter([blob_bytes]),
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{final_download_name}"'}
            )

        file_path = MEDIA_ROOT / storage_key
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DOCUMENT_NOT_FOUND"
            )

        media_type, _ = mimetypes.guess_type(str(file_path))
        final_download_name = _build_download_name(download_name, storage_key)
        return FileResponse(
            path=file_path,
            media_type=media_type or "application/octet-stream",
            filename=final_download_name,
        )
