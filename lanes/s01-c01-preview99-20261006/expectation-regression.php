<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(require get_template_directory().'/inc/bootstrap/manifests/admin-tabs/preview.php');
$assert=static function(bool $ok,string $message):void{if(!$ok)throw new RuntimeException($message);};
$hreflang_issues=static fn(array $issues):array=>array_values(array_filter($issues,static fn(array $row):bool=>($row['field']??'')==='hreflang'));
$rows=[];
foreach(['','tools','faq','guides'] as $route){
 $request=['url'=>home_url('/'.($route!==''?$route.'/':'')),'route'=>$route,'language'=>'en','targetType'=>'route','sameOrigin'=>true,'postId'=>0];
 $expected=vf_theme_seo_inspector_expected($request);$fetch=vf_theme_seo_inspector_fetch($request['url']);
 $assert(!empty($fetch['ok']),'actual public fetch failed');
 $assert(count($expected['hreflang'])>=2,'admin expectations lack registered language family: '.$route);
 $assert(!$hreflang_issues(vf_theme_seo_inspector_compare($request,$expected,$fetch)),'actual multilingual output incorrectly rejected: '.$route);
 $missing=$fetch;unset($missing['actual']['hreflang']['zh']);
 $assert((bool)$hreflang_issues(vf_theme_seo_inspector_compare($request,$expected,$missing)),'missing language output was accepted');
 $wrong=$fetch;$wrong['actual']['hreflang']['zh']=home_url('/wrong-language-target/');
 $assert((bool)$hreflang_issues(vf_theme_seo_inspector_compare($request,$expected,$wrong)),'incorrect language target was accepted');
 $rows[]=['route'=>$route,'expected'=>$expected['hreflang'],'actual'=>$fetch['actual']['hreflang'],'baseline'=>'PASS','missing'=>'FAIL_PRESERVED','wrong_target'=>'FAIL_PRESERVED'];
}
$request=['url'=>home_url('/404.html'),'route'=>'404.html','language'=>'en','targetType'=>'route','pageContext'=>'not_found','sameOrigin'=>true,'postId'=>0];
$expected=vf_theme_seo_inspector_expected($request);$fetch=vf_theme_seo_inspector_fetch($request['url']);
$assert(!$expected['hreflang']&&!$fetch['actual']['hreflang'],'system page language boundary changed');
$fetch['actual']['hreflang']=['en'=>home_url('/')];
$assert((bool)$hreflang_issues(vf_theme_seo_inspector_compare($request,$expected,$fetch)),'system-page forbidden language output accepted');
echo wp_json_encode(['status'=>'PASS','environment'=>'SYNTHETIC_DISPOSABLE_WORDPRESS','cases'=>$rows,'system_negative'=>'FAIL_PRESERVED','production'=>'NOT_EXECUTED'],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
