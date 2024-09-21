import paramiko
import re
from threading import RLock
from typing import List, Union, Pattern, Optional
import logging
import time
from socket import timeout as SocketTimeout
from cryptography.fernet import Fernet

debug = True
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
            scrub_esc: bool = False,  # New flag to scrub escape characters
            encryption_key_path: str = "./crypto.key"  # Path to the encryption key

    ):
        self.debug_output = True
        self._hostname = hostname
        self._displayname = hostname  # Default display name to hostname initially
        self._client = paramiko.SSHClient()
        self._channel: Optional[paramiko.Channel] = None
        self._output_buffer = ""
        self._accumulation_buffer = ""
        self._meta_data = {}
        self._lock = RLock()
        self._debug = debug
        self._look_for_keys = look_for_keys
        self._timeout = timeout
        self._allow_agent = allow_agent
        self._max_retries = max_retries
        self._retry_interval = retry_interval
        self._prompt_failure = prompt_failure
        self._scrub_esc = scrub_esc  # Initialize scrub_esc flag
        self._encryption_key_path = encryption_key_path  # Path to the encryption key


        # Configure logging
        logging.basicConfig(level=logging.DEBUG if self.debug_output else logging.INFO)
        self._logger = logging.getLogger(f"SSHConnection-{hostname}")
        if self.debug_output:
            self._logger.debug(f"Prompt failure detection set to: {self._prompt_failure}")

        # Apply SSH crypto settings
        self.set_ssh_crypto_settings()

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

    @property
    def debug(self) -> bool:
        with self._lock:
            return self._debug

    # @debug.setter
    # def debug(self, value: bool) -> None:
    #     with self._lock:
    #         self._debug = value
    #         self._logger.setLevel(logging.DEBUG if value else logging.INFO)

    def set_displayname(self, displayname: str) -> None:
        """Sets a human-readable display name for the connection."""
        with self._lock:
            self._displayname = displayname
            if self.debug_output:
                self._logger.debug(f"Display name set to: {self._displayname}")

    def set_meta_data(self, key: str, value: any) -> None:
        with self._lock:
            self._meta_data[key] = value

    def get_meta_data(self, key: str) -> any:
        with self._lock:
            return self._meta_data.get(key)

    def set_ssh_crypto_settings(self) -> None:
        """Sets SSH crypto settings for preferred KEX, ciphers, and keys."""
        if self.debug_output:
            self._logger.debug("Applying SSH crypto settings...")

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
            self._logger.debug("SSH crypto settings applied.")

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
            self._logger.error(f"Error decrypting password: {e}")
            raise RuntimeError("Failed to decrypt password")

    def connect(self, username: str, password: str, port: int = 22, **kwargs) -> None:
        for attempt in range(self._max_retries):
            try:
                # Decrypt password if it is encrypted
                if self.is_encrypted(password):
                    password = self.decrypt_password(password)
                    if self.debug_output:
                        self._logger.debug("Password decrypted successfully.")

                with self._lock:
                    self._logger.info(
                        f"Connecting to {self._hostname}:{port} with username {username} (Attempt {attempt + 1}/{self._max_retries})")
                    self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    if self.debug_output:
                        self._logger.debug("Set missing host key policy")
                        self._logger.debug(
                            f"Attempting connection with look_for_keys={self._look_for_keys}, timeout={self._timeout}, allow_agent={self._allow_agent}")
                    try:
                        self._client.connect(
                            self._hostname,
                            port,
                            username,
                            password,
                            look_for_keys=self._look_for_keys,
                            timeout=self._timeout,
                            allow_agent=self._allow_agent,
                            **kwargs,
                        )
                    except Exception as e:
                        print(e)
                        raise e
                    self._logger.info(f"Connected to {self.hostname}")
                    try:
                        self._channel = self._client.invoke_shell()
                        if self.debug_output:
                            self._logger.debug("Shell invoked successfully")
                    except Exception as e:
                        self._logger.error(f"Invoke shell failed: {e}")
                        raise RuntimeError("Invoke shell failed, host may not support it")
                    self._logger.info(f"Connected to {self._hostname} ({self._displayname})")
                    return  # Connection successful, exit the method
            except paramiko.AuthenticationException:
                self._logger.error("Authentication failed.")
                raise RuntimeError("Authentication failed, please verify your credentials")
            except paramiko.SSHException as e:
                self._logger.error(f"SSHException: {e}")
                if attempt < self._max_retries - 1:
                    self._logger.info(f"Retrying in {self._retry_interval} seconds...")
                    time.sleep(self._retry_interval)
                else:
                    raise RuntimeError(f"Failed to establish SSH connection after {self._max_retries} attempts: {e}")
            except Exception as e:
                self._logger.error(f"Exception during connection: {e}")
                if attempt < self._max_retries - 1:
                    self._logger.info(f"Retrying in {self._retry_interval} seconds...")
                    time.sleep(self._retry_interval)
                else:
                    raise RuntimeError(f"Error during SSH connection after {self._max_retries} attempts: {e}")

    def disconnect(self) -> None:
        with self._lock:
            self._logger.info("Disconnecting...")
            if self._channel:
                try:
                    self._channel.close()
                except Exception as e:
                    self._logger.error(f"Exception during channel close: {e}")
            try:
                self._client.close()
            except Exception as e:
                self._logger.error(f"Exception during client close: {e}")
            self._logger.info("Disconnected.")

    def send_newline(self, expect: Union[str, Pattern], timeout: float = 10,
                         expect_occurrences: int = 1) -> str:
        with self._lock:
            try:
                self._accumulation_buffer = ""  # Reset the accumulation buffer for the new command
                self._logger.debug(f"Sending new line/enter")
                try:
                    self._channel.send("\n")
                except Exception as e:
                    self._logger.error(f"Error in send \\n: {e}")
                    raise e

                if self._prompt_failure:
                    result = self._read_until(expect, timeout, expect_occurrences)
                else:
                    # If prompt failure is set to False, we'll use a different approach
                    result = self._read_with_timeout(timeout)

                if self._scrub_esc:  # Scrub escape characters if the flag is set
                    result = self._scrub_escape_characters(result)

                self._logger.debug(f"Received response for command : {result}")
                return result
            except Exception as e:
                self._logger.error(f"Exception during send_command: {e}")
                raise RuntimeError(f"Failed to send command '{command}': {e}")

    def send_command(self, command: str, expect: Union[str, Pattern], timeout: float = 10,
                     expect_occurrences: int = 1) -> str:
        with self._lock:
            try:
                self._accumulation_buffer = ""  # Reset the accumulation buffer for the new command
                self._logger.debug(f"Sending command: {command}")
                try:
                    if command == "\n":
                        self._channel.send("\n")
                    self._channel.send(command + "\n")
                except Exception as e:
                    self._logger.error(f"Error in send_command: {e}")
                    raise e

                if self._prompt_failure:
                    result = self._read_until(expect, timeout, expect_occurrences)
                else:
                    # If prompt failure is set to False, we'll use a different approach
                    result = self._read_with_timeout(timeout)

                if self._scrub_esc:  # Scrub escape characters if the flag is set
                    result = self._scrub_escape_characters(result)

                # self._logger.debug(f"Received response for command '{command}': {result}")
                return result
            except Exception as e:
                self._logger.error(f"Exception during send_command: {e}")
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
        self._logger.debug(f"Waiting for pattern '{expect.pattern}' {expect_occurrences} times")

        start_time = time.time()
        while True:
            try:
                chunk = self._channel.recv(1024).decode('utf-8')
                if not chunk:
                    raise EOFError("Connection closed by remote host")
                buffer += chunk
                self._accumulation_buffer += chunk
                self._output_buffer += chunk
                # self._logger.debug(f"Received chunk: {chunk}")

                if expect.search(self._accumulation_buffer):
                    occurrences += 1
                    self._logger.debug(f"Pattern '{expect.pattern}' occurrence {occurrences} found")
                    if occurrences >= expect_occurrences:
                        return self._accumulation_buffer

                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Timeout waiting for '{expect.pattern}' after {occurrences} occurrences")
            except SocketTimeout:
                self._logger.error("Socket timeout while waiting for pattern")
                raise TimeoutError(f"Timeout waiting for '{expect.pattern}' after {occurrences} occurrences")
            except Exception as e:
                self._logger.error(f"Exception in _read_until: {e}")
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
                # if self.debug_output:
                #     self._logger.debug(f"Received chunk: {chunk}")

                # Check if we've received the full output
                if "\n" in buffer and not self._channel.recv_ready():
                    time.sleep(0.1)  # Short sleep to ensure no more data is coming
                    if not self._channel.recv_ready():
                        return buffer

                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Timeout waiting for command output")
            except SocketTimeout:
                self._logger.error("Socket timeout while waiting for output")
                raise TimeoutError(f"Timeout waiting for command output")
            except Exception as e:
                self._logger.error(f"Exception in _read_with_timeout: {e}")
                raise RuntimeError(f"Error reading from channel: {e}")

    def _scrub_escape_characters(self, text: str) -> str:
        """Removes ANSI escape sequences and other control characters from the text."""
        if debug:
            self._logger.debug("Scrubbing escape characters from output.")
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


# Usage example with debug mode enabled:
# if __name__ == "__main__":
#     try:
#         with ThreadSafeSSHConnection("10.201.42.1", debug=False, prompt_failure=False, scrub_esc=True) as ssh:
#             ssh.set_displayname("CA-0492-ION-01")
#             ssh._logger.debug("Attempting to connect...")
#             ssh.connect("rtradmin", "Th!$istheW@y")
#             ssh._logger.debug("Connected successfully. Sending commands...")
#             output1 = ssh.send_commands(["set paging off", "dump vpn summary"], expect="CA-0492-ION-01#",
#                                        expect_occurrences=[6, 40])
#             buffer_count = 0
#             for buffer in output1:
#                 buffer_count += 1
#                 print(f"Command output [buffer: {buffer_count}]: {output1[buffer_count - 1]}")
#
#             output2 = ssh.send_command("dump config network", expect="CA-0492-ION-01#", expect_occurrences=1)
#             print(output2)
#
#     except Exception as e:
#         print(f"An error occurred: {e}")
#         import traceback
#
#         traceback.print_exc()
