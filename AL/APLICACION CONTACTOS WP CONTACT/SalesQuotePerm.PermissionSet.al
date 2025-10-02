permissionset 50100 SalesQuotePerm
{
    Assignable = true;
    Permissions = tabledata SalesQuoteBufferV2=RIMD, // SalesQuoteBufferV2
        tabledata "PDF Transfer Buffer"=RIMD; // PDF Transfer Buffer
}
