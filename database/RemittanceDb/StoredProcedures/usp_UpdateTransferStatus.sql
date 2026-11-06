CREATE PROCEDURE dbo.usp_UpdateTransferStatus
    @TransferId   BIGINT,
    @NewStatus    VARCHAR(20),
    @Reason       NVARCHAR(200) = NULL,
    @ChangedAtUtc DATETIME2(3) = NULL -- Lets the data generator replay historical changes
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    SET @ChangedAtUtc = COALESCE(@ChangedAtUtc, SYSUTCDATETIME());

    DECLARE @CurrentStatus VARCHAR(20);
    DECLARE @LastUpdatedAt DATETIME2(3);

    BEGIN TRY
        BEGIN TRANSACTION;

        -- UPDLOCK stops two sessions from reading the same status and both changing it
        SELECT
            @CurrentStatus = Status,
            @LastUpdatedAt = UpdatedAt
        FROM dbo.Transfer WITH (UPDLOCK, ROWLOCK)
        WHERE TransferId = @TransferId;

        IF @CurrentStatus IS NULL
            THROW 50007, 'Transfer does not exist.', 1;

        IF NOT
        (
            (@CurrentStatus = 'Pending' AND @NewStatus IN ('Processing', 'Cancelled', 'Failed'))
            OR (@CurrentStatus = 'Processing' AND @NewStatus IN ('Completed', 'Failed'))
        )
            THROW 50008, 'This status change is not allowed.', 1;

        IF @ChangedAtUtc < @LastUpdatedAt
            THROW 50009, 'A status change cannot be earlier than the last update.', 1;

        UPDATE dbo.Transfer
        SET
            Status = @NewStatus,
            UpdatedAt = @ChangedAtUtc,
            CompletedAt = CASE WHEN @NewStatus = 'Completed' THEN @ChangedAtUtc ELSE CompletedAt END
        WHERE TransferId = @TransferId;

        INSERT INTO dbo.TransferStatusHistory (TransferId, FromStatus, ToStatus, ChangedAt, Reason)
        VALUES (@TransferId, @CurrentStatus, @NewStatus, @ChangedAtUtc, @Reason);

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
