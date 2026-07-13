# ui/dialogs/fetch_post_help.py
"""
Help window for the Fetch Tags from Booru Post dialog.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTextBrowser, QPushButton, QHBoxLayout
)
from PyQt5.QtCore import Qt

from ui.windows_theme import set_dark_title_bar

HELP_HTML = """
<style>
    body { font-family: 'Segoe UI', sans-serif; color: #e2e8f0; background: transparent; line-height: 1.6; }
    h1 { color: #a78bfa; font-size: 18px; border-bottom: 1px solid rgba(139,92,246,0.3); padding-bottom: 6px; }
    h2 { color: #c4b5fd; font-size: 14px; margin-top: 18px; }
    h3 { color: #ddd6fe; font-size: 12px; margin-top: 12px; }
    code { background: rgba(139,92,246,0.15); padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; color: #c4b5fd; }
    .tip { background: rgba(34,197,94,0.1); border-left: 3px solid #22c55e; padding: 8px 12px; margin: 8px 0; border-radius: 0 6px 6px 0; }
    .warning { background: rgba(234,179,8,0.1); border-left: 3px solid #eab308; padding: 8px 12px; margin: 8px 0; border-radius: 0 6px 6px 0; }
    .info { background: rgba(59,130,246,0.1); border-left: 3px solid #3b82f6; padding: 8px 12px; margin: 8px 0; border-radius: 0 6px 6px 0; }
    table { border-collapse: collapse; width: 100%; margin: 8px 0; }
    th { background: rgba(139,92,246,0.15); text-align: left; padding: 6px 10px; color: #c4b5fd; font-size: 11px; }
    td { padding: 6px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 12px; }
    ul { padding-left: 20px; }
    li { margin-bottom: 4px; }
</style>

<h1>Fetch Tags from Booru Post</h1>

<p>This dialog lets you pull tags directly from any booru post — just paste a URL or enter a post ID.
Tags are organized by category (Artist, Copyright, Character, General, Meta) and can be added
to your current image's tag list with one click.</p>

<h2>Quick Start</h2>
<ol>
    <li>Paste a booru post URL or ID into the <b>URL or ID</b> field</li>
    <li>The source is auto-detected, or pick one manually from the dropdown</li>
    <li>Click <b>Fetch</b> (or press Enter)</li>
    <li>Review the tags, toggle categories on/off as needed</li>
    <li>Click <b>Add Tags to Current Image</b> or <b>Replace All Tags</b></li>
</ol>

<h2>Supported Input Formats</h2>

<table>
    <tr><th>Format</th><th>Example</th><th>Notes</th></tr>
    <tr><td>Full URL</td><td><code>https://danbooru.donmai.us/posts/4861569</code></td><td>Source auto-detected from domain</td></tr>
    <tr><td>id: format</td><td><code>id:4861569</code></td><td>Requires source to be selected manually</td></tr>
    <tr><td>Plain numeric ID</td><td><code>4861569</code></td><td>Requires source to be selected manually</td></tr>
    <tr><td>Gelbooru URL</td><td><code>https://gelbooru.com/index.php?page=post&s=view&id=12345</code></td><td>Auto-detected</td></tr>
    <tr><td>Rule34 URL</td><td><code>https://rule34.xxx/index.php?page=post&s=view&id=12345</code></td><td>Auto-detected</td></tr>
    <tr><td>yande.re URL</td><td><code>https://yande.re/post/show/12345</code></td><td>Auto-detected</td></tr>
    <tr><td>Konachan URL</td><td><code>https://konachan.com/post/show/12345</code></td><td>Auto-detected</td></tr>
</table>

<div class="tip"><b>Tip:</b> You can also paste a URL directly from your browser's address bar — the source will be auto-detected.</div>

<h2>Source Selection</h2>

<table>
    <tr><th>Source</th><th>Requires Auth?</th><th>Notes</th></tr>
    <tr><td><b>Danbooru</b></td><td>Yes (API key)</td><td>Largest tag database. Best for character/artist tags.</td></tr>
    <tr><td><b>Gelbooru</b></td><td>Yes (user ID + API key)</td><td>Good for anime-style art. Requires login.</td></tr>
    <tr><td><b>Rule34</b></td><td>Yes (user ID + API key)</td><td>NSFW content. Largest rule34 database.</td></tr>
    <tr><td><b>yande.re</b></td><td>No (anonymous OK)</td><td>High-quality anime art. No auth needed.</td></tr>
    <tr><td><b>Konachan</b></td><td>No (anonymous OK)</td><td>Similar to yande.re. No auth needed.</td></tr>
</table>

<div class="info"><b>Auto-detect:</b> When set to "Auto-detect", the dialog reads the domain from the URL to determine the source. If you enter a plain ID, you must select a source manually.</div>

<h2>Tag Categories</h2>

<p>Tags are color-coded by category. Use the checkboxes to include or exclude categories:</p>

<table>
    <tr><th>Category</th><th>Color</th><th>Description</th><th>Examples</th></tr>
    <tr><td><b>Artist</b></td><td style="color:#81C784;">Green</td><td>Artist/creator name</td><td><code>hews_async</code>, <code>wlop</code></td></tr>
    <tr><td><b>Copyright</b></td><td style="color:#B39DDB;">Purple</td><td>Franchise or series</td><td><code>genshin_impact</code>, <code>fate/grand_order</code></td></tr>
    <tr><td><b>Character</b></td><td style="color:#64B5F6;">Blue</td><td>Character name</td><td><code>ganyu_(genshin_impact)</code>, <code>saber_(fate)</code></td></tr>
    <tr><td><b>General</b></td><td style="color:#FFB347;">Orange</td><td>Visual description tags</td><td><code>1girl</code>, <code>solo</code>, <code>long_hair</code></td></tr>
    <tr><td><b>Meta</b></td><td style="color:#FF8A65;">Red-orange</td><td>Technical/meta tags</td><td><code>highres</code>, <code>extremely_detailed</code></td></tr>
</table>

<div class="tip"><b>Tip:</b> If you only want visual tags, uncheck Artist, Copyright, and Character to keep only General and Meta.</div>

<h2>Format Options</h2>

<h3>Replace _ with spaces</h3>
<p>Booru tags use underscores (<code>long_hair</code>). With this checked, they become
<code>long hair</code> — more readable for SD/FLUX prompts.</p>

<h3>Comma-separated</h3>
<p>When enabled, tags are separated by commas: <code>1girl, solo, long hair</code><br>
When disabled, tags are space-separated: <code>1girl solo long hair</code></p>

<div class="info"><b>Best practice:</b> Keep <b>Comma-separated</b> ON for most workflows. SD-based models and prompt builders expect comma-separated tags.</div>

<h2>Import Options</h2>

<h3>Add Tags to Current Image</h3>
<p>Appends the fetched tags to whatever tags the current image already has. Duplicate tags are preserved (you can deduplicate later with Normalize).</p>

<h3>Replace All Tags</h3>
<p>Completely replaces the current image's tags with the fetched tags. Use this when you want a fresh start from a reference post.</p>

<div class="warning"><b>Warning:</b> "Replace All Tags" cannot be undone. Consider saving your workspace first.</div>

<h2>Examples</h2>

<h3>Example 1: Fetch from Danbooru URL</h3>
<ol>
    <li>Paste: <code>https://danbooru.donmai.us/posts/4861569</code></li>
    <li>Source auto-detects to <b>Danbooru</b></li>
    <li>Click Fetch — tags appear grouped by category</li>
    <li>Uncheck "Artist" if you don't want the artist tag</li>
    <li>Click "Add Tags to Current Image"</li>
</ol>

<h3>Example 2: Fetch by ID from yande.re</h3>
<ol>
    <li>Set Source dropdown to <b>yande.re</b></li>
    <li>Enter: <code>12345</code> (just the number)</li>
    <li>Click Fetch</li>
    <li>yande.re requires no auth, so this works out of the box</li>
</ol>

<h3>Example 3: Fetch from Gelbooru</h3>
<ol>
    <li>Make sure Gelbooru credentials are configured in Settings → Sources</li>
    <li>Paste: <code>https://gelbooru.com/index.php?page=post&s=view&id=98765</code></li>
    <li>Click Fetch</li>
</ol>

<h2>Troubleshooting</h2>

<table>
    <tr><th>Problem</th><th>Solution</th></tr>
    <tr><td>"Could not extract post ID"</td><td>Check the URL format. Try copying just the ID number.</td></tr>
    <tr><td>"Cloudflare blocked"</td><td>Set browser cookies in the source's Settings → Sources tab.</td></tr>
    <tr><td>"HTTP 401 / 403"</td><td>API credentials are missing or wrong. Check Settings → Sources.</td></tr>
    <tr><td>No tags returned</td><td>The post may have been deleted, or the source API may be down.</td></tr>
    <tr><td>Tags are missing categories</td><td>yande.re and Gelbooru don't categorize tags in their API — all tags show as "General".</td></tr>
</table>

<div class="tip"><b>Tip:</b> If a source is not working, try another one! The same post ID often exists on multiple boorus.</div>
"""


class FetchPostHelpDialog(QDialog):
    """Help window for the Fetch Tags from Booru Post dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help — Fetch Tags from Booru Post")
        self.setMinimumSize(680, 600)
        self.resize(720, 650)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(HELP_HTML)
        browser.setStyleSheet("""
            QTextBrowser {
                background: rgba(16, 18, 26, 0.85);
                color: #e2e8f0;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 12px;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: rgba(30, 32, 40, 0.8);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(139, 92, 246, 0.35);
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(100, 100, 120, 0.3);
                color: #ccc;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 20px;
            }
            QPushButton:hover { background: rgba(100, 100, 120, 0.5); }
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def showEvent(self, event):
        super().showEvent(event)
        set_dark_title_bar(self)
