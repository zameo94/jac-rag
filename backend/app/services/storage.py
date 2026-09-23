from pathlib import Path

from app.core.config import get_settings


class StorageError(Exception):
    pass


def workspace_storage_dir(workspace_id: int) -> Path:
    settings = get_settings()
    return Path(settings.storage_dir) / f"workspace_{workspace_id}"


def save_upload(workspace_id: int, stored_name: str, content: bytes) -> str:
    if not stored_name or "/" in stored_name or "\\" in stored_name or stored_name.startswith("."):
        raise StorageError("Invalid stored file name")

    directory = workspace_storage_dir(workspace_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / stored_name
    path.write_bytes(content)
    return str(path)


def read_file(storage_path: str) -> bytes:
    path = Path(storage_path)
    if not path.is_file():
        raise StorageError(f"Stored file not found: {storage_path}")
    return path.read_bytes()


def delete_file(storage_path: str) -> None:
    path = Path(storage_path)
    if path.is_file():
        path.unlink()
