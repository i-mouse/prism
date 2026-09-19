using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Prism.ApiService.Migrations
{
    /// <inheritdoc />
    public partial class InitialSchema : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "domains",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    name = table.Column<string>(type: "text", nullable: false),
                    prompt_schema = table.Column<string>(type: "jsonb", nullable: false),
                    is_active = table.Column<bool>(type: "boolean", nullable: false),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updated_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_domains", x => x.id);
                });

            migrationBuilder.CreateTable(
                name: "file_records",
                columns: table => new
                {
                    file_id = table.Column<Guid>(type: "uuid", nullable: false),
                    file_name = table.Column<string>(type: "text", nullable: false),
                    summary = table.Column<string>(type: "text", nullable: true),
                    status = table.Column<string>(type: "text", nullable: false),
                    uploaded_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    content_hash = table.Column<string>(type: "character varying(64)", maxLength: 64, nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_file_records", x => x.file_id);
                });

            migrationBuilder.CreateTable(
                name: "prism_documents",
                columns: table => new
                {
                    chat_id = table.Column<Guid>(type: "uuid", nullable: false),
                    user_id = table.Column<string>(type: "text", nullable: false),
                    uploaded_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    chat_title = table.Column<string>(type: "text", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_prism_documents", x => x.chat_id);
                });

            migrationBuilder.CreateTable(
                name: "document_extractors",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    file_id = table.Column<Guid>(type: "uuid", nullable: false),
                    domain_id = table.Column<Guid>(type: "uuid", nullable: false),
                    fields = table.Column<string>(type: "jsonb", nullable: false),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updated_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    latest_run_id = table.Column<Guid>(type: "uuid", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_document_extractors", x => x.id);
                    table.ForeignKey(
                        name: "fk_document_extractors_domains_domain_id",
                        column: x => x.domain_id,
                        principalTable: "domains",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "fk_document_extractors_file_records_file_id",
                        column: x => x.file_id,
                        principalTable: "file_records",
                        principalColumn: "file_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "chat_files",
                columns: table => new
                {
                    chat_id = table.Column<Guid>(type: "uuid", nullable: false),
                    file_id = table.Column<Guid>(type: "uuid", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_chat_files", x => new { x.chat_id, x.file_id });
                    table.ForeignKey(
                        name: "fk_chat_files_file_records_file_id",
                        column: x => x.file_id,
                        principalTable: "file_records",
                        principalColumn: "file_id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "fk_chat_files_prism_documents_chat_id",
                        column: x => x.chat_id,
                        principalTable: "prism_documents",
                        principalColumn: "chat_id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "paper_claims",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false),
                    document_extractor_id = table.Column<Guid>(type: "uuid", nullable: false),
                    extraction_run_id = table.Column<Guid>(type: "uuid", nullable: false),
                    claim_text_verbatim = table.Column<string>(type: "text", nullable: false),
                    claim_summary = table.Column<string>(type: "text", nullable: false),
                    label = table.Column<string>(type: "text", nullable: false),
                    grounding_status = table.Column<string>(type: "text", nullable: false),
                    missing = table.Column<bool>(type: "boolean", nullable: false),
                    reason = table.Column<string>(type: "text", nullable: true),
                    position = table.Column<int>(type: "integer", nullable: false),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    updated_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false),
                    evidence_spans = table.Column<string>(type: "jsonb", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("pk_paper_claims", x => x.id);
                    table.ForeignKey(
                        name: "fk_paper_claims_document_extractors_document_extractor_id",
                        column: x => x.document_extractor_id,
                        principalTable: "document_extractors",
                        principalColumn: "id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.InsertData(
                table: "domains",
                columns: new[] { "id", "created_at", "is_active", "name", "prompt_schema", "updated_at" },
                values: new object[] { new Guid("11111111-1111-1111-1111-111111111111"), new DateTime(2026, 8, 9, 0, 0, 0, 0, DateTimeKind.Utc), true, "research-paper", "{}", new DateTime(2026, 8, 9, 0, 0, 0, 0, DateTimeKind.Utc) });

            migrationBuilder.CreateIndex(
                name: "ix_chat_files_file_id",
                table: "chat_files",
                column: "file_id");

            migrationBuilder.CreateIndex(
                name: "ix_document_extractors_domain_id",
                table: "document_extractors",
                column: "domain_id");

            migrationBuilder.CreateIndex(
                name: "ix_document_extractors_file_id",
                table: "document_extractors",
                column: "file_id");

            migrationBuilder.CreateIndex(
                name: "ix_domains_name",
                table: "domains",
                column: "name",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "ix_file_records_content_hash",
                table: "file_records",
                column: "content_hash",
                unique: true,
                filter: "content_hash IS NOT NULL");

            migrationBuilder.CreateIndex(
                name: "ix_paper_claims_document_extractor_id_label",
                table: "paper_claims",
                columns: new[] { "document_extractor_id", "label" });

            migrationBuilder.CreateIndex(
                name: "ix_paper_claims_extraction_run_id",
                table: "paper_claims",
                column: "extraction_run_id");

            migrationBuilder.CreateIndex(
                name: "ix_paper_claims_extraction_run_id_position",
                table: "paper_claims",
                columns: new[] { "extraction_run_id", "position" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "chat_files");

            migrationBuilder.DropTable(
                name: "paper_claims");

            migrationBuilder.DropTable(
                name: "prism_documents");

            migrationBuilder.DropTable(
                name: "document_extractors");

            migrationBuilder.DropTable(
                name: "domains");

            migrationBuilder.DropTable(
                name: "file_records");
        }
    }
}
