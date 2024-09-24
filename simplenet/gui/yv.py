import sys
import re
from ruamel.yaml import YAML as yaml
import argparse
import tempfile
import subprocess
from PyQt6.QtGui import (
    QAction, QTextCharFormat, QColor, QFont, QSyntaxHighlighter
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt

# Import the schema from action_schema.py
from action_schema import schema

def load_yaml(file_path):
    """
    Load a YAML file and return its data.
    """
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
        return data
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        return None

def get_action_line_number(yaml_lines, actions_line, action_index):
    """
    Helper function to find the line number of a specific action within the YAML.
    """
    try:
        count = -1
        for i in range(actions_line, len(yaml_lines)):
            line = yaml_lines[i].strip()
            if line.startswith("- action:"):
                count += 1
                if count == action_index:
                    return i
    except Exception as e:
        print(f"Error finding action line number: {e}")
    return actions_line

def validate_yaml(data, schema, file_path):
    """
    Validate the YAML data against the provided schema with precise action-level error placement.
    Returns a list of tuples containing line numbers and error messages.
    """
    errors = []

    try:
        with open(file_path, 'r') as file:
            yaml_content = file.read()

        yaml_lines = yaml_content.split('\n')

        if 'drivers' not in data:
            errors.append((0, "# Error: 'drivers' key missing in YAML data."))
            return errors

        for driver_name, driver_data in data.get('drivers', {}).items():
            try:
                driver_line = next(
                    i for i, line in enumerate(yaml_lines)
                    if line.strip().startswith(f"{driver_name}:")
                )
            except StopIteration:
                errors.append((0, f"# Error: Driver '{driver_name}' definition missing."))
                continue

            if 'actions' not in driver_data:
                errors.append((driver_line + 1, f"# Error: 'actions' key missing for driver '{driver_name}'."))
                continue

            try:
                actions_line = next(
                    i for i, line in enumerate(yaml_lines[driver_line:]) if line.strip() == "actions:"
                ) + driver_line
            except StopIteration:
                errors.append((driver_line + 1, f"# Error: 'actions' key is not properly defined for driver '{driver_name}'."))
                continue

            for idx, action in enumerate(driver_data['actions']):
                action_start = get_action_line_number(yaml_lines, actions_line, idx)
                if action_start == actions_line:
                    # If action_start wasn't found correctly, skip to avoid misplacement
                    print(f"Warning: Could not find the starting line for action index {idx} in driver '{driver_name}'.")
                    continue

                action_block = yaml_lines[action_start:]

                action_errors = []

                action_type = action.get('action')
                if action_type not in schema.get('actions', {}):
                    errors.append((action_start, f"# Error: Unknown action type '{action_type}' in driver '{driver_name}'."))
                    continue

                fields = schema['actions'].get(action_type, {}).get('fields', [])
                for field_info in fields:
                    field_name = field_info['name']
                    if field_info.get('required', False) and field_name not in action:
                        # Insert error after the '- action:' line
                        error_line = action_start + 1
                        errors.append((
                            error_line,
                            f"# Error: Missing required field '{field_name}' for action '{action_type}' in driver '{driver_name}'."
                        ))

    except Exception as e:
        print(f"Error validating YAML: {e}")

    return errors

def annotate_yaml(file_path, errors):
    """
    Produce an annotated version of the YAML file with comments precisely placed within action blocks.
    """
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()

        # Sort errors by line number in ascending order
        sorted_errors = sorted(errors, key=lambda x: x[0])

        # To avoid shifting issues when inserting lines, iterate from the end
        for line_no, error in reversed(sorted_errors):
            if line_no < len(lines):
                lines.insert(line_no, error + "\n")
            else:
                lines.append(error + "\n")

        return ''.join(lines)

    except Exception as e:
        print(f"Error reading YAML file for annotation: {e}")
        return ''

class YamlSyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighting_rules = []

        # Define text formats
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#0000FF"))  # Blue
        self.keyword_format.setFontWeight(QFont.Weight.Bold)

        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#008000"))  # Green

        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#808080"))  # Gray
        self.comment_format.setFontItalic(True)

        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#FF00FF"))  # Magenta

        self.bool_format = QTextCharFormat()
        self.bool_format.setForeground(QColor("#FF4500"))  # OrangeRed
        self.bool_format.setFontWeight(QFont.Weight.Bold)

        # Define regular expressions for different YAML elements
        # Keys (before the colon)
        key_pattern = re.compile(r'^\s*[^#\s][^:\n]+(?=\s*:)')
        self.highlighting_rules.append((key_pattern, self.keyword_format))

        # Strings (enclosed in quotes)
        string_pattern = re.compile(r'(["\'])(?:(?=(\\?))\2.)*?\1')
        self.highlighting_rules.append((string_pattern, self.string_format))

        # Comments
        comment_pattern = re.compile(r'#.*')
        self.highlighting_rules.append((comment_pattern, self.comment_format))

        # Numbers
        number_pattern = re.compile(r'\b\d+(\.\d+)?\b')
        self.highlighting_rules.append((number_pattern, self.number_format))

        # Booleans
        bool_pattern = re.compile(r'\b(true|false|True|False)\b')
        self.highlighting_rules.append((bool_pattern, self.bool_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

        self.setCurrentBlockState(0)

class YamlViewerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("YAML Validator and Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Create the menu bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        # Add Open action to the File menu
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.load_yaml_file)
        file_menu.addAction(open_action)

        main_layout = QVBoxLayout()

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        main_layout.addWidget(self.text_edit)

        # Apply the YAML syntax highlighter to the QTextEdit
        self.highlighter = YamlSyntaxHighlighter(self.text_edit.document())

        # Create a central widget for the main layout
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def load_yaml_file(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Open YAML File", "", "YAML Files (*.yml *.yaml)"
            )
        if file_path:
            data = load_yaml(file_path)
            if data:
                errors = validate_yaml(data, schema, file_path)
                if errors:
                    annotated_content = annotate_yaml(file_path, errors)
                    self.text_edit.setPlainText(annotated_content)
                else:
                    # If no errors, just display the original content
                    with open(file_path, 'r') as file:
                        self.text_edit.setPlainText(file.read())
                # Re-apply syntax highlighting by re-highlighting the document
                self.highlighter.rehighlight()

def main():
    parser = argparse.ArgumentParser(description="YAML Validator and Viewer")
    parser.add_argument('file', nargs='?', help='YAML file to load')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    viewer = YamlViewerApp()
    if args.file:
        viewer.load_yaml_file(args.file)
    viewer.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
