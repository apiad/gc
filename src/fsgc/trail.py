import hashlib
import struct
from dataclasses import dataclass

# Binary Schema Constants
MAGIC = b"GCTR"
VERSION = 2
# Header: Magic (4s), Version (B), TS (d), Hash (Q), Size (Q), RecSize (Q), NoiseSize (Q), Count (I)
HEADER_FORMAT = "!4sB d Q QQQ I"
SUBDIR_FORMAT = "!Q 255s"  # Size, Filename (fixed 255 bytes)
MAX_SUBDIRS = 10  # Top 10 Subdirectories


@dataclass
class TopSubdirectory:
    name: str
    size: int


@dataclass
class GCTrail:
    timestamp: float
    structural_hash: int
    total_size: int
    reconstructible_size: int
    noise_size: int
    top_subdirs: list[TopSubdirectory]

    @classmethod
    def from_bytes(cls, data: bytes) -> "GCTrail":
        header_size = struct.calcsize(HEADER_FORMAT)
        if len(data) < header_size:
            raise ValueError("Data too short for GCTrail header")

        magic, version, ts, s_hash, size, rec_size, noise, sub_count = struct.unpack(
            HEADER_FORMAT, data[:header_size]
        )

        if magic != MAGIC:
            raise ValueError(f"Invalid magic: {magic}")
        if version != VERSION:
            raise ValueError(f"Unsupported version: {version}")

        top_subdirs = []
        sub_size = struct.calcsize(SUBDIR_FORMAT)
        offset = header_size

        for _ in range(min(sub_count, MAX_SUBDIRS)):
            if offset + sub_size > len(data):
                break
            s_size, s_name_bytes = struct.unpack(SUBDIR_FORMAT, data[offset : offset + sub_size])
            s_name = s_name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
            top_subdirs.append(TopSubdirectory(name=s_name, size=s_size))
            offset += sub_size

        return cls(
            timestamp=ts,
            structural_hash=s_hash,
            total_size=size,
            reconstructible_size=rec_size,
            noise_size=noise,
            top_subdirs=top_subdirs,
        )

    def to_bytes(self) -> bytes:
        sub_count = len(self.top_subdirs)
        header = struct.pack(
            HEADER_FORMAT,
            MAGIC,
            VERSION,
            self.timestamp,
            self.structural_hash,
            self.total_size,
            self.reconstructible_size,
            self.noise_size,
            sub_count,
        )

        sub_data = []
        for sub in self.top_subdirs[:MAX_SUBDIRS]:
            name_bytes = sub.name.encode("utf-8")[:255].ljust(255, b"\x00")
            sub_data.append(struct.pack(SUBDIR_FORMAT, sub.size, name_bytes))

        return header + b"".join(sub_data)

    @staticmethod
    def calculate_structural_hash(mtime: float, inode_count: int) -> int:
        """
        Calculate a stable structural hash based on mtime and directory entries.
        """
        data = struct.pack("!d Q", mtime, inode_count)
        h = hashlib.blake2b(data, digest_size=8).digest()
        return struct.unpack("!Q", h)[0]
