import datetime
import click
import sqlite3
from ruamel.yaml import YAML
import subprocess
import sys
import os
import socket
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager


import sqlite3
import os
from ruamel.yaml import YAML


def create_sqlite_db(yaml_file, db_file):
    """
    Create a SQLite database file from a YAML file.

    Args:
        yaml_file (str): Path to the YAML file containing the inventory.
        db_file (str): Path to the SQLite database file to create.

    Returns:
        sqlite3.Connection: SQLite connection object to the created database.
    """
    try:
        # Remove the existing database file if it exists
        if os.path.exists(db_file):
            os.remove(db_file)

        # Create a new SQLite database file
        print(f"Creating new SQLite DB at {db_file}")
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

        # Load YAML data using ruamel.yaml
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True  # Preserve quotes if necessary

        with open(yaml_file, 'r') as file:
            data = yaml_loader.load(file)

        # Insert data into tables
        for device in data.get('devices', []):
            c.execute('''INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (device['id'], device['hostname'], device['mgmt_ip'], device['model'],
                       device['serial_number'], device['timestamp'], device['platform_id'],
                       device['role_id'], device['site_id'], device['vendor_id']))
            for cred_id in device.get('credential_ids', []):
                c.execute('INSERT INTO device_credentials VALUES (?, ?)', (device['id'], cred_id))

        for cred in data.get('credentials', []):
            c.execute('INSERT INTO credentials VALUES (?, ?, ?, ?)',
                      (cred['id'], cred['name'], cred['username'], cred['password']))

        for platform in data.get('platforms', []):
            c.execute('INSERT INTO platforms VALUES (?, ?)', (platform['id'], platform['name']))

        for role in data.get('roles', []):
            c.execute('INSERT INTO roles VALUES (?, ?)', (role['id'], role['name']))

        for site in data.get('sites', []):
            c.execute('INSERT INTO sites VALUES (?, ?, ?)', (site['id'], site['name'], site['location']))

        for vendor in data.get('vendors', []):
            c.execute('INSERT INTO vendors VALUES (?, ?)', (vendor['id'], vendor['name']))

        conn.commit()
        print("Database created and data inserted successfully.")
        return conn

    except sqlite3.Error as e:
        print(f"SQLite error occurred: {e}")
        return None

    except Exception as e:
        print(f"General error occurred: {e}")
        return None




def check_device_reachability(hostname):
    """
    Check if a device is reachable on port 22 (SSH).

    Args:
        hostname (str): The hostname or IP address of the device.

    Returns:
        bool: True if the device is reachable, False otherwise.
    """
    port = 22
    timeout = 10  # Timeout in seconds

    try:
        with socket.create_connection((hostname, port), timeout):
            return True
    except (socket.timeout, socket.error):
        return False


def log_message(log_file, hostname, reason):
    """
    Log a message to the specified log file.

    Args:
        log_file (str): The path to the log file.
        hostname (str): The hostname or IP address of the device.
        reason (str): The reason for the log entry.
    """
    with open(log_file, 'a') as file:
        file.write(f"{datetime.datetime.now()} - {hostname}: {reason}\n")


def run_for_device(row, db_file, driver, vars_file, driver_name, timeout, prompt, prompt_count, inter_command_time,
                   pretty, look_for_keys, timestamps, output_root, query, counters, error_log, connection_failures):
    """
    Run the new utility for a single device.

    Args:
        row: Device details from the SQL query.
        Other args are the Click parameters to pass to the new utility.
    """
    hostname = row[1]  # Assuming the hostname is the second column in the results
    mgmt_ip = row[2]
    print(f"Running tool for device: {hostname}")

    # Pre-check for device reachability on port 22
    if not check_device_reachability(mgmt_ip):
        print(f"Device {hostname}:{mgmt_ip} is not reachable on port 22.")
        log_message(connection_failures, hostname + ":" + mgmt_ip, "Unreachable on port 22")
        counters['failed'] += 1  # Increment failed counter
        return

    # Construct the command to run the utility
    cmd = [
        sys.executable, '-u', '-m', 'simplenet.cli.simplenet',
        '--inventory', db_file,
        '--query', f"select * from devices where hostname = '{hostname}'",
        '--driver', driver,
        '--driver-name', driver_name,
        '--timeout', str(timeout),
        '--prompt', prompt,
        '--prompt-count', str(prompt_count),
        '--inter-command-time', str(inter_command_time),
        '--output-root', output_root
    ]

    # Optional arguments
    if vars_file:
        cmd.extend(['--vars', vars_file])
    if pretty:
        cmd.append('--pretty')
    if look_for_keys:
        cmd.append('--look-for-keys')
    if timestamps:
        cmd.append('--timestamps')

    # Run the command and capture stdout/stderr
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    # Stream the output line by line
    for line in iter(process.stdout.readline, ''):
        print(line, end='')

    process.stdout.close()
    exit_code = process.wait()

    # Check for non-zero exit code and log it
    if exit_code != 0:
        print(f"Device {hostname} returned a non-zero exit code: {exit_code}")
        log_message(error_log, hostname, f"Non-zero exit code: {exit_code}")
        counters['failed'] += 1  # Increment failed counter
    else:
        counters['processed'] += 1  # Increment processed counter

    print(f"\n{'=' * 50}\nCompleted tool run for device: {hostname}\n{'=' * 50}\n")


@click.command()
@click.option('--inventory', required=True, help='Path to the YAML file containing the inventory.')
@click.option('--query', required=True, help='SQL query to execute on the inventory data.')
@click.option('--driver', required=True, help='Path to the driver YAML file.')
@click.option('--vars', required=False, help='Path to the variables YAML file.')
@click.option('--driver-name', default='cisco_ios', help='Driver name to use [default=cisco_ios].')
@click.option('--timeout', default=10, help='Command timeout in seconds [default=10].')
@click.option('--prompt', default='', help='Prompt to look for.')
@click.option('--prompt-count', default=1, help='Number of prompts to expect [default=1].')
@click.option('--look-for-keys', is_flag=True, help='Look for SSH keys for authentication.')
@click.option('--timestamps', is_flag=True, help='Add timestamps to output.')
@click.option('--inter-command-time', default=1.0, help='Time to wait between commands [default=1.0].')
@click.option('--pretty', is_flag=True, help='Enable pretty output.')
@click.option('--output-root', default='./output', help='Root directory for all output files [default=./output].')
@click.option('--num-processes', default=4, help='Number of processes to run concurrently [default=4].')
def query_yaml(inventory, query, driver, vars, driver_name, timeout, prompt, prompt_count, look_for_keys, timestamps,
               inter_command_time, pretty, output_root, num_processes):
    """
    Command-line tool to query YAML inventory data using SQL and execute commands for matching devices.
    """
    db_file = inventory.replace('.yaml', '.db')
    conn = None

    # Start time
    start_time = datetime.datetime.now()
    print(f"Processing started at: {start_time}")

    # Load driver logging paths from the YAML configuration
    yaml_loader = YAML()
    yaml_loader.preserve_quotes = True

    with open(driver, 'r') as f:
        driver_config = yaml_loader.load(f)

    error_log = "error.log"
    connection_failures = "connection_failures.log"

    # Initialize counters using Manager for thread-safe operations
    with Manager() as manager:
        counters = manager.dict()
        counters['processed'] = 0
        counters['failed'] = 0

        try:
            # Create a SQLite database file from the YAML file
            conn = create_sqlite_db(inventory, db_file)
            cursor = conn.cursor()

            # Execute the provided SQL query
            cursor.execute(query)
            results = cursor.fetchall()

            # If results found, run the utility for each matching device using concurrency
            if results:
                print(f"Devices matching query: {query}")

                # Use ProcessPoolExecutor for concurrency
                with ProcessPoolExecutor(max_workers=num_processes) as executor:
                    futures = {executor.submit(run_for_device, row, db_file, driver, vars, driver_name, timeout, prompt,
                                               prompt_count, inter_command_time, pretty, look_for_keys, timestamps,
                                               output_root, query, counters, error_log, connection_failures): row for row in results}

                    for future in as_completed(futures):
                        try:
                            future.result()  # Block until each future completes
                        except Exception as e:
                            print(f"Error occurred: {str(e)}")

                # Stop time
                stop_time = datetime.datetime.now()
                print(f"Processing stopped at: {stop_time}")

                # Calculate total execution time
                total_execution_time = stop_time - start_time

                # Format the total execution time as hh:mm:ss
                formatted_total_time = str(total_execution_time)

                # Display summary
                print(f"Devices processed: {counters['processed']}")
                print(f"Failed devices: {counters['failed']}")
                print(f"Start time: {start_time}")
                print(f"Stop time: {stop_time}")
                print(f"Total execution time: {formatted_total_time}")
            else:
                print("No results found for the given query.")

        except Exception as e:
            print(f"Error occurred: {str(e)}")

        finally:
            if conn:
                conn.close()


if __name__ == '__main__':
    query_yaml()
