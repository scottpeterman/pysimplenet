import sys
import json
import traceback
from ruamel.yaml import YAML as yaml, YAML
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QPushButton, QFileDialog, QCheckBox,
                             QSpinBox, QDoubleSpinBox, QLabel, QComboBox, QApplication, QMessageBox)
from PyQt6.QtCore import Qt


class RunnerForm(QDialog):
    def __init__(self, parent=None, driver_data=None):
        super().__init__(parent)
        self.driver_data = driver_data  # Driver data passed by the parent
        self.setWindowTitle("Run Automation")
        self.setModal(True)
        self.setGeometry(100, 100, 600, 400)
        self.setup_ui()
        self.load_form_data()
        self.populate_driver_selector()  # Populate driver selector with available drivers

    def setup_ui(self):
        layout = QVBoxLayout()

        # Form for runner options
        form_layout = QFormLayout()

        # Inventory file selection
        self.inventory_input = QLineEdit()
        self.inventory_button = QPushButton("Browse")
        self.inventory_button.clicked.connect(self.browse_inventory_file)
        inventory_layout = QHBoxLayout()
        inventory_layout.addWidget(self.inventory_input)
        inventory_layout.addWidget(self.inventory_button)
        form_layout.addRow("Inventory File:", inventory_layout)

        # Device selection from inventory
        self.device_selector = QComboBox()
        form_layout.addRow("Select Device:", self.device_selector)

        # Driver selection dropdown
        self.driver_selector = QComboBox()
        form_layout.addRow("Select Driver:", self.driver_selector)

        # Additional options
        self.pretty_checkbox = QCheckBox()
        form_layout.addRow("Pretty Output:", self.pretty_checkbox)

        self.timeout_input = QSpinBox()
        self.timeout_input.setValue(10)
        form_layout.addRow("Timeout (s):", self.timeout_input)

        self.prompt_input = QLineEdit()
        form_layout.addRow("Prompt:", self.prompt_input)

        self.prompt_count_input = QSpinBox()
        self.prompt_count_input.setValue(1)
        form_layout.addRow("Prompt Count:", self.prompt_count_input)

        self.inter_command_time_input = QDoubleSpinBox()
        self.inter_command_time_input.setValue(1.0)
        form_layout.addRow("Inter-Command Time (s):", self.inter_command_time_input)

        layout.addLayout(form_layout)

        # Run and Cancel buttons
        button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Automation")
        self.run_button.clicked.connect(self.validate_and_send_data)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.center_form()

    def browse_inventory_file(self):
        """
        Opens a file dialog to select the inventory YAML file.
        """
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Inventory YAML File", "", "YAML Files (*.yml *.yaml)")
        if file_name:
            self.inventory_input.setText(file_name)
            self.load_inventory(file_name)

    def validate_and_send_data(self):
        # Validate inputs
        if not self.inventory_input.text():
            QMessageBox.critical(self, "Error", "Inventory file is required.")
            return
        if not self.device_selector.currentText():
            QMessageBox.critical(self, "Error", "Please select a device.")
            return
        if not self.driver_selector.currentText():
            QMessageBox.critical(self, "Error", "Please select a driver.")
            return

        # If validation passes, collect form data, save it, and accept the dialog
        self.form_data = self.get_form_data()
        self.save_form_data()  # Save the form data to the file
        self.accept()  # Close the form dialog

    def get_form_data(self):
        """
        Gather data from the form fields.
        """
        return {
            'inventory': self.inventory_input.text(),
            'device': self.device_selector.currentData(),
            'driver_name': self.driver_selector.currentText(),
            'pretty': self.pretty_checkbox.isChecked(),
            'timeout': self.timeout_input.value(),
            'prompt': self.prompt_input.text(),
            'prompt_count': self.prompt_count_input.value(),
            'inter_command_time': self.inter_command_time_input.value(),
        }

    def save_form_data(self):
        """
        Save the current form data to a file.
        """
        try:
            with open('runner_form.saved', 'w') as f:
                json.dump(self.form_data, f)
        except Exception as e:
            print(f"Error saving form data: {e}")
            traceback.print_exc()

    def load_inventory(self, file_path):
        try:
            with open(file_path, 'r') as file:
                yaml_loader = YAML(typ='safe')
                inventory_data = yaml_loader.load(file)

            devices = inventory_data.get('devices', [])
            self.device_selector.clear()  # Clear the previous items
            for device in devices:
                display_name = f"{device['hostname']} ({device['mgmt_ip']})"
                self.device_selector.addItem(display_name, device)  # Store the device object in the item data
        except Exception as e:
            print(f"Error loading inventory file: {e}")
            traceback.print_exc()
    def populate_driver_selector(self):
        """
        Populate the driver selector with available drivers from the passed driver data.
        """
        if self.driver_data:
            self.driver_selector.clear()
            for driver_name in self.driver_data.keys():
                self.driver_selector.addItem(driver_name)

    def load_form_data(self):
        try:
            with open('runner_form.saved', 'r') as f:
                data = json.load(f)
            self.inventory_input.setText(data.get('inventory', ''))

            # Set device selector's current text correctly
            saved_device = data.get('device', '')
            if isinstance(saved_device, dict):  # Ensure it's a dict before accessing its fields
                display_name = f"{saved_device.get('hostname', '')} ({saved_device.get('mgmt_ip', '')})"
            else:
                display_name = saved_device  # If not a dict, assume it's already the correct string
            self.device_selector.setCurrentText(display_name)

            self.driver_selector.setCurrentText(data.get('driver_name', 'cisco_ios'))
            self.pretty_checkbox.setChecked(data.get('pretty', False))
            self.timeout_input.setValue(data.get('timeout', 10))
            self.prompt_input.setText(data.get('prompt', ''))
            self.prompt_count_input.setValue(data.get('prompt_count', 1))
            self.inter_command_time_input.setValue(data.get('inter_command_time', 1.0))
            if self.inventory_input.text() != "":
                try:
                    self.load_inventory(self.inventory_input.text())
                except Exception as e:
                    print("unable to load last inventory file")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def center_form(self):
        """
        Center the form on the screen.
        """
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        form_size = self.geometry()
        x = (screen_geometry.width() - form_size.width()) // 2
        y = (screen_geometry.height() - form_size.height()) // 2
        self.move(x, y)