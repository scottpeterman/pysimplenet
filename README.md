# PySimpleNet

PySimpleNet is a powerful and lightweight network automation toolkit that allows you to efficiently automate complex network, IOT and other SSH operations using a simple and intuitive interface. This tool is designed with flexibility in mind, supporting various network devices and protocols.

## Key Features

- **YAML-Driven Configuration**: Easily define actions and workflows using YAML files.
- **CLI and GUI Tools**: Choose between command-line interface or graphical user interface based on your preference.
- **Device Drivers**: Support for multiple network device types (e.g., Cisco IOS).
- **Automation Actions**: Send commands, loop through commands, audit configurations, and more.
- **Extensible Schema**: Define custom actions and extend the existing schema as needed.
- **Concurrent Execution**: Run tasks across multiple devices concurrently to save time.
- **Data Persistence**: Use SQLite databases for inventory and device data management.
- **Visual YAML Editor**: Use the GUI editor to create and modify YAML configuration files easily.
- **Debugger Tool**: Visually debug and step through automation workflows.

## Screenshots

### Full Interface
![Full GUI](https://raw.githubusercontent.com/scottpeterman/pysimplenet/refs/heads/main/screenshots/gui_full.png)

### GUI Debug Mode
![GUI Debug Mode](https://raw.githubusercontent.com/scottpeterman/pysimplenet/refs/heads/main/screenshots/gui-debug.png)

### TTP Parsing Example
![TTP Parsing Example](https://raw.githubusercontent.com/scottpeterman/pysimplenet/refs/heads/main/screenshots/gui_ttp.png)

### Inventory Management
![Inventory Management](https://raw.githubusercontent.com/scottpeterman/pysimplenet/refs/heads/main/screenshots/inventory1.png)

### Linux Device Interface
![Linux Device Interface 1](https://raw.githubusercontent.com/scottpeterman/pysimplenet/refs/heads/main/screenshots/linux1.png)
![Linux Device Interface 2](https://raw.githubusercontent.com/scottpeterman/pysimplenet/refs/heads/main/screenshots/linux2.png)

---

# PySimpleNet

[![PyPI version](https://badge.fury.io/py/pysimplenet.svg)](https://pypi.org/project/pysimplenet/)
[![License: GPLv3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

PySimpleNet is a powerful and lightweight network automation toolkit that allows you to efficiently automate complex network, IoT, REST API, and other SSH operations using a simple and intuitive interface. This tool is designed with flexibility in mind, supporting various network devices, protocols, and API interactions.

## Key Features

- **YAML-Driven Configuration**: Easily define actions and workflows using YAML files.
- **CLI and GUI Tools**: Choose between command-line interface or graphical user interface based on your preference.
- **Device Drivers**: Support for multiple network device types (e.g., Cisco IOS, Linux).
- **Automation Actions**: Send commands, loop through commands, audit configurations, make REST API calls, and more.
- **REST API Integration**: Automate interactions with RESTful APIs using `rest_api` and `rest_api_loop` actions.
- **Extensible Schema**: Define custom actions and extend the existing schema as needed.
- **Concurrent Execution**: Run tasks across multiple devices and APIs concurrently to save time.
- **Data Persistence**: Use SQLite databases for inventory and device data management.
- **Visual YAML Editor**: Use the GUI editor to create and modify YAML configuration files easily.
- **Debugger Tool**: Visually debug and step through automation workflows.

## Prerequisites

- Python 3.9 or higher
- Required Python packages (listed in `requirements.txt`)
- Access to network devices (e.g., Cisco IOS devices)
- SSH connectivity to target devices
- PyQt6 (for GUI tools)
- Access to RESTful APIs (if using REST API actions)

## Installation

You can install PySimpleNet via `pip`:

```bash
pip install pysimplenet
```

Alternatively, clone the repository and install:

```bash
git clone https://github.com/scottpeterman/pysimplenet.git
cd pysimplenet
pip install -r requirements.txt
```

## Usage

### Command-Line Interface (CLI)

#### Running Automation Tasks

Use the `simplenet-runner` command to execute automation tasks defined in your YAML driver files.
- Or runner.py if in development or running from source
```bash
simplenet-runner --inventory project/inventory/home_inventory.db --query "SELECT * FROM devices" --driver project/drivers/tests/cdp_interfaces_audit.yml
```

### Graphical User Interface (GUI)

#### Launching the Main GUI

```bash
simplenet-gui
```

#### Launching the Debugger GUI Tool

```bash
vsndebug
```

## Configuration

All configurations are done through YAML files. Below are sample configurations for both device interactions and REST API calls.

### Sample Driver Configuration for Device Interaction (`cdp_interfaces_audit.yml`)

```yaml
drivers:
  cisco_ios:
    error_string: "Invalid input detected"
    output_path: "./output/{{ hostname }}_version_check.txt"
    output_mode: "append"
    prompt_count: 4
    actions:
      - action: "send_command"
        display_name: "Set Terminal Length"
        command: "term len 0"
        expect: "#"
      - action: "send_command"
        display_name: "Show CDP Neighbors Detail"
        command: "show cdp neighbors detail"
        expect: "#"
        output_path: "./output/{{ hostname }}_cdp_neighbors.txt"
        output_mode: "overwrite"
        ttp_path: "./project/templates/ios_show_cdp_neighbors.ttp"
        store_query:
          query: "[][]"
          variable_name: "cdp_neighbors"
      - action: "send_command_loop"
        display_name: "Loop Through Interfaces"
        variable_name: "cdp_neighbors"
        key_to_loop: "interface"
        command_template: "show interface [{ interface }]"
        expect: "#"
        output_path: "./output/{{ hostname }}_interface_details.txt"
        output_mode: "append"
        parse_output: true
        use_named_list:
          list_name: "interface_mtu"
          item_key: "mtu"
          ttp_path: "./project/templates/interface_mtu_switch.ttp"
          store_query:
            query: "[][]"
            variable_name: "interface_mtu"
      - action: "audit_loop"
        display_name: "Check MTU for Interfaces with CDP Neighbors"
        policy_name: "MTU Check for CDP Neighbors"
        variable_name: "interface_mtu"
        key_to_check: "interface"
        target_value: "1500"
        query: '"{{ hostname }}".action_variables.interface_mtu[*].mtu[*]'
        pass_if:
          - check_type: jmespath
            key_to_check: mtu
            name: Check if MTU is 1500 for CDP Neighbor Interfaces
            operator:
              type: is_equal
              value: '1500'
            query: mtu[*]
      - action: "print_audit"
        display_name: "CDP Neighbor MTU Audit"
        output_file_path: "./output/{{ hostname }}_cdp_mtu_audit.yaml"
        format: "both"
```

### Sample Driver Configuration for REST API Interaction (`rest_api_example.yml`)

```yaml
drivers:
  flask_test:
    error_string: "400"  # Use a generic error code for failures
    actions:
      # 1. Action to log in and store the JWT token
      - action: "rest_api"
        display_name: "Login to Flask API"
        method: "POST"
        url: "http://127.0.0.1:5000/login"
        verify: "false"
        headers:
          Content-Type: "application/json"
        body:
          username: "testuser"
          password: "password123"
        expect: "200"
        store_query:
          query: "access_token"  # Retrieve the JWT token from the login response
          variable_name: "jwt_token"  # Store the token in the global data store

      # 2. Action to retrieve all devices and store their IDs
      - action: "rest_api"
        display_name: "Get Device List"
        method: "GET"
        url: "http://127.0.0.1:5000/devices"
        verify: "false"
        headers:
          Content-Type: "application/json"
          Authorization: "Bearer action_variables.jwt_token"  # Use the stored JWT token
        expect: "200"
        store_query:
          query: "[]"  # Store the list of devices
          variable_name: "devices"

      # 3. Loop action to retrieve each device separately
      - action: "rest_api_loop"
        display_name: "Retrieve Each Device"
        method: "GET"
        url: "http://127.0.0.1:5000/devices/[{ id }]"  # The URL will dynamically use the device_id
        verify: "false"
        headers:
          Content-Type: "application/json"
          Authorization: "Bearer action_variables.jwt_token"  # Use the stored JWT token
        variable_name: "devices"  # The global variable containing the devices
        key_to_loop: "id"  # Loop over the device IDs
        expect: "200"
        store_query:
          query: "name"  # Store the device name from each response
          variable_name: "device_names"
        output_path: "./output/device_details.json"
        output_mode: "overwrite"  # Overwrite the file for each new run
```

### Inventory File (`home_inventory.yaml`)

```yaml
devices:
  - id: 1
    hostname: "router1"
    mgmt_ip: "192.168.1.1"
    device_type: "cisco_ios"
    credential_ids:
      - 1
credentials:
  - id: 1
    username: "admin"
    password: "password"
```

### Variables File (Optional)

Variables can be defined in YAML files located under `project/vars/`.

## Schema Explanation

The schema defines the structure of the YAML configuration files used by the automation tool.

### Actions

#### `rest_api`

Performs a REST API call.

- **Fields**:
  - `display_name` (required): A friendly name for the action.
  - `method` (required): HTTP method (`GET`, `POST`, `PUT`, `DELETE`, etc.).
  - `url` (required): The API endpoint URL.
  - `headers` (optional): HTTP headers to include in the request.
  - `body` (optional): Data to send in the body of the request (for `POST`, `PUT`, etc.).
  - `verify` (optional): SSL verification (`true` or `false`).
  - `expect` (optional): Expected HTTP status code.
  - `store_query` (optional): Stores data from the response into variables.
    - **Fields**:
      - `query`: The JMESPath query to extract data.
      - `variable_name`: The name of the variable to store data.

#### `rest_api_loop`

Performs REST API calls in a loop based on variables.

- **Fields**:
  - Same as `rest_api`, plus:
    - `variable_name`: The variable to loop through.
    - `key_to_loop`: The key within the variable to iterate over.
    - `url` can include placeholders to be replaced with looped values.

### Existing Actions

- **`send_command`**: Sends a single command to the device.
- **`send_command_loop`**: Sends a command template in a loop based on variables.
- **`audit_loop`**: Audits configurations based on conditions.
- **`print_audit`**: Outputs the audit results.

## Components

The solution consists of several Python scripts and modules that work together to perform network automation tasks, including REST API interactions.

### 1. Runner Script (`simplenet/cli/runner.py`)

Orchestrates the overall automation process.

- **Functions**:
  - `create_sqlite_db()`: Converts YAML inventory to SQLite database.
  - `check_device_reachability()`: Verifies if devices are reachable.
  - `run_for_device()`: Executes automation tasks for a single device.
  - `main()`: Main Click command.

### 2. Simplenet Module (`simplenet/cli/simplenet.py`)

Handles the execution of automation tasks for individual devices and APIs.

- **Functions**:
  - `run_automation_for_device()`: Runs automation tasks.
  - `main()`: Main Click command for single-device automation.

### 3. Command Executor Library (`simplenet/cli/command_executor2.py`)

Executes individual actions defined in the driver, including REST API actions.

- **Functions**:
  - `execute_commands()`: Main function to execute a list of actions.
  - `handle_send_command_action()`: Handles `send_command` actions.
  - `handle_send_command_loop()`: Handles `send_command_loop` actions.
  - `handle_rest_api_action()`: Handles `rest_api` actions.
  - `handle_rest_api_loop_action()`: Handles `rest_api_loop` actions.
  - `handle_audit_action()`: Performs audit checks.
  - `handle_print_audit_action()`: Outputs audit results.

### 4. GUI Editor Tool (`simplenet/gui/main_gui.py`)

A PyQt6-based application to create and modify YAML configuration files.

- **Usage**:

  ```bash
  simplenet-gui
  ```

- **Features**:
  - Visual YAML editing.
  - Schema validation.
  - Action management.
  - YAML preview.
  - File operations.
  - Integration with the runner.

### 5. Debugger GUI Tool (`simplenet/gui/vsndebug.py`)

Visually debug and step through automation workflows.

- **Usage**:

  ```bash
  vsndebug
  ```

- **Features**:
  - Step-by-step execution.
  - Variable inspection.
  - Breakpoint setting.
  - Output monitoring.
  - Error handling.

## Examples

### Example: REST API Login and Data Retrieval

```yaml
- action: "rest_api"
  display_name: "Login to API"
  method: "POST"
  url: "https://api.example.com/login"
  headers:
    Content-Type: "application/json"
  body:
    username: "user"
    password: "pass"
  expect: "200"
  store_query:
    query: "token"
    variable_name: "api_token"

- action: "rest_api"
  display_name: "Get Devices"
  method: "GET"
  url: "https://api.example.com/devices"
  headers:
    Authorization: "Bearer action_variables.api_token"
  expect: "200"
  store_query:
    query: "devices"
    variable_name: "devices"

- action: "rest_api_loop"
  display_name: "Get Device Details"
  method: "GET"
  url: "https://api.example.com/devices/[{ id }]"
  headers:
    Authorization: "Bearer action_variables.api_token"
  variable_name: "devices"
  key_to_loop: "id"
  expect: "200"
  store_query:
    query: "device_info"
    variable_name: "device_details"
  output_path: "./output/device_details.json"
  output_mode: "append"
```

### Example: Sending a Command

```yaml
- action: "send_command"
  display_name: "Check Device Version"
  command: "show version"
  expect: "#"
  output_path: "./output/{{ hostname }}_version.txt"
  output_mode: "overwrite"
```

### Example: Looping Through Interfaces

```yaml
- action: "send_command_loop"
  display_name: "Collect Interface Details"
  variable_name: "interfaces"
  key_to_loop: "interface_name"
  command_template: "show interface [{ interface_name }]"
  expect: "#"
  output_path: "./output/{{ hostname }}_interfaces.txt"
  output_mode: "append"
  parse_output: true
```

## Running the Automation Tool

1. **Prepare the YAML Configuration**

   Use the GUI Editor or manually create your YAML configuration files under `project/drivers/`.

2. **Prepare the Inventory File**

   Place your inventory YAML file under `project/inventory/`.

3. **Execute the Runner Script**

   ```bash
   simplenet-runner --inventory project/inventory/home_inventory.db --query "SELECT * FROM devices" --driver project/drivers/tests/rest_api_example.yml
   ```

4. **View Outputs**

   Check the `./output/` directory for command outputs, API responses, and audit results. Logs can be found in the `./` directory.

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html).

## Additional Information

### Extending the Schema

You can add custom actions by extending the schema. For example, a `custom_action` allows you to define new behaviors.

### Code Structure and Workflow

The automation solution follows a modular approach, where each component plays a specific role in the overall workflow.

#### Workflow Overview

1. **Inventory Preparation**: Devices and credentials are defined in a YAML file.
2. **Database Creation**: The runner script converts the YAML inventory into a SQLite database.
3. **Device and API Interaction**: The runner script handles both device connections and API calls.
4. **Concurrent Execution**: The runner script executes tasks across multiple devices and APIs concurrently.
5. **Automation Execution**: For each device or API endpoint, the `simplenet` module executes the defined actions.
6. **Command and API Execution**: The `execute_commands` function processes each action.
7. **Data Storage**: Results are stored in the global data store.
8. **Reporting**: Audit results and outputs are saved to files.
9. **Debugging**: Use the Debugger GUI tool to step through workflows.


### Troubleshooting

- **Invalid Input Detected**: Ensure your commands and expectations match the device's responses.
- **Connection Timeouts**: Verify network connectivity and device/API accessibility.
- **Schema Validation Errors**: Make sure your YAML files conform to the defined schema.
- **Authentication Failures**: Confirm that credentials and tokens are correctly associated.

As of now, the tool primarily uses SSH for device communication and HTTP/S for API interactions. Support for other protocols can be added by extending the action handlers.

---

