import io
import logging
import subprocess
import sys
from copy import deepcopy
from pprint import pprint
from queue import Empty, Queue
from ttp import ttp
import json
from ruamel.yaml import YAML as yaml
import jmespath
from colorama import Fore, Style, init
import time
import re

from simplenet.cli.ssh_utils import ThreadSafeSSHConnection

audit_report = []

def wait_for_prompt(channel, prompt, timeout=30):
    """
    Waits for the specified prompt in the channel's output within a given timeout period.

    :param channel: The SSH channel from which to read the output.
    :param prompt: The prompt string to look for.
    :param timeout: Maximum time (in seconds) to wait for the prompt.
    :return: True if the prompt is detected within the timeout, False otherwise.
    """
    start_time = time.time()
    buffer = ""
    channel.send("\n")
    while time.time() - start_time < timeout:
        if channel.recv_ready():
            chunk = channel.recv(1024).decode('utf-8', errors='ignore')  # Ignore decoding errors
            # print(f"DEBUG: Received in wait_for_prompt: {repr(chunk)}")  # Show the exact received content
            buffer += chunk

            # Strip escape sequences and control characters from the buffer
            clean_buffer = ''.join(char for char in buffer if char.isprintable())
            # print(f"DEBUG: Clean Buffer: {repr(clean_buffer)}")  # Debug cleaned buffer

            if prompt in clean_buffer or clean_buffer.strip().endswith(prompt):
                print(f"Reader [{time.strftime('%Y-%m-%d %H:%M:%S')}] - Prompt '{prompt}' detected.")
                return True

        time.sleep(0.5)  # Adjust sleep if necessary (reduce or increase for faster polling)

    print(f"ERROR: Timed out waiting for initial prompt '{prompt}' after {timeout} seconds.")
    return False


def paced_send(channel, command, expect='#', pace=0.1, buffer_size=1024, timeout=30):
    """
    Sends a command to the SSH channel one character at a time with pacing
    and reads the output until the expected prompt or timeout.

    Parameters:
        channel: The SSH channel to send the command to.
        command: The command to be sent.
        expect: The expected prompt string that indicates command completion.
        pace: Time delay between sending each character.
        buffer_size: Size of the buffer to read from the channel.
        timeout: Maximum time to wait for the expected prompt.

    Returns:
        The full command output as a string.
    """
    # Send command character by character
    print(f"DEBUG: Sending command: {command}")
    for char in command:
        channel.send(char)
        time.sleep(pace)
    channel.send('\n')

    # Read output from the channel
    output = ''
    start_time = time.time()
    while True:
        if channel.recv_ready():
            recv = channel.recv(buffer_size).decode('utf-8')
            # print(f"DEBUG: Received chunk: {recv}")
            output += recv

        # Check if the expected prompt is in the output or if timeout is reached
        if expect in output:
            print(f"DEBUG: Expected prompt '{expect}' detected in output.")
            break
        if time.time() - start_time > timeout:
            print(f"WARNING: Timeout reached while waiting for prompt '{expect}'.")
            break
        time.sleep(0.1)  # Small sleep to avoid busy-wait

    # print(f"DEBUG: Full output received:\n{output}")
    return output

def strip_ansi_escape_codes(text):
    """
    Strips ANSI escape codes from a given string.

    Args:
        text (str): The input string containing ANSI escape codes.

    Returns:
        str: The cleaned string without ANSI escape codes.
    """
    # Regular expression pattern for matching ANSI escape codes
    ansi_escape_pattern = re.compile(r'(\x1B[@-_][0-?]*[ -/]*[@-~])')

    # Substitute the ANSI escape codes with an empty string
    cleaned_text = ansi_escape_pattern.sub('', text)

    return cleaned_text
def scrub_esc_codes(output_text, prompt):
    new_output = ""
    for line in str(output_text).splitlines():
        new_line = strip_ansi_escape_codes(line) + "\n"
        # if prompt not in line:
        new_output += new_line

    # print(f"New Output:")
    # print(new_output)
    return new_output


def send_command(channel, command, expect, output_queue, output_buffer, buffer_lock, timeout, maxpolls):
    channel.send(command + '\n')
    start_time = time.time()
    output = ""
    last_read_time = start_time
    current_polls = 0
    while time.time() - start_time < timeout:
        current_polls += 1
        print(f"polling [{current_polls}]...." + channel.hostname)
        if current_polls > maxpolls:
            if expect in output:
                print(f"DEBUG: Expected prompt found after max polls. Command completed.")
                output_queue.put("Command completed.")
                return True, scrub_esc_codes(output, expect)
            else:
                output_queue.put("DEBUG: Max polls reached, output may be incomplete.")
                return True, scrub_esc_codes(output, expect)
        if channel.recv_ready():
            chunk = channel.recv(4096).decode('utf-8')
            # print(f"DEBUG: Received chunk: {chunk}")
            output += chunk
            with buffer_lock:
                output_buffer.put(chunk)
            last_read_time = time.time()
        else:
            if expect in output:
                print(f"DEBUG: Expected prompt found. Command completed.")
                output_queue.put("Command completed.")
                return True, scrub_esc_codes(output, expect)
            elif time.time() - last_read_time > 2:
                # If no new data for 2 seconds, check if we're done
                if expect in output:
                    print(f"DEBUG: Expected prompt found after delay. Command completed.")
                    output_queue.put("Command completed.")
                    return True, scrub_esc_codes(output, expect)

            time.sleep(0.1)

    print(f"DEBUG: Timeout reached. Last output: {output[-200:]}")
    if expect in output:
        print(f"DEBUG: Expected prompt found, but timeout reached. Treating as success.")
        output_queue.put("Command completed (timeout reached).")
        return True, scrub_esc_codes(output, expect)
    else:
        output_queue.put("Timeout expired.")
        return True, scrub_esc_codes(output, expect)

def extract_dynamic_index(data, indices=[1, 2, 3]):
    """
    Attempts to extract data from the provided dictionary using dynamic indices.
    It checks the provided indices in order and returns the data from the first match.

    :param data: The dictionary from which to extract data.
    :param indices: A list of indices to check, default is [1, 2, 3].
    :return: The extracted data if found, otherwise raises an error.
    """
    for index in indices:
        if index in data:
            rvalue = data[index]
            return rvalue
    raise KeyError(f"None of the expected indices {indices} were found in the data.")

def execute_audit_action(action, global_data_store, current_device_name, pretty=False, timestamps=False):
    # current_device_data = deepcopy(global_data_store.get_device_data(current_device_name))
    current_device_data = global_data_store.get_device_data(current_device_name)

    logging.debug(f"Current device data structure:")
    logging.debug(json.dumps(current_device_data, indent=2))

    policy_name = action.get('policy_name', 'Unnamed Policy')
    display_name = action.get('display_name', 'Unnamed Audit')

    print_pretty(pretty, timestamps, f"Executing audit action: {display_name}", Fore.CYAN)
    print(f"DEBUG: Current device data: {json.dumps(current_device_data, indent=2)}")

    audit_results = []
    conditions = {
        'pass_if': action.get('pass_if'),
        'pass_if_not': action.get('pass_if_not'),
        'fail_if': action.get('fail_if'),
        'fail_if_not': action.get('fail_if_not')
    }

    audit_context = {
        'global_data_store': global_data_store,
        'current_device_name': current_device_name,
        'all_devices': global_data_store.get_all_data(),
        'current_device': current_device_data
    }

    for condition_name, condition in conditions.items():
        if condition:
            print(f"DEBUG: Evaluating condition: {condition_name}")
            print(f"DEBUG: Condition details: {json.dumps(condition, indent=2)}")

            query = condition.get('query')
            parsed_result = None
            new_current_data = None
            if query:
                try:
                    # Flatten the data structure for easier JMESPath querying
                    new_current_data = {}
                    for ttp_path, action_data in current_device_data.items():
                        for action_index, parsed_data in action_data.items():
                            key = ttp_path.split('/')[-1].replace('.ttp', '')
                            new_current_data[key] = parsed_data
                            new_current_data = new_current_data

                    print(f"DEBUG: Flattened data: {json.dumps(new_current_data, indent=2)}")
                    parsed_result = jmespath.search(str(query).strip(), new_current_data)
                    print(f"DEBUG: JMESPath query result: {parsed_result}")

                except jmespath.exceptions.JMESPathError as e:
                    print_pretty(pretty, timestamps, f"Error in JMESPath query '{query}': {str(e)}", Fore.RED)

            audit_context['parsed_result'] = parsed_result
            condition_met = check_run_if_condition(
                new_current_data if new_current_data else audit_context['current_device'], condition)

            print(f"DEBUG: Condition met: {condition_met}")

            result = {
                'condition': condition_name,
                'condition_met': condition_met,
                'details': condition,
                'parsed_result': parsed_result
            }
            audit_results.append(result)

            if condition_name in ['pass_if', 'fail_if'] and condition_met:
                print(f"DEBUG: Breaking loop due to {condition_name} condition being met")
                break
            elif condition_name in ['pass_if_not', 'fail_if_not'] and not condition_met:
                print(f"DEBUG: Breaking loop due to {condition_name} condition not being met")
                break

    audit_passed = any(r['condition_met'] for r in audit_results if r['condition'] in ['pass_if', 'pass_if_not']) and \
                   not any(r['condition_met'] for r in audit_results if r['condition'] in ['fail_if', 'fail_if_not'])

    overall_result = "PASSED" if audit_passed else "FAILED"
    print(f"DEBUG: Audit results: {json.dumps(audit_results, indent=2)}")
    print(f"DEBUG: Overall result: {overall_result}")

    audit_report_entry = {
        'policy_name': policy_name,
        'display_name': display_name,
        'device_name': current_device_name,
        'results': audit_results,
        'overall_result': overall_result
    }
    global_data_store.add_audit_report(audit_report_entry)

    print_pretty(pretty, timestamps, f"Overall Audit Result: {overall_result}",
                 Fore.GREEN if audit_passed else Fore.RED)

    if not audit_passed:
        print_pretty(pretty, timestamps, "Audit policy failed. Consider taking remediation actions.", Fore.YELLOW)

    return audit_report_entry
def check_run_if_condition(current_device_data, run_if):
    """
    Checks whether the 'run_if' condition is met for the current device context.

    Args:
        current_device_data (dict): The context data for the current device.
        run_if (dict): The condition to evaluate, containing check_type, operator, and query.

    Returns:
        bool: True if the condition is met, False otherwise.
    """
    check_type = run_if.get('check_type')
    operator = run_if.get('operator', {})
    operator_type = operator.get('type')
    operator_value = operator.get('value')

    print(f"DEBUG: Checking run_if condition - Type: {check_type}, Operator: {operator_type}")

    # Handle raw string checks
    if check_type == 'raw_string':
        template = run_if.get('template')
        index = int(run_if.get('index', 0))  # Default to 0 if index is not provided
        data = current_device_data.get(template, [])
        target_data = data[index] if index < len(data) else None

        if target_data and 'parsed_output' in target_data:
            target_str = json.dumps(target_data['parsed_output'])

            if operator_type == 'string_in':
                return operator_value in target_str
            elif operator_type == 'string_not_in':
                return operator_value not in target_str
            elif operator_type == 'is_equal':
                return target_str == operator_value

    # Handle JMESPath checks
    elif check_type == 'jmespath':
        query = run_if.get('query')
        target_value = jmespath.search(query, current_device_data)

        if target_value is None:
            print(f"DEBUG: JMESPath query '{query}' did not return any results.")
            return False

        # Convert target_value to string for string comparisons or to float for numeric comparisons
        result = False
        if operator_type == 'string_in':
            result = operator_value in str(target_value)
        elif operator_type == 'string_not_in':
            result = operator_value not in str(target_value)
        elif operator_type == 'is_equal':
            result = str(target_value) == operator_value
        elif operator_type in ['is_gt', 'is_lt', 'is_equal', 'is_ge', 'is_le']:  # Adding more numeric comparisons
            try:
                # Convert both values to float for numeric comparisons
                target_value_float = float(target_value)
                operator_value_float = float(operator_value)
                if operator_type == 'is_gt':
                    result = target_value_float > operator_value_float
                elif operator_type == 'is_lt':
                    result = target_value_float < operator_value_float
                elif operator_type == 'is_ge':
                    result = target_value_float >= operator_value_float
                elif operator_type == 'is_le':
                    result = target_value_float <= operator_value_float
                elif operator_type == 'is_equal':
                    result = target_value_float == operator_value_float
            except ValueError:
                print(f"DEBUG: Unable to compare values as floats: {target_value} and {operator_value}")
                return False

        print(f"DEBUG: JMESPath check result: {result}")
        return result

    # Add handling for any additional check types here...

    print(f"DEBUG: Unsupported check type or operator: {check_type}, {operator_type}")
    return False


def dump_yaml_to_file(data, output_file_path):
    try:
        with io.open(output_file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    except Exception as e:
        print(f"Error writing YAML to file: {str(e)}", Fore.RED)



def print_pretty(pretty, timestamps, msg, color=Fore.WHITE):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S') if timestamps else ''
    if pretty:
        print(f"{timestamp} {color + msg + Style.RESET_ALL}")
    else:
        print(f"{timestamp} {msg}")


def resolve_action_vars(action, context):
    """
    Resolves variables in action_vars using JMESPath queries within the context.

    Args:
        action (dict): The action containing action_vars with JMESPath queries.
        context (dict): The context data used for resolving JMESPath queries.

    Returns:
        dict: The resolved variables for use in the action.
    """
    resolved_vars = {}
    if 'action_vars' in action:
        for var in action['action_vars']:
            for key, query in var.items():
                try:
                    # Resolve the variable using JMESPath
                    resolved_vars[key] = jmespath.search(query, context)
                except jmespath.exceptions.JMESPathError as e:
                    print(f"Error resolving JMESPath query '{query}': {e}")
                    resolved_vars[key] = None  # Set to None if there's an error
    return resolved_vars


def dereference_placeholders(text, resolved_vars):
    """
    Replace placeholders in text with resolved variables.

    Args:
        text (str): The string with placeholders to replace.
        resolved_vars (dict): The resolved variables.

    Returns:
        str: The text with placeholders replaced by resolved variable values.
    """
    placeholder_pattern = re.compile(r'\[\%\s*(\w+)\s*\%\]')

    def replace_placeholder(match):
        var_name = match.group(1)
        return str(resolved_vars.get(var_name, match.group(0)))  # Replace with value or keep original if not found

    return placeholder_pattern.sub(replace_placeholder, text)


def log_command_execution(log_file, message):
    with open(log_file, 'a') as f:
        f.write(f"{message}\n")
        f.flush()
def log_command_output(log_file, command, output):
    with open(log_file, 'a') as f:
        f.write(f"Raw output for command '{command}':\n{output}\n")
        f.flush()

def parse_output_with_ttp(ttp_path, output):
    with open(ttp_path, 'r') as template_file:
        ttp_template = template_file.read()
    parser = ttp(data=output, template=ttp_template)
    parser.parse()
    result = parser.result()
    return result



def clean_output(output: str) -> str:
    """
    Cleans the output by removing carriage returns and normalizing line endings.
    :param output: The raw command output string.
    :return: Cleaned output string.
    """
    # Replace carriage return + newline with just newline, or remove carriage returns entirely
    cleaned_output = output.replace('\r\n', '\n').replace('\r', '')
    # Further processing can include removing other control characters if needed
    return cleaned_output


def execute_commands(ssh_connection: ThreadSafeSSHConnection, actions, variables, inter_command_time, log_file, error_string,
                     global_output_path, global_output_mode, prompt, buffer_lock, global_prompt_count,
                     pretty=False, global_audit=None, timestamps=False, global_data_store=None, timeout=10, max_polls=10):
    # Debug prints to show the initial parameters
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
    device_name = variables['hostname']
    global_data_store.set_current_device(device_name)  # Set the current device at the start of command execution

    if pretty:
        init(autoreset=True)

    global_output = ""
    stop_device_commands = False
    actions_skipped_due_to_prompt_count = False

    in_loop = False
    loop_data = None
    loop_variable = None
    loop_index = 0
    loop_start_index = 0

    action_index = 0
    while action_index < len(actions):
        action = actions[action_index]
        output_buffer = Queue()
        output_queue = Queue()

        # Debugging Global Data Store
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
            action_index += 1
            continue

        if action['action'] == 'sleep':
            sleep_seconds = action.get('seconds', 1)
            print_pretty(pretty, timestamps, f"Sleeping for {sleep_seconds} seconds.", Fore.CYAN)
            time.sleep(sleep_seconds)
            action_index += 1
            continue

        if action['action'] == 'python_script':
            use_parent_path = action.get('use_parent_path', False)
            path_to_python = action.get('path_to_python', sys.executable if use_parent_path else None)
            path_to_script = action.get('path_to_script')
            arguments_string = action.get('arguments_string', '')

            if not path_to_python or not path_to_script:
                print_pretty(pretty, timestamps, "ERROR: path_to_python or path_to_script is missing.", Fore.RED)
                action_index += 1
                continue

            command = [path_to_python, path_to_script] + arguments_string.split()
            print_pretty(pretty, timestamps, f"Executing Python script: {' '.join(command)}", Fore.CYAN)
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                print_pretty(pretty, timestamps, f"Script output: {result.stdout}", Fore.GREEN)
                print_pretty(pretty, timestamps, f"Script errors: {result.stderr}", Fore.RED)
                with open(log_file, 'a') as f:
                    f.write(f"Script output: {result.stdout}\n")
                    f.write(f"Script errors: {result.stderr}\n")
                    f.flush()
            except subprocess.CalledProcessError as e:
                print_pretty(pretty, timestamps, f"Script execution failed with error: {e}", Fore.RED)
                print_pretty(pretty, timestamps, f"Script stderr: {e.stderr}", Fore.RED)
                with open(log_file, 'a') as f:
                    f.write(f"Script execution failed with error: {e}\n")
                    f.write(f"Script stderr: {e.stderr}\n")
                    f.flush()
            action_index += 1
            continue

        # Loop handling logic
        if action['action'] == 'loop_start':
            if in_loop:
                print_pretty(pretty, timestamps, "Nested loops are not supported", Fore.RED)
                action_index += 1
                continue
            in_loop = True
            loop_variable = action['loop_variable']
            jmespath_query = action['data_source']['jmespath_query']
            loop_data = jmespath.search(jmespath_query, global_data_store.get_all_data())
            print(f"DEBUG: Loop Start - Query: {jmespath_query}, Resolved Data: {loop_data}")
            if not loop_data:
                print_pretty(pretty, timestamps, f"Warning: No data found for loop with query: {jmespath_query}",
                             Fore.YELLOW)
            loop_index = 0
            loop_start_index = action_index
            action_index += 1
            continue

        elif action['action'] == 'loop_end':
            if not in_loop:
                print_pretty(pretty, timestamps, "Encountered loop_end without loop_start", Fore.RED)
                action_index += 1
                continue
            loop_index += 1
            if loop_index < len(loop_data):
                index = loop_start_index + 1  # Go back to start of loop (after loop_start)
            else:
                in_loop = False
                loop_data = None
                loop_variable = None
            action_index += 1
            continue

        # Resolve action variables if in a loop
        context = {loop_variable: loop_data[loop_index]} if in_loop else global_data_store.get_all_data()
        resolved_vars = resolve_action_vars(action, context)

        if (action['action'] == 'send_command' or action['action'] == 'send_config') and not stop_device_commands:
            command = action.get('command') or action.get('config')
            command = dereference_placeholders(command, resolved_vars)

            print(f"DEBUG: Executing command with resolved variables: {command}")
            command_lines = command.strip().split('\n')
            for line in command_lines:
                if stop_device_commands:
                    break

                print_pretty(pretty, timestamps, f"Executing command: {line}", Fore.LIGHTYELLOW_EX)
                # log_command_execution(log_file, f"Executing command: {line}")

                expect = action.get('expect', prompt)
                try:
                    action_output = ssh_connection.send_command(line, expect, timeout, expect_occurrences=20)
                    # print(f"DEBUG: Command execution output: {action_output}")
                except Exception as e:
                    print_pretty(pretty, timestamps, f"Failed to execute command: {line}. Error: {e}", Fore.RED)
                    log_command_execution(log_file, f"Failed to execute command: {line}. Error: {e}")
                    continue

                log_command_output(log_file, line, action_output)

                print(dict(action))
                ttp_path = action.get('ttp_path', '')
                if ttp_path:
                    parsed_data = parse_output_with_ttp(ttp_path, action_output)
                    if parsed_data:
                        print(f"TTP Parser results:\n{json.dumps(parsed_data,indent=2)}")
                        global_data_store.update(device_name, ttp_path, action_index, parsed_data)


                if 'output_file_path' in action:
                    output_path = dereference_placeholders(action['output_file_path'], resolved_vars)
                    action['output_buffer'] = action_output  # Store output in action's buffer
                else:
                    global_output += action_output  # Append to global output if no action-specific path


                global_prompt_count[0] += 1
                if global_prompt_count[0] >= global_prompt_count[1]:
                    print_pretty(pretty, timestamps, "Prompt count reached, stopping device command execution.",
                                 Fore.YELLOW)
                    stop_device_commands = True
                    actions_skipped_due_to_prompt_count = True
                    break

                time.sleep(inter_command_time)
        elif action['action'] == 'dump_datastore':
            output_as = action.get('output_as', 'console')
            output_format = action.get('format', 'text')
            output_file_path = action.get('output_file_path', '')

            data = global_data_store.get_all_data()
            if output_format == 'json':
                formatted_data = json.dumps(data, indent=2)
            else:
                formatted_data = yaml.dump(data)

            if output_as in ('console', 'both'):
                pass

            if output_as in ('file', 'both') and output_file_path:
                with open(output_file_path, 'w') as f:
                    f.write(formatted_data)
                    f.flush()

        elif action['action'] == 'audit':
            print_pretty(pretty, timestamps, "Executing audit action", Fore.CYAN)

            # Create the audit context
            audit_context = {
                'global_data_store': global_data_store,
                'current_device_name': device_name,
                'all_devices': global_data_store.get_all_data(),
                'current_device': global_data_store.get_device_data(device_name)
            }

            # Execute the audit action
            audit_result = execute_audit_action(action, global_data_store, device_name, pretty, timestamps)

            # Update the global audit with the results
            policy_name = audit_result['policy_name']
            if policy_name not in global_audit:
                global_audit[policy_name] = []

            global_audit[policy_name].append({
                'display_name': audit_result['display_name'],
                'results': audit_result['results'],
                'overall_result': audit_result['overall_result']
            })

            # If you need to perform any additional actions based on the audit result, you can do so here
            if audit_result['overall_result'] == "FAILED":
                print_pretty(pretty, timestamps,
                             f"Audit policy {policy_name} failed. Consider taking remediation actions.", Fore.YELLOW)

            action_index += 1
            continue

        elif action['action'] == 'print_audit':
            print_pretty(pretty, timestamps, "Executing print_audit action", Fore.CYAN)
            output_format = action.get('format', 'console')
            output_file_path = action.get('output_file_path', '')

            if global_audit:
                audit_output = json.dumps(global_audit, indent=2) if output_format == 'json' else yaml.dump(
                    global_audit)

                if output_format in ('console', 'both'):
                    print_pretty(pretty, timestamps, "Audit results:", Fore.CYAN)

                if output_format in ('file', 'both') and output_file_path:
                    with open(output_file_path, 'w') as f:
                        f.write(audit_output)
                        f.flush()
            else:
                print_pretty(pretty, timestamps, "No audit results to print.", Fore.YELLOW)

        action_index += 1

    # Write global buffer contents to the global output file
    # if global_output_path:
    #     print_pretty(pretty, timestamps, f"Writing to global output file: {global_output_path}", Fore.CYAN)
    #     with open(global_output_path, 'a' if global_output_mode == 'append' else 'w') as f:
    #         f.write(global_output)
    #         f.flush()

    if actions_skipped_due_to_prompt_count:
        print_pretty(pretty, timestamps,
                     "WARNING: Script stopped performing device commands due to reaching the prompt count limit.",
                     Fore.YELLOW)

    return False, global_output
