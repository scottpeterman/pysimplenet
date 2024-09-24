import json
import os
import subprocess
import sys
import traceback

from ruamel.yaml import YAML as yaml
from PyQt6.QtCore import pyqtSignal
from colorama import Fore, init
import time

from simplenet.cli.lib.audit_loop_actions import handle_audit_action_loop
from simplenet.cli.lib.config_actions import execute_send_config
from simplenet.cli.lib.handle_restapi import handle_rest_api_action
from simplenet.cli.lib.handle_restapi_loop import handle_rest_api_loop
from simplenet.cli.lib.handle_send_config_loop import handle_send_config_loop
from simplenet.cli.lib.send_commands_action import handle_send_command_action
from simplenet.cli.lib.audit_actions import print_pretty, handle_audit_action, \
    handle_print_audit_action
from simplenet.cli.lib.utils import check_run_if_condition, resolve_action_vars, resolve_template_vars
from simplenet.cli.ssh_utils import ThreadSafeSSHConnection
from simplenet.cli.lib.send_command_loop_actions import handle_send_command_loop


debug_output = True

audit_report = []

mode_mapping = {
    'overwrite': 'w',
    'append': 'a',
    'read': 'r',
    # Add more mappings as needed
}

def execute_commands(ssh_connection: ThreadSafeSSHConnection, actions, variables, inter_command_time, log_file, error_string,
                     global_output_path, global_output_mode, prompt, buffer_lock, global_prompt_count,
                     pretty=False, global_audit=None, timestamps=False, global_data_store=None, timeout=10, max_polls=10, automation_wrapper = None):

    # Debug prints to show the initial parameters
    if debug_output:
        print(f"DEBUG: Received Parameters in execute_commands:")
        print(f"  prompt: {prompt}")
        print(f"  global_prompt_count: {global_prompt_count}")
        print(f"  inter_command_time: {inter_command_time}")
        print(f"  timeout: {timeout}")
        print(f"  pretty: {pretty}")
        print(f"  timestamps: {timestamps}")
        print(f"  log_file: {log_file}")
        print(f"  error_string: {error_string}")
        print(f"  global_output_path: {global_output_path}")
        print(f"  global_output_mode: {global_output_mode}")
    device_name = variables.get('hostname','not_provided')
    global_data_store.set_current_device(device_name)  # Set the current device at the start of command execution
    audit_result = None
    audit_data_received = pyqtSignal(str)
    # hostname = variables.get('hostname','unknown')

    if pretty:
        init(autoreset=True)

    global_output = ""
    stop_device_commands = False
    actions_skipped_due_to_prompt_count = False

    action_index = 0
    resolved_vars = {}

    while action_index < len(actions):
        action = actions[action_index]  # Remove deepcopy to avoid unintended behavior.
        print(action)
        # Debugging Global Data Store
        if debug_output:
            print(global_data_store.get_all_data())  # Use get_all_data() method instead of dict conversion

        # Check if run_if is present and has a check_type
        if 'run_if' in action and action['run_if'].get('check_type') not in [None, ""]:
            audit_context = {
                'global_data_store': global_data_store,
                'current_device_name': variables['hostname'],
                'all_devices': global_data_store.get_all_data(),
                'current_device': global_data_store.get_device_data(variables['hostname'])
            }
            if not check_run_if_condition(audit_context, action['run_if']):
                print_pretty(pretty, timestamps, f"Skipping action {action['action']} due to run_if condition.",
                             Fore.YELLOW)
                action_index += 1
                continue

        if global_prompt_count[0] >= global_prompt_count[1]:
            print_pretty(pretty, timestamps, "Prompt count reached, stopping device command execution.", Fore.YELLOW)
            stop_device_commands = True
            actions_skipped_due_to_prompt_count = True
            break  # Exit the loop as no further actions should be processed.

        # Handle 'sleep' action
        if action['action'] == 'sleep':
            sleep_seconds = action.get('seconds', 1)
            print_pretty(pretty, timestamps, f"Sleeping for {sleep_seconds} seconds.", Fore.CYAN)
            time.sleep(sleep_seconds)
            action_index += 1
            continue

        # need load_vars_file, put_vars_files
        # Handle 'python_script' action
        if action['action'] == 'python_script':
            use_parent_path = action.get('use_parent_path', False)

            # Use sys.executable if use_parent_path is True, to use the same venv as the main app
            if use_parent_path:
                path_to_python = sys.executable
            else:
                path_to_python = action.get('path_to_python')

            path_to_script = action.get('path_to_script')
            arguments_string = action.get('arguments_string', '')
            log_file = action.get('log_file')

            # Check for missing required fields
            if not path_to_python or not path_to_script:
                print_pretty(pretty, timestamps, "ERROR: Missing path_to_python or path_to_script.", Fore.RED)
                action_index += 1
                continue

            if not log_file:
                print_pretty(pretty, timestamps, "ERROR: log_file is missing.", Fore.RED)
                action_index += 1
                continue

            # Construct command to execute
            command = [path_to_python, path_to_script] + arguments_string.split()

            # Print command execution details
            print_pretty(pretty, timestamps, f"Executing Python script: {' '.join(command)}", Fore.CYAN)

            try:
                # Run the subprocess and capture both stdout and stderr
                result = subprocess.run(command, capture_output=True, text=True, check=True)

                # Print the output to the console
                print_pretty(pretty, timestamps, f"Script output: {result.stdout}", Fore.GREEN)
                print_pretty(pretty, timestamps, f"Script errors: {result.stderr}", Fore.RED)

                # Write the output and errors to the log file
                with open(log_file, 'a') as f:
                    f.write(f"Script output: {result.stdout}\n")
                    f.write(f"Script errors: {result.stderr}\n")
                    f.flush()

            except subprocess.CalledProcessError as e:
                # Handle script execution failure
                print_pretty(pretty, timestamps, f"Script execution failed with error: {e}", Fore.RED)
                if e.stderr:
                    print_pretty(pretty, timestamps, f"Script stderr: {e.stderr}", Fore.RED)

                # Log the error to the log file
                with open(log_file, 'a') as f:
                    f.write(f"Script execution failed with error: {e}\n")
                    if e.stderr:
                        f.write(f"Script stderr: {e.stderr}\n")
                    f.flush()

            # Move to the next action
            action_index += 1
            continue

        # Handle 'send_config' action
        if action['action'] == 'send_config' and not stop_device_commands:
            resolved_vars = resolve_action_vars(action, global_data_store.get_all_data())
            execute_send_config(ssh_connection, action, resolved_vars, log_file, prompt, pretty, timestamps,
                                stop_device_commands, global_output, global_prompt_count, inter_command_time,
                                error_string=error_string)
            action_index += 1
            continue

        if action['action'] == 'send_config_loop' and not stop_device_commands:
            global_output, stop_device_commands = handle_send_config_loop(
                action_index, ssh_connection, action, resolved_vars, log_file, prompt, pretty, timestamps,
                stop_device_commands, global_output, global_prompt_count, inter_command_time,
                error_string, device_name, global_data_store, debug_output
            )
            action_index += 1
            global_data_store.signal_global_data_updated.emit(json.dumps(global_data_store.get_all_data(), indent=2))
            continue
        # Handle 'send_command' action
            # Handle 'send_command' action

        if (action['action'] == 'rest_api') and not stop_device_commands:
            global_output, stop_device_commands = handle_rest_api_action(
                action, resolved_vars, log_file, pretty, timestamps, stop_device_commands,
                global_output, error_string, global_data_store, debug_output
            )
            action_index += 1
            global_data_store.signal_global_data_updated.emit(json.dumps(global_data_store.get_all_data(), indent=2))

            continue

        if (action['action'] == 'rest_api_loop') and not stop_device_commands:
            global_output, stop_device_commands = handle_rest_api_loop(
                action_index, action, resolved_vars, log_file, pretty, timestamps, stop_device_commands,
                global_output, global_prompt_count, inter_command_time, error_string, device_name,
                global_data_store, debug_output
            )
            action_index += 1
            global_data_store.signal_global_data_updated.emit(json.dumps(global_data_store.get_all_data(), indent=2))
            continue

        if (action['action'] == 'send_command') and not stop_device_commands:
            global_output, stop_device_commands = handle_send_command_action(action_index,
                ssh_connection, action, resolved_vars, log_file, prompt, pretty, timestamps,
                stop_device_commands, global_output, global_prompt_count, inter_command_time,
                error_string, device_name, global_data_store, debug_output
            )
            action_index += 1
            global_data_store.signal_global_data_updated.emit(json.dumps(global_data_store.get_all_data(), indent=2))

            continue

        # Handle 'send_command_loop' action
        if action['action'] == 'send_command_loop' and not stop_device_commands:
            global_output, stop_device_commands = handle_send_command_loop(
                action_index, ssh_connection, action, resolved_vars, log_file, prompt, pretty, timestamps,
                stop_device_commands, global_output, global_prompt_count, inter_command_time,
                error_string, device_name, global_data_store, debug_output
            )
            action_index += 1
            global_data_store.signal_global_data_updated.emit(json.dumps(global_data_store.get_all_data(), indent=2))
            continue

        # Handle 'audit' action
        if action['action'] == 'audit':
            audit_result = handle_audit_action(action, global_data_store, global_audit, pretty, timestamps)
            # Emit signal to update the GUI
            global_data_store.signal_global_data_updated.emit(json.dumps(audit_result, indent=2))
            automation_wrapper.emit_audit_result(json.dumps(audit_result, indent=2))

            action_index += 1
            continue
            # Handle 'print_audit' action
        try:
            if action['action'] == 'audit_loop':
                handle_audit_action_loop(
                    action=action,
                    global_data_store=global_data_store,
                    global_audit=global_audit,
                    pretty=pretty,
                    timestamps=timestamps,
                    debug_output=debug_output,
                    variables=variables
                )
                # Optionally emit signals if using PyQt6
                global_data_store.signal_global_data_updated.emit(json.dumps(global_audit, indent=2))
                if automation_wrapper:
                    automation_wrapper.emit_audit_result(json.dumps(global_audit, indent=2))
                action_index += 1
                continue
        except Exception as e:
            print(f"Error executing handle_audit_action_loop {e}")
            traceback.print_exc()
            continue


        if action['action'] == 'print_audit':
            handle_print_audit_action(action, global_audit, pretty, timestamps)
            action_index += 1
            continue

        if action['action'] == 'dump_datastore':
            print("DEBUG: Processing 'dump_datastore' action")
            format_type = action.get('format', 'json').lower()
            raw_output_path = action.get('output_file_path', './output-tests/cdp_one_command_datastore_output.json')

            # Resolve template variables in the output path
            output_path = resolve_template_vars(raw_output_path, variables)  # Use 'variables' for template substitution

            # Verify that output_path is a string
            if not isinstance(output_path, str):
                print_pretty(pretty, timestamps, f"Resolved output_path is not a string: {output_path}", Fore.RED)
                action_index += 1
                continue

            output_as = action.get('output_as', 'json').lower()
            output_mode = action.get('output_mode', 'w')  # Ensure 'output_mode' is retrieved

            if debug_output:
                print(f"DEBUG: Dumping datastore as {format_type} to {output_path}")

            try:
                # Retrieve all data from the global data store
                data = global_data_store.get_all_data()

                # Serialize data based on the specified format
                if format_type == 'json':
                    serialized_data = json.dumps(data, indent=2)
                elif format_type == 'yaml':
                    serialized_data = yaml.dump(data, sort_keys=False)
                else:
                    print_pretty(pretty, timestamps, f"Unsupported format: {format_type}", Fore.RED)
                    action_index += 1
                    continue

                # Ensure the output directory exists
                output_dir = os.path.dirname(output_path)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                    print_pretty(pretty, timestamps, f"Created directory: {output_dir}", Fore.GREEN)

                # Write to file
                with open(output_path, output_mode) as f:
                    f.write(serialized_data)
                    print_pretty(pretty, timestamps, f"Datastore dumped to {output_path}", Fore.GREEN)

                # Optionally, handle 'output_as' parameter if it requires different handling
                if output_as == 'both':
                    print_pretty(pretty, timestamps, serialized_data, Fore.BLUE)

            except Exception as e:
                print_pretty(pretty, timestamps, f"Failed to dump datastore: {e}", Fore.RED)
                print(traceback.format_exc())  # Print the full traceback for debugging

            action_index += 1
            continue
        action_index += 1

    if actions_skipped_due_to_prompt_count:
        print_pretty(pretty, timestamps,
                     "WARNING: Script stopped performing device commands due to reaching the prompt count limit.",
                     Fore.YELLOW)

    return False, global_output
