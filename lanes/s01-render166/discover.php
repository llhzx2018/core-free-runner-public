<?php
if (!defined('ABSPATH')) { exit(20); }
require_once ABSPATH.'wp-admin/includes/update.php';
delete_site_transient('update_themes');
delete_site_transient('update_plugins');
if (class_exists('VF_M3U8_Update_Source_V1')) { VF_M3U8_Update_Source_V1::clear_cache(); }
wp_update_themes();
wp_update_plugins();
$t=get_site_transient('update_themes');
$p=get_site_transient('update_plugins');
$themer=is_object($t)?($t->response['vf-tools-theme']??null):null;
$plugin=is_object($p)?($p->response['vf-tool-m3u8/vf-tool-m3u8.php']??null):null;
$tv=is_array($themer)?($themer['new_version']??''):($themer->new_version??'');
$package=is_array($themer)?($themer['package']??''):($themer->package??'');
$pv=is_object($plugin)?($plugin->new_version??''):($plugin['new_version']??'');
$installed=wp_get_theme('vf-tools-theme')->get('Version');
$provider=get_plugin_data(WP_PLUGIN_DIR.'/vf-tool-m3u8/vf-tool-m3u8.php',false,false)['Version'];
$result=[
 'theme_installed'=>$installed,'theme_offered'=>$tv,'package_present'=>$package!=='',
 'provider_installed'=>$provider,'provider_offered'=>$pv,'production'=>'UNTOUCHED',
];
echo wp_json_encode($result)."\n";
if($installed!=='1.35.165'||$tv!=='1.35.166'||$package===''||$provider!=='1.25.94'||$pv!=='')exit(43);
echo "NATIVE_THEME166_DISCOVERY_WITHOUT_APPLY_PASS\n";
