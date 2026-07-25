import os

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".xlsx", ".xls"}
ALLOWED_LABEL = "PDF, .txt, .xlsx, or .xls"


def get_file_type_error(file_obj):
    """Returns an error message if file_obj's extension isn't allowed, else None."""
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"Unsupported file type '{ext or 'unknown'}'. Allowed types: {ALLOWED_LABEL}."
    return None
