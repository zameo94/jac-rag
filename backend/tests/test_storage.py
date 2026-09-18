import pytest

from app.services import storage
from app.services.storage import StorageError


def test_save_upload_creates_file_in_tenant_dir(tmp_path):
    path = storage.save_upload(7, "abc.txt", b"hello")

    assert path.endswith("tenant_7/abc.txt")
    with open(path, "rb") as handle:
        assert handle.read() == b"hello"


def test_save_upload_creates_directory_when_missing():
    path = storage.save_upload(99, "file.txt", b"data")

    assert "tenant_99" in path


def test_save_upload_rejects_path_traversal():
    with pytest.raises(StorageError):
        storage.save_upload(1, "../escape.txt", b"x")


def test_save_upload_rejects_nested_path():
    with pytest.raises(StorageError):
        storage.save_upload(1, "nested/file.txt", b"x")


def test_save_upload_rejects_hidden_file():
    with pytest.raises(StorageError):
        storage.save_upload(1, ".secret", b"x")


def test_save_upload_rejects_empty_name():
    with pytest.raises(StorageError):
        storage.save_upload(1, "", b"x")


def test_read_file_returns_content():
    path = storage.save_upload(3, "read.txt", b"content")

    assert storage.read_file(path) == b"content"


def test_read_file_raises_for_missing_file():
    with pytest.raises(StorageError):
        storage.read_file("/nonexistent/path/file.txt")


def test_delete_file_removes_file():
    path = storage.save_upload(4, "delete.txt", b"bye")

    storage.delete_file(path)

    with pytest.raises(StorageError):
        storage.read_file(path)


def test_delete_file_is_idempotent_for_missing_file():
    storage.delete_file("/nonexistent/path/file.txt")
