page 50193 "Lambda Setup"
{
    PageType = Card;
    SourceTable = "Lambda Setup";
    ApplicationArea = All;
    UsageCategory = Administration;
    Caption = 'Lambda Setup';

    layout
    {
        area(content)
        {
            group(General)
            {
                field(Enabled; Rec."Enabled")
                {
                    ApplicationArea = All;
                }
                field(EndpointURL; Rec."Endpoint URL")
                {
                    ApplicationArea = All;
                }
                field(APIKey; Rec."API Key")
                {
                    ApplicationArea = All;
                }
                field(BearerToken; Rec."Bearer Token")
                {
                    ApplicationArea = All;
                }
            }
        }
    }
    trigger OnOpenPage()
    begin
        // Garantiza que exista el registro único SETUP
        if not Rec.Get('SETUP')then begin
            Rec.Init();
            Rec."Primary Key":='SETUP';
            Rec.Insert();
        end;
    end;
}
