from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

FORMAT_VERSION = 1
CHUNK_WIDTH = 76


class CapsuleError(RuntimeError):
    """Raised when a capsule cannot be trusted or completed."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_git(*args: str, cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    )
    return completed.stdout.strip()


def project_id_for(source_url: str) -> str:
    parsed = urlparse(source_url)
    raw = f"{parsed.netloc}{parsed.path}" if parsed.scheme else source_url
    raw = raw.removesuffix(".git").strip("/")
    return re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapsuleError(f"Cannot read manifest {path}: {exc}") from exc
    if manifest.get("format") != "ponyexpress/capsule" or manifest.get("format_version") != FORMAT_VERSION:
        raise CapsuleError("Unsupported or invalid PonyExpress manifest")
    if not isinstance(manifest.get("chunks"), list) or not manifest["chunks"]:
        raise CapsuleError("Manifest has no chunks")
    return manifest


def encoded_chunk(data: bytes) -> bytes:
    # MIME-style wrapping keeps browser code views responsive and readable.
    raw = base64.b64encode(data).decode("ascii")
    return ("\n".join(raw[i : i + CHUNK_WIDTH] for i in range(0, len(raw), CHUNK_WIDTH)) + "\n").encode("ascii")


def decode_chunk(encoded: bytes, expected: dict) -> bytes:
    if sha256_bytes(encoded) != expected["encoded_sha256"]:
        raise CapsuleError(f"Chunk {expected['index']} encoded SHA-256 mismatch")
    try:
        decoded = base64.b64decode(encoded, validate=False)
    except ValueError as exc:
        raise CapsuleError(f"Chunk {expected['index']} is not valid Base64") from exc
    if len(decoded) != expected["decoded_bytes"]:
        raise CapsuleError(f"Chunk {expected['index']} byte length mismatch")
    if sha256_bytes(decoded) != expected["decoded_sha256"]:
        raise CapsuleError(f"Chunk {expected['index']} decoded SHA-256 mismatch")
    return decoded


def verify_capsule(manifest_path: Path, chunk_root: Path) -> dict:
    manifest = read_manifest(manifest_path)
    joined = hashlib.sha256()
    total = 0
    expected_indexes = list(range(len(manifest["chunks"])))
    indexes = [entry["index"] for entry in manifest["chunks"]]
    if indexes != expected_indexes:
        raise CapsuleError("Manifest chunk indexes must be contiguous and ordered from zero")
    for entry in manifest["chunks"]:
        path = chunk_root / entry["path"]
        if not path.is_file():
            raise CapsuleError(f"Missing chunk {entry['index']}: {path}")
        decoded = decode_chunk(path.read_bytes(), entry)
        joined.update(decoded)
        total += len(decoded)
    bundle = manifest["bundle"]
    if total != bundle["bytes"] or joined.hexdigest() != bundle["sha256"]:
        raise CapsuleError("Reassembled bundle checksum mismatch")
    return manifest


def publish(source_url: str, ref: str, capsule_root: Path, chunk_size: int, project_id: str | None) -> Path:
    if chunk_size < 64 * 1024:
        raise CapsuleError("Chunk size must be at least 65536 bytes")
    project_id = project_id or project_id_for(source_url)
    with tempfile.TemporaryDirectory(prefix="ponyexpress-") as temporary:
        temp = Path(temporary)
        mirror = temp / "source.git"
        bundle = temp / "payload.bundle"
        run_git("clone", "--mirror", source_url, str(mirror))
        commit = run_git("rev-parse", f"{ref}^{{commit}}", cwd=mirror)
        run_git("bundle", "create", str(bundle), "--all", cwd=mirror)
        run_git("bundle", "verify", str(bundle), cwd=mirror)

        version = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{commit[:12]}"
        version_root = capsule_root / "capsules" / project_id / "versions" / version
        if version_root.exists():
            raise CapsuleError(f"Capsule version already exists: {version_root}")
        chunks_root = version_root / "chunks"
        chunks_root.mkdir(parents=True)
        chunks: list[dict] = []
        with bundle.open("rb") as handle:
            index = 0
            while data := handle.read(chunk_size):
                filename = f"chunks/{index:06d}.b64"
                encoded = encoded_chunk(data)
                (version_root / filename).write_bytes(encoded)
                chunks.append({
                    "index": index,
                    "path": filename,
                    "encoded_sha256": sha256_bytes(encoded),
                    "decoded_sha256": sha256_bytes(data),
                    "decoded_bytes": len(data),
                })
                index += 1

        manifest = {
            "format": "ponyexpress/capsule",
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "project_id": project_id,
            "source": {"url": source_url, "ref": ref, "commit": commit},
            "bundle": {
                "kind": "full",
                "filename": "payload.bundle",
                "sha256": sha256_file(bundle),
                "bytes": bundle.stat().st_size,
            },
            "chunks": chunks,
        }
        manifest_path = version_root / "manifest.json"
        write_json(manifest_path, manifest)
        verify_capsule(manifest_path, version_root)
        latest = capsule_root / "capsules" / project_id / "latest.json"
        write_json(latest, {"format": "ponyexpress/latest", "format_version": FORMAT_VERSION,
                            "version": version, "manifest": f"versions/{version}/manifest.json"})
        return manifest_path


def receive_chunk(manifest_path: Path, cache_root: Path, index: int, source: Path) -> Path:
    manifest = read_manifest(manifest_path)
    try:
        entry = manifest["chunks"][index]
    except IndexError as exc:
        raise CapsuleError(f"Chunk index {index} is outside this manifest") from exc
    if entry["index"] != index:
        raise CapsuleError("Manifest chunk ordering is invalid")
    encoded = source.read_bytes()
    decode_chunk(encoded, entry)
    destination = cache_root / entry["path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    temporary.write_bytes(encoded)
    os.replace(temporary, destination)
    return destination


def assemble(manifest_path: Path, cache_root: Path, output: Path) -> None:
    manifest = verify_capsule(manifest_path, cache_root)
    if output.exists() and any(output.iterdir()):
        raise CapsuleError(f"Output directory is not empty: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ponyexpress-assemble-") as temporary:
        bundle = Path(temporary) / "payload.bundle"
        with bundle.open("wb") as assembled:
            for entry in manifest["chunks"]:
                assembled.write(decode_chunk((cache_root / entry["path"]).read_bytes(), entry))
        if sha256_file(bundle) != manifest["bundle"]["sha256"]:
            raise CapsuleError("Assembled bundle SHA-256 mismatch")
        run_git("clone", str(bundle), str(output))
        run_git("bundle", "verify", str(bundle), cwd=output)

