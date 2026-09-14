using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Prism.ApiService.Migrations
{
    /// <inheritdoc />
    /// <remarks>
    /// MANUAL DEPLOY STEP — this migration is NOT applied automatically (see
    /// docs/deployment_notes.md: RUN_MIGRATIONS_ON_STARTUP is false in Azure).
    /// It touches existing data: every current file_records row's chat_id is
    /// backfilled into the new chat_files join table before the old column is
    /// dropped. Run manually once (dotnet ef database update, or the one-shot
    /// azd/init-container deploy task) and verify:
    ///   SELECT count(*) FROM file_records;   -- N, before and after
    ///   SELECT count(*) FROM chat_files;     -- must equal N after this runs
    /// before deploying the app code from this PR (the new code assumes
    /// chat_files exists and no longer reads/writes file_records.chat_id).
    /// </remarks>
    public partial class AddContentHashAndChatFiles : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "content_hash",
                table: "file_records",
                type: "character varying(64)",
                maxLength: 64,
                nullable: true);

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

            migrationBuilder.CreateIndex(
                name: "ix_chat_files_file_id",
                table: "chat_files",
                column: "file_id");

            // BACKFILL — one chat_files row per existing file_records row. The
            // app only ever wrote one file per chat, so this is a straight 1:1
            // copy: every file_records row before this runs produces exactly one
            // chat_files row. Must run before the chat_id column below is
            // dropped, or this data is unrecoverable.
            migrationBuilder.Sql(@"
                INSERT INTO chat_files (chat_id, file_id)
                SELECT chat_id, file_id FROM file_records;
            ");

            // Now safe to drop the old 1:1 FK/index/column — every row's chat
            // link has already been copied into chat_files above.
            migrationBuilder.DropForeignKey(
                name: "fk_file_records_prism_documents_chat_id",
                table: "file_records");

            migrationBuilder.DropIndex(
                name: "ix_file_records_chat_id",
                table: "file_records");

            migrationBuilder.DropColumn(
                name: "chat_id",
                table: "file_records");

            migrationBuilder.CreateIndex(
                name: "ix_file_records_content_hash",
                table: "file_records",
                column: "content_hash",
                unique: true,
                filter: "content_hash IS NOT NULL");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "chat_id",
                table: "file_records",
                type: "uuid",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            // Best-effort backfill for rollback: picks one linked chat per file
            // (arbitrary if a file ended up linked to more than one chat after
            // this migration shipped — the pre-migration schema cannot represent
            // more than one chat per file, so a genuine many-to-many state is
            // necessarily lossy on rollback).
            migrationBuilder.Sql(@"
                UPDATE file_records fr
                SET chat_id = cf.chat_id
                FROM (
                    SELECT DISTINCT ON (file_id) file_id, chat_id
                    FROM chat_files
                    ORDER BY file_id, chat_id
                ) cf
                WHERE fr.file_id = cf.file_id;
            ");

            migrationBuilder.DropTable(
                name: "chat_files");

            migrationBuilder.DropIndex(
                name: "ix_file_records_content_hash",
                table: "file_records");

            migrationBuilder.DropColumn(
                name: "content_hash",
                table: "file_records");

            migrationBuilder.CreateIndex(
                name: "ix_file_records_chat_id",
                table: "file_records",
                column: "chat_id");

            migrationBuilder.AddForeignKey(
                name: "fk_file_records_prism_documents_chat_id",
                table: "file_records",
                column: "chat_id",
                principalTable: "prism_documents",
                principalColumn: "chat_id",
                onDelete: ReferentialAction.Cascade);
        }
    }
}
