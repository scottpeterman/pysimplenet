import io
import subprocess
import sys
import threading
import time
from queue import Empty, Queue
from ttp import ttp
import jinja2
from simplenet.cli.reader import read_and_process_output
import json
from ruamel.yaml import YAML as yaml
import jmespath
from colorama import Fore, Style, init


def check_run_if_condition(global_data_store, run_if):
    check_type = run_if.get('check_type')
    operator = run_if.get('operator', {})
    operator_type = operator.get('type')
    operator_value = operator.get('value')

    if check_type == 'raw_string':
        template = run_if.get('template')
        index = int(run_if.get('index'))
        data = global_data_store.get_entries(template)
        target_data = data[index] if index < len(data) else None

        if target_data and 'parsed_output' in target_data:
            target_str = json.dumps(target_data['parsed_output'])
            if operator_type == 'string_in' and operator_value in target_str:
                return True
            elif operator_type == 'string_not_in' and operator_value not in target_str:
                return True

    elif check_type == 'jmespath':
        query = run_if.get('query')
        data = global_data_store.get_all_data()
        target_value = jmespath.search(query, data)

        if target_value is None:
            print(f"JMESPath query '{query}' did not return any results.")
            return False

        # Convert target_value to string for string comparisons
        if isinstance(target_value, (list, dict)):
            target_value = json.dumps(target_value)
        else:
            target_value = str(target_value)

        # Convert target_value to float for numerical comparisons
        try:
            target_value_float = float(target_value)
        except ValueError:
            target_value_float = None

        if operator_type == 'string_in':
            return operator_value in target_value
        elif operator_type == 'string_not_in':
            return operator_value not in target_value
        elif operator_type == 'is_equal':
            return target_value == operator_value
        elif operator_type == 'is_gt' and target_value_float is not None:
            return target_value_float > float(operator_value)
        elif operator_type == 'is_lt' and target_value_float is not None:
            return target_value_float < float(operator_value)

    return False

def dump_yaml_to_file(data, output_file_path):
    try:
        with io.open(output_file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    except Exception as e:
        print(f"Error writing YAML to file: {str(e)}", Fore.RED)

def execute_commands(channel, actions, variables, inter_command_time, log_file, error_string, global_output_path,
                     global_output_mode, prompt, buffer_lock, global_prompt_count, global_data_store, pretty=False,
                     global_audit=None, timestamps=False, timeout=10):
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

    if pretty:
        init(autoreset=True)

    def print_pretty(msg, color=Fore.WHITE):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S') if timestamps else ''
        if pretty:
            print(f"{timestamp} {color + msg + Style.RESET_ALL}")
        else:
            print(f"{timestamp} {msg}")

    def print_colored(msg, primary_color=Fore.WHITE, secondary_color=Fore.LIGHTGREEN_EX):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S') if timestamps else ''
        if pretty:
            parts = msg.split(": ")
            if len(parts) == 2:
                print(f"{timestamp} {primary_color + parts[0] + ': ' + secondary_color + parts[1] + Style.RESET_ALL}")
            else:
                print(f"{timestamp} {primary_color + msg + Style.RESET_ALL}")
        else:
            print(f"{timestamp} {msg}")

    global_output = ""
    stop_device_commands = False
    actions_skipped_due_to_prompt_count = False

    for index, action in enumerate(actions):
        output_buffer = Queue()
        output_queue = Queue()

        if 'run_if' in action and not check_run_if_condition(global_data_store, action['run_if']):
            print_pretty(f"Skipping action {action['action']} due to run_if condition.", Fore.YELLOW)
            continue

        if global_prompt_count[0] >= global_prompt_count[1]:
            print_pretty("Prompt count reached, stopping device command execution.", Fore.YELLOW)
            stop_device_commands = True
            actions_skipped_due_to_prompt_count = True

        if action['action'] == 'sleep':
            sleep_seconds = action.get('seconds', 1)
            print_pretty(f"Sleeping for {sleep_seconds} seconds.", Fore.CYAN)
            time.sleep(sleep_seconds)
            continue

        if action['action'] == 'python_script':
            use_parent_path = action.get('use_parent_path', False)
            path_to_python = action.get('path_to_python', sys.executable if use_parent_path else None)
            path_to_script = action.get('path_to_script')
            arguments_string = action.get('arguments_string', '')

            if not path_to_python or not path_to_script:
                print_pretty("ERROR: path_to_python or path_to_script is missing.", Fore.RED)
                continue

            command = [path_to_python, path_to_script] + arguments_string.split()
            print_pretty(f"Executing Python script: {' '.join(command)}", Fore.CYAN)
            try:
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                print_pretty(f"Script output: {result.stdout}", Fore.GREEN)
                print_pretty(f"Script errors: {result.stderr}", Fore.RED)
                with open(log_file, 'a') as f:
                    f.write(f"Script output: {result.stdout}\n")
                    f.write(f"Script errors: {result.stderr}\n")
                    f.flush()
            except subprocess.CalledProcessError as e:
                print_pretty(f"Script execution failed with error: {e}", Fore.RED)
                print_pretty(f"Script stderr: {e.stderr}", Fore.RED)
                with open(log_file, 'a') as f:
                    f.write(f"Script execution failed with error: {e}\n")
                    f.write(f"Script stderr: {e.stderr}\n")
                    f.flush()
            continue

        if (action['action'] == 'send_command' or action['action'] == 'send_config') and not stop_device_commands:
            command = action.get('command') or action.get('config')
            if action['action'] == 'send_config':
                template = jinja2.Template(command)
                command = template.render(variables)

            command_lines = command.strip().split('\n')
            for line in command_lines:
                if stop_device_commands:
                    break

                cmd_msg = f"Executing command: {line}\n"
                print_pretty(cmd_msg, Fore.LIGHTYELLOW_EX)
                with open(log_file, 'a') as f:
                    f.write(cmd_msg)
                    f.flush()
                channel.send(line + '\n')

                expect = action.get('expect', prompt)  # Use the provided expect or default to prompt
                read_thread = threading.Thread(target=read_and_process_output,
                                               args=(channel, output_queue, output_buffer, expect, prompt, log_file,
                                                     error_string, buffer_lock, global_prompt_count, pretty, timestamps,
                                                     timeout))
                read_thread.daemon = True
                read_thread.start()

                start_time = time.time()
                try:
                    reason = output_queue.get(timeout=timeout)  # Adjust timeout as needed
                    elapsed_time = time.time() - start_time
                    print_pretty(f"Exiting: {reason} (Elapsed time: {elapsed_time:.2f} seconds)", Fore.CYAN)
                    if "Error detected" in reason:
                        raise ValueError(reason)
                    if reason == "Timeout expired.":
                        timeout_msg = f"\nCommand timed out after {elapsed_time:.2f} seconds.\n"
                        print_pretty(timeout_msg, Fore.RED)
                        with open(log_file, 'a') as f:
                            f.write(timeout_msg)
                            f.flush()
                        stop_device_commands = True
                        break
                except Empty:
                    print_pretty("Timeout while waiting for command completion or prompt detection.", Fore.RED)

                with buffer_lock:
                    action_output = ""
                    while not output_buffer.empty():
                        action_output += output_buffer.get()

                # Handle TTP parsing if ttp_path is provided
                ttp_path = action.get('ttp_path', '')
                if ttp_path:
                    with open(ttp_path, 'r') as template_file:
                        ttp_template = template_file.read()
                    parser = ttp(data=action_output, template=ttp_template)
                    parser.parse()
                    parsed_data = parser.result()
                    print_pretty(f"Parsed data for {ttp_path}: {parsed_data}", Fore.CYAN)  # Debug print for parsed data
                    if parsed_data:
                        # Update global data store
                        global_data_store.update(ttp_path, index, parsed_data)

                        # Save parsed data to a JSON file with a unique name
                        action_name = action.get('display_name', f'action_{index}').replace(' ', '_').lower()
                        parsed_output_file = f"./output/{variables.get('hostname', 'device')}_{action_name}_parsed_output_{index}.json"
                        with open(parsed_output_file, 'w') as json_file:
                            json.dump(parsed_data, json_file, indent=4)
                        print_pretty(f"Parsed data saved to {parsed_output_file}", Fore.CYAN)

                if 'output_path' in action:
                    action['output_buffer'] = action_output  # Store output in action's buffer
                else:
                    global_output += action_output  # Append to global output if no action-specific path

                time.sleep(inter_command_time)  # Waiting between commands

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
                print_pretty("Data store content:", Fore.CYAN)
                print_pretty(formatted_data, Fore.GREEN)

            if output_as in ('file', 'both') and output_file_path:
                with open(output_file_path, 'w') as f:
                    f.write(formatted_data)
                    f.flush()
                print_pretty(f"Data store written to file: {output_file_path}", Fore.CYAN)

        # Handle audit action
        # Inside the execute_commands function, update the audit action handling:

        if action['action'] == 'audit':
            policy_name = action.get('policy_name')
            if not policy_name:
                print_pretty("ERROR: audit action requires a policy_name.", Fore.RED)
                continue

            audit_results = []

            conditions = {
                'pass_if': action.get('pass_if'),
                'pass_if_not': action.get('pass_if_not'),
                'fail_if': action.get('fail_if'),
                'fail_if_not': action.get('fail_if_not')
            }

            for condition_name, condition in conditions.items():
                if condition:
                    condition_met = check_run_if_condition(global_data_store, condition)

                    # Extract the actual parsed result
                    query = condition.get('query')
                    parsed_result = None
                    if query:
                        parsed_result = jmespath.search(query, global_data_store.get_all_data())

                    result = {
                        'condition': condition_name,
                        'condition_met': condition_met,
                        'details': condition,
                        'parsed_result': parsed_result
                    }
                    audit_results.append(result)
                    if condition_name in ['pass_if', 'fail_if'] and condition_met:
                        break
                    elif condition_name in ['pass_if_not', 'fail_if_not'] and not condition_met:
                        break

            if policy_name not in global_audit:
                global_audit[policy_name] = []

            global_audit[policy_name].append({
                'display_name': action.get('display_name', 'Unnamed'),
                'results': audit_results
            })

            # Print audit result
            print_pretty(f"Audit Policy: {policy_name}", Fore.CYAN)
            for result in audit_results:
                condition_status = 'Met' if result['condition_met'] else 'Not Met'
                print_pretty(f"{result['condition']} - {condition_status}",
                             Fore.GREEN if result['condition_met'] else Fore.RED)
                print_pretty(f"  Parsed Result: {result['parsed_result']}", Fore.YELLOW)

        # Handle print_audit action
        if action['action'] == 'print_audit':
            output_format = action.get('format', 'console')
            output_file_path = action.get('output_file_path', '')

            if global_audit:
                audit_output = json.dumps(global_audit, indent=2) if output_format == 'json' else yaml.dump(
                    global_audit)

                if output_format in ('console', 'both'):
                    print_pretty("Audit results:", Fore.CYAN)
                    print_pretty(audit_output, Fore.GREEN)

                if output_format in ('file', 'both') and output_file_path:
                    with open(output_file_path, 'w') as f:
                        f.write(audit_output)
                        f.flush()
                    print_pretty(f"Audit results written to file: {output_file_path}", Fore.CYAN)

                if output_format in ('json', 'both') and output_file_path:
                    with open(output_file_path, 'w') as f:
                        f.write(json.dumps(global_audit, indent=2))
                        f.flush()
                    print_pretty(f"Audit results written to file: {output_file_path}", Fore.CYAN)

                if output_format in ('yaml', 'both') and output_file_path:
                    dump_yaml_to_file(global_audit, output_file_path)
                    print_pretty(f"Audit results written to file: {output_file_path}", Fore.CYAN)


        # Handle output_path and output_mode
        if 'output_path' in action:
            output_path = action['output_path']
            output_mode = action.get('output_mode', 'overwrite')
            output_template = jinja2.Template(output_path)
            output_path_rendered = output_template.render(variables)
            print(output_path_rendered)

            print_pretty(f"Writing to file: {output_path_rendered}", Fore.CYAN)
            if output_path_rendered != "":
                with open(output_path_rendered, 'a' if output_mode == 'append' else 'w') as f:
                    f.write(action['output_buffer'])
                    f.flush()

        time.sleep(inter_command_time)

    # Write global buffer contents to the global output file
    if global_output_path:
        print_pretty(f"Writing to global output file: {global_output_path}", Fore.CYAN)
        with open(global_output_path, 'a' if global_output_mode == 'append' else 'w') as f:
            f.write(global_output)
            f.flush()

    if actions_skipped_due_to_prompt_count:
        print_pretty("WARNING: Script stopped performing device commands due to reaching the prompt count limit.",
                     Fore.YELLOW)

    return False, global_output  # Return False to indicate no error was detected


