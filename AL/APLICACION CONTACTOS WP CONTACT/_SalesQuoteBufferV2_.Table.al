table 50123 "SalesQuoteBufferV2"
{
    DataClassification = ToBeClassified;

    fields
    {
        field(1; "No."; Code[20])
        {
            DataClassification = CustomerContent;
        }
        field(2; "CustomerName"; Text[100])
        {
        }
        field(3; "CustomerEmail"; Text[100])
        {
        }
        field(4; "CustomerTemplateName"; Code[40])
        {
            Caption = 'Customer Template';
        }
        field(5; "CustomerCountryCode"; Code[40])
        {
            Caption = 'Customer Country Code';
        }
        field(6; "CodIdioma"; Code[10])
        {
            Caption = 'Customer Language Code';
        }
        // 👇 NUEVO: la marca para saltar descuentos
        field(7; "Skip Header Discounts"; Boolean)
        {
            Caption = 'Skip Header Discounts';
            DataClassification = CustomerContent;
        }
    }
    keys
    {
        key(PK; "No.")
        {
            Clustered = true;
        }
    }
}
