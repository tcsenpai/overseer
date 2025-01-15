from typing import Dict
from pathlib import Path

# Default workspace path (can be overridden by CLI argument)
DEFAULT_WORKSPACE = Path.cwd()  # Current working directory by default

# Supported file patterns
FILE_PATTERNS = [
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.py",
    "*.rs",
    "*.go",
    "*.java",
    "*.c",
    "*.h",
    "*.cpp",
    "*.hpp",
    "*.cs",
    "*.vb",
    "*.sql",
    "*.md",
    "*.txt",
    "*.yaml",
    "*.yml",
    #"*.json",
    "*.xml",
    "*.html",
    "*.css",
    "*.scss",
    "*.sass",
    "*.less",
    "*.styl",
    "*.stylus",
    "*.scss",
    "*.sass",
    "*.less",
    "*.styl",
    "*.stylus",
    "*.scss",
    "*.sass",
    "*.less",
    "*.styl",
    "*.stylus",
]

# Comment markers and their descriptions
COMMENT_MARKERS: Dict[str, str] = {
    "!": "Important",
    "TODO": "To Do",
    "?": "Question",
    "REVIEW": "Needs Review",
    "FIXME": "Fix Required",
    "NOTE": "Note",
}

# Color scheme for different comment types
COMMENT_COLORS: Dict[str, str] = {
    "!": "red",
    "TODO": "yellow",
    "?": "blue",
    "REVIEW": "magenta",
    "FIXME": "red",
    "NOTE": "green",
}

# Additional exclusions
DEFAULT_EXCLUDES = {"node_modules", "__pycache__", "build", "dist"}

# Default settings
DEFAULT_SKIP_MARKERS = {"NOTE"}  # Skip NOTE comments by default
CONTEXT_LINES = 2  # Number of lines before and after to show

# Output formats
EXPORT_FORMATS = ["pdf", "xlsx"]  # Supported export formats

COMMENT_PATTERNS = {
    # Default pattern (for unknown extensions)
    "default": {"single": ["//"], "multiline": None},
    # Python
    "py": {"single": ["#"], "multiline": ['"""', '"""']},  # Also handles '''
    # JavaScript/TypeScript
    "js": {"single": ["//"], "multiline": ["/*", "*/"]},
    "ts": {"single": ["//"], "multiline": ["/*", "*/"]},
    # C/C++
    "c": {"single": ["//"], "multiline": ["/*", "*/"]},
    "cpp": {"single": ["//"], "multiline": ["/*", "*/"]},
    "h": {"single": ["//"], "multiline": ["/*", "*/"]},
    # Java
    "java": {"single": ["//"], "multiline": ["/*", "*/"]},
    # Ruby
    "rb": {"single": ["#"], "multiline": ["=begin", "=end"]},
    # PHP
    "php": {"single": ["//"], "multiline": ["/*", "*/"]},
}
