from datetime import datetime
from pathlib import Path


def _sanitize_filename(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value)


def save_html_snapshot(
    project_root: Path,
    brand_id: str,
    category_name: str,
    html: str,
    reason: str,
) -> Path:
    debug_dir = project_root / "tmp_debug" / brand_id
    debug_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_sanitize_filename(category_name)}__{_sanitize_filename(reason)}__{timestamp}.html"
    file_path = debug_dir / filename
    file_path.write_text(html, encoding="utf-8")
    return file_path
