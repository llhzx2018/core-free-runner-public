<?php
// Only a declared synthetic context, never Production integration evidence.
if(!defined('VF_WP_UPDATE_TEST_MODE')||VF_WP_UPDATE_TEST_MODE!==true)return;
add_filter('vf_tools_m3u8_platform_compatibility_context',function($v){return get_option('vf_runner_overview_context')==='known'?['known'=>true,'production_usage'=>'SYNTHETIC_ISOLATED_CONTEXT','dependents'=>[]]:['known'=>false,'production_usage'=>'SYNTHETIC_UNKNOWN_EXTERNAL_OWNER','dependents'=>[]];},999);
add_filter('vf_tools_m3u8_provider_production_dependents',function($v){return get_option('vf_runner_overview_context')==='known'?['known'=>true,'dependents'=>[],'meaning'=>'SYNTHETIC_NOT_PRODUCTION']:['known'=>false,'dependents'=>[]];},999);

