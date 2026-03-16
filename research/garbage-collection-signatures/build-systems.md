# Build System Artifact and Cache Signatures

This document outlines common patterns, locations, and characteristics of build artifacts and caches across various ecosystems. This information is intended to guide garbage collection (GC) logic for reclaiming disk space.

---

## 1. C/C++ Ecosystem

C/C++ build systems typically favor "out-of-source" builds, concentrating artifacts in a specific directory.

### Patterns & Locations
- **CMake:** 
    - `build/`, `_build/`, `out/` (Project-local)
    - `CMakeCache.txt`, `CMakeFiles/` (Inside build dir)
- **Meson:** 
    - `build/`, `builddir/` (Project-local)
    - `meson-private/`, `meson-logs/`
- **Make:**
    - `obj/`, `bin/`, `lib/` (Convention-based)
- **Ninja:**
    - `.ninja_log`, `.ninja_deps`

### Impact & Characteristics
- **Size:** Intermediate files (`.o`, `.obj`, `.pch`) can be 10x the size of the final binary. Debug builds (`-g` or `/Zi`) significantly increase size.
- **Safety:** **High**. Deleting the build directory is the standard way to perform a "clean" build. All contents are regenerable from source.
- **Aging Thresholds:** Typically manually managed. Stale if the project hasn't been touched in >30 days.

---

## 2. Java/JVM Ecosystem

Java tools use centralized global caches for dependencies and distributions to avoid redundant downloads.

### Patterns & Locations
- **Maven:** 
    - `~/.m2/repository` (Global cache)
- **Gradle:** 
    - `~/.gradle/caches` (Global dependency cache)
    - `~/.gradle/wrapper/dists` (Gradle distributions/binaries)
    - `build/` (Project-local artifacts)

### Impact & Characteristics
- **Size:** Can easily reach 5-20GB as multiple versions of libraries accumulate. Gradle `dists` are particularly large.
- **Safety:** **Safe**. 
    - *Caveat:* If `mvn install` was used for local-only projects, those specific artifacts must be re-installed from their source.
    - *Caveat:* Deleting `~/.gradle` might remove global `gradle.properties` (credentials/proxies); prefer deleting `caches/` and `wrapper/`.
- **Aging Thresholds:** Gradle (4.10+) performs automatic periodic cleanup. A 30-day threshold for unused dependencies is a safe manual heuristic.

---

## 3. JavaScript / Node.js Ecosystem

Node.js is characterized by extremely heavy local `node_modules` folders and global package caches.

### Patterns & Locations
- **Local:** `node_modules/` (Every project)
- **npm:** `~/.npm` (Global)
- **Yarn:** `~/.cache/yarn` (v1), `.yarn/cache` (v2+ project-local)
- **pnpm:** `~/.pnpm-store` (Global), `node_modules/.pnpm` (Project-local virtual store)

### Impact & Characteristics
- **Size:** `node_modules` is famously large (100MB to 1GB+ per project). Global caches often exceed 10GB.
- **Safety:**
    - **npm/Yarn:** High. Self-healing on next install.
    - **pnpm:** **Medium**. Uses hard links from the global store. Use `pnpm store prune` to safely remove orphaned packages. Manual `rm -rf` on the store can break existing `node_modules`.
- **Aging Thresholds:** 7-14 days for `node_modules` in inactive projects. Global caches can be verified/pruned monthly.

---

## 4. Rust (Cargo)

Rust has robust cache management and recently introduced built-in garbage collection.

### Patterns & Locations
- **Local:** `target/` (Project-local compiled artifacts)
- **Global:** 
    - `~/.cargo/registry/cache` (Downloaded `.crate` files)
    - `~/.cargo/registry/src` (Extracted source code)
    - `~/.cargo/git/db` (Git dependency clones)

### Impact & Characteristics
- **Size:** `target/` directories grow indefinitely with every toolchain or profile switch. Global cache can reach several GBs.
- **Safety:** **High**. `cargo clean` handles local removal. `cargo clean gc` handles global removal safely.
- **Aging Thresholds:**
    - **Built-in (Rust 1.88+):** 1 month for extracted sources, 3 months for downloads.
    - **Manual:** Use `cargo-sweep` to clean `target/` older than 30 days.

---

## 5. Go (Golang)

Go uses two primary cache types: the build cache and the module cache.

### Patterns & Locations
- **Build Cache:** `$GOCACHE` (Default: `~/.cache/go-build`)
- **Module Cache:** `$GOMODCACHE` (Default: `$GOPATH/pkg/mod`)

### Impact & Characteristics
- **Size:** `GOMODCACHE` is often the largest (10GB-50GB+) as it stores every version of every dependency ever used. `GOCACHE` is typically smaller (100MB-2GB).
- **Safety:** **High**.
    - Use `go clean -cache -modcache` for safe removal.
    - *Caution:* Manual `rm -rf` may fail due to read-only permissions Go sets on module files.
- **Aging Thresholds:** No built-in aging. Manual cleanup recommended when disk pressure is high or every 3-6 months.

---

## Summary Table for GC Implementation

| Ecosystem | Primary Path(s) | Strategy | Regenerable? |
| :--- | :--- | :--- | :--- |
| **C/C++** | `build/`, `out/` | Delete entire directory | Yes |
| **Java** | `~/.m2/repository`, `~/.gradle/caches` | Delete sub-paths or use tool commands | Yes |
| **Node.js** | `node_modules/`, `~/.npm` | Delete directory / `pnpm store prune` | Yes |
| **Rust** | `target/`, `~/.cargo` | `cargo clean`, `cargo clean gc` | Yes |
| **Go** | `$GOCACHE`, `$GOMODCACHE` | `go clean -cache -modcache` | Yes |
