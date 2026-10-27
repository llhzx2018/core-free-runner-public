<?php
$path='/tmp/404-layout-preserve.bin';
if (!file_exists($path)) { file_put_contents($path,serialize(get_option('vf_theme_layout'))); }
$original=unserialize(file_get_contents($path),['allowed_classes'=>false]);
$mode=(string)($args[0]??'restore');$layout=$original;
if ($mode!=='restore') {
    $s=&$layout['moduleSettings']['not_found']['system_recovery'];
    $s=is_array($s)?$s:[];$s['override']=true;
    if ($mode==='custom' || $mode==='title-only') { $s['title']='Custom <title> preserved'; }
    if ($mode==='custom' || $mode==='description-only') { $s['description']='Custom <description> preserved'; }
    if ($mode==='off') { foreach(['show_search','show_popular_queries','show_home_route','show_tool_route','show_guide_route','show_problem_route','show_faq_route','show_recommended_content'] as $k){$s[$k]=false;} }
    if ($mode==='columns') { $s['route_columns']=1;$s['show_route_descriptions']=false;$s['show_popular_queries']=false;$s['show_recommended_content']=false; }
}
update_option('vf_theme_layout',$layout);
echo "SYNTHETIC_SETTINGS_MODE_APPLIED\n";
