"""Generate secrets in a private local env file; never print credentials."""

import argparse
import os
from pathlib import Path
import secrets

parser = argparse.ArgumentParser()
parser.add_argument("--profile", choices=["compose", "development"], default="compose")
parser.add_argument("--generate-secrets", action="store_true", help="Fill blank secrets in an already copied .env")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
target = root / ".env"
if target.exists() and not args.generate_secrets:
    raise SystemExit("Existing .env preserved. Use --generate-secrets to fill empty secret fields only.")
value = target.read_text(encoding="utf-8") if target.exists() else (root / ".env.example").read_text(encoding="utf-8")
for key in ("POSTGRES_PASSWORD", "POSTGRES_ADMIN_PASSWORD", "BOOTSTRAP_TOKEN"):
    value = value.replace(key + "=\n", key + "=" + secrets.token_urlsafe(40) + "\n")
if args.profile == "development":
    value = value.replace("APP_ENV=production", "APP_ENV=development")
    value = (
        "\n".join(
            "DATABASE_URL=sqlite:///./ai_soar.db" if line.startswith("DATABASE_URL=") else line
            for line in value.splitlines()
        )
        + "\n"
    )
if target.exists():
    temporary = root / ".env.pending"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)
    os.replace(temporary, target)
else:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(value)
print("Private .env prepared. Secrets were not printed. On Windows, restrict the file ACL to your account.")
