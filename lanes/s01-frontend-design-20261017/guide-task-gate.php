<?php
if (!defined('ABSPATH')) { exit(1); }
$cases = [
 ['what-is-m3u8','What Is M3U8? A Practical Guide to HLS Playlists','start'],
 ['hls-streaming-guide','HLS Streaming Guide: How M3U8 Playlists Work in Browsers','start'],
 ['hls-live-vs-vod','HLS Live vs VOD: What Changes in M3U8 Playlists?','start'],
 ['m3u8-master-playlist-explained','M3U8 Master Playlist Explained: Variants and Bandwidth','inspect'],
 ['hls-segment-duration-guide','HLS Segment Duration Guide','inspect'],
 ['m3u8-errors','M3U8 Errors: A Practical Troubleshooting Map','inspect'],
 ['player-comparison','Online M3U8 Player Comparison: What Matters Before You Test','play'],
 ['hls-vs-mp4-for-browser-playback','HLS vs MP4 for Browser Playback','play'],
 ['safe-m3u8-downloader','Safe M3U8 Downloader: Owner-Side Checklist','export'],
 ['downloader-vs-ffmpeg','M3U8 Downloader vs FFmpeg: Which Workflow?','export'],
 ['m3u8-vs-mp4','M3U8 vs MP4: Which Format Should You Use?','export'],
 ['what-is-m3u8-zh','什么是 M3U8？实用入门指南','start'],
 ['safe-downloader-zh','安全 M3U8 下载清单','export'],
];
$ids=[];
try {
  foreach ($cases as [$slug,$title,$expected]) {
    $id=wp_insert_post(['post_type'=>'vf_guide','post_status'=>'draft','post_name'=>$slug,'post_title'=>$title,'post_excerpt'=>'Inspect HLS segments, check player and download limitations; common generic excerpt.'],true);
    if (is_wp_error($id) || $id<1) { throw new RuntimeException('cannot create isolated test guide'); }
    $ids[]=$id;
    $got=vf_theme_guide_task_key($id);
    if ($got!==$expected) { throw new RuntimeException("$slug expected $expected got $got"); }
  }
  $id=$ids[0];
  update_post_meta($id,'_vf_guide_task','export');
  if (vf_theme_guide_task_key($id)!=='export') { throw new RuntimeException('explicit editor task must win'); }
  update_post_meta($id,'_vf_guide_task','diagnosis');
  if (vf_theme_guide_task_key($id)!=='inspect') { throw new RuntimeException('explicit task alias must win'); }
  echo 'GUIDE_TASK_CLASSIFICATION_EXCERPT_IMMUNITY_AND_EXPLICIT_META=PASS '.count($cases)." cases\n";
} finally {
  foreach ($ids as $id) { wp_delete_post($id,true); }
}
