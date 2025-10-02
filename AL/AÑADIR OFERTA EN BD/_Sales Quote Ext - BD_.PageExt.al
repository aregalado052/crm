pageextension 50194 "Sales Quote Ext - BD" extends "Sales Quote"
{
    layout
    {
        addlast(General)
        {
            group("Descuentos cabecera")
            {
                field("Skip Header Discounts"; Rec."Skip Header Discounts")
                {
                    ApplicationArea = All;
                    ToolTip = 'Si se activa, no se aplican descuentos de cabecera en cálculos/impresión; sólo se respetan los descuentos de línea.';
                }
                field("Volume Discount %"; Rec."Volume Discount %")
                {
                    ApplicationArea = All;
                    ToolTip = 'Descuento por volumen aplicado a todas las líneas (compuesto con el adicional).';
                }
                field("Additional Discount %"; Rec."Additional Discount %")
                {
                    ApplicationArea = All;
                    ToolTip = 'Descuento adicional aplicado a todas las líneas (compuesto con el de volumen).';
                }
            }
        }
    }
    actions
    {
        addlast(Processing)
        {
            action(SendToLambda)
            {
                ApplicationArea = All;
                Caption = 'Enviar a Oferta a CRM';
                Image = SendTo;
                Promoted = true;
                PromotedCategory = Process;
                PromotedIsBig = true;

                trigger OnAction()
                var
                    LambdaInvoker: Codeunit "AWS Lambda Invoker";
                begin
                    CurrPage.SaveRecord();
                    LambdaInvoker.InvokeForSalesQuote(Rec);
                end;
            }
        }
    }
}
