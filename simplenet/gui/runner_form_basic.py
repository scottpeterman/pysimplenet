import sys
import json
import re
import traceback
from shlex import quote as shlex_quote

from PyQt6.QtGui import QTextCharFormat, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QFileDialog, QCheckBox,
    QSpinBox, QDoubleSpinBox, QLabel, QProgressBar, QApplication,
    QSplitter, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QProcess


class RunnerForm(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run Automation")
        self.setModal(True)
        self.setGeometry(100, 100, 800, 600)
        self.setup_ui()
        self.load_form_data()
        self.process = None

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Create a QSplitter to separate form and output
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Upper part - Scrollable form area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)

        # Form for runner options
        form = QFormLayout()

        self.inventory_input = QLineEdit()
        self.inventory_button = QPushButton("Browse")
        self.inventory_button.clicked.connect(lambda: self.browse_file(self.inventory_input))
        inventory_layout = QHBoxLayout()
        inventory_layout.addWidget(self.inventory_input)
        inventory_layout.addWidget(self.inventory_button)
        form.addRow("Inventory:", inventory_layout)

        self.query_input = QLineEdit()
        form.addRow("Query:", self.query_input)

        self.driver_input = QLineEdit()
        self.driver_button = QPushButton("Browse")
        self.driver_button.clicked.connect(lambda: self.browse_file(self.driver_input))
        driver_layout = QHBoxLayout()
        driver_layout.addWidget(self.driver_input)
        driver_layout.addWidget(self.driver_button)
        form.addRow("Driver:", driver_layout)

        self.vars_input = QLineEdit()
        self.vars_button = QPushButton("Browse")
        self.vars_button.clicked.connect(lambda: self.browse_file(self.vars_input))
        vars_layout = QHBoxLayout()
        vars_layout.addWidget(self.vars_input)
        vars_layout.addWidget(self.vars_button)
        form.addRow("Vars:", vars_layout)

        self.driver_name_input = QLineEdit()
        self.driver_name_input.setText("cisco_ios")
        form.addRow("Driver Name:", self.driver_name_input)

        self.pretty_checkbox = QCheckBox()
        form.addRow("Pretty Output:", self.pretty_checkbox)

        self.timeout_input = QSpinBox()
        self.timeout_input.setValue(10)
        form.addRow("Timeout (s):", self.timeout_input)

        self.prompt_input = QLineEdit()
        form.addRow("Prompt:", self.prompt_input)

        self.prompt_count_input = QSpinBox()
        self.prompt_count_input.setValue(1)
        form.addRow("Prompt Count:", self.prompt_count_input)

        self.disable_auto_add_policy_checkbox = QCheckBox()
        form.addRow("Disable Auto-Add Policy:", self.disable_auto_add_policy_checkbox)

        self.look_for_keys_checkbox = QCheckBox()
        form.addRow("Look for Keys:", self.look_for_keys_checkbox)

        self.timestamps_checkbox = QCheckBox()
        form.addRow("Timestamps:", self.timestamps_checkbox)

        self.inter_command_time_input = QDoubleSpinBox()
        self.inter_command_time_input.setValue(1.0)
        form.addRow("Inter-Command Time (s):", self.inter_command_time_input)

        self.no_threading_checkbox = QCheckBox()
        form.addRow("No Threading:", self.no_threading_checkbox)

        form_layout.addLayout(form)

        # Run and Cancel buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()  # Push buttons to the right
        self.run_button = QPushButton("Run Automation")
        self.run_button.clicked.connect(self.run_and_save)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_automation)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.cancel_button)
        form_layout.addLayout(button_layout)

        # Status indicator
        self.status_bar = QProgressBar()
        self.status_bar.setRange(0, 0)  # Indeterminate progress
        self.status_bar.hide()
        form_layout.addWidget(self.status_bar)

        scroll_area.setWidget(form_container)
        splitter.addWidget(scroll_area)

        # Lower part - Output window
        output_container = QWidget()
        output_layout = QVBoxLayout(output_container)
        output_label = QLabel("Output:")
        output_layout.addWidget(output_label)
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        output_layout.addWidget(self.output_text)
        splitter.addWidget(output_container)

        # Set initial sizes
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

    def browse_file(self, line_edit):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select File")
        if file_name:
            line_edit.setText(file_name)

    def run_and_save(self):
        self.run_automation()
        self.save_form_data()

    def save_form_data(self):
        data = {
            'inventory': self.inventory_input.text(),
            'query': self.query_input.text(),
            'driver': self.driver_input.text(),
            'vars': self.vars_input.text(),
            'driver_name': self.driver_name_input.text(),
            'pretty': self.pretty_checkbox.isChecked(),
            'timeout': self.timeout_input.value(),
            'prompt': self.prompt_input.text(),
            'prompt_count': self.prompt_count_input.value(),
            'disable_auto_add_policy': self.disable_auto_add_policy_checkbox.isChecked(),
            'look_for_keys': self.look_for_keys_checkbox.isChecked(),
            'timestamps': self.timestamps_checkbox.isChecked(),
            'inter_command_time': self.inter_command_time_input.value(),
            'no_threading': self.no_threading_checkbox.isChecked()
        }
        try:
            with open('runner_form.saved', 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.output_text.append(f"Error saving form data: {str(e)}")
            traceback.print_exc()

    def load_form_data(self):
        try:
            with open('runner_form.saved', 'r') as f:
                data = json.load(f)

            self.inventory_input.setText(data.get('inventory', ''))
            self.query_input.setText(data.get('query', ''))
            self.driver_input.setText(data.get('driver', ''))
            self.vars_input.setText(data.get('vars', ''))
            self.driver_name_input.setText(data.get('driver_name', 'cisco_ios'))
            self.pretty_checkbox.setChecked(data.get('pretty', False))
            self.timeout_input.setValue(data.get('timeout', 10))
            self.prompt_input.setText(data.get('prompt', ''))
            self.prompt_count_input.setValue(data.get('prompt_count', 1))
            self.disable_auto_add_policy_checkbox.setChecked(data.get('disable_auto_add_policy', False))
            self.look_for_keys_checkbox.setChecked(data.get('look_for_keys', False))
            self.timestamps_checkbox.setChecked(data.get('timestamps', False))
            self.inter_command_time_input.setValue(data.get('inter_command_time', 1.0))
            self.no_threading_checkbox.setChecked(data.get('no_threading', False))
        except FileNotFoundError:
            # If the file doesn't exist, just use default values
            pass
        except json.JSONDecodeError:
            # If the file is corrupted, use default values and create a new file
            self.save_form_data()

    def run_automation(self):
        command = self.build_command()

        # Also print to console for debugging
        print("Formatted command:")
        print(command)

        # Display the command in the output widget
        self.output_text.clear()
        self.output_text.append("Command to be executed:")
        self.output_text.append(" ".join(command))
        self.output_text.append("\n")
        print(f"post formatted: {self.output_text.toPlainText()}")

        if self.vars_input.text():
            command.extend(["--vars", self.vars_input.text()])
        if self.pretty_checkbox.isChecked():
            command.append("--pretty")
        if self.disable_auto_add_policy_checkbox.isChecked():
            command.append("--disable-auto-add-policy")
        if self.look_for_keys_checkbox.isChecked():
            command.append("--look-for-keys")
        if self.timestamps_checkbox.isChecked():
            command.append("--timestamps")
        if self.no_threading_checkbox.isChecked():
            command.append("--no-threading")

        # Create a QProcess object
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.started.connect(self.on_process_started)
        self.process.finished.connect(self.on_process_finished)

        # Show status indicator and enable cancel button
        self.status_bar.show()
        self.cancel_button.setEnabled(True)
        self.run_button.setEnabled(False)

        # Start the process
        self.process.start(command[0], command[1:])

    def cancel_automation(self):
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
            self.output_text.append("Process cancelled by user.")
            self.on_process_finished()

    def build_command(self):
        command = [
            sys.executable,
            "-u", "simplenet/cli/runner.py",
            "--inventory", f"{self.inventory_input.text()}",
            "--query", f"{self.query_input.text()}",
            "--driver", f"{self.driver_input.text()}",
            "--driver-name", self.driver_name_input.text(),
            "--timeout", str(self.timeout_input.value()),
            "--prompt", f"{self.prompt_input.text()}",
            "--prompt-count", str(self.prompt_count_input.value()),
            "--inter-command-time", str(self.inter_command_time_input.value())
        ]

        if self.vars_input.text():
            command.extend(["--vars", f'"{self.vars_input.text()}"'])
        if self.pretty_checkbox.isChecked():
            command.append("--pretty")
        if self.disable_auto_add_policy_checkbox.isChecked():
            command.append("--disable-auto-add-policy")
        if self.look_for_keys_checkbox.isChecked():
            command.append("--look-for-keys")
        if self.timestamps_checkbox.isChecked():
            command.append("--timestamps")
        if self.no_threading_checkbox.isChecked():
            command.append("--no-threading")

        return command

    def on_process_started(self):
        self.output_text.clear()  # Clear previous output
        self.output_text.append("Automation started...")

    def on_process_finished(self):
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_bar.hide()
        self.save_form_data()
        self.output_text.append("Automation finished.")

    def filter_escape_characters(self, text):
        # Define ANSI color codes mapping to PyQt colors
        ansi_to_qcolor = {
            '0': QColor("white"),  # Reset/normal
            '30': QColor("black"),
            '31': QColor("red"),
            '32': QColor("lightGreen"),
            '33': QColor("yellow"),
            '34': QColor("blue"),
            '35': QColor("magenta"),
            '36': QColor("cyan"),
            '37': QColor("white"),
            '90': QColor("darkGray"),
            '91': QColor("lightCoral"),
            '92': QColor("lightGreen"),
            '93': QColor("lightYellow"),
            '94': QColor("lightBlue"),
            '95': QColor("lightPink"),
            '96': QColor("lightCyan"),
            '97': QColor("white")
        }

        # Regular expression to match ANSI escape sequences
        ansi_escape = re.compile(r'\x1B\[([0-9;]*)m')

        # Split the text into segments: text and ANSI codes
        segments = []
        last_end = 0
        for match in ansi_escape.finditer(text):
            segments.append(('text', text[last_end:match.start()]))
            segments.append(('ansi', match.group(1)))
            last_end = match.end()
        segments.append(('text', text[last_end:]))

        return segments, ansi_to_qcolor

    def append_qtextedit_with_color(self, segments, ansi_to_qcolor):
        cursor = self.output_text.textCursor()
        color_format = QTextCharFormat()
        color_format.setForeground(QColor("white"))  # Default color

        for segment_type, content in segments:
            if segment_type == 'text':
                cursor.insertText(content, color_format)
            elif segment_type == 'ansi':
                codes = content.split(';')
                for code in codes:
                    if code in ansi_to_qcolor:
                        color_format.setForeground(ansi_to_qcolor[code])
                    elif code == '0':
                        color_format.setForeground(QColor("white"))  # Reset to default

        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()

    def handle_stdout(self):
        try:
            data = self.process.readAllStandardOutput()
            stdout = bytes(data).decode("utf8")
            segments, ansi_to_qcolor = self.filter_escape_characters(stdout)
            self.append_qtextedit_with_color(segments, ansi_to_qcolor)
        except Exception as e:
            self.output_text.append(f"Error handling stdout: {str(e)}")
            traceback.print_exc()

    def handle_stderr(self):
        try:
            data = self.process.readAllStandardError()
            stderr = bytes(data).decode("utf8")
            segments, ansi_to_qcolor = self.filter_escape_characters(stderr)
            self.append_qtextedit_with_color(segments, ansi_to_qcolor)
        except Exception as e:
            self.output_text.append(f"Error handling stderr: {str(e)}")
            traceback.print_exc()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    runner_form = RunnerForm()
    screen = app.primaryScreen()
    if screen is not None:
        # Get the screen size
        screen_size = screen.size()
        screen_width = screen_size.width()
        screen_height = screen_size.height()

        # Calculate 80% width and 70% height
        desired_width = int(screen_width * 0.8)
        desired_height = int(screen_height * 0.8)

        # Set the window size
        runner_form.resize(desired_width, desired_height)

        # Optional: Center the window on the screen
        # Calculate top-left coordinates for centering
        x = (screen_width - desired_width) // 2
        y = (screen_height - desired_height) // 2
        runner_form.move(x, y - 50)
    runner_form.show()
    sys.exit(app.exec())
