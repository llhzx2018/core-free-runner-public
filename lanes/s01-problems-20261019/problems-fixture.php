<?php
// Isolated WordPress only. Replace synthetic Problems fixtures, never Production.
foreach (get_posts(['post_type'=>'vf_problem','post_status'=>'any','numberposts'=>-1,'lang'=>'']) as $p) { wp_delete_post($p->ID, true); }
$subjects = [
 ['hls-audio-out-of-sync','HLS Audio Out of Sync','HLS 音画不同步','playback','informational','m3u8-player'],
 ['hls-buffering-stuttering','HLS Buffering and Stuttering','HLS 缓冲与卡顿','playback','informational','m3u8-player'],
 ['how-to-check-if-m3u8-is-encrypted','Encrypted M3U8 Playlist: EXT-X-KEY','M3U8 加密播放列表检查','encryption','degraded','m3u8-encryption-detector'],
 ['m3u8-403-forbidden-fix','M3U8 403 Forbidden','M3U8 403 访问被拒绝','access','blocking','m3u8-browser-stream-test'],
 ['m3u8-404-segment-not-found','M3U8 404 Segment Not Found','M3U8 404 分片不存在','structure','limited','m3u8-segment-viewer'],
 ['m3u8-cors-error-explained','M3U8 CORS Error','M3U8 CORS 跨域错误','browser','blocking','m3u8-browser-stream-test'],
 ['m3u8-download-failed','M3U8 Download Failed','M3U8 下载失败','playback','informational','m3u8-player'],
 ['m3u8-mime-type-fix','M3U8 MIME Type Fix','M3U8 MIME 类型修复','playback','informational','m3u8-player'],
 ['m3u8-to-mp4-quality-loss','M3U8 to MP4 Quality Loss','M3U8 转 MP4 画质损失','playback','informational','m3u8-player'],
];
$result=[];
foreach ($subjects as [$slug,$en,$zh,$category,$severity,$tool]) {
 $pair=[];
 foreach (['en','zh'] as $lang) {
  $title=$lang==='en'?$en:$zh;
  $excerpt=$lang==='en'?'General checklist for access, playlist structure, segment URLs, CORS, 403 and encryption boundaries.':'按现象逐步检查播放问题。';
  $id=wp_insert_post(['post_type'=>'vf_problem','post_status'=>'publish','post_name'=>$slug,'post_title'=>$title,'post_excerpt'=>$excerpt,'post_content'=>'<h2>Isolated fixture</h2><p>Synthetic read-only directory test.</p>'],true);
  if (is_wp_error($id)) { throw new Exception('FIXTURE_INSERT_FAILED'); }
  pll_set_post_language($id,$lang);$pair[$lang]=$id;
  $result[$lang][]=['id'=>$id,'title'=>$title,'category'=>$category,'severity'=>$severity,'tool'=>$tool,'url'=>get_permalink($id)];
 }
 pll_save_post_translations($pair);
}
echo wp_json_encode($result,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
