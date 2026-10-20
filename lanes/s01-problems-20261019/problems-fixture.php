<?php
// Isolated WordPress only. Replace synthetic Problems fixtures, never Production.
foreach (get_posts(['post_type'=>'vf_problem','post_status'=>'any','numberposts'=>-1,'lang'=>'']) as $p) { wp_delete_post($p->ID, true); }
$subjects = [
 ['hls-audio-out-of-sync','HLS Audio Out of Sync: Causes and Fix Checklist','HLS 音画不同步：原因与修复清单','playback','informational','m3u8-player'],
 ['hls-buffering-stuttering','HLS Buffering and Stuttering: Practical Fix Checklist','HLS 缓冲和卡顿：实用修复清单','playback','informational','m3u8-player'],
 ['how-to-check-if-m3u8-is-encrypted','Encrypted M3U8 Playlist Problem: Check EXT-X-KEY Safely','加密 M3U8 播放列表问题：安全检查 EXT-X-KEY','encryption','degraded','m3u8-encryption-detector'],
 ['m3u8-403-forbidden-fix','M3U8 403 Forbidden Problem: Browser Access Checklist','M3U8 403 Forbidden 问题：浏览器访问检查清单','access','blocking','m3u8-browser-stream-test'],
 ['m3u8-404-segment-not-found','M3U8 404 Segment Not Found: How to Trace Broken HLS Paths','M3U8 分片 404：如何追踪损坏的 HLS 路径','structure','limited','m3u8-segment-viewer'],
 ['m3u8-cors-error-explained','M3U8 CORS Problem: Browser Access Checklist','M3U8 CORS 问题：浏览器访问检查清单','browser','blocking','m3u8-browser-stream-test'],
 ['m3u8-download-failed','M3U8 Download Failed: Diagnosis Checklist','M3U8 下载失败：诊断清单','playback','informational','m3u8-player'],
 ['m3u8-mime-type-fix','M3U8 MIME Type Fix: Why the Playlist Loads as Text or Fails','M3U8 MIME 类型修复：为什么播放列表显示为文本或加载失败','structure','limited','m3u8-playlist-checker'],
 ['m3u8-to-mp4-quality-loss','M3U8 to MP4 Quality Loss: What Actually Changes During Conversion','M3U8 转 MP4 画质损失：转换时到底发生了什么','playback','informational','m3u8-player'],
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
