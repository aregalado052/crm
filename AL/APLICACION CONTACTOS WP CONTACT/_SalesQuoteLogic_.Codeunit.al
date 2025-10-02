codeunit 50135 "SalesQuoteLogic"
{
    Access = Public;

    procedure CreateWebContact(Name: Text[100]; Email: Text[100]; CustomerTemplateName: Text[100]; CountryRegionCode: Code[10]; CodIdioma: Code[10]): Code[20]var
        Contact: Record Contact;
        NewContact: Record Contact;
        ContactNo: Code[20];
        NoSeries: Codeunit "No. Series";
        CustomerTemplMgt: Codeunit "Customer Templ. Mgt.";
        CustomerTemplate: Record "Customer Templ.";
    begin
        Contact.Reset();
        Contact.SetRange("E-Mail", Email);
        if Contact.FindFirst()then exit(Contact."No.");
        ContactNo:=NoSeries.GetNextNo('WEB-CONT', Today(), true);
        NewContact.Init();
        NewContact."No.":=ContactNo;
        NewContact.Name:=Name;
        NewContact."E-Mail":=Email;
        NewContact."Country/Region Code":=CountryRegionCode;
        NewContact."Language Code":=CodIdioma;
        NewContact."Type":=NewContact."Type"::Person;
        NewContact.Insert();
        if not CustomerTemplate.Get(CustomerTemplateName)then Error('No se encontró la plantilla de cliente ');
        NewContact."Language Code":=CustomerTemplate."Language Code";
        NewContact.Modify(true);
        Commit();
        exit(NewContact."No.");
    end;
    procedure CreateWebQuote(Name: Text[100]; Email: Text[100]; CustomerTemplateName: Code[40]; CountryRegionCode: Code[10]): Code[20]var
        Contact: Record Contact;
        SalesHeader: Record "Sales Header";
        SalesLine: Record "Sales Line";
        NoSeries: Codeunit "No. Series";
        CustomerTemplate: Record "Customer Templ.";
        Header: Record "Sales Header";
        Line: Record "Sales Line";
        NextLineNo: Integer;
        Buffer: Record "SalesQuoteBufferV2";
        ContactNo: Code[20];
    begin
        Contact.SetRange("E-Mail", Email);
        if not Contact.FindFirst()then begin
        // crear contacto y obtener ContactNo
        end
        else
            ContactNo:=Contact."No.";
        if not Contact.Get(ContactNo)then Error('Contacto no encontrado: %1', ContactNo);
        if not CustomerTemplate.Get(CustomerTemplateName)then Error('No se encontró la plantilla de cliente: %1', CustomerTemplateName);
        SalesHeader.Init();
        SalesHeader."Document Type":=SalesHeader."Document Type"::Quote;
        SalesHeader."No.":=NoSeries.GetNextNo('WEB-OFER', Today(), true);
        SalesHeader."WebQuotation":=true;
        // Plantilla
        SalesHeader."Language Code":=Contact."Language Code";
        SalesHeader."Customer Posting Group":=CustomerTemplate."Customer Posting Group";
        SalesHeader."Gen. Bus. Posting Group":=CustomerTemplate."Gen. Bus. Posting Group";
        SalesHeader."VAT Bus. Posting Group":=CustomerTemplate."VAT Bus. Posting Group";
        SalesHeader."Payment Terms Code":=CustomerTemplate."Payment Terms Code";
        SalesHeader."Payment Method Code":=CustomerTemplate."Payment Method Code";
        // Datos contacto
        SalesHeader."Sell-to Customer Name":=Contact.Name;
        SalesHeader."Sell-to Contact No.":=Contact."No.";
        SalesHeader."Sell-to Country/Region Code":=CountryRegionCode;
        SalesHeader."Sell-to Customer Templ. Code":=CustomerTemplateName;
        SalesHeader."Bill-to Name":=Contact.Name;
        SalesHeader."Bill-to Contact No.":=Contact."No.";
        SalesHeader."Bill-to Country/Region Code":=CountryRegionCode;
        SalesHeader."Bill-to Customer Templ. Code":=CustomerTemplateName;
        SalesHeader."Ship-to Contact":=Contact.Name;
        SalesHeader."Ship-to Name":=Contact.Name;
        SalesHeader."Ship-to Country/Region Code":=CountryRegionCode;
        SalesHeader."External Document No.":='Oferta WEB ' + Format(Today());
        SalesHeader.Insert(true);
        Buffer.Init();
        Buffer."No.":=SalesHeader."No.";
        Buffer."CustomerName":=Contact.Name;
        Buffer."CustomerEmail":=Contact."E-Mail";
        Buffer."CustomerTemplateName":=CustomerTemplateName;
        Buffer."CustomerCountryCode":=CountryRegionCode; // ← Añadido aquí
        Buffer.Insert();
        // Línea de ejemplo
        COMMIT;
        exit(SalesHeader."No.");
    end;
    procedure CreateQuote(Name: Text[100]; Email: Text[100]; CustomerTemplateName: Code[40]; CountryRegionCode: Code[10]; CodIdioma: Code[10]): Code[20]var
        ContactNo: Code[20];
    begin
        CreateWebContact(Name, Email, CustomerTemplateName, CountryRegionCode, CodIdioma);
        exit(CreateWebQuote(Name, Email, CustomerTemplateName, CountryRegionCode));
    end;
}
