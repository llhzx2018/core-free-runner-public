<?php
declare(strict_types=1);
/**
 * Read-only, one-off QA: evaluate the exact Ops 1.21.1065 Source HTML
 * inspector on two public page bodies fetched by the isolated runner.
 * Never makes WordPress write requests or runs the Production source job.
 */
define('ABSPATH','/ci-fixture/');
function add_action($hook,$callable,$priority=10):void {}
function wp_parse_url($url,$component=-1){return $component===-1?parse_url($url):parse_url($url,$component);}
function home_url($path=''):string{return 'https://www3.m3u8.one'.($path?:'/');}
function sanitize_key($s):string{return preg_replace('/[^a-z0-9_-]/','',strtolower((string)$s));}
function sanitize_text_field($s):string{return trim((string)$s);}
function wp_strip_all_tags($s):string{return strip_tags((string)$s);}
function wp_json_encode($data,$flags=0):string{return json_encode($data,$flags|JSON_THROW_ON_ERROR);}
function vf_ops_page_family_x_default_policy_for_url_v121439(string $url):array{
    if($url==='https://www3.m3u8.one/'){return [
        'family_id'=>94,'family_type'=>'language_specific','member_count'=>1,
        'state'=>'not_applicable','required'=>false,'target'=>'','strategy'=>'','languages'=>['en']
    ];}
    return ['family_id'=>0,'member_count'=>0,'state'=>'not_applicable','required'=>false,'target'=>''];
}
function vf_theme_get_hreflang_state($args):array{
    // AJAX context does not carry the public front-end home selector.
    return ['familyType'=>'home','xDefault'=>['state'=>'not_applicable','target'=>'','strategy'=>''],
        'map'=>[],'members'=>[]];
}
require dirname(__DIR__).'/target/includes/acceptance-o11/source-acceptance-product.php';
function check(bool $value,string $name):void{
    if(!$value){fwrite(STDERR,"FAIL $name\n");exit(1);}
    echo "PASS $name\n";
}
check(isset($argv[1],$argv[2]),'public pages provided');
$home=file_get_contents($argv[1]);$zh=file_get_contents($argv[2]);
check(is_string($home)&&strlen($home)>1000,'home HTTP body captured');
check(is_string($zh)&&strlen($zh)>1000,'zh HTTP body captured');
$canonical=function(string $html):array{return vf_ops_source_acceptance_links_v121427($html,'canonical');};
$alternates=function(string $html):array{
    return array_values(array_filter(vf_ops_source_acceptance_links_v121427($html,'alternate'),
        static fn($row)=>isset($row['hreflang'])));
};
$expected=[
    'en'=>'https://www3.m3u8.one/',
    'zh'=>'https://www3.m3u8.one/zh/',
    'x-default'=>'https://www3.m3u8.one/',
];
foreach([['en-root',$home,'https://www3.m3u8.one/'],['zh-root',$zh,'https://www3.m3u8.one/zh/']] as [$label,$html,$canonicalExpected]){
    $canon=$canonical($html);check(count($canon)===1&&($canon[0]['href']??'')===$canonicalExpected,$label.' canonical');
    $rows=$alternates($html);$map=[];foreach($rows as $row){$key=strtolower((string)$row['hreflang']);$map[$key][]=$row;}
    check(count($rows)===3&&count($map)===3,$label.' exactly three alternates');
    foreach($expected as $lang=>$target){
        check(count($map[$lang]??[])===1 && ($map[$lang][0]['href']??'')===$target
          && ($map[$lang][0]['data-vf-seo-head']??'')==='hreflang-single-writer',
          $label.' trusted '.$lang.' maps correctly');
    }
}
$source=vf_ops_source_acceptance_inspect_html_v121427(
    ['path'=>'/','owner'=>'vf-theme / Polylang'],200,$home,'text/html');
$issues=(array)($source['issues']??[]);
$codes=array_values(array_map(static fn($x)=>(string)($x['code']??''),$issues));
check(!in_array('x_default_policy',$codes,true),'1065 real public HTML no false x_default_policy P1');
check(!in_array('x_default_target_mismatch',$codes,true),'1065 real public HTML no fallback target mismatch');
check((int)($source['xDefaultCount']??0)===1,'Source inspector retains one x-default');
echo json_encode(['pass'=>true,'version'=>'1.21.1065','source_sha'=>'d3b98c05f4bdc621be311164072e7b7ee55517f2',
 'home_sha256'=>hash('sha256',$home),'zh_sha256'=>hash('sha256',$zh),
 'x_default_policy_p1'=>false,'other_issues'=>$codes,'production'=>'PUBLIC_READ_ONLY'],JSON_UNESCAPED_SLASHES)."\n";
