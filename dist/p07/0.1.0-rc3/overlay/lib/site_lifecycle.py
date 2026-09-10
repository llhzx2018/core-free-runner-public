#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import secrets
from typing import Any

import cloudpanel
import inventory


class SiteLifecycleError(RuntimeError):
    pass


@dataclass(frozen=True)
class TargetSiteIdentity:
    domain: str
    site_user: str
    site_password: str
    site_root: str


def _stable_token(text: str, length: int = 8) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _stem(domain: str, max_len: int = 10) -> str:
    raw = domain.split(".", 1)[0]
    value = re.sub(r"[^a-z0-9]", "", raw.lower())[:max_len]
    return value or "site"


def derive_target_identity(domain: str, seed: str) -> TargetSiteIdentity:
    domain = cloudpanel.validate_domain(domain)
    token = _stable_token(f"site:{domain}:{seed}", 8)
    user = cloudpanel.validate_user(f"p07{_stem(domain, 8)}{token[:6]}")
    return TargetSiteIdentity(
        domain=domain,
        site_user=user,
        site_password=secrets.token_urlsafe(24),
        site_root=f"/home/{user}/htdocs/{domain}",
    )


def derive_database_identity(domain: str, seed: str, index: int) -> tuple[str, str, str]:
    domain = cloudpanel.validate_domain(domain)
    token = _stable_token(f"db:{domain}:{seed}:{index}", 10)
    database = cloudpanel.validate_name(f"p07_{token}_{index}", "database")
    username = cloudpanel.validate_name(f"p07u_{token[:8]}_{index}", "database user")
    password = secrets.token_urlsafe(30)
    return database, username, password


def find_site(root: Path, domain: str) -> dict[str, Any] | None:
    domain = cloudpanel.validate_domain(domain)
    try:
        manifest = inventory.build_manifest(root.resolve())
    except Exception as exc:
        raise SiteLifecycleError("CloudPanel inventory is unavailable") from exc
    for site in manifest.get("sites", []):
        if not isinstance(site, dict):
            continue
        domains = site.get("domains", []) if isinstance(site.get("domains"), list) else []
        if site.get("domain") == domain or domain in domains:
            return site
    return None


def ensure_domain_available(root: Path, domain: str) -> None:
    domain = cloudpanel.validate_domain(domain)
    if find_site(root, domain) is not None:
        raise SiteLifecycleError("target domain already exists in CloudPanel")
    for candidate in (root.resolve() / "home").glob(f"*/htdocs/{domain}") if (root.resolve() / "home").is_dir() else []:
        if candidate.exists() or candidate.is_symlink():
            raise SiteLifecycleError("target domain path already exists")


def create_site(
    source_site: dict[str, Any],
    identity: TargetSiteIdentity,
    *,
    clpctl: str = "clpctl",
    vhost_template: str = "Generic",
) -> None:
    runtime = source_site.get("runtime", {}) if isinstance(source_site.get("runtime"), dict) else {}
    runtime_type = str(runtime.get("type", "")).lower().replace("-", "_")
    version = str(runtime.get("version", ""))
    app_port = runtime.get("app_port")

    try:
        if runtime_type == "php":
            if not version or version == "UNKNOWN":
                raise SiteLifecycleError("PHP version is unavailable")
            cloudpanel.add_php_site(identity.domain, version, identity.site_user, identity.site_password,
                                    vhost_template=vhost_template or "Generic", clpctl=clpctl)
        elif runtime_type in {"static", "static_html"}:
            cloudpanel.add_static_site(identity.domain, identity.site_user, identity.site_password, clpctl=clpctl)
        elif runtime_type in {"nodejs", "node_js"}:
            if not version or version == "UNKNOWN" or app_port in (None, "UNKNOWN"):
                raise SiteLifecycleError("Node.js runtime metadata is incomplete")
            cloudpanel.add_nodejs_site(identity.domain, version, app_port, identity.site_user, identity.site_password, clpctl=clpctl)
        elif runtime_type == "python":
            if not version or version == "UNKNOWN" or app_port in (None, "UNKNOWN"):
                raise SiteLifecycleError("Python runtime metadata is incomplete")
            cloudpanel.add_python_site(identity.domain, version, app_port, identity.site_user, identity.site_password, clpctl=clpctl)
        elif runtime_type in {"reverse_proxy", "reverseproxy"}:
            if app_port in (None, "UNKNOWN"):
                raise SiteLifecycleError("reverse proxy port is unavailable")
            cloudpanel.add_reverse_proxy_site(identity.domain, f"http://127.0.0.1:{int(app_port)}",
                                              identity.site_user, identity.site_password, clpctl=clpctl)
        else:
            raise SiteLifecycleError(f"unsupported CloudPanel runtime: {runtime_type or 'UNKNOWN'}")
    except (cloudpanel.CloudPanelError, ValueError) as exc:
        raise SiteLifecycleError("CloudPanel site creation failed") from exc


def cleanup_site(domain: str, *, clpctl: str = "clpctl") -> bool:
    try:
        cloudpanel.delete_site(domain, force=True, clpctl=clpctl)
        return True
    except (cloudpanel.CloudPanelError, ValueError):
        return False


def cleanup_database(database: str, *, clpctl: str = "clpctl") -> bool:
    try:
        cloudpanel.delete_database(database, force=True, clpctl=clpctl)
        return True
    except (cloudpanel.CloudPanelError, ValueError):
        return False
