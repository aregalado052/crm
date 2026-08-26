page 50193 "Lambda Setup"
{
    PageType = List;
    SourceTable = "Lambda Setup";
    ApplicationArea = All;
    UsageCategory = Administration;
    Caption = 'Lambda Setup';

    layout
    {
        area(content)
        {
            repeater(General)
            {
                field("Primary Key"; Rec."Primary Key")
                {
                    ApplicationArea = All;
                }

                field(Description; Rec.Description)
                {
                    ApplicationArea = All;
                }

                field(Enabled; Rec.Enabled)
                {
                    ApplicationArea = All;
                }

                field("Endpoint URL"; Rec."Endpoint URL")
                {
                    ApplicationArea = All;
                }

                field("API Key"; Rec."API Key")
                {
                    ApplicationArea = All;
                }

                field("Bearer Token"; Rec."Bearer Token")
                {
                    ApplicationArea = All;
                }
                field(DatabaseName; Rec."Database Name")
                {
                    ApplicationArea = All;
                    Caption = 'Base de datos';
                }
            }
        }
    }
}