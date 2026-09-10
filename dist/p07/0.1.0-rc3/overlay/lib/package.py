#!/usr/bin/env python3
from __future__ import annotations

# RC3 compatibility facade. The mature backup engine remains byte-for-byte in
# package_core.py. CloudPanel database export is routed through the shared
# CloudPanel foundation adapter, while build_backup keeps the safe application-
# config credential discovery used by current CloudPanel schemas.
import gzip
from pathlib import Path

import cloudpanel as _cloudpanel
import package_core as _core


def _export_mysql_via_cloudpanel(databases: list[str], out_dir: Path, clpctl: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    _core.chmod_private(out_dir, directory=True)
    results: list[dict] = []
    for database in databases:
        filename = f"{_core.safe_name(database)}.sql.gz"
        target = out_dir / filename
        try:
            _cloudpanel.export_database(database, target, clpctl=clpctl)
        except _cloudpanel.CloudPanelError as exc:
            exit_code = "UNKNOWN" if exc.returncode is None else str(exc.returncode)
            raise RuntimeError(
                f"CloudPanel database export failed: {database} (exit {exit_code})"
            ) from exc
        _core.chmod_private(target)
        try:
            with gzip.open(target, "rb") as handle:
                handle.read(64)
        except OSError as exc:
            raise RuntimeError(f"MySQL gzip validation failed: {database}") from exc
        results.append({
            "database": database,
            "file": f"mysql/{filename}",
            "method": "clpctl_db_export",
        })
    return results


# package_core.build_backup resolves export_mysql from its module globals at
# runtime. Patch only that primitive; the mature packaging engine stays intact.
_core.export_mysql = _export_mysql_via_cloudpanel

from package_core import *  # noqa: F401,F403,E402
import backup_frontend as _frontend  # noqa: E402

build_backup = _frontend.build_backup_with_discovery
export_mysql = _export_mysql_via_cloudpanel


def main() -> int:
    return _frontend.main()


if __name__ == "__main__":
    raise SystemExit(main())
