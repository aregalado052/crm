/**
* Fluent Forms -> enviar a backend cuando se inserta la submission
* Solo para el formulario ID 6
*/

/**
* VALIDACIONES Fluent Forms - SOLO Form ID 6
* Reemplaza los keys (email, country, language, pistas...) por tus "Atributo de nombre"
*/
add_filter('fluentform/validation_errors', function ($errors, $formData, $form, $fields) {

if (empty($form->id) || intval($form->id) !== 6) {
return $errors;
}

// ✅ Keys (Atributo de nombre) - ajusta estos según tu formulario
$key_nombre = 'names'; // ya confirmado
$key_email = 'email'; // <-- cambia si tu atributo de nombre es otro

    $key_pais='country' ; // <-- cambia
    $key_pp='pistas-perimetrales' ; // <-- cambia (si tu name es distinto)
    $key_pl='pistas-laterales' ; // <-- cambia

    $nombre=sanitize_text_field($formData[$key_nombre] ?? '' );
    $email=sanitize_email($formData[$key_email] ?? '' );

    $pais=sanitize_text_field($formData[$key_pais] ?? '' );

    $pistasPerimetrales=intval($formData[$key_pp] ?? 0);
    $pistasLaterales=intval($formData[$key_pl] ?? 0);

    // Nombre obligatorio
    if ($nombre==='' ) {
    $errors[$key_nombre]=['Por favor, introduce tu nombre.'];
    }

    // Email obligatorio y válido
    if ($email==='' || !is_email($email)) {
    $errors[$key_email]=['Introduce un email válido.'];
    }



    // País obligatorio
    if ($pais==='' || $pais==='Selecciona un país' ) {
    $errors[$key_pais]=['Selecciona un país válido.'];
    }

    // Al menos una pista
    if ($pistasPerimetrales <=0 && $pistasLaterales <=0) {
    $errors[$key_pp]=['Debes indicar al menos una pista.'];
    $errors[$key_pl]=['Debes indicar al menos una pista.'];
    }

    return $errors;

    }, 10, 4);




    add_action('fluentform/submission_inserted', function ($entryId, $formData, $form) {

    // 1) Filtra SOLO el formulario de contacto (ID=6)
    if (empty($form->id) || intval($form->id) !== 6) {
    return;
    }

    // 2) Lee campos por "Atributo de nombre" (input key)
    // ✅ Ya sabemos que el nombre es: names
    $nombre = sanitize_text_field($formData['names'] ?? '');

    // ⚠️ CAMBIA estos keys por los tuyos reales (Atributo de nombre)
    $email = sanitize_email($formData['email'] ?? '');
    $pais = sanitize_text_field($formData['country-list'] ?? ''); // ej: country / pais / your_country
    $idiom = sanitize_text_field($formData['form_lang'] ?? '');

    $pistasPerimetrales = intval($formData['numeric_filed_1'] ?? 0);
    $pistasLaterales = intval($formData['pistas-laterales'] ?? 0);

    // 3) Si quieres usar el idioma del sitio (Polylang/WPML), como hacías antes:
    if (function_exists('bc_current_lang') && function_exists('bc_lang_label')) {
    $idioma_slug = bc_current_lang();
    $idiom = bc_lang_label($idioma_slug);
    }

    $body = wp_json_encode([
    'name' => $nombre,
    'email' => $email,
    'idioma' => $idiom,
    'pais' => $pais,
    'pistas_perimetrales' => $pistasPerimetrales,
    'pistas_laterales' => $pistasLaterales,
    'mailorigen' => 'soporte@planetpower.es',
    'origen' => 'web_wp_formulario_contacto',
    ]);

    error_log("📤 FluentForms JSON enviado a backend (form 6): " . $body);

    $api_url = 'https://eufmhxy9qg.execute-api.eu-north-1.amazonaws.com/procesarFormularioContacto';
    $api_key = 'PON_AQUI_TU_API_KEY'; // ⚠️ recomendable moverla a wp-config (constante) y leerla aquí

    $response = wp_remote_post($api_url, [
    'headers' => [
    'Content-Type' => 'application/json',
    'x-api-key' => $api_key
    ],
    'body' => $body,
    'timeout' => 10
    ]);

    if (is_wp_error($response)) {
    error_log('❌ Error enviando datos a BC (FluentForms): ' . $response->get_error_message());
    return;
    }

    $code = wp_remote_retrieve_response_code($response);
    $resBody = wp_remote_retrieve_body($response);
    error_log("✅ Respuesta de BC (FluentForms) ($code): $resBody");

    }, 10, 3);