#!/usr/bin/env python3
from __future__ import annotations

# RC3 compatibility facade. The mature backup engine remains byte-for-byte in
# package_core.py; only build_backup is upgraded with safe application-config
# credential discovery for current CloudPanel schemas that no longer expose
# portable per-database plaintext credentials.
from package_core import *  # noqa: F401,F403
import backup_frontend as _frontend

build_backup = _frontend.build_backup_with_discovery


def main() -> int:
    return _frontend.main()


if __name__ == "__main__":
    raise SystemExit(main())
