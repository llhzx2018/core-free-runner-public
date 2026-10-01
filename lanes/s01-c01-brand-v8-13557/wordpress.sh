#!/usr/bin/env bash
set -Eeuo pipefail
NET="vf-v8-${GITHUB_RUN_ID}"; DB="$NET-db"; WP="$NET-wp"
cleanup(){ docker rm -f "$WP" "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; [[ -n "${MOCK_PID:-}" ]] && kill "$MOCK_PID" || true; }
trap cleanup EXIT
ASSET="vf-tools-theme_V${TARGET_VERSION}.zip"
export MOCK_PORT=18881 MOCK_ASSET="$PWD/proof/$ASSET" MOCK_STATE="$PWD/mock-state.json" MOCK_LOG="$PWD/mock.log" MOCK_HOST=vf-update.test
echo '{"mode":"normal"}' > "$MOCK_STATE"
python3 - <<'PY'
import pathlib,os
s=pathlib.Path('target/tests/wp-update/mock-github-server.py').read_text()
s=s.replace('1.35.8',os.environ['SOURCE_VERSION']).replace('1.35.9',os.environ['TARGET_VERSION'])
s=s.replace('VF_Tools_Theme_V'+os.environ['TARGET_VERSION']+'_UPDATE.zip','vf-tools-theme_V'+os.environ['TARGET_VERSION']+'.zip')
s=s.replace("if not self.auth_ok(): return", "if not self.auth_ok(): return\n        if p.path=='/repos/llhzx2018/core-updates': self.send_json({'private':True}); return")
pathlib.Path('/tmp/v8-mock.py').write_text(s)
PY
python3 /tmp/v8-mock.py >/tmp/v8-mock-stdout 2>&1 & MOCK_PID=$!
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" -e MARIADB_ROOT_PASSWORD=syntheticroot -e MARIADB_DATABASE=wordpress -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=syntheticdb mariadb:11.8.8 >/dev/null
for i in $(seq 1 60); do docker exec "$DB" mariadb-admin ping -h127.0.0.1 -uroot -psyntheticroot --silent >/dev/null 2>&1 && break; sleep 2; done
docker run -d --name "$WP" --network "$NET" --add-host vf-update.test:host-gateway -p 18880:80 -e WORDPRESS_DB_HOST="$DB:3306" -e WORDPRESS_DB_NAME=wordpress -e WORDPRESS_DB_USER=wordpress -e WORDPRESS_DB_PASSWORD=syntheticdb wordpress:7.1.2-php8.3-apache >/dev/null
for i in $(seq 1 90); do docker exec "$WP" test -f /var/www/html/wp-settings.php && curl -fsS http://127.0.0.1:18880/wp-admin/install.php >/dev/null && break; sleep 2; done
curl -fsSLo /tmp/wp-cli.phar https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar
docker cp /tmp/wp-cli.phar "$WP:/usr/local/bin/wp";docker exec "$WP" chmod 0755 /usr/local/bin/wp
cli(){ docker exec --user www-data -e TARGET_VERSION="$TARGET_VERSION" -e SOURCE_VERSION="$SOURCE_VERSION" "$WP" php /usr/local/bin/wp "$@" --path=/var/www/html; }
cli core install --url=http://127.0.0.1:18880 --title='Synthetic VF Update' --admin_user=admin --admin_password='Synthetic-Only-Update-54!' --admin_email=runner@example.invalid --skip-email >/dev/null
cli config set VF_WP_UPDATE_TEST_MODE true --raw >/dev/null
cli config set VF_WP_UPDATE_GITHUB_API_BASE http://vf-update.test:18881 >/dev/null
docker cp "previous/vf-tools-theme_V${SOURCE_VERSION}.zip" "$WP:/var/www/html/previous.zip"
cli theme install /var/www/html/previous.zip --activate >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
cli option update vf_private_update_credential_v1 runner-private-token >/dev/null
cli eval 'set_theme_mod("vf_v8_preservation_sentinel", "keep-me");' >/dev/null
cli eval 'VF_Theme_Update_Client_V1::clear_cache();delete_site_transient("update_themes");wp_update_themes();$t=get_site_transient("update_themes");if(($t->response["vf-tools-theme"]["new_version"]??"")!==getenv("TARGET_VERSION")){throw new Exception("discovery failed");}' >/dev/null
cli eval 'VF_Theme_Update_Client_V1::clear_cache();require_once ABSPATH."wp-admin/includes/class-wp-upgrader.php";$u=new Theme_Upgrader(new Automatic_Upgrader_Skin());$r=$u->upgrade("vf-tools-theme");if(is_wp_error($r)||($r!==true&&!is_array($r))){throw new Exception("native upgrade failed: ".wp_json_encode(VF_Theme_Update_Client_V1::status()));}' >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
test "$(cli option get stylesheet)" = vf-tools-theme
cli eval 'if(get_theme_mod("vf_v8_preservation_sentinel")!=="keep-me"){throw new Exception("settings changed");}$r=VF_Theme_Update_Client_V1::recovery();if($r["source_version"]!==getenv("SOURCE_VERSION")||$r["target_version"]!==getenv("TARGET_VERSION")||!is_file($r["path"])||hash_file("sha256",$r["path"])!==$r["sha256"]){throw new Exception("recovery invalid");}$s=VF_Theme_Runtime_Authority_V1::stored();$v=VF_Theme_Runtime_Authority_V1::verify(getenv("TARGET_VERSION"),get_template_directory());if(is_wp_error($v)){throw new Exception($v->get_error_code());}echo wp_json_encode(["upgrade"=>"PASS","source"=>$r["source_version"],"target"=>$r["target_version"],"recovery_sha256"=>$r["sha256"],"settings_preserved"=>true,"runtime"=>$s]);' > proof/upgrade.json
cli eval '$a=VF_Theme_Runtime_Authority_V1::snapshot(get_template_directory());echo wp_json_encode(["runtime_files"=>$a["file_count"],"runtime_fingerprint"=>$a["fingerprint_sha256"]]);' > proof/runtime.json
cli eval '$r=$GLOBALS["vf_theme_update_client_v1"]->restore_latest_recovery();if(is_wp_error($r)){throw new Exception($r->get_error_code());}' >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$SOURCE_VERSION"
test "$(cli option get stylesheet)" = vf-tools-theme
cli eval 'if(get_theme_mod("vf_v8_preservation_sentinel")!=="keep-me"){throw new Exception("rollback settings changed");}' >/dev/null
cli eval 'VF_Theme_Update_Client_V1::clear_cache();delete_site_transient("update_themes");wp_update_themes();require_once ABSPATH."wp-admin/includes/class-wp-upgrader.php";$u=new Theme_Upgrader(new Automatic_Upgrader_Skin());$r=$u->upgrade("vf-tools-theme");if(is_wp_error($r)||($r!==true&&!is_array($r))){throw new Exception("second upgrade failed");}' >/dev/null
test "$(cli theme get vf-tools-theme --field=version)" = "$TARGET_VERSION"
docker exec "$WP" mkdir -p /var/www/html/wp-content/mu-plugins
node lane/live-browser.js
curl -fsS http://127.0.0.1:18880/ >/tmp/v8-home.html
! grep -Ei 'Fatal error|critical error|Parse error' /tmp/v8-home.html
! grep -q AUTH_LEAK mock.log
python3 - <<'PY'
import json,pathlib,os
p=pathlib.Path('proof');m=json.loads((p/'identity.json').read_text());m.update(json.loads((p/'runtime.json').read_text()));m.update(status='PASS',upgrade='PASS',source_rollback='PASS',wordpress_browser='PASS',fixture_browser='PASS',brand_persistence='PASS',brand_csrf='PASS',owner_real_use='POST_PRODUCTION_REQUIRED',owner_preview_runtime='N_A',production='NOT_EXECUTED',candidate_run=os.environ['GITHUB_RUN_ID']);(p/'FINAL_EVIDENCE.json').write_text(json.dumps(m,indent=2));print(json.dumps(m))
PY
echo EXACT_CANDIDATE_GATE=PASS
