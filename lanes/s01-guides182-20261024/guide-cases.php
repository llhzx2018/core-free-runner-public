<?php
// Synthetic read-only configuration variants for isolated directory verification.
add_filter('option_vf_theme_layout',static function($raw){
    $case=(string)($_GET['vf_guide_case']??'');
    if(!in_array($case,['custom','hide_facts'],true))return $raw;
    $raw=is_array($raw)?$raw:[];$raw['moduleSettings']['guide_index']['post_list']['override']=true;
    if($case==='custom')$raw['moduleSettings']['guide_index']['post_list']['description']='Owner authored guide directory description';
    if($case==='hide_facts')foreach(['show_guide_difficulty','show_guide_duration','show_guide_steps']as$key)$raw['moduleSettings']['guide_index']['post_list'][$key]=false;
    return $raw;
},10001);
