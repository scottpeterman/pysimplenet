import sys
import re
from ruamel.yaml import YAML
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
    yaml = YAML()
    try:
        with open(file_path, 'r') as file:
            data = yaml.load(file)
        return data
    except Exception as e:
        print(f"Error loading YAML file: {e}")
        return None


def validate_yaml(data, schema, file_path):
    """
    Validate the YAML data against the provided schema with precise action-level error placement.
    Returns a list of errors with data paths instead of line numbers.
    """
    errors = []

    try:
        if 'drivers' not in data:
            errors.append(("root", "# Error: 'drivers' key missing in YAML data."))
            return errors

        for driver_name, driver_data in data.get('drivers', {}).items():
            if 'actions' not in driver_data:
                errors.append(
                    (f"drivers.{driver_name}", f"# Error: 'actions' key missing for driver '{driver_name}'.")
                )
                continue

            for idx, action in enumerate(driver_data['actions']):
                action_path = f"drivers.{driver_name}.actions[{idx}]"
                action_type = action.get('action')
                if not action_type:
                    errors.append((action_path, "# Error: 'action' field is missing."))
                    continue

                if action_type not in schema.get('actions', {}):
                    errors.append(
                        (action_path, f"# Error: Unknown action type '{action_type}' in driver '{driver_name}'.")
                    )
                    continue

                fields = schema['actions'].get(action_type, {}).get('fields', [])
                for field_info in fields:
                    field_name = field_info['name']
                    if field_info.get('required', False) and field_name not in action:
                        errors.append((
                            f"{action_path}",
                            f"# Error: Missing required field '{field_name}' for action '{action_type}' in driver '{driver_name}'."
                        ))

    except Exception as e:
        print(f"Error validating YAML: {e}")

    return errors


def annotate_yaml(file_path, errors):
    """
    Annotate the YAML data with error comments based on data paths.
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        with open(file_path, 'r') as file:
            data = yaml.load(file)

        for path, error in errors:
            keys = re.split(r'\.(?![^\[]*\])', path)  # Split by dot but not within brackets
            current = data
            try:
                for key in keys:
                    if '[' in key and ']' in key:
                        main_key, index = re.match(r'(\w+)\[(\d+)\]', key).groups()
                        current = current[main_key][int(index)]
                    else:
                        current = current[key]
                # Insert the error as a comment above the current key
                if hasattr(current, 'yaml_set_comment_before_after_key'):
                    # This assumes current is a mapping; adjust as needed
                    parent = data
                    subkeys = path.split('.')
                    for subkey in subkeys[:-1]:
                        if '[' in subkey and ']' in subkey:
                            main_key, index = re.match(r'(\w+)\[(\d+)\]', subkey).groups()
                            parent = parent[main_key][int(index)]
                        else:
                            parent = parent[subkey]
                    last_key = subkeys[-1]
                    if '[' in last_key and ']' in last_key:
                        main_key, index = re.match(r'(\w+)\[(\d+)\]', last_key).groups()
                        # Can't set comment on list items directly
                        # Consider alternative approaches if needed
                    else:
                        parent.yaml_set_comment_before_after_key(last_key, before=error)
                else:
                    # Handle cases where the method is not available
                    pass
            except (KeyError, IndexError, TypeError, AttributeError) as e:
                print(f"Warning: Could not locate path '{path}' to insert error. Error: {e}")

        annotated_file_path = file_path.replace('.yaml', '_annotated.yaml')
        with open(annotated_file_path, 'w') as file:
            yaml.dump(data, file)

        return annotated_file_path

    except Exception as e:
        print(f"Error annotating YAML file: {e}")
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

    def load_yaml_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open YAML File", "", "YAML Files (*.yml *.yaml)"
        )
        if file_path:
            data = load_yaml(file_path)
            if data:
                errors = validate_yaml(data, schema, file_path)
                annotated_file_path = annotate_yaml(file_path, errors)
                if annotated_file_path:
                    try:
                        with open(annotated_file_path, 'r') as file:
                            annotated_content = file.read()
                        self.text_edit.setPlainText(annotated_content)
                        # Re-apply syntax highlighting by re-highlighting the document
                        self.highlighter.rehighlight()
                    except Exception as e:
                        print(f"Error reading annotated YAML file: {e}")
                else:
                    # If annotation failed, display original content
                    try:
                        with open(file_path, 'r') as file:
                            original_content = file.read()
                        self.text_edit.setPlainText(original_content)
                        self.highlighter.rehighlight()
                    except Exception as e:
                        print(f"Error reading YAML file: {e}")


def main():
    app = QApplication(sys.argv)
    viewer = YamlViewerApp()
    viewer.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
