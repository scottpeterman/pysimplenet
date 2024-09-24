import logging
logging.basicConfig(level=logging.CRITICAL)

import traceback

import paramiko
import re
from threading import RLock
from typing import List, Union, Pattern, Optional
import time
from socket import timeout as SocketTimeout
from cryptography.fernet import Fernet

# Ensure stdout and stderr use UTF-8 encoding
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
debug = False




class ThreadSafeSSHConnection:
    def __init__(
            self,
            hostname: str,
            debug: bool = False,
            look_for_keys: bool = False,
            timeout: int = 10,
            allow_agent: bool = False,
            max_retries: int = 3,
            retry_interval: int = 5,
            prompt_failure: bool = True,
            scrub_esc: bool = False,  # Flag to scrub escape characters
            encryption_key_path: str = "./crypto.key"  # Path to the encryption key
    ):

        self.debug_output = debug
        # if self.debug_output:
        #     print(.setLevel(logging.DEBUG)
        # else:
        #     print(.setLevel(logging.INFO)

        # Validate hostname
        if not hostname or not isinstance(hostname, str):
            raise ValueError("Invalid hostname provided")
        self._hostname = hostname
        self._displayname = hostname  # Default display name to hostname initially

        # Initialize other attributes
        self._client = paramiko.SSHClient()
        self._channel: Optional[paramiko.Channel] = None
        self._output_buffer = ""
        self._accumulation_buffer = ""
        self._meta_data = {}
        self._lock = RLock()
        self._look_for_keys = look_for_keys
        self._timeout = timeout
        self._allow_agent = allow_agent
        self._max_retries = max_retries
        self._retry_interval = retry_interval
        self._prompt_failure = prompt_failure
        self._scrub_esc = scrub_esc
        self._encryption_key_path = encryption_key_path

        # Apply SSH crypto settings
        self.set_ssh_crypto_settings()

        print(f"Initialized SSHConnection to {self._hostname}")

    @property
    def hostname(self) -> str:
        with self._lock:
            return self._hostname

    @property
    def client(self) -> paramiko.SSHClient:
        with self._lock:
            return self._client

    @property
    def channel(self) -> Optional[paramiko.Channel]:
        with self._lock:
            return self._channel

    @property
    def meta_data(self) -> dict:
        with self._lock:
            return self._meta_data.copy()

    # @property
    # def debug(self) -> bool:
    #     with self._lock:
    #         return self._debug

    def set_displayname(self, displayname: str) -> None:
        """Sets a human-readable display name for the connection."""
        with self._lock:
            self._displayname = displayname
            if self.debug_output:
                print(f"Display name set to: {self._displayname}")

    def set_meta_data(self, key: str, value: any) -> None:
        with self._lock:
            self._meta_data[key] = value

    def get_meta_data(self, key: str) -> any:
        with self._lock:
            return self._meta_data.get(key)

    def set_ssh_crypto_settings(self) -> None:
        """Sets SSH crypto settings for preferred KEX, ciphers, and keys."""
        if self.debug_output:
            print("Applying SSH crypto settings...")

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
        if self.debug_output:
            print("SSH crypto settings applied.")

    @staticmethod
    def is_encrypted(password: str) -> bool:
        """Checks if a password is encrypted."""
        return password.startswith('gAAAAA')

    def decrypt_password(self, encrypted_password: str) -> str:
        """Decrypts an encrypted password using the provided key."""
        try:
            with open(self._encryption_key_path, "r") as fh:
                key = str(fh.read()).strip()
            fernet = Fernet(key)
            return fernet.decrypt(encrypted_password.encode()).decode()
        except Exception as e:
            print(f"Error decrypting password: {e}")
            raise RuntimeError("Failed to decrypt password")

    def connect(self, username: str, password: str, port: int = 22, look_for_keys = False, timeout = 10,  allow_agent = False):
                #alidate input parameters
        if not username or not isinstance(username, str):
            raise ValueError("Invalid username provided")
        if password is None or not isinstance(password, str):
            raise ValueError("Invalid password provided")
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise ValueError(f"Invalid port number: {port}")
        if not isinstance(self._hostname, str) or not self._hostname:
            raise ValueError(f"Invalid hostname: {self._hostname}")
        if not isinstance(self._look_for_keys, bool):
            raise ValueError(f"Invalid value for look_for_keys: {self._look_for_keys}")
        if not isinstance(self._allow_agent, bool):
            raise ValueError(f"Invalid value for allow_agent: {self._allow_agent}")
        if not isinstance(self._timeout, (int, float)) or self._timeout <= 0:
            raise ValueError(f"Invalid timeout value: {self._timeout}")

        # Log the parameters (excluding the password)
        print(f"Connecting with parameters:")
        print(f"Hostname: {self._hostname}")
        print(f"Port: {port}")
        print(f"Username: {username}")
        print(f"Look for keys: {self._look_for_keys}")
        print(f"Allow agent: {self._allow_agent}")
        print(f"Timeout: {self._timeout}")
        print(f"Max retries: {self._max_retries}")
        print(f"Retry interval: {self._retry_interval}")
        print(f"Prompt failure: {self._prompt_failure}")
        # print(f"Additional kwargs: {kwargs}")

        for attempt in range(self._max_retries):
            try:
                # Decrypt password if it is encrypted
                if self.is_encrypted(password):
                    password = self.decrypt_password(password)
                    print("Password decrypted successfully.")

                with self._lock:
                    print(
                        f"Connecting to {self._hostname}:{port} with username '{username}' (Attempt {attempt + 1}/{self._max_retries})"
                    )
                    self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    print(
                        f"Connection parameters: look_for_keys={self._look_for_keys}, timeout={self._timeout}, allow_agent={self._allow_agent}"
                    )
                    try:
                    # Attempt connection
                        self._client.connect(
                            hostname=self.hostname,
                            port=port,
                            username=username,
                            password=password,
                            look_for_keys=look_for_keys,
                            timeout=timeout,
                            allow_agent=allow_agent,
                            # **kwargs,
                        )
                    except Exception as e:
                        print(f"Paramiko connect failuer: (e)")
                        traceback.print_exc()
                    # print(f"Connected to {self._hostname}")

                    # Invoke shell
                    self._channel = self._client.invoke_shell()
                    # print("SSH shell invoked successfully")

                    return  # Connection successful, exit the method

            except paramiko.AuthenticationException as auth_error:
                print(f"Authentication failed: {auth_error}")
                raise auth_error
            except paramiko.SSHException as ssh_error:
                print(f"SSHException on attempt {attempt + 1}: {ssh_error}")
                if attempt < self._max_retries - 1:
                    print(f"Retrying in {self._retry_interval} seconds...")
                    time.sleep(self._retry_interval)
                else:
                    raise ssh_error
            except SocketTimeout as timeout_error:
                print(f"Socket timeout on attempt {attempt + 1}: {timeout_error}")
                if attempt < self._max_retries - 1:
                    print(f"Retrying in {self._retry_interval} seconds...")
                    time.sleep(self._retry_interval)
                else:
                    raise timeout_error
            except Exception as e:
                print(f"Exception on attempt {attempt + 1}: {e}")
                if attempt < self._max_retries - 1:
                    print(f"Retrying in {self._retry_interval} seconds...")
                    time.sleep(self._retry_interval)
                else:
                    raise RuntimeError(f"Connection failed after {self._max_retries} attempts: {e}")

    def disconnect(self) -> None:
        with self._lock:
            print("Disconnecting...")
            if self._channel:
                try:
                    self._channel.close()
                    print("Channel closed successfully")
                except Exception as e:
                    print(f"Exception during channel close: {e}")
            try:
                self._client.close()
                print("Client closed successfully")
            except Exception as e:
                print(f"Exception during client close: {e}")
            print("Disconnected.")

    def send_newline(self, expect: Union[str, Pattern], timeout: float = 10,
                     expect_occurrences: int = 1) -> str:
        with self._lock:
            try:
                self._accumulation_buffer = ""  # Reset the accumulation buffer for the new command
                print("Sending new line/enter")
                self._channel.send("\n")

                if self._prompt_failure:
                    result = self._read_until(expect, timeout, expect_occurrences)
                else:
                    result = self._read_with_timeout(timeout)

                if self._scrub_esc:  # Scrub escape characters if the flag is set
                    result = self._scrub_escape_characters(result)

                print(f"Received response: {result}")
                return result
            except Exception as e:
                print(f"Exception during send_newline: {e}")
                raise RuntimeError(f"Failed to send newline: {e}")

    def send_command(self, command: str, expect: Union[str, Pattern], timeout: float = 10,
                     expect_occurrences: int = 1) -> str:
        with self._lock:
            try:
                self._accumulation_buffer = ""  # Reset the accumulation buffer for the new command
                print(f"Sending command: {command}")
                self._channel.send(command + "\n")

                if self._prompt_failure:
                    result = self._read_until(expect, timeout, expect_occurrences)
                else:
                    result = self._read_with_timeout(timeout)

                if self._scrub_esc:  # Scrub escape characters if the flag is set
                    result = self._scrub_escape_characters(result)

                # print(f"Received response for command '{command}': {result}")
                return result
            except Exception as e:
                print(f"Exception during send_command: {e}")
                raise RuntimeError(f"Failed to send command '{command}': {e}")

    def send_commands(self, commands: List[str], expect: Union[str, Pattern], timeout: float = 10,
                      expect_occurrences: Union[int, List[int]] = 1) -> List[str]:
        with self._lock:
            outputs = []
            if isinstance(expect_occurrences, int):
                expect_occurrences = [expect_occurrences] * len(commands)
            elif len(expect_occurrences) != len(commands):
                raise ValueError("The length of expect_occurrences must match the length of commands")

            for command, occurrences in zip(commands, expect_occurrences):
                output = self.send_command(command, expect, timeout, occurrences)
                outputs.append(output)
            return outputs

    def _read_until(self, expect: Union[str, Pattern], timeout: float, expect_occurrences: int) -> str:
        buffer = ""
        occurrences = 0  # Track the number of times the expected pattern is found
        if isinstance(expect, str):
            expect = re.compile(re.escape(expect))

        self._channel.settimeout(timeout)
        print(f"Waiting for pattern '{expect.pattern}' {expect_occurrences} times")

        start_time = time.time()
        while True:
            try:
                chunk = self._channel.recv(1024).decode('utf-8')
                if not chunk:
                    raise EOFError("Connection closed by remote host")
                buffer += chunk
                self._accumulation_buffer += chunk
                self._output_buffer += chunk
                # print(f"Received chunk: {chunk}")

                if expect.search(self._accumulation_buffer):
                    occurrences += 1
                    print(f"Pattern '{expect.pattern}' occurrence {occurrences} found")
                    if occurrences >= expect_occurrences:
                        return self._accumulation_buffer

                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Timeout waiting for '{expect.pattern}' after {occurrences} occurrences")
            except SocketTimeout:
                print("Socket timeout while waiting for pattern")
                raise TimeoutError(f"Timeout waiting for '{expect.pattern}' after {occurrences} occurrences")
            except Exception as e:
                print(f"Exception in _read_until: {e}")
                raise RuntimeError(f"Error reading from channel: {e}")

    def _read_with_timeout(self, timeout: float) -> str:
        buffer = ""
        start_time = time.time()
        self._channel.settimeout(timeout)

        while True:
            try:
                chunk = self._channel.recv(1024).decode('utf-8')
                if not chunk:
                    raise EOFError("Connection closed by remote host")
                buffer += chunk
                self._accumulation_buffer += chunk
                self._output_buffer += chunk
                # print(f"Received chunk: {chunk}")

                # Check if we've received the full output
                if "\n" in buffer and not self._channel.recv_ready():
                    time.sleep(0.1)  # Short sleep to ensure no more data is coming
                    if not self._channel.recv_ready():
                        return buffer

                if time.time() - start_time > timeout:
                    raise TimeoutError("Timeout waiting for command output")
            except SocketTimeout:
                print("Socket timeout while waiting for output")
                raise TimeoutError("Timeout waiting for command output")
            except Exception as e:
                print(f"Exception in _read_with_timeout: {e}")
                raise RuntimeError(f"Error reading from channel: {e}")

    def _scrub_escape_characters(self, text: str) -> str:
        """Removes ANSI escape sequences and other control characters from the text."""
        if self.debug_output:
            print("Scrubbing escape characters from output.")
        ansi_escape = re.compile(r'(?:\x1B[@-_][0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def retrieve_buffer(self) -> str:
        with self._lock:
            return self._output_buffer

    def clear_buffer(self) -> None:
        with self._lock:
            self._output_buffer = ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def get_transport(self) -> Optional[paramiko.Transport]:
        with self._lock:
            return self._client.get_transport()

    def set_missing_host_key_policy(self, policy: paramiko.MissingHostKeyPolicy) -> None:
        with self._lock:
            self._client.set_missing_host_key_policy(policy)

    def get_host_keys(self) -> paramiko.HostKeys:
        with self._lock:
            return self._client.get_host_keys()

    def set_log_channel(self, name: str) -> None:
        with self._lock:
            self._client.set_log_channel(name)

if __name__ == "__main__":
    try:
        ssh_conn = ThreadSafeSSHConnection("172.16.101.100", debug=True)
        ssh_conn.connect("cisco", "cisco")
        output = ssh_conn.send_command("show users", expect='#', timeout=5)
        print(output)
        ssh_conn.disconnect()
    except Exception as e:
        print(f"An error occurred: {e}")