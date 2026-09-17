using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Prism.ApiService.Migrations
{
    /// <inheritdoc />
    public partial class AddExtractionStatusToFileRecord : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "status",
                table: "file_records",
                type: "text",
                nullable: false,
                defaultValue: "Pending");
                
            migrationBuilder.Sql(@"
                UPDATE file_records 
                SET status = CASE 
                    WHEN summary IS NULL THEN 'Pending' 
                    WHEN summary LIKE 'Processing failed after%' THEN 'Failed' 
                    ELSE 'Completed' 
                END
            ");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "status",
                table: "file_records");
        }
    }
}
