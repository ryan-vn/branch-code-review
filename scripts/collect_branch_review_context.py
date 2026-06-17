#!/usr/bin/env python3
"""Collect branch-level code review context from a git repository.

The script is intentionally dependency-free. It is not a substitute for a real
code graph, but it builds a useful local impact map from git, imports, symbols,
reference hints, tests, and project manifests.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


SOURCE_SUFFIXES = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mts",
    ".cts",
    ".mjs",
    ".cjs",
    ".py",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".swift",
    ".rs",
    ".rb",
    ".php",
    ".vue",
    ".svelte",
    ".astro",
    ".mdx",
    ".graphql",
    ".gql",
    ".proto",
    ".sql",
}

JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mts", ".cts", ".mjs", ".cjs", ".vue", ".svelte", ".astro"}
PY_SUFFIXES = {".py"}
GO_SUFFIXES = {".go"}
RUST_SUFFIXES = {".rs"}

DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Gemfile",
    "Gemfile.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "composer.json",
    "composer.lock",
    "mix.exs",
    "mix.lock",
    "Package.swift",
    "*.csproj",
}

CONFIG_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "tsconfig.json",
    "jsconfig.json",
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "webpack.config.js",
    "rollup.config.js",
    "eslint.config.js",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    "prettier.config.js",
    ".prettierrc",
    "pytest.ini",
    "tox.ini",
    "mypy.ini",
    "ruff.toml",
    "Cargo.toml",
    "go.mod",
}

SHARED_SEGMENTS = {
    "components",
    "ui",
    "shared",
    "common",
    "lib",
    "utils",
    "hooks",
    "stores",
    "store",
    "services",
    "api",
    "config",
    "middleware",
    "theme",
    "styles",
    "packages",
    "pkg",
    "internal",
}

ENTRYPOINT_SEGMENTS = {
    "app",
    "pages",
    "routes",
    "router",
    "controllers",
    "handlers",
    "commands",
    "cmd",
    "screens",
    "views",
    "api",
}

TEST_SEGMENTS = {"test", "tests", "__tests__", "spec", "specs", "e2e", "integration"}
TEST_NAME_RE = re.compile(r"(^test_|[._-](test|spec|e2e)\.)", re.IGNORECASE)

GENERATED_SEGMENTS = {"dist", "build", "coverage", ".next", ".nuxt", "target", "vendor"}
GENERATED_SUFFIXES = {".snap", ".min.js", ".map"}

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:type\s+)?(?:[^'"]+?\s+from\s*)?|export\s+(?:type\s+)?(?:[^'"]*?\s+from\s*)?|require\s*\(|import\s*\()\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", re.MULTILINE)
GO_IMPORT_RE = re.compile(r'^\s*(?:"([^"]+)"|[A-Za-z_][\w.]*\s+"([^"]+)")', re.MULTILINE)
RUST_USE_RE = re.compile(r"^\s*(?:pub\s+)?(?:use|mod)\s+([^;{]+)", re.MULTILINE)

JS_NAMED_EXPORT_RE = re.compile(
    r"^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
JS_EXPORT_BLOCK_RE = re.compile(r"^\s*export\s*\{([^}]+)\}", re.MULTILINE)
PY_SYMBOL_RE = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_]\w*)", re.MULTILINE)
GO_SYMBOL_RE = re.compile(r"^\s*(?:func|type|var|const)\s+([A-Z][A-Za-z0-9_]*)", re.MULTILINE)
RUST_SYMBOL_RE = re.compile(
    r"^\s*pub(?:\([^)]*\))?\s+(?:async\s+)?(?:fn|struct|enum|trait|type|const|static)\s+([A-Za-z_]\w*)",
    re.MULTILINE,
)

# Each rule: (category, rule_id, pattern, applicable_suffixes). suffixes None = all sources.
# Rules are scoped by language to cut false positives: Python `==` is idiomatic, JS `==` is not;
# `pickle`/`yaml.load` are Python; `dangerouslySetInnerHTML`/`console.log`/`debugger` are JS.
SCAN_RULES: list[tuple[str, str, re.Pattern[str], set[str] | None]] = [
    ("security", "possible_aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}"), None),
    ("security", "possible_private_key_header", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), None),
    ("security", "possible_hardcoded_secret", re.compile(r"(?i)(api[_-]?key|secret|password|token|auth)\s*[:=]\s*['\"][^'\"]{8,}['\"]"), None),
    ("security", "possible_bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"), None),
    ("security", "dangerous_eval", re.compile(r"\beval\s*\("), None),
    ("security", "dangerous_exec", re.compile(r"\bexec\s*\("), None),
    ("security", "dangerous_pickle_loads", re.compile(r"\bpickle\.loads\s*\("), PY_SUFFIXES),
    ("security", "dangerous_yaml_load", re.compile(r"\byaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)"), PY_SUFFIXES),
    ("security", "sql_string_concat", re.compile(r"(?i)(SELECT|INSERT|UPDATE|DELETE).*(?:\+|%|f['\"]|\.format\()"), None),
    ("security", "dangerously_set_inner_html", re.compile(r"dangerouslySetInnerHTML"), JS_SUFFIXES),
    ("security", "tls_verification_disabled", re.compile(r"(?i)(rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true)"), None),
    ("bug", "empty_catch_block", re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), JS_SUFFIXES),
    ("bug", "except_pass", re.compile(r"except\s*:\s*pass\b"), PY_SUFFIXES),
    # JS loose equality `==` only — excludes `===`, `!=`, `<=`, `>=` via lookarounds. Python `==` is excluded by scope.
    ("bug", "loose_equality", re.compile(r"(?<![<>=!])==(?![=])"), JS_SUFFIXES),
    ("bug", "console_log_leftover", re.compile(r"\bconsole\.(?:log|debug|info)\s*\("), JS_SUFFIXES),
    ("bug", "debugger_statement", re.compile(r"\bdebugger\b"), JS_SUFFIXES),
    # Intentionally removed as high-false-positive noise: missing_await_hint (legal promise
    # chains), todo_fixme_hack (TODOs are not bugs), return_null_early (near-100% FP),
    # ignored_promise. Re-enable only with language scoping and a validated low FP rate.
]

REMOVED_LINE_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("bug", "removed_throw_or_raise", re.compile(r"\b(throw|raise)\b")),
    ("bug", "removed_error_return", re.compile(r"return\s+(err|error|False|null|None)\b")),
    ("bug", "removed_validation_guard", re.compile(r"if\s+.*(?:null|undefined|None|empty|length|size|auth|permission|valid)")),
    ("bug", "removed_catch_handler", re.compile(r"\bcatch\b|\bexcept\b")),
]


def run_git(args: list[str], cwd: Path, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def repo_root(cwd: Path) -> Path:
    root = run_git(["rev-parse", "--show-toplevel"], cwd)
    return Path(root)


def current_branch(repo: Path) -> str:
    return run_git(["branch", "--show-current"], repo, check=False) or "(detached)"


def infer_branch_start(repo: Path, branch: str) -> tuple[str, str]:
    if branch == "(detached)":
        raise SystemExit("Could not infer branch start in detached HEAD. Re-run with --start <commit-or-ref>.")

    reflog_ref = f"refs/heads/{branch}"
    raw = run_git(["reflog", "show", "--format=%H", reflog_ref], repo, check=False)
    hashes = [line.strip() for line in raw.splitlines() if line.strip()]
    if hashes:
        return hashes[-1], f"oldest reflog entry for {reflog_ref}"

    raise SystemExit(
        "Could not infer current branch start from reflog. "
        "Re-run with --start <branch-start-commit-or-ref>. "
        "This script does not fall back to the default branch."
    )


def resolve_start(repo: Path, branch: str, start_arg: str | None, start_mode: str) -> tuple[str, str]:
    if start_arg:
        return start_arg, "provided via --start"
    if start_mode.startswith("merge-base-with="):
        base = start_mode.split("=", 1)[1].strip()
        if not base:
            raise SystemExit("--start-mode merge-base-with= requires a ref, e.g. origin/main")
        merge_base = run_git(["merge-base", "HEAD", base], repo)
        return merge_base, f"merge-base of HEAD and {base}"
    if start_mode != "reflog":
        raise SystemExit(f"Unknown --start-mode: {start_mode}. Use reflog or merge-base-with=<ref>.")
    return infer_branch_start(repo, branch)


def reflog_health(repo: Path, branch: str, start: str) -> dict[str, Any] | None:
    """Detect possible reflog truncation. `git gc` prunes reflog entries (default 90/30
    days), which makes the inferred branch start too recent and silently omits early
    commits from the review range. Surface entry count + warnings so the reviewer can
    re-run with an explicit --start when the branch predates the surviving reflog."""
    if branch == "(detached)":
        return None
    reflog_ref = f"refs/heads/{branch}"
    raw = run_git(["reflog", "show", "--format=%H|%ct", reflog_ref], repo, check=False)
    entries: list[list[str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        entries.append(line.split("|", 1))
    if not entries:
        return None
    count = len(entries)
    oldest_sha = entries[-1][0]
    oldest_ts = int(entries[-1][1]) if entries[-1][1].isdigit() else 0
    range_raw = run_git(["rev-list", "--count", f"{start}..HEAD"], repo, check=False)
    range_count = int(range_raw.strip()) if range_raw.strip().isdigit() else 0
    warnings: list[str] = []
    if count <= 2:
        warnings.append(
            "Reflog has very few entries for this branch; git gc may have pruned it and the "
            "inferred start could omit early commits. Re-run with --start <older-commit> if "
            "the branch predates these entries."
        )
    if range_count > 0 and count < range_count:
        warnings.append(
            f"Reflog entries ({count}) are fewer than commits in {start}..HEAD ({range_count}); "
            "the reflog may be truncated. Verify the start commit covers the whole branch."
        )
    return {
        "reflog_entries": count,
        "oldest_reflog_sha": oldest_sha,
        "oldest_reflog_unix_time": oldest_ts,
        "range_commit_count": range_count,
        "warnings": warnings,
    }


def collect_diff_text(repo: Path, start: str, include_working_tree: bool) -> str:
    # `git diff <start>` compares the working tree (committed-since-start + staged + unstaged)
    # against <start> as ONE coherent diff, so each file appears in a single `+++ b/file`
    # segment. Concatenating `start..HEAD` + `--cached` + unstaged would emit multiple
    # segments for the same file and corrupt line numbers in parse_added_lines.
    if include_working_tree:
        return run_git(["diff", "-U3", start], repo, check=False)
    return run_git(["diff", "-U3", f"{start}..HEAD"], repo, check=False)


def parse_added_lines(diff_text: str) -> dict[str, list[tuple[int, str]]]:
    result: dict[str, list[tuple[int, str]]] = defaultdict(list)
    current_file: str | None = None
    new_line_no = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            continue
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file == "/dev/null":
                current_file = None
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            new_line_no = int(match.group(1)) if match else 0
            continue
        if not current_file:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result[current_file].append((new_line_no, line[1:]))
            new_line_no += 1
        elif line.startswith(" "):
            new_line_no += 1
    return dict(result)


def parse_removed_lines(diff_text: str) -> dict[str, list[tuple[int, str]]]:
    result: dict[str, list[tuple[int, str]]] = defaultdict(list)
    current_file: str | None = None
    old_line_no = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            continue
        if line.startswith("--- a/"):
            current_file = line[6:].strip()
            if current_file == "/dev/null":
                current_file = None
            continue
        if line.startswith("@@"):
            match = re.search(r"-(\d+)", line)
            old_line_no = int(match.group(1)) if match else 0
            continue
        if not current_file:
            continue
        if line.startswith("-") and not line.startswith("---"):
            result[current_file].append((old_line_no, line[1:]))
            old_line_no += 1
        elif line.startswith(" "):
            old_line_no += 1
    return dict(result)


def scan_removed_lines(removed_lines_by_file: dict[str, list[tuple[int, str]]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, lines in sorted(removed_lines_by_file.items()):
        if not is_source_file(path):
            continue
        for line_no, content in lines:
            stripped = content.strip()
            if not stripped:
                continue
            for category, rule_id, pattern in REMOVED_LINE_RULES:
                if pattern.search(content):
                    findings.append(
                        {
                            "path": path,
                            "line": line_no,
                            "category": category,
                            "rule": rule_id,
                            "snippet": stripped[:200],
                            "change": "removed",
                        }
                    )
    return findings


def collect_line_changes(
    repo: Path,
    start: str,
    analysis_files: list[dict[str, Any]],
    include_working_tree: bool,
) -> tuple[dict[str, list[tuple[int, str]]], dict[str, list[tuple[int, str]]]]:
    diff_text = collect_diff_text(repo, start, include_working_tree)
    added = parse_added_lines(diff_text)
    removed = parse_removed_lines(diff_text)
    for item in analysis_files:
        if item["status"][0] == "D":
            continue
        path = item["path"]
        if "untracked" not in item.get("sources", []):
            continue
        if not (is_source_file(path) or is_config_file(path) or is_dependency_file(path)):
            continue
        text = read_head_file(repo, path)
        if text:
            added[path] = [(index + 1, line) for index, line in enumerate(text.splitlines())]
    return added, removed


def scan_added_lines(added_lines_by_file: dict[str, list[tuple[int, str]]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, lines in sorted(added_lines_by_file.items()):
        if not (is_source_file(path) or is_config_file(path) or is_dependency_file(path)):
            continue
        suffix = PurePosixPath(path).suffix.lower()
        for line_no, content in lines:
            stripped = content.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("#"):
                continue
            for category, rule_id, pattern, applicability in SCAN_RULES:
                if applicability is not None and suffix not in applicability:
                    continue
                if pattern.search(content):
                    findings.append(
                        {
                            "path": path,
                            "line": line_no,
                            "category": category,
                            "rule": rule_id,
                            "snippet": stripped[:200],
                            "change": "added",
                        }
                    )
    return findings


def scan_line_changes(
    added_lines_by_file: dict[str, list[tuple[int, str]]],
    removed_lines_by_file: dict[str, list[tuple[int, str]]],
) -> list[dict[str, Any]]:
    return scan_added_lines(added_lines_by_file) + scan_removed_lines(removed_lines_by_file)


def build_bug_hunt_queue(risk_targets: list[dict[str, Any]], pattern_findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bug_hint_counts: dict[str, int] = defaultdict(int)
    security_hint_counts: dict[str, int] = defaultdict(int)
    for finding in pattern_findings:
        if finding["category"] == "bug":
            bug_hint_counts[finding["path"]] += 1
        elif finding["category"] == "security":
            security_hint_counts[finding["path"]] += 1

    queue: list[dict[str, Any]] = []
    for target in risk_targets:
        path = target["path"]
        bug_hints = bug_hint_counts.get(path, 0)
        security_hints = security_hint_counts.get(path, 0)
        bug_hunt_score = target["score"] + bug_hints * 3 + security_hints * 4
        queue.append(
            {
                **target,
                "bug_hint_count": bug_hints,
                "security_hint_count": security_hints,
                "bug_hunt_score": bug_hunt_score,
            }
        )
    queue.sort(key=lambda value: (-value["bug_hunt_score"], -value["bug_hint_count"], value["path"]))
    return queue


def parse_name_status(raw: str, source: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        if len(parts) >= 3 and (status.startswith("R") or status.startswith("C")):
            files.append({"status": status, "old_path": parts[1], "path": parts[2], "sources": [source]})
        elif len(parts) >= 2:
            files.append({"status": status, "path": parts[1], "sources": [source]})
    return files


def parse_numstat(raw: str) -> dict[str, dict[str, str]]:
    stats: dict[str, dict[str, str]] = {}
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted, path = parts[0], parts[1], parts[-1]
        stats[path] = {"added": added, "deleted": deleted}
    return stats


def merge_file_entries(groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for item in group:
            path = item["path"]
            if path not in merged:
                merged[path] = dict(item)
                merged[path]["sources"] = list(item.get("sources", []))
                continue
            current = merged[path]
            current["sources"] = sorted(set(current.get("sources", [])) | set(item.get("sources", [])))
            if current.get("status") == "M" and item.get("status") != "M":
                current["status"] = item["status"]
            if item.get("old_path") and not current.get("old_path"):
                current["old_path"] = item["old_path"]
    return sorted(merged.values(), key=lambda value: value["path"])


def path_segments(path: str) -> set[str]:
    return {part.lower() for part in PurePosixPath(path).parts}


def name_matches(patterns: set[str], name: str) -> bool:
    if name in patterns:
        return True
    return any(pattern.startswith("*.") and name.endswith(pattern[1:]) for pattern in patterns)


def is_dependency_file(path: str) -> bool:
    return name_matches(DEPENDENCY_FILES, PurePosixPath(path).name)


def is_config_file(path: str) -> bool:
    p = PurePosixPath(path)
    return p.name in CONFIG_FILENAMES or ".github/workflows" in path or p.suffix in {".yml", ".yaml"} and "workflow" in path


def is_shared_file(path: str) -> bool:
    segments = path_segments(path)
    name = PurePosixPath(path).name.lower()
    return bool(segments & SHARED_SEGMENTS) or name in {"index.ts", "index.tsx", "index.js", "index.jsx", "__init__.py"}


def is_source_file(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES


def is_test_file(path: str) -> bool:
    p = PurePosixPath(path)
    return bool(path_segments(path) & TEST_SEGMENTS) or bool(TEST_NAME_RE.search(p.name))


def is_entrypoint_file(path: str) -> bool:
    p = PurePosixPath(path)
    segments = path_segments(path)
    if segments & ENTRYPOINT_SEGMENTS:
        return True
    return p.name in {"page.tsx", "page.jsx", "page.ts", "route.ts", "route.js", "layout.tsx", "main.ts", "main.go", "main.rs"}


def is_migration_file(path: str) -> bool:
    segments = path_segments(path)
    return "migration" in segments or "migrations" in segments or PurePosixPath(path).suffix.lower() == ".sql"


def is_generated_file(path: str) -> bool:
    segments = path_segments(path)
    name = PurePosixPath(path).name
    return bool(segments & GENERATED_SEGMENTS) or any(name.endswith(suffix) for suffix in GENERATED_SUFFIXES)


def read_head_file(repo: Path, path: str) -> str:
    full = repo / path
    if not full.exists() or not full.is_file():
        return ""
    try:
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_git_file(repo: Path, ref: str, path: str) -> str:
    if not path:
        return ""
    return run_git(["show", f"{ref}:{path}"], repo, check=False)


def list_source_files(repo: Path, include_untracked: bool) -> list[str]:
    raw = run_git(["ls-files"], repo)
    files = {line for line in raw.splitlines() if is_source_file(line)}
    if include_untracked:
        untracked = run_git(["ls-files", "--others", "--exclude-standard"], repo, check=False)
        files.update(line for line in untracked.splitlines() if is_source_file(line))
    return sorted(files)


def strip_json_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(^|\s)//.*$", "", text, flags=re.MULTILINE)


def read_json_file(repo: Path, path: str) -> dict[str, Any]:
    try:
        return json.loads(strip_json_comments(read_head_file(repo, path)))
    except Exception:
        return {}


def read_json_at_ref(repo: Path, ref: str, path: str) -> dict[str, Any]:
    try:
        return json.loads(strip_json_comments(read_git_file(repo, ref, path)))
    except Exception:
        return {}


def js_aliases(repo: Path) -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    for config in ("tsconfig.json", "jsconfig.json"):
        data = read_json_file(repo, config)
        compiler = data.get("compilerOptions", {}) if isinstance(data, dict) else {}
        base_url = compiler.get("baseUrl", ".")
        paths = compiler.get("paths", {})
        if not isinstance(paths, dict):
            continue
        for key, values in paths.items():
            if not isinstance(values, list) or not values:
                continue
            target = str(values[0])
            key_prefix = key.split("*", 1)[0]
            target_prefix = target.split("*", 1)[0]
            aliases.append((key_prefix, str(PurePosixPath(base_url) / target_prefix).strip("./")))
    return aliases


def go_module_name(repo: Path) -> str:
    text = read_head_file(repo, "go.mod")
    match = re.search(r"^module\s+(\S+)", text, re.MULTILINE)
    return match.group(1) if match else ""


def python_module_index(source_files: list[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for path in source_files:
        p = PurePosixPath(path)
        if p.suffix != ".py":
            continue
        no_suffix = p.with_suffix("")
        candidates = [str(no_suffix).replace("/", ".")]
        parts = list(no_suffix.parts)
        for marker in ("src", "lib"):
            if marker in parts:
                candidates.append(".".join(parts[parts.index(marker) + 1 :]))
        if p.name == "__init__.py":
            package = ".".join(parts[:-1])
            candidates.append(package)
            if "src" in parts:
                candidates.append(".".join(parts[parts.index("src") + 1 : -1]))
        for candidate in candidates:
            if candidate:
                index[candidate] = path
    return index


def normalize_posix(path: PurePosixPath) -> str:
    parts: list[str] = []
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def resolve_path_like(base: str, source_set: set[str]) -> str | None:
    base = base.strip("./")
    candidates = [base]
    for suffix in JS_SUFFIXES | PY_SUFFIXES | GO_SUFFIXES | RUST_SUFFIXES:
        candidates.append(base + suffix)
    for suffix in JS_SUFFIXES | PY_SUFFIXES:
        candidates.append(f"{base}/index{suffix}")
    if base:
        candidates.append(f"{base}/__init__.py")
    for candidate in candidates:
        if candidate in source_set:
            return candidate
    return None


def resolve_import(
    importer: str,
    spec: str,
    source_set: set[str],
    aliases: list[tuple[str, str]],
    py_index: dict[str, str],
    go_module: str,
) -> str | None:
    spec = spec.strip()
    if not spec:
        return None
    if spec.startswith("."):
        base = normalize_posix(PurePosixPath(importer).parent / spec)
        return resolve_path_like(base, source_set)
    for prefix, target_prefix in aliases:
        if prefix and spec.startswith(prefix):
            rest = spec[len(prefix) :]
            resolved = resolve_path_like(str(PurePosixPath(target_prefix) / rest), source_set)
            if resolved:
                return resolved
    if spec in py_index:
        return py_index[spec]
    if go_module and spec.startswith(go_module + "/"):
        resolved = resolve_path_like(spec[len(go_module) + 1 :], source_set)
        if resolved:
            return resolved
    return resolve_path_like(spec, source_set)


def imports_for_text(path: str, text: str) -> list[str]:
    suffix = PurePosixPath(path).suffix.lower()
    imports: set[str] = set()
    if suffix in JS_SUFFIXES:
        imports.update(JS_IMPORT_RE.findall(text))
    elif suffix in PY_SUFFIXES:
        for first, second in PY_IMPORT_RE.findall(text):
            imports.add(first or second)
    elif suffix in GO_SUFFIXES:
        in_block = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("import ("):
                in_block = True
                continue
            if in_block and stripped == ")":
                in_block = False
                continue
            if stripped.startswith("import "):
                stripped = stripped[len("import ") :].strip()
            if in_block or stripped.startswith('"') or '"' in stripped:
                match = GO_IMPORT_RE.search(stripped)
                if match:
                    imports.add(match.group(1) or match.group(2))
    elif suffix in RUST_SUFFIXES:
        imports.update(value.strip() for value in RUST_USE_RE.findall(text))
    return sorted(value for value in imports if value)


def imports_for_file(repo: Path, path: str) -> list[str]:
    if not is_source_file(path):
        return []
    return imports_for_text(path, read_head_file(repo, path))


def build_import_impact(repo: Path, source_files: list[str]) -> dict[str, Any]:
    source_set = set(source_files)
    aliases = js_aliases(repo)
    py_index = python_module_index(source_files)
    go_module = go_module_name(repo)
    imports: dict[str, list[str]] = {}
    resolved_imports: dict[str, list[dict[str, str]]] = {}
    direct_importers: dict[str, list[str]] = defaultdict(list)

    for source in source_files:
        specs = imports_for_file(repo, source)
        imports[source] = specs
        for spec in specs:
            target = resolve_import(source, spec, source_set, aliases, py_index, go_module)
            if target:
                resolved_imports.setdefault(source, []).append({"specifier": spec, "target": target})
                direct_importers[target].append(source)

    return {
        "aliases": [{"prefix": prefix, "target_prefix": target} for prefix, target in aliases],
        "go_module": go_module,
        "imports": imports,
        "resolved_imports": resolved_imports,
        "direct_importers": {path: sorted(set(importers)) for path, importers in direct_importers.items()},
    }


def possible_import_tokens(path: str) -> set[str]:
    p = PurePosixPath(path)
    no_suffix = str(p.with_suffix(""))
    tokens = {path, no_suffix, "./" + no_suffix, "../" + no_suffix, p.stem, "./" + p.stem, "../" + p.stem}
    if p.name.startswith("index.") or p.name == "__init__.py":
        tokens.add(str(p.parent))
    return {token.replace("\\", "/") for token in tokens if token and token != "."}


def symbols_for_text(path: str, text: str) -> list[str]:
    suffix = PurePosixPath(path).suffix.lower()
    symbols: set[str] = set()
    if suffix in JS_SUFFIXES:
        symbols.update(JS_NAMED_EXPORT_RE.findall(text))
        for block in JS_EXPORT_BLOCK_RE.findall(text):
            for raw_name in block.split(","):
                name = raw_name.strip().split(" as ")[-1].strip()
                if name and name != "default":
                    symbols.add(name)
    elif suffix in PY_SUFFIXES:
        symbols.update(name for name in PY_SYMBOL_RE.findall(text) if not name.startswith("_"))
    elif suffix in GO_SUFFIXES:
        symbols.update(GO_SYMBOL_RE.findall(text))
    elif suffix in RUST_SUFFIXES:
        symbols.update(RUST_SYMBOL_RE.findall(text))
    return sorted(symbols)


def symbol_delta(repo: Path, start: str, item: dict[str, Any]) -> dict[str, Any]:
    path = item["path"]
    old_path = item.get("old_path", path)
    old_symbols = set(symbols_for_text(old_path, read_git_file(repo, start, old_path)))
    new_symbols = set(symbols_for_text(path, read_head_file(repo, path)))
    return {
        "old_path": old_path,
        "path": path,
        "old": sorted(old_symbols),
        "current": sorted(new_symbols),
        "added": sorted(new_symbols - old_symbols),
        "removed": sorted(old_symbols - new_symbols),
    }


def file_content_index(repo: Path, source_files: list[str], max_files: int = 5000) -> dict[str, str]:
    index: dict[str, str] = {}
    for path in source_files[:max_files]:
        text = read_head_file(repo, path)
        if text:
            index[path] = text
    return index


def reference_hints_for_symbols(
    changed_items: list[dict[str, Any]],
    symbol_deltas: dict[str, dict[str, Any]],
    content_index: dict[str, str],
    cap_per_file: int = 20,
) -> dict[str, list[str]]:
    hints: dict[str, list[str]] = {}
    for item in changed_items:
        path = item["path"]
        symbols = list(symbol_deltas.get(path, {}).get("current", [])) + list(symbol_deltas.get(path, {}).get("removed", []))
        symbols = [symbol for symbol in symbols if len(symbol) >= 4][:12]
        if not symbols:
            continue
        found: list[str] = []
        patterns = [re.compile(rf"\b{re.escape(symbol)}\b") for symbol in symbols]
        for source, text in content_index.items():
            if source == path:
                continue
            if any(pattern.search(text) for pattern in patterns):
                found.append(source)
                if len(found) >= cap_per_file:
                    break
        if found:
            hints[path] = found
    return hints


def deleted_reference_hints(
    deleted_items: list[dict[str, Any]],
    content_index: dict[str, str],
    cap_per_file: int = 25,
) -> dict[str, list[str]]:
    hints: dict[str, list[str]] = {}
    for item in deleted_items:
        old_path = item.get("old_path", item["path"])
        tokens = [token for token in possible_import_tokens(old_path) if len(token) >= 4]
        found: list[str] = []
        for source, text in content_index.items():
            if source == item["path"]:
                continue
            if any(token in text for token in tokens):
                found.append(source)
                if len(found) >= cap_per_file:
                    break
        if found:
            hints[old_path] = found
    return hints


def group_by_status(files: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for item in files:
        status = item["status"][0]
        value = item["path"]
        if "old_path" in item:
            value = f"{item['old_path']} -> {item['path']}"
        suffix = ""
        if item.get("sources"):
            suffix = f" ({', '.join(item['sources'])})"
        grouped[status].append(value + suffix)
    return dict(grouped)


def new_directories(files: list[dict[str, Any]]) -> list[str]:
    dirs = set()
    for item in files:
        if item["status"][0] == "A":
            parent = str(PurePosixPath(item["path"]).parent)
            if parent != ".":
                dirs.add(parent)
    return sorted(dirs)


def find_test_neighbors(path: str, all_files: list[str], content_index: dict[str, str]) -> list[str]:
    p = PurePosixPath(path)
    stem = p.stem
    all_set = set(all_files)
    candidates = {
        str(p.with_name(f"{stem}.test{p.suffix}")),
        str(p.with_name(f"{stem}.spec{p.suffix}")),
        str(p.parent / "__tests__" / f"{stem}.test{p.suffix}"),
        str(PurePosixPath("tests") / p),
        str(PurePosixPath("test") / p),
    }
    if p.suffix == ".py":
        candidates.add(str(p.with_name(f"test_{stem}.py")))
        candidates.add(str(PurePosixPath("tests") / p.with_name(f"test_{stem}.py")))
    existing = sorted(candidate for candidate in candidates if candidate in all_set)
    if existing:
        return existing

    token_candidates = {stem, str(p.with_suffix("")), p.name}
    found: list[str] = []
    for source, text in content_index.items():
        if not is_test_file(source):
            continue
        if any(token in text for token in token_candidates):
            found.append(source)
    return sorted(set(found))[:10]


def detect_test_commands(repo: Path) -> list[str]:
    commands: list[str] = []
    package = read_json_file(repo, "package.json")
    if package:
        scripts = package.get("scripts", {})
        if isinstance(scripts, dict):
            if (repo / "pnpm-lock.yaml").exists():
                runner = "pnpm"
            elif (repo / "yarn.lock").exists():
                runner = "yarn"
            elif (repo / "bun.lock").exists() or (repo / "bun.lockb").exists():
                runner = "bun"
            else:
                runner = "npm run"
            for script in ("test", "test:unit", "test:e2e", "lint", "typecheck", "tsc", "build"):
                if script in scripts:
                    commands.append(f"{runner} {script}" if runner != "npm run" else f"npm run {script}")
    if (repo / "pyproject.toml").exists() or (repo / "pytest.ini").exists() or any((repo / name).exists() for name in ("requirements.txt", "tox.ini")):
        commands.append("python -m pytest")
    if (repo / "go.mod").exists():
        commands.append("go test ./...")
    if (repo / "Cargo.toml").exists():
        commands.append("cargo test")
        commands.append("cargo clippy --all-targets")
    makefile = read_head_file(repo, "Makefile")
    if makefile:
        for target in ("test", "lint", "check"):
            if re.search(rf"^{target}:", makefile, re.MULTILINE):
                commands.append(f"make {target}")
    return sorted(dict.fromkeys(commands))


def compare_package_dependencies(repo: Path, start: str, changed_paths: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    sections = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
    for path in changed_paths:
        if PurePosixPath(path).name != "package.json":
            continue
        old = read_json_at_ref(repo, start, path)
        new = read_json_file(repo, path)
        if not old and not new:
            continue
        package_result: dict[str, Any] = {}
        for section in sections:
            old_deps = old.get(section, {}) if isinstance(old, dict) else {}
            new_deps = new.get(section, {}) if isinstance(new, dict) else {}
            if not isinstance(old_deps, dict) or not isinstance(new_deps, dict):
                continue
            names = sorted(set(old_deps) | set(new_deps))
            changes = []
            for name in names:
                if old_deps.get(name) != new_deps.get(name):
                    changes.append({"name": name, "before": old_deps.get(name), "after": new_deps.get(name)})
            if changes:
                package_result[section] = changes
        if package_result:
            result[path] = package_result
    return result


def dependency_consistency(changed_paths: list[str]) -> list[str]:
    warnings: list[str] = []
    changed = set(changed_paths)
    package_manifests = [path for path in changed if PurePosixPath(path).name == "package.json"]
    lockfiles = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb"}
    if package_manifests and not any(PurePosixPath(path).name in lockfiles for path in changed):
        warnings.append("package.json changed without a recognized JS lockfile change.")
    py_manifests = {"pyproject.toml", "requirements.txt", "requirements-dev.txt", "Pipfile"}
    py_locks = {"poetry.lock", "uv.lock", "Pipfile.lock"}
    if any(PurePosixPath(path).name in py_manifests for path in changed) and not any(PurePosixPath(path).name in py_locks for path in changed):
        warnings.append("Python dependency manifest changed without a recognized lockfile change.")
    if "Cargo.toml" in {PurePosixPath(path).name for path in changed} and "Cargo.lock" not in {PurePosixPath(path).name for path in changed}:
        warnings.append("Cargo.toml changed without Cargo.lock.")
    return warnings


def classify_file(path: str) -> list[str]:
    categories: list[str] = []
    if is_dependency_file(path):
        categories.append("dependency")
    if is_config_file(path):
        categories.append("config")
    if is_source_file(path):
        categories.append("source")
    if is_shared_file(path):
        categories.append("shared")
    if is_entrypoint_file(path):
        categories.append("entrypoint")
    if is_migration_file(path):
        categories.append("migration")
    if is_test_file(path):
        categories.append("test")
    if is_generated_file(path):
        categories.append("generated")
    return categories or ["other"]


def risk_for_file(
    item: dict[str, Any],
    direct_importers: dict[str, list[str]],
    symbol_refs: dict[str, list[str]],
    test_neighbors: dict[str, list[str]],
    deleted_refs: dict[str, list[str]],
    symbol_deltas: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    path = item["path"]
    status = item["status"][0]
    categories = classify_file(path)
    score = 0
    reasons: list[str] = []

    if status == "D":
        score += 5
        reasons.append("deleted file")
    elif status == "R":
        score += 3
        reasons.append("renamed file")
    elif status == "A":
        score += 2
        reasons.append("added file")

    weights = {
        "dependency": 5,
        "migration": 5,
        "shared": 4,
        "entrypoint": 3,
        "config": 3,
        "source": 1,
        "generated": -2,
        "test": -1,
    }
    for category in categories:
        score += weights.get(category, 0)
        if category in {"dependency", "migration", "shared", "entrypoint", "config"}:
            reasons.append(f"{category} surface")

    importer_count = len(direct_importers.get(path, []))
    if importer_count:
        score += min(6, importer_count)
        reasons.append(f"{importer_count} direct importer(s)")

    ref_count = len(symbol_refs.get(path, []))
    if ref_count:
        score += min(4, ref_count)
        reasons.append(f"{ref_count} symbol reference hint(s)")

    old_path = item.get("old_path", path)
    deleted_ref_count = len(deleted_refs.get(old_path, []))
    if deleted_ref_count:
        score += min(6, deleted_ref_count)
        reasons.append(f"{deleted_ref_count} deleted-path reference hint(s)")

    delta = symbol_deltas.get(path, {})
    if delta.get("removed"):
        score += 4
        reasons.append("removed public symbol candidate(s)")
    if delta.get("added") and status != "A":
        score += 1
        reasons.append("new public symbol candidate(s)")

    if "source" in categories and "test" not in categories and not test_neighbors.get(path):
        score += 2
        reasons.append("no nearby/importing test detected")

    if "unstaged" in item.get("sources", []) or "staged" in item.get("sources", []) or "untracked" in item.get("sources", []):
        score += 1
        reasons.append("working tree change")

    return {
        "path": path,
        "status": item["status"],
        "categories": categories,
        "score": score,
        "reasons": sorted(set(reasons)),
        "direct_importers": direct_importers.get(path, [])[:20],
        "reference_hints": symbol_refs.get(path, [])[:20],
        "test_neighbors": test_neighbors.get(path, []),
    }


def markdown_list(values: list[str], empty: str = "None detected.") -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- `{value}`" for value in values)


def markdown_plain_list(values: list[str], empty: str = "None detected.") -> str:
    if not values:
        return f"- {empty}"
    return "\n".join(f"- {value}" for value in values)


def markdown_table(rows: list[list[str]], headers: list[str]) -> str:
    if not rows:
        return "- None detected."
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(cell.replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(lines)


def build_report(data: dict[str, Any]) -> str:
    files = data["analysis_files"]
    committed_files = data["committed_files"]
    grouped = group_by_status(files)
    committed_grouped = group_by_status(committed_files)
    changed_paths = [item["path"] for item in files if item["status"][0] != "D"]
    health = data.get("reflog_health") or {}
    reflog_health_lines: list[str] = []
    if health:
        reflog_health_lines = [
            "## Reflog Health",
            "",
            f"- Reflog entries: `{health.get('reflog_entries')}`",
            f"- Oldest reflog entry: `{health.get('oldest_reflog_sha')}`",
            f"- Commits in range: `{health.get('range_commit_count')}`",
        ]
        for warning in health.get("warnings", []):
            reflog_health_lines.append(f"- WARNING: {warning}")
        reflog_health_lines.append("")
    risk_rows = [
        [
            str(target["score"]),
            f"`{target['path']}`",
            ", ".join(target["categories"]),
            "; ".join(target["reasons"]),
        ]
        for target in data["risk_targets"][:25]
    ]
    bug_hunt_rows = [
        [
            str(target["bug_hunt_score"]),
            f"`{target['path']}`",
            str(target["bug_hint_count"]),
            str(target["security_hint_count"]),
            "; ".join(target["reasons"][:3]),
        ]
        for target in data["bug_hunt_queue"][:25]
    ]
    bug_findings = [finding for finding in data["pattern_findings"] if finding["category"] == "bug"]
    security_findings = [finding for finding in data["pattern_findings"] if finding["category"] == "security"]

    lines = [
        "# Branch Review Context",
        "",
        "## Branch",
        "",
        f"- Repository: `{data['repo']}`",
        f"- Branch start: `{data['start']}`",
        f"- Start inference: {data['start_source']}",
        f"- Start mode: `{data['start_mode']}`",
        f"- Head: `{data['head']}`",
        f"- Current branch: `{data['branch']}`",
        f"- Range: `{data['range']}`",
        f"- Include working tree in analysis: `{data['include_working_tree']}`",
        f"- Working tree status: `{data['working_tree_status'] or 'clean'}`",
        "",
        *reflog_health_lines,
        "## Commits Since Branch Start",
        "",
        data["commits"] or "No commits detected in range.",
        "",
        "## Committed File Inventory",
        "",
        f"- Added: {len(committed_grouped.get('A', []))}",
        f"- Modified: {len(committed_grouped.get('M', []))}",
        f"- Deleted: {len(committed_grouped.get('D', []))}",
        f"- Renamed: {len(committed_grouped.get('R', []))}",
        "",
        "### Added Files",
        "",
        markdown_list(committed_grouped.get("A", [])),
        "",
        "### Modified Files",
        "",
        markdown_list(committed_grouped.get("M", [])),
        "",
        "### Deleted Files",
        "",
        markdown_list(committed_grouped.get("D", [])),
        "",
        "### Renamed Files",
        "",
        markdown_list(committed_grouped.get("R", [])),
        "",
        "## Working Tree Inventory",
        "",
        "### Staged Files",
        "",
        markdown_list([item["path"] for item in data["staged_files"]]),
        "",
        "### Unstaged Files",
        "",
        markdown_list([item["path"] for item in data["unstaged_files"]]),
        "",
        "### Untracked Files",
        "",
        markdown_list([item["path"] for item in data["untracked_files"]]),
        "",
        "## Bug Hunt Queue",
        "",
        "Prioritize manual bug hunting here. Score combines impact risk, bug-pattern hints, and security-pattern hints.",
        "",
        markdown_table(bug_hunt_rows, ["Score", "File", "Bug hints", "Security hints", "Reasons"]),
        "",
        "## Bug Pattern Hints",
        "",
        "Automated leads only — validate in context before reporting as findings.",
        "",
    ]

    if bug_findings:
        lines.extend(
            markdown_table(
                [
                    [
                        f"`{finding['path']}:{finding['line']}`",
                        finding.get("change", "added"),
                        finding["rule"],
                        finding["snippet"].replace("|", "\\|"),
                    ]
                    for finding in bug_findings[:40]
                ],
                ["Location", "Change", "Rule", "Snippet"],
            ).splitlines()
        )
        lines.append("")
    else:
        lines.extend(["- No bug pattern hints detected in added/changed lines.", ""])

    lines.extend(
        [
            "## Security Pattern Hints",
            "",
            "Automated leads only — many are false positives. Confirm in source before reporting.",
            "",
        ]
    )

    if security_findings:
        lines.extend(
            markdown_table(
                [
                    [
                        f"`{finding['path']}:{finding['line']}`",
                        finding["rule"],
                        finding["snippet"].replace("|", "\\|"),
                    ]
                    for finding in security_findings[:40]
                ],
                ["Location", "Rule", "Snippet"],
            ).splitlines()
        )
        lines.append("")
    else:
        lines.extend(["- No security pattern hints detected in added/changed lines.", ""])

    lines.extend(
        [
            "## No-CodeGraph Impact Triage",
            "",
            "Use this as a review queue when CodeGraph is unavailable. Inspect the high-scoring files and their dependent hints first.",
            "",
            markdown_table(risk_rows, ["Score", "File", "Categories", "Reasons"]),
            "",
            "## New Directories",
            "",
            markdown_list(data["new_directories"]),
            "",
            "## Dependency Files Changed",
            "",
            markdown_list(data["dependency_files"]),
            "",
            "### Dependency Consistency Warnings",
            "",
            markdown_plain_list(data["dependency_warnings"]),
            "",
            "### package.json Dependency Deltas",
            "",
        ]
    )

    if data["package_dependency_deltas"]:
        for path, sections in data["package_dependency_deltas"].items():
            lines.append(f"#### `{path}`")
            lines.append("")
            for section, changes in sections.items():
                lines.append(f"- `{section}`")
                for change in changes:
                    lines.append(f"  - `{change['name']}`: `{change['before']}` -> `{change['after']}`")
            lines.append("")
    else:
        lines.append("- None detected.")
        lines.append("")

    lines.extend(
        [
            "## Shared/Public Surface Candidates",
            "",
            markdown_list(data["shared_files"]),
            "",
            "## Entry Point Candidates",
            "",
            markdown_list(data["entrypoint_files"]),
            "",
            "## Config/Migration Candidates",
            "",
            markdown_list(data["config_files"] + data["migration_files"]),
            "",
            "## Test Command Candidates",
            "",
            markdown_plain_list(data["test_commands"]),
            "",
            "## Import Summary For Changed Source Files",
            "",
        ]
    )

    for path in changed_paths:
        imports = data["imports"].get(path, [])
        if imports:
            lines.append(f"### `{path}`")
            lines.append("")
            lines.extend(f"- `{imp}`" for imp in imports)
            lines.append("")
    if not any(data["imports"].get(path) for path in changed_paths):
        lines.append("- No imports detected in changed source files.")
        lines.append("")

    lines.extend(["## Direct Importer Hints", ""])
    direct_importers = data["direct_importers"]
    any_importers = False
    for path in changed_paths:
        importers = direct_importers.get(path, [])
        if importers:
            any_importers = True
            lines.append(f"### `{path}`")
            lines.append("")
            lines.extend(f"- `{dep}`" for dep in importers[:30])
            lines.append("")
    if not any_importers:
        lines.append("- No direct importers resolved. Check symbol references and textual hints below.")
        lines.append("")

    lines.extend(["## Public Symbol Candidate Deltas", ""])
    any_symbols = False
    for path, delta in data["symbol_deltas"].items():
        if delta["current"] or delta["added"] or delta["removed"]:
            any_symbols = True
            lines.append(f"### `{path}`")
            lines.append("")
            lines.append(f"- Added: {', '.join(f'`{value}`' for value in delta['added']) or 'None'}")
            lines.append(f"- Removed: {', '.join(f'`{value}`' for value in delta['removed']) or 'None'}")
            lines.append(f"- Current: {', '.join(f'`{value}`' for value in delta['current'][:30]) or 'None'}")
            lines.append("")
    if not any_symbols:
        lines.append("- No public symbol candidates detected.")
        lines.append("")

    lines.extend(["## Symbol Reference Hints", ""])
    if data["symbol_reference_hints"]:
        for path, refs in data["symbol_reference_hints"].items():
            lines.append(f"### `{path}`")
            lines.append("")
            lines.extend(f"- `{ref}`" for ref in refs[:30])
            lines.append("")
    else:
        lines.append("- No symbol reference hints detected.")
        lines.append("")

    lines.extend(["## Deleted File Reference Hints", ""])
    if data["deleted_reference_hints"]:
        for path, refs in data["deleted_reference_hints"].items():
            lines.append(f"### `{path}`")
            lines.append("")
            lines.extend(f"- `{ref}`" for ref in refs[:30])
            lines.append("")
    else:
        lines.append("- No deleted-path references detected.")
        lines.append("")

    lines.extend(["## Nearby/Importing Test Hints", ""])
    has_test_hints = False
    for path, tests in data["test_neighbors"].items():
        if tests:
            has_test_hints = True
            lines.append(f"### `{path}`")
            lines.append("")
            lines.extend(f"- `{test}`" for test in tests)
            lines.append("")
    if not has_test_hints:
        lines.append("- No nearby/importing test hints detected for changed source files.")
        lines.append("")

    lines.extend(["## Diff Stat", "", "```", data["diff_stat"] or "No diff stat.", "```", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", help="Branch start commit or ref. Defaults to --start-mode reflog inference.")
    parser.add_argument("--base", help="Deprecated alias for --start.")
    parser.add_argument(
        "--start-mode",
        default="reflog",
        help="How to infer branch start when --start is omitted: reflog (default) or merge-base-with=<ref>.",
    )
    parser.add_argument("--output", help="Markdown output path. Defaults to stdout.")
    parser.add_argument("--json-output", help="Optional JSON output path.")
    parser.add_argument(
        "--include-working-tree",
        action="store_true",
        help="Include staged, unstaged, and untracked files in impact triage.",
    )
    args = parser.parse_args()

    repo = repo_root(Path.cwd())
    branch = current_branch(repo)
    start_arg = args.start or args.base
    start, start_source = resolve_start(repo, branch, start_arg, args.start_mode)
    start_mode = args.start_mode if not start_arg else "explicit"

    review_range = f"{start}..HEAD"
    head = run_git(["rev-parse", "--short", "HEAD"], repo)
    committed_files = parse_name_status(run_git(["diff", "--name-status", "--find-renames", review_range], repo), "committed")
    staged_files = parse_name_status(run_git(["diff", "--cached", "--name-status", "--find-renames"], repo, check=False), "staged")
    unstaged_files = parse_name_status(run_git(["diff", "--name-status", "--find-renames"], repo, check=False), "unstaged")
    untracked_files = [
        {"status": "A", "path": line, "sources": ["untracked"]}
        for line in run_git(["ls-files", "--others", "--exclude-standard"], repo, check=False).splitlines()
        if line.strip()
    ]
    working_groups = [staged_files, unstaged_files, untracked_files] if args.include_working_tree else []
    analysis_files = merge_file_entries([committed_files, *working_groups])
    changed_paths = [item["path"] for item in analysis_files]
    changed_existing_paths = [item["path"] for item in analysis_files if item["status"][0] != "D"]

    source_files = list_source_files(repo, args.include_working_tree)
    import_impact = build_import_impact(repo, source_files)
    imports = {path: imports_for_file(repo, path) for path in changed_existing_paths if is_source_file(path)}
    content_index = file_content_index(repo, source_files)
    symbol_deltas = {
        item["path"]: symbol_delta(repo, start, item)
        for item in analysis_files
        if is_source_file(item["path"]) and PurePosixPath(item["path"]).suffix.lower() in JS_SUFFIXES | PY_SUFFIXES | GO_SUFFIXES | RUST_SUFFIXES
    }
    symbol_reference_hints = reference_hints_for_symbols(analysis_files, symbol_deltas, content_index)
    deleted_items = [item for item in analysis_files if item["status"][0] == "D"]
    deleted_ref_hints = deleted_reference_hints(deleted_items, content_index)
    test_neighbors = {
        path: find_test_neighbors(path, source_files, content_index)
        for path in changed_existing_paths
        if is_source_file(path) and not is_test_file(path)
    }
    direct_importers = import_impact["direct_importers"]
    risk_targets = [
        risk_for_file(item, direct_importers, symbol_reference_hints, test_neighbors, deleted_ref_hints, symbol_deltas)
        for item in analysis_files
    ]
    risk_targets.sort(key=lambda value: (-value["score"], value["path"]))

    added_lines, removed_lines = collect_line_changes(repo, start, analysis_files, args.include_working_tree)
    pattern_findings = scan_line_changes(added_lines, removed_lines)
    bug_hunt_queue = build_bug_hunt_queue(risk_targets, pattern_findings)

    # Size / trigger signals must reflect what is actually under review. When the working
    # tree is included, `git diff <start>` covers committed + uncommitted changes against
    # <start>; otherwise use the committed-only range. This keeps the large-branch threshold
    # (Bugbot trigger) honest for WIP-heavy branches instead of undercounting uncommitted work.
    diff_range = start if args.include_working_tree else review_range
    numstat = parse_numstat(run_git(["diff", "--numstat", diff_range], repo))
    dependency_files = sorted(path for path in changed_paths if is_dependency_file(path))
    shared_files = sorted(path for path in changed_paths if is_shared_file(path))
    entrypoint_files = sorted(path for path in changed_paths if is_entrypoint_file(path))
    config_files = sorted(path for path in changed_paths if is_config_file(path))
    migration_files = sorted(path for path in changed_paths if is_migration_file(path))
    dependency_warnings = dependency_consistency(changed_paths)
    package_dependency_deltas = compare_package_dependencies(repo, start, changed_paths)

    data: dict[str, Any] = {
        "repo": str(repo),
        "start": start,
        "start_source": start_source,
        "start_mode": start_mode,
        "head": head,
        "branch": branch,
        "range": review_range,
        "include_working_tree": args.include_working_tree,
        "working_tree_status": run_git(["status", "--short", "--branch"], repo, check=False),
        "commits": run_git(["log", "--oneline", review_range], repo, check=False),
        "committed_files": committed_files,
        "staged_files": staged_files,
        "unstaged_files": unstaged_files,
        "untracked_files": untracked_files,
        "analysis_files": analysis_files,
        "numstat": numstat,
        "new_directories": new_directories(analysis_files),
        "dependency_files": dependency_files,
        "dependency_warnings": dependency_warnings,
        "package_dependency_deltas": package_dependency_deltas,
        "shared_files": shared_files,
        "entrypoint_files": entrypoint_files,
        "config_files": config_files,
        "migration_files": migration_files,
        "imports": imports,
        "import_aliases": import_impact["aliases"],
        "go_module": import_impact["go_module"],
        "resolved_imports": import_impact["resolved_imports"],
        "direct_importers": direct_importers,
        "symbol_deltas": symbol_deltas,
        "symbol_reference_hints": symbol_reference_hints,
        "deleted_reference_hints": deleted_ref_hints,
        "test_neighbors": test_neighbors,
        "test_commands": detect_test_commands(repo),
        "risk_targets": risk_targets,
        "pattern_findings": pattern_findings,
        "bug_hunt_queue": bug_hunt_queue,
        "diff_stat": run_git(["diff", "--stat", diff_range], repo, check=False),
        "reflog_health": reflog_health(repo, branch, start),
    }

    report = build_report(data)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    else:
        print(report)
    if args.json_output:
        json_output = Path(args.json_output)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
