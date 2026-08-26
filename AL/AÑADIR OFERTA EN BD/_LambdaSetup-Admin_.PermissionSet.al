permissionset 50117 "LambdaSetup-Admin"
{
    Caption = 'Lambda Setup - Admin';
    Assignable = true;

    Permissions =
        tabledata "Lambda Setup" = RIMD,
        table "Lambda Setup" = X,
        page "Lambda Setup" = X,
        codeunit "AWS Lambda Invoker" = X,
        codeunit "CRM Sale Won Subscriber" = X;
}