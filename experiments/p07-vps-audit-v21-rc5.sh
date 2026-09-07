#!/usr/bin/env bash
set -uo pipefail

APP="P07 VPS 一键验机 2.1"
VERSION="2.1.0-rc5-zh"

BASE_VERSION="2.0.0-rc4-zh"
BASE_URL="https://raw.githubusercontent.com/llhzx2018/core-free-runner-public/1197372f0b32b7cc9a8b35736c30563cb36633c9/experiments/p07-vps-audit-v20-rc4.sh"
BASE_SHA256="54325e92bdf78a90c74b5fed73be9d0633b402659fdfa2848dc751ff23efaecd"

YABS_COMMIT="f8c6a48cd6ff85b54c5cd2504f0807462dc58938"
FIO_X64_SHA256="b511bda3b26b6d840698f543d63e956d7466b8512c10ff0ada8292d556c33fb1"
FIO_AARCH64_SHA256="e2942a26d4b249076486677c9c12cd7f1a572854a5e136597d1391e8ad75ffb0"
FIO_TEST_MIB="${P07_FIO_TEST_MIB:-256}"
FIO_TIMEOUT_SEC="${P07_FIO_TIMEOUT_SEC:-60}"
BENCH_DIR="${P07_BENCH_DIR:-/var/tmp}"

case "${1:-}" in
  --version|-V) printf '%s %s\n' "$APP" "$VERSION"; exit 0 ;;
  --help|-h)
    cat <<'EOF'
P07 VPS 一键验机 2.1

一条命令自动完成：
- 系统 / CPU / 内存 / 隐藏资源限额
- 顺序磁盘、4K/fsync、4K/64K/512K/1M 混合随机读写
- 全球网络、东南亚、中国大陆区域参考
- IP / DNS / HTTPS 基础健康
- 综合评级与业务适配
- TXT / JSON / Markdown 本地报告

不会自动 apt/yum 安装软件，不会自动上传报告到第三方。
EOF
    exit 0 ;;
  "") ;;
  *) printf '未知参数：%s\n' "$1" >&2; exit 2 ;;
esac

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  RESET=$'\033[0m'; BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; CYAN=$'\033[36m'; GRAY=$'\033[90m'
else
  RESET=""; BOLD=""; RED=""; GREEN=""; YELLOW=""; CYAN=""; GRAY=""
fi

rule(){ printf '%s\n' '----------------------------------------------------------------------'; }
sha256_file(){
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$f" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$f" | awk '{print $1}'
  else return 127
  fi
}
fetch(){
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then curl -fsSL --retry 2 --connect-timeout 10 --max-time 90 "$url" -o "$out"
  elif command -v wget >/dev/null 2>&1; then wget -q --https-only --timeout=90 --tries=2 -O "$out" "$url"
  else return 127
  fi
}
strip_terminal_codes(){
  sed -E $'s/\x1B\\[[0-9;?]*[ -/]*[@-~]//g; s/\r$//'
}

TMP="$(mktemp -d -t p07-audit-rc5.XXXXXX 2>/dev/null || printf '/tmp/p07-audit-rc5.%s' "$$")"
mkdir -p "$TMP" 2>/dev/null || exit 3
cleanup(){ rm -rf "$TMP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if [[ -n "${P07_REPORT_DIR:-}" ]]; then
  REPORT_DIR="$P07_REPORT_DIR"
elif [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  REPORT_DIR="/var/lib/p07-bench/reports"
else
  REPORT_DIR="${XDG_STATE_HOME:-${HOME:-/tmp}/.local/state}/p07-bench/reports"
fi
mkdir -p "$REPORT_DIR" 2>/dev/null || REPORT_DIR="/tmp/p07-bench-reports"
mkdir -p "$REPORT_DIR" 2>/dev/null || true
START_EPOCH="$(date +%s)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BASE_OUTPUT="$TMP/base-output.txt"
BASE_PLAIN="$TMP/base-plain.txt"
: >"$BASE_OUTPUT"
: >"$BASE_PLAIN"
FIO_TSV="$TMP/fio.tsv"
: >"$FIO_TSV"
FIO_VERDICT="未执行"
FIO_SMALLFILE="未知"
FIO_LARGEBLOCK="未知"
BASE_GRADE="未知"
BASE_RECOMMEND="未知"
BASE_SCORE="未知"
FINAL_RECOMMEND="未知"
MARKDOWN_REPORT=""

normalize_base_output(){
  sed \
    -e 's/P07 VPS 一键验机 2\.0/P07 VPS 一键验机 2.1/g' \
    -e 's/2\.0\.0-rc3-zh/2.1.0-rc5-zh/g' \
    -e 's/ 最终验机结论/ 基础综合结论/g' \
    -e 's/ 总耗时             :/ 基础验机耗时       :/g' \
    -e 's/ 完成时间           :/ 基础验机完成       :/g'
}

run_base(){
  [[ "${P07_RC5_SKIP_BASE:-0}" == 1 ]] && return 0
  local base="$TMP/base-rc4.sh" got version rc
  if ! fetch "$BASE_URL" "$base"; then printf '%s基础验机模块下载失败。%s\n' "$RED" "$RESET" >&2; return 4; fi
  got="$(sha256_file "$base" 2>/dev/null || true)"
  if [[ "$got" != "$BASE_SHA256" ]]; then printf '%s基础验机模块完整性校验失败，已停止。%s\n' "$RED" "$RESET" >&2; return 5; fi
  version="$(NO_COLOR=1 bash "$base" --version 2>/dev/null | awk '{print $NF}' || true)"
  if [[ "$version" != "$BASE_VERSION" ]]; then printf '%s基础验机模块版本不匹配，已停止。%s\n' "$RED" "$RESET" >&2; return 6; fi

  set +e
  if command -v script >/dev/null 2>&1 && [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    script -qec "bash '$base'" /dev/null | normalize_base_output | tee "$BASE_OUTPUT"
    rc=${PIPESTATUS[0]}
  else
    bash "$base" 2>&1 | normalize_base_output | tee "$BASE_OUTPUT"
    rc=${PIPESTATUS[0]}
  fi
  set -e 2>/dev/null || true
  strip_terminal_codes <"$BASE_OUTPUT" >"$BASE_PLAIN"
  return "$rc"
}

fio_arch(){
  case "$(uname -m 2>/dev/null || true)" in
    x86_64|amd64) printf 'x64|%s' "$FIO_X64_SHA256" ;;
    aarch64|arm64|armv8|armv8l) printf 'aarch64|%s' "$FIO_AARCH64_SHA256" ;;
    *) return 1 ;;
  esac
}
prepare_fio(){
  if command -v fio >/dev/null 2>&1; then FIO_BIN="$(command -v fio)"; FIO_SOURCE="系统现有 fio"; return 0; fi
  command -v python3 >/dev/null 2>&1 || return 1
  local pair arch sha url got out
  pair="$(fio_arch 2>/dev/null || true)"; [[ -n "$pair" ]] || return 1
  IFS='|' read -r arch sha <<<"$pair"
  out="$TMP/fio"
  url="https://raw.githubusercontent.com/masonr/yet-another-bench-script/${YABS_COMMIT}/bin/fio/fio_${arch}"
  fetch "$url" "$out" || return 1
  got="$(sha256_file "$out" 2>/dev/null || true)"
  [[ "$got" == "$sha" ]] || { printf '%sfio 组件完整性校验失败，增强磁盘测试已跳过。%s\n' "$RED" "$RESET"; return 1; }
  chmod 700 "$out"
  "$out" --version >/dev/null 2>&1 || return 1
  FIO_BIN="$out"; FIO_SOURCE="校验版 fio 3.39（临时）"
}

fio_preflight(){
  [[ "$FIO_TEST_MIB" =~ ^[0-9]+$ ]] || return 1
  (( FIO_TEST_MIB >= 128 && FIO_TEST_MIB <= 512 )) || return 1
  [[ "$FIO_TIMEOUT_SEC" =~ ^[0-9]+$ ]] || return 1
  (( FIO_TIMEOUT_SEC >= 20 && FIO_TIMEOUT_SEC <= 180 )) || return 1
  [[ -d "$BENCH_DIR" && -w "$BENCH_DIR" ]] || return 1
  local fs free
  fs="$(df -PT "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $2}')"
  [[ "$fs" != tmpfs && "$fs" != devtmpfs ]] || return 1
  free="$(df -Pm "$BENCH_DIR" 2>/dev/null | awk 'NR==2{print $4}')"
  [[ "$free" =~ ^[0-9]+$ ]] && (( free >= FIO_TEST_MIB + 256 ))
}

run_fio_row(){
  local bs="$1" file="$BENCH_DIR/.p07-fio-$$.bin" json="$TMP/fio-${bs}.json" result rc
  rm -f "$file" "$json"
  set +e
  if command -v timeout >/dev/null 2>&1; then
    timeout "${FIO_TIMEOUT_SEC}s" "$FIO_BIN" --name="p07-${bs}" --filename="$file" --size="${FIO_TEST_MIB}M" \
      --rw=randrw --rwmixread=50 --bs="$bs" --ioengine=libaio --direct=1 --iodepth=32 \
      --numjobs=1 --group_reporting=1 --randrepeat=1 --output-format=json --output="$json" >/dev/null 2>&1
    rc=$?
  else
    "$FIO_BIN" --name="p07-${bs}" --filename="$file" --size="${FIO_TEST_MIB}M" \
      --rw=randrw --rwmixread=50 --bs="$bs" --ioengine=libaio --direct=1 --iodepth=32 \
      --numjobs=1 --group_reporting=1 --randrepeat=1 --output-format=json --output="$json" >/dev/null 2>&1
    rc=$?
  fi
  set -e 2>/dev/null || true
  rm -f "$file"
  (( rc == 0 )) || return 1
  result="$(python3 - "$json" <<'PY' 2>/dev/null || true
import json,sys
try:
    j=json.load(open(sys.argv[1],encoding='utf-8'))['jobs'][0]
    r,w=j['read'],j['write']
    print(f"{r['bw_bytes']/1048576:.2f}|{r['iops']:.1f}|{w['bw_bytes']/1048576:.2f}|{w['iops']:.1f}")
except Exception:
    pass
PY
)"
  [[ -n "$result" ]] || return 1
  printf '%s\t%s\n' "$bs" "$result" >>"$FIO_TSV"
}

assess_fio(){
  local four="" one="" read_iops write_iops read_mb write_mb min_iops min_mb
  four="$(awk -F '[\t|]' '$1=="4k"{print $2"|"$3"|"$4"|"$5}' "$FIO_TSV")"
  one="$(awk -F '[\t|]' '$1=="1m"{print $2"|"$3"|"$4"|"$5}' "$FIO_TSV")"
  if [[ -n "$four" ]]; then
    IFS='|' read -r _ read_iops _ write_iops <<<"$four"
    min_iops="$(awk -v a="$read_iops" -v b="$write_iops" 'BEGIN{print (a<b?a:b)}')"
    if awk -v n="$min_iops" 'BEGIN{exit !(n>=5000)}'; then FIO_SMALLFILE="良好"
    elif awk -v n="$min_iops" 'BEGIN{exit !(n>=1500)}'; then FIO_SMALLFILE="可用"
    else FIO_SMALLFILE="偏弱"; fi
  fi
  if [[ -n "$one" ]]; then
    IFS='|' read -r read_mb _ write_mb _ <<<"$one"
    min_mb="$(awk -v a="$read_mb" -v b="$write_mb" 'BEGIN{print (a<b?a:b)}')"
    if awk -v n="$min_mb" 'BEGIN{exit !(n>=300)}'; then FIO_LARGEBLOCK="良好"
    elif awk -v n="$min_mb" 'BEGIN{exit !(n>=100)}'; then FIO_LARGEBLOCK="可用"
    else FIO_LARGEBLOCK="偏弱"; fi
  fi
  if [[ "$FIO_SMALLFILE" == 良好 && "$FIO_LARGEBLOCK" == 良好 ]]; then FIO_VERDICT="良好"
  elif [[ "$FIO_SMALLFILE" == 偏弱 || "$FIO_LARGEBLOCK" == 偏弱 ]]; then FIO_VERDICT="需观察"
  elif [[ "$FIO_SMALLFILE" != 未知 || "$FIO_LARGEBLOCK" != 未知 ]]; then FIO_VERDICT="可用"
  else FIO_VERDICT="证据不足"; fi
}

print_fio(){
  rule
  printf '%s%s 增强磁盘混合读写%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' %s4 档 50/50 随机读写，用于识别数据库/小文件与大块混合负载，不替代现有 fsync/P95。%s\n' "$GRAY" "$RESET"
  if ! fio_preflight; then printf ' %s当前磁盘目录/空间不满足安全条件，已跳过增强测试。%s\n' "$YELLOW" "$RESET"; return 0; fi
  if ! prepare_fio; then printf ' %sfio 不可用，已保留现有磁盘验机结果。%s\n' "$YELLOW" "$RESET"; return 0; fi
  printf ' 测试引擎           : %s\n' "$FIO_SOURCE"
  printf ' 测试文件           : %s MiB（有界测试，单档最长 %s 秒）\n' "$FIO_TEST_MIB" "$FIO_TIMEOUT_SEC"
  printf ' %-8s %-15s %-13s %-15s %-13s\n' '块大小' '随机读取' '读 IOPS' '随机写入' '写 IOPS'
  local bs row rb ri wb wi pass=0
  for bs in 4k 64k 512k 1m; do
    if run_fio_row "$bs"; then
      row="$(tail -n1 "$FIO_TSV")"; IFS=$'\t|' read -r _ rb ri wb wi <<<"$row"
      printf ' %-8s %-15s %-13s %-15s %-13s\n' "$bs" "${rb} MB/s" "$ri" "${wb} MB/s" "$wi"
      pass=$((pass+1))
    else
      printf ' %-8s %-15s %-13s %-15s %-13s\n' "$bs" '测试失败' '-' '测试失败' '-'
    fi
  done
  assess_fio
  printf ' 有效档位           : %s / 4\n' "$pass"
  printf ' 小文件/数据库      : %s\n' "$FIO_SMALLFILE"
  printf ' 大块混合吞吐       : %s\n' "$FIO_LARGEBLOCK"
  case "$FIO_VERDICT" in
    良好) printf ' 增强磁盘判断       : %s%s%s\n' "$GREEN" "$FIO_VERDICT" "$RESET" ;;
    需观察) printf ' 增强磁盘判断       : %s%s%s\n' "$YELLOW" "$FIO_VERDICT" "$RESET" ;;
    *) printf ' 增强磁盘判断       : %s\n' "$FIO_VERDICT" ;;
  esac
}

extract_base_summary(){
  [[ -s "$BASE_PLAIN" ]] || return 0
  BASE_GRADE="$(awk -F: '$1 ~ /^[[:space:]]*综合评级[[:space:]]*$/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$BASE_PLAIN")"
  BASE_RECOMMEND="$(awk -F: '$1 ~ /^[[:space:]]*建议[[:space:]]*$/{sub(/^[^:]*:/, ""); gsub(/^[[:space:]]+|[[:space:]]+$/, ""); print; exit}' "$BASE_PLAIN")"
  BASE_SCORE="$(awk -F: '$1 ~ /^[[:space:]]*综合得分[[:space:]]*$/{gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2); print $2; exit}' "$BASE_PLAIN")"
  [[ -n "$BASE_GRADE" ]] || BASE_GRADE="未知"
  [[ -n "$BASE_RECOMMEND" ]] || BASE_RECOMMEND="未知"
  [[ -n "$BASE_SCORE" ]] || BASE_SCORE="未知"
}

build_final_recommendation(){
  if [[ "$BASE_RECOMMEND" == 未知 ]]; then
    FINAL_RECOMMEND="基础验机未执行；当前仅验证增强磁盘"
    return
  fi
  FINAL_RECOMMEND="$BASE_RECOMMEND"
  case "$FIO_VERDICT" in
    需观察)
      FINAL_RECOMMEND="${FINAL_RECOMMEND}；数据库/混合磁盘负载需观察"
      ;;
    证据不足|未执行)
      FINAL_RECOMMEND="${FINAL_RECOMMEND}；增强磁盘证据不足"
      ;;
  esac
}

write_markdown(){
  local md="$REPORT_DIR/p07-vps-audit_${STAMP}.md"
  {
    printf '# P07 VPS 一键验机报告\n\n'
    printf -- '- 版本：`%s`\n' "$VERSION"
    printf -- '- 时间：`%s`\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
    printf -- '- 说明：报告仅保存到本机，不自动上传第三方。\n\n'
    if [[ -s "$BASE_PLAIN" ]]; then
      printf '## 完整基础与网络验机输出\n\n```text\n'
      cat "$BASE_PLAIN"
      printf '\n```\n\n'
    fi
    printf '## 增强磁盘混合读写\n\n'
    printf '| 块大小 | 随机读取 MB/s | 读 IOPS | 随机写入 MB/s | 写 IOPS |\n'
    printf '|---|---:|---:|---:|---:|\n'
    while IFS=$'\t|' read -r bs rb ri wb wi; do
      [[ -n "$bs" ]] && printf '| %s | %s | %s | %s | %s |\n' "$bs" "$rb" "$ri" "$wb" "$wi"
    done <"$FIO_TSV"
    printf '\n### 增强磁盘判断\n\n'
    printf -- '- 小文件/数据库：**%s**\n' "$FIO_SMALLFILE"
    printf -- '- 大块混合吞吐：**%s**\n' "$FIO_LARGEBLOCK"
    printf -- '- 综合：**%s**\n' "$FIO_VERDICT"
    printf '\n## 最终验机结论\n\n'
    printf -- '- 综合评级：**%s**\n' "$BASE_GRADE"
    printf -- '- 基础得分：**%s**\n' "$BASE_SCORE"
    printf -- '- 增强磁盘：**%s**\n' "$FIO_VERDICT"
    printf -- '- 建议：**%s**\n' "$FINAL_RECOMMEND"
    printf '\n## 证据边界\n\n'
    printf -- '- 中国大陆区域结果反映本次 VPS 与真实大陆节点之间的有界跨境线路参考，不等同于中国普通用户到 VPS 的直接入站探测。\n'
  } >"$md"
  MARKDOWN_REPORT="$md"
  printf ' Markdown 报告       : %s%s%s\n' "$GREEN" "$md" "$RESET"
}

print_final(){
  local end_epoch total_sec total_min total_rem
  end_epoch="$(date +%s)"
  total_sec=$((end_epoch-START_EPOCH))
  total_min=$((total_sec/60))
  total_rem=$((total_sec%60))
  rule
  printf '%s%s 最终验机结论%s\n' "$BOLD" "$CYAN" "$RESET"
  printf ' 综合评级           : %s\n' "$BASE_GRADE"
  printf ' 基础得分           : %s\n' "$BASE_SCORE"
  printf ' 增强磁盘           : %s\n' "$FIO_VERDICT"
  printf ' 建议               : %s\n' "$FINAL_RECOMMEND"
  printf ' 完整验机总耗时     : %s 分 %s 秒\n' "$total_min" "$total_rem"
  printf ' 最终完成时间       : %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')"
  printf ' 本地报告           : TXT / JSON / Markdown\n'
  [[ -n "$MARKDOWN_REPORT" ]] && printf ' Markdown            : %s\n' "$MARKDOWN_REPORT"
}

set +e
run_base
base_rc=$?
set -e 2>/dev/null || true
if (( base_rc != 0 )); then
  printf '%s基础验机未正常完成，增强测试不继续。%s\n' "$RED" "$RESET" >&2
  exit "$base_rc"
fi

print_fio
extract_base_summary
build_final_recommendation
write_markdown
print_final
