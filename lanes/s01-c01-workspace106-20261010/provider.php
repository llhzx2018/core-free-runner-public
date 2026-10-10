<?php
require_once get_template_directory().'/inc/services/public-tool-runtime-contract.php';
$routes=vf_theme_public_tool_active_routes();$baseline=getenv('VF_EXPECT_BASELINE_BUG')==='1';
if($baseline){
    if(count($routes)!==9 || in_array('m3u8-downloader',$routes,true) || in_array('m3u8-to-mp4',$routes,true))throw new Exception('baseline missing-tool defect not reproduced');
    echo wp_json_encode(['status'=>'REPRODUCED','theme'=>wp_get_theme()->get('Version'),'provider'=>VF_TOOL_M3U8_VERSION,'directory_tools'=>count($routes),'provider_downloader_registered'=>shortcode_exists('vf_m3u8_downloader_lite'),'provider_converter_registered'=>shortcode_exists('vf_m3u8_converter_lite')]);return;
}
if(count($routes)!==11 || !in_array('m3u8-downloader',$routes,true) || !in_array('m3u8-to-mp4',$routes,true))throw new Exception('actual provider tool discovery failed');
foreach(vf_theme_public_tool_catalog_rows() as $route=>$row){if(!shortcode_exists($row['shortcode']))throw new Exception('missing shortcode: '.$route);}
$before=$routes;remove_shortcode('vf_m3u8_downloader_lite');
if(vf_theme_public_target_is_available('/m3u8-downloader/'))throw new Exception('missing runtime gate bypassed');
vf_tool_m3u8_register_lazy_shortcodes();
if(vf_theme_public_tool_active_routes()!==$before)throw new Exception('runtime restore failed');
echo wp_json_encode(['status'=>'PASS','theme'=>wp_get_theme()->get('Version'),'provider'=>VF_TOOL_M3U8_VERSION,'directory_tools'=>count($routes),'real_registered_shortcodes'=>'PASS','missing_runtime_fail_closed'=>'PASS','schema_mutation'=>false]);
