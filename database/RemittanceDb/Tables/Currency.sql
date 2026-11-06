CREATE TABLE dbo.Currency
(
    CurrencyCode  CHAR(3)       NOT NULL,
    CurrencyName  NVARCHAR(50)  NOT NULL,
    DecimalPlaces TINYINT       NOT NULL,

    CONSTRAINT PK_Currency PRIMARY KEY CLUSTERED (CurrencyCode),
    CONSTRAINT CK_Currency_DecimalPlaces CHECK (DecimalPlaces <= 4)
);
