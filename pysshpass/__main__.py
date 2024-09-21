import sys
import paramiko
import click
import jinja2
import threading
import time
import os
from queue import Queue, Empty

# Ensure log directory exists
if not os.path.exists('./log'):
    os.makedirs('./log')

# Global thread-safe buffer and lock
buffer_lock = threading.Lock()

def read_and_process_output(channel, output_queue, buffer, prompt, prompt_count, log_file):
    """
    Reads output from the SSH channel, logs it, and monitors for specified prompts.

    Args:
        channel (paramiko.Channel): The SSH channel to read from.
        output_queue (Queue): Queue to signal main thread upon prompt detection or channel closure.
        buffer (Queue): Buffer to store output for further processing.
        prompt (str): The prompt string to look for.
        prompt_count (int): Number of prompt occurrences to wait for before stopping.
        log_file (str): Path to the log file.
    """
    counter = 0
    with open(log_file, 'a') as f:
        while True:
            if channel.recv_ready():
                output_chunk = channel.recv(4096).decode('utf-8').replace('\r', '')
                print(f"Received chunk: {output_chunk}")
                f.write(output_chunk)
                f.flush()

                with buffer_lock:
                    buffer.put(output_chunk)

                lines = output_chunk.split("\n")
                for line in lines:
                    if prompt in line:
                        counter += 1
                        if counter >= prompt_count:
                            output_queue.put("Prompt detected.")
                            return

            if channel.closed:
                output_queue.put("Channel closed.")
                return
            time.sleep(0.1)

@click.command()
@click.option('--host', '-h', required=True, help='SSH Host (ip:port)')
@click.option('--user', '-u', required=True, help='SSH Username')
@click.option('--password', '-p', required=True, help='SSH Password')
@click.option('--cmds', '-c', default='', help='Commands to run, separated by comma')
@click.option('--invoke-shell', is_flag=True, help='Invoke shell before running the commands [default=False]')
@click.option('--prompt', default='', help='Prompt to look for before breaking the shell')
@click.option('--prompt-count', default=1, help='Number of prompts to look for before breaking the shell')
@click.option('--timeout', '-t', default=15, help='Command timeout duration in seconds')
@click.option('--disable-auto-add-policy', is_flag=True, default=False,
              help='Disable automatically adding the host key [default=False]')
@click.option('--look-for-keys', is_flag=True, default=False, help='Look for local SSH key [default=False]')
@click.option('--inter-command-time', '-i', default=1, help='Inter-command time in seconds [default is 1 second]')
def main(host, user, password, cmds, invoke_shell, prompt, prompt_count, timeout, disable_auto_add_policy,
               look_for_keys, inter_command_time):
    """
    SSH Client for running remote commands in string mode.

    Sample Usage:
    pysshpass -h "172.16.101.100:22" -u "cisco" -p "cisco" -c "term len 0,show cdp neigh,show int desc" --invoke-shell --prompt "#" --prompt-count 4 -t 10
    """
    # Set log file path
    log_file = os.path.join('./log', f'{host.replace(":", "_")}.log')

    # Initialize SSH client
    client = paramiko.SSHClient()

    # Set host key policy based on user input
    if disable_auto_add_policy:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Modify the transport defaults for key exchange algorithms, ciphers, and host key algorithms
    paramiko.Transport._preferred_kex = (
        "diffie-hellman-group14-sha1",
        "diffie-hellman-group-exchange-sha1",
        "diffie-hellman-group-exchange-sha256",
        "diffie-hellman-group1-sha1",
        "ecdh-sha2-nistp256",
        "ecdh-sha2-nistp384",
        "ecdh-sha2-nistp521",
        "curve25519-sha256",
        "curve25519-sha256@libssh.org",
        "diffie-hellman-group16-sha512",
        "diffie-hellman-group18-sha512"
    )
    paramiko.Transport._preferred_ciphers = (
        "aes128-cbc",
        "aes128-ctr",
        "aes192-ctr",
        "aes256-ctr",
        "aes256-cbc",
        "3des-cbc",
        "aes192-cbc",
        "aes256-gcm@openssh.com",
        "aes128-gcm@openssh.com",
        "chacha20-poly1305@openssh.com",
        "aes256-gcm",
        "aes128-gcm"
    )
    paramiko.Transport._preferred_keys = (
        "ssh-rsa",
        "ssh-dss",
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "ssh-ed25519",
        "rsa-sha2-256",
        "rsa-sha2-512"
    )

    try:
        # Connect to the SSH server
        hostname, port = host.split(':') if ':' in host else (host, 22)
        client.connect(
            hostname=hostname,
            port=int(port),
            username=user,
            password=password,
            look_for_keys=look_for_keys,
            timeout=timeout,
            allow_agent=False  # Ensure we don't use any other key authentication mechanisms
        )
        connect_msg = f"Connected to {host} using the specified algorithms.\n"
        print(connect_msg)
        with open(log_file, 'a') as f:
            f.write(connect_msg)
            f.flush()
    except paramiko.AuthenticationException:
        error_msg = "Authentication failed, please verify your credentials.\n"
        print(error_msg)
        with open(log_file, 'a') as f:
            f.write(error_msg)
            f.flush()
        sys.exit(1)
    except paramiko.SSHException as e:
        error_msg = f"Could not establish SSH connection: {str(e)}\n"
        print(error_msg)
        with open(log_file, 'a') as f:
            f.write(error_msg)
            f.flush()
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unhandled exception: {str(e)}\n"
        print(error_msg)
        with open(log_file, 'a') as f:
            f.write(error_msg)
            f.flush()
        sys.exit(1)

    if cmds:
        command_list = [cmd.strip() for cmd in cmds.split(',') if cmd.strip()]
    else:
        command_list = []

    if invoke_shell:
        try:
            channel = client.invoke_shell()
        except Exception as e:
            error_msg = f"Failed to invoke shell: {str(e)}\n"
            print(error_msg)
            with open(log_file, 'a') as f:
                f.write(error_msg)
                f.flush()
            sys.exit(1)

        output_queue = Queue()
        output_buffer = Queue()
        read_thread = threading.Thread(target=read_and_process_output,
                                       args=(channel, output_queue, output_buffer, prompt, prompt_count, log_file))
        read_thread.daemon = True
        read_thread.start()

        for cmd in command_list:
            cmd_msg = f"Executing command: {cmd}\n"
            print(cmd_msg)
            with open(log_file, 'a') as f:
                f.write(cmd_msg)
                f.flush()

            # If templating is needed, uncomment the following lines and provide variables
            # template = jinja2.Template(cmd)
            # cmd = template.render(variables)

            channel.send(cmd + '\n')
            time.sleep(inter_command_time)

        try:
            reason = output_queue.get(timeout=timeout)
            exit_msg = f"\nExiting: {reason}\n"
            print(exit_msg)
            with open(log_file, 'a') as f:
                f.write(exit_msg)
                f.flush()
        except Empty:
            timeout_msg = "\nExiting due to timeout.\n"
            print(timeout_msg)
            with open(log_file, 'a') as f:
                f.write(timeout_msg)
                f.flush()
            sys.exit()

        channel.close()
    else:
        for cmd in command_list:
            cmd_msg = f"Executing command: {cmd}\n"
            print(cmd_msg)
            with open(log_file, 'a') as f:
                f.write(cmd_msg)
                f.flush()

            # If templating is needed, uncomment the following lines and provide variables
            # template = jinja2.Template(cmd)
            # cmd = template.render(variables)

            try:
                stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                if output:
                    print(output)
                    with open(log_file, 'a') as f:
                        f.write(output)
                        f.flush()
                if error:
                    print(error)
                    with open(log_file, 'a') as f:
                        f.write(error)
                        f.flush()
            except Exception as e:
                error_msg = f"Failed to execute command '{cmd}': {str(e)}\n"
                print(error_msg)
                with open(log_file, 'a') as f:
                    f.write(error_msg)
                    f.flush()

    client.close()

# Entry point
if __name__ == '__main__':
    main()
