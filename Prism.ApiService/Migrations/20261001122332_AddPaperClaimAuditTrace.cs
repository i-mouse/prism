using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Prism.ApiService.Migrations
{
    /// <inheritdoc />
    public partial class AddPaperClaimAuditTrace : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "audit_checklist",
                table: "paper_claims",
                type: "jsonb",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "audit_reasoning",
                table: "paper_claims",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "auditor_verdict",
                table: "paper_claims",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "cap_reason",
                table: "paper_claims",
                type: "text",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "audit_checklist",
                table: "paper_claims");

            migrationBuilder.DropColumn(
                name: "audit_reasoning",
                table: "paper_claims");

            migrationBuilder.DropColumn(
                name: "auditor_verdict",
                table: "paper_claims");

            migrationBuilder.DropColumn(
                name: "cap_reason",
                table: "paper_claims");
        }
    }
}
