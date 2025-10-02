table 50111 "Lambda Setup"
{
    DataClassification = CustomerContent;

    fields
    {
        field(1; "Primary Key"; Code[10])
        {
            DataClassification = SystemMetadata;
        }
        field(10; "Enabled"; Boolean)
        {
        }
        field(20; "Endpoint URL"; Text[250])
        {
        }
        field(30; "API Key"; Text[100])
        {
        }
        field(40; "Bearer Token"; Text[250])
        {
        } // opcional si usas Authorization: Bearer
    }
    keys
    {
        key(PK; "Primary Key")
        {
            Clustered = true;
        }
    }
    trigger OnInsert()
    begin
        if "Primary Key" = '' then "Primary Key":='SETUP';
    end;
    procedure Get(): Boolean var
        L: Record "Lambda Setup";
    begin
        if not Get('SETUP')then begin
            Init();
            "Primary Key":='SETUP';
            Insert();
        end;
        exit(true);
    end;
}
