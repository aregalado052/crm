page 50191 "UpdateContactAPI"
{
    PageType = API;
    APIPublisher = 'planet';
    APIGroup = 'sales';
    APIVersion = 'v1.0';

    EntityName = 'updateContact';
    EntitySetName = 'updateContacts';

    SourceTable = "UpdateContactBufferV1";
    DelayedInsert = true;

    layout
    {
        area(content)
        {
            repeater(Group)
            {
                field(entryNo; Rec."Entry No.") { Editable = false; }
                field(quoteNo; Rec."QuoteNo") { }
                field(billToName; Rec."Bill-to Name") { }
                field(address; Rec."Address") { }
                field(address2; Rec."Address2") { }
                field(postCode; Rec."PostCode") { }
                field(city; Rec."City") { }
                field(vatRegNo; Rec."VATRegNo") { }
                field(foreignRegNo; Rec."ForeignRegNo") { }

                // Respuesta
                field(ok; Rec."OK") { Editable = false; }
                field(message; Rec."Message") { Editable = false; }
            }
        }
    }

    trigger OnInsertRecord(BelowxRec: Boolean): Boolean
    var
        Logic: Codeunit "SalesQuoteLogic";
    begin
        Logic.UpdateContactFromQuote(
            Rec."Bill-to Name",
            Rec."QuoteNo",
            Rec."Address",
            Rec."Address2",
            Rec."PostCode",
            Rec."City",
            Rec."VATRegNo",
            Rec."ForeignRegNo"
        );

        Rec."OK" := true;
        Rec."Message" := 'Contacto actualizado';

        exit(true);
    end;


}
pageextension 50196 "ContactCardExt_WP" extends "Contact Card"
{
    layout
    {
        // Añadir campos al final del grupo General
        addlast(General)
        {
            field(WP_VATRegNo_Edit; Rec."VAT Registration No.")
            {
                ApplicationArea = All;
                Caption = 'VAT Registration No.';
                Editable = true;
            }

            field(WP_ForeignRegNo; Rec."Foreign Registration No.")
            {
                ApplicationArea = All;
                Caption = 'Foreign Registration No.';
                Editable = true;
            }
        }
    }
}

page 50642 "SendProformaAPI"
{
    PageType = API;
    APIPublisher = 'planet';
    APIGroup = 'sales';
    APIVersion = 'v1.0';

    EntityName = 'sendProforma';
    EntitySetName = 'sendProformas';


    SourceTable = "ProformaTransferBuffer";
    DelayedInsert = true;

    layout
    {
        area(content)
        {
            repeater(Group)
            {
                field(entryNo; Rec."Entry No.") { Editable = false; }

                field(quoteNo; Rec."QuoteNo") { }
                field(sessionId; Rec."SessionId") { }
                field(url; Rec."Url") { }
                field(bd; Rec."BD") { }

                field(ok; Rec."OK") { Editable = false; }
                field(message; Rec."Message") { Editable = false; }
            }
        }
    }

    trigger OnInsertRecord(BelowxRec: Boolean): Boolean
    var
        Sender: Codeunit "SendProformaPDFToLambda";
    begin
        // Ejecuta: genera PDF con layout proforma y lo envía a Lambda
        Sender.SendProformaPDF(
            Rec."QuoteNo",
            Rec."SessionId",
            Rec."Url",
            Rec."BD"
        );

        Rec."OK" := true;
        Rec."Message" := 'Proforma enviada correctamente';

        exit(true);
    end;
}


