page 50176 "SalesQuoteLineAPI"
{
    PageType = API;
    DelayedInsert = true;
    APIPublisher = 'planet';
    APIGroup = 'sales';
    APIVersion = 'v1.0';
    EntityName = 'quoteLine';
    EntitySetName = 'quoteLines';
    SourceTable = "Sales Line";

    layout
    {
        area(content)
        {
            group(Group)
            {
                field(documentNo; Rec."Document No.")
                {
                }
                field(type; Rec."Type")
                {
                }
                field(lineNo; Rec."Line No.")
                {
                }
                field(itemNo; Rec."No.")
                {
                }
                field(description; Rec.Description)
                {
                }
                field(quantity; Rec.Quantity)
                {
                }
                field(unitPrice; Rec."Unit Price")
                {
                }
                field(lineDiscount; Rec."Line Discount %")
                {
                }
                field(locationCode; Rec."Location Code")
                {
                }
                // Campo virtual, no persistente
                field(isLastLine; IsLastLine)
                {
                    Caption = 'Es última línea';
                    ApplicationArea = All;
                }
                field(session_id; SessionId)
                {
                    Caption = 'ID de sesión';
                    ApplicationArea = All;
                }
                field(url; Url)
                {
                    Caption = 'URL Ofetas';
                    ApplicationArea = All;
                }
                field(bd; BD)
                {
                    Caption = 'BD';
                    ApplicationArea = All;
                }
            }
        }
    }
    var SessionId: Text;
    Url: Text;
    BD: Text;
    IsLastLine: Boolean;
    PDFSender: Codeunit "SendQuotePDFToLambda";
    trigger OnInsertRecord(BelowxRec: Boolean): Boolean var
        SalesLine: Record "Sales Line";
        Sh: Record "Sales Header";
        Handler: Codeunit "Quote Discount Handler";
        HasAmountLine: Boolean;
    begin
        if SalesLine.Get(SalesLine."Document Type"::Quote, Rec."Document No.", Rec."Line No.")then Error('La línea ya existe para el documento %1', Rec."Document No.");
        SalesLine.Init();
        SalesLine."Document Type":=SalesLine."Document Type"::Quote;
        SalesLine."Document No.":=Rec."Document No.";
        SalesLine."Line No.":=Rec."Line No.";
        SalesLine."Type":=Rec."Type";
        // ¿Es una línea con importes (no comentario)?
        HasAmountLine:=SalesLine.Type <> SalesLine.Type::" ";
        // Orden correcto de VALIDATE para que BC precalcule bien
        if HasAmountLine then begin
            SalesLine.Validate("No.", Rec."No.");
            SalesLine.Validate(Quantity, Rec.Quantity);
            SalesLine.Validate("Unit Price", Rec."Unit Price");
        end;
        // Inserta primero SIEMPRE
        SalesLine.Insert(true);
        // Copia campos "de texto" y ubicación
        SalesLine."Location Code":='OSES';
        SalesLine.Description:=Rec.Description;
        SalesLine.Modify(true);
        // === Rama según flag en cabecera ===
        if Sh.Get(Sh."Document Type"::Quote, Rec."Document No.")then begin
            if Sh."Skip Header Discounts" then begin
                // RESPETAR lo que venga en la API SOLO si es línea de importe
                if HasAmountLine then begin
                    // DEBUG: ver qué llegó realmente en el payload OData
                    Session.LogMessage('LD_IN', StrSubstNo('...'), Verbosity::Normal, DataClassification::CustomerContent, TelemetryScope::ExtensionPublisher, 'Source', 'SalesQuoteLineAPI', 'Company', CompanyName);
                    SalesLine.Validate("Line Discount %", Rec."Line Discount %");
                    SalesLine.Modify(true);
                end;
            end
            else
            begin
                // NO respetar el valor enviado: aplicar descuento global
                Handler.ApplyHeaderDiscountsToLines(Sh);
            end;
        end;
        if IsLastLine then begin
            // 1) Llamar al codeunit para mandar el PDF
            PDFSender.SendQuotePDF(Rec."Document No.", SessionId, Url, BD);
            // 2) Desmarcar el flag en la cabecera real para futuras modificaciones
            Sh.Reset();
            if Sh.Get(Sh."Document Type"::Quote, Rec."Document No.")then begin
                Sh."Skip Header Discounts":=False;
                Sh.Modify(true);
            end;
        end;
        exit(false);
    end;
}
