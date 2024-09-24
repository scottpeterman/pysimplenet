import os
import re
import requests
import json
import time
import jmespath
from pprint import pprint
from colorama import Fore
from jinja2 import Template


# Utility Functions
def log_command_output(log_file, command, output):
    """Logs the command and its output to a specified log file."""
    with open(log_file, 'a') as f:
        f.write(f"Raw output for command '{command}':\n{output}\n")
        f.flush()


def dereference_placeholders(text, resolved_vars):
    """Replaces placeholders in the text using the provided resolved variables."""
    placeholder_pattern = re.compile(r'\[\%\s*(\w+)\s*\%\]')

    def replace_placeholder(match):
        var_name = match.group(1)
        return str(resolved_vars.get(var_name, match.group(0)))  # Replace with variable value or keep original

    return placeholder_pattern.sub(replace_placeholder, text)


def create_directory_if_needed(output_file_path):
    """Ensures the directory for output files exists."""
    output_dir = os.path.dirname(output_file_path)
    if output_dir and not os.path.exists(output_dir):
        print(f"DEBUG: Creating output directory {output_dir}")
        os.makedirs(output_dir)


def prepare_request_components(action, resolved_vars):
    """Prepares the URL, headers, and body for the request."""
    url_template = action.get('url')
    headers = action.get('headers', {})
    body = action.get('body', {})

    # Replace placeholders in headers and body
    headers = {k: Template(v).render(**resolved_vars) for k, v in headers.items()}
    body = {k: Template(v).render(**resolved_vars) for k, v in body.items()}

    return url_template, headers, body


def send_api_request(method, url, headers, body, body_type, timeout, verify, debug_output):
    """Sends an API request and returns the response."""
    if body_type == 'json':
        response = requests.request(method, url, headers=headers,
                                    json=body if method not in ['GET', 'DELETE'] else None,
                                    timeout=timeout, verify=verify)
    elif body_type == 'form':
        response = requests.request(method, url, headers=headers,
                                    data=body if method not in ['GET', 'DELETE'] else None,
                                    timeout=timeout, verify=verify)
    else:
        response = requests.request(method, url, headers=headers,
                                    data=body if method not in ['GET', 'DELETE'] else None,
                                    timeout=timeout, verify=verify)

    if debug_output:
        print(f"DEBUG: API Request - Method: {method}, URL: {url}, Headers: {headers}, Body: {body}")

    return response


def handle_response(response, expected_status, log_file, url, pretty):
    """Handles the response, logging the output and formatting it."""
    if response.status_code != expected_status:
        print(f"Error: Unexpected status code {response.status_code} for {url}\n{response.text}")
        return None

    try:
        response_json = response.json()
        action_output = json.dumps(response_json, ensure_ascii=False, indent=2) if pretty else json.dumps(response_json)
    except json.JSONDecodeError:
        action_output = response.text  # Fallback to text if JSON parsing fails

    log_command_output(log_file, f"Response for {url}:", action_output)
    return action_output


def store_variables(store_query, response_json, global_data_store):
    """Stores variables from the response using the store_query field."""
    if store_query:
        query_result = jmespath.search(store_query['query'], response_json)
        if query_result is not None:
            variable_name = store_query.get('variable_name')
            if variable_name:
                global_data_store.set_variable(variable_name, query_result)
                print(f"Stored variable '{variable_name}' with value: {query_result}")


# Main Function for handling API loop
def replace_custom_tags_with_jinja2(text):
    """
    Replace custom tags [{ }] with Jinja2-compatible {{ }} tags.

    Args:
        text (str): The string containing custom tags.

    Returns:
        str: The string with custom tags replaced by Jinja2-compatible tags.
    """
    return re.sub(r'\[\{\s*(\w+)\s*\}\]', r'{{ \1 }}', text)


def handle_rest_api_loop(action_index, action, resolved_vars, log_file, pretty, timestamps,
                         stop_device_commands, global_output, global_prompt_count, inter_command_time, error_string,
                         device_name, global_data_store, debug_output):
    """
    Handles the 'rest_api_loop' action, sending API requests in a loop using a list of values and processing outputs.
    """
    if debug_output:
        debug_global_output = dict(global_data_store)
        pprint(debug_global_output)

    # Extract the key parameters from the action
    method = action.get('method', 'GET').upper()
    url_template = action.get('url')
    headers = action.get('headers', {})
    body = action.get('body', {})
    retries = action.get('retries', 1)
    verify = action.get('verify', 'False').strip().lower() == 'false'  # Convert string "True" or "False" to boolean
    timeout = action.get('timeout', 10)
    body_type = action.get('body_type', 'json')  # Default 'json', can be 'form'

    # Loop variable details
    variable_name = action.get('variable_name')
    key_to_loop = action.get('key_to_loop')
    output_file_path = action.get('output_path', '')
    output_mode = action.get('output_mode', 'a')
    output_mode = "w" if output_mode == "overwrite" else "a"

    # Ensure output directory exists
    if output_file_path:
        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            print(f"DEBUG: Creating output directory {output_dir}")
            os.makedirs(output_dir)

    # Retrieve the list of dictionaries from the global data store
    entry_list = global_data_store.get_variable(variable_name)

    if debug_output:
        print(f"DEBUG: Retrieved entry list '{variable_name}' from global data store: {entry_list}")

    if not entry_list:
        print(f"ERROR: No entries found for variable '{variable_name}'.")
        return global_output, stop_device_commands

    if debug_output:
        print(f"DEBUG: Starting loop through entries: {entry_list}")

    iteration_results = []

    for entry in entry_list:
        if stop_device_commands:
            break

        # Handle missing key_to_loop in entry
        if key_to_loop not in entry:
            print(f"ERROR: Key '{key_to_loop}' not found in entry: {entry}")
            continue

        loop_value = entry[key_to_loop]

        # First, replace custom tags [{ id }] with Jinja2-compatible {{ id }}
        url_template = replace_custom_tags_with_jinja2(url_template)

        # Use Jinja2 to render the URL and resolve placeholders dynamically with the looped value
        template = Template(url_template)
        # Dynamically replace placeholders with the loop value
        url = template.render({key_to_loop: loop_value})

        # Replace any placeholders in headers and body using the looped value and resolved_vars
        # headers = {k: Template(v).render(**resolved_vars) for k, v in headers.items()}
        headers['Authorization'] = f"Bearer {global_data_store.get_variable('jwt_token')}"

        body = {k: Template(v).render(**resolved_vars) for k, v in body.items()}

        if debug_output:
            print(f"DEBUG: Resolved URL: {url}")
            print(f"DEBUG: Headers: {headers}")
            print(f"DEBUG: Body: {body}")

        # API request loop with retry logic
        for attempt in range(retries):
            try:
                # Send the API request
                if body_type == 'json':
                    response = requests.request(method, url, headers=headers,
                                                json=body if method not in ['GET', 'DELETE'] else None,
                                                timeout=timeout, verify=verify)
                elif body_type == 'form':
                    response = requests.request(method, url, headers=headers,
                                                data=body if method not in ['GET', 'DELETE'] else None,
                                                timeout=timeout, verify=verify)
                else:
                    response = requests.request(method, url, headers=headers,
                                                data=body if method not in ['GET', 'DELETE'] else None,
                                                timeout=timeout, verify=verify)

                # Check for expected status code
                expected_status = int(action.get('expect', '200'))
                if response.status_code != expected_status:
                    print(f"Error: Unexpected status code {response.status_code} for {url}", response.text)
                    stop_device_commands = True
                    return global_output, stop_device_commands

                # Process the response
                try:
                    response_json = response.json()
                    action_output = json.dumps(response_json, ensure_ascii=False, indent=2) if pretty else json.dumps(
                        response_json, ensure_ascii=False)
                except json.JSONDecodeError:
                    action_output = response.text  # Fallback to text if JSON parsing fails

                # Log command output and append to global_output
                log_command_output(log_file, f"{method} {url} - Response:", action_output)
                global_output += action_output

                # Handle storing variables via store_query
                store_query = action.get('store_query', {})
                if store_query:
                    query_result = jmespath.search(store_query['query'], response_json)
                    if query_result is not None:
                        variable_name = store_query.get('variable_name')
                        if variable_name:
                            global_data_store.set_variable(variable_name, query_result)
                            print(f"Stored variable '{variable_name}' with value: {query_result}")

                # Write output to file if specified
                if output_file_path:
                    try:
                        with open(output_file_path, output_mode) as f:
                            f.write(f"URL: {url}\nResponse:\n{action_output}\n\n")
                        print(f"DEBUG: Output successfully written to {output_file_path}")
                    except Exception as e:
                        print(f"Unable to save file - {output_file_path}. Error: {e}")

                # Pause between requests if needed
                time.sleep(inter_command_time)

                # Successful request, break retry loop
                iteration_results.append(response_json)

                break

            except requests.exceptions.Timeout:
                print(f"API call to {url} timed out. Retrying...")
                log_command_output(log_file, f"Timeout error: API call to {url} timed out.", "")

            except requests.exceptions.HTTPError as http_err:
                print(f"HTTP error occurred: {http_err}")
                log_command_output(log_file, f"HTTP error:", str(http_err))

            except Exception as e:
                print(f"Failed to execute API call: {url}. Error: {e}")
                log_command_output(log_file, f"General error:", str(e))
                time.sleep(2)  # Retry after a short delay

        # Once the loop is complete, write the collected results to the output file
    if output_file_path:
        try:
            with open(output_file_path, output_mode) as f:
                json.dump(iteration_results, f, indent=2 if pretty else None)
            print(f"DEBUG: Output successfully written to {output_file_path}")
        except Exception as e:
            print(f"Unable to save file - {output_file_path}. Error: {e}")
    return global_output, stop_device_commands
