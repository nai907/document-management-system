import os

from .models import Document

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".xlsx", ".xls"}
ALLOWED_LABEL = "PDF, .txt, .xlsx, or .xls"


def get_file_type_error(file_obj):
    """Returns an error message if file_obj's extension isn't allowed, else None."""
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type '{ext or 'unknown'}'. Allowed types: {ALLOWED_LABEL}."
    return None


def get_duplicate_title_error(title, exclude_pk=None):
    """Returns an error message if another document already has this title
    once both are cleaned (trimmed + lowercased), else None."""
    cleaned = Document.clean_title(title)
    qs = Document.objects.filter(normalized_title=cleaned)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        return "A document with this title already exists."
    return None
