<?php
// Isolated fault injection only. Never packaged or copied to Production.
add_filter('pll_the_language_link',static function($url,$slug){
    if(isset($_GET['vf_missing_current']) && is_404() && $slug===pll_current_language('slug')){ return null; }
    return $url;
},PHP_INT_MAX,2);
