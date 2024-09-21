from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMenuBar, QFileDialog, QMessageBox, QMenu, QInputDialog
)
from PyQt6.Qsci import QsciScintilla
from PyQt6.QtGui import QColor, QFont, QAction
import os

from simplenet.gui.pyeasyedit.LexersCustom import CustomYAMLLexer, CustomPythonLexer, CustomJSONLexer, \
    CustomJavaScriptLexer, CustomHTMLLexer, CustomCSSLexer, CustomSQLLexer, CustomXMLLexer, CustomBashLexer, \
    CustomBatchLexer
from simplenet.gui.pyeasyedit.__main__ import QScintillaEditorWidget

# Example LEXER_MAP_MENU and GLOBAL_COLOR_SCHEME
LEXER_MAP_MENU = {
    ".py": CustomPythonLexer,
    ".json": CustomJSONLexer,
    ".js": CustomJavaScriptLexer,
    ".yaml": CustomYAMLLexer, ".yml": CustomYAMLLexer,
    ".html": CustomHTMLLexer, ".htm": CustomHTMLLexer,
    ".css": CustomCSSLexer,
    ".sql": CustomSQLLexer,
    ".xml": CustomXMLLexer,
    ".sh": CustomBashLexer,
    ".bat": CustomBatchLexer
}

GLOBAL_COLOR_SCHEME = {
    "Keyword": "#FFC66D",
    "Comment": "#367d36",
    "ClassName": "#FFEEAD",
    "FunctionMethodName": "#be6ff2",
    "TripleSingleQuotedString": "#7bd9db",
    "TripleDoubleQuotedString": "#7bd9db",
    "SingleQuotedString": "#7bd9db",
    "DoubleQuotedString": "#7bd9db",
}

class EditorWithMenu(QWidget):
    def __init__(self, defaultFolderPath, parent=None):
        super().__init__(parent)
        self.defaultFolderPath = defaultFolderPath
        self.current_file_path = None  # To keep track of the current file path

        # Set up the layout
        layout = QVBoxLayout(self)

        # Create the menu bar
        self.menuBar = QMenuBar(self)
        layout.setMenuBar(self.menuBar)

        # Set up the file menu
        fileMenu = self.menuBar.addMenu("&File")
        newAction = QAction("&New", self)
        newAction.setShortcut("Ctrl+N")
        newAction.triggered.connect(self.new_file)
        fileMenu.addAction(newAction)

        openAction = QAction("&Open", self)
        openAction.triggered.connect(self.open_file)
        fileMenu.addAction(openAction)

        saveAction = QAction("&Save", self)
        saveAction.triggered.connect(self.save_file)
        fileMenu.addAction(saveAction)

        saveAsAction = QAction("Save &As...", self)
        saveAsAction.triggered.connect(self.save_file_as)
        fileMenu.addAction(saveAsAction)

        # Add other menus (Edit, View, Help) and their actions
        editMenu = self.menuBar.addMenu("&Edit")
        searchAction = QAction("&Find", self)
        searchAction.setShortcut("Ctrl+F")
        searchAction.triggered.connect(self.search)
        editMenu.addAction(searchAction)

        replaceAction = QAction("&Replace", self)
        replaceAction.setShortcut("Ctrl+R")
        replaceAction.triggered.connect(self.replace)
        editMenu.addAction(replaceAction)

        viewMenu = self.menuBar.addMenu("&View")
        syntaxMenu = QMenu("Syntax", self)
        viewMenu.addMenu(syntaxMenu)

        # Populate the syntax menu with lexer options
        for name, lexer_class in LEXER_MAP_MENU.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked, lx=lexer_class: self.changeLexer(lx))
            syntaxMenu.addAction(action)

        zoomInAction = QAction("Zoom &In", self)
        zoomInAction.setShortcut("Ctrl++")
        zoomInAction.triggered.connect(self.zoom_in)
        viewMenu.addAction(zoomInAction)

        zoomOutAction = QAction("Zoom &Out", self)
        zoomOutAction.setShortcut("Ctrl+-")
        zoomOutAction.triggered.connect(self.zoom_out)
        viewMenu.addAction(zoomOutAction)

        helpMenu = self.menuBar.addMenu("&Help")
        aboutAction = QAction("&About", self)
        aboutAction.triggered.connect(self.show_about_dialog)
        helpMenu.addAction(aboutAction)

        # Create the editor widget and add it to the layout
        self.editor_widget = QScintillaEditorWidget(self.defaultFolderPath)
        layout.addWidget(self.editor_widget)

        # Set default syntax highlighting
        self.changeLexer(CustomYAMLLexer)  # Default to YAML for example

        # Setup margin and color schemes
        self.setup_editor()

    def setup_editor(self):
        # Set up margin for line numbers
        self.editor_widget.editor.setMarginType(0, QsciScintilla.MarginType.NumberMargin)

        # Set margin width based on expected number of lines
        total_lines = 1000  # Adjust based on your requirements
        self.editor_widget.editor.setMarginWidth(0, f"{total_lines:5d}")

        # Set the color for the line numbers and margin background
        self.editor_widget.editor.setMarginsForegroundColor(QColor("#CCCCCC"))  # Light grey for line numbers
        self.editor_widget.editor.setMarginsBackgroundColor(QColor("#333333"))  # Dark grey for margin background

        # Optional: Hide other margins if not used
        self.editor_widget.editor.setMarginWidth(1, 0)  # Hide margin 1 if not used
        self.editor_widget.editor.setMarginWidth(2, 0)  # Hide margin 2 if not used

    def set_margin_colors(self):
        # Set margin colors (line numbers)
        editor = self.editor_widget.editor
        editor.setMarginsForegroundColor(QColor("#CCCCCC"))  # Light grey color for text
        editor.setMarginsBackgroundColor(QColor("#333333"))
    def new_file(self):
        # Logic to create a new file
        self.editor_widget.editor.clear()
        self.current_file_path = None

    def open_file(self):
        # Logic to open a file
        filePath, _ = QFileDialog.getOpenFileName(self, "Open File", self.defaultFolderPath, "All Files (*)")
        if filePath:
            with open(filePath, 'r') as file:
                content = file.read()
            self.editor_widget.editor.setText(content)
            self.current_file_path = filePath
            self.apply_syntax_highlighting(filePath)
            self.set_margin_colors()

    def save_file(self):
        # Logic to save the current file
        if self.current_file_path:
            self._save_to_file(self.current_file_path)
        else:
            self.save_file_as()

    def save_file_as(self):
        # Logic to save the file with a new name
        filePath, _ = QFileDialog.getSaveFileName(self, "Save File As", self.defaultFolderPath, "All Files (*)")
        if filePath:
            self._save_to_file(filePath)

    def _save_to_file(self, filePath):
        try:
            with open(filePath, 'w') as file:
                text = self.editor_widget.editor.text()
                file.write(text)
                self.editor_widget.editor.setModified(False)
                self.current_file_path = filePath
        except Exception as e:
            QMessageBox.critical(self, "Error Saving File", f"An error occurred while saving the file:\n{str(e)}")

    def search(self):
        # Implement search functionality
        find_text, ok = QInputDialog.getText(self, "Find", "Enter the text to find:")
        if ok and find_text:
            self.editor_widget.editor.findFirst(find_text, False, True, False, True)

    def replace(self):
        # Implement replace functionality
        find_text, ok = QInputDialog.getText(self, "Find", "Enter the text to find:")
        if ok and find_text:
            replace_text, ok = QInputDialog.getText(self, "Replace", "Enter the replacement text:")
            if ok:
                # Ensure we search from the beginning
                self.editor_widget.editor.SendScintilla(QsciScintilla.SCI_DOCUMENTSTART)
                # The first search to initiate
                found = self.editor_widget.editor.findFirst(find_text, False, True, False, True)
                while found:
                    # Replace the found text
                    self.editor_widget.editor.replace(replace_text)
                    # Continue searching from the last match
                    found = self.editor_widget.editor.findNext()

    def zoom_in(self):
        # Logic to zoom in
        self.editor_widget.editor.zoomIn()

    def zoom_out(self):
        # Logic to zoom out
        self.editor_widget.editor.zoomOut()

    def show_about_dialog(self):
        # Show about dialog
        QMessageBox.about(self, "About", "EasyEdit Editor\nVersion 1.0")

    def changeLexer(self, lexer_class):
        # Change the lexer for syntax highlighting
        lexer = lexer_class(self.editor_widget.editor)
        self.editor_widget.editor.setLexer(lexer)
        self.apply_color_scheme(lexer)

    def apply_syntax_highlighting(self, filePath):
        # Apply syntax highlighting based on file extension
        extension = os.path.splitext(filePath)[1].lower()
        lexer_class = LEXER_MAP_MENU.get(extension, CustomYAMLLexer)
        self.changeLexer(lexer_class)

    def apply_color_scheme(self, lexer):
        # Print available styles in the lexer for debugging
        print(f"Applying color scheme for lexer: {type(lexer).__name__}")

        for style_id in range(128):  # 128 is an upper limit for style IDs in most lexers
            description = lexer.description(style_id)
            if description:
                print(f"Style ID {style_id}: {description}")

        # Apply the color scheme based on available styles
        for style_name, color in GLOBAL_COLOR_SCHEME.items():
            style_id = getattr(lexer, style_name, -1)  # Get the style ID from the lexer by name
            if style_id != -1:
                lexer.setColor(QColor(color), style_id)
                print(f"Applied color {color} to style '{style_name}' with style ID {style_id}")
            else:
                print(f"Style '{style_name}' not found in lexer {type(lexer).__name__}.")

        # Set font globally for the lexer
        font = QFont("Consolas", 10)
        lexer.setFont(font)
