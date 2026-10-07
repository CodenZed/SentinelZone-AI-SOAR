"""Verify extracted files or an archive without executing application source."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile


def verify(path):
    payload = {}
    if path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                payload[item.relative_to(path).as_posix()] = item.read_bytes()
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith("/"):
                    payload[name.removeprefix("sentinelzone-ai-soar/")] = archive.read(name)
    else:
        with tarfile.open(path) as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    raise ValueError("Unexpected non-file archive member")
                payload[member.name.removeprefix("sentinelzone-ai-soar/")] = archive.extractfile(member).read()
    for name in payload:
        path_name = PurePosixPath(name)
        if path_name.is_absolute() or ".." in path_name.parts or "\\" in name:
            raise ValueError("Unsafe archive path")
        if path_name.name == ".env" or path_name.suffix in {".db", ".pyc", ".pem", ".key"} or ".git" in path_name.parts:
            raise ValueError("Private/runtime file in release")
    entries = {}
    for line in payload["SHA256SUMS"].decode().splitlines():
        digest, filename = line.split("  ", 1)
        assert hashlib.sha256(payload[filename]).hexdigest() == digest, f"Hash mismatch: {filename}"
        entries[filename] = digest
    assert set(payload) == set(entries) | {"SHA256SUMS"}, "Unlisted/missing files"
    manifest = json.loads(payload["release-manifest.json"])
    assert all(entries[name] == digest for name, digest in manifest["files"].items())
    assert set(manifest["files"]) == set(payload) - {"SHA256SUMS", "release-manifest.json"}
    print(
        json.dumps(
            {"status": "PASS", "artifact": path.name, "verified_files": len(entries), "version": manifest["version"]}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    verify(parser.parse_args().path)
