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
p=Path('src/inc/update/class-vf-wp-update-admin-v1.php')
s=p.read_text()
old="""            $credential = VF_WP_Update_Credential_V1::redacted_status();
            $components = $this->components();"""
new="""            $credential = VF_WP_Update_Credential_V1::redacted_status();
            $credentialConfigured = !empty($credential['configured']);
            $components = $this->components();"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""                $view = $this->normalized_component((string)$componentId, $component);
                $views[] = $view;"""
new="""                $view = $this->normalized_component((string)$componentId, $component);
                if (!$credentialConfigured) {
                    $view['status_summary'] = '先配置更新凭证，再检查或安装此组件的更新。';
                }
                $views[] = $view;"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""            $runtime = VF_Theme_Runtime_Authority_V1::stored();
            $recovery = VF_Theme_Update_Client_V1::recovery();
            $credentialConfigured = !empty($credential['configured']);"""
new="""            $runtime = VF_Theme_Runtime_Authority_V1::stored();
            $recovery = VF_Theme_Update_Client_V1::recovery();"""
assert s.count(old)==1
s=s.replace(old,new,1)
old="""                        <?php if ($credentialConfigured) : ?>
                        <form method=\"post\">
                            <?php wp_nonce_field('vf_private_updates_v1'); ?>
                            <input type=\"hidden\" name=\"vf_update_action\" value=\"check_all_updates\">
                            <?php submit_button('检查全部 VF 更新', 'primary', 'submit', false); ?>
                        </form>
                        <?php else : ?>
                        <a class=\"button button-primary\" href=\"#vf-update-credential-setup\">配置更新凭证</a>
                        <?php endif; ?>
                        <a class=\"button button-secondary\" href=\"<?php echo esc_url(admin_url('update-core.php')); ?>\">打开 WordPress 更新</a>"""
new="""                        <?php if ($credentialConfigured) : ?>
                        <form method=\"post\">
                            <?php wp_nonce_field('vf_private_updates_v1'); ?>
                            <input type=\"hidden\" name=\"vf_update_action\" value=\"check_all_updates\">
                            <?php submit_button('检查全部 VF 更新', 'primary', 'submit', false); ?>
                        </form>
                        <a class=\"button button-secondary\" href=\"<?php echo esc_url(admin_url('update-core.php')); ?>\">打开 WordPress 更新</a>
                        <?php else : ?>
                        <a class=\"button button-primary\" href=\"#vf-update-credential-setup\">配置更新凭证</a>
                        <?php endif; ?>"""
assert s.count(old)==1
s=s.replace(old,new,1)
old='<input id="vf_update_token_initial" type="password" name="vf_update_token" value="" class="regular-text" autocomplete="new-password" spellcheck="false" placeholder="粘贴 VF 私有更新读取凭证">'
new='<input id="vf_update_token_initial" type="password" name="vf_update_token" value="" class="regular-text" autocomplete="new-password" spellcheck="false" placeholder="粘贴 VF 私有更新读取凭证" required>'
assert s.count(old)==1
s=s.replace(old,new,1)
old='<p>先看“是否需要处理”，再决定是否进入 WordPress 标准更新流程。</p>'
new="""<?php if ($credentialConfigured) : ?>
                            <p>先看“是否需要处理”，再决定是否进入 WordPress 标准更新流程。</p>
                            <?php else : ?>
                            <p>先完成上方更新凭证配置；保存后再检查组件状态。</p>
                            <?php endif; ?>"""
assert s.count(old)==1
s=s.replace(old,new,1)
p.write_text(s)

t=Path('tests/update-center-human-language-contract.php')
s=t.read_text()
old="""    \"submit_button('保存更新凭证', 'primary'\",
];"""
new="""    \"submit_button('保存更新凭证', 'primary'\",
    '先配置更新凭证，再检查或安装此组件的更新。',
    '先完成上方更新凭证配置；保存后再检查组件状态。',
    'placeholder=\"粘贴 VF 私有更新读取凭证\" required',
];"""
assert s.count(old)==1
s=s.replace(old,new,1)
insert="""
$credentialPosition = strpos($admin, \"$credentialConfigured = !empty($credential['configured']);\");
$normalizePosition = strpos($admin, '$view = $this->normalized_component');
$missingSummaryPosition = strpos($admin, \"if (!$credentialConfigured) {\");
$wordpressUpdatePosition = strpos($admin, '打开 WordPress 更新');
$heroElsePosition = strpos($admin, '<?php else : ?>', strpos($admin, 'vf-update-center__hero-actions'));
if ($credentialPosition === false || $normalizePosition === false || $missingSummaryPosition === false || $credentialPosition > $normalizePosition || $missingSummaryPosition < $normalizePosition) {
    fwrite(STDERR, \"FAIL_CREDENTIAL_FIRST_STATE_ORDER\\n\");
    exit(1);
}
if ($wordpressUpdatePosition === false || $heroElsePosition === false || $wordpressUpdatePosition > $heroElsePosition) {
    fwrite(STDERR, \"FAIL_WORDPRESS_UPDATE_VISIBLE_WITHOUT_CREDENTIAL\\n\");
    exit(1);
}
"""
marker='echo "PASS_THEME_UPDATE_CENTER_HUMAN_LANGUAGE\\n";'
assert s.count(marker)==1
s=s.replace(marker,insert+'\n'+marker,1)
t.write_text(s)
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
grep -F "\$view['status_summary'] = '先配置更新凭证，再检查或安装此组件的更新。';" src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'placeholder="粘贴 VF 私有更新读取凭证" required' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F '先完成上方更新凭证配置；保存后再检查组件状态。' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
git diff --name-only "$BASE_SHA" | sort >/tmp/actual
printf '%s\n' src/inc/update/class-vf-wp-update-admin-v1.php tests/update-center-human-language-contract.php | sort >/tmp/expected
diff -u /tmp/expected /tmp/actual
git diff --check
git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/inc/update/class-vf-wp-update-admin-v1.php tests/update-center-human-language-contract.php
git commit -m 'refine(S01-C01): keep credential-missing state guidance consistent'
git push -q origin HEAD:"$BRANCH"
echo "THEME_CREDENTIAL_STATE_COPY_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_CREDENTIAL_STATE_COPY_CANDIDATE'
