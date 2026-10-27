<?php
define('ABSPATH',__DIR__.'/');
$source=$argv[1];$phase=$argv[2];$GLOBALS['language']=$argv[3]??'en';$GLOBALS['scenario']=$argv[4]??'normal';
class WP_Post{public $ID;public $post_status;public $post_title;function __construct($id,$title,$status='publish'){$this->ID=$id;$this->post_title=$title;$this->post_status=$status;}}
function add_action(...$args){}function add_filter(...$args){}
function post_type_exists($s){return true;}
function get_option($k){return 0;}
function get_post($id){return new WP_Post($id,$id===1001?'Authored English sitemap':'作者的中文站点地图',$GLOBALS['scenario']==='draft'?'draft':'publish');}
function get_page_by_path(...$args){return new WP_Post(1002,'作者的中文站点地图');}
function vf_toolsite_multilingual_request_language_code(){return $GLOBALS['language'];}
function vf_theme_public_route_contract_find_exact_published_post_id_for_route_language($route,$language){if($GLOBALS['scenario']==='missing')return 0;return $language==='en'?1001:1002;}
require $source.'/inc/frontend-seo-context.php';
$p=vf_toolsite_static_route_existing_post('sitemap');
$expected=$phase==='before'?1002:($GLOBALS['scenario']==='normal'?($GLOBALS['language']==='en'?1001:1002):0);
if(($p->ID??0)!==$expected){fwrite(STDERR,'ROUTE_LANGUAGE_FAIL');exit(1);}
echo json_encode(['status'=>'PASS','phase'=>$phase,'language'=>$GLOBALS['language'],'scenario'=>$GLOBALS['scenario'],'selected'=>$p->ID??0,'expected'=>$expected],JSON_UNESCAPED_UNICODE)."\n";
