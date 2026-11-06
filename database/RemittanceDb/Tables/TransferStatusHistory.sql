CREATE TABLE dbo.TransferStatusHistory
(
    TransferStatusHistoryId BIGINT IDENTITY(1, 1) NOT NULL,
    TransferId              BIGINT                NOT NULL,
    FromStatus              VARCHAR(20)           NULL,
    ToStatus                VARCHAR(20)           NOT NULL,
    ChangedAt               DATETIME2(3)          NOT NULL CONSTRAINT DF_TransferStatusHistory_ChangedAt DEFAULT SYSUTCDATETIME(),
    Reason                  NVARCHAR(200)         NULL,

    CONSTRAINT PK_TransferStatusHistory PRIMARY KEY CLUSTERED (TransferStatusHistoryId),
    CONSTRAINT FK_TransferStatusHistory_Transfer FOREIGN KEY (TransferId) REFERENCES dbo.Transfer (TransferId),
    CONSTRAINT CK_TransferStatusHistory_FromStatus CHECK (FromStatus IN ('Pending', 'Processing', 'Completed', 'Cancelled', 'Failed')),
    CONSTRAINT CK_TransferStatusHistory_ToStatus CHECK (ToStatus IN ('Pending', 'Processing', 'Completed', 'Cancelled', 'Failed'))
);
GO

CREATE INDEX IX_TransferStatusHistory_TransferId ON dbo.TransferStatusHistory (TransferId, ChangedAt);
