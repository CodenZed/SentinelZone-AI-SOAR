"""CycloneDX 1.5 inventory and available license texts from the exact installed lock."""

from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import __version__

root = Path(__file__).resolve().parents[1]

components, records, notices = (
    [],
    [],
    [
        "# Third-party notices\n",
        "Dependency versions below were installed and tested from requirements.lock.txt. "
        "Only available license/notice files and metadata are copied; missing metadata is recorded, never invented. "
        "Python distributions are installed at deployment, not vendored. Container/base OS licenses are outside this Python SBOM.\n",
    ],
)
for line in (root / "requirements.lock.txt").read_text().splitlines():
    if not line or line.startswith("#"):
        continue
    name, expected = line.split("==", 1)
    distribution = metadata.distribution(name)
    if distribution.version != expected:
        raise SystemExit(f"Installed version differs from lock for {name}")
    canonical = re.sub(r"[-_.]+", "-", name).lower()
    license_name = distribution.metadata.get("License-Expression") or distribution.metadata.get("License") or "UNKNOWN"
    if len(license_name) > 200:
        license_name = "See bundled distribution metadata/license text"
    license_paths = []
    for item in distribution.files or []:
        parts = str(item).replace("\\", "/").split("/")
        filename = parts[-1]
        if ".dist-info" not in str(item) or not any(
            term in filename.upper() for term in ("LICENSE", "COPYING", "NOTICE")
        ):
            continue
        original = Path(distribution.locate_file(item))
        if not original.is_file():
            continue
        target = root / "licenses" / "dependencies" / canonical / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original.read_bytes())
        license_paths.append(target.relative_to(root).as_posix())
    # Include original metadata as authoritative license/project record when text is absent.
    if not license_paths:
        target = root / "licenses" / "dependencies" / canonical / "METADATA.txt"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(distribution.read_text("METADATA") or "Metadata unavailable", encoding="utf-8")
        license_paths.append(target.relative_to(root).as_posix())
    purl = f"pkg:pypi/{canonical}@{expected}"
    components.append(
        {
            "type": "library",
            "bom-ref": purl,
            "name": canonical,
            "version": expected,
            "purl": purl,
            "licenses": [{"license": {"name": license_name}}],
            "properties": [{"name": "sentinelzone:license-files", "value": ",".join(license_paths)}],
        }
    )
    records.append(
        {"name": canonical, "version": expected, "license_metadata": license_name, "notice_files": license_paths}
    )
    notices.append(
        f"- **{canonical} {expected}** — {license_name}. Files: " + ", ".join(f"`{p}`" for p in license_paths)
    )

lock_hash = hashlib.sha256((root / "requirements.lock.txt").read_bytes()).hexdigest()
sbom = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.5",
    "version": 1,
    "metadata": {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "component": {"type": "application", "name": "sentinelzone-ai-soar", "version": __version__},
        "properties": [{"name": "sentinelzone:requirements-sha256", "value": lock_hash}],
    },
    "components": components,
}
(root / "SBOM.cdx.json").write_text(json.dumps(sbom, indent=2) + "\n")
(root / "docs/DEPENDENCIES.json").write_text(json.dumps(records, indent=2) + "\n")
(root / "THIRD_PARTY_NOTICES.md").write_text("\n".join(notices) + "\n")
print(f"SBOM: {len(components)} pinned Python components; notices copied from installed distributions.")
