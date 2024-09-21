import threading
import time
from colorama import Fore, Style, init
from queue import Queue, Empty
from threading import Lock


def read_and_process_output(channel, output_queue, buffer, expect, prompt, log_file, error_string, buffer_lock,
                            global_prompt_count, pretty=False, timestamps=False, timeout=120):
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

    start_time = time.time()
    first_prompt_received = False
    prompt_received_event = threading.Event()

    with open(log_file, 'a') as f:
        while True:
            if channel.recv_ready():
                output_chunk = channel.recv(4096).decode('utf-8').replace('\r', '')
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"{timestamp} - {output_chunk}")
                f.flush()

                with buffer_lock:
                    buffer.put(output_chunk)

                if error_string and error_string in output_chunk:
                    output_queue.put(f"Error detected: {error_string}")
                    return

                lines = output_chunk.split("\n")
                for line in lines:
                    if prompt in line:
                        with buffer_lock:
                            global_prompt_count[0] += 1
                        print_colored(
                            f"Reader [{timestamp}] - Prompt '{prompt}' detected. Current count: {global_prompt_count[0]}",
                            Fore.YELLOW, Fore.LIGHTYELLOW_EX)

                        if not first_prompt_received:
                            first_prompt_received = True
                            prompt_received_event.set()

                        if global_prompt_count[0] >= global_prompt_count[1]:
                            output_queue.put("Prompt count reached.")
                            return

                    if expect in line:
                        output_queue.put("Command completed.")
                        return

            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                output_queue.put("Timeout expired.")
                return

            if channel.closed:
                output_queue.put("Channel closed.")
                return

            if not first_prompt_received:
                # Wait for the first prompt or timeout
                if prompt_received_event.wait(timeout=1):  # Wait for 1 second
                    continue
                elif elapsed_time > timeout:
                    output_queue.put("Timeout expired while waiting for first prompt.")
                    return
            else:
                time.sleep(0.1)