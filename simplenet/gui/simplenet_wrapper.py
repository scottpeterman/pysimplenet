import logging
logging.basicConfig(level=logging.CRITICAL)
import json
import traceback

from simplenet.cli.lib.audit_loop_actions import handle_audit_action_loop
from simplenet.cli.simplenet import load_variables_and_render_driver
from simplenet.cli.command_executor2 import execute_commands
from simplenet.cli.data_store_broke import GlobalDataStoreWrapper as GlobalDataStore
from simplenet.cli.ssh_utils import ThreadSafeSSHConnection
from PyQt6.QtCore import QObject, pyqtSignal
from ruamel.yaml import YAML as yaml, YAML
from simplenet.cli.lib.audit_loop_actions import handle_audit_action_loop


class AutomationWrapper(QObject):
    # Signals to update the GUI
    progress = pyqtSignal(str)  # Signal to update progress in the GUI
    action_complete = pyqtSignal(str, str)  # Signal to indicate an action has completed
    global_data_updated = pyqtSignal()
    audit_result_received = pyqtSignal(str)  # Signal to print audit results in results view

    def __init__(self, **kwargs):
        super().__init__()
        self.params = kwargs
        self.ssh_conn = None
        self.global_data_store = GlobalDataStore()
        self.current_action_index = 0
        self.actions = []
        self.variables = {}  # Initialize an empty dictionary to store variables
        self.connected = False
        self.global_audit = {}  # Initialize global_audit here



    def emit_audit_result(self, audit_result_json):
        """
        Emit the signal to display the audit results in the results view.
        """
        self.audit_result_received.emit(audit_result_json)

    def run_automation(self):
        """
        Main method to initiate automation for a single device, designed to work with the GUI.
        """
        inventory = self.params['inventory']
        device = self.params['device']
        driver_name = self.params.get('driver_name', 'cisco_ios')
        vars_file = self.params.get('vars')

        try:
            # Load the inventory data from YAML
            with open(inventory, 'r') as file:
                yaml_loader = YAML(typ='safe')
                inventory_data = yaml_loader.load(file)

            # Run automation for the selected device
            self._run_device_automation(device, inventory_data, vars_file, driver_name)

        except Exception as e:
            self.progress.emit(f"Unhandled exception: {str(e)}")
            traceback.print_exc()

    def _run_device_automation(self, device, inventory_data, vars_file, driver_name):
        """
        Internal method to handle automation for a single device, using the existing simplenet CLI logic.
        """
        try:
            hostname = device['hostname']
            mgmt_ip = device['mgmt_ip']

            # Retrieve credentials for the device from the YAML data
            credentials = self._get_device_credentials(device, inventory_data)
            if not credentials:
                self.progress.emit(f"Error: No credentials found for device {hostname}")
                return

            username, password = credentials['username'], credentials['password']

            # Establish an SSH connection
            self.ssh_conn = ThreadSafeSSHConnection(
                hostname=mgmt_ip,
                debug=True,
                look_for_keys=self.params.get('look_for_keys', False),
                timeout=self.params.get('timeout', 10),
                allow_agent=False,
                prompt_failure=False,
                scrub_esc=True
            )

            self.ssh_conn.set_displayname(hostname)
            try:
                self.ssh_conn.connect(username=username, password=password)
                self.progress.emit(f"Connected to {hostname} ({mgmt_ip})")
                self.ssh_conn.is_connected = True
            except Exception as e:
                self.progress.emit(f"Connection failure: {hostname}:{mgmt_ip} - {str(e)}")
                return

            # Load variables and driver data
            self.variables, driver_data = load_variables_and_render_driver(vars_file, self.params['driver_file'], (hostname, mgmt_ip))
            if 'drivers' not in driver_data or driver_name not in driver_data['drivers']:
                self.progress.emit(f"Error: Driver {driver_name} not found in the loaded driver data.")
                return

            self.actions = driver_data['drivers'][driver_name].get('actions', [])


            self.progress.emit(f"Ready to start executing actions for {hostname}")

        except Exception as e:
            self.progress.emit(f"Error during execution for device {device['hostname']}: {str(e)}")
            traceback.print_exc()

    def _get_device_credentials(self, device, inventory_data):
        """
        Retrieve the device credentials from the inventory data.

        Args:
            device (dict): The device information.
            inventory_data (dict): The entire inventory data loaded from YAML.

        Returns:
            dict: The credentials dictionary containing 'username' and 'password'.
        """
        credential_ids = device.get('credential_ids', [])
        credentials_list = inventory_data.get('credentials', [])
        for cred in credentials_list:
            if cred['id'] in credential_ids:
                return cred
        return None

    def run_next_action(self):
        """
        Execute the next action in the list.
        """
        try:
            print(f"DEBUG: Current action index before execution: {self.current_action_index}")
            if self.current_action_index < len(self.actions):
                current_action = self.actions[self.current_action_index]
                print(f"DEBUG: Executing action: {current_action.get('action', 'Unknown')} at index {self.current_action_index}")
                self._execute_action(current_action)
                self.current_action_index += 1  # Increment index for next action
                print(f"DEBUG: Next action index after execution: {self.current_action_index}")
            else:
                self.progress.emit("All actions have been executed.")
                self.ssh_conn.disconnect()
                self.connected = False

        except Exception as e:
            self.progress.emit(f"Error during action execution: {str(e)}")
            traceback.print_exc()

    def _execute_action(self, action):
        """
        Execute a single action on the connected device.
        """
        try:
            action_type = action.get('action', 'Unknown')
            self.progress.emit(f"Executing action: {action_type}")

            if action_type == 'audit_loop':
                self._handle_audit_loop_action(action, self.variables)
            else:
                # Existing code for other action types
                result, output = execute_commands(
                    ssh_connection=self.ssh_conn,
                    actions=[action],
                    variables=self.variables,
                    inter_command_time=self.params.get('inter_command_time', 1),
                    log_file=f"./log/{self.ssh_conn.hostname}.log",
                    error_string=self.params.get('error_string', ''),
                    global_output_path=self.params.get('global_output_path', 'output'),
                    global_output_mode=self.params.get('global_output_mode', 'overwrite'),
                    prompt=self.params.get('prompt', ''),
                    global_prompt_count=[0, self.params.get('prompt_count', 1)],
                    global_data_store=self.global_data_store,
                    pretty=self.params.get('pretty', False),
                    global_audit=self.global_audit,  # Add this line to store audit results
                    timestamps=self.params.get('timestamps', False),
                    timeout=self.params.get('timeout', 10),
                    max_polls=self.params.get('max_polls', 10),
                    buffer_lock=None,
                    automation_wrapper=self
                )
                self.global_data_updated.emit()
                self.action_complete.emit(f"Action {action_type} completed successfully", output)

        except Exception as e:
            self.progress.emit(f"Error executing action: {str(e)}")
            traceback.print_exc()

    def _handle_audit_loop_action(self, action, variables):
        """
        Handle the execution of an 'audit_loop' action.
        """
        try:
            # Ensure global_audit exists
            if not hasattr(self, 'global_audit'):
                self.global_audit = {}

            # Execute the audit loop action
            handle_audit_action_loop(
                action=action,
                global_data_store=self.global_data_store,
                global_audit=self.global_audit,
                pretty=False,
                timestamps=False,
                debug_output=False,
                variables=variables


            )

            # Convert audit results to JSON
            audit_result_json = json.dumps(self.global_audit, indent=4)

            # Emit signal to update GUI
            self.audit_result_received.emit(audit_result_json)

            # Indicate action completion
            self.action_complete.emit(f"Action {action.get('action')} completed successfully", audit_result_json)

        except Exception as e:
            self.progress.emit(f"Error executing audit_loop action: {str(e)}")
            traceback.print_exc()
