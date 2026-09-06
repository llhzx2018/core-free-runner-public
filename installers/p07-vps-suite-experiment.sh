#!/usr/bin/env bash
set -euo pipefail

APP="P07 VPS Acceptance Suite"
VERSION="0.2.0"
CHANNEL="EXPERIMENT"
INSTALL_DIR="${P07_SUITE_DIR:-/opt/p07-vps-suite}"
BIN_DIR="${P07_SUITE_BIN_DIR:-/usr/local/bin}"
BASE="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public"

INSPECT_COMMIT="cdf6378275cb7da288b3b0678c616e0359d58847"
INSPECT_BLOB="93a2dfb95a29d799a176aa4dcaf62308b36fb2d9"
BENCHMARK_COMMIT="35c773fc1a163551f7599203922883a91a6d6b8a"
BENCHMARK_BLOB="e00321a725b8eae7564ae7939d17b7c354719090"
NETCHECK_COMMIT="be59544b43ec29fe3d6f3b4f2d5d3ef0d992ded7"
NETCHECK_BLOB="f6141eb76ff5808d1eacd1d23bd82e2a68c61b7d"

log(){ printf '\n[P07] %s\n' "$*"; }
fail(){ printf '\n[P07] ERROR: %s\n' "$*" >&2; exit 1; }
need_root(){ [[ ${EUID:-$(id -u)} -eq 0 ]] || fail '请使用 root 运行安装器。'; }
need_cmd(){ command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"; }

blob_sha(){
  python3 - "$1" <<'PY'
import hashlib,sys
data=open(sys.argv[1],'rb').read()
print(hashlib.sha1((f'blob {len(data)}\0').encode()+data).hexdigest())
PY
}

fetch_exact(){
  local name="$1" commit="$2" blob="$3" remote="$4" out="$5" got
  log "下载 $name..."
  curl -fL --retry 2 --connect-timeout 8 --max-time 45 "$BASE/$commit/$remote" -o "$out"
  got="$(blob_sha "$out")"
  [[ "$got" == "$blob" ]] || fail "$name 字节校验失败：expected=$blob got=$got"
  chmod 0755 "$out"
  printf '[P07] %-12s VERIFIED  %s\n' "$name" "$blob"
}

self_check(){
  local file="$1" version="$2" name="$3"
  bash -n "$file" || fail "$name bash syntax 检查失败"
  NO_COLOR=1 "$file" --version | grep -F "$version" >/dev/null || fail "$name version 检查失败"
  NO_COLOR=1 "$file" --self-test | grep -F 'SELF_TEST=PASS' >/dev/null || fail "$name self-test 失败"
  printf '[P07] %-12s SELF_TEST PASS\n' "$name"
}

need_root
need_cmd curl
need_cmd python3
need_cmd grep
need_cmd bash

mkdir -p "$INSTALL_DIR/modules" "$BIN_DIR"
TMP="$(mktemp -d -t p07-suite.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

fetch_exact Inspect "$INSPECT_COMMIT" "$INSPECT_BLOB" experiments/p07-inspect.sh "$TMP/p07-inspect.sh"
fetch_exact Benchmark "$BENCHMARK_COMMIT" "$BENCHMARK_BLOB" experiments/p07-benchmark.sh "$TMP/p07-benchmark.sh"
fetch_exact NetCheck "$NETCHECK_COMMIT" "$NETCHECK_BLOB" experiments/p07-netcheck.sh "$TMP/p07-netcheck.sh"

log '安装模块...'
install -m 0755 "$TMP/p07-inspect.sh" "$INSTALL_DIR/modules/p07-inspect.sh"
install -m 0755 "$TMP/p07-benchmark.sh" "$INSTALL_DIR/modules/p07-benchmark.sh"
install -m 0755 "$TMP/p07-netcheck.sh" "$INSTALL_DIR/modules/p07-netcheck.sh"
ln -sfn "$INSTALL_DIR/modules/p07-inspect.sh" "$BIN_DIR/p07-inspect"
ln -sfn "$INSTALL_DIR/modules/p07-benchmark.sh" "$BIN_DIR/p07-benchmark"
ln -sfn "$INSTALL_DIR/modules/p07-netcheck.sh" "$BIN_DIR/p07-netcheck"

cat >"$INSTALL_DIR/p07-vpscheck" <<'EOF'
#!/usr/bin/env bash
set -u
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  R=$'\033[0m'; C=$'\033[38;5;45m'; G=$'\033[38;5;48m'; Y=$'\033[38;5;220m'; M=$'\033[38;5;141m'; D=$'\033[38;5;245m'; B=$'\033[1m'
else R=""; C=""; G=""; Y=""; M=""; D=""; B=""; fi
pause(){ printf '\n%s按 Enter 返回...%s' "$D" "$R"; read -r _ || true; }
while true; do
  [[ -t 1 ]] && clear 2>/dev/null || true
  printf '%s%sP07 · VPS 验机套件%s\n' "$B" "$C" "$R"
  printf '%s\n' '────────────────────────────────────────────────────────────'
  printf '  %s1%s  %-18s %s\n' "$G" "$R" '服务器概览' 'CPU / 内存 / 磁盘 / CloudPanel / IP'
  printf '  %s2%s  %-18s %s\n' "$Y" "$R" '性能测试' '磁盘 / 全球测速 / SOURCE-TARGET 对比'
  printf '  %s3%s  %-18s %s\n' "$M" "$R" '中国访问 / IP' '三网信号 / 风险判断 / 网络诊断'
  printf '\n  %s0 返回%s\n' "$D" "$R"
  printf '%s\n' '────────────────────────────────────────────────────────────'
  printf '请选择 [0-3]：'; read -r c || exit 0
  case "$c" in
    1) p07-inspect; pause;;
    2) p07-benchmark;;
    3) p07-netcheck;;
    0) exit 0;;
    *) sleep 1;;
  esac
done
EOF
chmod 0755 "$INSTALL_DIR/p07-vpscheck"
ln -sfn "$INSTALL_DIR/p07-vpscheck" "$BIN_DIR/p07-vpscheck"

log '安装后自检...'
self_check "$BIN_DIR/p07-inspect" 0.3.0 Inspect
self_check "$BIN_DIR/p07-benchmark" 0.4.0 Benchmark
self_check "$BIN_DIR/p07-netcheck" 0.5.0 NetCheck
bash -n "$BIN_DIR/p07-vpscheck" || fail 'p07-vpscheck syntax 检查失败'

cat >"$INSTALL_DIR/INSTALL_MANIFEST.txt" <<EOF
suite=$APP
suite_version=$VERSION
channel=$CHANNEL
installed_at=$(date -Is 2>/dev/null || date)
inspect_version=0.3.0
inspect_commit=$INSPECT_COMMIT
inspect_blob=$INSPECT_BLOB
benchmark_version=0.4.0
benchmark_commit=$BENCHMARK_COMMIT
benchmark_blob=$BENCHMARK_BLOB
netcheck_version=0.5.0
netcheck_commit=$NETCHECK_COMMIT
netcheck_blob=$NETCHECK_BLOB
suite_dispatcher=p07-vpscheck
vfops_integration=NOT_RUN
EOF
chmod 0644 "$INSTALL_DIR/INSTALL_MANIFEST.txt"

printf '\n============================================================\n'
printf ' P07 VPS Acceptance Suite %s · %s\n' "$VERSION" "$CHANNEL"
printf '============================================================\n'
printf ' Inspect    0.3.0   PASS\n'
printf ' Benchmark  0.4.0   PASS\n'
printf ' NetCheck   0.5.0   PASS\n'
printf '\n以后直接输入：p07-vpscheck\n'
printf '三个模块仍然独立安装，可分别运行 p07-inspect / p07-benchmark / p07-netcheck。\n'
printf '\n不会修改 vfops 总菜单，不会改 DNS，不会自动运行重负载测速。\n'

if [[ -t 0 && -t 1 && "${P07_SUITE_NO_LAUNCH:-0}" != "1" ]]; then
  printf '\n正在进入 P07 VPS 验机套件...\n\n'
  "$BIN_DIR/p07-vpscheck"
fi
