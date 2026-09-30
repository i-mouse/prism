using Prism.ApiService.Data.Schemas;
using Prism.ApiService.Services;
using Xunit;

namespace Prism.ApiService.Tests;

public class RabbitMqListenerServiceTests
{
    [Theory]
    [InlineData("Completed", ExtractionStatus.Completed)]
    [InlineData("Error", ExtractionStatus.Failed)]
    [InlineData(null, ExtractionStatus.Failed)]
    [InlineData("", ExtractionStatus.Failed)]
    [InlineData("SomethingUnexpected", ExtractionStatus.Failed)]
    public void MapCompletionStatus_MapsAsExpected(string? statusString, ExtractionStatus expected)
    {
        var actual = RabbitMqListenerService.MapCompletionStatus(statusString);

        Assert.Equal(expected, actual);
    }

    // Regression guard: a duplicate or malformed completion message must
    // never move a paper OUT of a terminal state (Completed or Failed).
    // RabbitMQ has no persistent volume in production and the retry path is
    // republish-and-ack, so a duplicate delivery for an already-resolved
    // file is plausible - applying it would silently overwrite a Completed
    // paper's real Summary with a failure string.

    [Fact]
    public void ShouldApplyStatusTransition_CompletedPlusLaterMessage_StaysCompleted()
    {
        // "Completed + malformed message stays Completed with its Summary
        // intact" - both call sites in RabbitMqListenerService check this
        // before writing Status/Summary, so false here means the write (and
        // the Summary overwrite) never happens.
        Assert.False(RabbitMqListenerService.ShouldApplyStatusTransition(ExtractionStatus.Completed));
    }

    [Fact]
    public void ShouldApplyStatusTransition_InProgressPlusLaterMessage_BecomesFailed()
    {
        // "InProgress + malformed message becomes Failed" - true here means
        // the malformed-message branch's write is applied.
        Assert.True(RabbitMqListenerService.ShouldApplyStatusTransition(ExtractionStatus.InProgress));
    }

    [Fact]
    public void ShouldApplyStatusTransition_FailedPlusAnyLaterMessage_StaysFailed()
    {
        // "Failed + any later message stays Failed" - a second failure (or
        // a stray completion) for an already-Failed file must not reopen it.
        Assert.False(RabbitMqListenerService.ShouldApplyStatusTransition(ExtractionStatus.Failed));
    }

    [Fact]
    public void ShouldApplyStatusTransition_Pending_AllowsTheFirstTransition()
    {
        // The other non-terminal state - a paper's very first completion
        // message must still be able to land.
        Assert.True(RabbitMqListenerService.ShouldApplyStatusTransition(ExtractionStatus.Pending));
    }
}
