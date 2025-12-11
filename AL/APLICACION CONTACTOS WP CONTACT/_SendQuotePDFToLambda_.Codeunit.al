codeunit 50198 "SendQuotePDFToLambda"
{
    procedure SendQuotePDF(DocumentNo: Code[20]; SessionId: Text; Url: Text; BD: Text)
    var
        SalesHeader: Record "Sales Header";
        TempBlob: Codeunit "Temp Blob";
        InStr: InStream;
        OutS: OutStream;
        HttpClient: HttpClient;
        HttpRequest: HttpRequestMessage;
        HttpResponse: HttpResponseMessage;
        HttpContent: HttpContent;
        LambdaUrl: Text;
        ErrorText: Text;
        Headers: HttpHeaders;
        PDFRec: Record "PDF Transfer Buffer";
        MediaId: Guid;
        TenantMedia: Record "Tenant Media";
        TotalExclIva: Decimal;
        TotalTxt: Text;
        Url_amazon: Text;
        Url_ngrok: Text;
        Url_Final: Text;
        Ok: Boolean;
        ErrText: Text;
        RespTxt: Text;
        Sh: Record "Sales Header";
        Suppressor: Codeunit "QuoteDiscountSuppressor";
        PrevSkip: Boolean;
    begin
        if not SalesHeader.Get(SalesHeader."Document Type"::Quote, DocumentNo) then Error('No se encontró la oferta con número %1', DocumentNo);
        // Comprobar si el supresor de descuentos está activo
        PrevSkip := SalesHeader."Skip Header Discounts";
        if not SalesHeader."Skip Header Discounts" then begin
            SalesHeader."Skip Header Discounts" := true;
            SalesHeader.Modify(true);
            Commit(); // Muy importante: el Report verá este estado
        end;
        Suppressor.Enable();
        // Generar el PDF
        TempBlob := GeneratePDF(DocumentNo);
        TempBlob.CreateInStream(InStr);
        // 2) Total sin IVA desde el propio Sales Header
        SalesHeader.CalcFields("Amount", "Amount Including VAT"); // FlowFields
        TotalExclIva := Round(SalesHeader."Amount", 0.01, '=');
        // Formato neutro (punto decimal)
        TotalTxt := ConvertStr(Format(TotalExclIva, 0, 9), ',', '.');
        // 2. Guardar en tabla con campo Media
        if not PDFRec.Get(DocumentNo) then begin
            PDFRec.Init();
            PDFRec."ID" := DocumentNo;
            PDFRec.Insert();
        end;
        PDFRec."PDF Blob".ImportStream(InStr, 'Oferta_' + DocumentNo + '.pdf');
        PDFRec.Modify();
        MediaId := PDFRec."PDF Blob".MediaId;
        if not TenantMedia.Get(MediaId) then Error('No se encontró el PDF.');
        TenantMedia.CalcFields(Content);
        TenantMedia.Content.CreateInStream(InStr);
        // Preparar contenido PDF
        HttpContent.WriteFrom(InStr);
        // Crear headers correctamente
        HttpContent.GetHeaders(Headers);
        Headers.Clear();
        Headers.Add('Content-Type', 'application/pdf');
        Url_amazon := StrSubstNo('https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/oferta?session_id=%1&total_excl_iva=%2', SessionId, TotalTxt);
        Url_ngrok := StrSubstNo('https://74a4dc24919c.ngrok-free.app/oferta?session_id=%1&total_excl_iva=%2', SessionId, TotalTxt);
        Url_Final := StrSubstNo(Url + '?session_id=%1&total_excl_iva=%2&BD=%3', SessionId, TotalTxt, BD);
        //Url_ngrok := StrSubstNo('https://c6f27745c3c8.ngrok-free.app/oferta?session_id=' + SessionId);
        // Configurar la solicitud
        //HttpRequest.SetRequestUri('https://8c51513d10b8.ngrok-free.app/oferta?session_id=' + SessionId);
        //HttpRequest.SetRequestUri('https://tx3fc457zf.execute-api.eu-north-1.amazonaws.com/prod/oferta?session_id=' + SessionId);
        //HttpRequest.SetRequestUri(Url_amazon);
        HttpRequest.SetRequestUri(Url_Final);
        HttpRequest.Method := 'POST';
        HttpRequest.Content := HttpContent;
        if not HttpClient.Send(HttpRequest, HttpResponse) then Error('No se pudo conectar a: %1. Asegúrate de que el túnel ngrok está activo y la ruta /oferta existe.', Url_Final);
        // Enviar
        //if not HttpClient.Send(HttpRequest, HttpResponse) then
        //    Error('Error enviando PDF al servidor');
        // Leemos el contenido de la respuesta
        HttpResponse.Content.ReadAs(RespTxt);
        // Siempre mostramos la respuesta para diagnóstico
        Message('Respuesta del servidor:\nHTTP %1 %2\nBody: %3', Format(HttpResponse.HttpStatusCode()), HttpResponse.ReasonPhrase(), CopyStr(RespTxt, 1, 500)); // Máximo 500 caracteres para no saturar
        // Si el status no es 2xx, lanzamos error para que sepas que algo fue mal
        if not HttpResponse.IsSuccessStatusCode() then Error('Error enviando PDF. HTTP %1 %2.\nRespuesta: %3', Format(HttpResponse.HttpStatusCode()), HttpResponse.ReasonPhrase(), CopyStr(RespTxt, 1, 500));
        if HttpResponse.HttpStatusCode <> 200 then begin
            HttpResponse.Content.ReadAs(ErrorText);
            Error('Error en respuesta: %1', ErrorText);
        end;
        if PDFRec.Get(DocumentNo) then PDFRec.Delete();
        Suppressor.Disable();
        if Sh.Get(Sh."Document Type"::Quote, DocumentNo) then begin
            if Sh."Skip Header Discounts" <> PrevSkip then begin
                Sh."Skip Header Discounts" := PrevSkip;
                Sh.Modify(true);
                Commit();
            end;
        end;
    end;

    local procedure GeneratePDF(DocumentNo: Code[20]): Codeunit "Temp Blob"
    var
        SalesHeader: Record "Sales Header";
        OutStr: OutStream;
        TempBlob: Codeunit "Temp Blob";
        RecRef: RecordRef;
        SalesHeaderVariant: Variant;
        RequestPageXml: Text;
        FileMgmt: Codeunit "File Management";
        InStr: InStream;
        FileFilter: Text;
        FileType: Text;
        FileName: Text;
        ClientFileName: Text;
    begin
        if not SalesHeader.Get(SalesHeader."Document Type"::Quote, DocumentNo) then Error('No se encuentra la oferta %1', DocumentNo);
        // Aplicar filtro
        SalesHeader.SetRange("Document Type", SalesHeader."Document Type"::Quote);
        SalesHeader.SetRange("No.", DocumentNo);
        // Crear salida del PDF
        TempBlob.CreateOutStream(OutStr);
        // Pasar los filtros al RecordRef
        RecRef.Open(Database::"Sales Header");
        RecRef.SetView(SalesHeader.GetView); // 🔥 Esta es la forma correcta de aplicar filtros
        RecRef.FindFirst();
        // Generar el informe con el filtro ya aplicado
        Report.SaveAs(Report::"Standard Sales - Quote", '', // Sin RequestPageXml porque usamos RecordRef filtrado
 ReportFormat::Pdf, OutStr, RecRef);
        exit(TempBlob);
    end;
}
