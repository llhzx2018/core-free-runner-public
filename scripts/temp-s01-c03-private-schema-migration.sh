#!/usr/bin/env bash
set -Eeuo pipefail

: "${EVIDENCE_DIR:?}"
: "${M3U8_SHA:?}"
: "${M3U8_LEGACY_SHA:?}"
: "${WP_VERSION:?}"

test "$(git -C m3u8 rev-parse HEAD)" = "$M3U8_SHA"
test "$(git -C m3u8-legacy rev-parse HEAD)" = "$M3U8_LEGACY_SHA"

MIGRATION_WP_PATH=/tmp/vf-s01-c03-migration-wp
MIGRATION_DB=vf_s01_migration
MIGRATION_URL=http://127.0.0.1:8090
MIGRATION_EVIDENCE="$EVIDENCE_DIR/c03-private-schema-migration"
mkdir -p "$MIGRATION_EVIDENCE" "$MIGRATION_WP_PATH"

mariadb -h127.0.0.1 -P3306 -uroot -proot -e "DROP DATABASE IF EXISTS ${MIGRATION_DB}; CREATE DATABASE ${MIGRATION_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON ${MIGRATION_DB}.* TO 'vf'@'%'; FLUSH PRIVILEGES;"
wp core download --path="$MIGRATION_WP_PATH" --version="$WP_VERSION" --force
wp config create --path="$MIGRATION_WP_PATH" --dbname="$MIGRATION_DB" --dbuser=vf --dbpass=vf --dbhost=127.0.0.1:3306 --skip-check
wp config set WP_DEBUG true --raw --path="$MIGRATION_WP_PATH"
wp config set WP_DEBUG_LOG true --raw --path="$MIGRATION_WP_PATH"
wp config set WP_DEBUG_DISPLAY false --raw --path="$MIGRATION_WP_PATH"
wp core install --path="$MIGRATION_WP_PATH" --url="$MIGRATION_URL" --title='VF S01 C03 Migration Sandbox' --admin_user=owner --admin_password='runner-only-not-production' --admin_email='owner@example.invalid' --skip-email

mkdir -p "$MIGRATION_WP_PATH/wp-content/plugins/vf-tool-m3u8"
rsync -a --delete m3u8-legacy/src/ "$MIGRATION_WP_PATH/wp-content/plugins/vf-tool-m3u8/"
wp plugin activate vf-tool-m3u8 --path="$MIGRATION_WP_PATH" > "$MIGRATION_EVIDENCE/legacy-activation.log" 2>&1
wp eval --path="$MIGRATION_WP_PATH" 'echo json_encode(["version"=>defined("VF_TOOL_M3U8_VERSION")?VF_TOOL_M3U8_VERSION:"","schema"=>function_exists("vf_tools_m3u8_v6_schema_version")?vf_tools_m3u8_v6_schema_version():"","tables"=>function_exists("vf_tools_m3u8_v6_table_names")?vf_tools_m3u8_v6_table_names():[]],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);' > "$MIGRATION_EVIDENCE/legacy-runtime.json"
jq -e '.version=="1.25.3" and .schema=="1.2.0" and ([.tables[]|contains("vf_m3u8_")]|any)==false' "$MIGRATION_EVIDENCE/legacy-runtime.json" >/dev/null

# Add state that cannot be reconstructed by bundled reseed alone, plus a
# foreign Provider family proving migration is row-owner scoped rather than
# whole-table copied.
mariadb -h127.0.0.1 -P3306 -uvf -pvf "$MIGRATION_DB" <<'SQL'
INSERT INTO wp_vf_capabilities (id,uid,semantic_key,provider_key,lifecycle_state,current_revision_id,draft_revision_id,created_at,updated_at)
VALUES (800001,'00000000-0000-7000-8000-000000800001','vf.m3u8.runner_custom','vf.m3u8','ACTIVE',NULL,800001,NOW(),NOW());
INSERT INTO wp_vf_capability_contracts (id,capability_id,revision_no,revision_state,schema_version,definition,content_hash,lock_version,sealed_at,created_at,updated_at)
VALUES (800001,800001,99,'DRAFT','1.0.0','{}',REPEAT('a',64),7,NULL,NOW(),NOW());
INSERT INTO wp_vf_pipelines (id,uid,semantic_key,owner_provider_key,lifecycle_state,current_revision_id,draft_revision_id,created_at,updated_at)
VALUES (800001,'00000000-0000-7000-8000-000000800002','vf.m3u8.runner_pipeline','vf.m3u8','ACTIVE',NULL,800001,NOW(),NOW());
INSERT INTO wp_vf_pipeline_revisions (id,pipeline_id,revision_no,revision_state,schema_version,definition,content_hash,lock_version,sealed_at,created_at,updated_at)
VALUES (800001,800001,99,'DRAFT','1.0.0','{}',REPEAT('b',64),5,NULL,NOW(),NOW());
INSERT INTO wp_vf_pipeline_steps (id,pipeline_revision_id,step_key,capability_semantic_key,capability_revision,capability_hash,definition)
VALUES (800001,800001,'runner-step','vf.m3u8.runner_custom',99,REPEAT('a',64),'{}');
INSERT INTO wp_vf_pipeline_edges (id,pipeline_revision_id,edge_order,from_port,to_port,definition)
VALUES (800001,800001,0,'runner-step.out','runner-step.in','{}');
SET @m3u8_fixture_revision=(SELECT r.id FROM wp_vf_provider_fixture_revisions r INNER JOIN wp_vf_provider_fixtures f ON f.id=r.fixture_id WHERE f.provider_key='vf.m3u8' ORDER BY r.id LIMIT 1);
INSERT INTO wp_vf_provider_fixture_runs (id,run_uid,fixture_revision_id,target_semantic_key,target_revision,target_hash,input_hash,result_state,expected_match,evidence,evidence_hash,started_at,finished_at)
SELECT 800001,'00000000-0000-7000-8000-000000800003',@m3u8_fixture_revision,'vf.m3u8.runner_custom',99,REPEAT('a',64),REPEAT('c',64),'PASS',1,'{}',REPEAT('d',64),NOW(),NOW() WHERE @m3u8_fixture_revision IS NOT NULL;
INSERT INTO wp_vf_runtime_bundles (id,uid,provider_key,bundle_key,version,lifecycle_state,definition,content_hash,created_at,updated_at,sealed_at)
VALUES (800001,'00000000-0000-7000-8000-000000800004','vf.m3u8','vf.m3u8.runner-runtime','9.9.9-runner-draft','DRAFT','{}',REPEAT('e',64),NOW(),NOW(),NULL);
INSERT INTO wp_vf_runtime_bundle_assets (id,runtime_bundle_id,asset_order,path,sha256,bytes,load_phase,self_hosted,definition)
VALUES (800001,800001,0,'runner/state.bin',REPEAT('f',64),123,'OPTIONAL',1,'{}');
INSERT INTO wp_vf_provider_operation_runs (id,run_uid,provider_key,run_kind,subject_key,state,fingerprint,evidence,evidence_hash,started_at,finished_at)
VALUES (800001,'00000000-0000-7000-8000-000000800005','vf.m3u8','RUNNER_HISTORY','vf.m3u8.runner_custom','PASS',REPEAT('1',64),'{}',REPEAT('2',64),NOW(),NOW());
INSERT INTO wp_vf_provider_snapshots (id,snapshot_uid,provider_key,provider_version,protocol_range,schema_version,compatibility_state,manifest,content_hash,created_at)
VALUES (800001,'00000000-0000-7000-8000-000000800006','vf.m3u8','1.25.3','>=1','1.2.0','PASS','{}',REPEAT('3',64),NOW());
INSERT INTO wp_vf_provider_snapshot_items (id,snapshot_id,item_kind,item_key,item_revision,item_hash,payload)
VALUES (800001,800001,'CAPABILITY','vf.m3u8.runner_custom',99,REPEAT('4',64),'{}');

INSERT INTO wp_vf_capabilities (id,uid,semantic_key,provider_key,lifecycle_state,current_revision_id,draft_revision_id,created_at,updated_at)
VALUES (900001,'00000000-0000-7000-8000-000000900001','foreign.capability','foreign.provider','ACTIVE',900001,NULL,NOW(),NOW());
INSERT INTO wp_vf_capability_contracts (id,capability_id,revision_no,revision_state,schema_version,definition,content_hash,lock_version,sealed_at,created_at,updated_at)
VALUES (900001,900001,1,'SEALED','1.0.0','{}',REPEAT('5',64),1,NOW(),NOW(),NOW());
INSERT INTO wp_vf_pipelines (id,uid,semantic_key,owner_provider_key,lifecycle_state,current_revision_id,draft_revision_id,created_at,updated_at)
VALUES (900001,'00000000-0000-7000-8000-000000900002','foreign.pipeline','foreign.provider','ACTIVE',900001,NULL,NOW(),NOW());
INSERT INTO wp_vf_pipeline_revisions (id,pipeline_id,revision_no,revision_state,schema_version,definition,content_hash,lock_version,sealed_at,created_at,updated_at)
VALUES (900001,900001,1,'SEALED','1.0.0','{}',REPEAT('6',64),1,NOW(),NOW(),NOW());
INSERT INTO wp_vf_pipeline_steps (id,pipeline_revision_id,step_key,capability_semantic_key,capability_revision,capability_hash,definition)
VALUES (900001,900001,'foreign-step','foreign.capability',1,REPEAT('5',64),'{}');
INSERT INTO wp_vf_pipeline_edges (id,pipeline_revision_id,edge_order,from_port,to_port,definition)
VALUES (900001,900001,0,'foreign-step.out','foreign-step.in','{}');
INSERT INTO wp_vf_provider_fixtures (id,uid,fixture_key,provider_key,lifecycle_state,current_revision_id,draft_revision_id,created_at,updated_at)
VALUES (900001,'00000000-0000-7000-8000-000000900003','foreign.fixture','foreign.provider','ACTIVE',900001,NULL,NOW(),NOW());
INSERT INTO wp_vf_provider_fixture_revisions (id,fixture_id,revision_no,revision_state,schema_version,definition,content_hash,lock_version,sealed_at,created_at,updated_at)
VALUES (900001,900001,1,'SEALED','1.0.0','{}',REPEAT('7',64),1,NOW(),NOW(),NOW());
INSERT INTO wp_vf_provider_fixture_runs (id,run_uid,fixture_revision_id,target_semantic_key,target_revision,target_hash,input_hash,result_state,expected_match,evidence,evidence_hash,started_at,finished_at)
VALUES (900001,'00000000-0000-7000-8000-000000900004',900001,'foreign.capability',1,REPEAT('5',64),REPEAT('8',64),'PASS',1,'{}',REPEAT('9',64),NOW(),NOW());
INSERT INTO wp_vf_runtime_bundles (id,uid,provider_key,bundle_key,version,lifecycle_state,definition,content_hash,created_at,updated_at,sealed_at)
VALUES (900001,'00000000-0000-7000-8000-000000900005','foreign.provider','foreign.runtime','1.0.0','SEALED','{}',REPEAT('a',64),NOW(),NOW(),NOW());
INSERT INTO wp_vf_runtime_bundle_assets (id,runtime_bundle_id,asset_order,path,sha256,bytes,load_phase,self_hosted,definition)
VALUES (900001,900001,0,'foreign.bin',REPEAT('b',64),1,'OPTIONAL',1,'{}');
INSERT INTO wp_vf_provider_operation_runs (id,run_uid,provider_key,run_kind,subject_key,state,fingerprint,evidence,evidence_hash,started_at,finished_at)
VALUES (900001,'00000000-0000-7000-8000-000000900006','foreign.provider','FOREIGN','foreign','PASS',REPEAT('c',64),'{}',REPEAT('d',64),NOW(),NOW());
INSERT INTO wp_vf_provider_snapshots (id,snapshot_uid,provider_key,provider_version,protocol_range,schema_version,compatibility_state,manifest,content_hash,created_at)
VALUES (900001,'00000000-0000-7000-8000-000000900007','foreign.provider','1.0.0','>=1','1.0.0','PASS','{}',REPEAT('e',64),NOW());
INSERT INTO wp_vf_provider_snapshot_items (id,snapshot_id,item_kind,item_key,item_revision,item_hash,payload)
VALUES (900001,900001,'CAPABILITY','foreign.capability',1,REPEAT('f',64),'{}');
SQL

LEGACY_TABLES="wp_vf_capabilities wp_vf_capability_contracts wp_vf_pipelines wp_vf_pipeline_revisions wp_vf_pipeline_steps wp_vf_pipeline_edges wp_vf_provider_fixtures wp_vf_provider_fixture_revisions wp_vf_provider_fixture_runs wp_vf_runtime_bundles wp_vf_runtime_bundle_assets wp_vf_provider_operation_runs wp_vf_provider_snapshots wp_vf_provider_snapshot_items"
mariadb-dump -h127.0.0.1 -P3306 -uvf -pvf "$MIGRATION_DB" $LEGACY_TABLES --no-create-info --skip-comments --compact --skip-extended-insert > "$MIGRATION_EVIDENCE/legacy-data-before.sql"

wp plugin deactivate vf-tool-m3u8 --path="$MIGRATION_WP_PATH" > "$MIGRATION_EVIDENCE/legacy-deactivation.log" 2>&1
rsync -a --delete m3u8/src/ "$MIGRATION_WP_PATH/wp-content/plugins/vf-tool-m3u8/"
php -l "$MIGRATION_WP_PATH/wp-content/plugins/vf-tool-m3u8/includes/v6-provider-schema.php" > "$MIGRATION_EVIDENCE/schema-php-lint.txt"
wp plugin activate vf-tool-m3u8 --path="$MIGRATION_WP_PATH" > "$MIGRATION_EVIDENCE/recovery-activation.log" 2>&1

wp eval --path="$MIGRATION_WP_PATH" 'echo json_encode(["version"=>VF_TOOL_M3U8_VERSION,"schema"=>vf_tools_m3u8_v6_schema_version(),"storedSchema"=>(string)get_option("vf_tools_m3u8_v6_schema_version",""),"ready"=>vf_tools_m3u8_v6_schema_ready(),"migration"=>get_option(vf_tools_m3u8_v6_private_schema_migration_option(),[]),"sourceCounts"=>vf_tools_m3u8_v6_legacy_owned_row_counts(),"targetCounts"=>vf_tools_m3u8_v6_table_row_counts(vf_tools_m3u8_v6_table_names()),"tables"=>vf_tools_m3u8_v6_table_names()],JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);' > "$MIGRATION_EVIDENCE/recovery-readback.json"
jq -e '.version=="1.25.3" and .schema=="1.3.0" and .storedSchema=="1.3.0" and .ready==true and .migration.status=="PASS" and .migration.sourceMode=="LEGACY_SHARED_PROVIDER_ROWS" and .migration.legacySchemaCompatible==true and .migration.legacyTablesMutated==false and .sourceCounts==.targetCounts and ([.tables[]|contains("vf_m3u8_")]|all)' "$MIGRATION_EVIDENCE/recovery-readback.json" >/dev/null

mariadb-dump -h127.0.0.1 -P3306 -uvf -pvf "$MIGRATION_DB" $LEGACY_TABLES --no-create-info --skip-comments --compact --skip-extended-insert > "$MIGRATION_EVIDENCE/legacy-data-after.sql"
cmp "$MIGRATION_EVIDENCE/legacy-data-before.sql" "$MIGRATION_EVIDENCE/legacy-data-after.sql"

wp eval --path="$MIGRATION_WP_PATH" '$t=vf_tools_m3u8_v6_table_names();global $wpdb;$checks=["customCapability"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["capabilities"]} WHERE semantic_key=\"vf.m3u8.runner_custom\" AND provider_key=\"vf.m3u8\""),"customPipeline"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["pipelines"]} WHERE semantic_key=\"vf.m3u8.runner_pipeline\" AND owner_provider_key=\"vf.m3u8\""),"fixtureRun"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["fixture_runs"]} WHERE run_uid=\"00000000-0000-7000-8000-000000800003\""),"runtimeDraft"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["runtime_bundles"]} WHERE bundle_key=\"vf.m3u8.runner-runtime\" AND lifecycle_state=\"DRAFT\""),"operationHistory"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["operation_runs"]} WHERE run_uid=\"00000000-0000-7000-8000-000000800005\""),"snapshotHistory"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["snapshots"]} WHERE snapshot_uid=\"00000000-0000-7000-8000-000000800006\""),"foreignCapabilities"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["capabilities"]} WHERE provider_key=\"foreign.provider\""),"foreignPipelines"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["pipelines"]} WHERE owner_provider_key=\"foreign.provider\""),"foreignFixtures"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["fixtures"]} WHERE provider_key=\"foreign.provider\""),"foreignRuntime"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["runtime_bundles"]} WHERE provider_key=\"foreign.provider\""),"foreignOperations"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["operation_runs"]} WHERE provider_key=\"foreign.provider\""),"foreignSnapshots"=>(int)$wpdb->get_var("SELECT COUNT(*) FROM {$t["snapshots"]} WHERE provider_key=\"foreign.provider\"")];echo json_encode($checks,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);' > "$MIGRATION_EVIDENCE/ownership-checks.json"
jq -e '.customCapability==1 and .customPipeline==1 and .fixtureRun==1 and .runtimeDraft==1 and .operationHistory==1 and .snapshotHistory==1 and .foreignCapabilities==0 and .foreignPipelines==0 and .foreignFixtures==0 and .foreignRuntime==0 and .foreignOperations==0 and .foreignSnapshots==0' "$MIGRATION_EVIDENCE/ownership-checks.json" >/dev/null

wp eval --path="$MIGRATION_WP_PATH" 'echo json_encode(vf_tools_m3u8_v6_table_row_counts(vf_tools_m3u8_v6_table_names()),JSON_PRETTY_PRINT);' > "$MIGRATION_EVIDENCE/private-counts-before-repeat.json"
wp eval --path="$MIGRATION_WP_PATH" 'echo json_encode(get_option(vf_tools_m3u8_v6_private_schema_migration_option(),[]),JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);' > "$MIGRATION_EVIDENCE/migration-marker-before-repeat.json"
wp eval --path="$MIGRATION_WP_PATH" 'if(!vf_tools_m3u8_v6_schema_install()){fwrite(STDERR,"REPEAT_SCHEMA_INSTALL_FAILED\n");exit(2);}echo "REPEAT_SCHEMA_INSTALL=PASS\n";' > "$MIGRATION_EVIDENCE/repeat-install.txt"
wp eval --path="$MIGRATION_WP_PATH" 'echo json_encode(vf_tools_m3u8_v6_table_row_counts(vf_tools_m3u8_v6_table_names()),JSON_PRETTY_PRINT);' > "$MIGRATION_EVIDENCE/private-counts-after-repeat.json"
wp eval --path="$MIGRATION_WP_PATH" 'echo json_encode(get_option(vf_tools_m3u8_v6_private_schema_migration_option(),[]),JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES);' > "$MIGRATION_EVIDENCE/migration-marker-after-repeat.json"
cmp "$MIGRATION_EVIDENCE/private-counts-before-repeat.json" "$MIGRATION_EVIDENCE/private-counts-after-repeat.json"
cmp "$MIGRATION_EVIDENCE/migration-marker-before-repeat.json" "$MIGRATION_EVIDENCE/migration-marker-after-repeat.json"

cat > "$MIGRATION_EVIDENCE/RESULT.txt" <<EOF
C03_PRIVATE_SCHEMA_MIGRATION=PASS
LEGACY_SHA=$M3U8_LEGACY_SHA
RECOVERY_SHA=$M3U8_SHA
SCHEMA=1.2.0_TO_1.3.0
LEGACY_M3U8_STATE=PRESERVED
LEGACY_SHARED_TABLES=MUTATED_0
FOREIGN_PROVIDER_ROWS_MIGRATED=0
CUSTOM_DRAFTS=PRESERVED
FIXTURE_RUN_HISTORY=PRESERVED
OPERATION_HISTORY=PRESERVED
SNAPSHOT_HISTORY=PRESERVED
REPEAT_INSTALL=IDEMPOTENT_PASS
EOF
