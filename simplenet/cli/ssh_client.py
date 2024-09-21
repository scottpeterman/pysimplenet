import sys
import paramiko
import click
from ruamel.yaml import YAML as yaml
import jinja2
import threading
import time
import os
from queue import Queue, Empty
from colorama import init, Fore, Style

from simplenet.cli.command_executor import execute_commands
from simplenet.cli.reader import read_and_process_output
# from simplenet.cli.ssh_utils import setup_ssh_client, connect_ssh_client, set_ssh_crypto_settings
# from simplenet.cli.data_store import global_data_store
debug = False
# Ensure log directory exists
if not os.path.exists('./log'):
    os.makedirs('./log')

# Function to read the SSH channel output and look for the prompt to stop reading.
def timeout_handler(output_queue):
    output_queue.put("Timeout expired.")

# Load YAML data and optionally initialize data store

# Global audit dictionary
global_audit = {}

# CLI configuration using click
# @click.command()
# @click.option('--host', '-h', required=True, help='SSH Host (ip:port)')
# @click.option('--user', '-u', required=True, help='SSH Username')
# @click.option('--password', '-p', required=True, help='SSH Password')
# @click.option('--driver', '-d', required=True, help='Path to the driver YAML file')
# @click.option('--vars-file', '-v', required=True, help='Variables file to use for rendering templates (YAML)')
# @click.option('--driver-name', '-n', default='cisco_ios', help='Driver name to use in the YAML file [default=cisco_ios]')
# @click.option('--pretty', is_flag=True, help='Enable pretty output with banners and colors')
# @click.option('--verbose', '-V', is_flag=True, help='Enable verbose output to print action details before each action')
# @click.option('--timestamps', is_flag=True, help='Enable timestamps in output')
# @click.option('--timeout', '-t', default=10, help='Command timeout duration in seconds')
# @click.option('--disable-auto-add-policy', is_flag=True, default=False,
#               help='Disable automatically adding the host key [default=False]')
# @click.option('--look-for-keys', is_flag=True, default=False, help='Look for local SSH key [default=False]')
# @click.option('--inter-command-time', '-i', default=1, help='Inter-command time in seconds [default is 1 second]')
# @click.option('--invoke-shell', is_flag=True, help='Invoke shell before running the command [default=False]')
# @click.option('--prompt', default='', help='Prompt to look for before breaking the shell')
# @click.option('--prompt-count', default=1, help='Number of prompts to look for before breaking the shell')
# def ssh_client(host, user, password, driver, vars_file, driver_name, pretty, verbose, timestamps, timeout, disable_auto_add_policy,
#                look_for_keys, inter_command_time, invoke_shell, prompt, prompt_count):
#     """
#     SSH Client for running remote commands based on driver files.
#
#     Sample Usage:
#     python ssh_client.py -h "172.16.101.100" -u "cisco" -p "cisco" -d "drivers/cisco_ios/loopback.yml" -v "vars/usa1-rtr-1_loopback0.yml" --pretty --verbose
#     """
#     # Initialize colorama
#     if pretty:
#         init(autoreset=True)
#
#     def print_pretty(msg, color=Fore.WHITE):
#         timestamp = time.strftime('%Y-%m-%d %H:%M:%S') if timestamps else ''
#         if pretty:
#             print(f"{timestamp} {color + msg + Style.RESET_ALL}")
#         else:
#             print(f"{timestamp} {msg}")
#
#     def write_log(msg):
#         timestamp = time.strftime('%Y-%m-%d %H:%M:%S') if timestamps else ''
#         with open(log_file, 'a') as f:
#             f.write(f"{timestamp} - {msg}\n")
#             f.flush()
#
#     # def print_verbose(msg):
#     #     if verbose:
#     #         print_pretty(msg, Fore.BLUE)
#
#     # def print_colored(label, command, label_color=Fore.GREEN):
#     #     if pretty:
#     #         print(label_color + label + Style.RESET_ALL + command)
#     #     else:
#     #         print(label + command)
#
#     # Set log file path
#     log_file = os.path.join('./log', f'{host}.log')
#
#     # Initialize SSH client and set cryptographic settings
#     client = setup_ssh_client(disable_auto_add_policy, look_for_keys)
#     set_ssh_crypto_settings()
#     connect_ssh_client(client, host, user, password, look_for_keys, timeout, log_file, pretty=pretty)
#
#     buffer_lock = threading.Lock()
#     global_prompt_count = [0, prompt_count]  # [current_count, required_count]
#
#     output_queue = Queue()  # Define output_queue here
#
#     # Set up the timeout timer
#     timer = threading.Timer(timeout, timeout_handler, args=[output_queue])
#     timer.start()
#
#     actions_skipped_due_to_prompt_count = False
#
#     # Load commands and variables from YAML
#     commands = load_yaml(driver, driver_name, is_driver=True)
#     variables = load_yaml(vars_file)
#     if debug:
#         print_pretty(f"Variables: {variables}", Fore.CYAN)  # Debug print for variables
#
#     if not commands or 'drivers' not in commands or driver_name not in commands['drivers']:
#         print_pretty(f"No driver found for {driver_name} in the YAML file.", Fore.RED)
#         # sys.exit(1)
#
#     driver_config = commands['drivers'][driver_name]
#     actions = driver_config['actions']
#     error_string = driver_config.get('error_string', '')
#     global_output_path_template = jinja2.Template(driver_config.get('output_path', './output/device_output.txt'))
#     global_output_path = global_output_path_template.render(variables)
#     global_output_mode = driver_config.get('output_mode', 'overwrite')
#
#     if invoke_shell:
#         try:
#             channel = client.invoke_shell()
#         except Exception as e:
#             error_msg = f"Failed to invoke shell: {str(e)}\n"
#             print_pretty(error_msg, Fore.RED)
#             write_log(error_msg)
#             # sys.exit(1)
#
#         output_buffer = Queue()
#         read_thread = threading.Thread(target=read_and_process_output,
#                                        args=(channel, output_queue, output_buffer, "", prompt, log_file, error_string, buffer_lock, global_prompt_count, pretty, timestamps))
#         read_thread.daemon = True
#         read_thread.start()
#
#         execute_commands(channel, actions, variables, inter_command_time, log_file, error_string,
#                          global_output_path, global_output_mode, prompt, buffer_lock, global_prompt_count,
#                          global_data_store, pretty, global_audit, timestamps=False)
#
#         try:
#             reason = output_queue.get(timeout=timeout)
#             exit_msg = f"\nExiting: {reason}\n"
#             print_pretty(exit_msg, Fore.CYAN)
#             write_log(exit_msg)
#         except Empty:
#             timeout_msg = "\nExiting due to timeout.\n"
#             print_pretty(timeout_msg, Fore.RED)
#             write_log(timeout_msg)
#             sys.exit()
#
#         channel.close()
#     else:
#         print_pretty("Invoke shell must be used to execute commands with YAML-based drivers.", Fore.RED)
#         # sys.exit(1)
#
#     if global_prompt_count[0] < global_prompt_count[1]:
#         print_colored(f"Prompt '{prompt}' detected. Current count: {global_prompt_count[0]}\n", "", Fore.YELLOW)
#
#     print_colored(f"Exiting: Prompt count reached.\n", "", Fore.YELLOW)
#
#     if global_output_path:
#         print_colored(f"Writing to file: {global_output_path}\n", "", Fore.CYAN)
#         print_colored(f"Writing to global output file: {global_output_path}\n", "", Fore.CYAN)
#
#     print_colored(f"Final prompt count: {global_prompt_count[0]} of {global_prompt_count[1]}\n", "", Fore.GREEN)
#
#     # Cancel the timeout timer if still running
#     if timer.is_alive():
#         timer.cancel()
#
#     if actions_skipped_due_to_prompt_count:
#         print_pretty("WARNING: Script stopped performing device commands due to reaching the prompt count limit.", Fore.YELLOW)
#
#     client.close()

def print_audit_summary(global_audit):
    print("Audit Summary:")
    for policy_name, audits in global_audit.items():
        print(f"Policy: {policy_name}")
        for audit in audits:
            print(f"  {audit['display_name']}:")
            for result in audit['results']:
                condition_status = 'Met' if result['condition_met'] else 'Not Met'
                print(f"    {result['condition']}: {condition_status}")

#
# if __name__ == '__main__':
#     ssh_client()
#     print_audit_summary(global_audit)
