<?php
// Synthetic-only DB failure, never shipped in the product.
add_filter('query',static function($sql){
    if (strtoupper($_SERVER['REQUEST_METHOD']??'GET')==='POST' && ($_POST['vf_theme_action']??'')==='frontend_pages_review_save'
        && ($_POST['vf_review_note']??'')==='Synthetic forced database failure' && str_contains($sql,'vf_theme_frontend_review_')
        && (str_starts_with($sql,'INSERT')||str_starts_with($sql,'UPDATE'))) {
        return "UPDATE {$GLOBALS['wpdb']->options} SET option_value=option_value WHERE 1=0";
    }
    return $sql;
});
