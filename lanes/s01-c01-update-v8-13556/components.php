<?php
// Synthetic consumer projections in the isolated Runner only.
add_filter('vf_wp_update_components_v1',function($components){
 foreach(['S01-C02'=>['VF Tools Ops','vf-ops/vf-ops.php','1.21.970'],'S01-C03'=>['VF Tools M3U8','vf-tool-m3u8/vf-tool-m3u8.php','1.25.40']] as $id=>$v){
  $components[$id]=['component_id'=>$id,'name'=>$v[0],'type'=>'PLUGIN','package_slug'=>explode('/',$v[1])[0],'plugin_file'=>$v[1],'current_version'=>$v[2],'target_version'=>$v[2],'state'=>'UP_TO_DATE','manage_url'=>admin_url('plugins.php')];
 }
 return $components;
});
