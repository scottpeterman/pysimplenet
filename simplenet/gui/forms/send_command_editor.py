from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QComboBox, QTextEdit,
    QCheckBox, QScrollArea, QFormLayout, QGroupBox, QPushButton,
    QHBoxLayout, QFileDialog
)
from PyQt6.QtCore import pyqtSignal

class SendCommandEditor(QWidget):
    action_updated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.init_ui()
        self.initial_action_data = {}

    def init_ui(self):
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        self.form_widget = QWidget()
        self.form_layout = QFormLayout(self.form_widget)
        scroll_area.setWidget(self.form_widget)
        self.layout.addWidget(scroll_area)

        # Create form fields
        self.display_name_input = QLineEdit(self)
        self.command_input = QLineEdit(self)
        self.expect_input = QLineEdit(self)
        self.output_path_input = QLineEdit(self)
        self.output_mode_input = QComboBox(self)
        self.output_mode_input.addItems(["append", "overwrite"])
        self.output_format_input = QComboBox(self)
        self.output_format_input.addItems(["text", "both"])
        self.ttp_path_input = QLineEdit(self)
        self.browse_ttp_path_button = QPushButton("Browse")
        self.browse_ttp_path_button.clicked.connect(self.browse_ttp_path)

        # Store Query fields (nested)
        self.store_query_group = QGroupBox("Store Query")
        self.store_query_layout = QFormLayout()
        self.store_query_group.setLayout(self.store_query_layout)
        self.query_input = QLineEdit(self)
        self.variable_name_input = QLineEdit(self)

        # Add fields to form layout
        self.form_layout.addRow("Display Name:", self.display_name_input)
        self.form_layout.addRow("Command:", self.command_input)
        self.form_layout.addRow("Expected Output:", self.expect_input)
        self.form_layout.addRow("Output Path:", self.output_path_input)
        self.form_layout.addRow("Output Mode:", self.output_mode_input)
        self.form_layout.addRow("Output Format:", self.output_format_input)

        # Add TTP Template Path with browse button
        ttp_path_layout = QHBoxLayout()
        ttp_path_layout.addWidget(self.ttp_path_input)
        ttp_path_layout.addWidget(self.browse_ttp_path_button)
        ttp_path_container = QWidget()
        ttp_path_container.setLayout(ttp_path_layout)
        self.form_layout.addRow("TTP Template Path:", ttp_path_container)

        # Add Store Query fields (nested)
        self.store_query_layout.addRow("Query:", self.query_input)
        self.store_query_layout.addRow("Variable Name:", self.variable_name_input)
        self.form_layout.addRow(self.store_query_group)
    def load_action_data(self, action_data):
        self.initial_action_data = action_data.copy()
        self.display_name_input.setText(action_data.get('display_name', ''))
        self.command_input.setText(action_data.get('command', ''))
        self.expect_input.setText(action_data.get('expect', ''))
        self.output_path_input.setText(action_data.get('output_path', ''))
        self.output_mode_input.setCurrentText(action_data.get('output_mode', 'append'))
        self.output_format_input.setCurrentText(action_data.get('output_format', 'text'))
        self.ttp_path_input.setText(action_data.get('ttp_path', ''))

        store_query = action_data.get('store_query', {})
        self.query_input.setText(store_query.get('query', ''))
        self.variable_name_input.setText(store_query.get('variable_name', ''))

    def get_action_data(self):
        return {
            'action': 'send_command',
            'display_name': self.display_name_input.text(),
            'command': self.command_input.text(),
            'expect': self.expect_input.text(),
            'output_path': self.output_path_input.text(),
            'output_mode': self.output_mode_input.currentText(),
            'output_format': self.output_format_input.currentText(),
            'ttp_path': self.ttp_path_input.text(),
            'store_query': {
                'query': self.query_input.text(),
                'variable_name': self.variable_name_input.text()
            }
        }

    def browse_ttp_path(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select TTP Template Path", "", "All Files (*)")
        if file_path:
            self.ttp_path_input.setText(file_path)