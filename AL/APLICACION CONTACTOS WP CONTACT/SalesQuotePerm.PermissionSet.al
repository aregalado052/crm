permissionset 50100 SalesQuotePerm
{
    Assignable = true;
    Permissions = tabledata SalesQuoteBufferV2 = RIMD, // SalesQuoteBufferV2
        tabledata "PDF Transfer Buffer" = RIMD; // PDF Transfer Buffer
}

permissionset 50192 "WEB PROFORMA PERMS"
{
    Assignable = true;
    Caption = 'Web Proforma Permissions';

    Permissions =
        tabledata "UpdateContactBufferV1" = RIMD,
        tabledata Contact = RM,
        tabledata "Sales Header" = R; // solo lectura para localizar la oferta
}

permissionset 50641 "PROFORMA API FULL"
{
    Assignable = true;

    Permissions =
        tabledata "ProformaTransferBuffer" = RIMD,
        tabledata "Sales Header" = RIMD,
        tabledata "Tenant Media" = RIMD;


}

