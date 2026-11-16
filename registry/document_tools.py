"""
Document Intelligence & Conversion Tools for Operation JARVIS.
Integrates Microsoft MarkItDown for multi-format file conversion to structured Markdown.
"""
from pathlib import Path
from typing import Any, Dict
from security.path_jail import path_jail, PathJailViolation

def tool_document_convert_markdown(path: str) -> Dict[str, Any]:
    """
    Converts diverse file formats (.docx, .pptx, .xlsx, .pdf, .html, .csv, .json, .xml, .txt)
    into structured Markdown using Microsoft MarkItDown.
    """
    try:
        safe_path = path_jail.validate_path(path)
        if not safe_path.exists():
            return {"ok": False, "error": f"File '{path}' does not exist."}
        if safe_path.is_dir():
            return {"ok": False, "error": f"Target '{path}' is a directory. Provide a document file path."}

        # Check file extension
        suffix = safe_path.suffix.lower()
        supported = (".docx", ".pptx", ".xlsx", ".pdf", ".html", ".htm", ".csv", ".json", ".xml", ".txt", ".md")
        if suffix not in supported:
            return {
                "ok": False,
                "error": f"Unsupported format '{suffix}'. Supported formats: {', '.join(supported)}"
            }

        # Run MarkItDown converter
        from markitdown import MarkItDown
        converter = MarkItDown()
        result = converter.convert(str(safe_path))

        markdown_text = result.text_content if hasattr(result, "text_content") else str(result)
        title = getattr(result, "title", safe_path.name) or safe_path.name

        # Truncate if exceeds 250,000 characters
        truncated = False
        if len(markdown_text) > 250000:
            markdown_text = markdown_text[:250000] + "\n\n... [Content truncated at 250,000 characters] ..."
            truncated = True

        return {
            "ok": True,
            "file_name": safe_path.name,
            "format": suffix,
            "title": title,
            "char_count": len(markdown_text),
            "line_count": len(markdown_text.splitlines()),
            "truncated": truncated,
            "markdown": markdown_text
        }

    except PathJailViolation as pe:
        return {"ok": False, "error": str(pe)}
    except Exception as e:
        return {"ok": False, "error": f"Document conversion failed: {str(e)}"}
