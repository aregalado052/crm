tableextension 50121 "Sales Header Discounts" extends "Sales Header"
{
    fields
    {
        field(50108; "Skip Header Discounts"; Boolean)
        {
            Caption = 'Skip Header Discounts';
            DataClassification = CustomerContent;
        }
        field(50127; "Volume Discount %"; Decimal)
        {
            Caption = 'Descuento volumen (%)';
            DataClassification = CustomerContent;
            MinValue = 0;
            MaxValue = 100;
            DecimalPlaces = 0: 5;

            trigger OnValidate()
            var
                Handler: Codeunit "Quote Discount Handler";
            begin
                // Si está activado el flag, no recalcular
                if Rec."Skip Header Discounts" then exit;
                Handler.ApplyHeaderDiscountsToLines(Rec);
            end;
        }
        field(50128; "Additional Discount %"; Decimal)
        {
            Caption = 'Descuento adicional (%)';
            DataClassification = CustomerContent;
            MinValue = 0;
            MaxValue = 100;
            DecimalPlaces = 0: 5;

            trigger OnValidate()
            var
                Handler: Codeunit "Quote Discount Handler";
            begin
                if Rec."Skip Header Discounts" then exit;
                Handler.ApplyHeaderDiscountsToLines(Rec);
            end;
        }
    }
}
