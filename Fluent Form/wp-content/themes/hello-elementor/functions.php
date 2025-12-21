<?php

/**
 * Theme functions and definitions
 *
 * @package HelloElementor
 */

if (! defined('ABSPATH')) {
    exit; // Exit if accessed directly.
}

define('HELLO_ELEMENTOR_VERSION', '3.4.4');
define('EHP_THEME_SLUG', 'hello-elementor');

define('HELLO_THEME_PATH', get_template_directory());
define('HELLO_THEME_URL', get_template_directory_uri());
define('HELLO_THEME_ASSETS_PATH', HELLO_THEME_PATH . '/assets/');
define('HELLO_THEME_ASSETS_URL', HELLO_THEME_URL . '/assets/');
define('HELLO_THEME_SCRIPTS_PATH', HELLO_THEME_ASSETS_PATH . 'js/');
define('HELLO_THEME_SCRIPTS_URL', HELLO_THEME_ASSETS_URL . 'js/');
define('HELLO_THEME_STYLE_PATH', HELLO_THEME_ASSETS_PATH . 'css/');
define('HELLO_THEME_STYLE_URL', HELLO_THEME_ASSETS_URL . 'css/');
define('HELLO_THEME_IMAGES_PATH', HELLO_THEME_ASSETS_PATH . 'images/');
define('HELLO_THEME_IMAGES_URL', HELLO_THEME_ASSETS_URL . 'images/');

if (! isset($content_width)) {
    $content_width = 800; // Pixels.
}

if (! function_exists('hello_elementor_setup')) {
    /**
     * Set up theme support.
     *
     * @return void
     */
    function hello_elementor_setup()
    {
        if (is_admin()) {
            hello_maybe_update_theme_version_in_db();
        }

        if (apply_filters('hello_elementor_register_menus', true)) {
            register_nav_menus(['menu-1' => esc_html__('Header', 'hello-elementor')]);
            register_nav_menus(['menu-2' => esc_html__('Footer', 'hello-elementor')]);
        }

        if (apply_filters('hello_elementor_post_type_support', true)) {
            add_post_type_support('page', 'excerpt');
        }

        if (apply_filters('hello_elementor_add_theme_support', true)) {
            add_theme_support('post-thumbnails');
            add_theme_support('automatic-feed-links');
            add_theme_support('title-tag');
            add_theme_support(
                'html5',
                [
                    'search-form',
                    'comment-form',
                    'comment-list',
                    'gallery',
                    'caption',
                    'script',
                    'style',
                    'navigation-widgets',
                ]
            );
            add_theme_support(
                'custom-logo',
                [
                    'height'      => 100,
                    'width'       => 350,
                    'flex-height' => true,
                    'flex-width'  => true,
                ]
            );
            add_theme_support('align-wide');
            add_theme_support('responsive-embeds');

            /*
			 * Editor Styles
			 */
            add_theme_support('editor-styles');
            add_editor_style('editor-styles.css');

            /*
			 * WooCommerce.
			 */
            if (apply_filters('hello_elementor_add_woocommerce_support', true)) {
                // WooCommerce in general.
                add_theme_support('woocommerce');
                // Enabling WooCommerce product gallery features (are off by default since WC 3.0.0).
                // zoom.
                add_theme_support('wc-product-gallery-zoom');
                // lightbox.
                add_theme_support('wc-product-gallery-lightbox');
                // swipe.
                add_theme_support('wc-product-gallery-slider');
            }
        }
    }
}
add_action('after_setup_theme', 'hello_elementor_setup');

function hello_maybe_update_theme_version_in_db()
{
    $theme_version_option_name = 'hello_theme_version';
    // The theme version saved in the database.
    $hello_theme_db_version = get_option($theme_version_option_name);

    // If the 'hello_theme_version' option does not exist in the DB, or the version needs to be updated, do the update.
    if (! $hello_theme_db_version || version_compare($hello_theme_db_version, HELLO_ELEMENTOR_VERSION, '<')) {
        update_option($theme_version_option_name, HELLO_ELEMENTOR_VERSION);
    }
}

if (! function_exists('hello_elementor_display_header_footer')) {
    /**
     * Check whether to display header footer.
     *
     * @return bool
     */
    function hello_elementor_display_header_footer()
    {
        $hello_elementor_header_footer = true;

        return apply_filters('hello_elementor_header_footer', $hello_elementor_header_footer);
    }
}

if (! function_exists('hello_elementor_scripts_styles')) {
    /**
     * Theme Scripts & Styles.
     *
     * @return void
     */
    function hello_elementor_scripts_styles()
    {
        if (apply_filters('hello_elementor_enqueue_style', true)) {
            wp_enqueue_style(
                'hello-elementor',
                HELLO_THEME_STYLE_URL . 'reset.css',
                [],
                HELLO_ELEMENTOR_VERSION
            );
        }

        if (apply_filters('hello_elementor_enqueue_theme_style', true)) {
            wp_enqueue_style(
                'hello-elementor-theme-style',
                HELLO_THEME_STYLE_URL . 'theme.css',
                [],
                HELLO_ELEMENTOR_VERSION
            );
        }

        if (hello_elementor_display_header_footer()) {
            wp_enqueue_style(
                'hello-elementor-header-footer',
                HELLO_THEME_STYLE_URL . 'header-footer.css',
                [],
                HELLO_ELEMENTOR_VERSION
            );
        }
    }
}
add_action('wp_enqueue_scripts', 'hello_elementor_scripts_styles');

if (! function_exists('hello_elementor_register_elementor_locations')) {
    /**
     * Register Elementor Locations.
     *
     * @param ElementorPro\Modules\ThemeBuilder\Classes\Locations_Manager $elementor_theme_manager theme manager.
     *
     * @return void
     */
    function hello_elementor_register_elementor_locations($elementor_theme_manager)
    {
        if (apply_filters('hello_elementor_register_elementor_locations', true)) {
            $elementor_theme_manager->register_all_core_location();
        }
    }
}
add_action('elementor/theme/register_locations', 'hello_elementor_register_elementor_locations');

if (! function_exists('hello_elementor_content_width')) {
    /**
     * Set default content width.
     *
     * @return void
     */
    function hello_elementor_content_width()
    {
        $GLOBALS['content_width'] = apply_filters('hello_elementor_content_width', 800);
    }
}
add_action('after_setup_theme', 'hello_elementor_content_width', 0);

if (! function_exists('hello_elementor_add_description_meta_tag')) {
    /**
     * Add description meta tag with excerpt text.
     *
     * @return void
     */
    function hello_elementor_add_description_meta_tag()
    {
        if (! apply_filters('hello_elementor_description_meta_tag', true)) {
            return;
        }

        if (! is_singular()) {
            return;
        }

        $post = get_queried_object();
        if (empty($post->post_excerpt)) {
            return;
        }

        echo '<meta name="description" content="' . esc_attr(wp_strip_all_tags($post->post_excerpt)) . '">' . "\n";
    }
}
add_action('wp_head', 'hello_elementor_add_description_meta_tag');

// Settings page
require get_template_directory() . '/includes/settings-functions.php';

// Header & footer styling option, inside Elementor
require get_template_directory() . '/includes/elementor-functions.php';

if (! function_exists('hello_elementor_customizer')) {
    // Customizer controls
    function hello_elementor_customizer()
    {
        if (! is_customize_preview()) {
            return;
        }

        if (! hello_elementor_display_header_footer()) {
            return;
        }

        require get_template_directory() . '/includes/customizer-functions.php';
    }
}
add_action('init', 'hello_elementor_customizer');

if (! function_exists('hello_elementor_check_hide_title')) {
    /**
     * Check whether to display the page title.
     *
     * @param bool $val default value.
     *
     * @return bool
     */
    function hello_elementor_check_hide_title($val)
    {
        if (defined('ELEMENTOR_VERSION')) {
            $current_doc = Elementor\Plugin::instance()->documents->get(get_the_ID());
            if ($current_doc && 'yes' === $current_doc->get_settings('hide_title')) {
                $val = false;
            }
        }
        return $val;
    }
}
add_filter('hello_elementor_page_title', 'hello_elementor_check_hide_title');

/**
 * BC:
 * In v2.7.0 the theme removed the `hello_elementor_body_open()` from `header.php` replacing it with `wp_body_open()`.
 * The following code prevents fatal errors in child themes that still use this function.
 */
if (! function_exists('hello_elementor_body_open')) {
    function hello_elementor_body_open()
    {
        wp_body_open();
    }
}

require HELLO_THEME_PATH . '/theme.php';

HelloTheme\Theme::instance();

add_action('fluentform/submission_inserted', function ($entryId, $formData, $form) {
    error_log("🔥 HOOK submission_inserted DISPARADO. form_id=" . ($form->id ?? 'null') . " entryId=" . $entryId);
    error_log("🔑 keys: " . implode(',', array_keys((array)$formData)));
}, 1, 3);


// === Idioma igual que antes (ES vs Ingles) ===
if (!function_exists('bc_current_lang')) {
    function bc_current_lang()
    {
        // 1) Polylang
        if (function_exists('pll_current_language')) {
            $l = pll_current_language('slug');
            if ($l) return $l;
        }

        // 2) WPML
        if (defined('ICL_LANGUAGE_CODE') && ICL_LANGUAGE_CODE) {
            return ICL_LANGUAGE_CODE;
        }

        // 3) Locale de WordPress (si el sitio cambia locale por idioma)
        if (function_exists('determine_locale')) {
            $loc = determine_locale(); // ej: en_US, es_ES
        } else {
            $loc = get_locale();
        }
        $loc2 = strtolower(substr($loc, 0, 2));
        if (in_array($loc2, ['es', 'en', 'fr', 'it'], true)) return $loc2;

        // 4) Detectar por URL /en/ /fr/ /it/
        $uri = $_SERVER['REQUEST_URI'] ?? '';
        if (preg_match('#^/(en|fr|it)(/|$)#i', $uri, $m)) {
            return strtolower($m[1]);
        }

        // fallback
        return 'es';
    }
}

function bc_detect_lang_from_path($path)
{
    $path = $path ?: '';
    $path = strtolower($path);

    // casos típicos: /en/, /fr/, /it/
    if (preg_match('#^/(en|fr|it)(/|$)#', $path, $m)) {
        return $m[1];
    }

    // si usas querystring tipo ?lang=en
    if (!empty($_GET['lang'])) {
        $q = strtolower($_GET['lang']);
        if (in_array($q, ['es', 'en', 'fr', 'it'], true)) return $q;
    }

    // si tu inglés es /contact/ y español /contacto/
    // (ajusta si aplica a tu web)
    if (strpos($path, '/contact/') !== false) return 'en';
    if (strpos($path, '/contacto/') !== false) return 'es';

    return null;
}


function bc_get_country_by_lang($formData, $slug)
{

    $key_by_lang = [
        'es' => 'paises_es',
        'en' => 'paises_en',
        'fr' => 'paises_fr',
        'it' => 'paises_it',
    ];

    $key = $key_by_lang[$slug] ?? 'paises_es';

    $pais_raw = $formData[$key] ?? '';

    if (is_array($pais_raw) && count($pais_raw) > 0) {
        $pais = sanitize_text_field($pais_raw[0]);
    } elseif (is_string($pais_raw)) {
        $pais = sanitize_text_field($pais_raw);
    } else {
        $pais = '';
    }

    return [$pais, $key];
}





if (!function_exists('bc_lang_label')) {
    function bc_lang_label($slug)
    {


        return [
            'es' => "Esp",
            'en' => 'Ingles',
            'fr' => 'Frances',
            'it' => 'Italiano',
        ][$slug] ?? $slug;
    }
}

// === VALIDACIÓN Fluent Forms (Form ID 6) ===
add_filter('fluentform/validation_errors', function ($errors, $formData, $form, $fields) {



    if (empty($form->id) || intval($form->id) !== 6) {
        return $errors;
    }

    // Keys (Atributo de nombre)
    $key_nombre = 'nombre';
    $key_email  = 'email';

    $key_pp     = 'numeric_field_1';
    $key_pl     = 'numeric_field';

    $nombre = sanitize_text_field($formData[$key_nombre] ?? '');
    $email  = sanitize_email($formData[$key_email] ?? '');

    $ref  = $formData['_wp_http_referer'] ?? '';
    $slug = bc_detect_lang_from_path($ref) ?: bc_current_lang();

    list($pais, $key_pais) = bc_get_country_by_lang($formData, $slug);

    if ($pais === '') {
        $errors[$key_pais] = ['Selecciona un país válido.'];
    }


    $pistasPerimetrales = intval($formData[$key_pp] ?? 0);
    $pistasLaterales    = intval($formData[$key_pl] ?? 0);

    // Logs de depuración (cuando ya funcione, puedes quitarlos)
    error_log("?? FF Datos recibidos: " . print_r($formData, true));
    error_log("?? FF Nombre: $nombre");
    error_log("?? FF Email: $email");
    error_log("?? FF País: [$pais]");
    error_log("?? FF Pistas Perimetrales: $pistasPerimetrales");
    error_log("?? FF Pistas Laterales: $pistasLaterales");

    if ($nombre === '') {
        $errors[$key_nombre] = ['Por favor, introduce tu nombre.'];
    }

    if ($email === '' || !is_email($email)) {
        $errors[$key_email] = ['Introduce un email válido.'];
    }

    // En Fluent Forms mejor validar por vacío (no por texto del placeholder)
    if ($pais === '' || $pais === 'Selecciona un país') {
        $errors[$key_pais] = ['Selecciona un país válido.'];
    }

    if ($pistasPerimetrales <= 0 && $pistasLaterales <= 0) {
        $errors[$key_pp] = ['Debes indicar al menos una pista.'];
        $errors[$key_pl] = ['Debes indicar al menos una pista.'];
    }

    return $errors;
}, 10, 4);

// === ENVÍO a tu API (Form ID 6) ===
add_action('fluentform/submission_inserted', function ($entryId, $formData, $form) {

    if (empty($form->id) || intval($form->id) !== 6) {
        return;
    }

    $nombre = sanitize_text_field($formData['nombre'] ?? '');
    $email  = sanitize_email($formData['email'] ?? '');

    // País array/string
    $ref  = $formData['_wp_http_referer'] ?? '';
    $slug = bc_detect_lang_from_path($ref) ?: bc_current_lang();

    list($pais, $key_pais) = bc_get_country_by_lang($formData, $slug);

    // LOG para verificar
    error_log("🌍 Pais detectado: slug={$slug} key={$key_pais} valor={$pais}");


    $pistasPerimetrales = intval($formData['numeric_field_1'] ?? 0);
    $pistasLaterales    = intval($formData['numeric_field'] ?? 0);

    // Idioma EXACTAMENTE como antes
    $ref = $formData['_wp_http_referer'] ?? '';   // ej: /contacto/ o /en/contact/
    $slug = bc_detect_lang_from_path($ref);

    if (!$slug) {
        // fallback a tu función anterior si no lo detecta por URL
        $slug = bc_current_lang();
    }

    $idiom = bc_lang_label($slug);

    // LOG para confirmar
    error_log("🌍 REF={$ref} | slug={$slug} | idiom={$idiom}");
    error_log('🔑 FF keys: ' . implode(',', array_keys($formData)));


    $idiom = mb_convert_encoding($idiom, 'UTF-8', 'UTF-8');

    $body = wp_json_encode([
        'name'                => $nombre,
        'email'               => $email,
        'idioma'              => $idiom,
        'pais'                => $pais,
        'pistas_perimetrales' => $pistasPerimetrales,
        'pistas_laterales'    => $pistasLaterales,
        'mailorigen'          => 'soporte@planetpower.es',
        'origen'              => 'web_wp_formulario_contacto',
    ], JSON_UNESCAPED_UNICODE);

    error_log("?? FF JSON enviado a backend: $body");

    $api_url = 'https://eufmhxy9qg.execute-api.eu-north-1.amazonaws.com/procesarFormularioContacto';
    $api_key = 'dEWUTmYOie8LPAQCDS4dt4eCJ2Mvm3xa8whtWxbS';  // API Key segura
    //$api_url = 'https://1ded59ee512e.ngrok-free.app/api/contacto';

    $response = wp_remote_post($api_url, [
        'method'  => 'POST',
        'headers' => [
            'Content-Type' => 'application/json',
            'x-api-key'    => $api_key
        ],
        'body'    => $body,
        'timeout' => 10
    ]);

    if (is_wp_error($response)) {
        error_log('? Error enviando datos a BC (FF): ' . $response->get_error_message());
        return;
    }

    $code    = wp_remote_retrieve_response_code($response);
    $resBody = wp_remote_retrieve_body($response);
    error_log("? Respuesta de BC (FF) ($code): $resBody");
}, 10, 3);
