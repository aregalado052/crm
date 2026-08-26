table 50111 "Lambda Setup"
{
    Caption = 'Lambda Setup';
    DataClassification = CustomerContent;

    fields
    {
        field(1; "Primary Key"; Code[10])
        {
            Caption = 'Código';
            DataClassification = SystemMetadata;
            NotBlank = true;
        }

        field(10; "Enabled"; Boolean)
        {
            Caption = 'Activo';
            DataClassification = CustomerContent;
        }

        field(20; "Endpoint URL"; Text[250])
        {
            Caption = 'Endpoint URL';
            DataClassification = CustomerContent;
        }

        field(30; "API Key"; Text[100])
        {
            Caption = 'API Key';
            DataClassification = CustomerContent;
        }

        field(40; "Bearer Token"; Text[250])
        {
            Caption = 'Bearer Token';
            DataClassification = CustomerContent;
        }

        field(50; Description; Text[100])
        {
            Caption = 'Descripción';
            DataClassification = CustomerContent;
        }

        field(60; "Database Name"; Text[50])
        {
            Caption = 'Base de datos';
            DataClassification = CustomerContent;
        }
    }

    keys
    {
        key(PK; "Primary Key")
        {
            Clustered = true;
        }
    }
}