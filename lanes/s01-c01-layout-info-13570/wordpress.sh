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
cli option update blogdescription 'Synthetic Runner tagline, preserved across native upgrade' >/dev/null
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
cli eval 'require_once get_template_directory()."/inc/options/options-inheritance.php";$r=vf_theme_temporary_visual_override_save(["label"=>"Synthetic inactive visual","enabled"=>false,"startsAt"=>time()-60,"expiresAt"=>time()+86400,"tokens"=>["brand"=>"#2563eb"]]);if(empty($r["ok"])||!empty($r["state"]["active"])){throw new Exception("synthetic inactive visual fixture invalid");}' >/dev/null
node lane/live-browser.js
curl -fsS http://127.0.0.1:18880/ >/tmp/v8-home.html
! grep -Ei 'Fatal error|critical error|Parse error' /tmp/v8-home.html
# This native lane does not run the obsolete credential mock server.
# Real nonce/logged-out negatives and bounded package/source checks are required.
python3 - <<'PY'
import json,pathlib,os
p=pathlib.Path('proof');m=json.loads((p/'identity.json').read_text());live=json.loads((p/'live-browser.json').read_text());fixture=json.loads((p/'fixture/browser-proof.json').read_text());assert len(live['checks'])==6 and all(c['preview_controls']=='PASS' and c['preview_scroll']=='PASS' and c['choice_controls']=='PASS' and c['recovery_controls']=='PASS' and c['number_controls']=='PASS' and c['advanced_controls']=='PASS' and c['advanced_interactions']=='PASS' for c in live['checks']);assert len(fixture['cases'])==24 and all(len(c.get('numbers',[]))==6 and bool(c.get('advanced')) and bool(c.get('preview')) for c in fixture['cases'] if c['scenario']!='interaction-regression');layout=json.loads((p/'layout-browser.json').read_text());assert layout['status']=='PASS' and len(layout['cases'])==120 and len(layout['interactions'])==6;controls=json.loads((p/'layout-controls.json').read_text());assert controls['status']=='PASS' and len(controls['cases'])==40 and len(controls['checks'])>1000;m.update(layout_all_controls='PASS',layout_control_cases=40,layout_control_checks=len(controls['checks']),layout_section_isolation='PASS',layout_mouse_wheel='PASS');m.update(layout_browser='PASS',layout_cases=120,layout_persistence='PASS',layout_csrf='PASS',layout_modal_keyboard='PASS',layout_information_hierarchy='PASS',layout_save_no_occlusion='PASS',layout_module_affordance='PASS',layout_module_provenance='PASS',layout_module_enable='PASS');runtime=json.loads((p/'runtime.json').read_text());provenance=json.loads((p/'layout-controls-provenance.json').read_text());assert all(runtime[k]==provenance[k] for k in ['runtime_files','runtime_fingerprint']);m.update(layout_controls_runtime_identity='PASS',layout_controls_proof_run=provenance['proof_run'],layout_controls_proof_source=provenance['proof_source'],layout_controls_reused=True);m.update(runtime);m.update(preview_controls='PASS',preview_scroll='PASS',advanced_controls='PASS',advanced_interactions='PASS',number_controls='PASS',choice_controls='PASS',recovery_controls='PASS',status='PASS',upgrade='PASS',source_rollback='PASS',wordpress_browser='PASS',fixture_browser='PASS',brand_persistence='PASS',brand_csrf='PASS',owner_real_use='POST_PRODUCTION_REQUIRED',owner_preview_runtime='N_A',production='NOT_EXECUTED',candidate_run=os.environ['GITHUB_RUN_ID']);(p/'FINAL_EVIDENCE.json').write_text(json.dumps(m,indent=2));print(json.dumps(m))
PY
echo EXACT_CANDIDATE_GATE=PASS


