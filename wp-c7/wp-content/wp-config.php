<?php
define('DB_NAME', 'local');
define('DB_USER', 'root');
define('DB_PASSWORD', 'root');
define('DB_HOST', '127.0.0.1:10013');


$table_prefix = 'servmask_prefix_';

define('WP_HOME', 'http://myproject.local/');
define('WP_SITEURL', 'http://myproject.local/');


define('WP_DEBUG', false);
define('WP_DEBUG_DISPLAY', false);
define('WP_DEBUG_LOG', false);
define('SCRIPT_DEBUG', false);



@ini_set('display_errors', 0);

define('WP_ENVIRONMENT_TYPE', 'local');

define('WP_CONTENT_DIR', 'C:/Desarrollo/crm/wp-c7/wp-content');
define('WP_CONTENT_URL', 'http://myproject.local/wp-content');

/** ¡NO poner nada debajo de aquí! */
if (! defined('ABSPATH')) {
    define('ABSPATH', __DIR__ . '/');
}
require_once ABSPATH . 'wp-settings.php';
