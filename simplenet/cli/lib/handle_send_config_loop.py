# send_config_loop_actions.py

import time
import json

import jmespath
from jinja2 import Template
from colorama import Fore

from simplenet.cli.lib.audit_actions import print_pretty
from simplenet.cli.lib.utils import scrub_esc_codes, log_command_output, render_template
from simplenet.cli.lib.utils import check_run_if_condition, resolve_action_vars

def handle_send_config_loop(action_index, ssh_connection, action, resolved_vars, log_file, prompt, pretty,
                            timestamps, stop_device_commands, global_output, global_prompt_count, inter_command_time,
                            error_string, device_name, global_data_store, debug_output):
    """
    Handles the 'send_config_loop' action, sending configuration commands in a loop using a list of values.

    Args:
        action_index (int): Index of the current action in the actions list.
        ssh_connection (ThreadSafeSSHConnection): SSH connection object.
        action (dict): Action details containing the config template and loop variables.
        resolved_vars (dict): Resolved variables for substitution.
        log_file (str): Path to the log file.
        prompt (str): Device prompt to expect.
        pretty (bool): Whether to use pretty printing.
        timestamps (bool): Whether to add timestamps to the output.
        stop_device_commands (bool): Flag to stop command execution.
        global_output (str): Accumulated global output.
        global_prompt_count (list): List containing current and max prompt counts.
        inter_command_time (float): Time to wait between commands.
        error_string (str): Error string to detect.
        device_name (str): The name of the device being interacted with.
        global_data_store: A global data store object for state management.
        debug_output (bool): Flag for debugging output.
    """
    variable_name = action.get('variable_name')
    key_to_loop = action.get('key_to_loop')
    config_template = action.get('command_template') or action.get('config_template')
    expect = action.get('expect', prompt)
    output_file_path = action.get('output_path', '')
    output_mode = action.get('output_mode', 'a')
    output_mode = "w" if output_mode == "overwrite" else "a"
    parse_output = action.get('parse_output', False)  # If you want to parse outputs after config commands
    use_condition = action.get('use_condition', {})

    # Retrieve the list of dictionaries from the global data store
    entry_list = global_data_store.get_variable(variable_name)

    if debug_output:
        print(f"DEBUG: Retrieved entry list '{variable_name}' from global data store: {entry_list}")

    if not entry_list:
        print_pretty(pretty, timestamps, f"ERROR: No entries found for variable '{variable_name}'.", Fore.RED)
        return global_output, stop_device_commands

    for entry in entry_list:
        if stop_device_commands:
            break

        if key_to_loop not in entry:
            print_pretty(pretty, timestamps, f"ERROR: Key '{key_to_loop}' not found in entry: {entry}", Fore.RED)
            continue

        loop_value = entry[key_to_loop]

        # Resolve variables for the current loop iteration
        loop_vars = resolved_vars.copy()
        loop_vars.update(entry)

        # Use Jinja2 to render the config with the current value
        try:
            config_commands = render_template(config_template, loop_vars)
        except Exception as e:
            print_pretty(pretty, timestamps, f"ERROR: Failed to render config template: {e}", Fore.RED)
            continue

        # Check the condition if specified
        if use_condition:
            condition_met = check_loop_condition(use_condition, loop_vars, global_data_store, debug_output)
            if not condition_met:
                print_pretty(pretty, timestamps, f"Condition not met for {loop_value}, skipping configuration.", Fore.YELLOW)
                continue

        # Send each configuration line
        config_lines = config_commands.strip().split('\n')
        for line in config_lines:
            if stop_device_commands:
                break

            print_pretty(pretty, timestamps, f"Sending config: {line}", Fore.LIGHTYELLOW_EX)
            try:
                action_output = ssh_connection.send_command(line, expect, timeout=10)
                action_output = scrub_esc_codes(action_output, prompt)
                log_command_output(log_file, line, action_output)

                # Check for error string in output
                if error_string and error_string in action_output:
                    print_pretty(pretty, timestamps, f"ERROR detected in device response: {action_output}", Fore.RED)
                    log_command_output(log_file, f"ERROR detected in device response: {action_output}")
                    stop_device_commands = True  # Stop execution if an error is detected
                    break

            except Exception as e:
                print_pretty(pretty, timestamps, f"Failed to send config: {line}. Error: {e}", Fore.RED)
                log_command_output(log_file, f"Failed to send config: {line}. Error: {e}")
                continue

            time.sleep(inter_command_time)

            # Update global prompt count and check if limit is reached
            global_prompt_count[0] += 1
            if global_prompt_count[0] >= global_prompt_count[1]:
                print_pretty(pretty, timestamps, "Prompt count reached, stopping device command execution.", Fore.YELLOW)
                stop_device_commands = True
                break

        # Write output to file if necessary
        if output_file_path:
            try:
                with open(output_file_path, output_mode) as f:
                    f.write(f"Configuration sent for {loop_value}:\n{config_commands}\n\n")
            except Exception as e:
                print(f"Unable to save files - {output_file_path}")

    return global_output, stop_device_commands

def check_loop_condition(condition, loop_vars, global_data_store, debug_output):
    """
    Checks whether the loop condition is met for the current loop iteration.

    Args:
        condition (dict): The condition to check.
        loop_vars (dict): Variables available in the current loop iteration.
        global_data_store: Global data store for accessing stored data.
        debug_output (bool): Flag for debugging output.

    Returns:
        bool: True if condition is met, False otherwise.
    """
    condition_name = condition.get('condition_name', '')
    condition_type = condition.get('condition_type', '')
    query_template = condition.get('condition_query', '')
    operator = condition.get('operator', {})

    # Render the query with loop_vars
    try:
        query = Template(query_template).render(loop_vars)
    except Exception as e:
        print(f"DEBUG: Failed to render condition query: {e}")
        return False

    if debug_output:
        print(f"DEBUG: Evaluating condition '{condition_name}' with query '{query}'")

    # Get current device data
    current_device_data = global_data_store.get_device_data(global_data_store.current_device)
    if not current_device_data:
        print("DEBUG: No current device data found.")
        return False

    # Flatten the data for JMESPath
    flattened_data = {}
    for ttp_path, action_data in current_device_data.items():
        for action_index, parsed_data in action_data.items():
            key = ttp_path.split('/')[-1].replace('.ttp', '')
            flattened_data[key] = parsed_data

    if debug_output:
        print(f"DEBUG: Flattened data for JMESPath: {json.dumps(flattened_data, indent=2)}")

    # Perform JMESPath query
    try:
        target_value = jmespath.search(query.strip(), flattened_data)
    except jmespath.exceptions.JMESPathError as e:
        print(f"DEBUG: Error in JMESPath query '{query}': {str(e)}")
        return False

    # Evaluate the operator
    operator_type = operator.get('type')
    operator_value = operator.get('value')

    result = False
    if operator_type == 'is_equal':
        result = str(target_value) == str(operator_value)
    elif operator_type == 'string_in':
        result = operator_value in str(target_value)
    elif operator_type == 'string_not_in':
        result = operator_value not in str(target_value)
    elif operator_type == 'is_gt':
        result = float(target_value) > float(operator_value)
    elif operator_type == 'is_lt':
        result = float(target_value) < float(operator_value)
    elif operator_type == 'is_ge':
        result = float(target_value) >= float(operator_value)
    elif operator_type == 'is_le':
        result = float(target_value) <= float(operator_value)

    if debug_output:
        print(f"DEBUG: Condition '{condition_name}' evaluated to {result}")

    # Depending on condition_type, determine if we should proceed
    if condition_type == 'pass_if' and result:
        return True
    elif condition_type == 'fail_if' and result:
        return False
    elif condition_type == 'pass_if_not' and not result:
        return True
    elif condition_type == 'fail_if_not' and not result:
        return False
    else:
        return False
