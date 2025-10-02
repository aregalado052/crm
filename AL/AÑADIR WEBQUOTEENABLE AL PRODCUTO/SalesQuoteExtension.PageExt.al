pageextension 50169 SalesQuoteExtension extends "Sales Quote"
{
    layout
    {
        addlast(General)
        {
            group("Oferta Web")
            {
                Caption = 'Oferta Web';

                field(WebQuotationField; Rec."WebQuotation")
                {
                    ApplicationArea = All;
                    Caption = 'Cotización realizada por la Web';
                }
            }
        }
    }
}
