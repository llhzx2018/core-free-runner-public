<?php
require_once ABSPATH.'wp-admin/includes/template.php';
if (!defined('POLYLANG_DIR') || !function_exists('PLL')) { throw new Exception('SYNTHETIC_SEED_POLYLANG_NOT_LOADED'); }
// Use the installed plugin autoloader; current versions moved classes to src/.
if (!class_exists('PLL_Admin_Model')) { throw new Exception('SYNTHETIC_SEED_ADMIN_MODEL_NOT_LOADED'); }
$model = new PLL_Admin_Model(PLL()->options);
foreach ([['en','en_US','English','us'],['zh','zh_CN','中文','cn']] as $language) {
    if (!$model->get_language($language[0])) {
        $result=$model->add_language(['slug'=>$language[0],'locale'=>$language[1],'name'=>$language[2],'flag'=>$language[3],'rtl'=>0,'term_group'=>0]);
        if (is_wp_error($result)) { throw new Exception('SYNTHETIC_SEED_LANGUAGE: '.$result->get_error_code()); }
    }
}
$options=get_option('polylang',[]);$options['default_lang']='en';$options['hide_default']=1;$options['force_lang']=1;update_option('polylang',$options);

