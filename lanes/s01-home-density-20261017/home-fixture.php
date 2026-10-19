<?php
// Synthetic-only GET projections; never persisted or included in a Theme artifact.
$home_fixture=static function($raw){
 if(!isset($_GET['vf_home_count']))return $raw;
 $raw=is_array($raw)?$raw:[];
 $raw['moduleSettings']['home']['tool_grid']['override']=true;
 $raw['moduleSettings']['home']['tool_grid']['count']=max(1,min(8,(int)$_GET['vf_home_count']));
 if(($_GET['vf_home_mode']??'')==='custom'){
  foreach(['tool_grid','content_matrix']as $m){$raw['moduleSettings']['home'][$m]['override']=true;$raw['moduleSettings']['home'][$m]['title']='Owner custom home '.$m;$raw['moduleSettings']['home'][$m]['description']='Owner custom description '.$m;}
  $raw['moduleSettings']['home']['content_matrix']['count']=2;
 }
 return $raw;
};add_filter('option_vf_theme_layout',$home_fixture,10001);add_filter('default_option_vf_theme_layout',$home_fixture,10001);
