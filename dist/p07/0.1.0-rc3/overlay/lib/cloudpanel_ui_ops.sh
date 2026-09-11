ssl_status() {
  local rc fields domain ssl days
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"; ssl="${fields[8]}"; days="${fields[9]}"
  printf '\nSSL 状态\n----------------------------------------\n域名：%s\n配置：%s\n剩余天数：%s\n' "$domain" "$ssl" "$days"
  printf '仅检查状态，不修改 DNS。\n'
  pause
}

issue_lets_encrypt() {
  local rc fields domain sans confirm
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"
  printf '附加域名 SAN（可留空；多个用逗号分隔）：'; read -r sans || true
  printf 'CloudPanel 申请 Let’s Encrypt 前要求 DNS 已正确指向本机。P07 不会修改 DNS。继续？[y/N]：'; read -r confirm || true
  [[ "$confirm" =~ ^[Yy]$ ]] || return 0
  if PYTHONPATH="$ROOT_DIR/lib" python3 - "$domain" "$sans" <<'PY'
import sys
import cloudpanel
sans=[x.strip() for x in sys.argv[2].split(',') if x.strip()]
cloudpanel.install_lets_encrypt(sys.argv[1],subject_alt_names=sans)
PY
  then printf '\nLet’s Encrypt 安装完成 ✓\n'; else printf '\n证书申请/安装未完成；DNS 未被 P07 修改。\n' >&2; fi
  pause
}

install_custom_certificate() {
  local rc fields domain key cert chain confirm
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"
  printf 'Private Key 文件：'; read -r key || return 0
  printf 'Certificate 文件：'; read -r cert || return 0
  printf 'Certificate Chain 文件（可留空）：'; read -r chain || true
  [[ -f "$key" && -f "$cert" ]] || { printf 'Key/Certificate 文件不存在。\n'; pause; return 0; }
  [[ -z "$chain" || -f "$chain" ]] || { printf 'Chain 文件不存在。\n'; pause; return 0; }
  printf '将为 %s 安装自定义证书，不修改 DNS。继续？[y/N]：' "$domain"; read -r confirm || true
  [[ "$confirm" =~ ^[Yy]$ ]] || return 0
  if PYTHONPATH="$ROOT_DIR/lib" python3 - "$domain" "$key" "$cert" "$chain" <<'PY'
import sys
import cloudpanel
chain=sys.argv[4] or None
cloudpanel.install_certificate(sys.argv[1],sys.argv[2],sys.argv[3],certificate_chain=chain)
PY
  then printf '\n自定义证书安装完成 ✓\n'; else printf '\n证书安装未完成。\n' >&2; fi
  pause
}

ssl_tools() {
  while true; do
    cat <<'EOF2'

SSL / HTTPS
----------------------------------------
  1. 查看 SSL 状态
  2. 申请 / 安装 Let’s Encrypt
  3. 安装自定义证书
  0. 返回
EOF2
    printf '请选择 [0-3]：'; read -r choice || return 0
    case "$choice" in
      1) ssl_status ;;
      2) issue_lets_encrypt ;;
      3) install_custom_certificate ;;
      0) return 0 ;;
      *) printf '请输入 0-3。\n' ;;
    esac
  done
}

repair_permissions() {
  local rc fields domain user root confirm
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"; user="${fields[1]}"; root="${fields[2]}"
  if [[ "$user" == UNKNOWN || "$root" == UNKNOWN ]]; then printf '网站用户/目录无法安全识别，已停止。\n'; pause; return 0; fi
  printf '\n将使用 CloudPanel Site User 权限修复：%s\n路径：%s\n' "$domain" "$root"
  printf '目录权限 770，文件权限 660；不会删除文件。继续？[y/N]：'; read -r confirm || return 0
  [[ "$confirm" =~ ^[Yy]$ ]] || return 0
  if PYTHONPATH="$ROOT_DIR/lib" python3 - "$user" "$root" <<'PY'
import sys
import cloudpanel_site
cloudpanel_site.reset_permissions(sys.argv[1],sys.argv[2])
PY
  then printf '\n权限修复完成 ✓\n'; else printf '\n权限修复没有完成；网站文件未被 P07 删除。\n' >&2; fi
  pause
}

purge_varnish() {
  local rc fields domain user target confirm
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"; user="${fields[1]}"
  [[ "$user" != UNKNOWN ]] || { printf 'Site User 无法识别，已停止。\n'; pause; return 0; }
  printf '清理目标 [all]（也可输入 URL 或 tag1,tag2）：'; read -r target || true; target="${target:-all}"
  printf '\n将清理 %s 的 Varnish 缓存：%s\n不会删除网站文件。继续？[Y/n]：' "$domain" "$target"; read -r confirm || true
  [[ -z "$confirm" || "$confirm" =~ ^[Yy]$ ]] || return 0
  if PYTHONPATH="$ROOT_DIR/lib" python3 - "$user" "$target" <<'PY'
import sys
import cloudpanel_site
cloudpanel_site.purge_varnish(sys.argv[1],sys.argv[2])
PY
  then printf '\nVarnish 缓存已清理 ✓\n'; else printf '\nVarnish 清理未完成；可能该网站未启用 Varnish。网站文件未修改。\n' >&2; fi
  pause
}

maintenance_tools() {
  while true; do
    cat <<'EOF2'

权限 / 缓存
----------------------------------------
  1. 修复网站权限
  2. 清理 Varnish 缓存
  0. 返回
EOF2
    printf '请选择 [0-2]：'; read -r choice || return 0
    case "$choice" in
      1) repair_permissions ;;
      2) purge_varnish ;;
      0) return 0 ;;
      *) printf '请输入 0-2。\n' ;;
    esac
  done
}
