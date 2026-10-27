<?php
$path='/tmp/sitemap-settings-original.json';if(!file_exists($path))file_put_contents($path,wp_json_encode(get_option('vf_theme_layout',[])));
$layout=json_decode(file_get_contents($path),true);$mode=$args[0]??'restore';$row=$layout['moduleSettings']['html_sitemap']['post_list'];
if($mode==='two')$row['sitemap_columns']=2;
if($mode==='toggles'){
 $row['sitemap_columns']=2;$row['show_sitemap_counts']=false;$row['show_sitemap_updated']=false;$row['show_sitemap_tools']=false;$row['show_sitemap_release_paths']=false;
 $row['title']='Authored directory heading';$row['description']='Authored directory description preserved.';
}
if($mode==='empty')foreach(array_keys($row)as$key)if(str_starts_with($key,'show_sitemap_'))$row[$key]=false;
if($mode!=='restore')$layout['moduleSettings']['html_sitemap']['post_list']=$row;
update_option('vf_theme_layout',$layout);
