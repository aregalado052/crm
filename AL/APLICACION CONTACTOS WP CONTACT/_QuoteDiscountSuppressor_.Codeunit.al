codeunit 50163 "QuoteDiscountSuppressor"
{
    SingleInstance = true;

    var Enabled: Boolean;
    procedure Enable()
    begin
        Enabled:=true;
    end;
    procedure Disable()
    begin
        Enabled:=false;
    end;
    procedure IsEnabled(): Boolean begin
        exit(Enabled);
    end;
    local procedure SalesCalcDisc_OnBeforeCalcInvDisc(SalesHeader: Record "Sales Header"; var Handled: Boolean)
    begin
        if(SalesHeader."Document Type" = SalesHeader."Document Type"::Quote) and SalesHeader."Skip Header Discounts" then Handled:=true; // no calcular descuento cabecera
    end;
}
