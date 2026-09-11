ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE="$ROOT_DIR/bin/vfops"
INV_FILE=""
SELECTED_INDEX=""
SELECTED_DOMAIN=""
SELECTED_DATABASE=""
SECRET_VALUE=""

cleanup() {
  [[ -n "$INV_FILE" ]] && rm -f "$INV_FILE" 2>/dev/null || true
  SECRET_VALUE=""
}
trap cleanup EXIT
pause() { printf '\n按 Enter 返回...'; read -r _ || true; }

clear_site_selection() {
  SELECTED_INDEX=""
  SELECTED_DOMAIN=""
  SELECTED_DATABASE=""
}

load_inventory() {
  [[ -n "$INV_FILE" ]] && rm -f "$INV_FILE" 2>/dev/null || true
  INV_FILE="$(mktemp -t p07-cp-tools.XXXXXX)"
  "$CORE" inventory --compact >"$INV_FILE" 2>/dev/null
}

select_site() {
  local count choice resolved

  if [[ -n "$SELECTED_DOMAIN" ]]; then
    load_inventory || { printf '\n无法刷新 CloudPanel 网站。\n'; clear_site_selection; return 1; }
    resolved="$(python3 - "$INV_FILE" "$SELECTED_DOMAIN" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
wanted=sys.argv[2].strip().lower().rstrip('.')
for i,s in enumerate(p.get('sites',[]),1):
    if str(s.get('domain','')).lower().rstrip('.') == wanted:
        print(i)
        raise SystemExit(0)
raise SystemExit(1)
PY
)" || true
    if [[ "$resolved" =~ ^[1-9][0-9]*$ ]]; then
      SELECTED_INDEX="$resolved"
      return 0
    fi
    printf '\n当前网站已不在 CloudPanel inventory 中，请重新选择。\n'
    clear_site_selection
  fi

  SELECTED_INDEX=""
  load_inventory || { printf '\n无法读取 CloudPanel 网站。\n'; return 1; }
  count="$(python3 - "$INV_FILE" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
sites=p.get('sites',[]) if isinstance(p.get('sites'),list) else []
print(len(sites))
PY
)"
  [[ "$count" -gt 0 ]] || { printf '\n没有发现 CloudPanel 网站。\n'; return 2; }
  printf '\n请选择网站\n----------------------------------------\n'
  python3 - "$INV_FILE" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
for i,s in enumerate(p.get('sites',[]),1):
    print(f"  {i}. {s.get('domain','UNKNOWN')}")
print('  0. 返回')
PY
  printf '\n请选择 [0-%s]：' "$count"; read -r choice || return 2
  [[ "$choice" =~ ^[0-9]+$ ]] || return 1
  [[ "$choice" == 0 ]] && return 2
  (( choice>=1 && choice<=count )) || return 1
  SELECTED_INDEX="$choice"
  SELECTED_DOMAIN="$(python3 - "$INV_FILE" "$SELECTED_INDEX" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
print(p['sites'][int(sys.argv[2])-1].get('domain','UNKNOWN'))
PY
)"
  [[ -n "$SELECTED_DOMAIN" && "$SELECTED_DOMAIN" != UNKNOWN ]]
}

site_fields() {
  python3 - "$INV_FILE" "$SELECTED_INDEX" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8')); s=p['sites'][int(sys.argv[2])-1]
r=s.get('runtime',{}) if isinstance(s.get('runtime'),dict) else {}
ssl=s.get('ssl',{}) if isinstance(s.get('ssl'),dict) else {}
mysql=s.get('mysql_databases'); sqlite=s.get('sqlite_paths')
print(s.get('domain','UNKNOWN'))
print(s.get('site_user','UNKNOWN'))
print(s.get('site_root','UNKNOWN'))
print(s.get('document_root','UNKNOWN'))
print(r.get('type','UNKNOWN'))
print(r.get('version','UNKNOWN'))
print(len(mysql) if isinstance(mysql,list) else -1)
print(len(sqlite) if isinstance(sqlite,list) else -1)
print('YES' if ssl.get('configured') is True else ('NO' if ssl.get('configured') is False else 'UNKNOWN'))
print(ssl.get('days_remaining','UNKNOWN'))
PY
}

site_domain_exists() {
  local domain="$1"
  load_inventory || return 2
  python3 - "$INV_FILE" "$domain" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8'))
domain=sys.argv[2].strip().lower().rstrip('.')
for s in p.get('sites',[]):
    if str(s.get('domain','')).lower().rstrip('.') == domain:
        raise SystemExit(0)
raise SystemExit(1)
PY
}

select_database() {
  SELECTED_DATABASE=""
  local choice count
  count="$(python3 - "$INV_FILE" "$SELECTED_INDEX" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8')); s=p['sites'][int(sys.argv[2])-1]
dbs=s.get('mysql_databases')
print(len(dbs) if isinstance(dbs,list) else -1)
PY
)"
  if [[ "$count" == -1 ]]; then printf '数据库清单为 UNKNOWN，已停止。\n'; return 1; fi
  if [[ "$count" == 0 ]]; then printf '该网站没有发现 MySQL 数据库。\n'; return 2; fi
  printf '\n请选择数据库\n----------------------------------------\n'
  python3 - "$INV_FILE" "$SELECTED_INDEX" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8')); s=p['sites'][int(sys.argv[2])-1]
for i,name in enumerate(s.get('mysql_databases',[]),1): print(f'  {i}. {name}')
print('  0. 返回')
PY
  printf '\n请选择 [0-%s]：' "$count"; read -r choice || return 2
  [[ "$choice" =~ ^[0-9]+$ ]] || return 1
  [[ "$choice" == 0 ]] && return 2
  (( choice>=1 && choice<=count )) || return 1
  SELECTED_DATABASE="$(python3 - "$INV_FILE" "$SELECTED_INDEX" "$choice" <<'PY'
import json,sys
p=json.load(open(sys.argv[1],encoding='utf-8')); s=p['sites'][int(sys.argv[2])-1]
print(s['mysql_databases'][int(sys.argv[3])-1])
PY
)"
  [[ -n "$SELECTED_DATABASE" ]]
}

prompt_secret_twice() {
  local label="$1" first second
  printf '%s：' "$label"; read -r -s first || return 1; printf '\n'
  printf '再次输入：'; read -r -s second || return 1; printf '\n'
  [[ -n "$first" ]] || { printf '密码不能为空。\n'; return 1; }
  [[ "$first" == "$second" ]] || { printf '两次输入不一致。\n'; return 1; }
  SECRET_VALUE="$first"
}

show_site_details() {
  local rc fields domain user root docroot runtime version mysql sqlite ssl days
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields)
  domain="${fields[0]}"; user="${fields[1]}"; root="${fields[2]}"; docroot="${fields[3]}"
  runtime="${fields[4]}"; version="${fields[5]}"; mysql="${fields[6]}"; sqlite="${fields[7]}"; ssl="${fields[8]}"; days="${fields[9]}"
  printf '\n网站详情\n----------------------------------------\n'
  printf '域名：%s\nSite User：%s\nSite Root：%s\nDocument Root：%s\n' "$domain" "$user" "$root" "$docroot"
  printf 'Runtime：%s %s\nMySQL：%s\nSQLite：%s\nSSL：%s\nSSL 剩余天数：%s\n' "$runtime" "$version" "$mysql" "$sqlite" "$ssl" "$days"
  printf '读取方式：只读，不修改网站。\n'
  pause
}

site_health() {
  local rc fields domain user docroot http_code https_code
  if select_site; then :; else rc=$?; [[ $rc -eq 2 ]] && return 0; pause; return 0; fi
  mapfile -t fields < <(site_fields); domain="${fields[0]}"; user="${fields[1]}"; docroot="${fields[3]}"
  printf '\n网站健康检查（只读）\n----------------------------------------\n'
  [[ "$user" != UNKNOWN ]] && id "$user" >/dev/null 2>&1 && printf 'Site User：PASS\n' || printf 'Site User：UNKNOWN/FAIL\n'
  [[ "$docroot" != UNKNOWN && -d "$docroot" ]] && printf 'Document Root：PASS\n' || printf 'Document Root：UNKNOWN/FAIL\n'
  if command -v nginx >/dev/null 2>&1 && nginx -t >/dev/null 2>&1; then printf 'NGINX 配置：PASS\n'; else printf 'NGINX 配置：UNKNOWN/FAIL\n'; fi
  http_code="$(curl -sS --max-time 8 --resolve "$domain:80:127.0.0.1" -o /dev/null -w '%{http_code}' "http://$domain/" 2>/dev/null || true)"
  https_code="$(curl -ksS --max-time 8 --resolve "$domain:443:127.0.0.1" -o /dev/null -w '%{http_code}' "https://$domain/" 2>/dev/null || true)"
  [[ "$http_code" =~ ^[1-5][0-9][0-9]$ ]] || http_code="NO_RESPONSE"
  [[ "$https_code" =~ ^[1-5][0-9][0-9]$ ]] || https_code="NO_RESPONSE"
  printf '本机 Host HTTP：%s\n本机 SNI HTTPS：%s\n' "$http_code" "$https_code"
  printf '说明：使用 127.0.0.1 本机路由验证，不修改 DNS、不修改 hosts。\n'
  pause
}
