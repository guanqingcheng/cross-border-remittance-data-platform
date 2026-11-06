CREATE TABLE dbo.Customer
(
    CustomerId  INT IDENTITY(1, 1) NOT NULL,
    FirstName   NVARCHAR(100)      NOT NULL,
    LastName    NVARCHAR(100)      NOT NULL,
    Email       VARCHAR(254)       NOT NULL,
    CountryCode CHAR(2)            NOT NULL,
    KycStatus   VARCHAR(20)        NOT NULL,
    CreatedAt   DATETIME2(3)       NOT NULL CONSTRAINT DF_Customer_CreatedAt DEFAULT SYSUTCDATETIME(),
    UpdatedAt   DATETIME2(3)       NOT NULL CONSTRAINT DF_Customer_UpdatedAt DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Customer PRIMARY KEY CLUSTERED (CustomerId),
    CONSTRAINT UQ_Customer_Email UNIQUE (Email),
    CONSTRAINT CK_Customer_KycStatus CHECK (KycStatus IN ('Pending', 'Verified', 'Rejected'))
);
GO

CREATE INDEX IX_Customer_UpdatedAt ON dbo.Customer (UpdatedAt);
