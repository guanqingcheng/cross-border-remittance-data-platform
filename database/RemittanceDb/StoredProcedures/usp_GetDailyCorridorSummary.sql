CREATE PROCEDURE dbo.usp_GetDailyCorridorSummary
    @FromDate DATE,
    @ToDate   DATE
AS
BEGIN
    SET NOCOUNT ON;

    -- Counts cover all transfers created that day; amounts cover completed transfers only
    SELECT
        CAST(t.CreatedAt AS DATE) AS SummaryDate,
        c.CorridorId,
        c.SourceCountryCode,
        c.DestinationCountryCode,
        c.SourceCurrencyCode,
        c.DestinationCurrencyCode,
        COUNT_BIG(*) AS TransferCount,
        SUM(CASE WHEN t.Status = 'Completed' THEN 1 ELSE 0 END) AS CompletedCount,
        SUM(CASE WHEN t.Status = 'Failed' THEN 1 ELSE 0 END) AS FailedCount,
        SUM(CASE WHEN t.Status = 'Completed' THEN t.SendAmount ELSE 0 END) AS TotalSendAmount,
        SUM(CASE WHEN t.Status = 'Completed' THEN t.FeeAmount ELSE 0 END) AS TotalFeeAmount,
        SUM(CASE WHEN t.Status = 'Completed' THEN t.ReceiveAmount ELSE 0 END) AS TotalReceiveAmount
    FROM dbo.Transfer AS t
    INNER JOIN dbo.Corridor AS c ON c.CorridorId = t.CorridorId
    WHERE t.CreatedAt >= @FromDate
        AND t.CreatedAt < DATEADD(DAY, 1, @ToDate)
    GROUP BY
        CAST(t.CreatedAt AS DATE),
        c.CorridorId,
        c.SourceCountryCode,
        c.DestinationCountryCode,
        c.SourceCurrencyCode,
        c.DestinationCurrencyCode
    ORDER BY SummaryDate, c.CorridorId;
END;
