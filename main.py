from pathlib import Path
from typing import List, Dict, Set
from rich.console import Console
from rich.table import Table
import os
import config
import argparse
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern
import pandas as pd
from fpdf import FPDF
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    BarColumn,
    TaskProgressColumn,
)


class CommentScanner:
    def __init__(
        self,
        workspace_path: str = None,
        skip_markers: Set[str] = None,
        show_context: bool = True,
    ):
        # Resolve relative paths
        workspace_path = workspace_path or config.DEFAULT_WORKSPACE
        self.workspace_path = Path(workspace_path).resolve()
        self.console = Console()
        self.exclude_patterns = self._load_gitignore()
        self.skip_markers = skip_markers or config.DEFAULT_SKIP_MARKERS
        self.show_context = show_context

    def _load_gitignore(self) -> PathSpec:
        gitignore_patterns = []
        gitignore_path = self.workspace_path / ".gitignore"

        # Add default exclusions
        for exclude in config.DEFAULT_EXCLUDES:
            gitignore_patterns.append(exclude)

        # Read .gitignore if it exists
        if gitignore_path.exists():
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gitignore_patterns.extend(
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                )

        return PathSpec.from_lines(GitWildMatchPattern, gitignore_patterns)

    def should_skip_path(
        self,
        path: Path,
        filename_filter: str = None,
        case_sensitive: bool = False,
        complete_match: bool = False,
    ) -> bool:
        """Check if a path should be skipped based on exclusion rules and filename filter."""
        try:
            # Convert path to relative path from workspace root
            rel_path = path.relative_to(self.workspace_path)

            # Apply filename filter if provided
            if filename_filter:
                filename = path.name
                if complete_match:
                    if case_sensitive:
                        if filename != filename_filter:
                            return True
                    else:
                        if filename.lower() != filename_filter.lower():
                            return True
                else:
                    if case_sensitive:
                        if filename_filter not in filename:
                            return True
                    else:
                        if filename_filter.lower() not in filename.lower():
                            return True

            # Check if path matches gitignore patterns
            if self.exclude_patterns.match_file(str(rel_path)):
                return True

            # Skip hidden files and directories
            if any(part.startswith(".") for part in path.parts):
                return True

            return False
        except ValueError:  # For paths outside workspace
            return True

    def get_context_lines(self, all_lines: List[str], comment_line_idx: int) -> str:
        context = []
        start_idx = max(0, comment_line_idx - config.CONTEXT_LINES)
        end_idx = min(len(all_lines), comment_line_idx + config.CONTEXT_LINES + 1)

        # Get lines before
        for i in range(start_idx, comment_line_idx):
            line = all_lines[i].strip()
            if line:  # Skip empty lines
                context.append(f"  {line}")

        # Add the comment line itself
        context.append(f"→ {all_lines[comment_line_idx].strip()}")

        # Get lines after
        for i in range(comment_line_idx + 1, end_idx):
            line = all_lines[i].strip()
            if line:  # Skip empty lines
                context.append(f"  {line}")

        return "\n".join(context)

    def scan_file(self, file_path: Path) -> List[Dict]:
        comments = []
        file_extension = file_path.suffix.lower()[1:]

        # Skip files we don't support
        if file_extension not in config.COMMENT_PATTERNS:
            return comments

        comment_patterns = config.COMMENT_PATTERNS[file_extension]

        # Pre-compile patterns for faster matching
        single_patterns = comment_patterns.get("single", [])
        multiline_pattern = comment_patterns.get("multiline")

        # Quick check if file might contain any markers
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not any(marker in content for marker in config.COMMENT_MARKERS):
                    return comments

                # Reset file pointer and continue with line-by-line processing
                f.seek(0)
                lines = f.readlines()
        except UnicodeDecodeError:
            return comments  # Skip binary files

        in_multiline_comment = False
        multiline_content = []

        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line:  # Skip empty lines early
                continue

            # Fast path: check if line might contain any comment
            if not any(
                pattern in stripped_line for pattern in single_patterns
            ) and not (
                multiline_pattern
                and (
                    multiline_pattern[0] in stripped_line
                    or multiline_pattern[1] in stripped_line
                )
            ):
                continue

            # Handle multiline comments
            if multiline_pattern:
                start_pattern, end_pattern = multiline_pattern

                if (
                    start_pattern in stripped_line
                    and end_pattern
                    in stripped_line[
                        stripped_line.find(start_pattern) + len(start_pattern) :
                    ]
                ):
                    comment_text = stripped_line[
                        stripped_line.find(start_pattern)
                        + len(start_pattern) : stripped_line.rfind(end_pattern)
                    ].strip()
                    self._process_comment(
                        comment_text, comments, file_path, line_num, lines
                    )
                    continue

                if start_pattern in stripped_line and not in_multiline_comment:
                    in_multiline_comment = True
                    multiline_content = [
                        stripped_line[
                            stripped_line.find(start_pattern) + len(start_pattern) :
                        ].strip()
                    ]
                    continue

                if in_multiline_comment:
                    if end_pattern in stripped_line:
                        in_multiline_comment = False
                        multiline_content.append(
                            stripped_line[: stripped_line.find(end_pattern)].strip()
                        )
                        comment_text = " ".join(multiline_content)
                        self._process_comment(
                            comment_text, comments, file_path, line_num, lines
                        )
                        multiline_content = []
                    else:
                        multiline_content.append(stripped_line)
                    continue

            # Handle single-line comments
            for pattern in single_patterns:
                if pattern in stripped_line:
                    comment_text = stripped_line[
                        stripped_line.find(pattern) + len(pattern) :
                    ].strip()
                    self._process_comment(
                        comment_text, comments, file_path, line_num, lines
                    )
                    break

        return comments

    def _process_comment(
        self,
        comment_text: str,
        comments: List[Dict],
        file_path: Path,
        line_num: int,
        lines: List[str],
    ) -> None:
        """Helper method to process and add valid comments to the comments list."""
        for marker in config.COMMENT_MARKERS:
            if comment_text.startswith(marker) and marker not in self.skip_markers:
                comments.append(
                    {
                        "type": marker,
                        "text": comment_text[len(marker) :].strip(),
                        "file": str(file_path.relative_to(self.workspace_path)),
                        "line": line_num + 1,
                        "context": self.get_context_lines(lines, line_num),
                    }
                )
                break

    def scan_workspace(
        self,
        filename_filter: str = None,
        case_sensitive: bool = True,
        complete_match: bool = False,
    ) -> List[Dict]:
        all_comments = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
        ) as progress:
            # Start with an indeterminate progress bar
            scan_task = progress.add_task("[cyan]Scanning files...", total=None)
            files_processed = 0

            for pattern in config.FILE_PATTERNS:
                try:
                    for file_path in self.workspace_path.rglob(pattern):
                        if file_path.is_file() and not self.should_skip_path(
                            file_path, filename_filter, case_sensitive, complete_match
                        ):
                            try:
                                files_processed += 1
                                progress.update(
                                    scan_task,
                                    completed=files_processed,
                                    description=f"[cyan]Scanning: {file_path.name}",
                                )
                                file_comments = self.scan_file(file_path)
                                if file_comments:  # Only extend if we found comments
                                    all_comments.extend(file_comments)
                            except Exception as e:
                                self.console.print(
                                    f"Error scanning {file_path}: {e}", style="red"
                                )
                except Exception as e:
                    self.console.print(f"Error during workspace scan: {e}", style="red")

        return all_comments

    def display_comments(self, comments: List[Dict]):
        table = Table(title="Project Comments Overview", show_lines=True)

        table.add_column("Type", style="bold")
        table.add_column("Comment")
        if self.show_context:
            table.add_column("Context", style="dim")
        table.add_column("File", style="dim")
        table.add_column("Line", style="dim")

        for comment in sorted(comments, key=lambda x: x["type"]):
            row = [
                config.COMMENT_MARKERS[comment["type"]],
                comment["text"],
                comment["file"],
                str(comment["line"]),
            ]
            if self.show_context:
                row.insert(2, comment["context"])

            table.add_row(
                *row, style=config.COMMENT_COLORS.get(comment["type"], "white")
            )

        self.console.print(table)

    def export_to_pdf(self, comments: List[Dict], output_path: str):
        class PDF(FPDF):
            def multi_cell_row(self, heights, cols, border=1):
                # Calculate max number of lines for all columns
                max_lines = 0
                lines = []
                # Adjust widths based on whether context is shown
                if self.show_context:
                    widths = [20, 60, 60, 60, 20]  # Type, Comment, Context, File, Line
                else:
                    widths = [20, 60, 60, 20]  # Type, Comment, File, Line

                x_start = self.get_x()
                for i, col in enumerate(cols):
                    self.set_x(x_start)
                    lines.append(
                        self.multi_cell(
                            widths[i], heights, col, border=border, split_only=True
                        )
                    )
                    max_lines = max(max_lines, len(lines[-1]))

                # Draw multi-cells with same height
                height_of_line = heights
                x_start = self.get_x()
                for i in range(max_lines):
                    self.set_x(x_start)
                    for j, width in enumerate(widths):
                        content = lines[j][i] if i < len(lines[j]) else ""
                        self.multi_cell(width, height_of_line, content, border=border)
                        self.set_xy(self.get_x() + width, self.get_y() - height_of_line)
                    self.ln(height_of_line)

                return max_lines * height_of_line

        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.show_context = self.show_context

        # Add title
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, "Project Comments Overview", ln=True, align="C")
        pdf.ln(5)
        pdf.set_font("Arial", size=10)

        # Headers
        headers = ["Type", "Comment", "File", "Line"]
        if self.show_context:
            headers.insert(2, "Context")

        pdf.set_fill_color(240, 240, 240)
        pdf.multi_cell_row(8, headers)

        # Content
        for comment in sorted(comments, key=lambda x: x["type"]):
            try:
                row = [
                    config.COMMENT_MARKERS[comment["type"]],
                    comment["text"],
                    comment["file"],
                    str(comment["line"]),
                ]

                if self.show_context:
                    # Clean up context for PDF compatibility
                    context = comment["context"]
                    context = context.replace("→", ">")
                    context = context.encode("ascii", "replace").decode("ascii")
                    context = context.replace(
                        "\n", " | "
                    )  # Replace line breaks with separator
                    row.insert(2, context)

                # Clean up all cells for PDF compatibility
                row = [
                    str(cell).encode("ascii", "replace").decode("ascii") for cell in row
                ]

                pdf.multi_cell_row(8, row)

            except Exception as e:
                self.console.print(
                    f"Warning: Skipped row due to encoding issue: {e}", style="yellow"
                )

        pdf.output(output_path)

    def export_to_excel(self, comments: List[Dict], output_path: str):
        df_data = []
        for comment in comments:
            row = {
                "Type": config.COMMENT_MARKERS[comment["type"]],
                "Comment": comment["text"],
                "File": comment["file"],
                "Line": comment["line"],
            }
            if self.show_context:
                row["Context"] = comment["context"]
            df_data.append(row)

        df = pd.DataFrame(df_data)
        df.to_excel(output_path, index=False, engine="openpyxl")


def main():
    parser = argparse.ArgumentParser(
        description="Scan TypeScript project comments",
        epilog="""
Examples:
  %(prog)s                                    # Scan all files with default settings
  %(prog)s -w /path/to/project               # Scan a specific workspace
  %(prog)s -f test.py                        # Find comments in files containing 'test.py' (case insensitive)
  %(prog)s -f test.py -c                     # Find comments in files named exactly 'test.py'
  %(prog)s -f Test.py -C                     # Find comments with case-sensitive filename match
  %(prog)s -f test.py -c -C                  # Find comments in files named exactly 'test.py' (case sensitive)
  %(prog)s --skip TODO FIXME                 # Skip TODO and FIXME comments
  %(prog)s -a                                # Include all comment types
  %(prog)s -e pdf -o comments.pdf            # Export comments to PDF
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workspace", "-w", type=str, help="Path to the workspace directory"
    )
    parser.add_argument(
        "--skip",
        "-s",
        type=str,
        nargs="+",
        help="Markers to skip (e.g., --skip NOTE TODO)",
        default=list(config.DEFAULT_SKIP_MARKERS),
    )
    parser.add_argument(
        "--include-all",
        "-a",
        action="store_true",
        help="Include all markers (override default skip)",
    )
    parser.add_argument(
        "--no-context",
        "-nc",
        action="store_true",
        help="Don't show context lines around comments",
    )
    parser.add_argument(
        "--export",
        "-e",
        type=str,
        choices=config.EXPORT_FORMATS,
        help="Export format (pdf or xlsx)",
    )
    parser.add_argument("--output", "-o", type=str, help="Output file path for export")

    # Create a filename filter group
    filename_group = parser.add_argument_group("filename filtering")
    filename_group.add_argument(
        "--filename",
        "-f",
        type=str,
        help="Filter files by filename (case insensitive by default)",
    )
    filename_group.add_argument(
        "--complete-match",
        "-c",
        action="store_true",
        help="Match complete filename instead of partial (only with -f)",
    )
    filename_group.add_argument(
        "--case-sensitive",
        "-C",
        action="store_true",
        help="Make filename filter case sensitive (only with -f)",
    )

    args = parser.parse_args()

    # Update validation
    if args.case_sensitive and not args.filename:
        parser.error("--case-sensitive can only be used with --filename")
    if args.complete_match and not args.filename:
        parser.error("--complete-match can only be used with --filename")

    try:
        skip_markers = set() if args.include_all else set(args.skip)
        scanner = CommentScanner(
            args.workspace, skip_markers, show_context=not args.no_context
        )
        comments = scanner.scan_workspace(
            filename_filter=args.filename,
            case_sensitive=args.case_sensitive,
            complete_match=args.complete_match,
        )

        if not comments:
            scanner.console.print("No comments found!", style="yellow")
            return

        # Display in console
        scanner.display_comments(comments)

        # Export if requested
        if args.export:
            if not args.output:
                raise ValueError("Output path (-o) is required when exporting")

            if args.export == "pdf":
                scanner.export_to_pdf(comments, args.output)
            elif args.export == "xlsx":
                scanner.export_to_excel(comments, args.output)

            scanner.console.print(f"\nExported to {args.output}", style="green")

    except Exception as e:
        Console().print(f"Error: {str(e)}", style="red")


if __name__ == "__main__":
    main()
