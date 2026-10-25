<?php
// Only synthetic fixture content, before the protected-data baseline.
foreach (['en','zh'] as $lang) {
 foreach (['previous','next'] as $kind) {
  $post=get_page_by_path('article-review-'.$kind.'-'.$lang,OBJECT,'post');
  if(!$post) throw new RuntimeException('ADJACENT_FIXTURE_MISSING');
  $title=$lang==='en' ? ($kind==='previous' ? 'Compare HLS Playback Across Browsers Without Losing the Cause' : 'ACompleteUnbrokenExampleTitleThatMustWrapWithoutClippingOrCreatingAnOrphanArrow') : ($kind==='previous' ? '跨浏览器比较 HLS 播放，别把原因一起改没了' : '保留真实错误与相关记录，再继续下一步播放问题定位');
  $id=wp_update_post(['ID'=>$post->ID,'post_title'=>$title],true);
  if(is_wp_error($id)) throw new RuntimeException('ADJACENT_FIXTURE_UPDATE_FAILED');
 }
}
echo "SYNTHETIC_ADJACENT_TITLES_READY\n";
