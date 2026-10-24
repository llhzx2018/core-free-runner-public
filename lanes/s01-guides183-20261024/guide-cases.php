<?php
// Synthetic read-only configuration variants for isolated directory verification.
add_filter('option_vf_theme_layout',static function($raw){
    $case=(string)($_GET['vf_guide_case']??'');
    if(!in_array($case,['custom','hide_facts','custom_cta','custom_title'],true))return $raw;
    $raw=is_array($raw)?$raw:[];$raw['moduleSettings']['guide_index']['post_list']['override']=true;
    if($case==='custom')$raw['moduleSettings']['guide_index']['post_list']['description']='Owner authored guide directory description';
    if($case==='hide_facts')foreach(['show_guide_difficulty','show_guide_duration','show_guide_steps']as$key)$raw['moduleSettings']['guide_index']['post_list'][$key]=false;
    if($case==='custom_cta')$raw['moduleSettings']['guide_index']['cta']=['override'=>true,'title'=>'Owner authored guide CTA','description'=>'Owner authored CTA description'];
    if($case==='custom_title')$raw['moduleSettings']['guide_index']['post_list']['title']='Owner authored guide heading';
    return $raw;
},10001);
