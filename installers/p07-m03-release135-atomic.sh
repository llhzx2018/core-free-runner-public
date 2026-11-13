#!/usr/bin/env bash
# P07-M03 网站与数据: immutable Release ZIP -> existing guarded atomic installer.
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
msg() { printf '%s\n' "$*"; }
deny() { msg 'P07-M03 网站与数据：正式升级包验证未通过；原模块和其它模块未执行安装。' >&2; exit 13; }
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
if ! curl --proto '=https' --tlsv1.2 -fsSL --retry 2 --connect-timeout 15 --max-time 180 "$URL" -o "$tmp/$ZIP_NAME"; then deny; fi
printf '%s  %s\n' "$ZIP_SHA256" "$tmp/$ZIP_NAME" | sha256sum -c - >/dev/null || deny
python3 -B - "$tmp/$ZIP_NAME" "$tmp/files" "$RUNTIME_BLOB" "$INSTALLER_BLOB" <<'PY' || deny
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
bash -n "$tmp/files/installers/p07-final.sh" || deny
msg 'P07-M03 网站与数据：正式包已验证，开始仅升级本模块程序。'
P07_PUBLIC_ROOT="file://$tmp/files" P07_NO_EXEC=1 bash "$tmp/files/installers/p07-final.sh" || deny
msg 'P07-M03 网站与数据：已完成本模块升级；未迁移网站、数据库或切换 DNS。'
