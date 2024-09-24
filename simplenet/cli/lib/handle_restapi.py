import re

import requests
import json
import time
import jmespath
import sys
import io
import os
import logging

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

# from simplenet.cli.command_executor import log_command_output, dereference_placeholders



console_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler('app.log', encoding='utf-8')  # Ensure UTF-8 encoding

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)


# # Ensure stdout and stderr use UTF-8 encoding
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set console code page to UTF-8 on Windows
if sys.platform.startswith('win'):
    os.system('chcp 65001')

def log_command_output(log_file, command, output):
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"Raw output for command '{command}':\n{output}\n")
        f.flush()


def handle_rest_api_action(action, resolved_vars, log_file, pretty, timestamps, stop_device_commands, global_output,
                           error_string, global_data_store, debug_output):
    method = action.get('method', 'GET').upper()
    url = action.get('url')
    headers = action.get('headers', {})
    body = action.get('body', {})

    # Convert retries and expected status to integers if they are present and valid strings
    retries = int(action.get('retries', '1'))
    expected_status = int(action.get('expect', '200'))
    verify = action.get('verify', 'True').lower() == 'true'  # Ensure verify is treated as a boolean
    timeout = int(action.get('timeout', '10'))  # Timeout as an integer, defaulting to 10 seconds
    body_type = action.get('body_type', 'json')  # Default body type

    # Replace placeholders in URL, headers, and body
    url = dereference_placeholders(url, resolved_vars)
    headers = {k: dereference_placeholders(v, resolved_vars) for k, v in headers.items()}
    body = {k: dereference_placeholders(v, resolved_vars) for k, v in body.items()}

    # Handle action variables from the global store (e.g., tokens)
    for header_key, header_value in headers.items():
        if 'action_variables.' in header_value:
            variable_name = header_value.split('action_variables.')[-1]
            stored_value = global_data_store.get_variable(variable_name)
            if stored_value:
                headers[header_key] = f"Bearer {stored_value}"

    if debug_output:
        print(
            f"Executing API call {method} {url} with headers {headers}, body {body}, verify={verify}, timeout={timeout}")

    for attempt in range(retries):
        try:
            # Handle the different HTTP methods
            if method == 'GET' or method == 'DELETE':
                # For GET and DELETE, no body should be sent
                response = requests.request(method, url, headers=headers, timeout=timeout, verify=verify)
            else:  # For POST, PUT, PATCH, use the body
                if body_type == 'json':
                    response = requests.request(method, url, headers=headers, json=body, timeout=timeout, verify=verify)
                elif body_type == 'form':
                    response = requests.request(method, url, headers=headers, data=body, timeout=timeout, verify=verify)
                else:
                    response = requests.request(method, url, headers=headers, data=body, timeout=timeout, verify=verify)

            # If status code is not the expected one
            if response.status_code != expected_status:
                log_command_output(log_file, f"Error: Unexpected status code {response.status_code} for {url}",
                                   response.text)
                print(f"ERROR: {response.status_code} - {response.text}")
                stop_device_commands = True
                return global_output, stop_device_commands

            # If request was successful (status code as expected)
            try:
                response_json = response.json()
                action_output = json.dumps(response_json, ensure_ascii=False, indent=2) if pretty else json.dumps(
                    response_json, ensure_ascii=False)
            except json.JSONDecodeError:
                action_output = response.text  # Fallback to text if JSON parsing fails

            log_command_output(log_file, f"{method} {url} - Response:", action_output)
            global_output += action_output

            # Handle storing variables via store_query
            store_query = action.get('store_query', {})
            if store_query:
                print(f"Store query detected: {store_query}")
                query_result = jmespath.search(store_query['query'],
                                               response_json if 'response_json' in locals() else {})
                print(f"Query result: {query_result}")
                if query_result is not None:
                    variable_name = store_query.get('variable_name')
                    if variable_name:
                        print(f"Storing variable {variable_name} with value: {query_result}")
                        global_data_store.set_variable(variable_name, query_result)
                        sanity = global_data_store.get_variable(variable_name)
                        print(f"Stored variable '{variable_name}' with value: {query_result}")
                        print(f"sanity check retrieved as [{sanity}]")
            return global_output, stop_device_commands

        except requests.exceptions.Timeout:
            print(f"API call to {url} timed out. Retrying...")
            log_command_output(log_file, f"Timeout error: API call to {url} timed out.", "")

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            log_command_output(log_file, f"HTTP error:", str(http_err))

        except UnicodeEncodeError as ue:
            safe_output = ue.object[ue.start:ue.end].encode('utf-8', errors='replace').decode('utf-8')
            print(f"Unicode encoding error: {safe_output}")
            log_command_output(log_file, f"Unicode encoding error:", safe_output)
            stop_device_commands = True
            return global_output, stop_device_commands

        except Exception as e:
            print(f"Failed to execute API call: {url}. Error: {e}")
            log_command_output(log_file, f"General error:", str(e))
            time.sleep(2)  # Retry after delay

    stop_device_commands = True
    return global_output, stop_device_commands
