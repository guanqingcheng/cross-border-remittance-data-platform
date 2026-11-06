CREATE PROCEDURE dbo.usp_GetCustomerTransferHistory
    @CustomerId INT,
    @FromDate   DATE = NULL,
    @ToDate     DATE = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        t.ReferenceNumber,
        t.CreatedAt,
        CONCAT(r.FirstName, N' ', r.LastName) AS RecipientName,
        c.DestinationCountryCode,
        c.SourceCurrencyCode,
        t.SendAmount,
        t.FeeAmount,
        c.DestinationCurrencyCode,
        t.ReceiveAmount,
        t.AppliedRate,
        t.Status
    FROM dbo.Transfer AS t
    INNER JOIN dbo.Recipient AS r ON r.RecipientId = t.RecipientId
    INNER JOIN dbo.Corridor AS c ON c.CorridorId = t.CorridorId
    WHERE t.CustomerId = @CustomerId
        AND (@FromDate IS NULL OR t.CreatedAt >= @FromDate)
        -- Upper bound is exclusive so the whole of @ToDate is included
        AND (@ToDate IS NULL OR t.CreatedAt < DATEADD(DAY, 1, @ToDate))
    ORDER BY t.CreatedAt DESC, t.TransferId DESC
    OPTION (RECOMPILE);
END;
