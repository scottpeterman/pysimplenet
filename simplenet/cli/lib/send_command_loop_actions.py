import json
import time
from pprint import pprint

import jmespath
from colorama import Fore

from simplenet.cli.lib.audit_actions import print_pretty
from simplenet.cli.lib.utils import scrub_esc_codes, parse_output_with_ttp, log_command_output, log_command_execution


def replace_custom_placeholders(template_string, variables):
    """
    Replaces custom placeholders [{ }] in the template_string with actual values from variables.

    Args:
        template_string (str): The string containing custom placeholders.
        variables (dict): A dictionary of variables to be substituted.

    Returns:
        str: The template string with placeholders replaced.
    """
    for key, value in variables.items():
        placeholder = f"[{{ {key} }}]"  # Custom tag format
        template_string = template_string.replace(placeholder, str(value))
    return template_string


def handle_send_command_loop(action_index, ssh_connection, action, resolved_vars, log_file, prompt, pretty, timestamps,
                             stop_device_commands, global_output, global_prompt_count, inter_command_time,
                             error_string, device_name, global_data_store, debug_output):
    """
    Handles the 'send_command_loop' action, sending commands in a loop using a list of values and processing outputs.
    """
    if debug_output:
        debug_global_output = dict(global_data_store)
        pprint(debug_global_output)

    # Retrieve required action details from schema (no hardcoded fields)
    variable_name = action.get('variable_name')  # Variable to retrieve from global data store
    key_to_loop = action.get('key_to_loop')  # Key within each entry to loop over
    command_template = action.get('command_template')  # Command template to be filled with data
    expect = action.get('expect', prompt)
    output_file_path = action.get('output_path', '')
    output_mode = action.get('output_mode', 'a')
    output_mode = "w" if output_mode == "overwrite" else "a"
    use_named_list = action.get('use_named_list', {})
    parse_output = action.get('parse_output', True)

    # Retrieve the list of dictionaries from the global data store
    entry_list = global_data_store.get_variable(variable_name)

    if debug_output:
        print(f"DEBUG: Retrieved entry list '{variable_name}' from global data store: {entry_list}")

    if not entry_list:
        print_pretty(pretty, timestamps, f"ERROR: No entries found for variable '{variable_name}'.", Fore.RED)
        return global_output, stop_device_commands

    # Initialize named list in global data store
    list_name = use_named_list.get('list_name')
    item_key = use_named_list.get('item_key')
    if list_name:
        named_list = global_data_store.get_variable(list_name) or []
    else:
        named_list = []

    if debug_output:
        print(f"DEBUG: Starting loop through entries: {entry_list}")

    for entry in entry_list:
        if stop_device_commands:
            break

        if key_to_loop not in entry:
            print_pretty(pretty, timestamps, f"ERROR: Key '{key_to_loop}' not found in entry: {entry}", Fore.RED)
            continue

        loop_value = entry[key_to_loop]

        # Replace the custom placeholders in the command template with the loop value, driven by schema
        command = replace_custom_placeholders(command_template, {key_to_loop: loop_value})

        print_pretty(pretty, timestamps, f"Executing command: {command}", Fore.LIGHTYELLOW_EX)

        try:
            action_output = ssh_connection.send_command(command, expect, timeout=10, expect_occurrences=20)
            action_output = scrub_esc_codes(action_output, prompt)
            print(f"DEBUG: Command execution output: {action_output}")
        except Exception as e:
            print_pretty(pretty, timestamps, f"Failed to execute command: {command}. Error: {e}", Fore.RED)
            log_command_execution(log_file, f"Failed to execute command: {command}. Error: {e}")
            continue

        log_command_output(log_file, command, action_output)

        # Apply TTP parsing if 'use_named_list' is defined and parse_output is True
        if parse_output and use_named_list:
            ttp_path = use_named_list.get('ttp_path')
            if ttp_path:
                parsed_data = parse_output_with_ttp(ttp_path, action_output)
                if parsed_data:
                    print(f"TTP Parser results:\n{json.dumps(parsed_data, indent=2)}")

                    # Always update the global data store with parsed data
                    global_data_store.update(device_name, ttp_path, action_index, parsed_data)

                    store_query = use_named_list.get('store_query')
                    if store_query:
                        query_result = jmespath.search(store_query['query'], parsed_data)
                        if query_result is not None:
                            # Append each result to the named list with the specified key from the schema
                            named_list.append({item_key: query_result})
                            print(f"Stored JMESPath query result '{query_result}' under key '{item_key}' in list '{list_name}'.")

                    # Update the named list in the global data store
                    if list_name:
                        global_data_store.set_variable(list_name, named_list)  # Correctly set the entire named list

        # Write output to file if necessary
        if output_file_path:
            try:
                with open(output_file_path, output_mode) as f:
                    f.write(f"Command: {command}\nOutput:\n{scrub_esc_codes(action_output, prompt)}\n\n")
            except Exception as e:
                print(f"Unable to save files - {output_file_path}")

        # Append to global output
        global_output += action_output

        # Update global prompt count and check if limit is reached
        global_prompt_count[0] += 1
        if global_prompt_count[0] >= global_prompt_count[1]:
            print_pretty(pretty, timestamps, "Prompt count reached, stopping device command execution.", Fore.YELLOW)
            stop_device_commands = True
            break

        # Pause between commands if required
        time.sleep(inter_command_time)

    return global_output, stop_device_commands
