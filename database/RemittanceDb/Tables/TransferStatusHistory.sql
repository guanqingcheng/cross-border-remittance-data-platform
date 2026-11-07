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
    CONSTRAINT CK_TransferStatusHistory_FromStatus CHECK ([FromStatus] = 'Failed' OR [FromStatus] = 'Cancelled' OR [FromStatus] = 'Completed' OR [FromStatus] = 'Processing' OR [FromStatus] = 'Pending'),
    CONSTRAINT CK_TransferStatusHistory_ToStatus CHECK ([ToStatus] = 'Failed' OR [ToStatus] = 'Cancelled' OR [ToStatus] = 'Completed' OR [ToStatus] = 'Processing' OR [ToStatus] = 'Pending')
);
GO

CREATE INDEX IX_TransferStatusHistory_TransferId ON dbo.TransferStatusHistory (TransferId, ChangedAt);
