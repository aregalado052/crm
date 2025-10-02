page 50174 "SalesQuoteAPI"
{
    PageType = API;
    APIPublisher = 'planet';
    APIGroup = 'sales';
    APIVersion = 'v1.0';
    EntityName = 'createQuote';
    EntitySetName = 'createQuotes';
    SourceTable = "SalesQuoteBufferV2"; // Asegúrate de que el nombre coincide con tu tabla
    DelayedInsert = true;

    layout
    {
        area(content)
        {
            group(Group)
            {
                field(No; Rec."No.")
                {
                    Caption = 'Quote No.';
                }
                field(CustomerName; Rec."CustomerName")
                {
                }
                field(CustomerEmail; Rec."CustomerEmail")
                {
                }
                field(CustomerTemplate; Rec."CustomerTemplateName")
                {
                }
                field(CustomerCountryCode; Rec."CustomerCountryCode")
                {
                }
                field(CodIdioma; Rec."CodIdioma")
                {
                }
                // Parámetro para saltar descuentos (campo en la tabla buffer)
                field(skipHeaderDiscounts; Rec."Skip Header Discounts")
                {
                    ApplicationArea = All;
                    Caption = 'skipHeaderDiscounts';
                    Editable = true;
                }
            }
        }
    }
    actions
    {
        area(processing)
        {
            action(Create)
            {
                ApplicationArea = All;
                Caption = 'Create Quote';

                trigger OnAction()
                var
                    QuoteLogic: Codeunit "SalesQuoteLogic";
                    Result: Text;
                begin
                    Result:=QuoteLogic.CreateQuote(Rec."CustomerName", Rec."CustomerEmail", Rec."CustomerTemplateName", Rec."CustomerCountryCode", Rec."CodIdioma");
                    Message(Result);
                end;
            }
            action(Confirm)
            {
                Caption = 'Confirm Quote';
                ApplicationArea = All;

                trigger OnAction()
                var
                    QuoteLogic: Codeunit "SalesQuoteLogic";
                    Result: Code[20];
                begin
                    Result:=QuoteLogic.CreateQuote(Rec."CustomerName", Rec."CustomerEmail", Rec."CustomerTemplateName", Rec."CustomerCountryCode", Rec."CodIdioma");
                    Message('Oferta creada: %1', Result);
                end;
            }
        }
    }
    trigger OnInsertRecord(BelowxRec: Boolean): Boolean var
        QuoteLogic: Codeunit "SalesQuoteLogic";
        Result: Code[20];
        Sh: Record "Sales Header";
    begin
        // Crear la oferta
        Result:=QuoteLogic.CreateQuote(Rec."CustomerName", Rec."CustomerEmail", Rec."CustomerTemplateName", Rec."CustomerCountryCode", Rec."CodIdioma");
        Rec."No.":=Result;
        // Si el buffer viene marcado, trasladar la marca a la cabecera real
        if Rec."Skip Header Discounts" then if Sh.Get(Sh."Document Type"::Quote, Result)then begin
                Sh."Skip Header Discounts":=true;
                Sh.Modify(true);
                Message('SKIP marcado en %1', Sh."No."); // <-- borrar después
            end;
        exit(false); // no insertar registro en la tabla buffer
    end;
}
