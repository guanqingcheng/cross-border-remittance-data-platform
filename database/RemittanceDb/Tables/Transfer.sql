CREATE TABLE dbo.Transfer
(
    TransferId      BIGINT IDENTITY(1, 1) NOT NULL,
    ReferenceNumber VARCHAR(20)           NOT NULL,
    CustomerId      INT                   NOT NULL,
    RecipientId     INT                   NOT NULL,
    CorridorId      INT                   NOT NULL,
    FeeScheduleId   INT                   NOT NULL,
    ExchangeRateId  BIGINT                NOT NULL,
    PayoutMethod    VARCHAR(20)           NOT NULL,
    SendAmount      DECIMAL(18, 2)        NOT NULL,
    FeeAmount       DECIMAL(18, 2)        NOT NULL,
    AppliedRate     DECIMAL(18, 8)        NOT NULL,
    ReceiveAmount   DECIMAL(18, 2)        NOT NULL,
    Status          VARCHAR(20)           NOT NULL,
    CreatedAt       DATETIME2(3)          NOT NULL CONSTRAINT DF_Transfer_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt       DATETIME2(3)          NOT NULL CONSTRAINT DF_Transfer_UpdatedAt DEFAULT SYSUTCDATETIME(),
    CompletedAt     DATETIME2(3)          NULL,

    CONSTRAINT PK_Transfer PRIMARY KEY CLUSTERED (TransferId),
    CONSTRAINT UQ_Transfer_ReferenceNumber UNIQUE (ReferenceNumber),
    CONSTRAINT FK_Transfer_Customer FOREIGN KEY (CustomerId) REFERENCES dbo.Customer (CustomerId),
    CONSTRAINT FK_Transfer_Recipient FOREIGN KEY (RecipientId, CustomerId) REFERENCES dbo.Recipient (RecipientId, CustomerId),
    CONSTRAINT FK_Transfer_Corridor FOREIGN KEY (CorridorId) REFERENCES dbo.Corridor (CorridorId),
    CONSTRAINT FK_Transfer_FeeSchedule FOREIGN KEY (FeeScheduleId) REFERENCES dbo.FeeSchedule (FeeScheduleId),
    CONSTRAINT FK_Transfer_ExchangeRate FOREIGN KEY (ExchangeRateId) REFERENCES dbo.ExchangeRate (ExchangeRateId),
    CONSTRAINT CK_Transfer_PayoutMethod CHECK (PayoutMethod IN ('BankDeposit', 'CashPickup', 'MobileWallet')),
    CONSTRAINT CK_Transfer_Amounts CHECK (SendAmount > 0 AND FeeAmount >= 0 AND AppliedRate > 0 AND ReceiveAmount >= 0),
    CONSTRAINT CK_Transfer_Status CHECK (Status IN ('Pending', 'Processing', 'Completed', 'Cancelled', 'Failed')),
    CONSTRAINT CK_Transfer_CompletedAt CHECK ((Status = 'Completed' AND CompletedAt IS NOT NULL) OR (Status <> 'Completed' AND CompletedAt IS NULL))
);
GO

CREATE INDEX IX_Transfer_CustomerId ON dbo.Transfer (CustomerId, CreatedAt);
GO

CREATE INDEX IX_Transfer_UpdatedAt ON dbo.Transfer (UpdatedAt);
GO

CREATE INDEX IX_Transfer_CorridorId ON dbo.Transfer (CorridorId, CreatedAt);
