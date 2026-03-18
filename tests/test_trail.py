import time
import pytest
from fsgc.trail import MAGIC, TopSubdirectory, GCTrail


def test_trail_roundtrip():
    """
    Verify that a GCTrail can be serialized and deserialized accurately.
    """
    timestamp = time.time()
    s_hash = 1234567890
    total_size = 100 * 1024 * 1024  # 100 MB
    rec_size = 50 * 1024 * 1024  # 50 MB
    noise_size = 10 * 1024 * 1024  # 10 MB

    top_subdirs = [
        TopSubdirectory(name="node_modules", size=80 * 1024 * 1024),
        TopSubdirectory(name=".venv", size=15 * 1024 * 1024),
        TopSubdirectory(name="truncated_name" * 100, size=1024),  # Test name truncation
    ]

    trail = GCTrail(
        timestamp=timestamp,
        structural_hash=s_hash,
        total_size=total_size,
        reconstructible_size=rec_size,
        noise_size=noise_size,
        top_subdirs=top_subdirs,
    )

    data = trail.to_bytes()
    new_trail = GCTrail.from_bytes(data)

    assert new_trail.timestamp == pytest.approx(timestamp)
    assert new_trail.structural_hash == s_hash
    assert new_trail.total_size == total_size
    assert new_trail.reconstructible_size == rec_size
    assert new_trail.noise_size == noise_size
    assert len(new_trail.top_subdirs) == 3
    assert new_trail.top_subdirs[0].name == "node_modules"
    assert new_trail.top_subdirs[0].size == 80 * 1024 * 1024
    assert len(new_trail.top_subdirs[2].name) == 255  # Check truncation


def test_invalid_magic():
    with pytest.raises(ValueError, match="Invalid magic"):
        GCTrail.from_bytes(b"WRNG" + b"\x00" * 100)


def test_unsupported_version():
    with pytest.raises(ValueError, match="Unsupported version"):
        GCTrail.from_bytes(MAGIC + b"\x03" + b"\x00" * 100)


def test_stable_structural_hash():
    """
    Verify that calculate_structural_hash is stable across calls.
    """
    mtime = 123456789.0
    inode_count = 10
    h1 = GCTrail.calculate_structural_hash(mtime, inode_count)
    h2 = GCTrail.calculate_structural_hash(mtime, inode_count)
    assert h1 == h2
    assert isinstance(h1, int)
    # Ensure it's 64-bit unsigned
    assert 0 <= h1 < 2**64
