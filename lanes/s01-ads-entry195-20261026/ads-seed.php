<?php
$layout=get_option('vf_theme_layout',[]);$layout['guideReading']['sidebarMode']='contextual';update_option('vf_theme_layout',$layout);
if(!username_exists('ads-reader')){$id=wp_create_user('ads-reader','Synthetic-Reader-54!','reader@example.invalid');if(is_wp_error($id))throw new RuntimeException('READER_FIXTURE_FAILED');(new WP_User($id))->set_role('subscriber');}

require_once get_template_directory().'/inc/admin/admin-tab-registry.php';
if(count(vf_theme_admin_tab_registry())!==8||count(vf_tools_theme_component_workspace_manifest()['tabs'])!==8)throw new RuntimeException('PRIMARY_CAPABILITY_COUNT_CHANGED');
if(vf_theme_admin_legacy_tab_aliases()['ads']!=='layout'||!str_contains(vf_theme_admin_tab_url('ads'),'view=ads'))throw new RuntimeException('AD_ENTRY_ROUTE_INVALID');
