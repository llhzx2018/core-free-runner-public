<?php
declare(strict_types=1);
if (!isset($vfSurface)) throw new RuntimeException('资源类型未指定。');
$vfWorkspaceMode = strtolower(trim((string)$vfSurface));
if (!in_array($vfWorkspaceMode, ['channels','watch','topics','books','courses','projects','tools','software'], true)) throw new RuntimeException('资源类型无效。');
require_once __DIR__ . '/app/FunctionalWorkspace.php';
vf_security_headers(true);
vf_render_functional_workspace();
