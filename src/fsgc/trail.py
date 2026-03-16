import hashlib
import struct
from dataclasses import dataclass

# Binary Schema Constants
MAGIC = b"GCTR"
VERSION = 1
# Header: Magic (4s), Version (B), TS (d), Hash (Q), Size (Q), RecSize (Q), NoiseSize (Q), Count (I)
HEADER_FORMAT = "!4sB d Q QQQ I"
FISH_FORMAT = "!Q 255s"  # Size, Filename (fixed 255 bytes)
MAX_FISH = 10  # Top 10 "Big Fish"


@dataclass
class BigFish:
    filename: str
    size: int


@dataclass
class GCTrail:
    timestamp: float
    structural_hash: int
    total_size: int
    reconstructible_size: int
    noise_size: int
    big_fish: list[BigFish]

    @classmethod
    def from_bytes(cls, data: bytes) -> "GCTrail":
        header_size = struct.calcsize(HEADER_FORMAT)
        if len(data) < header_size:
            raise ValueError("Data too short for GCTrail header")

        magic, version, ts, s_hash, size, rec_size, noise, fish_count = struct.unpack(
            HEADER_FORMAT, data[:header_size]
        )

        if magic != MAGIC:
            raise ValueError(f"Invalid magic: {magic}")
        if version != VERSION:
            raise ValueError(f"Unsupported version: {version}")

        big_fish = []
        fish_size = struct.calcsize(FISH_FORMAT)
        offset = header_size

        for _ in range(min(fish_count, MAX_FISH)):
            if offset + fish_size > len(data):
                break
            f_size, f_name_bytes = struct.unpack(FISH_FORMAT, data[offset : offset + fish_size])
            f_name = f_name_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
            big_fish.append(BigFish(filename=f_name, size=f_size))
            offset += fish_size

        return cls(
            timestamp=ts,
            structural_hash=s_hash,
            total_size=size,
            reconstructible_size=rec_size,
            noise_size=noise,
            big_fish=big_fish,
        )

    def to_bytes(self) -> bytes:
        fish_count = len(self.big_fish)
        header = struct.pack(
            HEADER_FORMAT,
            MAGIC,
            VERSION,
            self.timestamp,
            self.structural_hash,
            self.total_size,
            self.reconstructible_size,
            self.noise_size,
            fish_count,
        )

        fish_data = []
        for fish in self.big_fish[:MAX_FISH]:
            name_bytes = fish.filename.encode("utf-8")[:255].ljust(255, b"\x00")
            fish_data.append(struct.pack(FISH_FORMAT, fish.size, name_bytes))

        return header + b"".join(fish_data)

    @staticmethod
    def calculate_structural_hash(mtime: float, inode_count: int) -> int:
        """
        Calculate a stable structural hash based on mtime and directory entries.
        """
        data = struct.pack("!d Q", mtime, inode_count)
        h = hashlib.blake2b(data, digest_size=8).digest()
        return struct.unpack("!Q", h)[0]
