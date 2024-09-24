import sys
import os
import sqlite3

from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from ruamel.yaml import YAML
from PyQt6.QtWidgets import (QApplication, QMainWindow,QTabWidget,QWidget,QFileDialog,
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QTableWidget, QSplitter,
    QTableWidgetItem, QMessageBox, QTreeWidget, QTreeWidgetItem, QLineEdit
)

class CRUDWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.conn = None
        self.current_yaml_file = None

        self.setWindowTitle('Inventory Manager')
        self.setGeometry(100, 100, 1000, 700)

        # Initialize menu
        self.init_menu()

        # Initialize tab widget
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # Initialize with no data
        self.tables = ["devices", "credentials", "platforms", "roles", "sites", "vendors"]

    def init_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')

        open_action = QAction('Open', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_as_action = QAction('Save As', self)
        save_as_action.setShortcut('Ctrl+S')
        save_as_action.triggered.connect(self.save_as_file)
        file_menu.addAction(save_as_action)

        exit_action = QAction('Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Add an option to open the SQL Query Tester
        query_action = QAction('SQL Query Tester', self)
        query_action.setShortcut('Ctrl+T')
        query_action.triggered.connect(self.open_sql_query_tester)
        menubar.addAction(query_action)

    def open_sql_query_tester(self):
        """Open the SQL Query Tester dialog."""
        if self.conn:
            dialog = SQLQueryDialog(self.conn)
            dialog.exec()
        else:
            QMessageBox.warning(self, "No Database", "No database is currently loaded.")

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

        primary_key = 'id'
        pk_index = columns.index(primary_key)
        record_id = table_widget.item(selected_row, pk_index).text()

        current_values = {}
        for col_idx, col_name in enumerate(columns):
            current_values[col_name] = table_widget.item(selected_row, col_idx).text()

        input_dialog = RecordInputDialog(columns, current_values, exclude=[primary_key])
        if input_dialog.exec():
            new_values = input_dialog.get_values()
            set_clause = ', '.join([f"{k}=?" for k in new_values.keys()])
            try:
                cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE {primary_key} = ?", (*new_values.values(), record_id))
                self.conn.commit()
                self.load_data(table_widget, table_name)
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



class SQLQueryDialog(QDialog):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("SQL Query Tester")
        self.setGeometry(300, 200, 800, 600)

        # Main splitter (horizontal)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Database browser (QTreeWidget)
        self.db_tree = QTreeWidget(self)
        self.db_tree.setHeaderLabel("Database Structure")
        self.populate_db_tree()
        self.db_tree.itemDoubleClicked.connect(self.insert_column_into_query)

        # Add the DB tree to the left side of the splitter
        self.main_splitter.addWidget(self.db_tree)

        # Vertical splitter for query editor and result
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)

        # Query editor (Top Section)
        self.query_editor = QTextEdit(self)
        self.query_editor.setPlaceholderText("Type your SQL query here...")
        self.vertical_splitter.addWidget(self.query_editor)

        # Query results table (Bottom Section)
        self.query_results = QTableWidget(self)
        self.vertical_splitter.addWidget(self.query_results)

        # Add vertical splitter to the right side of the main splitter
        self.main_splitter.addWidget(self.vertical_splitter)

        # Layout setup
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.main_splitter)

        # Buttons (Run and Clear)
        self.button_layout = QHBoxLayout()
        self.run_button = QPushButton("Run Query")
        self.clear_button = QPushButton("Clear")
        self.button_layout.addWidget(self.run_button)
        self.button_layout.addWidget(self.clear_button)
        self.layout.addLayout(self.button_layout)

        self.setLayout(self.layout)

        # Connect buttons to their actions
        self.run_button.clicked.connect(self.run_query)
        self.clear_button.clicked.connect(self.clear_query)

    def populate_db_tree(self):
        """Populate the tree with tables, views, and columns from the SQLite database."""
        cursor = self.conn.cursor()

        # First, add the 'device_details' view as the top item
        view_item = QTreeWidgetItem(self.db_tree)
        view_item.setText(0, 'device_details')

        # Fetch columns for the view
        cursor.execute("PRAGMA table_info(devices)")  # Assuming 'device_details' uses the devices table
        columns = cursor.fetchall()
        for column in columns:
            column_name = column[1]
            column_item = QTreeWidgetItem(view_item)
            column_item.setText(0, column_name)

        # Get the list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]

            # Create a root node for each table
            table_item = QTreeWidgetItem(self.db_tree)
            table_item.setText(0, table_name)

            # Get the columns of the table
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            for column in columns:
                column_name = column[1]  # Column name is in the second position
                column_item = QTreeWidgetItem(table_item)
                column_item.setText(0, column_name)

        self.db_tree.expandAll()
    def insert_column_into_query(self, item, column):
        """Insert the selected column (or table) into the query editor."""
        text = item.text(0)

        # Check if the item is a column or table (leaf or root node)
        if item.parent():
            # It's a column, insert as `table.column`
            table_name = item.parent().text(0)
            self.query_editor.insertPlainText(f"{table_name}.{text}")
        else:
            # It's a table, insert the table name
            self.query_editor.insertPlainText(f"{text}")

    def run_query(self):
        """Run the SQL query typed by the user and display results in the table."""
        query = self.query_editor.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "No Query", "Please enter a SQL query to run.")
            return

        cursor = self.conn.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            # Set up the table with query results
            self.query_results.setRowCount(len(rows))
            self.query_results.setColumnCount(len(columns))
            self.query_results.setHorizontalHeaderLabels(columns)

            for row_idx, row_data in enumerate(rows):
                for col_idx, col_data in enumerate(row_data):
                    self.query_results.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))

        except sqlite3.Error as e:
            QMessageBox.critical(self, "SQL Error", f"Error executing query: {e}")

    def clear_query(self):
        """Clear the query editor and results table."""
        self.query_editor.clear()
        self.query_results.clearContents()
        self.query_results.setRowCount(0)
        self.query_results.setColumnCount(0)

class RecordInputDialog(QMessageBox):
    def __init__(self, columns, current_values=None, exclude=None):
        super().__init__()
        self.setWindowTitle("Record Input")
        self.setModal(True)
        self.columns = [col for col in columns if not exclude or col not in exclude]
        self.inputs = {}
        self.current_values = current_values or {}

        # Layout setup
        self.layout = QVBoxLayout()
        self.form_layout = QHBoxLayout()

        for column in self.columns:
            label = QPushButton(column.capitalize())
            label.setEnabled(False)  # Disable the button to act as a label
            input_field = QLineEdit()
            input_field.setText(self.current_values.get(column, ""))
            self.inputs[column] = input_field

            self.form_layout.addWidget(label)
            self.form_layout.addWidget(input_field)

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
        self.setLayout(self.layout)

    def get_values(self):
        return {col: self.inputs[col].text() for col in self.columns}

def create_sqlite_db(yaml_file, db_file = ':memory:'):
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

def main():
    app = QApplication(sys.argv)
    window = CRUDWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
