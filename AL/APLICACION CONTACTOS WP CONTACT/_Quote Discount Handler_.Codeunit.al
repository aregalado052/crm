codeunit 50122 "Quote Discount Handler"
{
    procedure ApplyHeaderDiscountsToLines(var SalesHeader: Record "Sales Header")
    var
        SalesLine: Record "Sales Line";
        CombinedPct: Decimal;
    begin
        if SalesHeader."Document Type" <> SalesHeader."Document Type"::Quote then exit;
        // Salir si la Lambda marcó el flag
        if SalesHeader."Skip Header Discounts" then exit;
        CombinedPct:=CalcCombinedPct(SalesHeader);
        SalesLine.SetRange("Document Type", SalesHeader."Document Type");
        SalesLine.SetRange("Document No.", SalesHeader."No.");
        if SalesLine.FindSet(true)then repeat if(SalesLine.Type <> SalesLine.Type::" ")then if SalesLine."Line Discount %" <> CombinedPct then begin
                        SalesLine.Validate("Line Discount %", CombinedPct);
                        SalesLine.Modify(true);
                    end;
            until SalesLine.Next() = 0;
    end;
    local procedure CalcCombinedPct(SalesHeader: Record "Sales Header"): Decimal var
        VolPct: Decimal;
        AddPct: Decimal;
        CombinedPct: Decimal;
    begin
        // Lee y acota a 0..100
        VolPct:=SalesHeader."Volume Discount %";
        AddPct:=SalesHeader."Additional Discount %";
        if VolPct < 0 then VolPct:=0;
        if VolPct > 100 then VolPct:=100;
        if AddPct < 0 then AddPct:=0;
        if AddPct > 100 then AddPct:=100;
        // Descuento compuesto: 1 - (1 - v/100) * (1 - a/100)
        CombinedPct:=(1 - ((1 - (VolPct / 100)) * (1 - (AddPct / 100)))) * 100;
        // Redondeo fino para Line Discount % (ajusta si quieres menos/más decimales)
        exit(Round(CombinedPct, 0.00001, '='));
    end;
    [EventSubscriber(ObjectType::Table, Database::"Sales Line", 'OnAfterInsertEvent', '', true, true)]
    local procedure SalesLine_OnAfterInsert(var Rec: Record "Sales Line"; RunTrigger: Boolean)
    var
        SalesHeader: Record "Sales Header";
        CombinedPct: Decimal;
    begin
        // Solo aplica en Ofertas y para líneas con tipo distinto de vacío
        if Rec."Document Type" <> Rec."Document Type"::Quote then exit;
        if not SalesHeader.Get(Rec."Document Type", Rec."Document No.")then exit;
        CombinedPct:=CalcCombinedPct(SalesHeader);
        // Si la línea recién creada no tiene el descuento correcto, lo fijamos
        if Rec."Line Discount %" <> CombinedPct then begin
            Rec.Validate("Line Discount %", CombinedPct);
            Rec.Modify(true);
        end;
    end;
}
