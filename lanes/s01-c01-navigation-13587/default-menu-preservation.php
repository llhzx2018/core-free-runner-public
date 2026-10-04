<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(['theme-options-runtime.php','theme-options.php','services/brand-design-service.php','services/navigation-service.php','services/navigation-default-menu-service.php']);
$original=get_theme_mod('nav_menu_locations',[]);
$id=(int)($original['mobile']??0);if($id<=0){throw new Exception('missing synthetic menu');}
try {
 set_theme_mod('nav_menu_locations',['header'=>0,'header___en'=>0,'mobile'=>$id,'mobile___en'=>$id]);
 vf_theme_assign_menu_to_locations($id,['header','mobile','footer_tools'],'en',false);
 $actual=get_theme_mod('nav_menu_locations',[]);
 foreach(['header','header___en'] as $k){if(!array_key_exists($k,$actual)||$actual[$k]!==0){throw new Exception('explicit unbound replaced');}}
 foreach(['mobile','mobile___en','footer_tools','footer_tools___en'] as $k){if(($actual[$k]??0)!==$id){throw new Exception('binding/missing default not preserved');}}
 vf_theme_assign_menu_to_locations($id,['header'],'en',true);$actual=get_theme_mod('nav_menu_locations',[]);
 if(($actual['header']??0)!==$id||($actual['header___en']??0)!==$id){throw new Exception('explicit overwrite unavailable');}
 echo wp_json_encode(['status'=>'PASS','explicit_zero'=>'PASS','language_zero'=>'PASS','existing_binding'=>'PASS','missing_binding_initialization'=>'PASS','explicit_overwrite'=>'PASS']);
} finally {set_theme_mod('nav_menu_locations',$original);}
