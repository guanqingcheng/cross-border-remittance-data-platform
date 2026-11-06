CREATE PROCEDURE dbo.usp_CreateTransfer
    @CustomerId      INT,
    @RecipientId     INT,
    @CorridorId      INT,
    @PayoutMethod    VARCHAR(20),
    @SendAmount      DECIMAL(18, 2),
    @AsOfUtc         DATETIME2(3) = NULL, -- Lets the data generator create historical transfers
    @TransferId      BIGINT = NULL OUTPUT,
    @ReferenceNumber VARCHAR(20) = NULL OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    SET @AsOfUtc = COALESCE(@AsOfUtc, SYSUTCDATETIME());

    DECLARE @AsOfDate DATE = CAST(@AsOfUtc AS DATE);
    DECLARE @CustomerCountryCode CHAR(2);
    DECLARE @SourceCountryCode CHAR(2);
    DECLARE @DestinationCountryCode CHAR(2);
    DECLARE @SourceCurrencyCode CHAR(3);
    DECLARE @DestinationCurrencyCode CHAR(3);
    DECLARE @MaxSendAmount DECIMAL(18, 2);
    DECLARE @FeeScheduleId INT;
    DECLARE @FlatFee DECIMAL(18, 2);
    DECLARE @PercentFee DECIMAL(6, 4);
    DECLARE @ExchangeRateId BIGINT;
    DECLARE @AppliedRate DECIMAL(18, 8);
    DECLARE @DestinationDecimalPlaces TINYINT;

    SELECT @CustomerCountryCode = CountryCode
    FROM dbo.Customer
    WHERE CustomerId = @CustomerId
        AND KycStatus = 'Verified';

    IF @CustomerCountryCode IS NULL
        THROW 50001, 'Customer does not exist or is not verified.', 1;

    SELECT
        @SourceCountryCode = c.SourceCountryCode,
        @DestinationCountryCode = c.DestinationCountryCode,
        @SourceCurrencyCode = c.SourceCurrencyCode,
        @DestinationCurrencyCode = c.DestinationCurrencyCode,
        @MaxSendAmount = c.MaxSendAmount,
        @DestinationDecimalPlaces = dc.DecimalPlaces
    FROM dbo.Corridor AS c
    INNER JOIN dbo.Currency AS dc ON dc.CurrencyCode = c.DestinationCurrencyCode
    WHERE c.CorridorId = @CorridorId
        AND c.IsActive = 1;

    IF @MaxSendAmount IS NULL
        THROW 50002, 'Corridor does not exist or is not active.', 1;

    IF @CustomerCountryCode <> @SourceCountryCode
        THROW 50010, 'Customer country must match the corridor source country.', 1;

    IF @SendAmount IS NULL OR @SendAmount <= 0 OR @SendAmount > @MaxSendAmount
        THROW 50003, 'Send amount must be greater than zero and within the corridor limit.', 1;

    IF NOT EXISTS
    (
        SELECT 1
        FROM dbo.Recipient
        WHERE RecipientId = @RecipientId
            AND CustomerId = @CustomerId
            AND IsActive = 1
            AND CountryCode = @DestinationCountryCode
    )
        THROW 50004, 'Recipient must be active, belong to the customer, and be in the destination country.', 1;

    SELECT TOP (1)
        @FeeScheduleId = FeeScheduleId,
        @FlatFee = FlatFee,
        @PercentFee = PercentFee
    FROM dbo.FeeSchedule
    WHERE CorridorId = @CorridorId
        AND PayoutMethod = @PayoutMethod
        AND @SendAmount BETWEEN MinSendAmount AND MaxSendAmount
        AND EffectiveFrom <= @AsOfDate
        AND (EffectiveTo IS NULL OR EffectiveTo >= @AsOfDate)
    ORDER BY EffectiveFrom DESC, FeeScheduleId DESC;

    IF @FeeScheduleId IS NULL
        THROW 50005, 'No fee schedule applies to this transfer.', 1;

    SELECT
        @ExchangeRateId = ExchangeRateId,
        @AppliedRate = CustomerRate
    FROM dbo.ExchangeRate
    WHERE FromCurrencyCode = @SourceCurrencyCode
        AND ToCurrencyCode = @DestinationCurrencyCode
        AND RateDate = @AsOfDate;

    IF @ExchangeRateId IS NULL
        THROW 50006, 'No exchange rate exists for this currency pair and date.', 1;

    DECLARE @FeeAmount DECIMAL(18, 2) = ROUND(@FlatFee + @SendAmount * @PercentFee, 2);
    DECLARE @ReceiveAmount DECIMAL(18, 2) = ROUND(@SendAmount * @AppliedRate, @DestinationDecimalPlaces);
    DECLARE @ReferenceValue BIGINT = NEXT VALUE FOR dbo.TransferReferenceSequence;

    SET @ReferenceNumber = CONCAT('RM', RIGHT(CONCAT('0000000000', @ReferenceValue), 10));

    BEGIN TRY
        BEGIN TRANSACTION;

        INSERT INTO dbo.Transfer
        (
            ReferenceNumber, CustomerId, RecipientId, CorridorId, FeeScheduleId, ExchangeRateId, PayoutMethod,
            SendAmount, FeeAmount, AppliedRate, ReceiveAmount, Status, CreatedAt, UpdatedAt
        )
        VALUES
        (
            @ReferenceNumber, @CustomerId, @RecipientId, @CorridorId, @FeeScheduleId, @ExchangeRateId, @PayoutMethod,
            @SendAmount, @FeeAmount, @AppliedRate, @ReceiveAmount, 'Pending', @AsOfUtc, @AsOfUtc
        );

        SET @TransferId = SCOPE_IDENTITY();

        INSERT INTO dbo.TransferStatusHistory (TransferId, FromStatus, ToStatus, ChangedAt)
        VALUES (@TransferId, NULL, 'Pending', @AsOfUtc);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
