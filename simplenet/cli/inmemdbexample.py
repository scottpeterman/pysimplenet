import click
import sqlite3
from ruamel.yaml import YAML as yaml

def create_in_memory_db(yaml_file):
    """
    Create an in-memory SQLite database from a YAML file.

    Args:
        yaml_file (str): Path to the YAML file containing the inventory.

    Returns:
        sqlite3.Connection: SQLite connection object to the in-memory database.
    """
    conn = sqlite3.connect(':memory:')
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

    # Load YAML data
    with open(yaml_file, 'r') as file:
        data = yaml.safe_load(file)

    # Insert data into tables
    for device in data['devices']:
        c.execute('''INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (device['id'], device['hostname'], device['mgmt_ip'], device['model'],
                   device['serial_number'], device['timestamp'], device['platform_id'],
                   device['role_id'], device['site_id'], device['vendor_id']))
        for cred_id in device['credential_ids']:
            c.execute('INSERT INTO device_credentials VALUES (?, ?)', (device['id'], cred_id))

    for cred in data['credentials']:
        c.execute('INSERT INTO credentials VALUES (?, ?, ?, ?)', (cred['id'], cred['name'], cred['username'], cred['password']))

    for platform in data['platforms']:
        c.execute('INSERT INTO platforms VALUES (?, ?)', (platform['id'], platform['name']))

    for role in data['roles']:
        c.execute('INSERT INTO roles VALUES (?, ?)', (role['id'], role['name']))

    for site in data['sites']:
        c.execute('INSERT INTO sites VALUES (?, ?, ?)', (site['id'], site['name'], site['location']))

    for vendor in data['vendors']:
        c.execute('INSERT INTO vendors VALUES (?, ?)', (vendor['id'], vendor['name']))

    # Create a view that joins devices with related tables
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

    conn.commit()
    return conn

@click.command()
@click.option('--yaml-path', required=True, help='Path to the YAML file containing the inventory.')
@click.option('--query', required=True, help='SQL query to execute on the inventory data.')
def query_yaml(yaml_path, query):
    """
    Command-line tool to query YAML inventory data using SQL.
    """
    try:
        # Create an in-memory SQLite database from the YAML file
        conn = create_in_memory_db(yaml_path)
        cursor = conn.cursor()

        # Execute the provided SQL query
        cursor.execute(query)
        results = cursor.fetchall()

        # Print the results
        if results:
            for row in results:
                print(row)
        else:
            print("No results found for the given query.")

    except Exception as e:
        print(f"Error occurred: {str(e)}")

    finally:
        conn.close()

if __name__ == '__main__':
    query_yaml()
