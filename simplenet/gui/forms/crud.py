import io
import os
import re
import sys

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget, QPushButton,
                             QHBoxLayout, QFileDialog, QTableWidget, QTableWidgetItem,
                             QMessageBox, QLineEdit, QApplication, QDialog, QLabel, QTextEdit)
import sqlite3
from ruamel.yaml import YAML
def create_sqlite_db(yaml_file=None, db_file = ':memory:'):
    """
    Create a SQLite database file from a YAML file.

    Args:
        yaml_file (str): Path to the YAML file containing the inventory.
        db_file (str): Path to the SQLite database file to create.

    Returns:
        sqlite3.Connection: SQLite connection object to the created database.
    """
    # Remove the existing database file if it exists
    if db_file != ':memory:' and os.path.exists(db_file):
        os.remove(db_file)

    # Create a new SQLite database file
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    # Create tables based on the YAML structure
    c.execute('''CREATE TABLE devices
                 (id INTEGER PRIMARY KEY, hostname TEXT, mgmt_ip TEXT, model TEXT,
                 serial_number TEXT, timestamp TEXT, platform_id INTEGER, role_id INTEGER,
                 site_id INTEGER, vendor_id INTEGER)''')
    c.execute('CREATE TABLE credentials (id INTEGER PRIMARY KEY, name TEXT, username TEXT, password TEXT)')
    c.execute('CREATE TABLE platforms (id INTEGER PRIMARY KEY, name TEXT)')
    c.execute('CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT)')
    c.execute('CREATE TABLE sites (id INTEGER PRIMARY KEY, name TEXT, location TEXT)')
    c.execute('CREATE TABLE vendors (id INTEGER PRIMARY KEY, name TEXT)')
    c.execute('CREATE TABLE device_credentials (device_id INTEGER, credential_id INTEGER)')
    c.execute('''
        CREATE VIEW device_details AS
        SELECT 
            d.id, d.hostname, d.mgmt_ip, d.model, d.serial_number, d.timestamp,
            p.name AS platform_name,
            r.name AS role_name,
            s.name AS site_name, s.location AS site_location,
            v.name AS vendor_name
        FROM devices d
        LEFT JOIN platforms p ON d.platform_id = p.id
        LEFT JOIN roles r ON d.role_id = r.id
        LEFT JOIN sites s ON d.site_id = s.id
        LEFT JOIN vendors v ON d.vendor_id = v.id
        ''')
    if yaml_file is None:

        # Create default records if no YAML file is provided
        c.execute(
            'INSERT INTO devices (id, hostname, mgmt_ip, model, serial_number, timestamp, platform_id, role_id, site_id, vendor_id) VALUES (1, "default-hostname", "0.0.0.0", "default-model", "default-serial", "2023-01-01 00:00:00", 1, 1, 1, 1)')
        c.execute(
            'INSERT INTO credentials (id, name, username, password) VALUES (1, "default-cred", "user", "password")')
        c.execute('INSERT INTO platforms (id, name) VALUES (1, "default-platform")')
        c.execute('INSERT INTO roles (id, name) VALUES (1, "default-role")')
        c.execute('INSERT INTO sites (id, name, location) VALUES (1, "default-site", "default-location")')
        c.execute('INSERT INTO vendors (id, name) VALUES (1, "default-vendor")')

    else:
        # Load YAML data using ruamel.yaml
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True  # Preserve quotes if necessary

        with open(yaml_file, 'r') as file:
            data = yaml_loader.load(file)

        # Insert data into tables
        for device in data.get('devices', []):
            c.execute('''INSERT INTO devices (id, hostname, mgmt_ip, model, serial_number, timestamp, platform_id, role_id, site_id, vendor_id)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (device.get('id'), device.get('hostname'), device.get('mgmt_ip'), device.get('model'),
                       device.get('serial_number'), device.get('timestamp'), device.get('platform_id'),
                       device.get('role_id'), device.get('site_id'), device.get('vendor_id')))
            for cred_id in device.get('credential_ids', []):
                c.execute('INSERT INTO device_credentials (device_id, credential_id) VALUES (?, ?)', (device.get('id'), cred_id))

        for cred in data.get('credentials', []):
            c.execute('INSERT INTO credentials (id, name, username, password) VALUES (?, ?, ?, ?)',
                      (cred.get('id'), cred.get('name'), cred.get('username'), cred.get('password')))

        for platform in data.get('platforms', []):
            c.execute('INSERT INTO platforms (id, name) VALUES (?, ?)', (platform.get('id'), platform.get('name')))

        for role in data.get('roles', []):
            c.execute('INSERT INTO roles (id, name) VALUES (?, ?)', (role.get('id'), role.get('name')))

        for site in data.get('sites', []):
            c.execute('INSERT INTO sites (id, name, location) VALUES (?, ?, ?)', (site.get('id'), site.get('name'), site.get('location')))

        for vendor in data.get('vendors', []):
            c.execute('INSERT INTO vendors (id, name) VALUES (?, ?)', (vendor.get('id'), vendor.get('name')))

    conn.commit()
    return conn


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


class RecordInputDialog(QDialog):  # Changed from QMessageBox to QDialog for better form input handling
    def __init__(self, columns, current_values=None, exclude=None):
        super().__init__()
        self.setWindowTitle("Record Input")
        self.columns = [col for col in columns if not exclude or col not in exclude]
        self.inputs = {}
        self.current_values = current_values or {}

        # Layout setup
        self.layout = QVBoxLayout(self)
        self.form_layout = QVBoxLayout()

        for column in self.columns:
            label = QLabel(column.capitalize())
            input_field = QLineEdit()
            input_field.setText(self.current_values.get(column, ""))  # Set current value if editing
            self.inputs[column] = input_field

            row_layout = QHBoxLayout()
            row_layout.addWidget(label)
            row_layout.addWidget(input_field)

            self.form_layout.addLayout(row_layout)

        self.layout.addLayout(self.form_layout)

        # Add buttons
        self.button_box = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.button_box.addWidget(self.ok_button)
        self.button_box.addWidget(self.cancel_button)

        self.layout.addLayout(self.button_box)

    def get_values(self):
        return {col: self.inputs[col].text() for col in self.columns}

class CRUDWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = None
        self.current_yaml_file = None

        self.setWindowTitle('Inventory Manager')
        self.setGeometry(100, 100, 1000, 700)

        # Create layout
        layout = QVBoxLayout(self)

        # Initialize toolbar
        self.init_toolbar(layout)

        # Initialize tab widget for table management
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Initialize with no data
        self.tables = ["devices", "credentials", "platforms", "roles", "sites", "vendors"]

    def init_toolbar(self, layout):
        toolbar = QHBoxLayout()

        open_button = QPushButton("Open YAML", self)
        save_button = QPushButton("Save As YAML", self)
        new_yaml_button = QPushButton("New YAML", self)
        view_yaml_button = QPushButton("View as YAML", self)  # New button

        open_button.clicked.connect(self.open_file)
        save_button.clicked.connect(self.save_as_file)
        new_yaml_button.clicked.connect(self.new_yaml)
        view_yaml_button.clicked.connect(self.view_as_yaml)  # Connect to view_as_yaml method

        toolbar.addWidget(open_button)
        toolbar.addWidget(save_button)
        toolbar.addWidget(new_yaml_button)
        toolbar.addWidget(view_yaml_button)  # Add the View as YAML button

        layout.addLayout(toolbar)

    def view_as_yaml(self):
        """Open a dialog to display the current database as YAML."""
        if not self.conn:
            QMessageBox.warning(self, "No Data", "No data available to view as YAML.")
            return

        # Retrieve current data from the database
        yaml_data = self.get_yaml_from_db()  # This should return a string

        # Open custom dialog to show the YAML content
        dialog = QDialog(self)
        dialog.setWindowTitle("View as YAML")
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)

        # Create a QTextEdit to display the YAML
        text_edit = QTextEdit(dialog)
        text_edit.setPlainText(yaml_data)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        # Apply YAML syntax highlighting
        self.highlighter = YamlSyntaxHighlighter(text_edit.document())

        # Add close button
        close_button = QPushButton("Close", dialog)
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.exec()

    import io

    def get_yaml_from_db(self):
        """Retrieve current database content and return it as a YAML string."""
        cursor = self.conn.cursor()
        yaml_data = {}

        try:
            # Fetch data from each table
            for table in self.tables:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                yaml_data[table] = [dict(zip(columns, row)) for row in rows]

            # Convert data to YAML string
            yaml = YAML()
            yaml.indent(mapping=2, sequence=4, offset=2)

            # Use StringIO as the stream to capture the output of dump()
            stream = io.StringIO()
            yaml.dump(yaml_data, stream)

            # Get the string from StringIO and return it
            yaml_str = stream.getvalue()
            return yaml_str

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error retrieving data from database: {e}")
            return ""

    def new_yaml(self):
        """Create a new in-memory SQLite database with default records."""
        self.conn = create_sqlite_db()  # Call create_sqlite_db with no YAML file (this will insert default records)

        # Clear and set up the new database with default records
        self.tab_widget.clear()
        self.setup_tabs()

        QMessageBox.information(self, "Success", "Created new YAML with default records.")


    def open_file(self):
        options = QFileDialog.Option.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Inventory YAML", "", "YAML Files (*.yaml *.yml)", options=options)
        if file_name:
            try:
                if self.conn:
                    self.conn.close()
                    self.tab_widget.clear()
                self.current_yaml_file = file_name
                self.conn = create_sqlite_db(file_name, ':memory:')
                self.setup_tabs()
                QMessageBox.information(self, "Success", f"Loaded inventory from {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {e}")

    def save_as_file(self):
        if not self.conn:
            QMessageBox.warning(self, "No Data", "No inventory data to save.")
            return

        options = QFileDialog.Option.DontUseNativeDialog
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Inventory YAML As", "", "YAML Files (*.yaml *.yml)", options=options)
        if file_name:
            try:
                self.save_to_yaml(file_name)
                QMessageBox.information(self, "Success", f"Inventory saved to {file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save file: {e}")

    def setup_tabs(self):
        for table in self.tables:
            self.add_tab(table)

    def add_tab(self, table_name):
        """Adds a new tab with the given table_name for CRUD operations"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Table for viewing data
        table_widget = QTableWidget()
        table_widget.setObjectName(f"{table_name}_table")
        self.load_data(table_widget, table_name)

        # Add CRUD buttons
        button_layout = QHBoxLayout()
        add_button = QPushButton("Add")
        update_button = QPushButton("Update")
        delete_button = QPushButton("Delete")

        add_button.clicked.connect(lambda: self.add_record(table_name, table_widget))
        update_button.clicked.connect(lambda: self.update_record(table_name, table_widget))
        delete_button.clicked.connect(lambda: self.delete_record(table_name, table_widget))

        button_layout.addWidget(add_button)
        button_layout.addWidget(update_button)
        button_layout.addWidget(delete_button)

        layout.addWidget(table_widget)
        layout.addLayout(button_layout)

        tab.setLayout(layout)
        self.tab_widget.addTab(tab, table_name.capitalize())

    def load_data(self, table_widget, table_name):
        """Load data from SQLite into the table widget"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            table_widget.setRowCount(len(rows))
            table_widget.setColumnCount(len(columns))
            table_widget.setHorizontalHeaderLabels(columns)

            for row_idx, row_data in enumerate(rows):
                for col_idx, col_data in enumerate(row_data):
                    table_widget.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error loading data from {table_name}: {e}")

    def add_record(self, table_name, table_widget):
        """Add a new record to the selected table"""
        cursor = self.conn.cursor()
        columns = self.get_table_columns(table_name)
        if not columns:
            return

        # Exclude the primary key (assuming it's 'id' and it's auto-increment)
        input_dialog = RecordInputDialog(columns, exclude=['id'])
        if input_dialog.exec():
            values = input_dialog.get_values()
            placeholders = ', '.join(['?'] * len(values))
            column_names = ', '.join(values.keys())
            try:
                cursor.execute(f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})", tuple(values.values()))
                self.conn.commit()
                self.load_data(table_widget, table_name)
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Error adding record: {e}")

    def update_record(self, table_name, table_widget):
        """Update the selected record in the table"""
        cursor = self.conn.cursor()
        selected_row = table_widget.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a row to update.")
            return

        columns = self.get_table_columns(table_name)
        if not columns:
            return

        primary_key = 'id'  # Assuming 'id' is the primary key
        pk_index = columns.index(primary_key)
        record_id = table_widget.item(selected_row, pk_index).text()

        current_values = {}
        for col_idx, col_name in enumerate(columns):
            current_values[col_name] = table_widget.item(selected_row, col_idx).text()

        # Open input dialog with current values
        input_dialog = RecordInputDialog(columns, current_values, exclude=[primary_key])
        if input_dialog.exec():
            new_values = input_dialog.get_values()
            set_clause = ', '.join([f"{k} = ?" for k in new_values.keys()])

            try:
                cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE {primary_key} = ?",
                               (*new_values.values(), record_id))
                self.conn.commit()
                self.load_data(table_widget, table_name)  # Reload data to reflect the update
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Error updating record: {e}")

    def delete_record(self, table_name, table_widget):
        """Delete the selected record from the table"""
        cursor = self.conn.cursor()
        selected_row = table_widget.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "No Selection", "Please select a row to delete.")
            return

        columns = self.get_table_columns(table_name)
        if not columns:
            return

        primary_key = 'id'
        pk_index = columns.index(primary_key)
        record_id = table_widget.item(selected_row, pk_index).text()

        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete record ID {record_id}?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                cursor.execute(f"DELETE FROM {table_name} WHERE {primary_key} = ?", (record_id,))
                self.conn.commit()
                self.load_data(table_widget, table_name)
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Error deleting record: {e}")

    def get_table_columns(self, table_name):
        """Retrieve column names for a given table"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            columns = [info[1] for info in columns_info]
            return columns
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error retrieving columns for {table_name}: {e}")
            return []

    def save_to_yaml(self, file_path):
        """Save the current database state back to a YAML file"""
        cursor = self.conn.cursor()
        yaml_data = {}

        try:
            # Fetch data from each table
            for table in self.tables:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                yaml_data[table] = [dict(zip(columns, row)) for row in rows]

            # Handle device_credentials separately
            cursor.execute("SELECT * FROM device_credentials")
            device_creds = cursor.fetchall()
            yaml_data["device_credentials"] = [{"device_id": dc[0], "credential_id": dc[1]} for dc in device_creds]

            yaml = YAML()
            yaml.indent(mapping=2, sequence=4, offset=2)
            with open(file_path, 'w') as file:
                yaml.dump(yaml_data, file)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", f"Error saving to YAML: {e}")


def main():
    app = QApplication(sys.argv)
    widget = CRUDWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()