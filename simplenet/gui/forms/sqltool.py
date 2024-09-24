import sys
import sqlite3
from ruamel.yaml import YAML
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QSplitter, QTreeWidget, QTextEdit,
                             QTableWidget, QHBoxLayout, QPushButton, QFileDialog, QMessageBox,
                             QTreeWidgetItem, QTableWidgetItem)


class SQLQueryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.conn = None  # SQLite connection
        self.setWindowTitle("SQL Query Tester")
        self.setGeometry(300, 200, 1000, 700)

        # Main layout
        self.layout = QVBoxLayout()
        self.init_toolbar()

        # Main splitter (horizontal)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Database browser (QTreeWidget)
        self.db_tree = QTreeWidget(self)
        self.db_tree.setHeaderLabel("Database Structure")
        self.db_tree.itemDoubleClicked.connect(self.insert_column_into_query)
        self.main_splitter.addWidget(self.db_tree)

        # Vertical splitter for query editor and results
        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)

        # Query editor
        self.query_editor = QTextEdit(self)
        self.query_editor.setPlaceholderText("Type your SQL query here...")
        self.vertical_splitter.addWidget(self.query_editor)

        # Query results table
        self.query_results = QTableWidget(self)
        self.vertical_splitter.addWidget(self.query_results)

        # Add vertical splitter to the right side of the main splitter
        self.main_splitter.addWidget(self.vertical_splitter)
        self.layout.addWidget(self.main_splitter)

        self.setLayout(self.layout)

    def init_toolbar(self):
        toolbar_layout = QHBoxLayout()

        # Button to open YAML file
        open_yaml_button = QPushButton("Open YAML", self)
        open_yaml_button.clicked.connect(self.open_yaml)
        toolbar_layout.addWidget(open_yaml_button)

        # Button to run query
        run_query_button = QPushButton("Run Query", self)
        run_query_button.clicked.connect(self.run_query)
        toolbar_layout.addWidget(run_query_button)

        # Button to clear query and results
        clear_button = QPushButton("Clear", self)
        clear_button.clicked.connect(self.clear_query)
        toolbar_layout.addWidget(clear_button)

        # Add stretch to push buttons to the left
        toolbar_layout.addStretch()

        self.layout.addLayout(toolbar_layout)

    def open_yaml(self):
        """Open a YAML file and load it into an in-memory SQLite database."""
        options = QFileDialog.Option.ReadOnly
        yaml_file, _ = QFileDialog.getOpenFileName(self, "Open YAML File", "", "YAML Files (*.yaml *.yml)",
                                                   options=options)

        if yaml_file:
            try:
                self.conn = self.create_sqlite_db(yaml_file)
                self.populate_db_tree()
                QMessageBox.information(self, "Success", f"Loaded YAML and created in-memory database.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load YAML: {e}")

    def populate_db_tree(self):
        """Populate the tree with tables and columns from the SQLite database."""
        if not self.conn:
            return

        cursor = self.conn.cursor()
        self.db_tree.clear()

        # Get the list of tables and views
        cursor.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';")
        objects = cursor.fetchall()

        for obj_name, obj_type in objects:
            root_item = QTreeWidgetItem(self.db_tree)
            root_item.setText(0, obj_name)

            # Get the columns of the table or view
            cursor.execute(f"PRAGMA table_info({obj_name})")
            columns = cursor.fetchall()

            for column in columns:
                column_name = column[1]
                column_item = QTreeWidgetItem(root_item)
                column_item.setText(0, column_name)

        self.db_tree.expandAll()

    def insert_column_into_query(self, item, column):
        """Insert the selected column (or table) into the query editor."""
        text = item.text(0)

        # Check if the item is a column or table/view (leaf or root node)
        if item.parent():
            table_name = item.parent().text(0)
            self.query_editor.insertPlainText(f"{table_name}.{text}")
        else:
            self.query_editor.insertPlainText(f"{text}")

    def run_query(self):
        """Run the SQL query typed by the user and display results in the table."""
        if not self.conn:
            QMessageBox.warning(self, "No Database", "Please load a YAML file to create a database first.")
            return

        query = self.query_editor.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "No Query", "Please enter a SQL query to run.")
            return

        cursor = self.conn.cursor()
        try:
            cursor.execute(query)
            if query.lower().startswith("select"):
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

                self.query_results.setRowCount(len(rows))
                self.query_results.setColumnCount(len(columns))
                self.query_results.setHorizontalHeaderLabels(columns)

                for row_idx, row_data in enumerate(rows):
                    for col_idx, col_data in enumerate(row_data):
                        self.query_results.setItem(row_idx, col_idx, QTableWidgetItem(str(col_data)))
            else:
                self.conn.commit()
                QMessageBox.information(self, "Success", "Query executed successfully.")
                self.populate_db_tree()  # Refresh the tree in case of schema changes
        except sqlite3.Error as e:
            QMessageBox.critical(self, "SQL Error", f"Error executing query: {e}")

    def clear_query(self):
        """Clear the query editor and results table."""
        self.query_editor.clear()
        self.query_results.clearContents()
        self.query_results.setRowCount(0)
        self.query_results.setColumnCount(0)

    def create_sqlite_db(self, yaml_file, db_file=':memory:'):
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
                c.execute('INSERT INTO device_credentials (device_id, credential_id) VALUES (?, ?)',
                          (device.get('id'), cred_id))

        for cred in data.get('credentials', []):
            c.execute('INSERT INTO credentials (id, name, username, password) VALUES (?, ?, ?, ?)',
                      (cred.get('id'), cred.get('name'), cred.get('username'), cred.get('password')))

        for platform in data.get('platforms', []):
            c.execute('INSERT INTO platforms (id, name) VALUES (?, ?)', (platform.get('id'), platform.get('name')))

        for role in data.get('roles', []):
            c.execute('INSERT INTO roles (id, name) VALUES (?, ?)', (role.get('id'), role.get('name')))

        for site in data.get('sites', []):
            c.execute('INSERT INTO sites (id, name, location) VALUES (?, ?, ?)',
                      (site.get('id'), site.get('name'), site.get('location')))

        for vendor in data.get('vendors', []):
            c.execute('INSERT INTO vendors (id, name) VALUES (?, ?)', (vendor.get('id'), vendor.get('name')))

        conn.commit()
        return conn


def main():
    app = QApplication(sys.argv)
    widget = SQLQueryWidget()
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
