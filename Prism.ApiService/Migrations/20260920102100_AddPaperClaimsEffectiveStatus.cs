using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Prism.ApiService.Migrations
{
    /// <inheritdoc />
    public partial class AddPaperClaimsEffectiveStatus : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "effective_status",
                table: "paper_claims",
                type: "text",
                nullable: false,
                computedColumnSql: "CASE WHEN \"missing\" THEN 'not_supported' ELSE \"label\" END",
                stored: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "effective_status",
                table: "paper_claims");
        }
    }
}
