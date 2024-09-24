import time

from colorama import Fore

from simplenet.cli.lib.audit_actions import print_pretty
from simplenet.cli.lib.utils import load_variables_from_file, render_template, log_command_output, log_command_execution


def execute_send_config(ssh_connection, action, resolved_vars, log_file, prompt, pretty, timestamps,
                        stop_device_commands, global_output, global_prompt_count, inter_command_time, error_string):
    """
    Handle the 'send_config' action, which sends configuration commands to a device.

    Args:
        ssh_connection (ThreadSafeSSHConnection): SSH connection object.
        action (dict): Action details containing 'config' or 'config_template_path'.
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
    """
    variables = {}
    # Load variables and render the configuration if variables_path is provided
    if 'variables_path' in action:
        variables_path = action['variables_path']
        variables = load_variables_from_file(variables_path)
        resolved_vars.update(variables)  # Merge loaded variables with resolved_vars

    if action.get('error_string'):
        error_string = action['error_string']

    config_content = action.get('config', '')
    # print(f"config:\n{config_content}")

    # Replace custom markers with Jinja2 markers
    config_content = config_content.replace("{[", "{{").replace("]}", "}}")
    # print(f"New config: \n{config_content}")

    # If no config content provided, check for a config template path
    if not config_content and 'config_template_path' in action:
        template_path = action['config_template_path']
        try:
            with open(template_path, 'r') as file:
                template_str = file.read()
            if variables:
                config_content = render_template(template_str, variables)
        except Exception as e:
            print_pretty(pretty, timestamps, f"Failed to load or render template: {template_path}. Error: {e}",
                         Fore.RED)
            return

    # Render inline configuration with variables if config content is present
    if config_content and resolved_vars:
        config_content = render_template(config_content, resolved_vars)

    # If still no configuration content, notify and exit
    if not config_content:
        print_pretty(pretty, timestamps, "No configuration commands found.", Fore.YELLOW)
        return



    # Send each configuration line (device is already in config mode)
    config_lines = config_content.strip().split('\n')

    for line in config_lines:
        if stop_device_commands:
            break

        print_pretty(pretty, timestamps, f"Sending config: {line}", Fore.LIGHTYELLOW_EX)
        try:
            action_output = ssh_connection.send_command(line, prompt, timeout=10)
            log_command_output(log_file, line, action_output)

            # Check for error string in output
            if error_string and error_string in action_output:
                print_pretty(pretty, timestamps, f"ERROR detected in device response: {action_output}", Fore.RED)
                log_command_execution(log_file, f"ERROR detected in device response: {action_output}")
                return  # Stop execution if an error is detected

        except Exception as e:
            print_pretty(pretty, timestamps, f"Failed to send config: {line}. Error: {e}", Fore.RED)
            log_command_execution(log_file, f"Failed to send config: {line}. Error: {e}")
            continue

        time.sleep(inter_command_time)
