#!/usr/bin/env bash
# P07-M03 网站与数据 / D04 服务器迁移：Owner试用 147rc2。SHA256+Git blob 双重校验，仅试用程序隔离安装。
# Only this module's runtime path changes; databases, websites, DNS and other modules stay untouched.
set -Eeuo pipefail
MODULE='P07-M03'
BUILD='0.1.0-release147-rc2'
RELEASE='p07-m03-v0.1.0-release147-rc2-ownertrial-20261123'
ZIP_NAME='P07-M03-0.1.0-release147-rc2-OWNER-TRIAL.zip'
ZIP_SHA256='09406d27e47ad2f1946cc129e9492fc009b30e278b0ae65df56775a145244c0d'
RUNTIME_BLOB='667030be8a7e4dd1b557690c66858e8b5cbb42ba'
INSTALLER_BLOB='3d3322d8266033b9113a117a2b865d33719ed89a'
URL="https://github.com/llhzx2018/core-free-runner-public/releases/download/$RELEASE/$ZIP_NAME"
# Same immutable official Release asset via primary download URL and public
# GitHub API fallback. Neither is trusted until SHA256 and embedded Git blobs pass.
ASSET_API_URL="https://api.github.com/repos/llhzx2018/core-free-runner-public/releases/assets/781226439"
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
[[ "${P07_INSTALL_DIR:-}" == "/opt/vf-server-ops-ownertrial147rc2" &&
   "${P07_PREVIOUS_DIR:-}" == "/opt/vf-server-ops-ownertrial147rc2.previous" &&
   "${P07_BIN_LINK:-}" == "/usr/local/bin/vfops-rc147rc2" &&
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
tmp="$(mktemp -d -t p07-m03-ownertrial147rc2.XXXXXXXX)" || deny
chmod 0700 "$tmp"
trap 'rm -rf -- "$tmp"' EXIT
if ! curl --proto '=https' --tlsv1.2 -fsSL --retry 1 --connect-timeout 10 --max-time 90 "$URL" -o "$tmp/$ZIP_NAME" 2>"$tmp/primary-error"; then
  # Public GitHub API asset endpoint; hash-verify even if API returns JSON.
  if ! curl --proto '=https' --tlsv1.2 -fsSL --retry 1 --connect-timeout 10 --max-time 120 \
      -H 'Accept: application/octet-stream' "$ASSET_API_URL" -o "$tmp/$ZIP_NAME" 2>"$tmp/fallback-error"; then
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
if (manifest.parent/"BUILD_ID").read_text().strip()!="0.1.0-release147-rc2": raise ValueError("build")
PY
bash -n "$tmp/files/installers/p07-final.sh" || deny INSTALLER_REJECTED
# Owner safety recovery: release139->140 legitimately retains an earlier
# .previous snapshot. The signed release141 internal installer refuses to
# overwrite that existing path. Preserve it with verified, non-overwriting
# versioned rotation; then the signed installer can retain current140 as
# .previous. Do not erase, overwrite, assume ownership, or process unknown
# recoveries. All paths are module runtime paths, not website/data snapshots.
m03_root="${P07_INSTALL_DIR:-/opt/vf-server-ops-ownertrial147rc2}"
m03_previous="${P07_PREVIOUS_DIR:-/opt/vf-server-ops-ownertrial147rc2.previous}"
m03_bin="${P07_BIN_LINK:-/usr/local/bin/vfops-rc147rc2}"
m03_lock="$m03_root.upgrade.lock"
for tool in flock mv readlink; do command -v "$tool" >/dev/null 2>&1 || deny APPLY_FAILED; done
[[ -d "$(dirname "$m03_root")" && ! -L "$(dirname "$m03_root")" &&
   ! -L "$m03_lock" ]] || deny APPLY_FAILED
# Serialize overlapping invocations before examining or moving any backup.
exec {m03_lock_fd}>>"$m03_lock" || deny APPLY_FAILED
flock -x "$m03_lock_fd" || deny APPLY_FAILED

verified_m03_build() {
  python3 -B - "$1" <<'PY_CHECK'
import hashlib, pathlib, re, sys
root=pathlib.Path(sys.argv[1])
trusted={
    "0.1.0-release115":"4acbaca22aac0da681b34376e2cc86d876593181",
    "0.1.0-release135":"f57e114e0ef23f73a1ec12ba864d8f2e67a5bd30",
    "0.1.0-release136":"59153685ef834114e01e0330c78ae174a042c1fa",
    "0.1.0-release137":"fc94d7c573a0437517726de22c4ac6ff33e582e7",
    "0.1.0-release138":"2c6ccd51b7e73d3d9db1ec6d37beaa6ce1cdff73",
    "0.1.0-release139":"efdfff0b4348b334bbbc2da26d40280338fc7868",
    "0.1.0-release140":"239bd543e4f64449ca498c1d67ccb7471abbee66",
    "0.1.0-release141":"6a3a949064ffb8fe1df56e7bc555173b5ca9cf3b",
    "0.1.0-release142":"cc3d90839bf71ea9139f5fc0d1c6cb12403b58e0",
    "0.1.0-release144":"5dd59de44fa024add3e6317b6dc8617fb92df91f",
    "0.1.0-release145":"db2eb38ef136af4a7d140a3753ff4592b9b64c9f",
    "0.1.0-release146":"78caa4b85edc5441039483117e3f9660cf6e3af6",
    "0.1.0-release147-rc2":"667030be8a7e4dd1b557690c66858e8b5cbb42ba",
}
def digest(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
try:
    if not root.is_dir() or root.is_symlink(): raise ValueError()
    manifest=root/".runtime-manifest.gitblob"
    marker=root/"BUILD_ID"
    if any(not p.is_file() or p.is_symlink() for p in (manifest,marker)): raise ValueError()
    build=marker.read_text(encoding="utf-8").strip()
    if build not in trusted or digest(manifest.read_bytes()) != trusted[build]: raise ValueError()
    rows=manifest.read_text(encoding="utf-8").splitlines()
    if not 50 <= len(rows) <= 240: raise ValueError()
    seen=set()
    for row in rows:
        match=re.fullmatch(r"([0-9a-f]{40})  ((?:bin|lib|components)/[A-Za-z0-9_./-]+|BUILD_ID)",row)
        if match is None: raise ValueError()
        expected,rel=match.groups()
        path=pathlib.PurePosixPath(rel)
        if ".." in path.parts or rel in seen: raise ValueError()
        seen.add(rel)
        member=root.joinpath(*path.parts)
        if not member.is_file() or member.is_symlink() or digest(member.read_bytes())!=expected:
            raise ValueError()
    if "BUILD_ID" not in seen or "bin/vfops-user" not in seen: raise ValueError()
    print(build)
except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
    sys.exit(13)
PY_CHECK
}

m03_rotation=0
m03_old_current=""
m03_old_previous=""
m03_archive=""
if [[ -e "$m03_previous" || -L "$m03_previous" ]]; then
  [[ ! -e "$m03_root.new" && ! -L "$m03_root.new" ]] || {
    msg 'P07-M03 网站与数据：临时升级目录未完成恢复，拒绝自动移动旧恢复点。' >&2
    deny APPLY_FAILED
  }
  m03_old_current="$(verified_m03_build "$m03_root")" || {
    msg 'P07-M03 网站与数据：现有程序身份无法核实，恢复目录原样保留。' >&2
    deny APPLY_FAILED
  }
  if [[ "$m03_old_current" != "$BUILD" ]]; then
    m03_old_previous="$(verified_m03_build "$m03_previous")" || {
      msg 'P07-M03 网站与数据：旧恢复目录不属于可识别的完整正式版本，原样保留。' >&2
      deny APPLY_FAILED
    }
    [[ -L "$m03_bin" && "$(readlink "$m03_bin")" == "$m03_root/bin/vfops-user" ]] || {
      msg 'P07-M03 网站与数据：程序入口不是已验证的目标，拒绝调整恢复点。' >&2
      deny APPLY_FAILED
    }
    m03_archive="$m03_previous.preserved-$m03_old_previous"
    [[ ! -e "$m03_archive" && ! -L "$m03_archive" ]] || {
      msg 'P07-M03 网站与数据：同版本恢复档案已经存在，拒绝覆盖；请保留现场。' >&2
      deny APPLY_FAILED
    }
    if ! mv -nT -- "$m03_previous" "$m03_archive"; then deny APPLY_FAILED; fi
    [[ ! -e "$m03_previous" && ! -L "$m03_previous" &&
       -d "$m03_archive" && ! -L "$m03_archive" ]] || deny APPLY_FAILED
    m03_rotation=1
    msg "P07-M03 网站与数据：已无损保留历史恢复版本 $m03_old_previous；当前版 $m03_old_current 将作为升级回滚点。"
  fi
fi

msg 'P07-M03 网站与数据：人工试用包已验证，仅安装隔离试用程序；迁移未通过真机验收。'
if ! P07_PUBLIC_ROOT="file://$tmp/files" P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh"; then
  # An independent installer error normally restores the active old runtime.
  # Rehydrate the original .previous path only if the current old runtime
  # was fully restored and no other process/path owns that recovery slot.
  if (( m03_rotation == 1 )) &&
     [[ ! -e "$m03_previous" && ! -L "$m03_previous" ]] &&
     [[ "$(verified_m03_build "$m03_root" 2>/dev/null || true)" == "$m03_old_current" ]] &&
     [[ "$(verified_m03_build "$m03_archive" 2>/dev/null || true)" == "$m03_old_previous" ]]; then
    mv -nT -- "$m03_archive" "$m03_previous" || true
    if [[ -d "$m03_previous" && ! -e "$m03_archive" ]]; then
      msg 'P07-M03 网站与数据：升级失败，已保留现有程序并恢复原历史恢复目录。'
    fi
  fi
  deny APPLY_FAILED
fi
if (( m03_rotation == 1 )); then
  [[ "$(verified_m03_build "$m03_root" 2>/dev/null || true)" == "$BUILD" &&
     "$(verified_m03_build "$m03_previous" 2>/dev/null || true)" == "$m03_old_current" &&
     "$(verified_m03_build "$m03_archive" 2>/dev/null || true)" == "$m03_old_previous" ]] || {
    msg 'P07-M03 网站与数据：升级后恢复点核验未通过，全部恢复目录保留待安全处理。' >&2
    deny APPLY_FAILED
  }
fi
msg 'P07-M03 网站与数据：隔离人工试用版安装成功；原正式版未修改，尚未执行迁移或 DNS 切换。'
