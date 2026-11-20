-- Fixed version of the bad example. UpdatedAt is NOT NULL, so the ISNULL was never needed,
-- and the bare column lets SQL Server seek IX_Transfer_UpdatedAt.
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
    WHERE t.UpdatedAt >= @Since
    ORDER BY t.UpdatedAt;
END;
