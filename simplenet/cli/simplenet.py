from pprint import pprint
from ruamel.yaml import YAML
import click
import os
import logging
import traceback
from jinja2 import Template
import sqlite3

from simplenet.cli.data_store_broke import GlobalDataStoreWrapper as GlobalDataStore
from simplenet.cli.ssh_utils import ThreadSafeSSHConnection
from simplenet.cli.command_executor2 import execute_commands

# Configure logging
logging.basicConfig(filename='automation.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def load_variables_and_render_driver(vars_file, driver_file, device_info):
    """
    Load variables from a file and render the driver file with these variables.

    Args:
        vars_file (str): Path to the YAML file containing variables, or None.
        driver_file (str): Path to the driver YAML file.
        device_info (tuple): A tuple containing (hostname, mgmt_ip) for the device.

    Returns:
        tuple: (variables, driver_data)
    """
    yaml_loader = YAML()
    yaml_loader.preserve_quotes = True  # Preserve quotes if necessary

    if vars_file:
        with open(vars_file, 'r') as f:
            variables = yaml_loader.load(f)
    else:
        variables = {}

    hostname, mgmt_ip = device_info
    variables.update({'hostname': hostname, 'mgmt_ip': mgmt_ip})

    with open(driver_file, 'r') as f:
        driver_template = f.read()

    template = Template(driver_template)
    rendered_driver = template.render(variables)
    driver_data = yaml_loader.load(rendered_driver)

    return variables, driver_data

def get_device_credentials(device_id, db_conn):
    """
    Retrieve the credentials for a given device based on its credential_ids.

    Args:
        device_id (int): Device ID to look up credentials for.
        db_conn (sqlite3.Connection): Connection to the SQLite database.

    Returns:
        tuple: (username, password) for the device, or (None, None) if not found.
    """
    cursor = db_conn.cursor()

    cursor.execute('''
        SELECT username, password 
        FROM credentials 
        WHERE id IN (SELECT credential_id FROM device_credentials WHERE device_id = ?)
    ''', (device_id,))

    credential = cursor.fetchone()

    if credential:
        return credential[0], credential[1]

    return None, None

def run_automation_for_device(device, driver_file, vars_file, driver_name, db_conn, global_data_store, **kwargs):
    """
    Execute automation tasks for a single device.

    Args:
        device (sqlite3.Row): Device information retrieved from the SQLite database.
        driver_file (str): Path to the driver YAML file.
        vars_file (str): Path to the variables YAML file.
        driver_name (str): Name of the driver.
        db_conn (sqlite3.Connection): Connection to the SQLite database.
        global_data_store (GlobalDataStore): Instance of the global data store.
    """
    hostname = device['hostname']
    mgmt_ip = device['mgmt_ip']
    print(f"Run automation for device {hostname}")

    try:
        # Retrieve credentials for the device
        username, password = get_device_credentials(device['id'], db_conn)
        if not username or not password:
            print(f"Error: No credentials found for device {hostname}")
            return

        ssh_conn = ThreadSafeSSHConnection(
            hostname=mgmt_ip,
            debug=True,
            look_for_keys=kwargs.get('look_for_keys', False),
            timeout=kwargs.get('timeout', 10),
            allow_agent=False,
            prompt_failure=False,
            scrub_esc=True
        )

        ssh_conn.set_displayname(hostname)

        try:
            ssh_conn.connect(username=username, password=password)
        except Exception as e:
            print(f"Connection failure: {hostname}:{mgmt_ip}")
            return

        variables, driver_data = load_variables_and_render_driver(vars_file, driver_file, (hostname, mgmt_ip))
        ssh_conn.channel.hostname = hostname
        actions = driver_data['drivers'][driver_name]['actions']
        error_string = driver_data['drivers'][driver_name].get('error_string', '')
        global_prompt_count = [0, kwargs.get('prompt_count', 1)]

        # Execute commands
        execute_commands(
            ssh_connection=ssh_conn,
            actions=actions,
            variables=variables,
            inter_command_time=kwargs.get('inter_command_time', 1),
            log_file=f"./log/{hostname}.log",
            error_string=error_string,
            global_output_path=kwargs.get('global_output_path', 'output'),
            global_output_mode=kwargs.get('global_output_mode', 'overwrite'),
            prompt=kwargs.get('prompt', ''),
            global_prompt_count=global_prompt_count,
            global_data_store=global_data_store,
            pretty=kwargs.get('pretty', False),
            global_audit={},
            timestamps=kwargs.get('timestamps', False),
            timeout=kwargs.get('timeout', 10),
            max_polls=kwargs.get('max_polls', 10),
            buffer_lock=None
        )

        ssh_conn.disconnect()
        print(f"Device {hostname} completed successfully")

    except Exception as e:
        print(f"Error during execution for device {hostname}: {str(e)}")
        traceback.print_exc()

@click.command()
@click.option('--inventory', required=True, help='Path to the inventory SQLite file')
@click.option('--query', required=True, help='SQL query string to filter devices')
@click.option('--driver', required=True, help='Path to the driver YAML file')
@click.option('--vars', required=False, help='Path to the variables YAML file')
@click.option('--driver-name', default='cisco_ios', help='Driver name to use [default=cisco_ios]')
@click.option('--pretty', is_flag=True, help='Enable pretty output')
@click.option('--timeout', default=10, help='Command timeout in seconds [default=10]')
@click.option('--prompt', default='', help='Prompt to look for')
@click.option('--prompt-count', default=1, help='Number of prompts to expect [default=1]')
@click.option('--look-for-keys', is_flag=True, help='Look for SSH keys for authentication')
@click.option('--timestamps', is_flag=True, help='Add timestamps to output')
@click.option('--inter-command-time', default=1.0, help='Time to wait between commands [default=1.0]')
@click.option('--output-root', default='./output', help='Root directory for all output files [default=./output]')
def main(inventory, query, driver, vars, driver_name, pretty, timeout, prompt, prompt_count,
         look_for_keys, timestamps, inter_command_time, output_root):
    """Single-device automation based on inventory."""
    try:
        # Connect to the SQLite database
        db_conn = sqlite3.connect(inventory)
        db_conn.row_factory = sqlite3.Row

        # Apply the SQL query string to filter devices
        cursor = db_conn.cursor()
        cursor.execute(query)
        filtered_devices = cursor.fetchall()

        if not filtered_devices:
            print("No devices found matching the query.")
            return

        # Ensure output and log directories exist
        os.makedirs(output_root, exist_ok=True)
        os.makedirs('./log', exist_ok=True)

        # Initialize the global data store
        global_operation_store = GlobalDataStore()

        # Process each filtered device
        for device in filtered_devices:
            run_automation_for_device(
                device, driver, vars, driver_name,
                db_conn=db_conn,
                global_data_store=global_operation_store,
                pretty=pretty,
                timeout=timeout,
                prompt=prompt,
                prompt_count=prompt_count,
                look_for_keys=look_for_keys,
                timestamps=timestamps,
                inter_command_time=inter_command_time,
                global_output_path=output_root,
                global_output_mode='overwrite'
            )

        # pprint(global_operation_store.get_all_data())

    except Exception as e:
        logging.critical(f"Unhandled exception: {str(e)}", exc_info=True)
        traceback.print_exc()

    finally:
        try:
            db_conn.close()
        except:
            pass

if __name__ == '__main__':
    main()
