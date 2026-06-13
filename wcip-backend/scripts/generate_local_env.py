"""Generate local-only environment files with secure development secrets.

This script never prints generated secrets. It creates:

- wcip-backend/.env
- wcip-frontend/.env.local

Existing files are left untouched unless --force is provided.
"""
from __future__ import annotations

import argparse
import secrets
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = REPO_ROOT / "wcip-frontend"


def _secret() -> str:
    return secrets.token_urlsafe(48)


def _render_backend_env() -> str:
    template = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
    replacements = {
        "replace-with-generated-local-secret": _secret(),
        "replace-with-generated-local-refresh-secret": _secret(),
        "replace-with-generated-local-postgres-password": _secret(),
        "replace-with-your-api-key": "",
    }
    for old, new in replacements.items():
        template = template.replace(old, new)
    return template


def _render_frontend_env() -> str:
    return (FRONTEND_ROOT / ".env.local.example").read_text(encoding="utf-8")


def _write_env(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        print(f"Skipped {path.relative_to(REPO_ROOT)}; file already exists. Use --force to overwrite.")
        return False
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path.relative_to(REPO_ROOT)} with local-development values. Secrets hidden.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate local .env files for WCIP without printing secrets."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing local env files.",
    )
    args = parser.parse_args()

    print("Generating local development env files only. Do not reuse these secrets in production.")
    _write_env(BACKEND_ROOT / ".env", _render_backend_env(), force=args.force)
    _write_env(FRONTEND_ROOT / ".env.local", _render_frontend_env(), force=args.force)
    print("Done. Add production secrets through your deployment provider dashboards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
