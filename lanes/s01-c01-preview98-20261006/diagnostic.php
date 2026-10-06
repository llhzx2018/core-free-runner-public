<?php
wp_set_current_user(1);
vf_theme_bootstrap_require_many(require get_template_directory().'/inc/bootstrap/manifests/admin-tabs/preview.php');
$ids=json_decode(file_get_contents('/tmp/preview-run-ids.json'),true);
$out=['status'=>'COLLECTED','environment'=>'SYNTHETIC_DISPOSABLE_WORDPRESS','version'=>vf_theme_runtime_version(),'runs'=>[],'production'=>'NOT_EXECUTED'];
$select=static fn(array $a,array $keys):array=>array_intersect_key($a,array_flip($keys));
$safe=function($v) use (&$safe){
 if(is_array($v)){foreach($v as $k=>$item)$v[$k]=$safe($item);return $v;}
 if(is_string($v))return preg_replace_callback('~https?://[^\s<>"\']+~',static function($m){$u=wp_parse_url($m[0]);return ($u['scheme']??'http').'://'.($u['host']??'').(isset($u['port'])?':'.$u['port']:'').($u['path']??'/');},$v);
 return $v;
};
foreach($ids as $id){
 $j=vf_theme_preview_workbench_load_job((string)$id);$a=(array)($j['artifact']??[]);
 if(!$j||!$a){$out['runs'][]=['runId'=>$id,'diagnostic'=>'JOB_OR_ARTIFACT_MISSING'];continue;}
 $r=$select($a,['runId','mode','status','runState','summary','issues','rows','evidenceState','finalOnlinePass']);
 $b=(array)($a['rawEvidence']['browserEvidence']??[]);
 $r['browser']=$select($b,['pageTypeCount','sampleCount','pageTypeMatrixComplete','blockingProbeCount','consoleErrorCount','horizontalOverflowCount','unsafeLinkCount']);
 $rowkeys=['width','loaded','horizontalOverflow','runtimeProbeFailures','consoleErrors','overflowRootDiagnostics','unsafeLinks','unsafeLinkCount','runtimeProbeBlockingFailureCount'];
 $r['browser']['breakpoints']=array_map(static fn($row)=>$select((array)$row,$rowkeys),(array)($b['breakpoints']??[]));
 $r['browser']['pages']=array_map(static function($row)use($select,$rowkeys){$page=$select((array)$row,['targetKey','targetLabel','language','url']);$page['breakpoints']=array_map(static fn($row)=>$select((array)$row,$rowkeys),(array)($row['breakpoints']??[]));return $page;},(array)($b['pages']??[]));
 $r['foundation']=$select((array)($a['rawEvidence']['foundation']??[]),['issues','catalog']);
 $out['runs'][]=$safe($r);
}
$request=['url'=>home_url('/tools/'),'route'=>'tools','language'=>'en','targetType'=>'route','sameOrigin'=>true];
$out['hreflangTrace']['beforeAvailable']=function_exists('vf_theme_get_hreflang_map');
$out['hreflangTrace']['beforeExpected']=vf_theme_seo_inspector_expected($request)['hreflang'];
vf_theme_bootstrap_require_many(['services/hreflang-service.php']);
$out['hreflangTrace']['afterAvailable']=function_exists('vf_theme_get_hreflang_map');
$out['hreflangTrace']['afterExpected']=vf_theme_seo_inspector_expected($request)['hreflang'];
$out['routeTrace']=[];
foreach(['','tools','faq','guides','about','404.html'] as $route){
 $out['routeTrace'][$route]=['resolved'=>vf_theme_url_resolver_resolve(['route'=>$route,'language'=>'en']), 'family'=>vf_theme_get_page_family_technical_state(['route'=>$route,'language'=>'en']), 'hreflang'=>vf_theme_get_hreflang_state(['route'=>$route,'language'=>'en'])];
}
echo wp_json_encode($safe($out),JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);

