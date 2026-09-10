#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
from typing import Iterable, Sequence

DEFAULT_TIMEOUT = 300
LONG_TIMEOUT = 1800
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
USER_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ALLOWED_USER_ROLES = {"admin", "site-manager", "user"}


class CloudPanelError(RuntimeError):
    """A bounded CloudPanel CLI failure safe to classify without secret output."""

    def __init__(self, operation: str, returncode: int | None = None):
        self.operation = operation
        self.returncode = returncode
        suffix = "" if returncode is None else f" (exit {returncode})"
        super().__init__(f"CloudPanel operation failed: {operation}{suffix}")


@dataclass(frozen=True)
class CommandResult:
    operation: str
    returncode: int
    stdout: str


def _scalar(value: object, label: str) -> str:
    text = str(value)
    if not text or "\x00" in text or "\n" in text or "\r" in text:
        raise ValueError(f"invalid {label}")
    return text


def validate_domain(domain: str) -> str:
    domain = _scalar(domain.strip().rstrip("."), "domain").lower()
    if not DOMAIN_RE.fullmatch(domain):
        raise ValueError("invalid domain")
    return domain


def validate_name(value: str, label: str = "name") -> str:
    value = _scalar(value.strip(), label)
    if not NAME_RE.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def validate_user(value: str) -> str:
    value = _scalar(value.strip(), "site user")
    if not USER_RE.fullmatch(value):
        raise ValueError("invalid site user")
    return value


def validate_email(value: str) -> str:
    value = _scalar(value.strip(), "email")
    if not EMAIL_RE.fullmatch(value):
        raise ValueError("invalid email")
    return value


def validate_version(value: str, label: str) -> str:
    value = _scalar(value.strip(), label)
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,2}", value):
        raise ValueError(f"invalid {label}")
    return value


def validate_port(value: int | str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    return port


def validate_file(path: str | Path, label: str) -> str:
    candidate = Path(path).expanduser().resolve(strict=False)
    if "\x00" in str(candidate) or "\n" in str(candidate) or "\r" in str(candidate):
        raise ValueError(f"invalid {label}")
    return str(candidate)


def run(
    args: Sequence[str],
    *,
    clpctl: str = "clpctl",
    timeout: int = DEFAULT_TIMEOUT,
    operation: str | None = None,
) -> CommandResult:
    if not args:
        raise ValueError("CloudPanel command is required")
    command = [_scalar(clpctl, "clpctl"), *[_scalar(item, "argument") for item in args]]
    op = operation or args[0]
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CloudPanelError(op) from exc
    if proc.returncode != 0:
        raise CloudPanelError(op, proc.returncode)
    return CommandResult(op, proc.returncode, proc.stdout)


def version(*, clpctl: str = "clpctl") -> str:
    return run(["--version"], clpctl=clpctl, operation="version").stdout.strip()


def import_vhost_templates(*, clpctl: str = "clpctl") -> None:
    run(["vhost-templates:import"], clpctl=clpctl, timeout=LONG_TIMEOUT, operation="vhost_templates_import")


def list_vhost_templates(*, clpctl: str = "clpctl") -> str:
    return run(["vhost-templates:list"], clpctl=clpctl, operation="vhost_templates_list").stdout


def add_vhost_template(name: str, source: str | Path, *, clpctl: str = "clpctl") -> None:
    source_text = _scalar(source, "vhost template source")
    if not re.fullmatch(r"https?://[^\s]+", source_text):
        source_text = validate_file(source_text, "vhost template file")
        if not Path(source_text).is_file():
            raise ValueError("vhost template file does not exist")
    run([
        "vhost-template:add",
        f"--name={_scalar(name.strip(), 'vhost template name')}",
        f"--file={source_text}",
    ], clpctl=clpctl, timeout=LONG_TIMEOUT, operation="vhost_template_add")


def view_vhost_template(name: str, *, clpctl: str = "clpctl") -> str:
    return run([
        "vhost-template:view",
        f"--name={_scalar(name.strip(), 'vhost template name')}",
    ], clpctl=clpctl, operation="vhost_template_view").stdout


def delete_vhost_template(name: str, *, clpctl: str = "clpctl") -> None:
    run([
        "vhost-template:delete",
        f"--name={_scalar(name.strip(), 'vhost template name')}",
    ], clpctl=clpctl, operation="vhost_template_delete")


def _site_common(domain: str, site_user: str, site_password: str) -> list[str]:
    return [
        f"--domainName={validate_domain(domain)}",
        f"--siteUser={validate_user(site_user)}",
        f"--siteUserPassword={_scalar(site_password, 'site password')}",
    ]


def add_php_site(domain: str, php_version: str, site_user: str, site_password: str, *, vhost_template: str = "Generic", clpctl: str = "clpctl") -> None:
    run(["site:add:php", f"--phpVersion={validate_version(php_version, 'PHP version')}", f"--vhostTemplate={_scalar(vhost_template, 'vhost template')}", *_site_common(domain, site_user, site_password)], clpctl=clpctl, operation="site_add_php")


def add_static_site(domain: str, site_user: str, site_password: str, *, clpctl: str = "clpctl") -> None:
    run(["site:add:static", *_site_common(domain, site_user, site_password)], clpctl=clpctl, operation="site_add_static")


def add_nodejs_site(domain: str, nodejs_version: str, app_port: int | str, site_user: str, site_password: str, *, clpctl: str = "clpctl") -> None:
    run(["site:add:nodejs", f"--nodejsVersion={validate_version(nodejs_version, 'Node.js version')}", f"--appPort={validate_port(app_port)}", *_site_common(domain, site_user, site_password)], clpctl=clpctl, operation="site_add_nodejs")


def add_python_site(domain: str, python_version: str, app_port: int | str, site_user: str, site_password: str, *, clpctl: str = "clpctl") -> None:
    run(["site:add:python", f"--pythonVersion={validate_version(python_version, 'Python version')}", f"--appPort={validate_port(app_port)}", *_site_common(domain, site_user, site_password)], clpctl=clpctl, operation="site_add_python")


def add_reverse_proxy_site(domain: str, reverse_proxy_url: str, site_user: str, site_password: str, *, clpctl: str = "clpctl") -> None:
    url = _scalar(reverse_proxy_url.strip(), "reverse proxy URL")
    if not re.fullmatch(r"https?://[^\s]+", url):
        raise ValueError("invalid reverse proxy URL")
    run(["site:add:reverse-proxy", f"--reverseProxyUrl={url}", *_site_common(domain, site_user, site_password)], clpctl=clpctl, operation="site_add_reverse_proxy")


def delete_site(domain: str, *, force: bool = False, clpctl: str = "clpctl") -> None:
    args = ["site:delete", f"--domainName={validate_domain(domain)}"]
    if force:
        args.append("--force")
    run(args, clpctl=clpctl, operation="site_delete")


def add_database(domain: str, database: str, username: str, password: str, *, clpctl: str = "clpctl") -> None:
    run(["db:add", f"--domainName={validate_domain(domain)}", f"--databaseName={validate_name(database, 'database')}", f"--databaseUserName={validate_name(username, 'database user')}", f"--databaseUserPassword={_scalar(password, 'database password')}"] , clpctl=clpctl, operation="db_add")


def delete_database(database: str, *, force: bool = False, clpctl: str = "clpctl") -> None:
    args = ["db:delete", f"--databaseName={validate_name(database, 'database')}"]
    if force:
        args.append("--force")
    run(args, clpctl=clpctl, operation="db_delete")


def export_database(database: str, output: str | Path, *, clpctl: str = "clpctl") -> Path:
    target = Path(validate_file(output, "database export file"))
    run(["db:export", f"--databaseName={validate_name(database, 'database')}", f"--file={target}"], clpctl=clpctl, timeout=LONG_TIMEOUT, operation="db_export")
    if not target.is_file() or target.stat().st_size == 0:
        raise CloudPanelError("db_export_output")
    return target


def import_database(database: str, dump: str | Path, *, clpctl: str = "clpctl") -> None:
    source = Path(validate_file(dump, "database import file"))
    if not source.is_file():
        raise ValueError("database import file does not exist")
    run(["db:import", f"--databaseName={validate_name(database, 'database')}", f"--file={source}"], clpctl=clpctl, timeout=LONG_TIMEOUT, operation="db_import")


def install_certificate(domain: str, private_key: str | Path, certificate: str | Path, *, certificate_chain: str | Path | None = None, clpctl: str = "clpctl") -> None:
    args = ["site:install:certificate", f"--domainName={validate_domain(domain)}", f"--privateKey={validate_file(private_key, 'private key')}", f"--certificate={validate_file(certificate, 'certificate')}"]
    if certificate_chain is not None:
        args.append(f"--certificateChain={validate_file(certificate_chain, 'certificate chain')}")
    run(args, clpctl=clpctl, operation="certificate_install")


def install_lets_encrypt(domain: str, *, subject_alt_names: Iterable[str] = (), clpctl: str = "clpctl") -> None:
    args = ["lets-encrypt:install:certificate", f"--domainName={validate_domain(domain)}"]
    sans = [validate_domain(item) for item in subject_alt_names]
    if sans:
        args.append(f"--subjectAlternativeName={','.join(sans)}")
    run(args, clpctl=clpctl, timeout=LONG_TIMEOUT, operation="lets_encrypt_install")


def reset_permissions(path: str | Path, *, directories: str = "770", files: str = "660", clpctl: str = "clpctl") -> None:
    if not re.fullmatch(r"[0-7]{3,4}", directories) or not re.fullmatch(r"[0-7]{3,4}", files):
        raise ValueError("invalid permission mode")
    run(["system:permissions:reset", f"--directories={directories}", f"--files={files}", f"--path={validate_file(path, 'permissions path')}"] , clpctl=clpctl, operation="permissions_reset")


def purge_varnish(target: str = "all", *, clpctl: str = "clpctl") -> None:
    target = _scalar(target.strip(), "varnish purge target")
    run(["varnish-cache:purge", f"--purge={target}"], clpctl=clpctl, operation="varnish_purge")


def add_panel_user(username: str, email: str, first_name: str, last_name: str, password: str, *, role: str = "user", sites: Iterable[str] = (), timezone: str = "UTC", enabled: bool = True, clpctl: str = "clpctl") -> None:
    role = _scalar(role.strip(), "role")
    if role not in ALLOWED_USER_ROLES:
        raise ValueError("invalid role")
    args = ["user:add", f"--userName={validate_user(username)}", f"--email={validate_email(email)}", f"--firstName={_scalar(first_name.strip(), 'first name')}", f"--lastName={_scalar(last_name.strip(), 'last name')}", f"--password={_scalar(password, 'password')}", f"--role={role}", f"--timezone={_scalar(timezone.strip(), 'timezone')}", f"--status={1 if enabled else 0}"]
    site_list = [validate_domain(site) for site in sites]
    if role == "user" and site_list:
        args.append(f"--sites={','.join(site_list)}")
    run(args, clpctl=clpctl, operation="user_add")


def list_panel_users(*, clpctl: str = "clpctl") -> str:
    return run(["user:list"], clpctl=clpctl, operation="user_list").stdout


def delete_panel_user(username: str, *, clpctl: str = "clpctl") -> None:
    run(["user:delete", f"--userName={validate_user(username)}"], clpctl=clpctl, operation="user_delete")


def reset_panel_user_password(username: str, password: str, *, clpctl: str = "clpctl") -> None:
    run(["user:reset:password", f"--userName={validate_user(username)}", f"--password={_scalar(password, 'password')}"] , clpctl=clpctl, operation="user_reset_password")


def disable_panel_user_mfa(username: str, *, clpctl: str = "clpctl") -> None:
    run(["user:disable:mfa", f"--userName={validate_user(username)}"], clpctl=clpctl, operation="user_disable_mfa")


def enable_panel_basic_auth(username: str, password: str, *, clpctl: str = "clpctl") -> None:
    run(["cloudpanel:enable:basic-auth", f"--userName={validate_user(username)}", f"--password={_scalar(password, 'password')}"] , clpctl=clpctl, operation="cloudpanel_enable_basic_auth")


def disable_panel_basic_auth(*, clpctl: str = "clpctl") -> None:
    run(["cloudpanel:disable:basic-auth"], clpctl=clpctl, operation="cloudpanel_disable_basic_auth")


def update_cloudflare_ips(*, clpctl: str = "clpctl") -> None:
    run(["cloudflare:update:ips"], clpctl=clpctl, timeout=LONG_TIMEOUT, operation="cloudflare_update_ips")
