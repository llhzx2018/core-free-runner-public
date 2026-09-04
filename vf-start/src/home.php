<?php
declare(strict_types=1);
require_once __DIR__ . '/app/FunctionalHome.php';
require_once __DIR__ . '/app/HomeProjectAttention.php';

// Home keeps the canonical FunctionalHome renderer. Buffer only to attach
// shared action-layer capabilities (Quick Open, direct Inbox focus, and the
// deduplicated Projects attention signal); no second Home shell or duplicate
// search/health implementation.
ob_start();
vf_render_home_workspace();
$html = ob_get_clean();
if (!is_string($html) || $html === '') exit;

$quickOpenStyle = '<link rel="stylesheet" href="' . vf_fw_h(vf_asset_url('assets/quick-open.css')) . '">';
$quickOpenScript = '<script src="' . vf_fw_h(vf_asset_url('assets/quick-open.js')) . '" defer></script>';
if (str_contains($html, '</head>')) $html = str_replace('</head>', $quickOpenStyle . '</head>', $html);
if (str_contains($html, '</body>')) $html = str_replace('</body>', $quickOpenScript . '</body>', $html);

// Give the existing Home mobile search the same hook used by shared Quick Open.
$html = str_replace(
    '<form action="surfaces.php" method="get"><span aria-hidden="true">⌕</span><input type="search" name="q"',
    '<form class="vf-mobile-command-search" action="surfaces.php" method="get"><span aria-hidden="true">⌕</span><input type="search" name="q"',
    $html
);

// Home is an action surface: when Inbox has work, enter the continuous processor
// directly instead of making the Owner choose the same action a second time.
$html = str_replace(
    'class="vf-home-attention-item" href="surface-manager.php"',
    'class="vf-home-attention-item" href="surface-manager.php?mode=focus"',
    $html
);

// Projects already has its own explainable signal layer. Home promotes only the
// project-specific problems that are NOT already represented by the global
// Link Health card, so the action center stays concise and non-duplicative.
$projectAttention = ['count'=>0,'detail'=>''];
try { $projectAttention = VfHomeProjectAttention::read(vf_db()); } catch (Throwable $ignored) {}
$projectAttentionCount = max(0, (int)($projectAttention['count'] ?? 0));
if ($projectAttentionCount > 0) {
    $projectDetail = trim((string)($projectAttention['detail'] ?? ''));
    if ($projectDetail === '') $projectDetail = '项目存在需要处理的入口问题';
    $projectCard = '<a class="vf-home-attention-item warning" href="projects.php">'
        . '<span class="vf-home-attention-copy"><b>项目</b><small>' . vf_fw_h($projectDetail) . '</small></span>'
        . '<strong>' . number_format($projectAttentionCount) . '</strong><i>处理 →</i></a>';

    $listMarker = '<div class="vf-home-attention-list">';
    $listPos = strpos($html, $listMarker);
    if ($listPos !== false) {
        $insertPos = $listPos + strlen($listMarker);
        $html = substr_replace($html, $projectCard, $insertPos, 0);
    } else {
        // If Projects is the only current action, canonical Home rendered its
        // calm state. Replace only the opening marker, keep the original calm
        // content hidden, and reuse the same attention-list presentation.
        $calmMarker = '<div class="vf-home-calm">';
        $calmPos = strpos($html, $calmMarker);
        if ($calmPos !== false) {
            $replacement = '<div class="vf-home-attention-list">' . $projectCard . '</div><div class="vf-home-calm" hidden>';
            $html = substr_replace($html, $replacement, $calmPos, strlen($calmMarker));
        }
    }
}

echo $html;
