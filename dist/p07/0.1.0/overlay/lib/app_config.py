#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urlsplit, urlunsplit

ENV_NAMES = (".env", ".env.local", ".env.production", ".env.prod")
DB_NAME_KEYS = {"DB_DATABASE", "DB_NAME", "MYSQL_DATABASE", "DATABASE_NAME"}
DB_USER_KEYS = {"DB_USERNAME", "DB_USER", "MYSQL_USER", "DATABASE_USER"}
DB_PASS_KEYS = {"DB_PASSWORD", "DB_PASS", "MYSQL_PASSWORD", "DATABASE_PASSWORD"}
DB_URL_KEYS = {"DATABASE_URL", "MYSQL_URL", "MARIADB_URL"}
SITE_URL_KEYS = {"APP_URL", "SITE_URL", "URL"}


class AppConfigError(RuntimeError):
    pass


def _php_single_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def rewrite_wordpress_config(path: Path, database: str, username: str, password: str) -> None:
    try:
        original = path.read_text(encoding="utf-8")
        mode = path.stat().st_mode & 0o777
    except OSError as exc:
        raise AppConfigError("WordPress wp-config.php cannot be read") from exc

    replacements = {
        "DB_NAME": database,
        "DB_USER": username,
        "DB_PASSWORD": password,
    }
    text = original
    for key, value in replacements.items():
        pattern = re.compile(
            rf"define\s*\(\s*(['\"])({re.escape(key)})\1\s*,\s*(['\"])(.*?)\3\s*\)\s*;",
            re.DOTALL,
        )
        replacement = f"define('{key}', '{_php_single_quote(value)}');"
        text, count = pattern.subn(lambda _m, r=replacement: r, text, count=1)
        if count != 1:
            # Keep compatibility with define("KEY", "...") and unusual quote pairing.
            pattern = re.compile(
                rf"define\s*\(\s*(['\"]){re.escape(key)}\1\s*,\s*(['\"])(.*?)\2\s*\)\s*;",
                re.DOTALL,
            )
            text, count = pattern.subn(lambda _m, r=replacement: r, text, count=1)
        if count != 1:
            raise AppConfigError(f"WordPress {key} mapping is unavailable")

    fd, temp_name = tempfile.mkstemp(prefix=".vfops-wp-config-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _split_env_line(line: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(\s*(?:export\s+)?)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)(.*?)(\r?\n?)$", line)
    if not match:
        return None
    prefix = f"{match.group(1)}{match.group(2)}{match.group(3)}"
    return match.group(2), prefix, f"{match.group(4)}{match.group(5)}"


def _env_quote_like(old: str, value: str) -> str:
    newline = "\n" if old.endswith("\n") else ""
    body = old[:-1] if newline else old
    stripped = body.strip()
    if stripped.startswith("'") and stripped.endswith("'"):
        return "'" + value.replace("'", "\\'") + "'" + newline
    if stripped.startswith('"') and stripped.endswith('"'):
        return '"' + value.replace('"', '\\"') + '"' + newline
    return value + newline


def _rewrite_database_url(old_value: str, database: str, username: str, password: str) -> str:
    quote_char = ""
    stripped = old_value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        quote_char = stripped[0]
        stripped = stripped[1:-1]
    parts = urlsplit(stripped)
    if parts.scheme not in {"mysql", "mariadb"} or not parts.hostname:
        raise AppConfigError("database URL cannot be safely remapped")
    host = parts.hostname
    if parts.port:
        host = f"{host}:{parts.port}"
    netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{host}"
    rebuilt = urlunsplit((parts.scheme, netloc, f"/{quote(database, safe='')}", parts.query, parts.fragment))
    return f"{quote_char}{rebuilt}{quote_char}" if quote_char else rebuilt


def rewrite_dotenv(
    path: Path,
    database: str,
    username: str,
    password: str,
    source_domain: str,
    target_domain: str,
) -> bool:
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        mode = path.stat().st_mode & 0o777
    except OSError:
        return False

    changed = False
    mapped_db = mapped_user = mapped_pass = False
    out: list[str] = []
    for line in lines:
        parsed = _split_env_line(line)
        if parsed is None:
            out.append(line)
            continue
        key, prefix, old_value = parsed
        new_value: str | None = None
        if key in DB_NAME_KEYS:
            new_value = _env_quote_like(old_value, database)
            mapped_db = True
        elif key in DB_USER_KEYS:
            new_value = _env_quote_like(old_value, username)
            mapped_user = True
        elif key in DB_PASS_KEYS:
            new_value = _env_quote_like(old_value, password)
            mapped_pass = True
        elif key in DB_URL_KEYS:
            new_value = _env_quote_like(
                old_value,
                _rewrite_database_url(old_value, database, username, password).strip("'\""),
            )
            mapped_db = mapped_user = mapped_pass = True
        elif key in SITE_URL_KEYS and source_domain in old_value:
            new_value = old_value.replace(source_domain, target_domain)
        if new_value is None:
            out.append(line)
            continue
        out.append(prefix + new_value)
        changed = True

    if not changed or not (mapped_db and mapped_user and mapped_pass):
        return False

    fd, temp_name = tempfile.mkstemp(prefix=".vfops-env-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines(out)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    return True


def locate_wordpress_config(site: Path) -> Path | None:
    for candidate in (site / "wp-config.php", site / "public" / "wp-config.php"):
        if candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None


def verify_rewritten_application_database_config(
    site: Path, database: str, username: str, password: str,
) -> bool:
    """Fail closed on ambiguous target app database mappings.

    A matching comment, shadowed duplicate, or conflicting .env override must
    never prove that the imported database is connected to the application.
    This is intentionally stricter than guessing an application's config
    precedence; no credential or config content is returned to the caller.
    """
    def bounded(path: Path) -> str | None:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
                return None
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            return None

    # A symlinked or duplicated WordPress entrypoint is ambiguous even when
    # an unrelated .env appears correct. Never fall back to .env in that case.
    wp_candidates = (site / "wp-config.php", site / "public" / "wp-config.php")
    if any(path.is_symlink() for path in wp_candidates):
        return False
    if sum(path.is_file() for path in wp_candidates) > 1:
        return False
    config = locate_wordpress_config(site)
    if config is not None:
        content = bounded(config)
        if content is None:
            return False
        for name, value in (("DB_NAME", database), ("DB_USER", username),
                            ("DB_PASSWORD", password)):
            # The migration rewrite uses one exact standalone literal define.
            # Counting all line-start definitions prevents a second active
            # definition from shadowing the expected credentials. A commented
            # line or a matching substring inside other code cannot prove it.
            definition = re.compile(
                rf"(?m)^[ \t]*define[ \t]*\([ \t]*(['\"]){re.escape(name)}\1[ \t]*,"
            )
            expected = f"define('{name}', '{_php_single_quote(value)}');"
            if (len(definition.findall(content)) != 1
                    or not re.search(r"(?m)^[ \t]*" + re.escape(expected)
                                     + r"[ \t]*$", content)):
                return False
        return True

    from urllib.parse import unquote
    found = False
    for name in ENV_NAMES:
        for file in (site / name, site / "public" / name):
            if file.is_symlink():
                return False
            if not file.exists():
                continue
            content = bounded(file)
            if content is None:
                return False
            seen: dict[str, str] = {}
            for line in content.splitlines(keepends=True):
                parsed = _split_env_line(line)
                if parsed is None:
                    continue
                key, _, value = parsed
                if key not in DB_NAME_KEYS | DB_USER_KEYS | DB_PASS_KEYS | DB_URL_KEYS:
                    continue
                body = value.strip()
                if len(body) >= 2 and body[0] == body[-1] and body[0] in {"'", '"'}:
                    body = body[1:-1]
                current: dict[str, str] = {}
                if key in DB_NAME_KEYS:
                    current["database"] = body
                elif key in DB_USER_KEYS:
                    current["user"] = body
                elif key in DB_PASS_KEYS:
                    current["password"] = body
                else:
                    try:
                        parts = urlsplit(body)
                        if parts.scheme not in ("mysql", "mariadb") or not parts.hostname:
                            return False
                        current = {
                            "database": unquote(parts.path.lstrip("/")),
                            "user": unquote(parts.username or ""),
                            "password": unquote(parts.password or ""),
                        }
                    except ValueError:
                        return False
                for field, actual in current.items():
                    if field in seen and seen[field] != actual:
                        return False
                    seen[field] = actual
            if seen:
                if seen != {"database": database, "user": username,
                            "password": password}:
                    return False
                found = True
    return found


def rewrite_application_database_config(
    staged_site: Path,
    source_domain: str,
    target_domain: str,
    database: str,
    username: str,
    password: str,
) -> tuple[str, Path | None]:
    wp_config = locate_wordpress_config(staged_site)
    if wp_config is not None:
        rewrite_wordpress_config(wp_config, database, username, password)
        return "WORDPRESS_WP_CONFIG", wp_config

    for name in ENV_NAMES:
        for candidate in (staged_site / name, staged_site / "public" / name):
            if candidate.is_file() and not candidate.is_symlink():
                if rewrite_dotenv(candidate, database, username, password, source_domain, target_domain):
                    return "DOTENV", candidate

    raise AppConfigError("application database configuration cannot be safely remapped")
