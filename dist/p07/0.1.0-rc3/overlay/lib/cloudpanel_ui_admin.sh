panel_security() {
  while true; do
    cat <<'EOF2'

CloudPanel 安全
----------------------------------------
  1. 启用 Panel Basic Auth
  2. 关闭 Panel Basic Auth
  3. 更新 Cloudflare Trusted IP 清单
  0. 返回
EOF2
    printf '请选择 [0-3]：'; read -r choice || return 0
    case "$choice" in
      1)
        printf 'Basic Auth 用户名：'; read -r username || continue
        prompt_secret_twice 'Basic Auth 密码' || { pause; continue; }
        printf '启用后访问 CloudPanel 需要额外认证。继续？[y/N]：'; read -r confirm || true
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
          if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" <<'PY'
import os,sys
import cloudpanel
pw=os.environ.pop('P07_SECRET')
cloudpanel.enable_panel_basic_auth(sys.argv[1],pw)
PY
          then printf '\nBasic Auth 已启用 ✓\n'; else printf '\nBasic Auth 启用未完成。\n' >&2; fi
        fi
        SECRET_VALUE=""; pause ;;
      2)
        printf '关闭后 CloudPanel 将失去这一层额外认证。输入 DISABLE 继续：'; read -r confirm || true
        if [[ "$confirm" == DISABLE ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
cloudpanel.disable_panel_basic_auth()
PY
          then printf '\nBasic Auth 已关闭。\n'; else printf '\nBasic Auth 关闭未完成。\n' >&2; fi
        fi
        pause ;;
      3)
        printf '这只刷新 CloudPanel 的 Cloudflare IP allowlist，不修改 DNS。继续？[Y/n]：'; read -r confirm || true
        if [[ -z "$confirm" || "$confirm" =~ ^[Yy]$ ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
cloudpanel.update_cloudflare_ips()
PY
          then printf '\nCloudflare Trusted IP 已更新 ✓\nDNS：未修改\n'; else printf '\nTrusted IP 更新未完成。\n' >&2; fi
        fi
        pause ;;
      0) return 0 ;;
      *) printf '请输入 0-3。\n' ;;
    esac
  done
}

panel_users() {
  while true; do
    cat <<'EOF2'

CloudPanel 用户
----------------------------------------
  1. 查看用户
  2. 新增用户
  3. 重置用户密码
  4. 关闭用户 2FA
  0. 返回
EOF2
    printf '请选择 [0-4]：'; read -r choice || return 0
    case "$choice" in
      1)
        if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
print(cloudpanel.list_panel_users(),end='')
PY
        then :; else printf '用户清单读取失败。\n' >&2; fi
        pause ;;
      2)
        printf '用户名：'; read -r username || continue
        printf 'Email：'; read -r email || continue
        printf 'First Name：'; read -r first || continue
        printf 'Last Name：'; read -r last || continue
        printf '角色 [user/site-manager/admin]（默认 user）：'; read -r role || true; role="${role:-user}"
        sites=""; if [[ "$role" == user ]]; then printf '限制站点（可留空；多个逗号分隔）：'; read -r sites || true; fi
        printf 'Timezone [UTC]：'; read -r timezone || true; timezone="${timezone:-UTC}"
        prompt_secret_twice '用户密码' || { pause; continue; }
        if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" "$email" "$first" "$last" "$role" "$sites" "$timezone" <<'PY'
import os,sys
import cloudpanel
pw=os.environ.pop('P07_SECRET')
sites=[x.strip() for x in sys.argv[6].split(',') if x.strip()]
cloudpanel.add_panel_user(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],pw,role=sys.argv[5],sites=sites,timezone=sys.argv[7])
PY
        then printf '\n用户已创建 ✓\n'; else printf '\n用户创建未完成。\n' >&2; fi
        SECRET_VALUE=""; pause ;;
      3)
        printf '用户名：'; read -r username || continue
        prompt_secret_twice '新密码' || { pause; continue; }
        if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" <<'PY'
import os,sys
import cloudpanel
pw=os.environ.pop('P07_SECRET')
cloudpanel.reset_panel_user_password(sys.argv[1],pw)
PY
        then printf '\n密码已重置 ✓\n'; else printf '\n密码重置未完成。\n' >&2; fi
        SECRET_VALUE=""; pause ;;
      4)
        printf '用户名：'; read -r username || continue
        printf '关闭 2FA 会降低该用户登录保护。输入 DISABLE-MFA 继续：'; read -r confirm || true
        if [[ "$confirm" == DISABLE-MFA ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" <<'PY'
import sys
import cloudpanel
cloudpanel.disable_panel_user_mfa(sys.argv[1])
PY
          then printf '\n2FA 已关闭。\n'; else printf '\n2FA 关闭未完成。\n' >&2; fi
        fi
        pause ;;
      0) return 0 ;;
      *) printf '请输入 0-4。\n' ;;
    esac
  done
}

vhost_tools() {
  while true; do
    cat <<'EOF2'

Vhost Templates
----------------------------------------
  1. 查看模板
  2. 刷新官方模板
  3. 查看指定模板内容
  4. 添加自定义模板
  0. 返回
EOF2
    printf '请选择 [0-4]：'; read -r choice || return 0
    case "$choice" in
      1)
        PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY' || true
import cloudpanel
print(cloudpanel.list_vhost_templates(),end='')
PY
        pause ;;
      2)
        printf '刷新模板不会删除网站。继续？[Y/n]：'; read -r confirm || true
        if [[ -z "$confirm" || "$confirm" =~ ^[Yy]$ ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
cloudpanel.import_vhost_templates()
PY
          then printf '\n模板已刷新 ✓\n'; else printf '\n模板刷新未完成。\n' >&2; fi
        fi
        pause ;;
      3)
        printf '模板名：'; read -r name || continue
        PYTHONPATH="$ROOT_DIR/lib" python3 - "$name" <<'PY' || true
import sys,cloudpanel
print(cloudpanel.view_vhost_template(sys.argv[1]),end='')
PY
        pause ;;
      4)
        printf '模板名：'; read -r name || continue
        printf '本地文件或 HTTPS URL：'; read -r source || continue
        if PYTHONPATH="$ROOT_DIR/lib" python3 - "$name" "$source" <<'PY'
import sys,cloudpanel
cloudpanel.add_vhost_template(sys.argv[1],sys.argv[2])
PY
        then printf '\n自定义模板已添加 ✓\n'; else printf '\n模板添加未完成。\n' >&2; fi
        pause ;;
      0) return 0 ;;
      *) printf '请输入 0-4。\n' ;;
    esac
  done
}

platform_status() {
  printf '\nCloudPanel 基础能力自检\n----------------------------------------\n'
  if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
print('CLI：READY')
print('版本：'+cloudpanel.version())
templates=cloudpanel.list_vhost_templates().strip().splitlines()
print('Vhost Templates：READY' if templates else 'Vhost Templates：EMPTY/UNKNOWN')
print('站点类型：PHP / Static / Node.js / Python / Reverse Proxy')
print('数据库：ADD / EXPORT / IMPORT')
print('SSL：STATUS / LETS_ENCRYPT / CUSTOM_CERT')
print('Panel 安全：BASIC_AUTH / CLOUDFLARE_TRUSTED_IPS')
print('用户：LIST / ADD / RESET_PASSWORD / DISABLE_MFA')
PY
  then
    if command -v nginx >/dev/null 2>&1 && nginx -t >/dev/null 2>&1; then printf 'NGINX：READY\n'; else printf 'NGINX：UNKNOWN/NOT_READY\n'; fi
    if load_inventory; then
      python3 - "$INV_FILE" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
print('Inventory：READY')
print('Sites：'+str(len(p.get('sites',[]) if isinstance(p.get('sites'),list) else [])))
PY
    else printf 'Inventory：NOT_READY\n'; fi
  else
    printf 'CloudPanel 基础能力检查没有完成。\n' >&2
  fi
  printf '安全边界：不改 DNS / 不删除 SOURCE / 不覆盖 existing TARGET。\n'
  pause
}
