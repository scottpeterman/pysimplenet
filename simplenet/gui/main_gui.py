import os
import sys

import markdown
from ruamel.yaml import YAML
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QSplitter, QFileDialog,
    QMenuBar, QMenu, QLineEdit, QComboBox, QDialog, QTextEdit,
    QTabWidget, QToolBar, QCheckBox, QMessageBox, QInputDialog, QScrollArea, QTextBrowser
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from simplenet.gui.action_schema import schema
from simplenet.gui.forms.crud import CRUDWidget
from simplenet.gui.forms.sqltool import SQLQueryWidget
from simplenet.gui.help.drivers import show_drivers_help
from simplenet.gui.pyeasyedit.EasyEditorWithMenu import EditorWithMenu
from simplenet.gui.uglyplugin_parsers.uglyparsers2 import UglyParsingWidget
from simplenet.gui.action_gui import ActionEditor
from simplenet.gui.runner_form_basic import RunnerForm
from simplenet.gui.vsndebug import VisualDebugger
from simplenet.gui.yaml_viewer import YamlValidationDialog
from ruamel.yaml import YAML as yaml

from simplenet.gui.pyeasyedit.__main__ import QScintillaEditorWidget

from PyQt6.QtWidgets import QTabBar, QMessageBox

class CustomTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)

    def tabInserted(self, index):
        """
        Override the tabInserted method to hide the close button for the "Form View" tab.
        """
        super().tabInserted(index)
        if self.tabText(index) == "Form View":
            self.setTabButton(index, QTabBar.ButtonPosition.RightSide, None)

class DriverEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.schema = schema  # Load schema directly from the Python file
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Driver YAML Editor")
        self.setGeometry(100, 100, 1000, 600)

        self.current_file_path = None

        self.create_menu()
        self.create_toolbar()

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)  # Enable close buttons on tabs

        # Replace the default tab bar with CustomTabBar
        custom_tab_bar = CustomTabBar(self.tab_widget)
        self.tab_widget.setTabBar(custom_tab_bar)

        # Connect the tabCloseRequested signal to handle tab closures
        self.tab_widget.tabCloseRequested.connect(self.close_tab)

        main_layout.addWidget(self.tab_widget)

        # Create the form view tab with a splitter for layout
        self.form_tab = QWidget()
        form_layout = QVBoxLayout(self.form_tab)

        # Add the global driver settings fields
        self.driver_name_input = QLineEdit()
        self.error_string_input = QLineEdit()
        self.output_path_input = QLineEdit()
        self.output_mode_input = QComboBox()
        self.output_mode_input.addItems(["append", "overwrite"])
        self.prompt_count_input = QLineEdit()

        global_layout = QHBoxLayout()
        global_layout.addWidget(QLabel("Driver Name:"))
        global_layout.addWidget(self.driver_name_input)
        global_layout.addWidget(QLabel("Error String:"))
        global_layout.addWidget(self.error_string_input)
        global_layout.addWidget(QLabel("Output Path:"))
        global_layout.addWidget(self.output_path_input)
        global_layout.addWidget(QLabel("Output Mode:"))
        global_layout.addWidget(self.output_mode_input)
        global_layout.addWidget(QLabel("Prompt Count:"))
        global_layout.addWidget(self.prompt_count_input)

        form_layout.addLayout(global_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Add QListWidget for action navigation
        self.action_list = QListWidget()
        self.action_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.action_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        splitter.addWidget(self.action_list)

        # Connect selection change in the list to update the form
        self.action_list.currentItemChanged.connect(self.on_action_selected)

        # Left side buttons for Add and Delete actions
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add Action")
        delete_button = QPushButton("Delete Action")
        button_layout.addWidget(add_button)
        button_layout.addWidget(delete_button)
        form_layout.addLayout(button_layout)

        add_button.clicked.connect(self.add_action)
        delete_button.clicked.connect(self.remove_action)

        # Right side of the splitter: Form fields using ActionEditor
        form_container = QWidget()
        form_layout_right = QVBoxLayout(form_container)

        # Add ActionEditor for editing selected action
        self.action_editor = ActionEditor(self.schema, self)
        form_layout_right.addWidget(self.action_editor)

        # Buttons to save or cancel changes
        action_button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        action_button_layout.addWidget(save_button)
        action_button_layout.addWidget(cancel_button)
        form_layout_right.addLayout(action_button_layout)

        save_button.clicked.connect(self.save_action_changes)
        cancel_button.clicked.connect(self.cancel_action_changes)

        # Connect ActionEditor signal to update the list item
        self.action_editor.action_updated.connect(self.update_action_item)

        splitter.addWidget(form_container)
        splitter.setSizes([200, 800])  # Adjust initial sizes

        form_layout.addWidget(splitter)

        self.tab_widget.addTab(self.form_tab, "Form View")
        self.tab_widget.setTabsClosable(True)

        # Create the "Parsing Tools" tab
        self.parsers_tab = UglyParsingWidget(self)
        self.tab_widget.addTab(self.parsers_tab, "Parsing Tools")

        # Initialize the status label at the bottom
        self.file_path_label = QLabel("")
        self.file_path_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.file_path_label.setStyleSheet("border-top: 1px solid #ccc; padding: 5px;")
        main_layout.addWidget(self.file_path_label)

    def close_tab(self, index):
        """
        Handles the closing of tabs. Prevents closing the "Form View" tab.
        """
        tab_text = self.tab_widget.tabText(index)
        if tab_text != "Form View":
            self.tab_widget.removeTab(index)
        else:
            QMessageBox.information(self, "Info", "The 'Form View' tab cannot be closed.")

    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        new_action = QAction("New", self)
        new_action.triggered.connect(self.new_file)
        file_menu.addAction(new_action)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("Save As", self)
        save_as_action.triggered.connect(lambda: self.save_file(save_as=True))
        file_menu.addAction(save_as_action)

        view_menu = menubar.addMenu("View")
        view_yaml_action = QAction("View YAML", self)
        view_yaml_action.triggered.connect(self.view_yaml)
        view_menu.addAction(view_yaml_action)

        run_menu = menubar.addMenu("Run")
        run_action = QAction("Run Automation", self)
        run_action.triggered.connect(self.open_runner_form)
        run_menu.addAction(run_action)

        # Help menu
        help_menu = menubar.addMenu("Help")

        # Drivers help action
        drivers_action = QAction("Drivers", self)
        drivers_action.triggered.connect(self._show_help_drivers)
        help_menu.addAction(drivers_action)

        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        # Create the dialog
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About EasyEdit")
        about_dialog.setMinimumSize(400, 300)

        layout = QVBoxLayout(about_dialog)

        # Create a QTextBrowser to render markdown content
        text_browser = QTextBrowser(about_dialog)

        # Render a sample markdown string (this could be loaded from a file as well)
        about_markdown = """
        # SimpleNet: Vendor-Agnostic Network Automation

SimpleNet is a versatile, vendor-agnostic SSH automation solution designed for network engineers. It bridges the gap between complex automation frameworks and usability by providing a powerful CLI utility with YAML-based configurations for network device automation.

## Features

- **Vendor Agnostic**: Supports various network devices across multiple manufacturers.
- **Comprehensive CLI**: Easy-to-use command-line interface with YAML-based configurations.
- **Flexible Configuration**: Use YAML files for inventories, drivers, variables, and actions.
- **Conditional Execution**: Dynamically execute commands based on output conditions.
- **Concurrency and Efficiency**: Run tasks on multiple devices concurrently with robust error handling.
- **Auditing and Compliance**: Built-in auditing capabilities to check compliance and run validations.
- **Structured Data Parsing**: Template-based parsing using TTP for structured data extraction.
- **Visual Debugger (`vsndebug`)**: Interactive, GUI-based debugger for visualizing automation steps and data.
- **Data Management**: Store, manipulate, and reuse parsed data across actions.
- **Cross-Platform**: Supports multi-platform automation with customizable drivers.
"""

        # Convert markdown to HTML and set it to QTextBrowser
        about_html = markdown.markdown(about_markdown)
        text_browser.setHtml(about_html)

        layout.addWidget(text_browser)
        about_dialog.setLayout(layout)

        # Show the dialog
        about_dialog.exec()

    def _show_help_drivers(self):
        show_drivers_help(self)

    def create_toolbar(self):
        toolbar = QToolBar("Tools")
        self.addToolBar(toolbar)

        parsers_action = QAction("Parsers", self)
        parsers_action.triggered.connect(self.parsers)
        toolbar.addAction(parsers_action)

        # Debugger Action
        debugger_action = QAction("Debugger", self)
        debugger_action.triggered.connect(self.open_debugger)  # Connect to the method to open the debugger
        toolbar.addAction(debugger_action)

        editor_action = QAction("Editor", self)
        editor_action.triggered.connect(self.open_editor)  # Connect to the method to open the editor
        toolbar.addAction(editor_action)

        inventory_action = QAction("Inventory", self)
        inventory_action.triggered.connect(self.open_inventory)  # Connect to the method to open the editor
        toolbar.addAction(inventory_action)

        sql_action = QAction("SQL", self)
        sql_action.triggered.connect(self.open_sql)  # Connect to the method to open the editor
        toolbar.addAction(sql_action)

    def parsers(self):
        self.parsers_tab = UglyParsingWidget(self)
        self.tab_widget.addTab(self.parsers_tab, "Parsing Tools")
        self.tab_widget.setCurrentWidget(self.parsers_tab)

    def open_debugger(self):
        """
        Opens the Visual Debugger in a separate child window.
        """
        try:
            # Instantiate the VisualDebugger window
            self.debugger_window = VisualDebugger()  # Make sure to use the correct class name
            self.debugger_window.setWindowModality(
                Qt.WindowModality.NonModal)  # Ensure it's non-modal to keep main window active
            self.debugger_window.show()
        except Exception as e:
            print("Error opening debugger:")
            print(e)

    def open_inventory(self):
        """
        Opens the Inventory editor as a new tab in the main application.
        """
        try:
            # Check if the inventory tab already exists
            existing_tab_index = -1
            if existing_tab_index == -1:  # If the tab does not exist, create it
                # Instantiate the Editor widget
                self.inventory_window = CRUDWidget()  # Use the correct class name

                # Add the editor as a new tab in the main application's tab widget
                self.tab_widget.addTab(self.inventory_window, "Inventory")

                # Switch to the newly added tab
                self.tab_widget.setCurrentWidget(self.inventory_window)
            else:
                # Switch to the existing tab if it's already open
                self.tab_widget.setCurrentIndex(existing_tab_index)

        except Exception as e:
            print("Error opening EasyEdit editor:")
            print(e)

    def open_sql(self):
        """
        Opens the Inventory editor as a new tab in the main application.
        """
        try:
            # Check if the sql tab already exists
            existing_tab_index = -1
            if existing_tab_index == -1:  # If the tab does not exist, create it
                # Instantiate the SQL widget
                self.sql_window = SQLQueryWidget()  # Use the correct class name

                # Add the editor as a new tab in the main application's tab widget
                self.tab_widget.addTab(self.sql_window, "SQL")

                # Switch to the newly added tab
                self.tab_widget.setCurrentWidget(self.sql_window)
            else:
                # Switch to the existing tab if it's already open
                self.tab_widget.setCurrentIndex(existing_tab_index)

        except Exception as e:
            print("Error opening EasyEdit editor:")
            print(e)

    def open_editor(self):
        """
        Opens the EasyEdit editor as a new tab in the main application.
        """
        try:
            # Check if the editor tab already exists
            # existing_tab_index = self.tab_widget.indexOf(self.editor_window) if hasattr(self, 'editor_window') else -1
            existing_tab_index = -1
            if existing_tab_index == -1:  # If the tab does not exist, create it
                # Instantiate the Editor widget
                self.editor_window = EditorWithMenu("./project")  # Use the correct class name

                # Add the editor as a new tab in the main application's tab widget
                self.tab_widget.addTab(self.editor_window, "EasyEdit")

                # Switch to the newly added tab
                self.tab_widget.setCurrentWidget(self.editor_window)
            else:
                # Switch to the existing tab if it's already open
                self.tab_widget.setCurrentIndex(existing_tab_index)

        except Exception as e:
            print("Error opening EasyEdit editor:")
            print(e)

    def new_file(self):
        """
        Creates a new YAML file with a minimal driver setup.
        """
        folder_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder_path:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save YAML File", folder_path, "YAML Files (*.yml *.yaml)")
            if file_name:
                # Create a minimal driver structure
                minimal_driver = {
                    'drivers': {
                        'Default Driver': {
                            'error_string': '',
                            'output_path': '',
                            'output_mode': 'append',
                            'prompt_count': 1,
                            'actions': [
                                {
                                    'action': 'send_command',
                                    'display_name': 'Set Terminal Length',
                                    'command': 'term len 0',
                                    'expect': '#'
                                }
                            ]
                        }
                    }
                }
                try:
                    with open(file_name, 'w') as file:
                        yaml.dump(minimal_driver, file, default_flow_style=False)
                    self.current_file_path = file_name
                    self.populate_tabs(minimal_driver)
                    # self.update_yaml_preview()
                    self.file_path_label.setText(f"Created New File: {file_name}")  # Update the label
                    print(f"New file created: {file_name}")
                except Exception as e:
                    print(f"Error creating new file: {e}")
                    self.file_path_label.setText(f"Error creating file: {e}")  # Update the label on error

    def save_action_changes(self):
        """
        Saves the changes made to the current action in the ActionEditor.
        """
        current_item = self.action_list.currentItem()
        if current_item:
            action_data = self.action_editor.get_action_data()
            current_item.setData(Qt.ItemDataRole.UserRole, action_data)
            current_item.setText(action_data.get('display_name', action_data.get('action', '')))
            self.update_yaml_preview()
            print("Action changes saved.")

    def cancel_action_changes(self):
        """
        Cancels the changes made to the current action and reloads the original data.
        """
        current_item = self.action_list.currentItem()
        if current_item:
            action_data = current_item.data(Qt.ItemDataRole.UserRole)
            self.action_editor.update_form(action_data)
            print("Action changes canceled.")

    def on_action_selected(self, current, previous):
        """
        Updates the ActionEditor with the currently selected action.
        """
        if current:
            action_data = current.data(Qt.ItemDataRole.UserRole)
            self.action_editor.update_form(action_data)

    def update_action_item(self, action_data):
        """
        Updates the currently selected list item in the action list with new data.
        """
        current_item = self.action_list.currentItem()
        if current_item:
            current_item.setData(Qt.ItemDataRole.UserRole, action_data)
            current_item.setText(action_data.get('display_name', action_data.get('action', '')))
        self.update_yaml_preview()

    def add_action(self):
        """
        Adds a new action to the action list.
        """
        action_types = list(self.schema['actions'].keys())
        action_type, ok = QInputDialog.getItem(self, "Select Action Type", "Action Type:", action_types, 0, False)
        if ok and action_type:
            new_action = {'action': action_type, 'display_name': f"New {action_type.replace('_', ' ').title()} Action"}
            item = QListWidgetItem(new_action['display_name'])
            item.setData(Qt.ItemDataRole.UserRole, new_action)
            self.action_list.addItem(item)
            self.action_list.setCurrentItem(item)
        self.update_yaml_preview()

    def remove_action(self):
        """
        Removes the currently selected action from the action list.
        """
        current_item = self.action_list.currentItem()
        if current_item:
            self.action_list.takeItem(self.action_list.row(current_item))
        self.update_yaml_preview()

    def open_file(self):
        """
        Opens and loads a YAML file.
        """
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open YAML File", "", "YAML Files (*.yml *.yaml)")
            if file_path:
                yaml_loader = YAML()
                yaml_loader.preserve_quotes = True  # Preserve quotes
                with open(file_path, 'r') as file:
                    yaml_data = yaml_loader.load(file)
                self.current_file_path = file_path

                if self.validate_yaml(yaml_data):
                    self.populate_tabs(yaml_data)
                    self.update_yaml_preview()
                    self.file_path_label.setText(f"Loaded File: {file_path}")  # Update the label
                else:
                    self.display_invalid_yaml_message()
                    self.file_path_label.setText("")  # Clear the label if invalid

        except Exception as e:
            print(f"Error in open_file: {e}")
            self.file_path_label.setText(f"Error loading file: {e}")  # Update the label on error

    def populate_tabs(self, yaml_data):
        """
        Populates the action list and form view with the loaded YAML data.
        """
        self.action_list.clear()  # Clear existing actions

        # Populate global settings
        driver_name = list(yaml_data['drivers'].keys())[0]
        driver_data = yaml_data['drivers'][driver_name]
        self.driver_name_input.setText(driver_name)
        self.error_string_input.setText(driver_data.get('error_string', ''))
        self.output_path_input.setText(driver_data.get('output_path', ''))
        self.output_mode_input.setCurrentText(driver_data.get('output_mode', 'append'))
        self.prompt_count_input.setText(str(driver_data.get('prompt_count', '')))

        # Populate actions
        if 'actions' in driver_data:
            for action in driver_data['actions']:
                item = QListWidgetItem(action.get('display_name', action.get('action', '')))
                item.setData(Qt.ItemDataRole.UserRole, action)
                self.action_list.addItem(item)

        if self.action_list.count() > 0:
            # Select the first item by default
            self.action_list.setCurrentRow(0)

    def save_file(self, save_as=False):
        """
        Saves the current YAML data to a file.
        """
        try:
            if save_as or not self.current_file_path:
                self.current_file_path, _ = QFileDialog.getSaveFileName(self, "Save YAML File", "", "YAML Files (*.yml *.yaml)")
            if self.current_file_path:
                yaml_data = self.get_yaml_data()
                yaml_dumper = YAML()
                yaml_dumper.preserve_quotes = True  # Preserve quotes
                with open(self.current_file_path, 'w') as file:
                    yaml_dumper.dump(yaml_data, file)
                print(f"File saved: {self.current_file_path}")
                self.file_path_label.setText(f"Saved File: {self.current_file_path}")  # Update the label
        except Exception as e:
            print(f"Error in save_file: {e}")
            self.file_path_label.setText(f"Error saving file: {e}")  # Update the label on error

    def view_yaml(self):
        """
        Updates and displays the current YAML data in the YAML Preview tab.
        """
        try:
            yaml_data = self.get_yaml_data()
            yaml_dumper = YAML()
            yaml_dumper.preserve_quotes = True  # Preserve quotes
            from io import StringIO
            stream = StringIO()
            yaml_dumper.dump(yaml_data, stream)
            yaml_string = stream.getvalue()

            self.YamlDialog = YamlValidationDialog()
            # file_path = self.current_file_path
            # if file_path:
            #     self.YamlDialog.load_yaml_file_from_path(file_path)
            # else:
            self.YamlDialog.text_edit.setText(yaml_string)

            self.YamlDialog.show()
            # self.YamlDialog.exec()
            # self.yaml_text_edit.setPlainText(yaml_string)  # Update YAML preview
            # self.tab_widget.setCurrentWidget(self.yaml_preview_tab)  # Switch to the YAML preview tab
            # self.file_path_label.setText("")  # Optionally clear or update the label
        except Exception as e:
            print(f"Error in view_yaml: {e}")
            self.file_path_label.setText(f"Error viewing YAML: {e}")  # Update the label on error

    def validate_yaml(self, yaml_data):
        """
        Validates the YAML data against the schema.
        """
        if 'drivers' not in yaml_data:
            print("Error: 'drivers' key missing in YAML data.")
            return False

        for driver_name, driver_data in yaml_data.get('drivers', {}).items():
            if 'actions' not in driver_data:
                print(f"Error: 'actions' key missing for driver '{driver_name}'.")
                return False

            for action in driver_data['actions']:
                action_type = action.get('action')
                if action_type not in self.schema['actions']:
                    print(f"Error: Unknown action type '{action_type}' in driver '{driver_name}'.")
                    return False

                # Validate the required fields for each action type directly
                fields = self.schema['actions'][action_type]['fields']
                for field_info in fields:
                    field_name = field_info['name']

                    # Only validate fields explicitly marked as required
                    if field_info.get('required', False) and field_name not in action:
                        print(
                            f"Error: Missing required field '{field_name}' for action '{action_type}' in driver '{driver_name}'.")
                        return False

        return True

    def display_invalid_yaml_message(self):
        """
        Displays a message when the YAML is invalid and opens the viewer dialog.
        """
        # Display a simple warning dialog
        reply = QMessageBox.warning(
            self,
            "Invalid YAML File",
            "The loaded YAML file does not conform to the expected schema and cannot be edited. "
            "Do you want to view the details?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Ok:
            # Open the YAML viewer dialog with the current file path
            dialog = YamlValidationDialog()
            dialog.load_yaml_file_from_path(self.current_file_path)  # Add a method to load from a file path
            dialog.exec()

        # Optionally, reset specific components if necessary
        self.action_list.clear()
        # self.yaml_text_edit.clear()

    def get_yaml_data(self):
        """
        Collects data from the form fields to construct the updated action dictionary.
        """
        try:
            yaml_data = {'drivers': {}}
            driver_name = self.driver_name_input.text()
            driver_data = {
                'error_string': self.error_string_input.text(),
                'output_path': self.output_path_input.text(),
                'output_mode': self.output_mode_input.currentText(),
                'prompt_count': int(self.prompt_count_input.text()) if self.prompt_count_input.text().isdigit() else None,
                'actions': []
            }

            for i in range(self.action_list.count()):
                item = self.action_list.item(i)
                action_data = item.data(Qt.ItemDataRole.UserRole)
                driver_data['actions'].append(action_data)

            yaml_data['drivers'][driver_name] = driver_data
            return yaml_data
        except Exception as e:
            print(f"Error in get_yaml_data: {e}")
            return {}

    def update_yaml_preview(self):
        """
        Updates the YAML preview tab with the current data.
        """
        try:
            yaml_data = self.get_yaml_data()
            yaml_dumper = YAML()
            yaml_dumper.preserve_quotes = True  # Preserve quotes
            from io import StringIO
            stream = StringIO()
            yaml_dumper.dump(yaml_data, stream)
            yaml_string = stream.getvalue()
            # self.yaml_text_edit.setPlainText(yaml_string)
        except Exception as e:
            print(f"Error in update_yaml_preview: {e}")
            self.file_path_label.setText(f"Error updating YAML preview: {e}")  # Update the label on error

    def open_runner_form(self):
        # Instantiate the RunnerForm with the current window as its parent
        runner_form = RunnerForm(self)

        # Retrieve the primary screen using QApplication
        screen = QApplication.primaryScreen()
        if screen is not None:
            # Get the available geometry of the screen (excludes taskbars, etc.)
            screen_geometry = screen.availableGeometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()

            # Calculate desired size: 80% width and 70% height
            desired_width = int(screen_width * 0.8)
            desired_height = int(screen_height * 0.7)
            runner_form.resize(desired_width, desired_height)

            # Calculate the center position
            screen_center = screen_geometry.center()
            form_rect = runner_form.frameGeometry()
            form_rect.moveCenter(screen_center)

            # Move the form to the center of the screen
            runner_form.move(form_rect.topLeft())

        # Execute the dialog modally
        runner_form.exec()


def check_and_create_directories():
    # List of required directories
    required_dirs = [
        './output',
        './log',
        './project',
        './project/drivers',
        './project/inventory',
        './project/scripts',
        './project/templates',
        './project/vars'
    ]

    # Check for missing directories
    missing_dirs = [dir_path for dir_path in required_dirs if not os.path.exists(dir_path)]

    if missing_dirs:
        # Prompt the user to create missing directories
        response = QMessageBox.question(
            None,
            "Create Missing Directories",
            f"The following directories are missing:\n\n{', '.join(missing_dirs)}\n\nWould you like to create them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if response == QMessageBox.StandardButton.Yes:
            # Create the missing directories
            try:
                for dir_path in missing_dirs:
                    os.makedirs(dir_path)
                create_sample_inventory("project/inventory/sample_inventory.yaml")
                QMessageBox.information(None, "Success", "Missing directories created successfully.")
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Failed to create directories: {str(e)}")
                sys.exit(1)  # Exit the app if directories can't be created
        else:
            sys.exit(1)  # Exit the app if user refuses to create directories


def create_sample_inventory(file_path):
    # Sample data in the YAML format
    sample_data = {
        'credentials': [
            {'id': 1, 'name': 'default', 'username': 'cisco', 'password': 'cisco'}
        ],
        'devices': [
            {'credential_ids': [1], 'hostname': 'usa1-rtr-1', 'id': 1, 'mgmt_ip': '172.16.101.100',
             'model': 'Unknown Model',
             'platform_id': 2, 'role_id': 3, 'serial_number': 'Unknown SN', 'site_id': 1,
             'timestamp': '2023-08-24 10:00:00',
             'vendor_id': 1},
            {'credential_ids': [1], 'hostname': 'usa1-core-02', 'id': 2, 'mgmt_ip': '172.16.101.1',
             'model': 'Unknown Model',
             'platform_id': 2, 'role_id': 2, 'serial_number': 'Unknown SN', 'site_id': 1,
             'timestamp': '2023-08-24 10:00:00',
             'vendor_id': 1},

        ],
        'platforms': [
            {'id': 1, 'name': 'Unknown'},
            {'id': 2, 'name': 'unknown'},
            {'id': 3, 'name': 'Unknown Platform'}
        ],
        'roles': [
            {'id': 1, 'name': 'access'},
            {'id': 2, 'name': 'core'},
            {'id': 3, 'name': 'rtr'}
        ],
        'sites': [
            {'id': 1, 'location': 'Unknown Location', 'name': 'usa1'},
            {'id': 2, 'location': 'Unknown Location', 'name': 'usa2'}
        ],
        'vendors': [
            {'id': 1, 'name': 'Cisco'}
        ]
    }

    # Write the sample data to a YAML file
    with open(file_path, 'w') as file:
        yaml.dump(sample_data, file)


def main():
    app = QApplication(sys.argv)

    # Check and create required directories
    check_and_create_directories()

    editor = DriverEditor()

    # Retrieve the primary screen
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
        editor.resize(desired_width, desired_height)

        # Optional: Center the window on the screen
        x = (screen_width - desired_width) // 2
        y = (screen_height - desired_height) // 2
        editor.move(x, y - 50)
    else:
        # Fallback size if screen information is unavailable
        editor.resize(800, 600)

    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()