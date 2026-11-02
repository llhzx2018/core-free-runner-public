<?php
$data=vf_m3u8_copy_data();
$tests=0;
foreach (['zh','en'] as $lang) {
  $copy=$data;
  foreach ($copy['labels'] as &$row) {
    if (($row['toolId']??'')==='test-links' && ($row['language']??'')===$lang) {
      $row['inputLabel']='CUSTOM SOURCE '.$lang;
      $row['primaryAction']='CUSTOM ACTION '.$lang;
      $row['resultLabels']['empty']='CUSTOM EMPTY '.$lang;
    }
  }
  unset($row);
  $projected=vf_m3u8_copy_runtime_projection($copy);
  $key=vf_m3u8_copy_row_key('test-links',$lang);
  $row=$projected['normalized'][$key]??[];
  if (($row['inputLabel']??'')!=='CUSTOM SOURCE '.$lang ||
      ($row['primaryAction']??'')!=='CUSTOM ACTION '.$lang ||
      ($row['resultLabels']['empty']??'')!=='CUSTOM EMPTY '.$lang) {
      throw new RuntimeException('custom labels not preserved for '.$lang);
  }
  $tests++;
}
echo wp_json_encode(['status'=>'PASS','custom_languages'=>$tests,'production'=>'untouched']);
