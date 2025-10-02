pageextension 50102 "ContactCard_AddLog" extends 5050 // Contact Card
{
    Caption = 'Contact Card - Registrar Interacción';

    actions
    {
        // ✅ Anclar justo después de la acción estándar "Email" (existe en 5050)
        addafter(Email)
        {
            action(RegisterEmailInteraction)
            {
                ApplicationArea = All;
                Caption = 'Registrar email interacción';
                Image = Email;

                // Asegura visibilidad en la cinta (también en el add-in)
                Promoted = true;
                PromotedCategory = Process;
                PromotedIsBig = true;

                trigger OnAction()
                var
                    Interaction: Record "Interaction Log Entry";
                    Template: Record "Interaction Template";
                    ContactNo: Code[20];
                    DescTxt: Text[250];
                    NextEntryNo: Integer;
                    DescDialog: Page "Interaction Desc Dialog";
                begin
                    // Validar contacto
                    ContactNo := Rec."No.";
                    if ContactNo = '' then begin
                        Message('No hay Nº de contacto en la ficha.');
                        exit;
                    end;

                    // Pedir texto al usuario
                    if DescDialog.RunModal() = Action::OK then
                        DescTxt := DescDialog.GetDescription()
                    else
                        exit; // cancelado

                    // Siguiente Nº mov.
                    Interaction.Reset();
                    Interaction.SetCurrentKey("Entry No.");
                    if Interaction.FindLast() then
                        NextEntryNo := Interaction."Entry No." + 1
                    else
                        NextEntryNo := 1;

                    // Insertar interacción
                    Interaction.Init();
                    Interaction."Entry No." := NextEntryNo;
                    Interaction.Validate("Contact No.", ContactNo);
                    Interaction.Validate("Date", Today());
                    Interaction.Validate(Description, CopyStr(DescTxt, 1, MaxStrLen(Interaction.Description)));
                    if Template.Get('EMAIL') then
                        Interaction.Validate("Interaction Template Code", Template.Code);
                    Interaction.Insert(true);

                    Message('Interacción registrada para %1 (Nº mov. %2).', Rec.Name, Interaction."Entry No.");
                end;

            }
        }

        // (Plan B si quieres aún más visibilidad)
        // addfirst(Processing)
        // {
        //     action(RegisterEmailInteractionAlt) { ... misma lógica ... }
        // }
    }
}

page 50137 "Interaction Desc Dialog"
{
    PageType = StandardDialog;
    Caption = 'Descripción de Interacción';

    layout
    {
        area(content)
        {
            field(DescriptionTxt; DescriptionTxt)
            {
                ApplicationArea = All;
                Caption = 'Descripción';
            }
        }
    }

    var
        DescriptionTxt: Text[250];

    procedure GetDescription(): Text[250]
    begin
        exit(DescriptionTxt);
    end;
}

