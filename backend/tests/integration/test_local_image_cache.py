from app.infrastructure.cache.local_image_cache import LocalImageCache


def test_delete_removes_the_file_from_disk(tmp_path):
    cache = LocalImageCache(tmp_path)
    image = tmp_path / "parts" / "3001_0.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"jpeg")

    cache.delete("parts/3001_0.jpg")

    assert not image.exists()


def test_delete_is_silent_when_the_file_is_already_gone(tmp_path):
    """Deleting a set whose image download had failed must not blow up the request."""
    LocalImageCache(tmp_path).delete("parts/never-downloaded.jpg")


def test_delete_refuses_to_escape_the_cache_root(tmp_path):
    root = tmp_path / "images"
    root.mkdir()
    outsider = tmp_path / "important.db"
    outsider.write_bytes(b"data")

    LocalImageCache(root).delete("../important.db")

    assert outsider.exists()
