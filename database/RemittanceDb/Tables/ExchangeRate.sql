CREATE TABLE dbo.ExchangeRate
(
    ExchangeRateId   BIGINT IDENTITY(1, 1) NOT NULL,
    FromCurrencyCode CHAR(3)               NOT NULL,
    ToCurrencyCode   CHAR(3)               NOT NULL,
    RateDate         DATE                  NOT NULL,
    MidRate          DECIMAL(18, 8)        NOT NULL,
    CustomerRate     DECIMAL(18, 8)        NOT NULL,

    CONSTRAINT PK_ExchangeRate PRIMARY KEY CLUSTERED (ExchangeRateId),
    CONSTRAINT UQ_ExchangeRate_PairDate UNIQUE (FromCurrencyCode, ToCurrencyCode, RateDate),
    CONSTRAINT FK_ExchangeRate_FromCurrency FOREIGN KEY (FromCurrencyCode) REFERENCES dbo.Currency (CurrencyCode),
    CONSTRAINT FK_ExchangeRate_ToCurrency FOREIGN KEY (ToCurrencyCode) REFERENCES dbo.Currency (CurrencyCode),
    CONSTRAINT CK_ExchangeRate_Pair CHECK (FromCurrencyCode <> ToCurrencyCode),
    CONSTRAINT CK_ExchangeRate_Rates CHECK (CustomerRate > 0 AND CustomerRate <= MidRate)
);
