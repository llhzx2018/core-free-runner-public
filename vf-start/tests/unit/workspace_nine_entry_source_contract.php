<?php
declare(strict_types=1);
$root = dirname(__DIR__, 2);
$read = static fn(string $path): string => (string)file_get_contents($root . '/' . $path);

$core = $read('src/app/FunctionalWorkspaceCore.php');
$shell = $read('src/app/FunctionalWorkspaceShell.php');
$workspace = $read('src/app/FunctionalWorkspace.php');
$surface = $read('src/surface.php');
$legacyBooks = $read('src/books.php');

foreach (['courses.php','tools.php','software.php'] as $route) {
    if (!is_file($root . '/src/' . $route)) throw new RuntimeException('Missing presentation route: ' . $route);
}
foreach (['courses','tools','software'] as $mode) {
    if (strpos($core, "'{$mode}'") === false) throw new RuntimeException('Core mode missing: ' . $mode);
    if (strpos($surface, "'{$mode}'") === false) throw new RuntimeException('Surface guard missing: ' . $mode);
}
if (strpos($legacyBooks, "\$vfSurface = 'courses';") === false) throw new RuntimeException('Legacy books route must render Courses.');
if (strpos($workspace, "\$mode==='courses'") === false) throw new RuntimeException('Courses renderer missing.');
if (strpos($workspace, "['tools','software']") === false) throw new RuntimeException('Derived view real-data filters missing.');
if (substr_count($shell, 'VfWorkspaceViewCatalog::entries') < 2) throw new RuntimeException('Global and sidebar IA must use one catalog.');
if (strpos($core, 'VfWorkspaceViewCatalog::assets') === false) throw new RuntimeException('Mode assets must route through derived catalog.');

echo "WORKSPACE_NINE_ENTRY_SOURCE_CONTRACT_PASS\n";
