<?php
if (!defined('ABSPATH')) exit(20);
require_once ABSPATH.'wp-admin/includes/plugin.php';
require_once ABSPATH.'wp-admin/includes/update.php';
delete_site_transient('update_plugins');
if (class_exists('VF_M3U8_Update_Source_V1')) VF_M3U8_Update_Source_V1::clear_cache();
wp_update_plugins();
$updates=get_site_transient('update_plugins');
$item=is_object($updates)?($updates->response['vf-tool-m3u8/vf-tool-m3u8.php']??null):null;
$version=is_object($item)?(string)($item->new_version??''):(is_array($item)?(string)($item['new_version']??''):'');
$installed=(string)get_plugin_data(WP_PLUGIN_DIR.'/vf-tool-m3u8/vf-tool-m3u8.php',false,false)['Version'];
echo wp_json_encode(['installed'=>$installed,'offered'=>$version,'production'=>'UNTOUCHED'])."\n";
if ($installed!=='1.25.94'||$version!=='1.25.95') exit(43);
