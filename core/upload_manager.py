"""
Secure Document Upload & Processing Manager for Operation JARVIS.
Handles file validation, magic byte content inspection, path sanitization,
deduplication, and indexing through DocumentIntelligence.
"""
import io
import os
import re
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from config.settings import settings
from core.doc_intelligence import doc_intelligence
from security.path_jail import path_jail, PathJailViolation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
DEFAULT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Configurable limits
MAX_FILE_SIZE_MB = int(os.getenv("JARVIS_MAX_UPLOAD_MB", "25"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_BATCH_UPLOAD_COUNT = 10

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}

class UploadValidationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class DocumentUploadManager:
    def __init__(self, upload_dir: Path = DEFAULT_UPLOADS_DIR):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, filename: str) -> str:
        """Sanitizes user filename to prevent path traversal and shell injection."""
        base = os.path.basename(filename.strip().replace("\\", "/"))
        # Strip path traversal indicators
        base = re.sub(r"\.\.+", ".", base)
        # Allow alphanumeric, underscores, hyphens, and dots
        clean = re.sub(r"[^a-zA-Z0-9_\.-]", "_", base)
        if not clean or clean.startswith("."):
            clean = f"document_{clean}"
        return clean[:120]  # Cap filename length

    def validate_file_content(self, filename: str, content: bytes) -> str:
        """
        Validates declared extension against actual binary content signatures.
        Returns the confirmed lowercase file extension (e.g. '.pdf').
        Raises UploadValidationError on mismatch or malicious signature.
        """
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UploadValidationError(
                f"Unsupported file format '{ext}'. Allowed extensions: PDF, DOCX, PPTX, TXT.",
                status_code=400
            )

        # Check for empty content
        if len(content) == 0:
            raise UploadValidationError(f"File '{filename}' is empty (0 bytes).", status_code=400)

        # Size check
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise UploadValidationError(
                f"File '{filename}' ({round(len(content)/(1024*1024), 2)}MB) exceeds maximum permitted limit of {MAX_FILE_SIZE_MB}MB.",
                status_code=413
            )

        # 1. PDF Signature Validation: must contain %PDF- in header
        if ext == ".pdf":
            header_sample = content[:1024]
            if b"%PDF-" not in header_sample:
                raise UploadValidationError(
                    f"File '{filename}' failed PDF signature verification. Content does not start with valid %PDF header.",
                    status_code=400
                )

        # 2. DOCX Signature Validation: must be valid zip with word/document.xml
        elif ext == ".docx":
            if not content.startswith(b"PK\x03\x04"):
                raise UploadValidationError(
                    f"File '{filename}' failed DOCX signature verification. Missing PK zip magic bytes.",
                    status_code=400
                )
            try:
                with zipfile.ZipFile(io.BytesIO(content), "r") as z:
                    names = z.namelist()
                    if not any("word/document.xml" in n for n in names):
                        raise UploadValidationError(
                            f"File '{filename}' is a zip archive but does not contain valid Word document XML.",
                            status_code=400
                        )
            except zipfile.BadZipFile:
                raise UploadValidationError(f"File '{filename}' is corrupted or not a valid DOCX archive.", status_code=400)

        # 3. PPTX Signature Validation: must be valid zip with ppt/
        elif ext == ".pptx":
            if not content.startswith(b"PK\x03\x04"):
                raise UploadValidationError(
                    f"File '{filename}' failed PPTX signature verification. Missing PK zip magic bytes.",
                    status_code=400
                )
            try:
                with zipfile.ZipFile(io.BytesIO(content), "r") as z:
                    names = z.namelist()
                    if not any(n.startswith("ppt/") for n in names):
                        raise UploadValidationError(
                            f"File '{filename}' is a zip archive but does not contain PowerPoint presentation components.",
                            status_code=400
                        )
            except zipfile.BadZipFile:
                raise UploadValidationError(f"File '{filename}' is corrupted or not a valid PPTX archive.", status_code=400)

        # 4. TXT Validation: must be valid text, reject binary null bytes
        elif ext == ".txt":
            # Reject binary null bytes indicative of compiled binaries/payloads
            if b"\x00" in content[:4096]:
                raise UploadValidationError(
                    f"File '{filename}' contains binary null bytes and cannot be parsed as plain text.",
                    status_code=400
                )
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content.decode("latin-1")
                except Exception:
                    raise UploadValidationError(f"File '{filename}' contains un-decodable text encoding.", status_code=400)

        return ext

    def save_and_ingest(
        self,
        filename: str,
        content: bytes,
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """
        Validates content, saves to dedicated uploads directory with collision-resistant name,
        and indexes into SQLite FTS5 via DocumentIntelligence.
        """
        # Validate content & extension
        ext = self.validate_file_content(filename, content)
        clean_name = self.sanitize_filename(filename)

        # Generate safe collision-resistant filename preserving original stem
        timestamp_prefix = int(time.time())
        unique_suffix = uuid.uuid4().hex[:6]
        stem = Path(clean_name).stem
        safe_disk_filename = f"{timestamp_prefix}_{unique_suffix}_{stem}{ext}"
        destination_path = self.upload_dir / safe_disk_filename

        # Path jail security verification
        try:
            validated_dest = path_jail.validate_path(destination_path)
        except PathJailViolation as e:
            raise UploadValidationError(f"Security Path Jail violation: {e}", status_code=403)

        # Write to disk
        with open(validated_dest, "wb") as f:
            f.write(content)

        # Ingest into DocumentIntelligence
        ingest_res = doc_intelligence.ingest_document(
            file_path=validated_dest,
            force_reindex=force_reindex
        )

        if not ingest_res.get("ok"):
            # Clean up disk file on extraction failure
            try:
                validated_dest.unlink(missing_ok=True)
            except Exception:
                pass
            raise UploadValidationError(
                ingest_res.get("error", "Document intelligence extraction failed."),
                status_code=400
            )

        # Include original user-friendly filename in metadata
        ingest_res["original_filename"] = clean_name
        ingest_res["stored_filename"] = safe_disk_filename
        return ingest_res

    def process_batch_uploads(
        self,
        files_data: List[Tuple[str, bytes]],
        force_reindex: bool = False
    ) -> Dict[str, Any]:
        """Processes multiple uploaded files in one transaction."""
        if len(files_data) > MAX_BATCH_UPLOAD_COUNT:
            raise UploadValidationError(
                f"Maximum batch upload limit exceeded. Allowed up to {MAX_BATCH_UPLOAD_COUNT} files, received {len(files_data)}.",
                status_code=400
            )

        results = []
        errors = []

        for original_name, content in files_data:
            try:
                res = self.save_and_ingest(original_name, content, force_reindex=force_reindex)
                results.append(res)
            except UploadValidationError as ve:
                errors.append({"filename": original_name, "error": ve.message, "status_code": ve.status_code})
            except Exception as ex:
                errors.append({"filename": original_name, "error": str(ex), "status_code": 500})

        return {
            "ok": len(results) > 0 or len(errors) == 0,
            "total_uploaded": len(files_data),
            "successful_count": len(results),
            "failed_count": len(errors),
            "indexed_documents": results,
            "errors": errors
        }

upload_manager = DocumentUploadManager()
