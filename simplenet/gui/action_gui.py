import traceback
from time import sleep

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QComboBox, QCheckBox, QListWidget, QPushButton, QFileDialog,
    QScrollArea, QFormLayout, QMessageBox, QGroupBox, QDialog,
    QDialogButtonBox, QMenu, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal


class ActionEditor(QWidget):
    action_updated = pyqtSignal(dict)

    def __init__(self, schema, parent=None):
        super().__init__(parent)
        self.schema = schema
        self.current_action = None
        self.fields = {}
        self.init_ui()

    def init_ui(self):
        try:
            self.layout = QVBoxLayout(self)
            scroll_area = QScrollArea(self)
            scroll_area.setWidgetResizable(True)
            self.form_widget = QWidget()
            self.form_layout = QFormLayout(self.form_widget)
            scroll_area.setWidget(self.form_widget)
            self.layout.addWidget(scroll_area)
            print("Initialized UI with scroll area and form layout.")
        except Exception as e:
            print(f"Error in init_ui: {e}")
            traceback.print_exc()

    def update_form(self, action_data):
        try:
            print("Updating form with action data.")
            self.clear_dynamic_fields()
            self.current_action = action_data
            action_type = action_data.get('action', 'send_command')

            self.action_type_combo = QComboBox()
            self.action_type_combo.addItems(self.schema['actions'].keys())
            self.form_layout.addRow("Action Type:", self.action_type_combo)
            self.action_type_combo.setCurrentText(action_type)
            self.action_type_combo.currentTextChanged.connect(self.on_action_type_changed)

            self.create_fields_for_action(self.schema['actions'][action_type]['fields'], self.form_layout)

            # Set field values, including nested fields
            fields = self.schema['actions'][action_type]['fields']
            self.set_field_values(fields, action_data)
            # Don't hardcode displayname, its in the schema
            print("Form updated successfully.")

        except Exception as e:
            print(f"Error in update_form: {e}")
            traceback.print_exc()

    def clear_dynamic_fields(self):
        try:
            print("Clearing dynamic fields.")
            for i in reversed(range(self.form_layout.count())):
                widget_item = self.form_layout.itemAt(i)
                if widget_item is not None:
                    widget = widget_item.widget()
                    if widget is not None:
                        widget.deleteLater()
                        print(f"Deleted widget at index {i}.")
            self.fields.clear()
            print("All dynamic fields cleared.")
        except Exception as e:
            print(f"Error in clear_dynamic_fields: {e}")
            traceback.print_exc()

    def create_fields_for_action(self, fields, layout, parent_key=''):
        try:
            for field_info in fields:
                field_name = field_info['name']
                field_label = QLabel(field_info['label'])

                # Create a unique key for each field, including nested ones
                full_key = f"{parent_key}.{field_name}" if parent_key else field_name

                if field_info['type'] == 'text':
                    field_widget = QLineEdit()
                elif field_info['type'] == 'multiline_text':
                    field_widget = QTextEdit()
                elif field_info['type'] == 'file':
                    field_widget = QLineEdit()
                    browse_button = QPushButton("Browse")
                    # Correct lambda to capture current field_widget
                    browse_button.clicked.connect(lambda _, fw=field_widget: self.browse_file(fw))
                    file_layout = QHBoxLayout()
                    file_layout.addWidget(field_widget)
                    file_layout.addWidget(browse_button)
                    file_widget_container = QWidget()
                    file_widget_container.setLayout(file_layout)
                    layout.addRow(field_label, file_widget_container)
                    self.fields[full_key] = field_widget
                    print(f"Created file field '{full_key}'.")
                    continue
                elif field_info['type'] == 'checkbox':
                    field_widget = QCheckBox()
                elif field_info['type'] == 'choice':
                    field_widget = QComboBox()
                    field_widget.addItems(field_info.get('choices', []))
                elif field_info['type'] == 'nested':
                    nested_layout = QFormLayout()
                    nested_group = QGroupBox(field_info['label'])
                    nested_group.setLayout(nested_layout)
                    layout.addRow(nested_group)
                    # Recursively create nested fields
                    self.create_fields_for_action(field_info['fields'], nested_layout, parent_key=full_key)
                    print(f"Created nested field '{full_key}'.")
                    continue
                elif field_info['type'] == 'list':
                    list_widget = QListWidget()
                    list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    list_widget.customContextMenuRequested.connect(
                        lambda pos, lw=list_widget, fi=field_info: self.show_context_menu(pos, lw, fi))

                    add_button = QPushButton("Add")
                    # Correct lambda to capture current full_key and field_info
                    add_button.clicked.connect(lambda checked, fn=full_key, fi=field_info: self.add_list_item(fn, fi))

                    list_layout = QVBoxLayout()
                    list_layout.addWidget(list_widget)
                    list_layout.addWidget(add_button)
                    list_container = QWidget()
                    list_container.setLayout(list_layout)
                    layout.addRow(field_label, list_container)
                    self.fields[full_key] = list_widget
                    print(f"Created list field '{full_key}'.")
                    continue

                layout.addRow(field_label, field_widget)
                self.fields[full_key] = field_widget
                print(f"Created field '{full_key}' of type '{field_info['type']}'.")

                if not field_info.get('required', True):
                    field_label.setEnabled(True)
                    field_widget.setEnabled(True)

        except Exception as e:
            print(f"Error in create_fields_for_action: {e}")
            traceback.print_exc()

    def browse_file(self, field_edit):
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*)")
            if file_path:
                field_edit.setText(file_path)
                print(f"File selected: {file_path}")
        except Exception as e:
            print(f"Error in browse_file: {e}")
            traceback.print_exc()

    def on_action_type_changed(self, action_type):
        try:
            print(f"Action type changed to '{action_type}'.")
            self.clear_dynamic_fields()
            self.create_fields_for_action(self.schema['actions'][action_type]['fields'], self.form_layout)

            # After creating new fields, populate them with data if available
            if self.current_action:
                # Retrieve the relevant subset of action_data
                action_data_subset = self.current_action.copy()
                # Avoid duplicating 'action' and 'display_name'
                action_data_subset.pop('action', None)
                action_data_subset.pop('display_name', None)
                self.set_field_values(self.schema['actions'][action_type]['fields'], action_data_subset)
                print(f"Populated fields for action type '{action_type}'.")
        except KeyError as e:
            print(f"KeyError in on_action_type_changed: {e} not found in schema.")
            traceback.print_exc()
        except Exception as e:
            print(f"Error in on_action_type_changed: {e}")
            traceback.print_exc()

    def show_context_menu(self, pos, list_widget, field_info):
        try:
            item = list_widget.itemAt(pos)
            if item is None:
                return

            menu = QMenu()
            edit_action = menu.addAction("Edit")
            delete_action = menu.addAction("Delete")

            action = menu.exec(list_widget.mapToGlobal(pos))
            if action == edit_action:
                self.edit_list_item(list_widget, item, field_info)
            elif action == delete_action:
                list_widget.takeItem(list_widget.row(item))
                print(f"Deleted list item from '{list_widget}': {item.text()}")

        except Exception as e:
            print(f"Error in show_context_menu: {e}")
            traceback.print_exc()

    def add_list_item(self, field_name, field_info):
        try:
            list_widget = self.fields[field_name]
            item_editor = ListItemEditor(field_info['fields'], self)
            if item_editor.exec():
                item_data = item_editor.get_item_data()
                list_item = QListWidgetItem()
                # Use 'name' or another appropriate field for display
                display_name = item_data.get('name', f"Item {list_widget.count() + 1}")
                list_item.setText(display_name)
                list_item.setData(Qt.ItemDataRole.UserRole, item_data)
                list_widget.addItem(list_item)
                print(f"Added list item to '{field_name}': {item_data}")

        except Exception as e:
            print(f"Error in add_list_item: {e}")
            traceback.print_exc()

    def edit_list_item(self, list_widget, item, field_info):
        try:
            item_data = item.data(Qt.ItemDataRole.UserRole)
            item_editor = ListItemEditor(field_info['fields'], self, item_data)
            if item_editor.exec():
                new_item_data = item_editor.get_item_data()
                item.setData(Qt.ItemDataRole.UserRole, new_item_data)
                display_name = new_item_data.get('name', f"Item {list_widget.row(item) + 1}")
                item.setText(display_name)
                print(f"Edited list item in '{list_widget}': {new_item_data}")

        except Exception as e:
            print(f"Error in edit_list_item: {e}")
            traceback.print_exc()

    def get_action_data(self):
        try:
            print("Retrieving action data.")
            action_type = self.action_type_combo.currentText()
            self.current_action['action'] = action_type
            # self.current_action['display_name'] = self.display_name_edit.text()

            # Iterate over all fields and set values
            for full_key, field in self.fields.items():
                # Split the full_key to handle nested data
                keys = full_key.split('.')
                current_dict = self.current_action
                for key in keys[:-1]:
                    current_dict = current_dict.setdefault(key, {})
                final_key = keys[-1]

                if isinstance(field, QLineEdit):
                    current_dict[final_key] = field.text()
                    print(f"Saved QLineEdit '{full_key}': {field.text()}")
                elif isinstance(field, QTextEdit):
                    current_dict[final_key] = field.toPlainText()
                    print(f"Saved QTextEdit '{full_key}': {field.toPlainText()}")
                elif isinstance(field, QCheckBox):
                    current_dict[final_key] = field.isChecked()
                    print(f"Saved QCheckBox '{full_key}': {field.isChecked()}")
                elif isinstance(field, QComboBox):
                    current_dict[final_key] = field.currentText()
                    print(f"Saved QComboBox '{full_key}': {field.currentText()}")
                elif isinstance(field, QListWidget):
                    items = []
                    for index in range(field.count()):
                        item = field.item(index)
                        item_data = item.data(Qt.ItemDataRole.UserRole)
                        items.append(item_data)
                        print(f"Saved QListWidget '{full_key}' item {index}: {item_data}")
                    current_dict[final_key] = items

            self.action_updated.emit(self.current_action)
            print(f"Action data retrieved successfully: {self.current_action}")
            return self.current_action

        except Exception as e:
            print(f"Error in get_action_data: {e}")
            traceback.print_exc()

    def validate_fields(self):
        missing_fields = []
        fields = self.schema['actions'][self.current_action['action']]['fields']
        self.recursive_validate(fields, self.current_action, missing_fields)

        if missing_fields:
            QMessageBox.warning(self, "Validation Error",
                                f"Please fill in the required fields: {', '.join(missing_fields)}")
            print(f"Validation failed. Missing fields: {missing_fields}")
            return False
        print("Validation successful.")
        return True

    def recursive_validate(self, fields, data, missing_fields, parent_key=''):
        for field_info in fields:
            field_name = field_info['name']
            full_key = f"{parent_key}.{field_name}" if parent_key else field_name
            field_type = field_info['type']
            is_required = field_info.get('required', True)

            if field_type == 'nested':
                nested_data = data.get(field_name, {})
                nested_fields = field_info.get('fields', [])
                print(f"Validating nested field '{full_key}'.")
                self.recursive_validate(nested_fields, nested_data, missing_fields, parent_key=full_key)
            elif field_type == 'list':
                list_data = data.get(field_name, [])
                if is_required and len(list_data) == 0:
                    missing_fields.append(field_info['label'])
                    print(f"List field '{full_key}' is required but empty.")
                else:
                    for index, item in enumerate(list_data):
                        print(f"Validating list item {index} in '{full_key}'.")
                        nested_fields = field_info.get('fields', [])
                        self.recursive_validate(nested_fields, item, missing_fields, parent_key=f"{full_key}.{index}")
            else:
                if is_required:
                    widget = self.fields.get(full_key)
                    if widget:
                        if isinstance(widget, QLineEdit) and not widget.text():
                            missing_fields.append(field_info['label'])
                            print(f"Required QLineEdit '{full_key}' is empty.")
                        elif isinstance(widget, QTextEdit) and not widget.toPlainText():
                            missing_fields.append(field_info['label'])
                            print(f"Required QTextEdit '{full_key}' is empty.")
                        elif isinstance(widget, QComboBox) and not widget.currentText():
                            missing_fields.append(field_info['label'])
                            print(f"Required QComboBox '{full_key}' is empty.")
                        elif isinstance(widget, QListWidget) and widget.count() == 0:
                            missing_fields.append(field_info['label'])
                            print(f"Required QListWidget '{full_key}' is empty.")

    def set_field_values(self, fields, data, parent_key=''):
        """
        Recursively set field values based on the schema and action data.

        :param fields: List of field definitions from the schema.
        :param data: Dictionary containing the data to populate the fields.
        :param parent_key: Hierarchical key representing the field's position in the schema.
        """

        for field_info in fields:
            field_name = field_info['name']
            full_key = f"{parent_key}.{field_name}" if parent_key else field_name
            field_type = field_info['type']

            # Retrieve the corresponding widget
            widget = self.fields.get(full_key)

            if field_type == 'nested':
                # For nested fields, retrieve the nested data
                nested_data = data.get(field_name, {})
                nested_fields = field_info.get('fields', [])
                print(f"Setting nested fields for '{full_key}': {nested_data}")
                # Recursively set values for nested fields
                self.set_field_values(nested_fields, nested_data, parent_key=full_key)
            elif field_type == 'list':
                # Handle list fields
                try:
                    list_data = data.get(field_name, [])

                    if True:
                        widget.clear()
                        print(f"Setting list field '{full_key}' with {len(list_data)} items.")
                        for index, item_data in enumerate(list_data):
                            sleep(1)
                            list_item = QListWidgetItem()
                            # Use 'name' or another appropriate field for display name
                            display_name = item_data.get('name', f"Item {index + 1}")
                            list_item.setText(display_name)
                            list_item.setData(Qt.ItemDataRole.UserRole, item_data)
                            widget.addItem(list_item)
                            print(f"Added list item '{display_name}' to '{full_key}': {item_data}")
                        print(f"Total items in '{full_key}': {widget.count()}")
                except Exception as e:
                    traceback.print_exc()
            else:
                if widget:
                    value = data.get(field_name, '' if field_type not in ['checkbox', 'list'] else [])
                    # Set widget value based on its type
                    if field_type == 'text':
                        widget.setText(str(value))
                        print(f"Setting QLineEdit '{full_key}': {value}")
                    elif field_type == 'multiline_text':
                        widget.setPlainText(str(value))
                        print(f"Setting QTextEdit '{full_key}': {value}")
                    elif field_type == 'file':
                        widget.setText(str(value))
                        print(f"Setting File Path '{full_key}': {value}")
                    elif field_type == 'checkbox':
                        widget.setChecked(bool(value))
                        print(f"Setting QCheckBox '{full_key}': {bool(value)}")
                    elif field_type == 'choice':
                        index = widget.findText(str(value))
                        if index != -1:
                            widget.setCurrentIndex(index)
                            print(f"Setting QComboBox '{full_key}': {value}")
                    # No else needed since list and nested are already handled

class ListItemEditor(QDialog):
    def __init__(self, fields, parent=None, initial_data=None):
        super().__init__(parent)
        self.fields = fields
        self.field_widgets = {}
        self.initial_data = initial_data
        self.init_ui()

    def init_ui(self):
        try:
            layout = QFormLayout(self)
            for field in self.fields:
                self.create_field(field, layout, self.field_widgets)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addRow(buttons)
            print("Initialized ListItemEditor UI.")
        except Exception as e:
            print(f"Error in ListItemEditor init_ui: {e}")
            traceback.print_exc()

    def create_field(self, field, layout, widget_dict):
        try:
            field_name = field['name']
            field_label = QLabel(field['label'])

            if field['type'] == 'text':
                widget = QLineEdit()
            elif field['type'] == 'multiline_text':
                widget = QTextEdit()
            elif field['type'] == 'choice':
                widget = QComboBox()
                widget.addItems(field.get('choices', []))
            elif field['type'] == 'nested':
                widget = self.create_nested_widget(field['fields'])
            else:
                widget = QLineEdit()  # Default to QLineEdit for unknown types

            layout.addRow(field_label, widget)
            widget_dict[field_name] = widget
            print(f"ListItemEditor: Created field '{field_name}' of type '{field['type']}'.")

            if self.initial_data and field_name in self.initial_data:
                self.set_widget_value(widget, self.initial_data[field_name])

        except Exception as e:
            print(f"Error in create_field: {e}")
            traceback.print_exc()

    def create_nested_widget(self, nested_fields):
        try:
            nested_widget = QWidget()
            nested_layout = QFormLayout(nested_widget)
            nested_widgets = {}
            for field in nested_fields:
                self.create_field(field, nested_layout, nested_widgets)
            nested_widget.setProperty("nested_widgets", nested_widgets)
            print("ListItemEditor: Created nested widget.")
            return nested_widget
        except Exception as e:
            print(f"Error in create_nested_widget: {e}")
            traceback.print_exc()

    # def set_widget_value(self, widget, value):
    #     try:
    #         if isinstance(widget, QLineEdit):
    #             widget.setText(str(value))
    #             print(f"ListItemEditor: Setting QLineEdit value to '{value}'.")
    #         elif isinstance(widget, QTextEdit):
    #             widget.setPlainText(str(value))
    #             print(f"ListItemEditor: Setting QTextEdit value to '{value}'.")
    #         elif isinstance(widget, QComboBox):
    #             index = widget.findText(str(value))
    #             if index >= 0:
    #                 widget.setCurrentIndex(index)
    #                 print(f"ListItemEditor: Setting QComboBox value to '{value}'.")
    #         elif isinstance(widget, QWidget) and isinstance(value, dict):
    #             nested_widgets = widget.property("nested_widgets")
    #             if nested_widgets:
    #                 for key, nested_value in value.items():
    #                     if key in nested_widgets:
    #                         self.set_widget_value(nested_widgets[key], nested_value)
    #                         print(f"ListItemEditor: Setting Nested Widget '{key}' to '{nested_value}'.")
    #     except Exception as e:
    #         print(f"Error in set_widget_value: {e}")
    #         traceback.print_exc()

    def get_item_data(self):
        try:
            item_data = self.get_widget_data(self.field_widgets)
            print(f"ListItemEditor: Retrieved item data: {item_data}")
            return item_data
        except Exception as e:
            print(f"Error in get_item_data: {e}")
            traceback.print_exc()
            return {}

    def set_widget_value(self, widget, value):
        try:
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
                print(f"ListItemEditor: Setting QLineEdit '{widget}' value to '{value}'.")
            elif isinstance(widget, QTextEdit):
                widget.setPlainText(str(value))
                print(f"ListItemEditor: Setting QTextEdit '{widget}' value to '{value}'.")
            elif isinstance(widget, QComboBox):
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
                    print(f"ListItemEditor: Setting QComboBox '{widget}' value to '{value}'.")
            elif isinstance(widget, QWidget) and isinstance(value, dict):
                nested_widgets = widget.property("nested_widgets")
                if nested_widgets:
                    for key, nested_value in value.items():
                        if key in nested_widgets:
                            self.set_widget_value(nested_widgets[key], nested_value)
                            print(f"ListItemEditor: Setting Nested Widget '{key}' to '{nested_value}'.")
        except Exception as e:
            print(f"Error in ListItemEditor set_widget_value: {e}")
            traceback.print_exc()

    def get_widget_data(self, widget_dict):
        try:
            item_data = {}
            for field_name, widget in widget_dict.items():
                if isinstance(widget, QLineEdit):
                    item_data[field_name] = widget.text()
                    print(f"ListItemEditor: Retrieved QLineEdit '{field_name}': {widget.text()}")
                elif isinstance(widget, QTextEdit):
                    item_data[field_name] = widget.toPlainText()
                    print(f"ListItemEditor: Retrieved QTextEdit '{field_name}': {widget.toPlainText()}")
                elif isinstance(widget, QComboBox):
                    item_data[field_name] = widget.currentText()
                    print(f"ListItemEditor: Retrieved QComboBox '{field_name}': {widget.currentText()}")
                elif isinstance(widget, QWidget):
                    nested_widgets = widget.property("nested_widgets")
                    if nested_widgets:
                        item_data[field_name] = self.get_widget_data(nested_widgets)
                        print(f"ListItemEditor: Retrieved Nested Widget '{field_name}': {item_data[field_name]}")
            return item_data
        except Exception as e:
            print(f"Error in ListItemEditor get_widget_data: {e}")
            traceback.print_exc()
            return {}
