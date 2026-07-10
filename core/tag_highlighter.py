# core/tag_highlighter.py
"""
Booru tag highlighter – colors tags by Danbooru category.
"""

import re
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor

# Danbooru category colors (approximate)
CATEGORY_COLORS = {
    0: QColor("#88CCEE"),  # General (light blue)
    1: QColor("#FFB347"),  # Artist (orange)
    3: QColor("#B39DDB"),  # Copyright (purple)
    4: QColor("#81C784"),  # Character (green)
    5: QColor("#FF8A65"),  # Meta (red-orange)
}

class TagHighlighter(QSyntaxHighlighter):
    def __init__(self, document, tag_category_lookup):
        super().__init__(document)
        self.tag_category_lookup = tag_category_lookup  # function(tag) -> category
        self.tag_pattern = re.compile(r'[a-zA-Z0-9_()]+')

    def highlightBlock(self, text):
        for match in self.tag_pattern.finditer(text):
            tag = match.group()
            try:
                category = self.tag_category_lookup(tag)
            except:
                category = 0
            color = CATEGORY_COLORS.get(category, CATEGORY_COLORS[0])
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.setFormat(match.start(), match.end() - match.start(), fmt)