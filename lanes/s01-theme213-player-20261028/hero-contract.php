<?php
// Synthetic renderer inputs. No WordPress installation or production writes.
define('ABSPATH', __DIR__);
function esc_html($s){return htmlspecialchars((string)$s,ENT_QUOTES,'UTF-8');}
function esc_attr($s){return esc_html($s);}
function esc_url($s){return esc_html($s);}
function sanitize_title($s){return (string)$s;}
function vf_theme_context_field_data($c){return $c['field_data']??[];}
function vf_theme_public_is_zh(){return $GLOBALS['zh']??false;}
function vf_theme_context_route($c){return $c['route']??'';}
function vf_theme_public_url($p){return ($GLOBALS['zh']?'/zh':'').$p;}
$root=$argv[1];$mode=$argv[2];require $root.'/inc/modules/module-hero.php';
$out=[];
foreach([false,true] as $zh){
 $GLOBALS['zh']=$zh;
 foreach(['m3u8-player','m3u8-playlist-checker','m3u8-backup-restore','custom-tool']as$route){
  foreach([false,true]as$custom){
   $title=$custom?'Authored <Player> title':($zh?'在线 M3U8/HLS 播放器':'M3U8 Player Online for HLS Playback');
   $description=$custom?'Authored description & limits':($zh?'粘贴已授权的 M3U8 或 HLS URL，在插件负责的播放器区域中播放。':'Paste an authorized M3U8 or HLS URL and play it inside the plugin-owned player area.');
   $c=['route'=>$route,'title'=>$title,'description'=>$description,'field_data'=>['eyebrow'=>$custom?'Authored label':($zh?'播放器':'Player')]];
   ob_start();vf_theme_module_render_tool_hero($c);$html=ob_get_clean();
   if(substr_count($html,'<h1>')!==1||!str_contains($html,esc_html($title)))throw new Exception('canonical H1 changed');
   if($custom&&(!str_contains($html,esc_html($description))||!str_contains($html,'Authored label')))throw new Exception('authored copy lost');
   if($mode==='after'&&$route==='m3u8-player'){
    if(str_contains($html,'vf-tool-breadcrumb')||str_contains($html,'href="#tool"'))throw new Exception('duplicate route/start entry remains');
    if(!$custom&&(str_contains($html,'plugin-owned')||str_contains($html,'插件负责')))throw new Exception('internal copy remains');
   }
   $out[($zh?'zh':'en').'|'.$route.'|'.(int)$custom]=hash('sha256',$html);
  }
 }
}
echo json_encode(['status'=>'PASS','mode'=>$mode,'cases'=>count($out),'hashes'=>$out]);
