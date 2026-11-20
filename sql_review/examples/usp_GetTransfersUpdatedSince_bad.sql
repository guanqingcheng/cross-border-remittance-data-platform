-- Deliberately bad example for the AI SQL review demo. It is not part of the database project.
-- The ISNULL around t.UpdatedAt stops SQL Server from seeking IX_Transfer_UpdatedAt (rule R1).
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
