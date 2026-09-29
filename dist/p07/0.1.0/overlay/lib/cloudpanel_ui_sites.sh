create_site() {
  local type domain user version port template proxy confirm rc
  say; ui_title '创建 CloudPanel 网站'; ui_rule
  ui_menu_warn 1 'PHP'
  ui_menu_warn 2 'Static HTML'
  ui_menu_warn 3 'Node.js'
  ui_menu_warn 4 'Python'
  ui_menu_warn 5 'Reverse Proxy'
  ui_menu_back 0 '返回'
  ui_prompt '请选择 [0-5]：'; read -r type || return 0
  [[ "$type" == 0 ]] && return 0
  [[ "$type" =~ ^[1-5]$ ]] || { printf '无效类型。\n'; pause; return 0; }
  printf '域名：'; read -r domain || return 0
  printf 'Site User：'; read -r user || return 0
  if site_domain_exists "$domain"; then
    ui_bad 'TARGET 已存在，P07 不会覆盖。'; pause; return 0
  else
    rc=$?
    [[ $rc -eq 1 ]] || { ui_bad '无法安全确认 TARGET 是否存在，已停止。'; pause; return 0; }
  fi
  prompt_secret_twice 'Site User 密码' || { pause; return 0; }
  version=""; port=""; template=""; proxy=""
  case "$type" in
    1) printf 'PHP 版本 [8.4]：'; read -r version || true; version="${version:-8.4}"; printf 'Vhost Template [Generic]：'; read -r template || true; template="${template:-Generic}" ;;
    3) printf 'Node.js 版本 [22]：'; read -r version || true; version="${version:-22}"; printf 'App Port [3000]：'; read -r port || true; port="${port:-3000}" ;;
    4) printf 'Python 版本 [3.13]：'; read -r version || true; version="${version:-3.13}"; printf 'App Port [8000]：'; read -r port || true; port="${port:-8000}" ;;
    5) printf 'Reverse Proxy URL（例如 http://127.0.0.1:8000）：'; read -r proxy || true ;;
  esac
  say; ui_attention "将创建新 TARGET：$domain"; ui_note '不会修改 DNS，不会删除任何 SOURCE。'; ui_prompt '继续？[y/N]：'; read -r confirm || true
  [[ "$confirm" =~ ^[Yy]$ ]] || { SECRET_VALUE=""; return 0; }
  if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$type" "$domain" "$user" "$version" "$port" "$template" "$proxy" <<'PY'
import os,sys
import cloudpanel
kind,domain,user,version,port,template,proxy=sys.argv[1:]
password=os.environ.pop('P07_SECRET')
if kind=='1': cloudpanel.add_php_site(domain,version,user,password,vhost_template=template)
elif kind=='2': cloudpanel.add_static_site(domain,user,password)
elif kind=='3': cloudpanel.add_nodejs_site(domain,version,port,user,password)
elif kind=='4': cloudpanel.add_python_site(domain,version,port,user,password)
elif kind=='5': cloudpanel.add_reverse_proxy_site(domain,proxy,user,password)
PY
  then
    SECRET_VALUE=""
    if site_domain_exists "$domain"; then
      ui_good '网站已创建并读回确认 ✓'
    else
      ui_attention 'CloudPanel 已返回成功，但 P07 暂未在 inventory 中读回该网站；未执行删除或覆盖，请稍后查看。'
    fi
    ui_note 'DNS：未修改 · SOURCE：未删除'
  else
    SECRET_VALUE=""
    printf '%b\n' "${C_RED}网站创建未完成；P07 未修改 DNS，也未删除 SOURCE。${C_RESET}" >&2
  fi
  pause
}

list_site_databases() {
  local rc
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  say; ui_title '数据库清单'; ui_rule
  python3 - "$INV_FILE" "$SELECTED_INDEX" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8')); s=p['sites'][int(sys.argv[2])-1]
dbs=s.get('mysql_databases')
if dbs == 'UNKNOWN' or not isinstance(dbs,list): print('UNKNOWN')
elif not dbs: print('（无）')
else:
    for name in dbs: print(name)
PY
  pause
}

add_site_database() {
  local rc fields domain db dbuser confirm
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"
  printf '数据库名：'; read -r db || return 0
  printf '数据库用户名：'; read -r dbuser || return 0
  prompt_secret_twice '数据库密码' || { pause; return 0; }
  ui_attention "将在 $domain 新增数据库 $db；不会删除已有数据库。"; ui_prompt '继续？[y/N]：'; read -r confirm || true
  [[ "$confirm" =~ ^[Yy]$ ]] || { SECRET_VALUE=""; return 0; }
  if P07_SECRET="$SECRET_VALUE" PYTHONPATH="$ROOT_DIR/lib" python3 - "$domain" "$db" "$dbuser" <<'PY'
import os,sys
import cloudpanel
password=os.environ.pop('P07_SECRET')
cloudpanel.add_database(sys.argv[1],sys.argv[2],sys.argv[3],password)
PY
  then ui_good '数据库已创建 ✓'; else printf '%b\n' "${C_RED}数据库创建未完成。${C_RESET}" >&2; fi
  SECRET_VALUE=""
  pause
}

export_site_database() {
  local rc fields user db out
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); user="${fields[1]}"
  [[ "$user" != UNKNOWN ]] || { printf 'Site User UNKNOWN，已停止。\n'; pause; return 0; }
  if select_database; then db="$SELECTED_DATABASE"; else pause; return 0; fi
  out="/home/$user/tmp/p07-${db}-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
  runuser -u "$user" -- mkdir -p "/home/$user/tmp" 2>/dev/null || { printf '无法准备 Site User tmp 目录。\n'; pause; return 0; }
  if PYTHONPATH="$ROOT_DIR/lib" python3 - "$user" "$db" "$out" <<'PY'
import sys
import cloudpanel_site
cloudpanel_site.export_database(sys.argv[1],sys.argv[2],sys.argv[3])
PY
  then ui_good '数据库导出完成 ✓'; say "文件：${C_GRAY}$out${C_RESET}"; else printf '%b\n' "${C_RED}数据库导出未完成。${C_RESET}" >&2; fi
  pause
}

import_site_database() {
  local rc fields user db src confirm
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); user="${fields[1]}"
  [[ "$user" != UNKNOWN ]] || { printf 'Site User UNKNOWN，已停止。\n'; pause; return 0; }
  if select_database; then db="$SELECTED_DATABASE"; else pause; return 0; fi
  printf 'SQL 文件绝对路径：'; read -r src || return 0
  [[ -f "$src" ]] || { printf '文件不存在。\n'; pause; return 0; }
  say; ui_attention "注意：导入会修改数据库 $db 的数据，但不会删除数据库或网站。"; ui_prompt '输入 IMPORT 继续：'; read -r confirm || true
  [[ "$confirm" == IMPORT ]] || return 0
  if PYTHONPATH="$ROOT_DIR/lib" python3 - "$user" "$db" "$src" <<'PY'
import sys
import cloudpanel_site
cloudpanel_site.import_database(sys.argv[1],sys.argv[2],sys.argv[3])
PY
  then ui_good '数据库导入完成 ✓'; else printf '%b\n' "${C_RED}数据库导入未完成。${C_RESET}" >&2; fi
  pause
}

database_tools() {
  while true; do
    say; ui_title '数据库工具'; ui_rule
    ui_menu_info 1 '查看数据库'
    ui_menu_warn 2 '新增数据库'
    ui_menu_good 3 '导出数据库'
    ui_menu_warn 4 '导入数据库'
    ui_menu_back 0 '返回'
    ui_prompt '请选择 [0-4]：'; read -r choice || return 0
    case "$choice" in
      1) list_site_databases ;;
      2) add_site_database ;;
      3) export_site_database ;;
      4) import_site_database ;;
      0) return 0 ;;
      *) ui_warn '请输入 0-4。' ;;
    esac
  done
}
