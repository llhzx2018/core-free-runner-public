#!/usr/bin/env bash
set -Eeuo pipefail
: "${READ_TOKEN:?}" "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"
echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO MIGRATION_USED=NO'
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" repo
cd repo
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test "$(git rev-parse origin/main)" = "$BASE_SHA"
python3 - <<'PY'
from pathlib import Path
admin=Path('src/inc/update/class-vf-wp-update-admin-v1.php')
s=admin.read_text()
old='''                    <div class="vf-update-center__hero-actions">
                        <form method="post">
                            <?php wp_nonce_field('vf_private_updates_v1'); ?>
                            <input type="hidden" name="vf_update_action" value="check_all_updates">
                            <?php submit_button('检查全部 VF 更新', 'primary', 'submit', false); ?>
                        </form>
                        <a class="button button-secondary" href="<?php echo esc_url(admin_url('update-core.php')); ?>">打开 WordPress 更新</a>
                    </div>'''
new='''                    <div class="vf-update-center__hero-actions">
                        <?php if ($credentialConfigured) : ?>
                        <form method="post">
                            <?php wp_nonce_field('vf_private_updates_v1'); ?>
                            <input type="hidden" name="vf_update_action" value="check_all_updates">
                            <?php submit_button('检查全部 VF 更新', 'primary', 'submit', false); ?>
                        </form>
                        <?php else : ?>
                        <a class="button button-primary" href="#vf-update-credential-setup">配置更新凭证</a>
                        <?php endif; ?>
                        <a class="button button-secondary" href="<?php echo esc_url(admin_url('update-core.php')); ?>">打开 WordPress 更新</a>
                    </div>'''
assert s.count(old)==1
s=s.replace(old,new,1)
marker='''                </div>

                <section class="vf-update-center__section" aria-labelledby="vf-update-components-title">'''
insertion='''                </div>

                <?php if (!$credentialConfigured) : ?>
                <section id="vf-update-credential-setup" class="vf-update-center__section vf-update-center__credential-setup" aria-labelledby="vf-update-credential-setup-title">
                    <div class="vf-update-center__section-heading">
                        <h2 id="vf-update-credential-setup-title">先配置更新凭证</h2>
                        <p>VF 在线更新使用私有发布源。保存凭证后，再检查组件更新。</p>
                    </div>
                    <form method="post" autocomplete="off" class="vf-update-center__credential-form">
                        <?php wp_nonce_field('vf_private_updates_v1'); ?>
                        <input type="hidden" name="vf_update_action" value="save_token">
                        <label for="vf_update_token_initial"><strong>更新凭证</strong></label>
                        <input id="vf_update_token_initial" type="password" name="vf_update_token" value="" class="regular-text" autocomplete="new-password" spellcheck="false" placeholder="粘贴 VF 私有更新读取凭证">
                        <p class="description">凭证保存后不会在页面中回显；这里只显示是否已配置。</p>
                        <?php submit_button('保存更新凭证', 'primary', 'submit', false); ?>
                    </form>
                </section>
                <?php endif; ?>

                <section class="vf-update-center__section" aria-labelledby="vf-update-components-title">'''
assert s.count(marker)==1
s=s.replace(marker,insertion,1)
admin.write_text(s)
css=Path('src/assets/css/admin/admin-update-center.css')
s=css.read_text()
marker='.vf-update-center__section-heading p { margin: 0; color: var(--vf-muted); }\n\n'
addition='''.vf-update-center__section-heading p { margin: 0; color: var(--vf-muted); }

.vf-update-center__credential-setup {
    scroll-margin-top: 48px;
    padding: 18px;
    border: 1px solid #dba617;
    border-left: 4px solid #dba617;
    border-radius: 12px;
    background: #fffaf0;
    box-sizing: border-box;
}

'''
assert s.count(marker)==1
s=s.replace(marker,addition,1)
css.write_text(s)
test=Path('tests/update-center-human-language-contract.php')
s=test.read_text()
old="    '组件技术状态',\n];"
new="    '组件技术状态',\n    '先配置更新凭证',\n    'VF 在线更新使用私有发布源。保存凭证后，再检查组件更新。',\n    'href=\"#vf-update-credential-setup\"',\n    \"submit_button('保存更新凭证', 'primary'\",\n];"
assert s.count(old)==1
s=s.replace(old,new,1)
internal="    \"'check_all_updates'\",\n"
assert s.count(internal)==1
s=s.replace(internal,internal+"    'if ($credentialConfigured)',\n    'if (!$credentialConfigured)',\n",1)
test.write_text(s)
PY
php -l src/inc/update/class-vf-wp-update-admin-v1.php
php -l tests/update-center-human-language-contract.php
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
php tests/workbench-primary-action-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php
grep -F 'if ($credentialConfigured)' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'href="#vf-update-credential-setup"' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'id="vf-update-credential-setup"' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F "submit_button('保存更新凭证', 'primary'" src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F "return new WP_Error('vf_private_update_token_missing'" src/inc/update/class-vf-theme-update-source-v1.php >/dev/null
git diff --name-only "$BASE_SHA" | sort >/tmp/actual
printf '%s\n' src/assets/css/admin/admin-update-center.css src/inc/update/class-vf-wp-update-admin-v1.php tests/update-center-human-language-contract.php | sort >/tmp/expected
diff -u /tmp/expected /tmp/actual
git diff --check
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/assets/css/admin/admin-update-center.css src/inc/update/class-vf-wp-update-admin-v1.php tests/update-center-human-language-contract.php
git commit -m 'refine(S01-C01): make missing credentials the primary update action'
git push -q origin HEAD:"$BRANCH"
echo "THEME_CREDENTIAL_FIRST_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_CREDENTIAL_FIRST_CANDIDATE'
