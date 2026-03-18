# GCTrail Reference

**GCTrail** is a lightweight binary caching system used by **fsgc** to store historical metadata about large directories. This allows the scanner to "remember" the size and structure of a directory without fully re-scanning it on every run.

---

## 🏗 Binary Schema (Version 2)

The `.gctrail` file is stored directly within each scanned directory (if its size exceeds 100MB). It uses a fixed-length header followed by a list of top subdirectories.

### 📜 Header Format

The header uses a big-endian (`!`) binary format:

| Field | Type | Size (Bytes) | Description |
| :--- | :--- | :--- | :--- |
| `MAGIC` | `char[4]` | 4 | Magic number `GCTR`. |
| `VERSION`| `uint8` | 1 | Schema version (currently 2). |
| `TS` | `double`| 8 | Timestamp (`mtime`) of the directory. |
| `Hash` | `uint64`| 8 | Structural hash of the directory contents. |
| `Size` | `uint64`| 8 | Total size of the directory (including children). |
| `RecSize`| `uint64`| 8 | Size of reconstructible files (reserved). |
| `Noise` | `uint64`| 8 | Size of noise/temporary files (reserved). |
| `Count` | `uint32`| 4 | Number of top subdirectories included in the trail. |

### 📂 Subdirectory Entries

Each of the top 10 subdirectories (ranked by size) is stored as an entry:

| Field | Type | Size (Bytes) | Description |
| :--- | :--- | :--- | :--- |
| `Size` | `uint64`| 8 | Total size of the subdirectory. |
| `Name` | `char[255]`| 255 | UTF-8 encoded filename, null-padded to 255 bytes. |

---

## 🛡 Structural Hashing

Before **fsgc** trusts a `.gctrail` file, it calculates a **structural hash** to ensure the directory hasn't been significantly modified since the trail was last saved.

### Calculation Logic
The hash is calculated using `blake2b` (digest size: 8 bytes) from the following data:
*   The `mtime` (modification time) of the directory.
*   The `entry_count` (number of files and folders directly inside the directory).

If the current `mtime` or `entry_count` differs from the hash stored in the trail, the cache is invalidated and a full scan is triggered.

---

## 🔍 Inspecting Trails

You can view the contents of a `.gctrail` file using the `gc inspect` command:

```bash
# Inspect the current directory's trail
uvx fsgc inspect .

# Inspect with more depth to see child trails
uvx fsgc inspect . -d 3
```

### Example Output:
```text
/home/user/project - 2.4 GB (2024-03-18 14:30)
├── node_modules - 1.2 GB
├── target - 800.5 MB
└── .cache - 400.0 MB
```

---

## ⚙ Implementation Details

*   **Location:** Trails are stored as hidden `.gctrail` files in the directory they represent.
*   **Storage Threshold:** By default, trails are only persisted for directories that meet or exceed **100MB** in total size.
*   **Serialization:** The implementation uses Python's `struct` module for cross-platform binary consistency.
*   **Error Handling:** If a trail is corrupted or uses an unsupported version, **fsgc** gracefully ignores it and performs a standard scan.
