CREATE PROCEDURE dbo.usp_GetTransfersUpdatedSince
    @Since DATETIME2(3)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        t.TransferId,
        t.ReferenceNumber,
        t.Status,
        t.UpdatedAt
    FROM dbo.Transfer AS t
    WHERE ISNULL(t.UpdatedAt, t.CreatedAt) >= @Since
    ORDER BY t.UpdatedAt;
END;
