<?php
// Disposable synthetic shortcode: rendering a summary must never execute it.
add_shortcode('vf_summary_probe',static function(){update_option('vf_summary_probe_called','executed');return 'SHORTCODE_EXECUTED_UNEXPECTEDLY';});
