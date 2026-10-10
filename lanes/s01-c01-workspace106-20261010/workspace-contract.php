<?php
require_once get_template_directory().'/inc/modules/module-tool-shortcode.php';
$capture=function(array $context): string {ob_start();vf_theme_module_render_tool_shortcode($context);return (string)ob_get_clean();};
$html=$capture(['route'=>'m3u8-downloader','shortcode'=>'[vf_m3u8_downloader_lite]']);
if(substr_count($html,'class="vf-m3u8-launchbar"')!==1||strpos($html,'class="vf-tool-runtime-path"')!==false)throw new Exception('real Provider workflow not singular');
remove_shortcode('vf_m3u8_downloader_lite');
$missing=$capture(['route'=>'m3u8-downloader','shortcode'=>'[vf_m3u8_downloader_lite]']);
if(strpos($missing,'Tool unavailable')===false||strpos($missing,'Workspace ready')!==false||strpos($missing,'VF_THEME_M3U8_TOOL_SHORTCODE_UNRENDERED')===false||strpos($missing,'data-vf-module-fallback')!==false)throw new Exception('missing Provider readiness/fail-closed regression');
vf_tool_m3u8_register_lazy_shortcodes();
$calls=0;add_shortcode('vf_workspace_fixture',function()use(&$calls){$calls++;return '<div data-synthetic-custom-tool="1">Custom output</div>';});
$custom=$capture(['route'=>'m3u8-downloader','shortcode'=>'[vf_workspace_fixture]']);
if($calls!==1||substr_count($custom,'class="vf-tool-runtime-path"')!==1||strpos($custom,'data-synthetic-custom-tool')===false)throw new Exception('custom renderer lost generic guide or rendered twice');
remove_shortcode('vf_workspace_fixture');
echo wp_json_encode(['status'=>'PASS','real_provider_single_workflow'=>'PASS','missing_provider_not_ready'=>'PASS','missing_provider_fail_closed'=>'PASS','custom_renderer_generic_workflow'=>'PASS','render_count'=>1,'production'=>'NOT_EXECUTED']);
