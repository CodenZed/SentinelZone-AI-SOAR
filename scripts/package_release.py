"""Build complete source ZIP and deployment TAR from an explicit file allowlist.
No .git history, private config, DB, cache, environment or credential is packaged.
"""

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import __version__

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {
    "app",
    "migrations",
    "contracts",
    "config",
    "playbooks",
    "scripts",
    "tests",
    "docs",
    "fixtures",
    "licenses",
    "source",
    ".github",
    "frontend",
    "deploy",
    "examples",
}
TOP_FILES = {
    ".env.example",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    "Dockerfile",
    "LICENSE",
    "alembic.ini",
    "docker-compose.yml",
    "docker-compose.native.yml",
    "requirements.lock.txt",
    "requirements.txt",
    "pyproject.toml",
    "pytest.ini",
    "SBOM.cdx.json",
}
EXCLUDED = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "venv", ".git"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def collect():
    payload = {}
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if any(p in EXCLUDED for p in relative.parts) or not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError("Symlinks are not permitted in release")
        if (
            path.suffix in {".pyc", ".db", ".pem", ".key"}
            or path.name.startswith(".env")
            and relative.as_posix() != ".env.example"
        ):
            continue
        if (
            relative.parts[0] in DIRECTORIES
            or relative.as_posix() in TOP_FILES
            or len(relative.parts) == 1
            and path.suffix == ".md"
        ):
            payload[relative.as_posix()] = path.read_bytes()
    required = {
        "app/main.py",
        "docs/openapi.json",
        "SBOM.cdx.json",
        "VALIDATION_REPORT.md",
        "KNOWN_LIMITATIONS.md",
        "source/input-provenance.json",
        "INSTALL.md",
        "CONFIGURATION.md",
        "CONNECTORS.md",
        "SECURITY.md",
        "FINAL_REPORT.md",
        ".env.example",
    }
    if not required <= payload.keys():
        raise ValueError("Missing required release files: " + ", ".join(sorted(required - payload.keys())))
    # Narrow indicator scan. Synthetic test canaries are intentionally documented and excluded.
    findings = []
    indicators = [
        re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
        re.compile(rb"AKIA[A-Z0-9]{16}"),
        re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=]{30,}"),
    ]
    for filename, data in payload.items():
        for pattern in indicators:
            for match in pattern.finditer(data):
                if not any(x in match.group().lower() for x in (b"synthetic", b"canary")):
                    findings.append(filename)
    if findings:
        raise ValueError("Credential indicator requires review in: " + ", ".join(sorted(set(findings))))
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT.parent / "release")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "1791288000"))
    payload = collect()
    evidence = json.loads((ROOT / "docs/validation-summary.json").read_text())
    manifest = {
        "name": "sentinelzone-ai-soar",
        "version": __version__,
        "release_type": "release-candidate",
        "baseline_commit": "f49b2064d8f78d763ebc21fdf47b6da5238950c7",
        "source_date_epoch": epoch,
        "runtime_port": 8004,
        "frontend_port": 8080,
        "database": "product-owned PostgreSQL (configurable)",
        "migration_head": "0003",
        "core_dependency": "optional",
        "default_executor": "dry_run",
        "live_executors_implemented": False,
        "validation": evidence,
        "files": {n: digest(b) for n, b in sorted(payload.items())},
        "checksum_scope": "files excludes release-manifest.json and SHA256SUMS to avoid self-reference; SHA256SUMS includes manifest",
    }
    payload["release-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    payload["SHA256SUMS"] = "".join(f"{digest(b)}  {n}\n" for n, b in sorted(payload.items())).encode()
    for name in ("release-manifest.json", "SHA256SUMS"):
        (ROOT / name).write_bytes(payload[name])
    prefix = "sentinelzone-ai-soar/"
    stem = f"sentinelzone-ai-soar-v{__version__}"
    archives = [args.output / f"{stem}-source.zip", args.output / f"{stem}-deploy.tar.gz"]
    timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    with zipfile.ZipFile(archives[0], "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            info = zipfile.ZipInfo(prefix + name, timestamp.timetuple()[:6])
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with archives[1].open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in sorted(payload.items()):
                    info = tarfile.TarInfo(prefix + name)
                    info.size, info.mtime, info.mode = len(data), epoch, 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    archive.addfile(info, io.BytesIO(data))
    checksum = args.output / f"{stem}-SHA256SUMS.txt"
    checksum.write_text("".join(f"{digest(p.read_bytes())}  {p.name}\n" for p in archives))
    print(
        json.dumps(
            {
                "files": len(payload),
                "archives": [
                    {"name": p.name, "bytes": p.stat().st_size, "sha256": digest(p.read_bytes())} for p in archives
                ],
                "checksum_file": checksum.name,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
