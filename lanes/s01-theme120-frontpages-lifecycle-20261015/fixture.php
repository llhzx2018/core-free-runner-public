<?php
// Synthetic WordPress only. Never included in the product package.
add_action('init',static function(): void {
    foreach(['vf_guide'=>'guides','vf_problem'=>'problems','vf_glossary'=>'glossary','vf_tool_note'=>'tool-notes'] as $type=>$slug){
        register_post_type($type,['public'=>true,'show_ui'=>true,'label'=>$type,'supports'=>['title','editor','excerpt','revisions'],'rewrite'=>['slug'=>$slug,'with_front'=>false]]);
    }
},0);
add_filter('pll_get_post_types',static function(array $types): array {foreach(['vf_guide','vf_problem','vf_glossary','vf_tool_note'] as $type){$types[$type]=$type;}return $types;});
add_action('pre_get_posts',static function($query): void {
    if(!$query->get('vf_frontend_page_directory')){return;}
    $GLOBALS['s01_directory_query_count']=(int)($GLOBALS['s01_directory_query_count']??0)+1;
    if($query->get('s')==='synthetic-read-failure'){throw new RuntimeException('SYNTHETIC_INTERNAL_ERROR_DO_NOT_EXPOSE');}
});
add_action('admin_footer',static function(): void {echo '<!-- s01-directory-queries:'.(int)($GLOBALS['s01_directory_query_count']??0).' -->';});
