#!/usr/bin/env bash
set -Eeuo pipefail
: "${WRITE_TOKEN:?}" "${REPO:?}" "${BRANCH:?}" "${BASE_SHA:?}"

echo 'MAIN_WRITE_USED=NO RELEASE_USED=NO DISTRIBUTION_USED=NO PRODUCTION_WRITE_USED=NO STATIC_WRITE_USED=NO ONLINE_WRITE_USED=NO'
rm -rf repo
git clone -q "https://x-access-token:${WRITE_TOKEN}@github.com/${REPO}.git" repo
cd repo
git checkout -q "$BRANCH"
test "$(git rev-parse HEAD)" = "$BASE_SHA"
test "$(git rev-parse origin/main)" = "$BASE_SHA"

python3 - <<'PY'
from pathlib import Path
p = Path('src/inc/update/class-vf-wp-update-admin-v1.php')
s = p.read_text()

old = """            $credential = VF_WP_Update_Credential_V1::redacted_status();
            $components = $this->components();"""
new = """            $credential = VF_WP_Update_Credential_V1::redacted_status();
            $credentialConfigured = !empty($credential['configured']);
            $components = $this->components();"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """                $view = $this->normalized_component((string)$componentId, $component);
                $views[] = $view;"""
new = """                $view = $this->normalized_component((string)$componentId, $component);
                if (!$credentialConfigured) {
                    $view['status_summary'] = '先配置更新凭证，再检查或安装此组件的更新。';
                }
                $views[] = $view;"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """            $runtime = VF_Theme_Runtime_Authority_V1::stored();
            $recovery = VF_Theme_Update_Client_V1::recovery();
            $credentialConfigured = !empty($credential['configured']);"""
new = """            $runtime = VF_Theme_Runtime_Authority_V1::stored();
            $recovery = VF_Theme_Update_Client_V1::recovery();
            if (!$credentialConfigured) {
                $overallState = 'setup';
                $overallLabel = '需要先配置';
            } elseif ($summary['attention'] > 0) {
                $overallState = 'attention';
                $overallLabel = '有项目需要处理';
            } elseif ($summary['available'] > 0) {
                $overallState = 'available';
                $overallLabel = '发现可用更新';
            } elseif ($summary['unchecked'] > 0) {
                $overallState = 'unchecked';
                $overallLabel = '等待检查';
            } else {
                $overallState = 'current';
                $overallLabel = '状态正常';
            }"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """                <div class=\"vf-update-center__hero\">
                    <div>
                        <p class=\"vf-update-center__eyebrow\">VF TOOLS · 在线更新</p>
                        <h1>VF 在线更新</h1>
                        <p class=\"vf-update-center__lead\">一个入口管理全部 VF 组件。每个组件仍独立发布、独立验证，也能独立恢复。</p>
                    </div>
                    <div class=\"vf-update-center__hero-actions\">
                        <?php if ($credentialConfigured) : ?>
                        <form method=\"post\">
                            <?php wp_nonce_field('vf_private_updates_v1'); ?>
                            <input type=\"hidden\" name=\"vf_update_action\" value=\"check_all_updates\">
                            <?php submit_button('检查全部 VF 更新', 'primary', 'submit', false); ?>
                        </form>
                        <?php else : ?>
                        <a class=\"button button-primary\" href=\"#vf-update-credential-setup\">配置更新凭证</a>
                        <?php endif; ?>
                        <a class=\"button button-secondary\" href=\"<?php echo esc_url(admin_url('update-core.php')); ?>\">打开 WordPress 更新</a>
                    </div>
                </div>"""
new = """                <header class=\"vf-update-center__hero\">
                    <div class=\"vf-update-center__hero-copy\">
                        <div class=\"vf-update-center__eyebrow-row\">
                            <p class=\"vf-update-center__eyebrow\">VF TOOLS · 在线更新</p>
                            <span class=\"vf-update-center__overall vf-update-center__overall--<?php echo esc_attr($overallState); ?>\"><?php echo esc_html($overallLabel); ?></span>
                        </div>
                        <h1>VF 在线更新</h1>
                        <p class=\"vf-update-center__lead\">一个入口查看、检查和更新全部 VF 组件。发布、验证与恢复仍保持独立。</p>
                    </div>
                    <div class=\"vf-update-center__hero-actions\">
                        <?php if ($credentialConfigured) : ?>
                        <form method=\"post\">
                            <?php wp_nonce_field('vf_private_updates_v1'); ?>
                            <input type=\"hidden\" name=\"vf_update_action\" value=\"check_all_updates\">
                            <?php submit_button('检查全部 VF 更新', 'primary', 'submit', false); ?>
                        </form>
                        <a class=\"button button-secondary\" href=\"<?php echo esc_url(admin_url('update-core.php')); ?>\">WordPress 更新</a>
                        <?php else : ?>
                        <a class=\"button button-primary\" href=\"#vf-update-credential-setup\">配置更新凭证</a>
                        <?php endif; ?>
                    </div>
                </header>"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = '<input id="vf_update_token_initial" type="password" name="vf_update_token" value="" class="regular-text" autocomplete="new-password" spellcheck="false" placeholder="粘贴 VF 私有更新读取凭证">'
new = '<input id="vf_update_token_initial" type="password" name="vf_update_token" value="" class="regular-text" autocomplete="new-password" spellcheck="false" placeholder="粘贴 VF 私有更新读取凭证" required>'
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """                    <div class=\"vf-update-center__section-heading\">
                        <h2 id=\"vf-update-credential-setup-title\">先配置更新凭证</h2>
                        <p>VF 在线更新使用私有发布源。保存凭证后，再检查组件更新。</p>
                    </div>"""
new = """                    <div class=\"vf-update-center__section-heading\">
                        <span class=\"vf-update-center__step\">步骤 1</span>
                        <div>
                            <h2 id=\"vf-update-credential-setup-title\">先配置更新凭证</h2>
                            <p>VF 在线更新使用私有发布源。凭证只需配置一次，保存后即可检查全部组件。</p>
                        </div>
                    </div>"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """                    <div class=\"vf-update-center__section-heading\">
                        <div>
                            <h2 id=\"vf-update-components-title\">组件更新</h2>
                            <p>先看“是否需要处理”，再决定是否进入 WordPress 标准更新流程。</p>
                        </div>
                    </div>"""
new = """                    <div class=\"vf-update-center__section-heading\">
                        <span class=\"vf-update-center__step\"><?php echo $credentialConfigured ? '组件状态' : '步骤 2'; ?></span>
                        <div>
                            <h2 id=\"vf-update-components-title\">组件更新</h2>
                            <?php if ($credentialConfigured) : ?>
                            <p>这里只展示需要你判断的状态；真正安装仍走 WordPress 标准更新流程。</p>
                            <?php else : ?>
                            <p>先完成上方凭证配置；保存后再检查组件状态。</p>
                            <?php endif; ?>
                        </div>
                    </div>"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """                            <article id=\"component-<?php echo esc_attr($view['id']); ?>\" class=\"vf-update-component vf-update-component--<?php echo esc_attr($view['status_key']); ?>\">"""
new = """                            <article id=\"component-<?php echo esc_attr($view['id']); ?>\" class=\"vf-update-component vf-update-component--<?php echo esc_attr($view['status_key']); ?><?php echo $credentialConfigured ? '' : ' vf-update-component--locked'; ?>\"<?php echo $credentialConfigured ? '' : ' aria-disabled=\"true\"'; ?>>"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

p.write_text(s)

t = Path('tests/update-center-human-language-contract.php')
s = t.read_text()
old = "$admin = (string) file_get_contents($root . '/src/inc/update/class-vf-wp-update-admin-v1.php');"
new = "$admin = (string) file_get_contents($root . '/src/inc/update/class-vf-wp-update-admin-v1.php');\n$css = (string) file_get_contents($root . '/src/assets/css/admin/admin-update-center.css');"
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = """    \"submit_button('保存更新凭证', 'primary'\",
];"""
new = """    \"submit_button('保存更新凭证', 'primary'\",
    '先配置更新凭证，再检查或安装此组件的更新。',
    '先完成上方凭证配置；保存后再检查组件状态。',
    'vf-update-center__overall--',
    'vf-update-component--locked',
    'placeholder=\"粘贴 VF 私有更新读取凭证\" required',
];"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

insert = r'''
$credentialPosition = strpos($admin, "$credentialConfigured = !empty($credential['configured']);");
$normalizePosition = strpos($admin, '$view = $this->normalized_component');
$wordpressUpdatePosition = strpos($admin, '>WordPress 更新</a>');
$heroElsePosition = strpos($admin, '<?php else : ?>', strpos($admin, 'vf-update-center__hero-actions'));
if ($credentialPosition === false || $normalizePosition === false || $credentialPosition > $normalizePosition) {
    fwrite(STDERR, "FAIL_CREDENTIAL_STATE_ORDER\n");
    exit(1);
}
if ($wordpressUpdatePosition === false || $heroElsePosition === false || $wordpressUpdatePosition > $heroElsePosition) {
    fwrite(STDERR, "FAIL_WORDPRESS_UPDATE_VISIBLE_WITHOUT_CREDENTIAL\n");
    exit(1);
}
$cssContracts = [
    '.vf-update-center__hero {',
    'border-radius: 20px;',
    '.vf-update-center__overall',
    '.vf-update-summary-card',
    '.vf-update-component--locked',
    '.vf-update-center__step',
    '@media (max-width: 600px)',
];
foreach ($cssContracts as $token) {
    if (!str_contains($css, $token)) {
        fwrite(STDERR, "FAIL_V4_VISUAL_CONTRACT: {$token}\n");
        exit(1);
    }
}
'''
marker = 'echo "PASS_THEME_UPDATE_CENTER_HUMAN_LANGUAGE\\n";'
assert s.count(marker) == 1
s = s.replace(marker, insert + "\n" + marker, 1)
t.write_text(s)
PY

cat > src/assets/css/admin/admin-update-center.css <<'CSS'
.vf-update-center {
    --vf-bg: #f5f7fa;
    --vf-border: #dce3ea;
    --vf-border-strong: #c7d3df;
    --vf-surface: #ffffff;
    --vf-surface-soft: #f7f9fb;
    --vf-text: #17212b;
    --vf-muted: #66727f;
    --vf-accent: #1769aa;
    --vf-accent-dark: #0f568e;
    --vf-accent-soft: #eaf4fc;
    --vf-success: #12833f;
    --vf-success-soft: #e8f6ed;
    --vf-warning: #956300;
    --vf-warning-soft: #fff4d6;
    --vf-danger: #b3262e;
    --vf-danger-soft: #fdecee;
    max-width: 1180px;
    padding-bottom: 36px;
}

.vf-update-center,
.vf-update-center * { box-sizing: border-box; }

.vf-update-center h1,
.vf-update-center h2,
.vf-update-center h3 { color: var(--vf-text); }

.vf-update-center__hero {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 32px;
    margin-top: 22px;
    padding: 30px 32px;
    border: 1px solid #cfe0ee;
    border-radius: 20px;
    background: linear-gradient(135deg, #f3f9fe 0%, #ffffff 62%);
    box-shadow: 0 12px 34px rgba(24, 52, 76, .07);
}

.vf-update-center__hero-copy { min-width: 0; }
.vf-update-center__eyebrow-row { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }

.vf-update-center__eyebrow {
    margin: 0;
    color: var(--vf-accent-dark);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .12em;
}

.vf-update-center__overall {
    display: inline-flex;
    align-items: center;
    min-height: 26px;
    padding: 3px 9px;
    border-radius: 999px;
    background: #edf1f5;
    color: #53606d;
    font-size: 12px;
    font-weight: 700;
}

.vf-update-center__overall--setup,
.vf-update-center__overall--attention { background: var(--vf-danger-soft); color: var(--vf-danger); }
.vf-update-center__overall--available { background: var(--vf-warning-soft); color: var(--vf-warning); }
.vf-update-center__overall--current { background: var(--vf-success-soft); color: var(--vf-success); }
.vf-update-center__overall--unchecked { background: var(--vf-accent-soft); color: var(--vf-accent-dark); }

.vf-update-center__hero h1 {
    margin: 9px 0 8px;
    font-size: 31px;
    line-height: 1.15;
    letter-spacing: -.02em;
}

.vf-update-center__lead {
    max-width: 690px;
    margin: 0;
    color: var(--vf-muted);
    font-size: 14px;
    line-height: 1.7;
}

.vf-update-center__hero-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 9px;
    flex: 0 0 auto;
}

.vf-update-center__hero-actions form,
.vf-update-center__hero-actions .submit { margin: 0; padding: 0; }
.vf-update-center__hero-actions .button {
    min-height: 42px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0 16px;
    border-radius: 8px;
    font-weight: 600;
}
.vf-update-center__hero-actions .button-primary {
    border-color: var(--vf-accent);
    background: var(--vf-accent);
}
.vf-update-center__hero-actions .button-primary:hover,
.vf-update-center__hero-actions .button-primary:focus {
    border-color: var(--vf-accent-dark);
    background: var(--vf-accent-dark);
}

.vf-update-center > .notice { margin: 16px 0 0; }

.vf-update-center__summary {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin: 18px 0 30px;
}

.vf-update-summary-card {
    min-height: 94px;
    padding: 17px 19px;
    border: 1px solid var(--vf-border);
    border-radius: 14px;
    background: var(--vf-surface);
    box-shadow: 0 5px 18px rgba(26, 43, 58, .045);
}
.vf-update-summary-card span {
    display: block;
    margin-bottom: 9px;
    color: var(--vf-muted);
    font-size: 12px;
    font-weight: 600;
}
.vf-update-summary-card strong {
    display: block;
    font-size: 26px;
    line-height: 1;
    letter-spacing: -.02em;
}
.vf-update-summary-card--available strong { color: var(--vf-warning); }
.vf-update-summary-card--attention strong { color: var(--vf-danger); }
.vf-update-summary-card strong.vf-update-summary-card__text { font-size: 17px; line-height: 1.35; }

.vf-update-center__section { margin: 0 0 30px; }
.vf-update-center__section-heading {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 14px;
}
.vf-update-center__section-heading h2 { margin: 0 0 5px; font-size: 20px; line-height: 1.3; }
.vf-update-center__section-heading p { margin: 0; color: var(--vf-muted); line-height: 1.6; }
.vf-update-center__step {
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    min-height: 26px;
    padding: 3px 9px;
    border-radius: 999px;
    background: var(--vf-accent-soft);
    color: var(--vf-accent-dark);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .03em;
}

.vf-update-center__credential-setup {
    scroll-margin-top: 48px;
    padding: 22px;
    border: 1px solid #b9d5e9;
    border-left: 5px solid var(--vf-accent);
    border-radius: 16px;
    background: #f8fcff;
    box-shadow: 0 6px 20px rgba(23, 105, 170, .06);
}

.vf-update-components {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
    gap: 14px;
}

.vf-update-component {
    position: relative;
    min-height: 250px;
    padding: 20px;
    border: 1px solid var(--vf-border);
    border-radius: 16px;
    background: var(--vf-surface);
    box-shadow: 0 5px 20px rgba(26, 43, 58, .05);
    scroll-margin-top: 48px;
    overflow: hidden;
}
.vf-update-component::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: #b9c2cb;
}
.vf-update-component--available::before { background: #d69a13; }
.vf-update-component--attention::before { background: var(--vf-danger); }
.vf-update-component--current::before { background: var(--vf-success); }
.vf-update-component--unchecked::before { background: var(--vf-accent); }
.vf-update-component--locked { background: #fbfcfd; }
.vf-update-component--locked::after {
    content: "待配置";
    position: absolute;
    right: 16px;
    bottom: 16px;
    color: #8a949e;
    font-size: 11px;
    font-weight: 700;
}

.vf-update-component__topline,
.vf-update-component__title-row,
.vf-update-component__footer,
.vf-update-component__versions { display: flex; align-items: center; }
.vf-update-component__topline { justify-content: flex-start; margin-bottom: 11px; }
.vf-update-component__type {
    padding: 4px 8px;
    border-radius: 999px;
    background: var(--vf-surface-soft);
    color: var(--vf-muted);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .04em;
}
.vf-update-component__title-row { justify-content: space-between; gap: 14px; }
.vf-update-component__title-row h3 { margin: 0; font-size: 18px; line-height: 1.35; }
.vf-update-status {
    flex: 0 0 auto;
    padding: 5px 9px;
    border-radius: 999px;
    background: #eef1f4;
    color: #53606d;
    font-size: 12px;
    font-weight: 800;
}
.vf-update-status--available { background: var(--vf-warning-soft); color: var(--vf-warning); }
.vf-update-status--attention { background: var(--vf-danger-soft); color: var(--vf-danger); }
.vf-update-status--current { background: var(--vf-success-soft); color: var(--vf-success); }
.vf-update-status--unchecked { background: var(--vf-accent-soft); color: var(--vf-accent-dark); }
.vf-update-component__summary {
    min-height: 44px;
    margin: 11px 0 17px;
    color: var(--vf-muted);
    line-height: 1.6;
}
.vf-update-component__versions {
    justify-content: space-between;
    gap: 12px;
    padding: 13px 14px;
    border: 1px solid #edf0f3;
    border-radius: 11px;
    background: var(--vf-surface-soft);
}
.vf-update-component__versions > div { min-width: 0; }
.vf-update-component__versions span { display: block; color: var(--vf-muted); font-size: 11px; font-weight: 600; }
.vf-update-component__versions strong { display: block; margin-top: 3px; font-size: 15px; overflow-wrap: anywhere; }
.vf-update-component__arrow { color: #9aa4ae; font-size: 17px; }
.vf-update-component__footer {
    justify-content: flex-start;
    gap: 12px;
    margin-top: 15px;
    padding-top: 14px;
    border-top: 1px solid #edf0f3;
}
.vf-update-component__footer .button {
    min-height: 36px;
    display: inline-flex;
    align-items: center;
    border-radius: 7px;
}

.vf-update-center__panel {
    margin: 12px 0;
    border: 1px solid var(--vf-border);
    border-radius: 13px;
    background: var(--vf-surface);
    overflow: hidden;
}
.vf-update-center__panel > summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 16px 18px;
    cursor: pointer;
    list-style: none;
}
.vf-update-center__panel > summary::-webkit-details-marker { display: none; }
.vf-update-center__panel > summary::after { content: "+"; color: var(--vf-muted); font-size: 20px; line-height: 1; }
.vf-update-center__panel[open] > summary::after { content: "−"; }
.vf-update-center__panel > summary span:first-child { display: flex; flex-direction: column; gap: 3px; }
.vf-update-center__panel > summary small { color: var(--vf-muted); font-weight: 400; }
.vf-update-center__panel-state { margin-left: auto; color: var(--vf-muted); font-size: 12px; }
.vf-update-center__panel-body { padding: 4px 18px 18px; border-top: 1px solid #edf0f3; }
.vf-update-center__panel-body > p { color: var(--vf-muted); line-height: 1.6; }
.vf-update-center__facts {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin: 14px 0 18px;
}
.vf-update-center__facts > div { padding: 12px; border-radius: 9px; background: var(--vf-surface-soft); }
.vf-update-center__facts dt { margin-bottom: 4px; color: var(--vf-muted); font-size: 11px; }
.vf-update-center__facts dd { margin: 0; font-weight: 600; overflow-wrap: anywhere; }

.vf-update-center__credential-form {
    display: grid;
    grid-template-columns: minmax(220px, 430px) auto;
    align-items: end;
    gap: 9px 10px;
    max-width: 780px;
}
.vf-update-center__credential-form label,
.vf-update-center__credential-form .description { grid-column: 1 / -1; }
.vf-update-center__credential-form .submit { margin: 0; padding: 0; }
.vf-update-center__credential-form input[type="password"] {
    width: 100%;
    min-height: 42px;
    border-radius: 7px;
}
.vf-update-center__credential-form .button { min-height: 42px; border-radius: 7px; }
.vf-update-center__danger-action { margin-top: 12px; }
.vf-update-center__danger-action .submit { margin: 0; padding: 0; }
.vf-update-center .notice.inline { margin: 0; }

@media (max-width: 960px) {
    .vf-update-center__summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .vf-update-center__hero { align-items: flex-start; flex-direction: column; }
    .vf-update-center__hero-actions { justify-content: flex-start; }
}

@media (max-width: 600px) {
    .vf-update-center { margin-right: 10px; }
    .vf-update-center__hero { margin-top: 14px; padding: 22px 18px; border-radius: 16px; }
    .vf-update-center__hero h1 { font-size: 27px; }
    .vf-update-center__hero-actions { width: 100%; }
    .vf-update-center__hero-actions form,
    .vf-update-center__hero-actions .button { width: 100%; }
    .vf-update-center__hero-actions .submit { width: 100%; }
    .vf-update-center__hero-actions .submit .button { width: 100%; }
    .vf-update-center__summary { grid-template-columns: 1fr 1fr; gap: 8px; }
    .vf-update-summary-card { min-height: 78px; padding: 14px; }
    .vf-update-center__section-heading { flex-direction: column; gap: 8px; }
    .vf-update-center__credential-setup { padding: 18px; }
    .vf-update-components { grid-template-columns: 1fr; }
    .vf-update-component { min-height: 0; padding: 18px; }
    .vf-update-component__title-row { align-items: flex-start; }
    .vf-update-component__footer { align-items: flex-start; flex-direction: column; }
    .vf-update-component__footer .button { width: 100%; justify-content: center; }
    .vf-update-center__facts { grid-template-columns: 1fr; }
    .vf-update-center__credential-form { grid-template-columns: 1fr; }
    .vf-update-center__credential-form .button { width: 100%; }
}
CSS

php -l src/inc/update/class-vf-wp-update-admin-v1.php
php -l tests/update-center-human-language-contract.php
find src -type f -name '*.php' -print0 | xargs -0 -n1 php -l >/dev/null
php tests/update-center-human-language-contract.php
php tests/update-refresh-policy-contract.php
php tests/visible-console-v2-contract.php
php tests/workbench-primary-action-contract.php
php tests/final-admin-human-closure-contract.php
php tests/deep-admin-human-language-contract.php

grep -F "vf-update-center__overall--<?php echo esc_attr(\$overallState); ?>" src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F "\$view['status_summary'] = '先配置更新凭证，再检查或安装此组件的更新。';" src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F 'placeholder="粘贴 VF 私有更新读取凭证" required' src/inc/update/class-vf-wp-update-admin-v1.php >/dev/null
grep -F '.vf-update-component--locked' src/assets/css/admin/admin-update-center.css >/dev/null

git diff --name-only "$BASE_SHA" | sort >/tmp/actual
printf '%s\n' \
  src/inc/update/class-vf-wp-update-admin-v1.php \
  src/assets/css/admin/admin-update-center.css \
  tests/update-center-human-language-contract.php | sort >/tmp/expected
diff -u /tmp/expected /tmp/actual
git diff --check

git config user.name VictorForge
git config user.email llhzx2018@gmail.com
git add src/inc/update/class-vf-wp-update-admin-v1.php src/assets/css/admin/admin-update-center.css tests/update-center-human-language-contract.php
git commit -m 'refine(S01-C01): rebuild update center page hierarchy and visual system'
git push -q origin HEAD:"$BRANCH"
echo "THEME_UPDATE_CENTER_V4_HEAD=$(git rev-parse HEAD)"
echo 'PASS_S01_C01_UPDATE_CENTER_V4_CANDIDATE'
