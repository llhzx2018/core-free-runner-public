<?php
// Public article content and request-only settings; isolated Runner only.
$article_fixture_settings = static function ($raw) {
    $variant = (string)($_GET['vf_article_review'] ?? '');
    $mode = (string)($_GET['vf_article_mode'] ?? '');
    $raw = is_array($raw) ? $raw : [];
    if (in_array($variant, ['legacy', 'custom'], true)) {
        $rows = [
            'related_tools'=>['Try the matching tool','Send readers back to the practical tool route instead of leaving the article isolated.'],
            'faq'=>['Common questions','Only public answers directly related to this page are shown.'],
            'cta'=>['Turn the answer into action.','Open the checker or player to test the issue described on this page.'],
        ];
        foreach ($rows as $module=>$copy) {
            $raw['moduleSettings']['article_detail'][$module]=['override'=>true,'title'=>$variant==='custom'?'Owner '.$module.' title':$copy[0],'description'=>$variant==='custom'?'Owner '.$module.' description':$copy[1]];
        }
    }
    if (in_array($mode,['inline','sidebar','off','always'],true)) {
        $raw['articleReading']=array_replace((array)($raw['articleReading']??[]),[
            'tocPosition'=>$mode==='off'?'off':($mode==='sidebar'?'sidebar':'inline'),
            'sidebarMode'=>$mode==='always'?'always':($mode==='off'?'off':'contextual'),
        ]);
    }
    return $raw;
};
add_filter('option_vf_theme_layout',$article_fixture_settings,10003);
add_filter('default_option_vf_theme_layout',$article_fixture_settings,10003);
add_filter('the_title',static function($title,$id) {
    if((int)$id!==get_queried_object_id()||get_post_type($id)!=='post')return $title;
    return function_exists('vf_theme_public_is_zh')&&vf_theme_public_is_zh()
        ? '请求 HLS 支持前，别把不想分享的访问权限一起发出去'
        : 'Before Asking for HLS Support, Redact the Access You Did Not Mean to Share';
},99998,2);
add_filter('the_content',static function($html) {
    if(get_post_type()!=='post')return $html;
    $lang=function_exists('vf_theme_public_is_zh')&&vf_theme_public_is_zh()?'zh':'en';
    $body=file_get_contents(__DIR__.'/article-body-'.$lang.'.html');
    return $body.'<h2>'.($lang==='zh'?'合成代码排版样例':'Synthetic code layout sample').'</h2><pre><code>https://example.invalid/authorized/master.m3u8?synthetic=long-example-value-for-reading-layout-only</code></pre>';
},99998);
