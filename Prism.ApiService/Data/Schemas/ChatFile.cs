namespace Prism.ApiService.Data;

// Many-to-many join between chats and files. Introduced so that a file
// deduped-by-content-hash (see FileRecord.ContentHash) can be linked to
// every chat that uploaded matching content, instead of a file belonging
// to exactly one chat.
public class ChatFile
{
    public Guid ChatId { get; set; }
    public Guid FileId { get; set; }
}
