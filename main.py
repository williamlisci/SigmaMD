import json
import sys
from pathlib import Path

import markdown

from PySide6.QtCore import QEvent, QSettings, QTimer, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QFont,
    QIcon,
    QKeySequence,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView


APP_NAME = "SigmaMD"
PREVIEW_THEMES = {
    "light": "Light",
    "dark": "Dark",
    "sepia": "Sepia",
}


def application_dir() -> Path:
    """Return the resource directory in source and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


class SigmaMD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_path: Path | None = None
        self.settings = QSettings(APP_NAME, APP_NAME)
        saved_theme = self.settings.value("preview_theme", "light", type=str)
        self.preview_theme = (
            saved_theme if saved_theme in PREVIEW_THEMES else "light"
        )
        self._loading_file = False
        self.autosave_enabled = True
        self._preview_ready = False
        self._preview_loading = False
        self._preview_template_loading = False
        self._pending_preview_body: str | None = None
        self._syncing_editor_scroll = False
        self._editor_scroll_generation = 0
        self._preview_scroll_generation = 0
        self.find_dialog = None
        self.find_input = None
        self.find_case_sensitive = None
        self.find_status = None

        icon_path = application_dir() / "assets" / "SigmaMD.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setMinimumSize(850, 550)
        self.resize(1200, 760)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Viết nội dung Markdown tại đây...")
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.cursorPositionChanged.connect(
            self.update_selection_toolbar
        )

        self.preview = QWebEngineView()

        # Accept files dragged from Windows File Explorer. Qt scroll areas
        # deliver drop events to their viewport, and WebEngine may deliver them
        # to internal child widgets, so install the filter throughout both panes.
        self._drop_filter_targets: list[QWidget] = []
        self.setAcceptDrops(True)
        self._install_drop_filters(self.editor)
        self._install_drop_filters(self.editor.viewport())
        self._install_drop_filters(self.preview)
        self.preview.loadFinished.connect(
            lambda _ok: self._install_drop_filters(self.preview)
        )
        self.preview.loadFinished.connect(self._on_preview_load_finished)
        self.preview.page().scrollPositionChanged.connect(
            self.sync_editor_scroll
        )
        self.editor.verticalScrollBar().valueChanged.connect(
            self.sync_preview_scroll
        )
        QTimer.singleShot(0, self._install_all_drop_filters)

        # Keep KaTeX local/offline while allowing local CSS, JavaScript and fonts.
        settings = self.preview.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            False,
        )

        splitter = QSplitter()
        splitter.addWidget(self.editor)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 600])
        self.setCentralWidget(splitter)
        self._create_selection_toolbar()
        self.statusBar().showMessage("Sẵn sàng")

        self.editor.textChanged.connect(self.schedule_preview)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self.update_preview)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(5000)
        self.autosave_timer.timeout.connect(self.autosave_file)
        self.editor.textChanged.connect(self.schedule_autosave)
        self.editor.document().modificationChanged.connect(
            self.update_window_title
        )

        self.create_menus()
        self.update_window_title()
        self.update_preview()

    def create_action(self, menu, text, shortcut, callback):
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _create_selection_toolbar(self):
        self.selection_toolbar = QToolBar(self)
        self.selection_toolbar.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        )
        self.selection_toolbar.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextOnly
        )
        self.selection_toolbar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.selection_toolbar.setMovable(False)

        formats = (
            ("B", "**", "**", "In đậm"),
            ("I", "*", "*", "In nghiêng"),
            ("U", "<u>", "</u>", "Gạch chân"),
            ("S", "~~", "~~", "Gạch ngang"),
            ("`", "`", "`", "Mã nội dòng"),
        )
        for label, prefix, suffix, tooltip in formats:
            action = self.selection_toolbar.addAction(label)
            action.setToolTip(tooltip)
            action.triggered.connect(
                lambda _checked=False, before=prefix, after=suffix: (
                    self.format_selection(before, after)
                )
            )

        self.selection_toolbar.addSeparator()
        link_action = self.selection_toolbar.addAction("Link")
        link_action.setToolTip("Chèn liên kết")
        link_action.triggered.connect(self.format_selection_as_link)
        for button in self.selection_toolbar.findChildren(QToolButton):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.selection_toolbar.adjustSize()
        self.selection_toolbar.hide()

    def update_selection_toolbar(self):
        selected_text = self.editor.textCursor().selectedText()
        self.sync_preview_selection(selected_text)
        if not selected_text:
            self.selection_toolbar.hide()
            return

        cursor_rect = self.editor.cursorRect(self.editor.textCursor())
        position = self.editor.viewport().mapToGlobal(
            cursor_rect.bottomLeft()
        )
        self.selection_toolbar.adjustSize()
        screen = QApplication.screenAt(position) or self.screen()
        available = screen.availableGeometry()
        x = min(
            max(position.x(), available.left()),
            available.right() - self.selection_toolbar.width() + 1,
        )
        y = position.y() + 4
        if y + self.selection_toolbar.height() > available.bottom():
            y = position.y() - self.selection_toolbar.height() - 4
        self.selection_toolbar.move(x, y)
        self.selection_toolbar.show()

    def format_selection(self, prefix: str, suffix: str):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        if not selected_text:
            return

        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        before = QTextCursor(cursor)
        before.setPosition(start)
        before.movePosition(
            QTextCursor.MoveOperation.PreviousCharacter,
            QTextCursor.MoveMode.KeepAnchor,
            len(prefix),
        )
        after = QTextCursor(cursor)
        after.setPosition(end)
        after.movePosition(
            QTextCursor.MoveOperation.NextCharacter,
            QTextCursor.MoveMode.KeepAnchor,
            len(suffix),
        )

        if before.selectedText() == prefix and after.selectedText() == suffix:
            edit_cursor = QTextCursor(cursor)
            edit_cursor.setPosition(start - len(prefix))
            edit_cursor.setPosition(
                end + len(suffix), QTextCursor.MoveMode.KeepAnchor
            )
            edit_cursor.insertText(selected_text)
            content = selected_text
            selection_start = start - len(prefix)
            result_cursor = edit_cursor
        else:
            content = selected_text
            cursor.insertText(f"{prefix}{content}{suffix}")
            selection_start = start + len(prefix.encode("utf-16-le")) // 2
            result_cursor = cursor

        result_cursor.setPosition(selection_start)
        result_cursor.setPosition(
            selection_start + len(content.encode("utf-16-le")) // 2,
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.editor.setTextCursor(result_cursor)
        self.editor.setFocus()

    def sync_preview_selection(self, selected_text: str | None = None):
        if not self._preview_ready:
            return
        if selected_text is None:
            selected_text = self.editor.textCursor().selectedText()
        selected_text = selected_text.replace("\u2029", "\n")
        self.preview.page().runJavaScript(
            "window.syncEditorSelection && "
            f"window.syncEditorSelection({json.dumps(selected_text)});"
        )

    def format_selection_as_link(self):
        cursor = self.editor.textCursor()
        selected_text = cursor.selectedText()
        if not selected_text:
            return

        url, accepted = QInputDialog.getText(
            self, "Chèn liên kết", "Địa chỉ liên kết:"
        )
        if not accepted or not url:
            return

        start = cursor.selectionStart()
        cursor.insertText(f"[{selected_text}]({url})")
        cursor.setPosition(start + 1)
        cursor.setPosition(
            start + 1 + len(selected_text.encode("utf-16-le")) // 2,
            QTextCursor.MoveMode.KeepAnchor,
        )
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def create_menus(self):
        file_menu = self.menuBar().addMenu("&File")
        self.create_action(
            file_menu, "&New", QKeySequence.StandardKey.New, self.new_file
        )
        self.create_action(
            file_menu, "&Open...", QKeySequence.StandardKey.Open, self.open_file
        )
        file_menu.addSeparator()
        self.restore_session_action = self.create_action(
            file_menu,
            "Restore Previous Session",
            None,
            self.restore_previous_session,
        )
        self.restore_session_action.setEnabled(
            bool(self.settings.value("last_opened_file", "", type=str))
        )
        file_menu.addSeparator()
        self.create_action(
            file_menu, "&Save", QKeySequence.StandardKey.Save, self.save_file
        )
        self.create_action(
            file_menu,
            "Save &As...",
            QKeySequence.StandardKey.SaveAs,
            self.save_file_as,
        )
        file_menu.addSeparator()
        self.autosave_action = self.create_action(
            file_menu,
            "Autosave after 5 seconds",
            None,
            self.set_autosave_enabled,
        )
        self.autosave_action.setCheckable(True)
        self.autosave_action.setChecked(self.autosave_enabled)
        file_menu.addSeparator()
        self.create_action(
            file_menu, "E&xit", QKeySequence.StandardKey.Quit, self.close
        )

        edit_menu = self.menuBar().addMenu("&Edit")
        self.create_action(
            edit_menu,
            "&Find...",
            QKeySequence.StandardKey.Find,
            self.show_find_dialog,
        )
        edit_menu.addSeparator()
        self.create_action(
            edit_menu, "Undo", QKeySequence.StandardKey.Undo, self.editor.undo
        )
        self.create_action(
            edit_menu, "Redo", QKeySequence.StandardKey.Redo, self.editor.redo
        )
        edit_menu.addSeparator()
        self.create_action(
            edit_menu, "Cut", QKeySequence.StandardKey.Cut, self.editor.cut
        )
        self.create_action(
            edit_menu, "Copy", QKeySequence.StandardKey.Copy, self.editor.copy
        )
        self.create_action(
            edit_menu, "Paste", QKeySequence.StandardKey.Paste, self.editor.paste
        )
        self.create_action(
            edit_menu,
            "Select All",
            QKeySequence.StandardKey.SelectAll,
            self.editor.selectAll,
        )

        view_menu = self.menuBar().addMenu("&View")
        preview_theme_menu = view_menu.addMenu("Preview Theme")
        preview_theme_group = QActionGroup(self)
        preview_theme_group.setExclusive(True)
        for theme, label in PREVIEW_THEMES.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(theme == self.preview_theme)
            action.triggered.connect(
                lambda checked, selected_theme=theme: (
                    self.set_preview_theme(selected_theme) if checked else None
                )
            )
            preview_theme_group.addAction(action)
            preview_theme_menu.addAction(action)

    def set_preview_theme(self, theme: str):
        if theme not in PREVIEW_THEMES or theme == self.preview_theme:
            return

        self.preview_theme = theme
        self.settings.setValue("preview_theme", theme)
        if self._preview_ready:
            self.preview.page().runJavaScript(
                "document.body.dataset.theme = "
                f"{json.dumps(theme)};"
            )

    def show_find_dialog(self):
        if self.find_dialog is None:
            self.find_dialog = QDialog(self)
            self.find_dialog.setWindowTitle("Find")
            self.find_dialog.setWindowModality(Qt.WindowModality.NonModal)

            layout = QVBoxLayout(self.find_dialog)
            layout.addWidget(QLabel("Find what:", self.find_dialog))

            self.find_input = QLineEdit(self.find_dialog)
            self.find_input.setClearButtonEnabled(True)
            self.find_input.returnPressed.connect(self.find_next)
            layout.addWidget(self.find_input)

            self.find_case_sensitive = QCheckBox(
                "Match case", self.find_dialog
            )
            layout.addWidget(self.find_case_sensitive)

            self.find_status = QLabel("", self.find_dialog)
            layout.addWidget(self.find_status)

            buttons = QHBoxLayout()
            previous_button = QPushButton("Previous", self.find_dialog)
            previous_button.clicked.connect(self.find_previous)
            buttons.addWidget(previous_button)
            next_button = QPushButton("Next", self.find_dialog)
            next_button.clicked.connect(self.find_next)
            buttons.addWidget(next_button)
            close_button = QPushButton("Close", self.find_dialog)
            close_button.clicked.connect(self.find_dialog.hide)
            buttons.addWidget(close_button)
            layout.addLayout(buttons)

        selected_text = self.editor.textCursor().selectedText()
        if selected_text and "\n" not in selected_text:
            self.find_input.setText(selected_text)
            self.find_input.selectAll()
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()
        self.find_input.setFocus()

    def find_next(self):
        self.find_in_editor()

    def find_previous(self):
        self.find_in_editor(backward=True)

    def find_in_editor(self, backward=False):
        search_text = self.find_input.text()
        if not search_text:
            self.find_status.clear()
            return

        flags = QTextDocument.FindFlag(0)
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        if self.find_case_sensitive.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively

        if self.editor.find(search_text, flags):
            self.find_status.clear()
            return

        cursor = self.editor.textCursor()
        cursor.movePosition(
            QTextCursor.MoveOperation.End
            if backward
            else QTextCursor.MoveOperation.Start
        )
        self.editor.setTextCursor(cursor)
        if self.editor.find(search_text, flags):
            self.find_status.clear()
            return

        self.find_status.setText("No matches found")

    def _install_drop_filters(self, root: QWidget):
        """Install drag/drop interception on a widget and its current children."""
        targets = [root, *root.findChildren(QWidget)]
        for target in targets:
            if any(target is installed for installed in self._drop_filter_targets):
                continue
            target.setAcceptDrops(True)
            target.installEventFilter(self)
            self._drop_filter_targets.append(target)

    def _install_all_drop_filters(self):
        """Re-scan both panes because Qt WebEngine may create internal widgets lazily."""
        self._install_drop_filters(self)
        self._install_drop_filters(self.editor)
        self._install_drop_filters(self.editor.viewport())
        self._install_drop_filters(self.preview)

    def eventFilter(self, watched, event):
        """Open local Markdown files dropped onto the editor or WebEngine pane."""
        event_type = event.type()

        # WebEngine creates internal child widgets after initialisation. Re-scan
        # on the next event-loop turn so drops on those widgets are intercepted.
        if event_type == QEvent.Type.ChildAdded:
            QTimer.singleShot(0, self._install_all_drop_filters)
            return super().eventFilter(watched, event)

        if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            path = self._markdown_path_from_event(event)
            if path is not None:
                event.acceptProposedAction()
                return True

        elif event_type == QEvent.Type.Drop:
            path = self._markdown_path_from_event(event)
            if path is not None:
                event.acceptProposedAction()
                self.open_path(path)
                return True

        return super().eventFilter(watched, event)

    @staticmethod
    def _markdown_path_from_event(event) -> Path | None:
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return None

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            path = Path(url.toLocalFile())
            if path.suffix.lower() in {".md", ".markdown"} and path.is_file():
                return path

        return None

    def schedule_autosave(self):
        if not self._loading_file and self.autosave_enabled:
            self.autosave_timer.start()

    def schedule_preview(self):
        if not self._loading_file:
            self.preview_timer.start()

    def set_autosave_enabled(self, enabled: bool):
        self.autosave_enabled = enabled
        if enabled:
            self.schedule_autosave()
        else:
            self.autosave_timer.stop()

    def autosave_file(self):
        if not self.autosave_enabled or not self.editor.document().isModified():
            return
        if self.current_path is None:
            self.statusBar().showMessage(
                "Save this Markdown file first to use autosave", 4000
            )
            return
        if self.current_path.suffix.lower() not in {".md", ".markdown"}:
            return
        self.save_file(is_autosave=True)

    def update_preview(self):
        source = self.editor.toPlainText()
        body = markdown.markdown(
            source,
            extensions=[
                "fenced_code",
                "tables",
                "sane_lists",
                "pymdownx.tilde",
                "pymdownx.arithmatex",
            ],
            extension_configs={
                "pymdownx.arithmatex": {"generic": True},
            },
        )
        self._pending_preview_body = body

        katex_dir = application_dir() / "assets" / "katex"
        css_file = katex_dir / "katex.min.css"
        js_file = katex_dir / "katex.min.js"
        render_file = katex_dir / "contrib" / "auto-render.min.js"

        missing = [
            str(path.relative_to(application_dir()))
            for path in (css_file, js_file, render_file)
            if not path.is_file()
        ]
        if missing:
            self._preview_ready = False
            self._preview_template_loading = False
            self._preview_loading = True
            details = "<br>".join(missing)
            error_html = f"""<!DOCTYPE html>
<html lang="vi"><meta charset="utf-8">
<body style="font-family:Segoe UI;padding:24px">
<h2>Không tìm thấy tệp KaTeX</h2>
<p>Kiểm tra các tệp sau trong thư mục SigmaMD:</p>
<p>{details}</p>
</body></html>"""
            self.preview.setHtml(error_html)
            return

        css_url = QUrl.fromLocalFile(str(css_file.resolve())).toString()
        js_url = QUrl.fromLocalFile(str(js_file.resolve())).toString()
        render_url = QUrl.fromLocalFile(str(render_file.resolve())).toString()

        # Keep links/images relative to the Markdown file, not the application folder.
        base_dir = self.current_path.parent if self.current_path else Path.cwd()
        base_url = QUrl.fromLocalFile(str(base_dir.resolve()) + "/")
        if self._preview_ready:
            self._apply_preview_body(body, base_url.toString())
            return
        if self._preview_loading:
            return

        template = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base href="__BASE_URL__">
<link rel="stylesheet" href="__KATEX_CSS__">
<style>
:root {
    color-scheme: light;
    --page-background: #fff;
    --text-color: #20242b;
    --code-background: #f2f4f7;
    --blockquote-border: #c8ced8;
    --blockquote-color: #535b68;
    --table-border: #d6dae1;
    --link-color: #1769aa;
    --rule-color: #ddd;
}
body[data-theme="dark"] {
    color-scheme: dark;
    --page-background: #1e1f22;
    --text-color: #e6e8eb;
    --code-background: #2b2d31;
    --blockquote-border: #555b66;
    --blockquote-color: #b7bdc7;
    --table-border: #454951;
    --link-color: #7ab8ff;
    --rule-color: #454951;
}
body[data-theme="sepia"] {
    color-scheme: light;
    --page-background: #f4ecd8;
    --text-color: #433522;
    --code-background: #e9dec5;
    --blockquote-border: #b8a889;
    --blockquote-color: #66573f;
    --table-border: #cfc1a6;
    --link-color: #79521c;
    --rule-color: #cfc1a6;
}
body {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 15px;
    line-height: 1.7;
    color: var(--text-color);
    background: var(--page-background);
    margin: 0;
    padding: 24px;
    overflow-wrap: anywhere;
    overflow-anchor: none;
}
main { max-width: 950px; margin: 0 auto; }
main ::selection { background: #b9d7ff; }
h1, h2, h3, h4 { line-height: 1.35; margin-top: 1.5em; }
pre { padding: 14px; overflow-x: auto; background: var(--code-background); border-radius: 6px; }
code { font-family: Consolas, monospace; background: var(--code-background); padding: 2px 4px; border-radius: 3px; }
pre code { padding: 0; }
blockquote { margin-left: 0; padding-left: 16px; border-left: 3px solid var(--blockquote-border); color: var(--blockquote-color); }
table { border-collapse: collapse; max-width: 100%; }
th, td { border: 1px solid var(--table-border); padding: 7px 10px; }
img { max-width: 100%; height: auto; }
a { color: var(--link-color); }
hr { border: none; border-top: 1px solid var(--rule-color); }
.katex-display { overflow-x: auto; overflow-y: hidden; padding: 4px 0; }
</style>
</head>
<body data-theme="__PREVIEW_THEME__">
<main>
<!-- MARKDOWN_CONTENT -->
</main>
<script>
window.syncEditorSelection = (selectedText) => {
    const main = document.querySelector("main");
    const selection = window.getSelection();
    if (!main || !selection) return;
    selection.removeAllRanges();
    if (!selectedText) return;

    const cleanMarkdown = (text) => text
        .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
        .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
        .replace(/(\*\*|__|~~|`|[*_])/g, "")
        .replace(/^#{1,6}\s+/gm, "");
    const normalize = (text) => text.replace(/\s+/g, " ").trim();
    let flattened = "";
    const positions = [];
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    const blockTags = new Set([
        "BLOCKQUOTE", "DIV", "H1", "H2", "H3", "H4", "H5", "H6",
        "LI", "P", "PRE", "TD", "TH"
    ]);
    const blockParent = (textNode) => {
        let element = textNode.parentElement;
        while (element && element !== main && !blockTags.has(element.tagName)) {
            element = element.parentElement;
        }
        return element;
    };
    let previousBlock = null;
    let node;
    while ((node = walker.nextNode())) {
        const currentBlock = blockParent(node);
        if (previousBlock && currentBlock !== previousBlock &&
            flattened && !flattened.endsWith(" ")) {
            flattened += " ";
            positions.push({node, offset: 0});
        }
        previousBlock = currentBlock;
        const value = node.nodeValue || "";
        for (let offset = 0; offset < value.length; offset += 1) {
            const character = value[offset];
            if (/\s/.test(character)) {
                if (!flattened || flattened.endsWith(" ")) continue;
                flattened += " ";
            } else {
                flattened += character;
            }
            positions.push({node, offset});
        }
    }

    const exactTarget = normalize(selectedText);
    const markdownTarget = normalize(cleanMarkdown(selectedText));
    const start = flattened.indexOf(exactTarget);
    const target = start >= 0 ? exactTarget : markdownTarget;
    const matchStart = start >= 0 ? start : flattened.indexOf(target);
    if (!target || matchStart < 0 || !positions[matchStart] ||
        !positions[matchStart + target.length - 1]) {
        return;
    }
    const range = document.createRange();
    range.setStart(positions[matchStart].node, positions[matchStart].offset);
    const end = positions[matchStart + target.length - 1];
    range.setEnd(end.node, end.offset + 1);
    selection.addRange(range);
};
</script>
<script src="__KATEX_JS__"></script>
<script src="__KATEX_RENDER__"></script>
<script>
if (typeof renderMathInElement === "function") {
    renderMathInElement(document.querySelector("main"), {
        delimiters: [
            {left: "$$", right: "$$", display: true},
            {left: "\\[", right: "\\]", display: true},
            {left: "\\(", right: "\\)", display: false},
            {left: "$", right: "$", display: false}
        ],
        ignoredTags: [
            "script", "noscript", "style", "textarea", "pre",
            "code", "option"
        ],
        throwOnError: false
    });
} else {
    document.querySelector("main").insertAdjacentHTML(
        "afterbegin",
        "<p style='color:#b00020'>Không tải được bộ xử lý KaTeX auto-render.</p>"
    );
}
</script>
</body>
</html>"""

        html = (
            template.replace("__BASE_URL__", base_url.toString())
            .replace("__KATEX_CSS__", css_url)
            .replace("__KATEX_JS__", js_url)
            .replace("__KATEX_RENDER__", render_url)
            .replace("__PREVIEW_THEME__", self.preview_theme)
            .replace("<!-- MARKDOWN_CONTENT -->", body)
        )
        self._preview_loading = True
        self._preview_template_loading = True
        self.preview.setHtml(html, base_url)

    def _on_preview_load_finished(self, success: bool):
        if not self._preview_loading:
            return

        self._preview_loading = False
        if not self._preview_template_loading:
            return

        self._preview_template_loading = False
        if not success:
            return

        self._preview_ready = True
        base_dir = self.current_path.parent if self.current_path else Path.cwd()
        base_url = QUrl.fromLocalFile(str(base_dir.resolve()) + "/").toString()
        self._apply_preview_body(self._pending_preview_body or "", base_url)
        self.sync_preview_scroll(self.editor.verticalScrollBar().value())

    def _apply_preview_body(self, body: str, base_url: str):
        script = f"""(() => {{
    const main = document.querySelector("main");
    const base = document.querySelector("base");
    if (!main || !base) return;
    const scrollY = window.scrollY;
    base.href = {json.dumps(base_url)};
    document.body.dataset.theme = {json.dumps(self.preview_theme)};
    main.innerHTML = {json.dumps(body)};
    if (typeof renderMathInElement === "function") {{
        renderMathInElement(main, {{
            delimiters: [
                {{left: "$$", right: "$$", display: true}},
                {{left: "\\\\[", right: "\\\\]", display: true}},
                {{left: "\\\\(", right: "\\\\)", display: false}},
                {{left: "$", right: "$", display: false}}
            ],
            ignoredTags: [
                "script", "noscript", "style", "textarea", "pre",
                "code", "option"
            ],
            throwOnError: false
        }});
    }}
    if (window.syncEditorSelection) {{
        window.syncEditorSelection(
            {json.dumps(self.editor.textCursor().selectedText().replace(chr(0x2029), chr(10)))}
        );
    }}
    window.scrollTo(0, scrollY);
}})();"""
        self.preview.page().runJavaScript(script)

    def sync_preview_scroll(self, editor_value: int):
        if not self._preview_ready or self._syncing_editor_scroll:
            return

        self._editor_scroll_generation += 1
        scrollbar = self.editor.verticalScrollBar()
        ratio = editor_value / scrollbar.maximum() if scrollbar.maximum() else 0
        self.preview.page().runJavaScript(
            "(() => {"
            "const max = Math.max(0, "
            "document.documentElement.scrollHeight - window.innerHeight);"
            f"window.scrollTo(0, max * {ratio});"
            "})();"
        )

    def sync_editor_scroll(self, _position):
        if not self._preview_ready or self._syncing_editor_scroll:
            return

        self._preview_scroll_generation += 1
        editor_generation = self._editor_scroll_generation
        preview_generation = self._preview_scroll_generation
        self.preview.page().runJavaScript(
            "(() => {"
            "const max = Math.max(0, "
            "document.documentElement.scrollHeight - window.innerHeight);"
            "return max ? window.scrollY / max : 0;"
            "})()",
            lambda ratio: self._set_editor_scroll(
                ratio, editor_generation, preview_generation
            ),
        )

    def _set_editor_scroll(
        self, ratio: float, editor_generation: int, preview_generation: int
    ):
        if (
            editor_generation != self._editor_scroll_generation
            or preview_generation != self._preview_scroll_generation
            or not isinstance(ratio, (int, float))
        ):
            return

        ratio = min(1.0, max(0.0, ratio))
        scrollbar = self.editor.verticalScrollBar()
        self._syncing_editor_scroll = True
        scrollbar.setValue(round(ratio * scrollbar.maximum()))
        self._syncing_editor_scroll = False

    def update_window_title(self, *_):
        name = self.current_path.name if self.current_path else "Untitled.md"
        marker = " *" if self.editor.document().isModified() else ""
        self.setWindowTitle(f"{APP_NAME} — {name}{marker}")

    def maybe_save(self):
        if not self.editor.document().isModified():
            return True

        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            "File có thay đổi chưa được lưu. Bạn muốn lưu không?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Yes:
            return self.save_file()
        return True

    def new_file(self):
        if not self.maybe_save():
            return
        self.current_path = None
        self._loading_file = True
        self.editor.clear()
        self.editor.document().setModified(False)
        self._loading_file = False
        self.update_window_title()
        self.update_preview()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Markdown",
            str(self.current_path.parent) if self.current_path else str(Path.cwd()),
            "Markdown files (*.md *.markdown);;All files (*.*)",
        )
        if path:
            self.open_path(path)

    def restore_previous_session(self):
        path = self.settings.value("last_opened_file", "", type=str)
        if path:
            self.open_path(path)

    def open_path(self, file_path: str | Path) -> bool:
        """Open a Markdown file supplied by the dialog or Windows file association."""
        path = Path(file_path).expanduser()

        if not path.is_file():
            QMessageBox.critical(
                self,
                "Open failed",
                f"Không tìm thấy file:\n{path}",
            )
            return False

        if not self.maybe_save():
            return False

        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            QMessageBox.critical(self, "Open failed", str(error))
            return False

        self.current_path = path.resolve()
        self.remember_current_file()
        self._loading_file = True
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)
        self._loading_file = False
        self.update_window_title()
        self.update_preview()
        self.statusBar().showMessage(f"Opened: {self.current_path}", 4000)
        return True

    def remember_current_file(self):
        if self.current_path is None:
            return
        self.settings.setValue("last_opened_file", str(self.current_path))
        self.restore_session_action.setEnabled(True)

    def save_file(self, is_autosave: bool = False):
        if self.current_path is None:
            return self.save_file_as()
        self.autosave_timer.stop()
        try:
            self.current_path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Save failed", str(error))
            return False

        self.editor.document().setModified(False)
        self.update_window_title()
        status = "Autosaved" if is_autosave else "Saved"
        self.statusBar().showMessage(f"{status}: {self.current_path}", 4000)
        return True

    def save_file_as(self):
        default_path = (
            str(self.current_path)
            if self.current_path
            else str(Path.cwd() / "untitled.md")
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Markdown As",
            default_path,
            "Markdown files (*.md);;All files (*.*)",
        )
        if not path:
            return False

        new_path = Path(path)
        if not new_path.suffix:
            new_path = new_path.with_suffix(".md")

        old_path = self.current_path
        self.current_path = new_path
        if not self.save_file():
            self.current_path = old_path
            self.update_window_title()
            return False
        self.remember_current_file()
        self.update_preview()
        return True

    def closeEvent(self, event):
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    icon_path = application_dir() / "assets" / "SigmaMD.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = SigmaMD()
    window.show()

    if len(sys.argv) > 1:
        # A file explicitly opened from Windows takes precedence over the session.
        QTimer.singleShot(0, lambda path=sys.argv[1]: window.open_path(path))
    else:
        previous_file = window.settings.value("last_opened_file", "", type=str)
        if previous_file:
            QTimer.singleShot(
                0, lambda path=previous_file: window.open_path(path)
            )

    sys.exit(app.exec())
