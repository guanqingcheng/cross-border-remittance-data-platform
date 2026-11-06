CREATE TABLE dbo.Corridor
(
    CorridorId              INT IDENTITY(1, 1) NOT NULL,
    SourceCountryCode       CHAR(2)            NOT NULL,
    DestinationCountryCode  CHAR(2)            NOT NULL,
    SourceCurrencyCode      CHAR(3)            NOT NULL,
    DestinationCurrencyCode CHAR(3)            NOT NULL,
    MaxSendAmount           DECIMAL(18, 2)     NOT NULL,
    IsActive                BIT                NOT NULL CONSTRAINT DF_Corridor_IsActive DEFAULT 1,

    CONSTRAINT PK_Corridor PRIMARY KEY CLUSTERED (CorridorId),
    CONSTRAINT UQ_Corridor_Route UNIQUE (SourceCountryCode, DestinationCountryCode, SourceCurrencyCode, DestinationCurrencyCode),
    CONSTRAINT FK_Corridor_SourceCurrency FOREIGN KEY (SourceCurrencyCode) REFERENCES dbo.Currency (CurrencyCode),
    CONSTRAINT FK_Corridor_DestinationCurrency FOREIGN KEY (DestinationCurrencyCode) REFERENCES dbo.Currency (CurrencyCode),
    CONSTRAINT CK_Corridor_Countries CHECK (SourceCountryCode <> DestinationCountryCode),
    CONSTRAINT CK_Corridor_MaxSendAmount CHECK (MaxSendAmount > 0)
);
