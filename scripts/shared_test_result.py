"""Shared, read-only JUnit diagnostic normalization for existing VF test lanes.

No dispatch, shell, credentials, workspace mutation, or raw log publication.
Use only after the owning lane has admitted its exact source and test ID.
"""
from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET

MAX_REPORT = 4 * 1024 * 1024
MAX_CASES = 20000
MAX_FAILURES = 40
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_\\.:/() -]{0,179}\Z")
REASONS = (
    ("ASSERT_EQUALITY", ("failed asserting that", "to equal", "to be equal", "assertionerror")),
    ("ASSERT_HTTP_STATUS", ("expected response status", "unexpected status code")),
    ("ASSERT_VISIBILITY", ("tobevisible", "to be visible")),
    ("ASSERT_TIMEOUT", ("timeouterror", "timeout exceeded", "timed out")),
    ("DB_CONNECTION", ("sqlstate[hy000] [2002]", "connection refused")),
    ("DEPENDENCY_MISSING", ("module not found", "class not found", "cannot find module")),
    ("PERMISSION_DENIED", ("permission denied",)),
    ("ASSERT_CONTAINS", ("tocontain", "to contain", "not to contain")),
    ("ASSERT_LENGTH", ("tohavelength", "to have length")),
    ("ASSERT_MISMATCH", ("expected", "actual")),
)

def _reason(value: str, tag: str) -> str:
    low = value[:65536].lower()
    # More specific diagnostics precede the generic assertion category.
    for reason, needles in REASONS[1:] + REASONS[:1]:
        if any(needle in low for needle in needles):
            return reason
    return "ASSERTION_FAILURE" if tag == "failure" else "TEST_RUNTIME_ERROR"

def _name(value: str, known_names: frozenset[str]) -> str:
    # Only names independently supplied from reviewed source may leave the
    # report. Parameterized titles and arbitrary XML strings remain private.
    candidates = [value, value.rsplit(" > ", 1)[-1]]
    parameterized = re.match(r"^([A-Za-z_][A-Za-z0-9_]*) with data set(?: |$)", value)
    if parameterized:
        candidates.append(parameterized.group(1))
    for candidate in candidates:
        if candidate in known_names and IDENTIFIER.fullmatch(candidate):
            return candidate
    return "case-" + hashlib.sha256(value.encode()).hexdigest()[:16]

def summarize_junit(data: bytes, *, known_names: frozenset[str] = frozenset()) -> dict:
    if not isinstance(data, bytes) or len(data) > MAX_REPORT:
        return {"status": "REPORT_INVALID", "reason": "REPORT_SIZE_OR_TYPE"}
    # Standard reporters use CDATA for failures; reject DTD/entity declarations
    # while permitting ordinary JUnit CDATA and XML comments.
    try:
        xml = data.decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.IGNORECASE):
            raise ValueError("declaration")
        root = ET.fromstring(xml)
    except (UnicodeError, ValueError, ET.ParseError):
        return {"status": "REPORT_INVALID", "reason": "REPORT_XML"}
    if root.tag not in {"testsuites", "testsuite"}:
        return {"status": "REPORT_INVALID", "reason": "REPORT_ROOT"}
    failures = []
    cases = failed = skipped = 0
    for case in root.iter("testcase"):
        cases += 1
        if cases > MAX_CASES:
            return {"status": "REPORT_INVALID", "reason": "REPORT_CASE_LIMIT"}
        problem = next((x for x in case if x.tag in {"failure", "error"}), None)
        if problem is None:
            skipped += int(case.find("skipped") is not None)
            continue
        failed += 1
        if len(failures) >= MAX_FAILURES:
            continue
        name = case.get("name", "")
        qualified = case.get("classname", "") + "::" + name
        identity = qualified if qualified in known_names else name
        details = problem.get("message", "")[:32768] + (problem.text or "")[:32768]
        failures.append({"test": _name(identity, known_names),
                         "kind": problem.tag,
                         "assertion": _reason(details, problem.tag)})
    return {"status": "REPORT_OBSERVED" if cases else "REPORT_EMPTY",
            "cases": cases, "failed": failed, "skipped": skipped,
            "failures": failures, "omitted_failures": failed - len(failures)}
