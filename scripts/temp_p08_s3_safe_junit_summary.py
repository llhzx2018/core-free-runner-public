#!/usr/bin/env python3
"""One-off safe metadata-only PHPUnit JUnit classifier.

Never print source, stack, fixtures, URLs, request/response bodies,
credentials, or raw failure text on the Public Runner.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def summary(path: Path) -> int:
    root = ET.parse(path).getroot()
    found = []
    for case in root.iter("testcase"):
        problem = next((n for n in case if n.tag in {"failure", "error"}), None)
        if problem is None:
            continue
        classname = case.attrib.get("class", case.attrib.get("classname", ""))
        method = case.attrib.get("name", "")
        label = f"{classname}::{method}"
        source = (problem.attrib.get("message", "") + "\n" + (problem.text or ""))
        locations = re.findall(r"tests/Feature/[A-Za-z0-9_]+\.php:(\d+)", source)
        first = problem.attrib.get("message", "").splitlines()
        headline = first[0] if first else ""
        statuses = re.search(r"Expected response status code \[(\d+)\] but received (\d+)", source)
        numbers = re.search(r"Failed asserting that (\d+) is identical to (\d+)", source)
        result = {
            "case_sha12": hashlib.sha256(label.encode()).hexdigest()[:12],
            "failure_sha12": hashlib.sha256(source.encode()).hexdigest()[:12],
            "phpunit_tag": "error" if problem.tag == "error" else "failure",
            "assertion_line": int(locations[-1]) if locations else None,
            "kind": (
                "HTTP_STATUS" if statuses
                else "INTEGER_EQUALITY" if numbers
                else "SESSION_ERROR" if "session has errors" in source.lower()
                else "STRING_ASSERTION" if "strings are equal" in source.lower()
                else "ASSERTION" if "Failed asserting" in source or "failed asserting" in source.lower()
                else "PHP_ERROR"
            ),
        }
        # Purely semantic, bounded diagnostics: no raw message content is logged.
        # Cache-Control token set is an allowlist of standard non-sensitive directives.
        lowered = source.lower()
        result["signals"] = {
            "missing_session_errors": "session is missing expected" in lowered or "session does not have" in lowered,
            "session_error_bag": "session" in lowered and "error" in lowered,
            "assert_true_failed": "failed asserting that false is true" in lowered,
            "assert_false_failed": "failed asserting that true is false" in lowered,
            "cache_no_store": "no-store" in lowered,
            "cache_no_cache": "no-cache" in lowered,
            "cache_private": "private" in lowered,
            "cache_max_age_zero": "max-age=0" in lowered,
            "security_header": "content-security-policy" in lowered,
            "expected_history_error": "history_id" in lowered,
            "actual_vps_error": "vps" in lowered,
            "actual_confirmation_error": "confirmation" in lowered,
        }
        result["diff_safe"] = [
            value for line in source.splitlines()
            if line.startswith(("+", "-")) and not line.startswith(("++", "--"))
            for value in [line[1:].strip().strip(chr(39)).strip(chr(34))]
            if value and re.fullmatch(
                r"(?:private|no-cache|no-store|max-age=0|noindex|nofollow|noarchive|[ ,;])+",
                value.lower(),
            )
        ][:4]
        if statuses:
            result.update(expected_http=int(statuses[1]), received_http=int(statuses[2]))
        if numbers:
            result.update(actual_integer=int(numbers[1]), expected_integer=int(numbers[2]))
        found.append(result)
    print("P08_S3_SAFE_JUNIT_COUNT=" + str(len(found)))
    for item in sorted(found, key=lambda i: i["case_sha12"]):
        print("P08_S3_SAFE_JUNIT=" + json.dumps(item, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(summary(Path(sys.argv[1])))
