#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from intrusion_scan import (
    DEFAULT_MAX_HASH_BYTES, DEFAULT_MAX_TRACKED_FILES, ScanBudget,
    ScanBudgetExceededError, collect, diff, discover, unbaselined_site_event,
)
from intrusion_logs import correlate
from intrusion_state import (
    DEFAULT_STATE_DIR, SCHEMA, ensure_dir, exclusive_lock, iso, parse_iso,
    prune_events, read_events, read_json, utcnow, write_events, write_json,
)

DEFAULT_SCAN_TIMEOUT_SECONDS = 30 * 60
DEFAULT_MAX_EVENT_RECORDS = 5_000


class StateBaselineMissingError(RuntimeError):
    pass


class StateGenerationMissingError(RuntimeError):
    pass


class StateGenerationMismatchError(RuntimeError):
    pass


class StateScanCorruptError(RuntimeError):
    pass


class StateEventsMissingError(RuntimeError):
    pass


class StateEventsCorruptError(RuntimeError):
    pass


class StateEventCountMismatchError(RuntimeError):
    pass


class EvidenceCapacityExceededError(RuntimeError):
    def __init__(self, limit: int, existing: int, pending_new: int):
        super().__init__("evidence event capacity exceeded")
        self.limit = int(limit)
        self.existing = int(existing)
        self.pending_new = int(pending_new)


@contextmanager
def wall_clock_timeout(seconds: int) -> Iterator[None]:
    """Bound a scan on Linux/Unix while still letting Python record FAILED state."""
    if seconds < 1:
        raise ValueError("scan timeout must be positive")
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def _timeout(_signum, _frame):
        raise TimeoutError("intrusion evidence scan exceeded wall-clock budget")

    signal.signal(signal.SIGALRM, _timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def bounded_env_int(name: str, default: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name}") from exc
    if value < 1 or value > maximum:
        raise ValueError(f"{name} out of range")
    return value


def scan_timeout_seconds() -> int:
    return bounded_env_int("P07_IE_SCAN_TIMEOUT_SECONDS", DEFAULT_SCAN_TIMEOUT_SECONDS, 24 * 60 * 60)


def scan_budget_from_env() -> ScanBudget:
    return ScanBudget(
        max_files=bounded_env_int("P07_IE_MAX_TRACKED_FILES", DEFAULT_MAX_TRACKED_FILES, 1_000_000),
        max_bytes=bounded_env_int("P07_IE_MAX_HASH_BYTES", DEFAULT_MAX_HASH_BYTES, 100 * 1024 * 1024 * 1024),
    )


def event_record_limit() -> int:
    return bounded_env_int("P07_IE_MAX_EVENT_RECORDS", DEFAULT_MAX_EVENT_RECORDS, 100_000)


def safe_event_count(path: Path, fallback: int = 0) -> int:
    try:
        return len(read_events(path))
    except Exception:
        return fallback


def parse_nonnegative_int(value, error_class: type[Exception], field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise error_class(f"invalid {field}") from exc
    if parsed < 0:
        raise error_class(f"invalid {field}")
    return parsed


def load_events_consistent(path: Path, scan: dict) -> list[dict]:
    expected = parse_nonnegative_int(scan.get("event_count"), StateEventCountMismatchError, "event_count")
    if not path.is_file():
        if expected == 0:
            return []
        raise StateEventsMissingError("events store missing")
    try:
        rows = read_events(path)
    except Exception as exc:
        raise StateEventsCorruptError("events store corrupt") from exc
    if len(rows) != expected:
        raise StateEventCountMismatchError("events count mismatch")
    return rows


def error_detail(error: Exception) -> dict:
    if isinstance(error, ScanBudgetExceededError):
        return {
            "resource": error.resource,
            "limit": error.limit,
            "current": error.current,
            "requested": error.requested,
        }
    if isinstance(error, EvidenceCapacityExceededError):
        return {
            "event_limit": error.limit,
            "existing_events": error.existing,
            "pending_new_events": error.pending_new,
        }
    return {}


def baseline_doc(roots: list[Path], previous: Optional[dict], budget: ScanBudget) -> dict:
    now = iso()
    sites = {}
    for root in roots:
        files = collect(root, budget=budget)
        for meta in files.values():
            meta["first_seen_at"] = now
            meta["last_seen_at"] = now
        sites[str(root)] = {"label": root.name, "root": str(root), "files": files, "tracked_count": len(files)}
    return {
        "schema": SCHEMA,
        "baseline_generation": uuid.uuid4().hex,
        "created_at": (previous or {}).get("created_at", now),
        "rebuilt_at": now,
        "last_known_clean_at": now,
        "trust_model": "USER_ESTABLISHED_REFERENCE_BASELINE_NOT_MALWARE_SCAN",
        "sites": sites,
    }


def command_baseline(args: argparse.Namespace) -> int:
    state = Path(args.state_dir); ensure_dir(state)
    with exclusive_lock(state):
        baseline_path, scan_path, events_path = state / "baseline.json", state / "scan_state.json", state / "events.json"

        # Rebaseline is allowed to replace a corrupt/missing baseline only after explicit user action,
        # but it may never silently discard event history that scan_state says should exist.
        prior_scan: dict = {}
        if scan_path.is_file():
            try:
                prior_scan = read_json(scan_path)
            except Exception:
                prior_scan = {}
        if prior_scan and "event_count" in prior_scan:
            events = load_events_consistent(events_path, prior_scan)
        elif events_path.is_file():
            try:
                events = read_events(events_path)
            except Exception as exc:
                raise StateEventsCorruptError("events store corrupt") from exc
        else:
            events = []

        previous = None
        if baseline_path.is_file():
            try:
                previous = read_json(baseline_path)
            except Exception:
                # Explicit rebaseline is the recovery action for a corrupt baseline.
                previous = None

        limit = event_record_limit()
        if len(events) > limit:
            raise EvidenceCapacityExceededError(limit, len(events), 0)
        roots = discover(args.site_root)
        if not roots:
            raise ValueError("no WordPress sites discovered")
        budget = scan_budget_from_env()
        doc = baseline_doc(roots, previous, budget)
        write_json(baseline_path, doc)
        write_json(scan_path, {
            "schema": SCHEMA,
            "baseline_generation": doc["baseline_generation"],
            "result": "BASELINE_READY", "previous_scan_at": None,
            "scan_started_at": doc["rebuilt_at"], "scan_finished_at": doc["rebuilt_at"],
            "last_known_clean_at": doc["last_known_clean_at"], "first_detected_at": None,
            "incident_open": False, "unbaselined_site_count": 0,
            "baseline_trust": doc["trust_model"],
            "event_count": len(events), "event_record_limit": limit, "site_count": len(roots),
            "scan_budget": budget.snapshot(),
        })
    print(json.dumps({
        "result": "BASELINE_READY", "site_count": len(roots),
        "tracked_count": sum(x["tracked_count"] for x in doc["sites"].values()),
        "scan_budget": budget.snapshot(), "event_record_limit": limit,
    }))
    return 0


def merge_events(
    path: Path,
    candidates: list[dict],
    last_clean: Optional[str],
    *,
    existing_rows: list[dict],
    event_limit: int,
    preserve_since: Optional[str] = None,
) -> tuple[list[dict], str]:
    rows = list(existing_rows)
    by_id = {row.get("event_id"): row for row in rows if row.get("event_id")}
    new_ids = {candidate["event_id"] for candidate in candidates if candidate["event_id"] not in by_id}
    if len(rows) > event_limit or len(rows) + len(new_ids) > event_limit:
        raise EvidenceCapacityExceededError(event_limit, len(rows), len(new_ids))

    now = iso()
    current_ids = set()
    for candidate in candidates:
        key = candidate["event_id"]
        current_ids.add(key)
        if key in by_id:
            by_id[key]["last_seen_at"] = now
            continue
        candidate["last_known_clean_at"] = last_clean
        candidate["last_seen_at"] = now
        mtime = candidate.get("mtime")
        if isinstance(mtime, int):
            requests, correlation_meta = correlate(Path(candidate["site_root"]), mtime)
            candidate["correlated_requests"] = requests
            candidate["correlation_meta"] = correlation_meta
        else:
            candidate["correlated_requests"] = []
            candidate["correlation_meta"] = {"status": "NOT_APPLICABLE", "reason": "NO_FILE_MTIME"}
        rows.append(candidate); by_id[key] = candidate
    rows = prune_events(
        rows,
        utcnow(),
        preserve_since=parse_iso(preserve_since),
        preserve_ids=current_ids,
    )
    if len(rows) > event_limit:
        raise EvidenceCapacityExceededError(event_limit, len(existing_rows), len(new_ids))
    write_events(path, rows)
    active = [parse_iso(by_id[row["event_id"]].get("first_detected_at")) for row in candidates if row["event_id"] in by_id]
    active = [value for value in active if value]
    return rows, iso(min(active)) if active else iso()


def earliest_iso(*values: Optional[str]) -> Optional[str]:
    parsed = [parse_iso(value) for value in values]
    parsed = [value for value in parsed if value is not None]
    return iso(min(parsed)) if parsed else None


def failure_state(
    state: Path,
    started,
    previous_scan: Optional[str],
    last_clean: Optional[str],
    error: Exception,
    *,
    baseline_generation: Optional[str] = None,
    incident_open: bool = False,
    first_detected: Optional[str] = None,
    unbaselined_site_count: int = 0,
    previous_event_count: int = 0,
    budget: Optional[ScanBudget] = None,
    event_limit: Optional[int] = None,
) -> int:
    count = safe_event_count(state / "events.json", fallback=previous_event_count)
    doc = {
        "schema": SCHEMA,
        "baseline_generation": baseline_generation,
        "result": "FAILED", "previous_scan_at": previous_scan,
        "scan_started_at": iso(started), "scan_finished_at": iso(),
        "last_known_clean_at": last_clean, "first_detected_at": first_detected,
        "incident_open": incident_open, "unbaselined_site_count": unbaselined_site_count,
        "event_count": count, "error_class": error.__class__.__name__,
    }
    if event_limit is not None:
        doc["event_record_limit"] = event_limit
    if budget is not None:
        doc["scan_budget"] = budget.snapshot()
    detail = error_detail(error)
    if detail:
        doc["error_detail"] = detail
    write_json(state / "scan_state.json", doc)
    print(json.dumps({"result": "FAILED", "error_class": error.__class__.__name__, "error_detail": detail}), file=sys.stderr)
    return 20


def direct_state_failure(error_class: str) -> int:
    print(json.dumps({"result": "FAILED", "error_class": error_class}), file=sys.stderr)
    return 20


def command_scan(args: argparse.Namespace) -> int:
    state = Path(args.state_dir); ensure_dir(state)
    with exclusive_lock(state):
        return command_scan_locked(state)


def command_scan_locked(state: Path) -> int:
    baseline_path, scan_path, events_path = state / "baseline.json", state / "scan_state.json", state / "events.json"
    started = utcnow(); previous_scan = None; last_clean = None
    previous_doc: dict = {}
    if scan_path.is_file():
        try:
            previous_doc = read_json(scan_path)
            previous_scan = previous_doc.get("scan_finished_at")
        except Exception:
            return direct_state_failure("StateScanCorruptError")
    incident_open = bool(previous_doc.get("incident_open")) or previous_doc.get("result") in {"ANOMALY", "ANOMALY_HISTORY"}
    incident_first = previous_doc.get("first_detected_at") if incident_open else None
    unbaselined_site_count = int(previous_doc.get("unbaselined_site_count", 0) or 0)
    last_clean = previous_doc.get("last_known_clean_at") if previous_doc else None
    previous_generation = previous_doc.get("baseline_generation") if previous_doc else None
    baseline_generation: Optional[str] = previous_generation if isinstance(previous_generation, str) and previous_generation else None
    try:
        previous_event_count = parse_nonnegative_int(previous_doc.get("event_count", 0), StateEventCountMismatchError, "event_count")
    except Exception:
        return direct_state_failure("StateEventCountMismatchError")
    budget: Optional[ScanBudget] = None
    limit: Optional[int] = None
    try:
        with wall_clock_timeout(scan_timeout_seconds()):
            limit = event_record_limit()
            budget = scan_budget_from_env()
            if not baseline_path.is_file():
                raise StateBaselineMissingError("baseline missing")
            baseline = read_json(baseline_path)
            if baseline.get("schema") != SCHEMA or not isinstance(baseline.get("sites"), dict) or not baseline["sites"]:
                raise ValueError("invalid baseline")
            current_generation = baseline.get("baseline_generation")
            if not isinstance(current_generation, str) or not current_generation:
                return direct_state_failure("StateGenerationMissingError")
            baseline_generation = current_generation
            if not previous_doc:
                return direct_state_failure("StateScanStateMissingError")
            if previous_doc.get("baseline_generation") != baseline_generation:
                return direct_state_failure("StateGenerationMismatchError")
            try:
                existing_events = load_events_consistent(events_path, previous_doc)
            except StateEventsMissingError:
                return direct_state_failure("StateEventsMissingError")
            except StateEventsCorruptError:
                return direct_state_failure("StateEventsCorruptError")
            except StateEventCountMismatchError:
                return direct_state_failure("StateEventCountMismatchError")
            if len(existing_events) > limit:
                raise EvidenceCapacityExceededError(limit, len(existing_events), 0)

            last_clean = baseline.get("last_known_clean_at") or last_clean
            baseline_roots = set(baseline["sites"])
            auto_discovered = discover([])
            new_sites = [root for root in auto_discovered if str(root) not in baseline_roots]
            unbaselined_site_count = len(new_sites)
            candidates = [unbaselined_site_event(root, iso(started)) for root in new_sites]
            current_by_site = {}
            for root_text, site in baseline["sites"].items():
                old = site.get("files")
                if not isinstance(old, dict):
                    raise ValueError("invalid files map")
                root = Path(root_text); current = collect(root, budget=budget); current_by_site[root_text] = current
                candidates.extend(diff(root, old, current, iso(started)))
            finished = utcnow()
            if candidates:
                events, current_first = merge_events(
                    events_path, candidates, last_clean,
                    existing_rows=existing_events, event_limit=limit,
                    preserve_since=incident_first,
                )
                first_detected = earliest_iso(incident_first, current_first)
                incident_open = True
                result = "ANOMALY"
            else:
                events = prune_events(
                    existing_events,
                    finished,
                    preserve_since=parse_iso(incident_first) if incident_open else None,
                )
                if len(events) > limit:
                    raise EvidenceCapacityExceededError(limit, len(existing_events), 0)
                if events_path.is_file() or events:
                    write_events(events_path, events)
                if incident_open:
                    first_detected = incident_first
                    result = "ANOMALY_HISTORY"
                else:
                    clean_at = iso(finished)
                    for root_text, current in current_by_site.items():
                        old = baseline["sites"][root_text].get("files", {})
                        for rel, meta in current.items():
                            prior = old.get(rel, {}) if isinstance(old, dict) else {}
                            meta["first_seen_at"] = prior.get("first_seen_at") if prior.get("sha256") == meta.get("sha256") else clean_at
                            meta["first_seen_at"] = meta["first_seen_at"] or clean_at
                            meta["last_seen_at"] = clean_at
                        baseline["sites"][root_text]["files"] = current
                        baseline["sites"][root_text]["tracked_count"] = len(current)
                    baseline["last_known_clean_at"] = clean_at
                    write_json(baseline_path, baseline)
                    first_detected = None
                    result = "CLEAN"
            result_doc = {
                "schema": SCHEMA, "baseline_generation": baseline_generation,
                "result": result, "previous_scan_at": previous_scan,
                "scan_started_at": iso(started), "scan_finished_at": iso(finished),
                "last_known_clean_at": baseline.get("last_known_clean_at"),
                "first_detected_at": first_detected, "incident_open": incident_open,
                "event_count": len(events), "event_record_limit": limit,
                "detected_this_scan": len(candidates),
                "site_count": len(baseline["sites"]), "unbaselined_site_count": unbaselined_site_count,
                "scan_timeout_seconds": scan_timeout_seconds(), "scan_budget": budget.snapshot(),
            }
            write_json(scan_path, result_doc)
            print(json.dumps(result_doc, ensure_ascii=False, sort_keys=True))
            return 0
    except Exception as error:
        return failure_state(
            state, started, previous_scan, last_clean, error,
            baseline_generation=baseline_generation,
            incident_open=incident_open, first_detected=incident_first,
            unbaselined_site_count=unbaselined_site_count,
            previous_event_count=previous_event_count,
            budget=budget, event_limit=limit,
        )


def failed_status(result: str, error_class: str, *, baseline: Optional[dict] = None, scan: Optional[dict] = None) -> dict:
    baseline = baseline or {}; scan = scan or {}
    return {
        "enabled": True, "status": "FAILED", "result": result,
        "error_class": error_class,
        "last_scan_at": scan.get("scan_finished_at"),
        "last_known_clean_at": scan.get("last_known_clean_at") or baseline.get("last_known_clean_at"),
        "first_detected_at": scan.get("first_detected_at"),
        "incident_open": bool(scan.get("incident_open")),
        "event_count": int(scan.get("event_count", 0) or 0) if str(scan.get("event_count", 0) or 0).isdigit() else 0,
        "unbaselined_site_count": int(scan.get("unbaselined_site_count", 0) or 0) if str(scan.get("unbaselined_site_count", 0) or 0).isdigit() else 0,
        "error_detail": scan.get("error_detail") if isinstance(scan.get("error_detail"), dict) else {},
    }


def status_doc(state: Path) -> dict:
    baseline_path, scan_path, events_path = state / "baseline.json", state / "scan_state.json", state / "events.json"
    if not baseline_path.is_file():
        residual_state = baseline_path.exists() or scan_path.exists() or events_path.exists()
        if residual_state:
            scan = {}
            if scan_path.is_file():
                try:
                    scan = read_json(scan_path)
                except Exception:
                    scan = {}
            return failed_status("STATE_BASELINE_MISSING", "StateBaselineMissingError", scan=scan)
        return {"enabled": False, "status": "NOT_ENABLED", "result": "NOT_ENABLED", "event_count": 0, "unbaselined_site_count": 0}
    try:
        baseline = read_json(baseline_path)
    except Exception as error:
        return failed_status("STATE_BASELINE_CORRUPT", error.__class__.__name__)
    generation = baseline.get("baseline_generation")
    if not isinstance(generation, str) or not generation:
        return failed_status("STATE_GENERATION_MISSING", "StateGenerationMissingError", baseline=baseline)
    if not scan_path.is_file():
        return failed_status("STATE_SCAN_STATE_MISSING", "StateScanStateMissingError", baseline=baseline)
    try:
        scan = read_json(scan_path)
    except Exception:
        return failed_status("STATE_SCAN_STATE_CORRUPT", "StateScanCorruptError", baseline=baseline)
    if scan.get("baseline_generation") != generation:
        return failed_status("STATE_GENERATION_MISMATCH", "StateGenerationMismatchError", baseline=baseline, scan=scan)
    result = scan.get("result", "UNKNOWN")
    if result not in {"BASELINE_READY", "CLEAN", "ANOMALY", "ANOMALY_HISTORY", "FAILED"}:
        return failed_status("STATE_SCAN_STATE_INVALID", "StateScanStateInvalidError", baseline=baseline, scan=scan)
    try:
        event_count = parse_nonnegative_int(scan.get("event_count"), StateEventCountMismatchError, "event_count")
        unbaselined = parse_nonnegative_int(scan.get("unbaselined_site_count", 0), StateEventCountMismatchError, "unbaselined_site_count")
    except StateEventCountMismatchError:
        return failed_status("STATE_SCAN_STATE_INVALID", "StateScanStateInvalidError", baseline=baseline, scan=scan)
    try:
        rows = load_events_consistent(events_path, scan)
    except StateEventsMissingError:
        return failed_status("STATE_EVENTS_MISSING", "StateEventsMissingError", baseline=baseline, scan=scan)
    except StateEventsCorruptError:
        return failed_status("STATE_EVENTS_CORRUPT", "StateEventsCorruptError", baseline=baseline, scan=scan)
    except StateEventCountMismatchError:
        return failed_status("STATE_EVENT_COUNT_MISMATCH", "StateEventCountMismatchError", baseline=baseline, scan=scan)
    try:
        limit = event_record_limit()
    except Exception:
        return failed_status("STATE_RESOURCE_CONFIG_INVALID", "ResourceBudgetConfigError", baseline=baseline, scan=scan)
    if len(rows) > limit:
        return failed_status("EVIDENCE_CAPACITY_EXCEEDED", "EvidenceCapacityExceededError", baseline=baseline, scan=scan)
    return {
        "enabled": True,
        "status": {
            "BASELINE_READY": "NORMAL", "CLEAN": "NORMAL", "ANOMALY": "ATTENTION",
            "ANOMALY_HISTORY": "ATTENTION", "FAILED": "FAILED",
        }[result],
        "result": result, "error_class": scan.get("error_class"),
        "last_scan_at": scan.get("scan_finished_at"),
        "last_known_clean_at": scan.get("last_known_clean_at"), "first_detected_at": scan.get("first_detected_at"),
        "incident_open": bool(scan.get("incident_open")),
        "event_count": event_count, "unbaselined_site_count": unbaselined,
        "error_detail": scan.get("error_detail") if isinstance(scan.get("error_detail"), dict) else {},
    }


def command_status(args: argparse.Namespace) -> int:
    out = status_doc(Path(args.state_dir))
    if args.kv:
        detail = out.get("error_detail") or {}
        values = {
            "P07_IE_ENABLED": 1 if out["enabled"] else 0, "P07_IE_STATUS": out["status"], "P07_IE_RESULT": out["result"],
            "P07_IE_LAST_SCAN_AT": out.get("last_scan_at") or "-", "P07_IE_LAST_KNOWN_CLEAN_AT": out.get("last_known_clean_at") or "-",
            "P07_IE_FIRST_DETECTED_AT": out.get("first_detected_at") or "-", "P07_IE_EVENT_COUNT": out.get("event_count", 0),
            "P07_IE_UNBASELINED_SITE_COUNT": out.get("unbaselined_site_count", 0),
            "P07_IE_ERROR_CLASS": out.get("error_class") or "-",
            "P07_IE_ERROR_RESOURCE": detail.get("resource") or "-",
            "P07_IE_ERROR_LIMIT": detail.get("limit") or detail.get("event_limit") or "-",
        }
        for key, value in values.items(): print(f"{key}={value}")
    else: print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return 0


def command_report(args: argparse.Namespace) -> int:
    state = Path(args.state_dir)
    status = status_doc(state)
    if status.get("status") == "FAILED" and str(status.get("result", "")).startswith("STATE_"):
        if args.json:
            print(json.dumps({"status": status, "events": []}, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print("P07 · 网站入侵留证")
            print("状态       FAILED")
            print(f"失败类型   {status.get('error_class') or '-'}")
            print("说明       留证状态不完整，已停止读取事件明细。")
        return 20
    scan = read_json(state / "scan_state.json") if (state / "scan_state.json").is_file() else {}
    events = load_events_consistent(state / "events.json", scan) if scan else []
    events = sorted(events, key=lambda x: x.get("first_detected_at") or "", reverse=True)
    if args.json:
        print(json.dumps({"scan": scan, "events": events[:args.limit]}, ensure_ascii=False, sort_keys=True, indent=2)); return 0
    print("P07 · 网站入侵留证")
    print(f"状态       {scan.get('result', 'NOT_ENABLED')}")
    print(f"最近扫描   {scan.get('scan_finished_at') or '-'}")
    print(f"可信基线   {scan.get('last_known_clean_at') or '-'}")
    print(f"首次异常   {scan.get('first_detected_at') or '-'}")
    print(f"异常事件   {len(events)}")
    print(f"未纳入基线 {int(scan.get('unbaselined_site_count', 0) or 0)}")
    if not events: print("\n未记录异常。"); return 0
    print("\n最近异常：")
    for event in events[:args.limit]:
        print(f"- {event.get('first_detected_at')}  {event.get('type')}  {event.get('site')}:{event.get('relative_path')}")
        for req in (event.get("correlated_requests") or [])[:3]:
            print(f"  关联请求  {req.get('timestamp')} {req.get('source_ip')} {req.get('method')} {req.get('path_without_query')} {req.get('status')}  [仅线索]")
        meta = event.get("correlation_meta") or {}
        if meta.get("status") == "PARTIAL_BUDGET":
            print("  日志关联  已达到安全读取上限，仅保留已读范围内线索")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(); root.add_argument("--state-dir", default=os.environ.get("P07_IE_STATE_DIR", DEFAULT_STATE_DIR))
    subs = root.add_subparsers(dest="command", required=True)
    p = subs.add_parser("baseline"); p.add_argument("--site-root", action="append", default=[]); p.set_defaults(func=command_baseline)
    p = subs.add_parser("scan"); p.set_defaults(func=command_scan)
    p = subs.add_parser("status"); p.add_argument("--kv", action="store_true"); p.set_defaults(func=command_status)
    p = subs.add_parser("report"); p.add_argument("--limit", type=int, default=20); p.add_argument("--json", action="store_true"); p.set_defaults(func=command_report)
    return root


def main() -> int:
    args = parser().parse_args()
    try: return int(args.func(args))
    except Exception as error:
        print(f"P07_IE_ERROR={error.__class__.__name__}", file=sys.stderr); return 20


if __name__ == "__main__": raise SystemExit(main())
