<?php
/* Synthetic isolated API transport only; package verifier, updater hooks,
 * runtime/state authority and native WP upgrader remain unmodified. */
add_filter('pre_http_request',function($pre,$args,$url){
 if(!defined('VF_WP_UPDATE_TEST_MODE')||VF_WP_UPDATE_TEST_MODE!==true){return $pre;}
 $base='https://api.github.com/repos/llhzx2018/';$kind='';
 if($url===$base.'core-updates/contents/projects/S01-C03.json?ref=main'){$kind='manifest';}
 elseif($url===$base.'vf-tools-m3u8/releases/tags/v'.getenv('CANDIDATE_VERSION')){$kind='release';}
 elseif($url===$base.'vf-tools-m3u8/releases/assets/590059'){$kind='asset';}
 else{return $pre;}
 if(($args['headers']['Authorization']??'')!=='Bearer runner-private-token'){return new WP_Error('synthetic_auth_required','Synthetic credential required');}
 $trace=get_option('vf_runner_api_trace',[]);$trace[$kind]=($trace[$kind]??0)+1;update_option('vf_runner_api_trace',$trace,false);
 $m=json_decode(file_get_contents('/tmp/synthetic-channel.json'),true);
 if($kind==='manifest'){$body=wp_json_encode($m);}
 elseif($kind==='release'){$body=wp_json_encode(['tag_name'=>$m['release_tag'],'assets'=>[['name'=>$m['asset_name'],'size'=>$m['asset_bytes'],'url'=>$base.'vf-tools-m3u8/releases/assets/590059']]]);}
 else{
  if(empty($args['stream'])||empty($args['filename'])){return new WP_Error('synthetic_stream_required','Actual streamed download required');}
  $body=file_get_contents('/tmp/candidate.zip');
  if(get_option('vf_runner_corrupt_asset',false)){$body[100]=chr(ord($body[100])^1);}
  file_put_contents($args['filename'],$body);$body='';
 }
 return ['headers'=>[],'body'=>$body,'response'=>['code'=>200,'message'=>'OK'],'cookies'=>[],'filename'=>$args['filename']??null];
},10,3);

