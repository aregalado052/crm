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

tableextension 50142 ContactExt extends Contact
{
    fields
    {
        field(50100; "Foreign Registration No."; Text[30])
        {
            Caption = 'Registration No. (Non-EU)';
            DataClassification = CustomerContent;
        }
    }
}

table 50143 "UpdateContactBufferV1"
{
    DataClassification = CustomerContent;

    fields
    {
        field(1; "Entry No."; Integer)
        {
            AutoIncrement = true;
        }

        field(2; "QuoteNo"; Code[20]) { }

        field(11; "Bill-to Name"; Text[100]) { }
        field(3; "Address"; Text[100]) { }
        field(4; "Address2"; Text[50]) { }
        field(5; "PostCode"; Code[20]) { }
        field(6; "City"; Text[30]) { }
        field(7; "VATRegNo"; Text[20]) { }
        field(8; "ForeignRegNo"; Text[30]) { }
        field(9; "OK"; Boolean) { }
        field(10; "Message"; Text[250]) { }
    }

    keys
    {
        key(PK; "Entry No.")
        {
            Clustered = true;
        }
    }
}

table 50641 "ProformaTransferBuffer"
{
    DataClassification = CustomerContent;

    fields
    {
        field(1; "Entry No."; Integer)
        {
            AutoIncrement = true;
        }

        field(2; "QuoteNo"; Code[20]) { }
        field(3; "SessionId"; Text[100]) { }
        field(4; "Url"; Text[250]) { }
        field(5; "BD"; Text[30]) { }

        field(10; "OK"; Boolean) { }
        field(11; "Message"; Text[250]) { }
    }

    keys
    {
        key(PK; "Entry No.") { Clustered = true; }
    }
}

