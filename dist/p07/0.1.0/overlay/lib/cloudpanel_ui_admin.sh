panel_security() {
  while true; do
    say; ui_title 'CloudPanel 安全'; ui_rule
    ui_menu_good 1 '启用面板基础认证（Basic Auth）'
    ui_menu_danger 2 '关闭面板基础认证（Basic Auth）'
    ui_menu_warn 3 '更新 Cloudflare 可信 IP 清单'
    ui_menu_back 0 '返回'
    ui_prompt '请选择 [0-3]：'; read -r choice || return 0
    case "$choice" in
      1)
        printf '基础认证用户名：'; read -r username || continue
        prompt_secret_twice 'Basic Auth 密码' || { pause; continue; }
        ui_attention '启用后访问 CloudPanel 需要额外认证。'; ui_prompt '继续？[y/N]：'; read -r confirm || true
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
          if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" <<'PY'
import os,sys
import cloudpanel
pw=os.environ.pop('P07_SECRET')
cloudpanel.enable_panel_basic_auth(sys.argv[1],pw)
PY
          then ui_good '基础认证已启用 ✓'; else printf '%b\n' "${C_RED}基础认证启用未完成。${C_RESET}" >&2; fi
        fi
        SECRET_VALUE=""; pause ;;
      2)
        ui_bad '关闭后 CloudPanel 将失去这一层额外认证。'; ui_prompt '输入 DISABLE 继续：'; read -r confirm || true
        if [[ "$confirm" == DISABLE ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
cloudpanel.disable_panel_basic_auth()
PY
          then ui_bad '基础认证已关闭。'; else printf '%b\n' "${C_RED}基础认证关闭未完成。${C_RESET}" >&2; fi
        fi
        pause ;;
      3)
        ui_attention '这只刷新 CloudPanel 的 Cloudflare IP allowlist，不修改 DNS。'; ui_prompt '继续？[Y/n]：'; read -r confirm || true
        if [[ -z "$confirm" || "$confirm" =~ ^[Yy]$ ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
cloudpanel.update_cloudflare_ips()
PY
          then ui_good 'Cloudflare 可信 IP 已更新 ✓'; ui_note 'DNS：未修改'; else printf '%b\n' "${C_RED}可信 IP 更新未完成。${C_RESET}" >&2; fi
        fi
        pause ;;
      0) return 0 ;;
      *) ui_warn '请输入 0-3。' ;;
    esac
  done
}

panel_users() {
  while true; do
    say; ui_title 'CloudPanel 用户'; ui_rule
    ui_menu_info 1 '查看用户'
    ui_menu_warn 2 '新增用户'
    ui_menu_warn 3 '重置用户密码'
    ui_menu_danger 4 '关闭用户 2FA'
    ui_menu_back 0 '返回'
    ui_prompt '请选择 [0-4]：'; read -r choice || return 0
    case "$choice" in
      1)
        if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import cloudpanel
print(cloudpanel.list_panel_users(),end='')
PY
        then :; else printf '%b\n' "${C_RED}用户清单读取失败。${C_RESET}" >&2; fi
        pause ;;
      2)
        printf '用户名：'; read -r username || continue
        printf 'Email：'; read -r email || continue
        printf 'First Name：'; read -r first || continue
        printf 'Last Name：'; read -r last || continue
        printf '角色 [user/site-manager/admin]（默认 user）：'; read -r role || true; role="${role:-user}"
        sites=""; if [[ "$role" == user ]]; then printf '限制站点（可留空；多个逗号分隔）：'; read -r sites || true; fi
        printf '时区 [UTC]：'; read -r timezone || true; timezone="${timezone:-UTC}"
        prompt_secret_twice '用户密码' || { pause; continue; }
        if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" "$email" "$first" "$last" "$role" "$sites" "$timezone" <<'PY'
import os,sys
import cloudpanel
pw=os.environ.pop('P07_SECRET')
sites=[x.strip() for x in sys.argv[6].split(',') if x.strip()]
cloudpanel.add_panel_user(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],pw,role=sys.argv[5],sites=sites,timezone=sys.argv[7])
PY
        then ui_good '用户已创建 ✓'; else printf '%b\n' "${C_RED}用户创建未完成。${C_RESET}" >&2; fi
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
        then ui_good '密码已重置 ✓'; else printf '%b\n' "${C_RED}密码重置未完成。${C_RESET}" >&2; fi
        SECRET_VALUE=""; pause ;;
      4)
        printf '用户名：'; read -r username || continue
        ui_bad '关闭 2FA 会降低该用户登录保护。'; ui_prompt '输入 DISABLE-MFA 继续：'; read -r confirm || true
        if [[ "$confirm" == DISABLE-MFA ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - "$username" <<'PY'
import sys
import cloudpanel
cloudpanel.disable_panel_user_mfa(sys.argv[1])
PY
          then ui_bad '2FA 已关闭。'; else printf '%b\n' "${C_RED}2FA 关闭未完成。${C_RESET}" >&2; fi
        fi
        pause ;;
      0) return 0 ;;
      *) ui_warn '请输入 0-4。' ;;
    esac
  done
}

# Advanced/internal helper. Ordinary users do not see this menu.
vhost_tools() {
  while true; do
    cat <<'EOF2'

Vhost Templates（高级）
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
        if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import sys,cloudpanel
try:
    print(cloudpanel.list_vhost_templates(),end='')
except Exception:
    print('模板清单读取未完成。', file=sys.stderr)
    raise SystemExit(1)
PY
        then :; else printf '模板清单读取未完成。\n' >&2; fi
        pause ;;
      2)
        printf '刷新模板不会删除网站。继续？[Y/n]：'; read -r confirm || true
        if [[ -z "$confirm" || "$confirm" =~ ^[Yy]$ ]]; then
          if PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import sys,cloudpanel
try:
    cloudpanel.import_vhost_templates()
except Exception:
    print('模板刷新未完成。', file=sys.stderr)
    raise SystemExit(1)
PY
          then printf '\n模板已刷新 ✓\n'; else printf '\n模板刷新未完成。\n' >&2; fi
        fi
        pause ;;
      3)
        printf '模板名：'; read -r name || continue
        if [[ -z "${name//[[:space:]]/}" ]]; then printf '模板名不能为空。\n' >&2; pause; continue; fi
        if PYTHONPATH="$ROOT_DIR/lib" python3 - "$name" <<'PY'
import sys,cloudpanel
try:
    print(cloudpanel.view_vhost_template(sys.argv[1]),end='')
except Exception:
    print('模板读取未完成，请检查模板名。', file=sys.stderr)
    raise SystemExit(1)
PY
        then :; else :; fi
        pause ;;
      4)
        printf '模板名：'; read -r name || continue
        if [[ -z "${name//[[:space:]]/}" ]]; then printf '模板名不能为空。\n' >&2; pause; continue; fi
        printf '本地文件或 HTTPS URL：'; read -r source || continue
        if [[ -z "${source//[[:space:]]/}" ]]; then printf '模板来源不能为空。\n' >&2; pause; continue; fi
        if PYTHONPATH="$ROOT_DIR/lib" python3 - "$name" "$source" <<'PY'
import sys,cloudpanel
try:
    cloudpanel.add_vhost_template(sys.argv[1],sys.argv[2])
except Exception:
    print('模板添加未完成，请检查模板名和来源。', file=sys.stderr)
    raise SystemExit(1)
PY
        then printf '\n自定义模板已添加 ✓\n'; else printf '\n模板添加未完成。\n' >&2; fi
        pause ;;
      0) return 0 ;;
      *) printf '请输入 0-4。\n' ;;
    esac
  done
}

platform_status() {
  say; ui_title 'CloudPanel 基础能力自检'; ui_rule
  if C_GREEN="$C_GREEN" C_YELLOW="$C_YELLOW" C_RESET="$C_RESET" PYTHONPATH="$ROOT_DIR/lib" python3 - <<'PY'
import os,cloudpanel
green=os.environ.get("C_GREEN",""); yellow=os.environ.get("C_YELLOW",""); reset=os.environ.get("C_RESET","")
def paint(text,color): return f"{color}{text}{reset}" if color else text
print('命令行工具：'+paint('已就绪',green))
print('版本：'+cloudpanel.version())
templates=cloudpanel.list_vhost_templates().strip().splitlines()
print('Vhost 配置模板：'+(paint('已就绪',green)+'（建站自动使用）' if templates else paint('为空/未知',yellow)))
print('站点类型：PHP / 静态 HTML / Node.js / Python / 反向代理')
print('数据库：新增 / 导出 / 导入')
print('SSL：状态 / Let’s Encrypt / 自定义证书')
print('面板安全：基础认证 / Cloudflare 可信 IP')
print('用户：列表 / 新增 / 重置密码 / 关闭 2FA')
PY
  then
    if command -v nginx >/dev/null 2>&1 && nginx -t >/dev/null 2>&1; then ui_good 'NGINX：已就绪'; else ui_bad 'NGINX：未知/未就绪'; fi
    if load_inventory; then
      C_GREEN="$C_GREEN" C_RESET="$C_RESET" python3 - "$INV_FILE" <<'PY'
import json,os,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
green=os.environ.get("C_GREEN",""); reset=os.environ.get("C_RESET","")
ready=f"{green}READY{reset}" if green else "READY"
print('Inventory：'+ready)
print('Sites：'+str(len(p.get('sites',[]) if isinstance(p.get('sites'),list) else [])))
PY
    else ui_bad '资源清单：未就绪'; fi
  else
    printf '%b\n' "${C_RED}CloudPanel 基础能力检查没有完成。${C_RESET}" >&2
  fi
  ui_note '安全边界：不改 DNS / 不删除源服务器 / 不覆盖已有目标。'
  pause
}
