import io
import json
import re
import time

import jmespath
from ruamel.yaml import YAML as yaml
from colorama import Fore
from jinja2 import Template
from ttp import ttp
from ruamel.yaml import YAML

debug = False
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
    if debug:
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
        if debug:
            print(f"DEBUG: JMESPath check result: {result}")
        return result

    # Add handling for any additional check types here...

    print(f"DEBUG: Unsupported check type or operator: {check_type}, {operator_type}")
    return False

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


def parse_output_with_ttp(ttp_path, output):
    with open(ttp_path, 'r') as template_file:
        ttp_template = template_file.read()
    parser = ttp(data=output, template=ttp_template)
    parser.parse()
    result = parser.result()
    return result



def log_command_execution(log_file, message):
    with open(log_file, 'a') as f:
        f.write(f"{message}\n")
        f.flush()
def log_command_output(log_file, command, output):
    with open(log_file, 'a') as f:
        f.write(f"Raw output for command '{command}':\n{output}\n")
        f.flush()


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


def dump_yaml_to_file(data, output_file_path):
    try:
        with io.open(output_file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)

    except Exception as e:
        print(f"Error writing YAML to file: {str(e)}", Fore.RED)



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

import re

import re

def resolve_template_vars(template_str, variables):
    """
    Replace placeholders in the template string with actual values from variables.

    Args:
        template_str (str): The string containing placeholders, e.g., "./output/{{ hostname }}_data.json"
        variables (dict): Dictionary containing variable values.

    Returns:
        str: The resolved string with variables replaced.
    """
    if not isinstance(template_str, str):
        # If the input is not a string, return it unchanged
        return template_str

    # Regular expression to find placeholders like {{ variable }}
    pattern = re.compile(r'{{\s*([^}]+)\s*}}')

    # Function to replace each match with the corresponding variable value
    def replace(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))  # Leave placeholder unchanged if variable not found

    # Substitute all placeholders in the template string
    resolved_str = pattern.sub(replace, template_str)

    return resolved_str

def render_template(template_str, variables):
    # Replace custom markers {[]} with standard Jinja2 markers {{}}
    # template_str = template_str.replace('{[', '{{').replace(']}', '}}')
    template = Template(template_str)
    result = template.render(variables)
    return result


def load_variables_from_file(variables_path):
    """
    Load variables from a YAML file using ruamel.yaml.

    Args:
        variables_path (str): Path to the variables YAML file.

    Returns:
        dict: Loaded variables.
    """
    yaml = YAML()  # Initialize a YAML object from ruamel.yaml
    try:
        with open(variables_path, 'r') as file:
            variables = yaml.load(file)
        return variables
    except Exception as e:
        print(f"Failed to load variables from {variables_path}: {e}")
        return {}

# def load_variables_from_file(variables_path):
#     """
#     Load variables from a YAML file.
#
#     Args:
#         variables_path (str): Path to the variables YAML file.
#
#     Returns:
#         dict: Loaded variables.
#     """
#     try:
#         with open(variables_path, 'r') as file:
#             variables = yaml.safe_load(file)
#         return variables
#     except Exception as e:
#         print(f"Failed to load variables from {variables_path}: {e}")
#         return {}
