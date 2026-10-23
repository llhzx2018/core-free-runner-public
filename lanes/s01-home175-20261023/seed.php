<?php
// Synthetic isolated review fixtures, before the protected-state snapshot.
// Retain the established existing-installation marker without unrelated pages.
$layout=get_option('vf_theme_layout',[]);$layout['s01_authored_keep']='retained';$layout['moduleSettings']['home']['tool_grid']['override']=true;$layout['moduleSettings']['home']['tool_grid']['count']=6;$layout['moduleSettings']['home']['tool_grid']['featured_count']=0;update_option('vf_theme_layout',$layout);set_theme_mod('s01_authored_keep','retained');
// Reuse the established configured-install native menu fixture, bounded to one tool.
$menus=[];
foreach(['en','zh'] as $lang){
 foreach(['header','mobile','footer_tools','footer_resources','footer_company','footer_partners'] as $location){
  $menu=wp_create_nav_menu('Synthetic existing '.$location.' '.$lang);
  if(is_wp_error($menu))throw new RuntimeException('EXISTING_MENU_FIXTURE_FAILED');
  $item=wp_update_nav_menu_item($menu,0,['menu-item-title'=>'Existing public tool','menu-item-url'=>home_url('/'.($lang==='zh'?'zh/':'').'m3u8-player/'),'menu-item-status'=>'publish','menu-item-type'=>'custom']);
  if(is_wp_error($item))throw new RuntimeException('EXISTING_MENU_ITEM_FAILED');
  $menus[$location][$lang]=(int)$menu;
 }
}
$options=get_option('polylang',[]);$options['nav_menus'][get_stylesheet()]=$menus;update_option('polylang',$options);
$locations=[];foreach($menus as $location=>$langs)$locations[$location]=$langs['en'];set_theme_mod('nav_menu_locations',$locations);
$base=['schema'=>1,'phase'=>'complete','status'=>'accepted','note'=>'Synthetic existing owner record preserved','version'=>'1.35.162','updated'=>'2026-10-21 12:00:00','user'=>1,'token'=>'synthetic-record-162'];
foreach ([['home','en','desktop'],['contact_page','en','desktop']] as [$subject,$language,$device]) {
    $value=array_merge($base,compact('subject','language','device'));
    if ($subject==='contact_page') {$value['status']='needs_changes';$value['note']='Synthetic contact note preserved';}
    update_option('vf_theme_frontend_review_'.hash('sha256',$subject.'|'.$language.'|'.$device),wp_json_encode($value),false);
}
update_option('vf_theme_frontend_review_'.hash('sha256','about_page|zh|mobile'),'{"schema":99,"keep":"unknown-schema-must-not-change"}',false);



