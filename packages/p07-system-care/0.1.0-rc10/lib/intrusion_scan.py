from __future__ import annotations

from pathlib import Path

import intrusion_scan_rc9 as _base
from intrusion_scan_rc9 import *  # noqa: F401,F403


def _cloudpanel_user_bounded_roots(home_resolved: Path, rows: list[tuple[str, str]]) -> list[Path]:
    """Find WordPress roots only inside CloudPanel-proven site-user htdocs trees.

    This is a bounded secondary path for real CloudPanel layouts whose document root
    differs from /home/<user>/htdocs/<domain>. It never scans arbitrary /home users,
    never follows wp-config.php symlinks, and keeps the existing one/two-level bound.
    """
    found: dict[str, Path] = {}
    users = sorted({str(user).strip() for _, user in rows if str(user).strip()})
    for user in users:
        user_home = home_resolved / user
        try:
            user_resolved = user_home.resolve(strict=True)
            user_resolved.relative_to(home_resolved)
        except (FileNotFoundError, ValueError):
            continue
        if user_resolved.parent != home_resolved:
            continue

        htdocs = user_resolved / "htdocs"
        if not htdocs.is_dir():
            continue
        try:
            htdocs_resolved = htdocs.resolve(strict=True)
            htdocs_resolved.relative_to(user_resolved)
        except (FileNotFoundError, ValueError):
            continue

        for pattern in ("*/wp-config.php", "*/*/wp-config.php"):
            for marker in htdocs_resolved.glob(pattern):
                resolved = _base._validated_candidate(marker.parent, home_resolved)
                if resolved is not None:
                    found[str(resolved)] = resolved
    return [found[key] for key in sorted(found)]


def discover(explicit: list[str]) -> list[Path]:
    if explicit:
        return _base.discover(explicit)

    home = _base.discovery_home()
    if not home.is_dir():
        return []
    home_resolved = home.resolve(strict=True)

    authoritative, rows = _base._cloudpanel_sites()
    if authoritative:
        _, primary = _base._discover_cloudpanel(home_resolved)
        bounded = _cloudpanel_user_bounded_roots(home_resolved, rows)
        merged = {str(path): path for path in primary}
        for path in bounded:
            merged[str(path)] = path
        return [merged[key] for key in sorted(merged)]

    return _base._discover_fallback(home, home_resolved)
