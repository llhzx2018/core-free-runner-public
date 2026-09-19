#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "vf-ephemeral-lane-spec/v1"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TOKEN_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
EXTRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

RESERVED = {
    "LANE_ID",
    "PROJECT_ID",
    "REPOSITORY",
    "TARGET_VERSION",
    "TARGET_TAG",
    "TARGET_VERSION_COMPACT",
    "TARGET_SHA",
    "TARGET_TREE",
    "SCHEMA_VERSION",
    "CANDIDATE_RUN",
    "SOURCE_VERSIONS_JSON",
    "SOURCE_VERSIONS_CSV",
}


class ContractError(ValueError):
    pass


def _require_string(data: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ContractError(f"{key}: expected string")
    if not allow_empty and not value.strip():
        raise ContractError(f"{key}: empty")
    return value.strip()


def _optional_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key, "")
    if value in (None, ""):
        return ""
    if not isinstance(value, (str, int)):
        raise ContractError(f"{key}: expected string/int")
    return str(value).strip()


def load_spec(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid json: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError("root: expected object")
    if data.get("schema") != SCHEMA:
        raise ContractError(f"schema: expected {SCHEMA}")

    lane_id = _require_string(data, "lane_id")
    project_id = _require_string(data, "project_id")
    repository = _require_string(data, "repository")
    target_version = _require_string(data, "target_version")
    target_sha = _require_string(data, "target_sha")
    target_tree = _optional_string(data, "target_tree")
    schema_version = _optional_string(data, "schema_version")
    candidate_run = _optional_string(data, "candidate_run")

    if not REPO_RE.fullmatch(repository):
        raise ContractError("repository: expected owner/name")
    if not VERSION_RE.fullmatch(target_version):
        raise ContractError("target_version: expected x.y.z")
    if not SHA_RE.fullmatch(target_sha):
        raise ContractError("target_sha: expected lowercase 40-hex")
    if target_tree and not SHA_RE.fullmatch(target_tree):
        raise ContractError("target_tree: expected lowercase 40-hex")
    if candidate_run and not candidate_run.isdigit():
        raise ContractError("candidate_run: expected digits")
    if schema_version and not re.fullmatch(r"[A-Za-z0-9_.-]+", schema_version):
        raise ContractError("schema_version: unsafe characters")

    source_versions = data.get("source_versions", [])
    if not isinstance(source_versions, list) or not all(isinstance(v, str) for v in source_versions):
        raise ContractError("source_versions: expected string array")
    source_versions = [v.strip() for v in source_versions]
    if any(not VERSION_RE.fullmatch(v) for v in source_versions):
        raise ContractError("source_versions: every entry must be x.y.z")
    if len(source_versions) != len(set(source_versions)):
        raise ContractError("source_versions: duplicates forbidden")
    if target_version in source_versions:
        raise ContractError("source_versions: target version must not be a source")

    previous = data.get("previous_lane", {})
    if previous in (None, ""):
        previous = {}
    if not isinstance(previous, dict):
        raise ContractError("previous_lane: expected object")
    previous_target_version = _optional_string(previous, "target_version")
    previous_target_sha = _optional_string(previous, "target_sha")
    previous_target_tree = _optional_string(previous, "target_tree")
    if previous_target_version and not VERSION_RE.fullmatch(previous_target_version):
        raise ContractError("previous_lane.target_version: expected x.y.z")
    if previous_target_sha and not SHA_RE.fullmatch(previous_target_sha):
        raise ContractError("previous_lane.target_sha: expected lowercase 40-hex")
    if previous_target_tree and not SHA_RE.fullmatch(previous_target_tree):
        raise ContractError("previous_lane.target_tree: expected lowercase 40-hex")

    extra = data.get("extra", {})
    if extra in (None, ""):
        extra = {}
    if not isinstance(extra, dict):
        raise ContractError("extra: expected object")
    normalized_extra: dict[str, str] = {}
    for key, value in extra.items():
        if not isinstance(key, str) or not EXTRA_KEY_RE.fullmatch(key):
            raise ContractError(f"extra key {key!r}: expected UPPER_SNAKE_CASE")
        if key in RESERVED:
            raise ContractError(f"extra key {key}: reserved")
        if any(marker in key for marker in ("SECRET", "PASSWORD", "CREDENTIAL", "TOKEN_VALUE")):
            raise ContractError(f"extra key {key}: secret-bearing fields forbidden")
        if not isinstance(value, (str, int, float, bool)):
            raise ContractError(f"extra.{key}: scalar only")
        normalized_extra[key] = str(value)

    return {
        "schema": SCHEMA,
        "lane_id": lane_id,
        "project_id": project_id,
        "repository": repository,
        "target_version": target_version,
        "target_sha": target_sha,
        "target_tree": target_tree,
        "source_versions": source_versions,
        "schema_version": schema_version,
        "candidate_run": candidate_run,
        "previous_lane": {
            "target_version": previous_target_version,
            "target_sha": previous_target_sha,
            "target_tree": previous_target_tree,
        },
        "extra": normalized_extra,
    }


def variables(spec: dict[str, Any]) -> dict[str, str]:
    version = spec["target_version"]
    compact = version.replace(".", "")
    out = {
        "LANE_ID": spec["lane_id"],
        "PROJECT_ID": spec["project_id"],
        "REPOSITORY": spec["repository"],
        "TARGET_VERSION": version,
        "TARGET_TAG": f"v{version}",
        "TARGET_VERSION_COMPACT": compact,
        "TARGET_SHA": spec["target_sha"],
        "TARGET_TREE": spec["target_tree"],
        "SCHEMA_VERSION": spec["schema_version"],
        "CANDIDATE_RUN": spec["candidate_run"],
        "SOURCE_VERSIONS_JSON": json.dumps(spec["source_versions"], separators=(",", ":")),
        "SOURCE_VERSIONS_CSV": ",".join(spec["source_versions"]),
    }
    out.update(spec["extra"])
    return out


def lint_template(text: str, spec: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    mapping = variables(spec)
    tokens = set(TOKEN_RE.findall(text))
    required = {"REPOSITORY", "TARGET_VERSION", "TARGET_SHA"}
    missing = sorted(required - tokens)
    if missing:
        failures.append("MISSING_REQUIRED_TOKENS:" + ",".join(missing))
    unknown = sorted(tokens - set(mapping))
    if unknown:
        failures.append("UNKNOWN_TOKENS:" + ",".join(unknown))

    # Identity belongs to the spec, never to copied template literals.
    protected_literals = [
        spec["target_version"],
        spec["target_sha"],
        spec["target_tree"],
        *spec["source_versions"],
        spec["previous_lane"]["target_version"],
        spec["previous_lane"]["target_sha"],
        spec["previous_lane"]["target_tree"],
    ]
    seen: set[str] = set()
    for value in protected_literals:
        if not value or value in seen:
            continue
        seen.add(value)
        if value in text:
            failures.append(f"IDENTITY_LITERAL_IN_TEMPLATE:{value}")

    compact = mapping["TARGET_VERSION_COMPACT"]
    if compact and len(compact) >= 4 and compact in text:
        failures.append(f"COMPACT_VERSION_LITERAL_IN_TEMPLATE:{compact}")
    return failures


def render(template: str, spec: dict[str, Any]) -> str:
    failures = lint_template(template, spec)
    if failures:
        raise ContractError(";".join(failures))
    mapping = variables(spec)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in mapping:
            raise ContractError(f"unknown token: {key}")
        return mapping[key]

    rendered = TOKEN_RE.sub(replace, template)
    unresolved = TOKEN_RE.findall(rendered)
    if unresolved:
        raise ContractError("unresolved tokens: " + ",".join(sorted(set(unresolved))))
    return rendered


def github_outputs(spec: dict[str, Any]) -> str:
    mapping = variables(spec)
    keys = [
        "LANE_ID",
        "PROJECT_ID",
        "REPOSITORY",
        "TARGET_VERSION",
        "TARGET_TAG",
        "TARGET_VERSION_COMPACT",
        "TARGET_SHA",
        "TARGET_TREE",
        "SCHEMA_VERSION",
        "CANDIDATE_RUN",
        "SOURCE_VERSIONS_JSON",
        "SOURCE_VERSIONS_CSV",
    ] + sorted(spec["extra"])
    rows = []
    for key in keys:
        value = mapping.get(key, "")
        if "\n" in value or "\r" in value:
            raise ContractError(f"{key}: multiline GitHub output forbidden")
        rows.append(f"{key.lower()}={value}")
    return "\n".join(rows) + "\n"


def payload(spec: dict[str, Any]) -> dict[str, Any]:
    public = dict(spec)
    public["previous_lane"] = dict(spec["previous_lane"])
    public["extra"] = dict(spec["extra"])
    return {
        "schema": "vf-ephemeral-lane-spec-check/v1",
        "status": "PASS",
        "lane": public,
        "variables": variables(spec),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Single-source identity contract for temporary VF Runner lanes"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate_p = sub.add_parser("validate")
    validate_p.add_argument("--spec", type=Path, required=True)

    render_p = sub.add_parser("render")
    render_p.add_argument("--spec", type=Path, required=True)
    render_p.add_argument("--template", type=Path, required=True)
    render_p.add_argument("--output", type=Path, required=True)

    output_p = sub.add_parser("github-output")
    output_p.add_argument("--spec", type=Path, required=True)

    args = parser.parse_args()
    try:
        spec = load_spec(args.spec)
        if args.command == "validate":
            print(json.dumps(payload(spec), ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == "github-output":
            print(github_outputs(spec), end="")
            return 0
        template = args.template.read_text(encoding="utf-8")
        rendered = render(template, spec)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        result = {
            "schema": "vf-ephemeral-lane-render/v1",
            "status": "PASS",
            "output": args.output.as_posix(),
            "sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            "target_version": spec["target_version"],
            "target_sha": spec["target_sha"],
            "source_versions": spec["source_versions"],
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ContractError) as exc:
        print(json.dumps({
            "schema": "vf-ephemeral-lane-spec-check/v1",
            "status": "FAIL",
            "error": str(exc),
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
