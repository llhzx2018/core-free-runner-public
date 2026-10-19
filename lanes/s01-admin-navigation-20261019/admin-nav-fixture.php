<?php
// Synthetic host adapter only. Never part of a Theme package or Production.
add_action('admin_menu', static function(): void {
 add_theme_page('Synthetic Theme Host','Synthetic Theme Host','manage_options','synthetic-theme-host',static function(): void {
  vf_tools_theme_render_component_workspace(['tab'=>$_GET['tab']??'overview','hostUrl'=>admin_url('admin.php?page=synthetic-theme-host&component=theme')]);
 });
});
add_action('admin_enqueue_scripts', static function(): void {
 if(($_GET['page']??'')==='synthetic-theme-host') { vf_tools_theme_enqueue_component_workspace_assets($_GET['tab']??'overview'); }
});
