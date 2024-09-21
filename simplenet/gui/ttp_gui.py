import sys
import traceback
import json
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextEdit,
    QMenu, QInputDialog, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor, QAction

# Ensure that ttp is installed: pip install ttp
from ttp import ttp

class HighlightedTextEdit(QTextEdit):
    selection_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.highlighted_ranges = []
        self.extra_selections = []

    def show_context_menu(self, pos):
        try:
            cursor = self.cursorForPosition(pos)
            if self.textCursor().hasSelection():
                menu = QMenu(self)
                assign_action = QAction("Assign Variable", self)
                assign_action.triggered.connect(self.assign_variable)
                menu.addAction(assign_action)
                menu.exec(self.mapToGlobal(pos))
            else:
                menu = self.createStandardContextMenu()
                menu.exec(self.mapToGlobal(pos))
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in show_context_menu:\n{tb}")

    def assign_variable(self):
        try:
            cursor = self.textCursor()
            selected_text = cursor.selectedText()
            if not selected_text:
                QMessageBox.warning(self, "No Selection", "Please select some text to assign a variable.")
                return

            # Ask for variable name
            var_name, ok = QInputDialog.getText(self, "Variable Name", "Enter variable name:")
            if not ok or not var_name.strip():
                return

            # Ask for match variable type
            match_types = [
                "None", "WORD", "PHRASE", "ORPHRASE", "_line_", "ROW",
                "DIGIT", "IP", "PREFIX", "IPV6", "PREFIXV6", "MAC", "re"
            ]
            match_type, ok = QInputDialog.getItem(
                self, "Select Match Type", "Choose a TTP match variable type:", match_types, 0, False
            )
            if not ok:
                return

            # Handle 're' match type
            if match_type.lower() == 're':
                regex, ok = QInputDialog.getText(self, "Enter Regular Expression", "Enter regex for the variable:")
                if not ok or not regex.strip():
                    return
                match_type = f're("{regex.strip()}")'
            else:
                match_type = match_type.upper() if match_type != "None" else None

            # Store the variable assignment
            start = min(cursor.position(), cursor.anchor())
            end = max(cursor.position(), cursor.anchor())
            self.highlighted_ranges.append({
                'start': start,
                'end': end,
                'var_name': var_name.strip(),
                'match_type': match_type
            })

            # Update highlights
            self.update_highlights()
            self.selection_changed.emit()
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in assign_variable:\n{tb}")

    def update_highlights(self):
        try:
            self.extra_selections = []
            for rng in self.highlighted_ranges:
                selection = QTextEdit.ExtraSelection()
                # Create a new QTextCursor from the document
                cursor = QTextCursor(self.document())
                cursor.setPosition(rng['start'])
                cursor.setPosition(rng['end'], QTextCursor.MoveMode.KeepAnchor)
                selection.cursor = cursor
                selection.format.setBackground(QColor("#C1E1C1"))  # Light green background
                self.extra_selections.append(selection)
            self.setExtraSelections(self.extra_selections)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in update_highlights:\n{tb}")

    def clear_highlights(self):
        try:
            self.highlighted_ranges = []
            self.extra_selections = []
            self.setExtraSelections(self.extra_selections)
            self.selection_changed.emit()
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in clear_highlights:\n{tb}")

    def mouseDoubleClickEvent(self, event):
        try:
            # Clear selection on double-click outside selection
            super().mouseDoubleClickEvent(event)
            self.selection_changed.emit()
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in mouseDoubleClickEvent:\n{tb}")

class TTPTemplateBuilder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TTP Template Builder")
        self.resize(1200, 600)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Pane - Sample Text Input
        self.left_pane = QWidget()
        left_layout = QVBoxLayout()
        self.sample_text_edit = HighlightedTextEdit()
        self.sample_text_edit.textChanged.connect(self.on_text_changed)
        self.sample_text_edit.selection_changed.connect(self.update_template)
        left_layout.addWidget(QLabel("Sample Text:"))
        left_layout.addWidget(self.sample_text_edit)
        self.left_pane.setLayout(left_layout)

        # Middle Pane - Generated Template
        self.middle_pane = QWidget()
        middle_layout = QVBoxLayout()
        self.template_text_edit = QTextEdit()
        self.template_text_edit.setReadOnly(True)
        middle_layout.addWidget(QLabel("Generated Template:"))
        middle_layout.addWidget(self.template_text_edit)
        self.middle_pane.setLayout(middle_layout)

        # Right Pane - Parsed Results
        self.right_pane = QWidget()
        right_layout = QVBoxLayout()
        self.result_text_edit = QTextEdit()
        self.result_text_edit.setReadOnly(True)
        right_layout.addWidget(QLabel("Parsed Results:"))
        right_layout.addWidget(self.result_text_edit)
        self.right_pane.setLayout(right_layout)

        splitter.addWidget(self.left_pane)
        splitter.addWidget(self.middle_pane)
        splitter.addWidget(self.right_pane)
        splitter.setSizes([400, 400, 400])

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def on_text_changed(self):
        # Clear highlights and variables when text changes
        try:
            self.sample_text_edit.clear_highlights()
            self.template_text_edit.clear()
            self.result_text_edit.clear()
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in on_text_changed:\n{tb}")

    def update_template(self):
        try:
            template_text = self.generate_template()
            self.template_text_edit.setPlainText(template_text)
            self.parse_text()
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in update_template:\n{tb}")

    def parse_text(self):
        try:
            # Only parse if there are assigned variables
            if not self.sample_text_edit.highlighted_ranges:
                self.result_text_edit.clear()
                return

            template_text = self.template_text_edit.toPlainText()
            sample_text = self.sample_text_edit.toPlainText()

            if not template_text.strip() or not sample_text.strip():
                self.result_text_edit.clear()
                return

            # Print the template for debugging
            print("Generated Template:")
            print(template_text)

            try:
                parser = ttp(data=sample_text, template=template_text)
                parser.parse()
                results = parser.result()
                results_json = json.dumps(results, indent=4)
                self.result_text_edit.setPlainText(results_json)
            except Exception as e:
                # Capture detailed traceback
                tb = traceback.format_exc()
                error_message = f"Error parsing template:\n{str(e)}\n\nTraceback:\n{tb}"
                self.result_text_edit.setPlainText(error_message)
                print(error_message)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in parse_text:\n{tb}")

    def generate_template(self):
        try:
            sample_text = self.sample_text_edit.toPlainText()
            lines = sample_text.splitlines(keepends=True)

            # Build a list of lines with their start and end positions
            line_positions = []
            current_pos = 0
            for line in lines:
                line_length = len(line)
                line_start = current_pos
                line_end = current_pos + line_length
                line_positions.append({'index': len(line_positions), 'start': line_start, 'end': line_end, 'text': line})
                current_pos += line_length

            # Build a mapping from line index to variables in that line
            line_variables = {}  # key: line index, value: list of variable assignments
            for rng in self.sample_text_edit.highlighted_ranges:
                # Find which line this variable is in
                for line_info in line_positions:
                    line_start = line_info['start']
                    line_end = line_info['end']
                    if rng['start'] >= line_start and rng['end'] <= line_end:
                        idx = line_info['index']
                        if idx not in line_variables:
                            line_variables[idx] = []
                        line_variables[idx].append(rng)
                        break  # Stop after finding the line
                    # Else, continue to next line

            # Build the template lines
            template_lines = []
            for line_info in line_positions:
                idx = line_info['index']
                line_text = line_info['text']
                if idx in line_variables:
                    vars_in_line = line_variables[idx]
                    # Sort variables by start position in line
                    vars_in_line.sort(key=lambda x: x['start'])
                    # Build the line with variables replaced
                    line_start = line_info['start']
                    new_line = ''
                    last_pos = line_start
                    for var in vars_in_line:
                        var_start = var['start']
                        var_end = var['end']
                        # Calculate positions relative to line start
                        rel_start = var_start - line_start
                        rel_end = var_end - line_start

                        # Append text before variable
                        new_line += line_text[last_pos - line_start:rel_start]

                        # Build variable placeholder with match type
                        if var['match_type']:
                            var_string = f"{{{{ {var['var_name']} | {var['match_type']} }}}}"
                        else:
                            var_string = f"{{{{ {var['var_name']} }}}}"

                        new_line += var_string
                        last_pos = var_end

                    # Append any remaining text after last variable
                    new_line += line_text[last_pos - line_start:]
                    template_lines.append(new_line)
                else:
                    # Skip lines without variables
                    pass

            template_text = ''.join(template_lines)
            return template_text
        except Exception as e:
            tb = traceback.format_exc()
            print(f"Exception in generate_template:\n{tb}")
            return ""

def main():
    app = QApplication(sys.argv)
    window = TTPTemplateBuilder()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
