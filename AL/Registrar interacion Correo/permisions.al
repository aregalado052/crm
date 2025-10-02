permissionset 50120 "INTERACTION_WRITE"
{
    Assignable = true;
    Caption = 'Registrar Interacciones (Outlook/BC)';
    Permissions =
        tabledata Contact = R,
        tabledata "Interaction Log Entry" = RIM;

    // Añade más tablas si tu escenario lo requiere (comentarios, plantillas, etc.)
    // tabledata "Interaction Template" = R;
    // tabledata "Interaction Log Entry Comment Line" = RIM;
}
