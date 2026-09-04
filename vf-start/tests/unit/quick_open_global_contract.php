<?php
declare(strict_types=1);

$root = dirname(__DIR__, 2);
$quickOpen = (string)file_get_contents($root . '/src/assets/quick-open.js');
$home = (string)file_get_contents($root . '/src/home.php');
$workspace = (string)file_get_contents($root . '/src/app/FunctionalWorkspace.php');

foreach (['event.metaKey||event.ctrlKey', "toLowerCase()!=='k'", 'event.preventDefault()', 'input.focus()', 'input.select()'] as $needle) {
    if (strpos($quickOpen, $needle) === false) throw new RuntimeException('Global Quick Open shortcut contract missing: ' . $needle);
}
if (strpos($quickOpen, 'input.offsetParent!==null') === false) throw new RuntimeException('Shortcut must prefer the currently visible search input.');
if (strpos($quickOpen, "fetch(`quick-search.php?") === false) throw new RuntimeException('Shortcut closure must keep using the shared quick-search endpoint.');
if (substr_count($quickOpen, "document.addEventListener('keydown'") !== 1) throw new RuntimeException('Global keyboard shortcut must be installed exactly once.');

foreach (['assets/quick-open.css', 'assets/quick-open.js', 'vf-mobile-command-search', 'surface-manager.php?mode=focus'] as $needle) {
    if (strpos($home, $needle) === false) throw new RuntimeException('Home Quick Open / continuous Inbox contract missing: ' . $needle);
}
if (strpos($home, 'vf_render_home_workspace();') === false) throw new RuntimeException('Home must keep the canonical FunctionalHome renderer.');
foreach (['assets/quick-open.css', 'assets/quick-open.js'] as $needle) {
    if (strpos($workspace, $needle) === false) throw new RuntimeException('Existing resource workspace Quick Open integration regressed: ' . $needle);
}

echo "QUICK_OPEN_GLOBAL_CONTRACT_PASS\n";
