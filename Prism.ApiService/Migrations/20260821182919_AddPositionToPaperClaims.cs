using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Prism.ApiService.Migrations
{
    /// <inheritdoc />
    public partial class AddPositionToPaperClaims : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "position",
                table: "paper_claims",
                type: "integer",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.Sql(@"
                UPDATE paper_claims
                SET position = sub.rn - 1
                FROM (
                    SELECT id, row_number() OVER (
                        PARTITION BY extraction_run_id ORDER BY id
                    ) AS rn
                    FROM paper_claims
                ) sub
                WHERE paper_claims.id = sub.id;
            ");

            migrationBuilder.CreateIndex(
                name: "ix_paper_claims_extraction_run_id_position",
                table: "paper_claims",
                columns: new[] { "extraction_run_id", "position" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "ix_paper_claims_extraction_run_id_position",
                table: "paper_claims");

            migrationBuilder.DropColumn(
                name: "position",
                table: "paper_claims");
        }
    }
}
