#!/usr/bin/env bash
# P07-M03 网站与数据：RC4 独立维护程序。只升级真实已发行 RC3 或独立首次安装。
# Only this module's runtime path changes; databases, websites, DNS and other modules stay untouched.
set -Eeuo pipefail
MODULE='P07-M03'
BUILD='0.1.0-release147-rc4'
RELEASE='p07-m03-v0.1.0-release147-rc4-maintenance-20261125'
ZIP_NAME='P07-M03-0.1.0-release147-rc4-MAINTENANCE.zip'
ZIP_SHA256='ef6e8731c4b0a7501d2fe55f18f86a74f374d03ad0e7030709b3120a7b13f1e7'
RUNTIME_BLOB='980ef2b84b521f41b1d2ca51fa09ac5c83ecaea9'
INSTALLER_BLOB='33556a8df5c5c0903613ecc42077d9292ca22cfc'
URL="https://github.com/llhzx2018/core-free-runner-public/releases/download/$RELEASE/$ZIP_NAME"
# Fallback resolves the exact public tag/name/size; the same pinned ZIP hash remains mandatory.
RELEASE_API_URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/tags/$RELEASE"
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
# Fail closed if somebody tries to use this installer as the stable updater.
# Trial only occupies its separate owner-trial root and executable.
[[ "${P07_INSTALL_DIR:-}" == "/opt/vf-server-ops-ownertrial147rc3" &&
   "${P07_PREVIOUS_DIR:-}" == "/opt/vf-server-ops-ownertrial147rc3.previous" &&
   "${P07_BIN_LINK:-}" == "/usr/local/bin/vfops-rc147rc3" &&
   "${P07_TOOLBOX_PARENT:-0}" == 1 ]] || {
  printf '%s\n' 'P07-M03 试用安装：仅允许由公共工具箱装入独立试用目录。' >&2
  exit 13
}
case "${1:-}" in
  --version) msg "P07-M03 网站与数据 $BUILD (OWNER_TRIAL)"; exit 0 ;;
  --help) msg 'P07-M03 网站与数据：install 在确认后独立安装/升级程序文件；不执行迁移、数据恢复或 DNS 切换。'; exit 0 ;;
  install) [[ "$#" -eq 1 ]] || deny ;;
  *) deny ;;
esac
for tool in curl sha256sum python3 mktemp bash; do command -v "$tool" >/dev/null 2>&1 || deny; done
if [[ "${P07_ALLOW_NONROOT:-0}" != 1 ]]; then
  [[ "$(id -u)" -eq 0 ]] || deny
fi
tmp="$(mktemp -d -t p07-m03-ownertrial147rc4.XXXXXXXX)" || deny
chmod 0700 "$tmp"
trap 'rm -rf -- "$tmp"' EXIT
if ! curl --proto '=https' --tlsv1.2 -fsSL --retry 1 --connect-timeout 10 --max-time 90 "$URL" -o "$tmp/$ZIP_NAME" 2>"$tmp/primary-error"; then
  curl --proto '=https' --tlsv1.2 -fsSL --connect-timeout 10 --max-time 30 "$RELEASE_API_URL" -o "$tmp/release.json" 2>"$tmp/fallback-error" || deny DOWNLOAD_UNAVAILABLE
  asset_id="$(python3 -B - "$tmp/release.json" "$RELEASE" "$ZIP_NAME" "$URL" <<'PY'
import json,pathlib,re,sys
try:
    p=pathlib.Path(sys.argv[1])
    if p.stat().st_size>1024*1024: raise ValueError()
    data=json.loads(p.read_bytes())
    if data.get("tag_name")!=sys.argv[2] or data.get("draft") is not False: raise ValueError()
    assets=[a for a in data["assets"] if a.get("name")==sys.argv[3] and a.get("browser_download_url")==sys.argv[4] and a.get("size")==719273 and a.get("state")=="uploaded"]
    if len(assets)!=1: raise ValueError()
    value=assets[0]["id"]
    if type(value) is not int or not re.fullmatch(r"[1-9][0-9]{0,18}",str(value)): raise ValueError()
    print(value)
except (OSError,ValueError,KeyError,TypeError):
    sys.exit(13)
PY
)" || deny DOWNLOAD_UNAVAILABLE
  curl --proto '=https' --tlsv1.2 -fsSL --retry 1 --connect-timeout 10 --max-time 120 \
    -H 'Accept: application/octet-stream' "https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/$asset_id" -o "$tmp/$ZIP_NAME" 2>"$tmp/fallback-error" || deny DOWNLOAD_UNAVAILABLE
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
        if not re.fullmatch(r"(?:dist/p07/0[.]1[.]0/overlay/(?:bin|lib|components)/[A-Za-z0-9_./-]+|dist/p07/0[.]1[.]0/overlay/(?:BUILD_ID|RUNTIME[.]gitblob)|dist/p07/0[.]1[.]0-rc2/P07_VF_SERVER_OPS_0[.]1[.]0-rc2[.]tar[.]gz|installers/p07-final[.]sh)",name):
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
    if not re.fullmatch(r"(?:bin|lib|components)/[A-Za-z0-9_./-]+|BUILD_ID",rel) or ".." in pathlib.PurePosixPath(rel).parts or rel in names:
        raise ValueError("manifest")
    names.add(rel)
    if blob(manifest.parent/rel)!=expected: raise ValueError("runtime file")
if len(names)+3!=len(items): raise ValueError("extra asset")
if (manifest.parent/"BUILD_ID").read_text().strip()!="0.1.0-release147-rc4": raise ValueError("build")
PY
bash -n "$tmp/files/installers/p07-final.sh" || deny INSTALLER_REJECTED
# Preliminary identity never executes or imports installed RC3.
# The signed inner installer owns full exact RC3 provenance and rollback.
# No wrapper-side rename/rotation/cleanup of runtime backups.
root="$P07_INSTALL_DIR"
previous="$P07_PREVIOUS_DIR"
bin="$P07_BIN_LINK"
lock="$root.upgrade.lock"
for tool in flock readlink sha1sum; do command -v "$tool" >/dev/null 2>&1 || deny APPLY_FAILED; done
source_pinned() {
  case "${P07_M03_EXPECTED_SOURCE:-}" in
    ABSENT)
      [[ ! -e "$root" && ! -L "$root" && ! -e "$bin" && ! -L "$bin" &&
         ! -e "$previous" && ! -L "$previous" && ! -e "$root.new" && ! -L "$root.new" ]] ;;
    RC3)
      [[ -d "$root" && ! -L "$root" && -d "$root/bin" && ! -L "$root/bin" &&
         -d "$root/lib" && ! -L "$root/lib" && -d "$root/components" && ! -L "$root/components" &&
         -f "$root/BUILD_ID" && ! -L "$root/BUILD_ID" &&
         -f "$root/.runtime-manifest.gitblob" && ! -L "$root/.runtime-manifest.gitblob" &&
         -L "$bin" && "$(readlink "$bin")" == "$root/bin/vfops-user" &&
         "$(cat "$root/BUILD_ID")" == "0.1.0-release147-rc3" ]] || return 1
      local manifest="$root/.runtime-manifest.gitblob" size hash
      size="$(wc -c < "$manifest")" || return 1
      [[ "$size" =~ ^[0-9]+$ ]] && ((size>0 && size<=1048576)) || return 1
      hash="$( { printf 'blob %s\0' "$size"; cat "$manifest"; } | sha1sum | awk '{print $1}')" || return 1
      [[ "$hash" == "06c79cf8595de625cc84d6a849d9e88fe01c4520" ]] ;;
    *) return 1 ;;
  esac
}
[[ -d "$(dirname "$root")" && ! -L "$(dirname "$root")" &&
   ! -L "$lock" && ( ! -e "$lock" || -f "$lock" ) ]] || deny APPLY_FAILED
source_pinned || { msg 'P07-M03 网站与数据：确认时的原程序身份已经改变，未升级。' >&2; deny APPLY_FAILED; }
exec {lock_fd}>>"$lock" || deny APPLY_FAILED
flock -x "$lock_fd" || deny APPLY_FAILED
source_pinned || { msg 'P07-M03 网站与数据：原程序身份已变化，恢复目录原样保留。' >&2; deny APPLY_FAILED; }
msg 'P07-M03 网站与数据：维护包已校验，正在独立安装或升级程序。'
P07_PUBLIC_ROOT="file://$tmp/files" P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh" || deny APPLY_FAILED
[[ -f "$root/BUILD_ID" && ! -L "$root/BUILD_ID" && "$(cat "$root/BUILD_ID")" == "$BUILD" &&
   -L "$bin" && "$(readlink "$bin")" == "$root/bin/vfops-user" ]] || deny APPLY_FAILED
msg 'P07-M03 网站与数据：独立维护程序安装或升级成功，未迁移网站、恢复数据库或修改 DNS。'
