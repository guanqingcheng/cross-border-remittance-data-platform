CREATE TABLE dbo.Recipient
(
    RecipientId INT IDENTITY(1, 1) NOT NULL,
    CustomerId  INT                NOT NULL,
    FirstName   NVARCHAR(100)      NOT NULL,
    LastName    NVARCHAR(100)      NOT NULL,
    CountryCode CHAR(2)            NOT NULL,
    IsActive    BIT                NOT NULL CONSTRAINT DF_Recipient_IsActive DEFAULT 1,
    CreatedAt   DATETIME2(3)       NOT NULL CONSTRAINT DF_Recipient_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt   DATETIME2(3)       NOT NULL CONSTRAINT DF_Recipient_UpdatedAt DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Recipient PRIMARY KEY CLUSTERED (RecipientId),
    CONSTRAINT UQ_Recipient_Id_Customer UNIQUE (RecipientId, CustomerId),
    CONSTRAINT FK_Recipient_Customer FOREIGN KEY (CustomerId) REFERENCES dbo.Customer (CustomerId)
);
GO

CREATE INDEX IX_Recipient_CustomerId ON dbo.Recipient (CustomerId);
GO

CREATE INDEX IX_Recipient_UpdatedAt ON dbo.Recipient (UpdatedAt);
