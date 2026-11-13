#!/usr/bin/env bash
# P07-M03 网站与数据: Owner field repair. Authenticated, SHA256-pinned ZIP -> guarded atomic installer.
# Only this module's runtime path changes; databases, websites, DNS and other modules stay untouched.
set -Eeuo pipefail
MODULE='P07-M03'
BUILD='0.1.0-release135'
RELEASE='p07-v0.1.0-five-modules-ux3-20261113'
ZIP_NAME='P07-M03-0.1.0-release135.zip'
ZIP_SHA256='2e5509bf7f2d36c5bc9f4ec9e2e05016e9e30f94cff546880e93e441af8af866'
RUNTIME_BLOB='f57e114e0ef23f73a1ec12ba864d8f2e67a5bd30'
INSTALLER_BLOB='dc6e0be1419ee77a71fabb332cb8f7c97237122f'
URL="https://github.com/llhzx2018/core-free-runner-public/releases/download/$RELEASE/$ZIP_NAME"
# SHA256-identical copy of the previously published official ZIP, kept under
# one immutable Git commit. RAW download is preferred for VPS networking; only
# the published checksum and embedded manifest grant installation permission.
RAW_MIRROR_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/38d201e3e84bbe7f30fccdea142bf5fe74f26173/dist/p07/0.1.0-release135/P07-M03-0.1.0-release135.zip"
msg() { printf '%s\n' "$*"; }
deny() {
  local step="${1:-P07_M03_VERIFY_FAILED}"
  case "$step" in
    DOWNLOAD_UNAVAILABLE) msg 'P07-M03 网站与数据：官方更新包下载失败（网络或 GitHub 发布资源不可访问），未开始升级。' >&2 ;;
    HASH_MISMATCH) msg 'P07-M03 网站与数据：下载内容与官方 SHA-256 不匹配，已拒绝，不会使用不可信文件。' >&2 ;;
    ARCHIVE_REJECTED) msg 'P07-M03 网站与数据：压缩包内容或文件清单不符合正式版本，已拒绝安装。' >&2 ;;
    INSTALLER_REJECTED) msg 'P07-M03 网站与数据：内部安装器无效，未开始升级。' >&2 ;;
    APPLY_FAILED) msg 'P07-M03 网站与数据：升级步骤失败，请保留旧版与恢复目录；未操作网站、数据库或 DNS。' >&2 ;;
    *) msg 'P07-M03 网站与数据：预检未通过；未进行升级。' >&2 ;;
  esac
  msg "错误阶段：$step" >&2
  exit 13
}
case "${1:-}" in
  --version) msg "P07-M03 网站与数据 $BUILD"; exit 0 ;;
  --help) msg 'P07-M03 网站与数据：install 在确认后独立安装/升级程序文件；不执行迁移、数据恢复或 DNS 切换。'; exit 0 ;;
  install) [[ "$#" -eq 1 ]] || deny ;;
  *) deny ;;
esac
for tool in curl sha256sum python3 mktemp bash; do command -v "$tool" >/dev/null 2>&1 || deny; done
if [[ "${P07_ALLOW_NONROOT:-0}" != 1 ]]; then
  [[ "$(id -u)" -eq 0 ]] || deny
fi
tmp="$(mktemp -d -t p07-m03-release135.XXXXXXXX)" || deny
chmod 0700 "$tmp"
trap 'rm -rf -- "$tmp"' EXIT
if ! curl --proto '=https' --tlsv1.2 -fsSL --retry 1 --connect-timeout 10 --max-time 90 "$RAW_MIRROR_URL" -o "$tmp/$ZIP_NAME" 2>"$tmp/primary-error"; then
  # Only the official GitHub Release is an alternative transport; both need
  # to match the same pinned SHA256 and the same signed file manifest.
  if ! curl --proto '=https' --tlsv1.2 -fsSL --retry 1 --connect-timeout 10 --max-time 120 \
      "$URL" -o "$tmp/$ZIP_NAME" 2>"$tmp/fallback-error"; then
    deny DOWNLOAD_UNAVAILABLE
  fi
fi
actual_sha="$(sha256sum "$tmp/$ZIP_NAME" | awk '{print $1}')" || deny HASH_MISMATCH
[[ "$actual_sha" == "$ZIP_SHA256" ]] || deny HASH_MISMATCH
python3 -B - "$tmp/$ZIP_NAME" "$tmp/files" "$RUNTIME_BLOB" "$INSTALLER_BLOB" 2>"$tmp/verify-error" <<'PY' || deny ARCHIVE_REJECTED
import hashlib,pathlib,re,stat,sys,zipfile
archive=pathlib.Path(sys.argv[1]); dest=pathlib.Path(sys.argv[2]); manifest_blob=sys.argv[3]; installer_blob=sys.argv[4]
def blob(p):
    d=p.read_bytes()
    return hashlib.sha1(b"blob "+str(len(d)).encode()+b"\0"+d).hexdigest()
with zipfile.ZipFile(archive) as z:
    items=z.infolist()
    if not 50<=len(items)<=240: raise ValueError("member count")
    dest.mkdir(mode=0o700)
    seen=set()
    limit=0
    for f in items:
        path=pathlib.PurePosixPath(f.filename)
        name=f.filename
        if name in seen or not name.isascii() or path.is_absolute() or ".." in path.parts or f.is_dir() or "\\" in name:
            raise ValueError("path")
        if not re.fullmatch(r"(?:dist/p07/0[.]1[.]0/overlay/(?:bin|lib)/[A-Za-z0-9_./-]+|dist/p07/0[.]1[.]0/overlay/(?:BUILD_ID|RUNTIME[.]gitblob)|dist/p07/0[.]1[.]0-rc2/P07_VF_SERVER_OPS_0[.]1[.]0-rc2[.]tar[.]gz|installers/p07-final[.]sh)",name):
            raise ValueError("unexpected asset")
        if stat.S_IFMT(f.external_attr>>16)!=stat.S_IFREG or f.file_size>64*1024*1024:
            raise ValueError("unsafe mode")
        limit+=f.file_size
        if limit>110*1024*1024: raise ValueError("size")
        seen.add(name)
        target=dest.joinpath(*path.parts); target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(z.read(f))
manifest=dest/"dist/p07/0.1.0/overlay/RUNTIME.gitblob"
installer=dest/"installers/p07-final.sh"
if blob(manifest)!=manifest_blob or blob(installer)!=installer_blob:
    raise ValueError("identity")
names=set()
for row in manifest.read_text().splitlines():
    expected,rel=row.split("  ",1)
    if not re.fullmatch(r"(?:bin|lib)/[A-Za-z0-9_./-]+|BUILD_ID",rel) or ".." in pathlib.PurePosixPath(rel).parts or rel in names:
        raise ValueError("manifest")
    names.add(rel)
    if blob(manifest.parent/rel)!=expected: raise ValueError("runtime file")
if len(names)+3!=len(items): raise ValueError("extra asset")
if (manifest.parent/"BUILD_ID").read_text().strip()!="0.1.0-release135": raise ValueError("build")
PY
bash -n "$tmp/files/installers/p07-final.sh" || deny INSTALLER_REJECTED
msg 'P07-M03 网站与数据：正式包已验证，开始仅升级本模块程序。'
P07_PUBLIC_ROOT="file://$tmp/files" P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh" || deny APPLY_FAILED
msg 'P07-M03 网站与数据：已完成本模块升级；未迁移网站、数据库或切换 DNS。'
