import json
import time
import traceback

import jmespath
from colorama import Fore

from simplenet.cli.lib.audit_actions import print_pretty
from simplenet.cli.lib.utils import scrub_esc_codes, parse_output_with_ttp, log_command_output, log_command_execution, \
    dereference_placeholders

def handle_send_command_action(action_index, ssh_connection, action, resolved_vars, log_file, prompt, pretty,
                               timestamps, stop_device_commands, global_output, global_prompt_count,
                               inter_command_time, error_string, device_name, global_data_store, debug_output):
    # Set the current device to ensure global_data_store works correctly
    global_data_store.set_current_device(device_name)

    command = action.get('command') or action.get('config')
    command = dereference_placeholders(command, resolved_vars)

    if command == "\n":
        print("Enter /n sent")
        ssh_connection.send_newline(prompt, timeout=10)
        return global_output, stop_device_commands

    if debug_output:
        print(f"DEBUG: Executing command with resolved variables: {command}")

    command_lines = command.strip().split('\n')

    for line in command_lines:
        if stop_device_commands:
            break

        print_pretty(pretty, timestamps, f"Executing command: {line}", Fore.LIGHTYELLOW_EX)
        expect = action.get('expect', prompt)
        try:
            action_output = ssh_connection.send_command(line, expect, timeout=10, expect_occurrences=20)
            action_output = scrub_esc_codes(action_output, prompt)

            # Check if the error string is present in the output
            if error_string and error_string in action_output:
                print_pretty(pretty, timestamps, f"Error string '{error_string}' detected in output.", Fore.RED)
                log_command_execution(log_file, f"Error string '{error_string}' detected in output: {line}")
                stop_device_commands = True  # Optionally stop further command execution
                break  # Exit the loop early if error_string is detected

        except Exception as e:
            print_pretty(pretty, timestamps, f"Failed to execute command: {line}. Error: {e}", Fore.RED)
            log_command_execution(log_file, f"Failed to execute command: {line}. Error: {e}")
            continue

        log_command_output(log_file, line, action_output)

        if debug_output:
            print(json.dumps(dict(action), indent=2))

        # Handle output parsing with TTP if specified
        ttp_path = action.get('ttp_path', '')
        parsed_data = None
        if ttp_path:
            print(f"DEBUG: Raw output before TTP parsing:\n{action_output}")
            parsed_data = parse_output_with_ttp(ttp_path, action_output)
            print(f"DEBUG: Parsed data after TTP parsing:\n{json.dumps(parsed_data, indent=2)}")

            if parsed_data and parsed_data != [{}]:  # Check if parsed data is not an empty dictionary
                global_data_store.update(device_name, ttp_path, action_index, parsed_data)

                # Handle storing variables if 'store_query' is specified
                store_query = action.get('store_query', {})
                if store_query:
                    print(f"DEBUG: Processing store_query: {store_query}")
                    query_result = jmespath.search(store_query['query'], parsed_data)
                    print(f"DEBUG: JMESPath query result: {query_result}")
                    if query_result is not None:
                        variable_name = store_query.get('variable_name')
                        print(f"DEBUG: Variable name to store: {variable_name}")
                        if variable_name:
                            global_data_store.set_variable(variable_name, query_result)
                            sanity = global_data_store.get_variable(variable_name)
                            print(f"Stored variable '{variable_name}' with value: {query_result}")
                            print(f"Sanity check retrieved as [{sanity}]")
            else:
                print("DEBUG: TTP parsing returned an empty result. Check the TTP template and input data.")

        # Handle output file writing
        output_path = action.get('output_path')
        if output_path:
            output_mode = action.get('output_mode', 'append')
            output_mode = "w" if output_mode == "overwrite" else "a"
            output_format = action.get('output_format', 'text')

            try:
                if output_format in ['text', 'both']:
                    with open(output_path, output_mode) as f:
                        f.write(f"Command: {command}\nOutput:\n{action_output}\n\n")
                    print(f"DEBUG: Output written to {output_path}")

                if parsed_data and output_format == 'both':
                    parsed_output_path = f"{output_path}_parsed.json"
                    with open(parsed_output_path, "w") as fh:
                        fh.write(json.dumps(parsed_data, indent=2))
                    print(f"DEBUG: Parsed data written to {parsed_output_path}")
            except Exception as e:
                print(f"Unable to save files - {output_path}. Error: {e}")
                print(traceback.format_exc())
            global_output += action_output
        else:
            global_output += action_output

        # Update global prompt count and check if limit is reached
        global_prompt_count[0] += 1
        if global_prompt_count[0] >= global_prompt_count[1]:
            print_pretty(pretty, timestamps, "Prompt count reached, stopping device command execution.", Fore.YELLOW)
            stop_device_commands = True
            break

        time.sleep(inter_command_time)

    return global_output, stop_device_commands
