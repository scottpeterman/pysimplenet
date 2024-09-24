# PySimpleNet CLI Usage Guide

This guide provides detailed instructions on how to use the command-line interface (CLI) tools provided by PySimpleNet, focusing on the primary utility script `runner.py`. This script allows you to execute automation tasks across multiple devices concurrently, based on an inventory defined in YAML format.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Command-Line Utility (`runner.py`)](#command-line-utility-runnerpy)
  - [Usage](#usage)
  - [Command-Line Options](#command-line-options)
  - [Examples](#examples)
- [Workflow Explanation](#workflow-explanation)
- [Detailed Functionality](#detailed-functionality)
  - [1. Creating the SQLite Database](#1-creating-the-sqlite-database)
  - [2. Device Reachability Check](#2-device-reachability-check)
  - [3. Running Tasks for Each Device](#3-running-tasks-for-each-device)
- [Logging and Output](#logging-and-output)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

## Overview

The `runner.py` script is the primary CLI utility in PySimpleNet. It orchestrates the execution of automation tasks across multiple devices by:

- Converting a YAML inventory file into a SQLite database for efficient querying.
- Allowing you to specify SQL queries to select devices from the inventory.
- Running automation tasks concurrently across multiple devices.
- Logging outputs, errors, and connection failures for troubleshooting.

## Prerequisites

- Python 3.9 or higher.
- Required Python packages (listed in `requirements.txt`).
- Access to network devices (e.g., Cisco IOS devices).
- SSH connectivity to target devices.
- PySimpleNet installed (either via `pip` or cloned from GitHub).

## Installation

If you haven't installed PySimpleNet yet, you can do so via `pip`:

```bash
pip install pysimplenet
```

Alternatively, clone the repository and install dependencies:

```bash
git clone https://github.com/scottpeterman/pysimplenet.git
cd pysimplenet
pip install -r requirements.txt
```

## Command-Line Utility (`runner.py`)

### Usage

The `runner.py` script accepts several command-line options to customize its behavior. Below is the general usage pattern:

```bash
python runner.py [OPTIONS]
```

### Command-Line Options

- `--inventory`: **(Required)** Path to the YAML file containing the inventory.
- `--query`: **(Required)** SQL query to execute on the inventory data.
- `--driver`: **(Required)** Path to the driver YAML file that defines automation actions.
- `--vars`: Path to the variables YAML file (optional).
- `--driver-name`: Driver name to use (default: `cisco_ios`).
- `--timeout`: Command timeout in seconds (default: `10`).
- `--prompt`: Prompt to look for (optional).
- `--prompt-count`: Number of prompts to expect (default: `1`).
- `--look-for-keys`: Look for SSH keys for authentication (flag).
- `--timestamps`: Add timestamps to output (flag).
- `--inter-command-time`: Time to wait between commands in seconds (default: `1.0`).
- `--pretty`: Enable pretty output (flag).
- `--output-root`: Root directory for all output files (default: `./output`).
- `--num-processes`: Number of processes to run concurrently (default: `4`).

### Examples

#### Example 1: Run Automation on All Devices

```bash
python runner.py \
  --inventory project/inventory/home_inventory.yaml \
  --query "SELECT * FROM devices" \
  --driver project/drivers/tests/cdp_interfaces_audit.yml \
  --vars project/vars/global_vars.yml \
  --driver-name cisco_ios \
  --timeout 15 \
  --prompt "#" \
  --prompt-count 2 \
  --inter-command-time 1.0 \
  --pretty \
  --output-root ./output \
  --num-processes 4
```

#### Example 2: Run Automation on Specific Devices

```bash
python runner.py \
  --inventory project/inventory/home_inventory.yaml \
  --query "SELECT * FROM devices WHERE role_id = 2" \
  --driver project/drivers/tests/linux.yml \
  --driver-name linux \
  --timeout 10 \
  --prompt "$" \
  --num-processes 2
```

#### Example 3: Use Variables File and Look for SSH Keys

```bash
python runner.py \
  --inventory project/inventory/home_inventory.yaml \
  --query "SELECT * FROM devices WHERE hostname LIKE 'router%'" \
  --driver project/drivers/tests/configure_routes_home.yml \
  --vars project/vars/router_vars.yml \
  --driver-name cisco_ios \
  --timeout 20 \
  --look-for-keys \
  --timestamps \
  --output-root ./output \
  --num-processes 3
```

## Workflow Explanation

1. **Inventory Processing**: The script reads the specified YAML inventory file and converts it into a SQLite database (`.db` file). This database includes tables for devices, credentials, platforms, roles, sites, and vendors.

2. **SQL Query Execution**: The provided SQL query is executed against the SQLite database to select the devices you want to run automation tasks on.

3. **Device Reachability Check**: Before executing tasks, the script checks if each device is reachable on port 22 (SSH).

4. **Concurrent Execution**: The script uses `ProcessPoolExecutor` to run tasks across multiple devices concurrently. The number of concurrent processes is controlled by the `--num-processes` option.

5. **Automation Execution**: For each device, the script runs the `simplenet` module, passing the necessary parameters.

6. **Logging and Output**: Outputs are logged to the console and can be saved to files specified in your driver configurations.

## Detailed Functionality

### 1. Creating the SQLite Database

The `create_sqlite_db` function reads the inventory YAML file and creates a SQLite database for efficient querying.

- **Tables Created**:
  - `devices`
  - `credentials`
  - `platforms`
  - `roles`
  - `sites`
  - `vendors`
  - `device_credentials`
- **View Created**:
  - `device_details`: Joins devices with related tables for easier querying.

### 2. Device Reachability Check

Before executing any automation tasks, the script checks if each device is reachable on port 22 using the `check_device_reachability` function.

- If a device is not reachable, it's logged to `connection_failures.log`.
- The script skips unreachable devices to save time.

### 3. Running Tasks for Each Device

For each device that passes the reachability check:

- The `run_for_device` function constructs a command to execute the `simplenet` module with appropriate parameters.
- The command includes options like inventory database path, device-specific query, driver file, driver name, timeouts, prompts, etc.
- The function uses `subprocess.Popen` to execute the command and streams the output in real-time.
- Exit codes are checked to determine if the execution was successful. Non-zero exit codes are logged to `error.log`.

## Logging and Output

- **Standard Output**: The script prints progress and execution details to the console.
- **Logs**:
  - `error.log`: Records devices that returned a non-zero exit code.
  - `connection_failures.log`: Records devices that are unreachable on port 22.
- **Output Files**: Outputs from automation tasks are saved to files as specified in your driver configurations, typically under the `./output` directory.

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](https://github.com/scottpeterman/pysimplenet/blob/main/CONTRIBUTING.md) for guidelines on how to get involved.

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).

## Support

For support or questions, please open an issue on the [GitHub repository](https://github.com/scottpeterman/pysimplenet/issues) or contact us at [scottpeterman@gmail.com](mailto:scottpeterman@gmail.com).

---

**Note**: Ensure that the paths and filenames used in the examples match your actual project structure.

---

# Additional Details

## Command-Line Options Explained

- **`--inventory`**: Path to your inventory YAML file. This file should contain details about your devices, credentials, platforms, roles, sites, and vendors.

- **`--query`**: SQL query to select devices from the inventory database. For example, `SELECT * FROM devices WHERE platform_id = 1`.

- **`--driver`**: Path to the driver YAML file that defines the automation actions to be performed on each device.

- **`--vars`**: (Optional) Path to a variables YAML file. This can include global variables or device-specific variables used in your driver templates.

- **`--driver-name`**: Specifies which driver to use from your driver YAML file, if multiple are defined. Default is `cisco_ios`.

- **`--timeout`**: Command timeout in seconds. Adjust this based on network latency and the expected response time of your devices.

- **`--prompt`**: The expected command prompt on your devices. This helps the script know when a command has completed.

- **`--prompt-count`**: Number of prompts to expect during command execution. This can help in scenarios where multiple prompts are involved.

- **`--look-for-keys`**: If set, the script will attempt to use SSH keys for authentication, in addition to passwords specified in the inventory.

- **`--timestamps`**: If set, timestamps will be added to the output, which can be helpful for logging and auditing purposes.

- **`--inter-command-time`**: Time in seconds to wait between commands. Useful if devices require a short delay between commands.

- **`--pretty`**: Enables pretty output formatting, which can make logs and outputs easier to read.

- **`--output-root`**: Root directory where output files will be saved. Default is `./output`.

- **`--num-processes`**: Number of concurrent processes to run. Increasing this can speed up execution but may consume more system resources.

## Understanding the Workflow

1. **Start Time Logging**: The script logs the start time of the execution for benchmarking purposes.

2. **Inventory Conversion**: The YAML inventory is converted to a SQLite database, which allows for complex SQL queries and efficient data access.

3. **SQL Query Execution**: The specified SQL query is executed against the database to fetch the list of devices.

4. **Device Processing Loop**: For each device:

   - **Reachability Check**: The script checks if the device is reachable on port 22.
   - **Command Construction**: A command is constructed to run the `simplenet` module with device-specific parameters.
   - **Subprocess Execution**: The command is executed using a subprocess, and the output is streamed to the console.
   - **Error Handling**: Non-zero exit codes are logged, and failed devices are counted.

5. **Concurrent Execution**: The `ProcessPoolExecutor` is used to run device tasks concurrently, controlled by the `--num-processes` option.

6. **Completion Logging**: The script logs the stop time and calculates the total execution time.

7. **Summary Output**: A summary is printed, showing the number of devices processed, failed devices, and execution times.

## Tips for Effective Use

- **Adjust Concurrency**: Experiment with the `--num-processes` option to find the optimal concurrency level for your system.

- **Use Specific Queries**: Tailor your SQL queries to target specific groups of devices, reducing unnecessary load and focusing on relevant tasks.

- **Monitor Logs**: Regularly check `error.log` and `connection_failures.log` to troubleshoot issues.

- **Customize Timeouts**: Adjust `--timeout` and `--inter-command-time` based on your network conditions and device responsiveness.

- **Secure Your Credentials**: Ensure that sensitive information like passwords is securely managed and, if possible, use SSH keys (`--look-for-keys`).

- **Leverage Variables**: Use the `--vars` option to pass variables that can be used within your driver templates for dynamic content.

- **Test Drivers Individually**: Before running tasks across multiple devices, test your driver configurations on a single device to ensure they work as expected.

## Example Inventory YAML Structure

```yaml
devices:
  - id: 1
    hostname: "router1"
    mgmt_ip: "192.168.1.1"
    model: "ISR4451"
    serial_number: "FTX1234X1YZ"
    timestamp: "2023-09-25T12:34:56"
    platform_id: 1
    role_id: 1
    site_id: 1
    vendor_id: 1
    credential_ids:
      - 1
credentials:
  - id: 1
    name: "default_credential"
    username: "admin"
    password: "password123"
platforms:
  - id: 1
    name: "cisco_ios"
roles:
  - id: 1
    name: "core_router"
sites:
  - id: 1
    name: "HQ"
    location: "New York"
vendors:
  - id: 1
    name: "Cisco"
```

## Example Driver YAML Structure

```yaml
drivers:
  cisco_ios:
    error_string: "Invalid input detected"
    output_path: "./output/{{ hostname }}_output.txt"
    output_mode: "append"
    prompt_count: 2
    actions:
      - action: "send_command"
        display_name: "Show Version"
        command: "show version"
        expect: "#"
        output_path: "./output/{{ hostname }}_version.txt"
        output_mode: "overwrite"
```

---

By following this guide, you should be able to effectively use the `runner.py` CLI utility to automate tasks across your network devices using PySimpleNet.