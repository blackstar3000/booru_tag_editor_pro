# core/syntax_highlighter.py
"""
Syntax highlighting for various file types (Python, JS, HTML, CSS, JSON, YAML, Markdown).
"""

from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, file_type="txt"):
        super().__init__(document)
        self.file_type = file_type
        self._init_formats()
        self._init_rules()

    def _init_formats(self):
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#569CD6"))
        self.keyword_format.setFontWeight(QFont.Bold)

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#CE9178"))

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#B5CEA8"))

        self.operator_format = QTextCharFormat()
        self.operator_format.setForeground(QColor("#D4D4D4"))

        self.function_format = QTextCharFormat()
        self.function_format.setForeground(QColor("#DCDCAA"))

        self.class_format = QTextCharFormat()
        self.class_format.setForeground(QColor("#4EC9B0"))

        self.decorator_format = QTextCharFormat()
        self.decorator_format.setForeground(QColor("#C586C0"))

    def _init_rules(self):
        self.rules = []

        if self.file_type in ("py", "python"):
            self.rules = [
                (QRegExp(r"\bdef\b"), self.keyword_format),
                (QRegExp(r"\bclass\b"), self.keyword_format),
                (QRegExp(r"\bimport\b"), self.keyword_format),
                (QRegExp(r"\bfrom\b"), self.keyword_format),
                (QRegExp(r"\breturn\b"), self.keyword_format),
                (QRegExp(r"\bif\b"), self.keyword_format),
                (QRegExp(r"\belse\b"), self.keyword_format),
                (QRegExp(r"\belif\b"), self.keyword_format),
                (QRegExp(r"\bfor\b"), self.keyword_format),
                (QRegExp(r"\bwhile\b"), self.keyword_format),
                (QRegExp(r"\btry\b"), self.keyword_format),
                (QRegExp(r"\bexcept\b"), self.keyword_format),
                (QRegExp(r"\bwith\b"), self.keyword_format),
                (QRegExp(r"\bas\b"), self.keyword_format),
                (QRegExp(r"\bpass\b"), self.keyword_format),
                (QRegExp(r"\bbreak\b"), self.keyword_format),
                (QRegExp(r"\bcontinue\b"), self.keyword_format),
                (QRegExp(r"\blambda\b"), self.keyword_format),
                (QRegExp(r'"[^"]*"'), self.string_format),
                (QRegExp(r"'[^']*'"), self.string_format),
                (QRegExp(r"#.*"), self.comment_format),
                (QRegExp(r"\b\d+\b"), self.number_format),
                (QRegExp(r"@\w+"), self.decorator_format),
                (QRegExp(r"\b[A-Z_][A-Z0-9_]*\b"), self.class_format),
            ]
        elif self.file_type in ("js", "javascript"):
            self.rules = [
                (QRegExp(r"\bfunction\b"), self.keyword_format),
                (QRegExp(r"\bvar\b"), self.keyword_format),
                (QRegExp(r"\blet\b"), self.keyword_format),
                (QRegExp(r"\bconst\b"), self.keyword_format),
                (QRegExp(r"\bif\b"), self.keyword_format),
                (QRegExp(r"\belse\b"), self.keyword_format),
                (QRegExp(r"\bfor\b"), self.keyword_format),
                (QRegExp(r"\bwhile\b"), self.keyword_format),
                (QRegExp(r"\breturn\b"), self.keyword_format),
                (QRegExp(r"\bclass\b"), self.keyword_format),
                (QRegExp(r"\bnew\b"), self.keyword_format),
                (QRegExp(r"\bthis\b"), self.keyword_format),
                (QRegExp(r'"[^"]*"'), self.string_format),
                (QRegExp(r"'[^']*'"), self.string_format),
                (QRegExp(r"//.*"), self.comment_format),
                (QRegExp(r"/\*.*\*/"), self.comment_format),
                (QRegExp(r"\b\d+\b"), self.number_format),
            ]
        elif self.file_type in ("html", "htm"):
            self.rules = [
                (QRegExp(r"<[^>]+>"), self.keyword_format),
                (QRegExp(r'"[^"]*"'), self.string_format),
                (QRegExp(r"'[^']*'"), self.string_format),
                (QRegExp(r"<!--.*-->"), self.comment_format),
            ]
        elif self.file_type in ("css",):
            self.rules = [
                (QRegExp(r"@[a-zA-Z-]+"), self.keyword_format),
                (QRegExp(r"[a-zA-Z-]+:"), self.keyword_format),
                (QRegExp(r'"[^"]*"'), self.string_format),
                (QRegExp(r"'[^']*'"), self.string_format),
                (QRegExp(r"/\*.*\*/"), self.comment_format),
                (QRegExp(r"\b\d+\b"), self.number_format),
            ]
        elif self.file_type in ("json",):
            self.rules = [
                (QRegExp(r'"[^"]*"'), self.string_format),
                (QRegExp(r"\btrue\b|\bfalse\b|\bnull\b"), self.keyword_format),
                (QRegExp(r"\b\d+\b"), self.number_format),
            ]
        elif self.file_type in ("yaml", "yml"):
            self.rules = [
                (QRegExp(r"^[a-zA-Z_]+:"), self.keyword_format),
                (QRegExp(r'"[^"]*"'), self.string_format),
                (QRegExp(r"'[^']*'"), self.string_format),
                (QRegExp(r"#.*"), self.comment_format),
            ]
        elif self.file_type in ("md", "markdown"):
            self.rules = [
                (QRegExp(r"^#+ "), self.keyword_format),
                (QRegExp(r"\*\*.*?\*\*"), self.keyword_format),
                (QRegExp(r"\*.*?\*"), self.keyword_format),
                (QRegExp(r"`[^`]*`"), self.string_format),
            ]
        else:
            # TXT – no syntax highlighting, but we'll use tag highlighter separately
            self.rules = []

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)