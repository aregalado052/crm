table 50129 "PDF Transfer Buffer"
{
    DataClassification = ToBeClassified;

    fields
    {
        field(1; "ID"; Code[20])
        {
        }
        field(2; "PDF Blob"; Media)
        {
            DataClassification = ToBeClassified;
        }
    }
    keys
    {
        key(PK; "ID")
        {
            Clustered = true;
        }
    }
}
