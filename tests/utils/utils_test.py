from pathlib import Path


from mujoco_mojo.utils.utils import get_checksum, get_local_ip


def test_get_checksum_returns_md5_hex(tmp_path: Path) -> None:
    """get_checksum() returns a 32-char hex string for a known file."""
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    result: str = get_checksum(f)
    assert len(result) == 32
    assert all(c in "0123456789abcdef" for c in result)


def test_get_checksum_is_deterministic(tmp_path: Path) -> None:
    """Calling get_checksum() twice on the same file returns identical hashes."""
    f = tmp_path / "data.bin"
    f.write_bytes(b"determinism check")
    assert get_checksum(f) == get_checksum(f)


def test_get_checksum_differs_for_different_content(tmp_path: Path) -> None:
    """Files with different content produce different checksums."""
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"aaa")
    b.write_bytes(b"bbb")
    assert get_checksum(a) != get_checksum(b)


def test_get_local_ip_returns_non_empty_string() -> None:
    """get_local_ip() returns a non-empty string (falls back to 127.0.0.1 on failure)."""
    ip: str = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0
