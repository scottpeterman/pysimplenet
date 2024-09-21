import sys
import re
from ruamel.yaml import YAML as yaml, YAML
from PyQt6.QtGui import (
    QAction, QTextCharFormat, QColor, QFont, QSyntaxHighlighter
)
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QWidget, QTextEdit, QFileDialog, QMenuBar,
    QPushButton, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

# Import the schema from action_schema.py
from simplenet.gui.action_schema import schema

yaml = YAML()


def load_yaml(file_path):
    """
    Load a YAML file and return its data.
    """
    try:
        with open(file_path, 'r') as file:
            data = yaml.load(file)
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
                    print(f"Warning: Could not find the starting line for action index {idx} in driver '{driver_name}'.")
                    continue

                action_type = action.get('action')
                if action_type not in schema.get('actions', {}):
                    errors.append((action_start, f"# Error: Unknown action type '{action_type}' in driver '{driver_name}'."))
                    continue

                fields = schema['actions'].get(action_type, {}).get('fields', [])
                for field_info in fields:
                    field_name = field_info['name']
                    if field_info.get('required', False) and field_name not in action:
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
        self.keyword_format.setForeground(QColor("#f5bc42"))  # Blue
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
        key_pattern = re.compile(r'^\s*[^#\s][^:\n]+(?=\s*:)')
        self.highlighting_rules.append((key_pattern, self.keyword_format))

        string_pattern = re.compile(r'(["\'])(?:(?=(\\?))\2.)*?\1')
        self.highlighting_rules.append((string_pattern, self.string_format))

        comment_pattern = re.compile(r'#.*')
        self.highlighting_rules.append((comment_pattern, self.comment_format))

        number_pattern = re.compile(r'\b\d+(\.\d+)?\b')
        self.highlighting_rules.append((number_pattern, self.number_format))

        bool_pattern = re.compile(r'\b(true|false|True|False)\b')
        self.highlighting_rules.append((bool_pattern, self.bool_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

        self.setCurrentBlockState(0)

class YamlValidationDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("YAML Validator and Editor")
        self.setGeometry(100, 100, 600, 400)

        # Layout for the main content
        main_layout = QVBoxLayout(self)

        # Create text editor for displaying and editing YAML content
        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(False)  # Make the QTextEdit editable
        main_layout.addWidget(self.text_edit)

        # Apply the YAML syntax highlighter
        self.highlighter = YamlSyntaxHighlighter(self.text_edit.document())

        # Button layout at the bottom of the dialog
        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)

        # Open button to load YAML file
        open_button = QPushButton("Open YAML File")
        open_button.clicked.connect(self.load_yaml_file)
        button_layout.addWidget(open_button)

        # Save button to save the edited YAML file
        save_button = QPushButton("Save YAML File")
        save_button.clicked.connect(self.save_yaml_file)
        button_layout.addWidget(save_button)

        # Close button to close the dialog
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)

    def load_yaml_file_from_path(self, file_path):
        """
        Loads and annotates a YAML file from a given path.
        """
        if file_path:
            self.current_file_path = file_path  # Store the current file path for saving
            data = load_yaml(file_path)
            if data:
                errors = validate_yaml(data, schema, file_path)
                annotated_content = annotate_yaml(file_path, errors)
                self.text_edit.setPlainText(annotated_content)
                # Re-apply syntax highlighting
                self.highlighter.rehighlight()

    def load_yaml_file(self):
        """
        Open file dialog to load a YAML file.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open YAML File", "", "YAML Files (*.yml *.yaml)"
        )
        self.load_yaml_file_from_path(file_path)

    def save_yaml_file(self):
        """
        Save the current YAML content back to the file.
        """
        try:
            if hasattr(self, 'current_file_path') and self.current_file_path:
                with open(self.current_file_path, 'w') as file:
                    file.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "File Saved", "YAML file saved successfully.")
            else:
                self.save_yaml_file_as()  # If no file path is available, use Save As
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Error saving file: {e}")

    def save_yaml_file_as(self):
        """
        Save the YAML content to a new file using a file dialog.
        """
        file_path, _ = QFileDialog.getSaveFileName(self, "Save YAML File As", "", "YAML Files (*.yml *.yaml)")
        if file_path:
            try:
                with open(file_path, 'w') as file:
                    file.write(self.text_edit.toPlainText())
                self.current_file_path = file_path
                QMessageBox.information(self, "File Saved", "YAML file saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Error saving file: {e}")

def main():
    app = QApplication(sys.argv)
    dialog = YamlValidationDialog()
    dialog.exec()

if __name__ == "__main__":
    main()
