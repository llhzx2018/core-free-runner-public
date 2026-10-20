<?php
// Request-only synthetic variants, mounted solely in the isolated Runner.
$detail_layout = static function($raw) {
 if (!isset($_GET['vf_detail_mode'])) { return $raw; }
 $raw=is_array($raw)?$raw:[];$mode=(string)$_GET['vf_detail_mode'];
 foreach(['articleReading','guideReading','problemReading','glossaryReading'] as $key){
 $raw[$key]=array_replace((array)($raw[$key]??[]),[
  'tocPosition'=>$mode==='off'?'off':($mode==='sidebar'?'sidebar':'inline'),
  'sidebarMode'=>$mode==='off'?'off':'contextual',
  'reading_width'=>$mode==='wide'?'relaxed':'focused',
  'sidebar_width'=>'balanced',
 ]);}
 return $raw;
};
add_filter('option_vf_theme_layout',$detail_layout,10001);
add_filter('default_option_vf_theme_layout',$detail_layout,10001);
add_filter('the_content',static function($html) {
 if(!in_array(get_post_type(),['post','vf_guide','vf_problem','vf_glossary'],true))return $html;
 $zh=function_exists('vf_theme_public_is_zh')&&vf_theme_public_is_zh();
 if(($_GET['vf_detail_mode']??'')==='short')return '<p>'.($zh?'简短问题说明。':'Short problem explanation.').'</p>';
 $title=$zh?'检查音画不同步':'Check audio synchronization';
 $paragraph=$zh?'先确认播放列表和分片可以正常读取，再比较源音频与视频的时间戳。记录问题发生的位置，对照另一段已获授权的测试视频，确认问题来自源编码还是浏览器。':'Confirm that the manifest and segments are readable, then compare the source audio and video timestamps. Record the failing position and compare another authorized test clip to distinguish source encoding from browser playback.';
 return '<p>'.$paragraph.'</p><h2>'.$title.'</h2><p>'.$paragraph.'</p><h2>'.($zh?'按顺序诊断':'Diagnose in order').'</h2><ol><li>'.$paragraph.'</li><li>'.$paragraph.'</li></ol><h2>'.($zh?'检查结果':'Inspect the result').'</h2><table><thead><tr><th>Signal</th><th>Next step</th></tr></thead><tbody><tr><td>Timestamp</td><td>'.$paragraph.'</td></tr><tr><td>Encoding</td><td>'.$paragraph.'</td></tr></tbody></table><h2>'.($zh?'安全边界':'Safety boundaries').'</h2><p>'.$paragraph.'</p>';
},99998);
