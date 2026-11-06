CREATE TABLE dbo.FeeSchedule
(
    FeeScheduleId INT IDENTITY(1, 1) NOT NULL,
    CorridorId    INT                NOT NULL,
    PayoutMethod  VARCHAR(20)        NOT NULL,
    MinSendAmount DECIMAL(18, 2)     NOT NULL,
    MaxSendAmount DECIMAL(18, 2)     NOT NULL,
    FlatFee       DECIMAL(18, 2)     NOT NULL,
    PercentFee    DECIMAL(6, 4)      NOT NULL,
    EffectiveFrom DATE               NOT NULL,
    EffectiveTo   DATE               NULL,

    CONSTRAINT PK_FeeSchedule PRIMARY KEY CLUSTERED (FeeScheduleId),
    CONSTRAINT FK_FeeSchedule_Corridor FOREIGN KEY (CorridorId) REFERENCES dbo.Corridor (CorridorId),
    CONSTRAINT CK_FeeSchedule_PayoutMethod CHECK (PayoutMethod IN ('BankDeposit', 'CashPickup', 'MobileWallet')),
    CONSTRAINT CK_FeeSchedule_AmountBand CHECK (MinSendAmount >= 0 AND MaxSendAmount >= MinSendAmount),
    CONSTRAINT CK_FeeSchedule_Fees CHECK (FlatFee >= 0 AND PercentFee >= 0 AND PercentFee < 1),
    CONSTRAINT CK_FeeSchedule_Effective CHECK (EffectiveTo IS NULL OR EffectiveTo >= EffectiveFrom)
);
GO

CREATE INDEX IX_FeeSchedule_Lookup ON dbo.FeeSchedule (CorridorId, PayoutMethod, EffectiveFrom);
