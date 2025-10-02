codeunit 50190 "AWS Lambda Invoker"
{
    procedure InvokeForSalesQuote(var SalesHeader: Record "Sales Header")
    var
        Client: HttpClient;
        Content: HttpContent;
        Response: HttpResponseMessage;
        CntHeaders: HttpHeaders;
        Payload: JsonObject;
        Lines: JsonArray;
        LineObj: JsonObject;
        SalesLine: Record "Sales Line";
        BodyText: Text;
        RespText: Text;
        ENDPOINT_URL: Text[250];
        API_KEY: Text[100];
        BEARER_TOKEN: Text[250];
        VolPct: Decimal;
        AddPct: Decimal;
        TotalPct: Decimal;
        CCode: Code[10];
    begin
        //ENDPOINT_URL := ' https://2a4e1c3c5cf4.ngrok-free.app/salesquote_bd'; // ejemplo
        ENDPOINT_URL:='https://2wyjgrvl1i.execute-api.eu-north-1.amazonaws.com/prod/salesquote_bd';
        API_KEY:='';
        BEARER_TOKEN:='';
        // ----- Descuentos de cabecera -----
        VolPct:=SalesHeader."Volume Discount %";
        AddPct:=SalesHeader."Additional Discount %";
        TotalPct:=CalcCombinedPct(VolPct, AddPct); // compuesto: 1 - (1 - v/100)*(1 - a/100)
        if SalesHeader."Document Type" <> SalesHeader."Document Type"::Quote then Error('Esta acción solo está permitida para Ofertas (Sales Quote).');
        if ENDPOINT_URL = '' then Error('Configura ENDPOINT_URL.');
        // ----- JSON -----
        Clear(Payload);
        Clear(Lines);
        Payload.Add('documentType', 'SalesQuote');
        Payload.Add('documentNo', SalesHeader."No.");
        if SalesHeader."Sell-to Customer No." = '' then begin
            Payload.Add('sellToCustomerNo', SalesHeader."Sell-to Contact No.");
            Payload.Add('sellToName', GetSellToContactName(SalesHeader));
        end
        else
        begin
            Payload.Add('sellToCustomerNo', SalesHeader."Sell-to Customer No.");
            Payload.Add('sellToName', SalesHeader."Sell-to Customer Name");
        end;
        Payload.Add('sellToEmail', GetSellToEmail(SalesHeader));
        Payload.Add('postingDate', Format(SalesHeader."Document Date", 0, 9));
        Payload.Add('additionalDiscountPct', AddPct); // descuento adicional cabecera
        Payload.Add('totalDiscountPct', TotalPct); // descuento total compuesto
        SalesHeader.CalcFields(Amount, "Amount Including VAT");
        Payload.Add('amount', SalesHeader.Amount);
        Payload.Add('amountInclVAT', SalesHeader."Amount Including VAT");
        CCode:=GetSellToCountryCode(SalesHeader);
        Payload.Add('countryCode', CCode);
        Payload.Add('countryName', GetCountryName(CCode));
        // Idioma (código)
        Payload.Add('languageCode', GetSellToLanguageCode(SalesHeader));
        SalesLine.SetRange("Document Type", SalesHeader."Document Type");
        SalesLine.SetRange("Document No.", SalesHeader."No.");
        if SalesLine.FindSet()then repeat Clear(LineObj);
                LineObj.Add('lineNo', SalesLine."Line No.");
                LineObj.Add('type', Format(SalesLine.Type));
                LineObj.Add('no', SalesLine."No.");
                LineObj.Add('description', SalesLine.Description);
                LineObj.Add('quantity', SalesLine.Quantity);
                LineObj.Add('unitPrice', SalesLine."Unit Price");
                LineObj.Add('lineAmount', SalesLine."Line Amount");
                Lines.Add(LineObj);
            until SalesLine.Next() = 0;
        Payload.Add('lines', Lines);
        Payload.WriteTo(BodyText);
        // ----- Headers del cliente (sin argumentos) -----
        Client.DefaultRequestHeaders().Clear();
        Client.DefaultRequestHeaders().Add('Accept', 'application/json');
        Client.DefaultRequestHeaders().Add('User-Agent', 'BC-Lambda-Connector/1.0');
        if API_KEY <> '' then Client.DefaultRequestHeaders().Add('x-api-key', API_KEY);
        if BEARER_TOKEN <> '' then Client.DefaultRequestHeaders().Add('Authorization', StrSubstNo('Bearer %1', BEARER_TOKEN));
        // ----- Contenido y headers de contenido (con var) -----
        Content.WriteFrom(BodyText);
        Content.GetHeaders(CntHeaders);
        CntHeaders.Clear();
        CntHeaders.Add('Content-Type', 'application/json');
        // ----- POST -----
        if not Client.Post(ENDPOINT_URL, Content, Response)then Error('No se pudo establecer conexión con el endpoint.');
        Response.Content().ReadAs(RespText);
        if not Response.IsSuccessStatusCode()then Error('Error HTTP %1. Respuesta: %2', Response.HttpStatusCode(), CopyStr(RespText, 1, 250));
        Message('Oferta %1 enviada correctamente. %2', SalesHeader."No.", CopyStr(RespText, 1, 250));
    end;
    local procedure CalcCombinedPct(VolPct: Decimal; AddPct: Decimal): Decimal var
        V: Decimal;
        A: Decimal;
        R: Decimal;
    begin
        // Limitar a 0..100
        V:=VolPct;
        if V < 0 then V:=0;
        if V > 100 then V:=100;
        A:=AddPct;
        if A < 0 then A:=0;
        if A > 100 then A:=100;
        // 1 - (1 - v/100) * (1 - a/100)
        R:=(1 - ((1 - (V / 100)) * (1 - (A / 100)))) * 100;
        exit(Round(R, 0.00001, '='));
    end;
    local procedure GetSellToEmail(SalesHeader: Record "Sales Header"): Text[250]var
        Cust: Record Customer;
        Cont: Record Contact;
    begin
        // 1) Email grabado en la propia oferta (si existe)
        if SalesHeader."Sell-to E-Mail" <> '' then exit(SalesHeader."Sell-to E-Mail");
        // 2) Email del cliente
        if(SalesHeader."Sell-to Customer No." <> '') and Cust.Get(SalesHeader."Sell-to Customer No.")then if Cust."E-Mail" <> '' then exit(Cust."E-Mail");
        // 3) Email del contacto asociado
        if(SalesHeader."Sell-to Contact No." <> '') and Cont.Get(SalesHeader."Sell-to Contact No.")then if Cont."E-Mail" <> '' then exit(Cont."E-Mail");
        exit(''); // si no hay email disponible
    end;
    local procedure GetSellToContactName(SalesHeader: Record "Sales Header"): Text[250]var
        Cont: Record Contact;
        FullName: Text[250];
    begin
        // 1) Si la oferta ya trae el nombre del contacto en "Sell-to Contact", úsalo
        if SalesHeader."Sell-to Contact" <> '' then exit(SalesHeader."Sell-to Contact");
        // 2) Si hay "Sell-to Contact No.", lee el registro Contact
        if(SalesHeader."Sell-to Contact No." <> '') and Cont.Get(SalesHeader."Sell-to Contact No.")then begin
            FullName:=Cont.Name; // Contact.Name
            if Cont."Name 2" <> '' then FullName:=StrSubstNo('%1 %2', FullName, Cont."Name 2"); // concatena Name + Name 2
            exit(FullName);
        end;
        exit(''); // sin contacto
    end;
    local procedure GetSellToCountryCode(SalesHeader: Record "Sales Header"): Code[10]var
        Cust: Record Customer;
        Cont: Record Contact;
        Code: Code[10];
    begin
        // 1) Del propio documento
        Code:=SalesHeader."Sell-to Country/Region Code";
        if Code <> '' then exit(Code);
        // 2) Del cliente, si existe
        if(SalesHeader."Sell-to Customer No." <> '') and Cust.Get(SalesHeader."Sell-to Customer No.")then begin
            if Cust."Country/Region Code" <> '' then exit(Cust."Country/Region Code");
        end;
        // 3) Del contacto, si existe
        if(SalesHeader."Sell-to Contact No." <> '') and Cont.Get(SalesHeader."Sell-to Contact No.")then begin
            if Cont."Country/Region Code" <> '' then exit(Cont."Country/Region Code");
        end;
        exit('');
    end;
    local procedure GetCountryName(CountryCode: Code[10]): Text[100]var
        Country: Record "Country/Region";
    begin
        if(CountryCode <> '') and Country.Get(CountryCode)then exit(Country.Name);
        exit('');
    end;
    local procedure GetSellToLanguageCode(SalesHeader: Record "Sales Header"): Code[10]var
        Cust: Record Customer;
        Cont: Record Contact;
        Code: Code[10];
    begin
        // 1) Del propio documento (campo estándar)
        Code:=SalesHeader."Language Code";
        if Code <> '' then exit(Code);
        // 2) Del cliente
        if(SalesHeader."Sell-to Customer No." <> '') and Cust.Get(SalesHeader."Sell-to Customer No.")then if Cust."Language Code" <> '' then exit(Cust."Language Code");
        // 3) Del contacto (si tu tabla Contact tiene Language Code)
        if(SalesHeader."Sell-to Contact No." <> '') and Cont.Get(SalesHeader."Sell-to Contact No.")then if Cont."Language Code" <> '' then exit(Cont."Language Code");
        exit('');
    end;
}
