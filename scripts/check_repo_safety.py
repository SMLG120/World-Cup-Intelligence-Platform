"""Fail if generated files or likely secrets are tracked by Git."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

UNSAFE_PATH_PATTERNS = [
    re.compile(r"(^|/)__pycache__/"),
    re.compile(r"\.py[cod]$"),
    re.compile(r"(^|/)\.env($|\.)"),
    re.compile(r"\.(db|sqlite|sqlite3)$"),
    re.compile(r"\.(db|sqlite)-journal$"),
    re.compile(r"\.(pkl|joblib|onnx)$"),
    re.compile(r"(^|/)catboost_info/"),
    re.compile(r"(^|/)mlruns/"),
    re.compile(r"(^|/)wandb/"),
    re.compile(r"(^|/)artifacts/"),
    re.compile(r"(^|/)etl/data/etl_state\.json$"),
    re.compile(r"(^|/)data/cache/"),
    re.compile(r"(^|/)node_modules/"),
    re.compile(r"(^|/)\.next/"),
    re.compile(r"\.tsbuildinfo$"),
    re.compile(r"\.zip$"),
    re.compile(r"(^|/)\.DS_Store$"),
]

SAFE_TRACKED_ENV_EXAMPLES = {
    ".env.example",
    "wcip-backend/.env.example",
    "wcip-frontend/.env.local.example",
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"BEGIN (RSA |OPENSSH |PRIVATE )?PRIVATE KEY"),
    re.compile(r"AWS_SECRET_ACCESS_KEY", re.IGNORECASE),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
]
KEY_VALUE_SECRET = re.compile(
    r"\b(api[_-]?key|secret[_-]?key|password)\s*=(?!=)\s*['\"]?([^\s'\"#]*)",
    re.IGNORECASE,
)

PLACEHOLDER_MARKERS = (
    "replace-with",
    "change-me",
    "placeholder",
    "your-api-key",
    "generated-local",
    "test-secret-key",
    "<token>",
    "<admin-token>",
    "<user-token>",
)

TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".ini",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def is_env_example(path: str) -> bool:
    return path in SAFE_TRACKED_ENV_EXAMPLES or path.endswith(".env.example")


def unsafe_path_reason(path: str) -> str | None:
    if is_env_example(path):
        return None
    for pattern in UNSAFE_PATH_PATTERNS:
        if pattern.search(path):
            return pattern.pattern
    return None


def should_scan_text(path: str) -> bool:
    p = Path(path)
    if p.suffix in TEXT_SUFFIXES:
        return True
    return p.name in {"Dockerfile", "Makefile", ".gitignore"}


def is_placeholder(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in PLACEHOLDER_MARKERS)


def key_value_secret(line: str) -> str | None:
    match = KEY_VALUE_SECRET.search(line)
    if not match:
        return None
    value = match.group(2).strip()
    if not value or is_placeholder(line):
        return None
    return match.group(1)


def secret_findings(paths: list[str]) -> list[str]:
    findings: list[str] = []
    for rel in paths:
        if not should_scan_text(rel):
            continue
        path = ROOT / rel
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if key_name := key_value_secret(line):
                findings.append(f"{rel}:{lineno}: suspicious non-placeholder {key_name}")
                continue
            if is_placeholder(line):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{rel}:{lineno}: suspicious secret pattern {pattern.pattern}")
                    break
    return findings


def main() -> int:
    tracked = git_ls_files()

    unsafe_files = [
        f"{path} ({reason})"
        for path in tracked
        if (reason := unsafe_path_reason(path)) is not None
    ]
    secrets = secret_findings(tracked)

    if unsafe_files or secrets:
        print("Repository safety check failed.")
        if unsafe_files:
            print("\nTracked generated/sensitive files:")
            for item in unsafe_files:
                print(f"  - {item}")
        if secrets:
            print("\nSuspicious tracked secret strings:")
            for item in secrets:
                print(f"  - {item}")
        print("\nFix by removing generated files from the Git index and rotating any real secrets.")
        return 1

    print("Repository safety check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
