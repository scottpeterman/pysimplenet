---

# Pysimplenet

![GUI Full Screenshot](https://raw.githubusercontent.com/scottpeterman/pysimplenet/main/screenshots/gui_full.png)
![GUI Debugger Screenshot](https://raw.githubusercontent.com/scottpeterman/pysimplenet/main/screenshots/gui-debug.png)

## Network Automation Solution

Pysimplenet is a YAML-driven network automation solution that includes both CLI and GUI tools for managing network devices. This tool simplifies network configuration, auditing, and automation tasks by leveraging a structured YAML schema and a set of Python scripts.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [Launching the Applications](#launching-the-applications)
  - [Configuration](#configuration)
  - [Schema Explanation](#schema-explanation)
  - [Components](#components)
    - [Runner Script (`runner.py`)](#1-runner-script-runnerpy)
    - [Simplenet Module (`simplenet/cli/simplenet.py`)](#2-simplenet-module-simplenetclisimplenetpy)
    - [Command Executor (`command_executor2.py`)](#3-command-executor-command_executor2py)
    - [GUI Editor Tool (`driver_editor.py`)](#4-gui-editor-tool-driver_editorpy)
    - [Debugger GUI Tool (`debugger.py`)](#5-debugger-gui-tool-debuggerpy)
  - [Examples](#examples)
- [Contributing](#contributing)
- [License](#license)
- [Additional Information](#additional-information)
  - [Extending the Schema](#extending-the-schema)
  - [GUI Usage](#gui-usage)
    - [Editor GUI Tool](#editor-gui-tool)
    - [Debugger GUI Tool](#debugger-gui-tool)
  - [Code Structure and Workflow](#code-structure-and-workflow)
    - [Workflow Overview](#workflow-overview)
    - [File and Module Details](#file-and-module-details)
  - [Troubleshooting](#troubleshooting)
  - [Support](#support)
  - [Frequently Asked Questions](#frequently-asked-questions)

## Features

- **YAML-Driven Configuration**: Easily define actions and workflows using YAML files.
- **CLI and GUI Tools**: Choose between command-line interface or graphical user interface based on your preference.
- **Device Drivers**: Support for multiple network device types (e.g., Cisco IOS).
- **Automation Actions**: Send commands, loop through commands, audit configurations, and more.
- **Extensible Schema**: Define custom actions and extend the existing schema as needed.
- **Concurrent Execution**: Run tasks across multiple devices concurrently to save time.
- **Data Persistence**: Use SQLite databases for inventory and device data management.
- **Visual YAML Editor**: Use the GUI editor to create and modify YAML configuration files easily.
- **Debugger Tool**: Visually debug and step through automation workflows.

## Prerequisites

- **Python**: 3.9 or higher
- **Required Python packages**: Listed in [`requirements.txt`](requirements.txt)
- **Network Access**: Access to network devices (e.g., Cisco IOS devices) with SSH connectivity
- **GUI Tools**: PyQt6 (for GUI tools)

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/scottpeterman/pysimplenet.git
   ```

2. **Navigate to the Project Directory**

   ```bash
   cd pysimplenet
   ```

3. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install the Package**

   ```bash
   pip install .
   ```

## Usage

### Launching the Applications

After installation, you can launch the various tools using the following console scripts:

- **CLI Tools**:
  - `pysshpass`: Authenticate using SSH pass.
    ```bash
    pysshpass
    ```
  - `simplenet`: Execute CLI-based network automation tasks.
    ```bash
    simplenet
    ```
  - `vsndebug`: Launch the VSN Debugger GUI tool.
    ```bash
    vsndebug
    ```

- **GUI Tool**:
  - `simplenet-gui`: Launch the main GUI application.
    ```bash
    simplenet-gui
    ```

### Configuration

All configurations are done through YAML files. Below is a sample configuration for a Cisco IOS device:

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
      # Additional actions...
```

### Schema Explanation

The schema defines the structure of the YAML configuration files used by the automation tool. Below is an overview of the schema and its components:

#### Actions

- **send_command**: Sends a single command to the device.
  - **Fields**:
    - `display_name` (required): A friendly name for the action.
    - `command` (required): The command to execute.
    - `expect` (required): The expected prompt after command execution.
    - `output_path` (optional): File path to save the command output.
    - `output_mode` (optional): Either `append` or `overwrite`.
    - `ttp_path` (optional): Path to the TTP template for parsing output.
    - `store_query` (optional): Stores parsed data into variables.
      - **Fields**:
        - `query`: The query to execute on the parsed data.
        - `variable_name`: The name of the variable to store data.

- **send_command_loop**: Sends a command template in a loop based on variables.
  - **Fields**:
    - `display_name`: A friendly name for the action.
    - `variable_name`: The variable to loop through.
    - `key_to_loop`: The key within the variable to iterate over.
    - `command_template`: The command template using placeholders.
    - `expect`: The expected prompt after command execution.
    - `output_path` (optional): File path to save the command output.
    - `output_mode`: Either `append` or `overwrite`.
    - `parse_output`: Boolean to parse the output.
    - `use_named_list` (optional): Stores parsed data into a named list.
      - **Fields**:
        - `list_name`: Name of the list.
        - `item_key`: Key for each item in the list.
        - `ttp_path`: Path to the TTP template.
        - `store_query`: Stores parsed data into variables.

- **audit_loop**: Audits configurations based on conditions.
  - **Fields**:
    - `display_name`: A friendly name for the action.
    - `policy_name`: Name of the audit policy.
    - `variable_name`: The variable containing data to audit.
    - `key_to_check`: The key to check within the variable.
    - `target_value`: The desired value for the key.
    - `query`: The query to retrieve data.
    - `pass_if`: Conditions for passing the audit.
      - **Fields**:
        - `name`: Name of the condition.
        - `check_type`: Type of check (`jmespath` or `regex`).
        - `query`: The query or regex pattern.
        - `key_to_check`: The key within the data to check.
        - `operator`: The operator for comparison.
          - **Fields**:
            - `type`: Operator type (`is_equal` or `not_equal`).
            - `value`: Value to compare against.

- **print_audit**: Outputs the audit results.
  - **Fields**:
    - `display_name`: A friendly name for the action.
    - `output_file_path`: File path to save the audit output.
    - `format`: Output format (`yaml`, `json`, or `both`).

### Components

The solution consists of several Python scripts and modules that work together to perform network automation tasks.

#### 1. Runner Script (`runner.py`)

The runner script orchestrates the overall automation process by:

- **Creating a SQLite Database**: Converts the YAML inventory file into a SQLite database for efficient querying.
- **Device Reachability Checks**: Verifies if devices are reachable on port 22 (SSH) before attempting to connect.
- **Concurrency Management**: Uses `ProcessPoolExecutor` to run tasks across multiple devices concurrently.
- **Logging and Error Handling**: Logs errors and connection failures to specified log files.
- **Command-Line Interface**: Uses `Click` for a user-friendly CLI to accept various parameters.

**Key Functions:**

- `create_sqlite_db(yaml_file, db_file)`: Converts YAML inventory to SQLite database.
- `check_device_reachability(hostname)`: Checks if the device is reachable over SSH.
- `run_for_device(row, db_file, ...)`: Executes automation tasks for a single device.
- `query_yaml()`: The main Click command that ties everything together.

**Usage Example:**

```bash
python runner.py --inventory inventory.yaml --query "SELECT * FROM devices" --driver driver.yaml
```

#### 2. Simplenet Module (`simplenet/cli/simplenet.py`)

This module handles the execution of automation tasks for individual devices:

- **SSH Connections**: Establishes SSH connections to devices using credentials from the database.
- **Variable Rendering**: Loads variables and renders driver templates using Jinja2.
- **Command Execution**: Executes commands defined in the driver actions.
- **Data Storage**: Uses a global data store to keep track of variables and results across actions.
- **Error Handling**: Catches exceptions and logs errors for troubleshooting.

**Key Functions:**

- `load_variables_and_render_driver(vars_file, driver_file, device_info)`: Loads and renders driver templates.
- `get_device_credentials(device_id, db_conn)`: Retrieves credentials for a device from the database.
- `run_automation_for_device(device, driver_file, ...)`: Runs automation tasks for a single device.
- `main()`: The main Click command for single-device automation.

**Usage Example:**

```bash
python -m simplenet.cli.simplenet --inventory devices.db --query "SELECT * FROM devices WHERE id=1" --driver driver.yaml
```

#### 3. Command Executor (`command_executor2.py`)

The command executor handles the execution of individual actions defined in the driver:

- **Action Handlers**: Supports various action types like `send_command`, `send_command_loop`, `audit`, and more.
- **Prompt Management**: Manages prompts and counts to ensure commands are executed in the correct context.
- **Output Handling**: Handles output modes (`overwrite`, `append`) and saves command outputs to files.
- **Global Data Store Integration**: Updates the global data store with results and variables from actions.
- **Debugging and Logging**: Provides debug outputs and writes logs for each action executed.

**Key Functions:**

- `execute_commands(ssh_connection, actions, variables, ...)`: Main function to execute a list of actions.
- `handle_send_command_action(...)`: Handles the execution of `send_command` actions.
- `handle_send_command_loop(...)`: Handles the execution of `send_command_loop` actions.
- `handle_audit_action(...)`: Performs audit checks based on conditions.
- `handle_print_audit_action(...)`: Outputs audit results in specified formats.

**Usage:**

This module is typically called internally by the `simplenet` module and is not run directly.

#### 4. GUI Editor Tool (`driver_editor.py`)

The GUI Editor is a PyQt6-based application that allows users to create and modify YAML configuration files in a user-friendly way.

**Features:**

- **Visual YAML Editing**: Provides a form-based interface to create and edit actions without directly modifying YAML code.
- **Schema Validation**: Ensures that the YAML configurations conform to the predefined schema.
- **Action Management**: Add, remove, and reorder actions within the driver configurations.
- **YAML Preview**: Displays the current YAML configuration in real-time as you edit.
- **File Operations**: Open existing YAML files, save changes, and create new configurations.
- **Integration with Runner**: Launch automation runs directly from the editor.

**Key Components:**

- **DriverEditor Class**: The main window that handles the overall layout and functionality.
- **ActionEditor**: A separate component imported from `simplenet.gui.action_gui` that provides the form fields for editing individual actions.
- **RunnerForm**: A form to configure and execute automation runs, imported from `simplenet.gui.runner_form_basic`.

**Usage Instructions:**

1. **Launching the Editor**

   Run the `driver_editor.py` script to start the GUI editor:

   ```bash
   python driver_editor.py
   ```

2. **Creating a New Driver Configuration**

   - Click on **File > New** or use the toolbar to add a new driver.
   - Provide a name for the driver when prompted.

3. **Adding Actions**

   - Use the **Add Action** button to add a new action.
   - Select the action type from the list (e.g., `send_command`, `send_command_loop`).
   - Fill in the required fields in the form displayed on the right.

4. **Editing Actions**

   - Select an action from the list on the left to edit its details.
   - The form fields will update to reflect the selected action.
   - Make changes as needed, and the YAML preview will update accordingly.

5. **Removing Actions**

   - Select the action you wish to remove.
   - Click the **Remove Action** button.

6. **Saving the Configuration**

   - Click on **File > Save** or **Save As** to save your configuration to a YAML file.

7. **Viewing YAML Preview**

   - Switch to the **YAML Preview** tab to see the generated YAML configuration.
   - The preview updates in real-time as you make changes.

8. **Running Automation**

   - Click on **Run > Run Automation** to open the Runner Form.
   - Configure the run parameters and execute the automation tasks directly from the editor.

**Notes:**

- The editor validates the YAML configuration against the schema to prevent invalid configurations.
- The application provides helpful error messages if required fields are missing or invalid.

#### 5. Debugger GUI Tool (`debugger.py`)

The Debugger GUI tool allows you to visually debug and step through your automation workflows.

**Features:**

- **Step-by-Step Execution**: Execute actions one at a time to observe behavior.
- **Variable Inspection**: View the state of variables and data stores at each step.
- **Breakpoint Setting**: Set breakpoints on specific actions.
- **Output Monitoring**: See real-time output from devices as actions are executed.
- **Error Handling**: Catch and display errors with detailed traceback information.

**Usage Instructions:**

1. **Launching the Debugger**

   ```bash
   python debugger.py
   ```

2. **Loading a Configuration**

   - Open an existing YAML configuration file.
   - The debugger will parse the file and display the actions.

3. **Setting Breakpoints**

   - Click on the action where you want to set a breakpoint.
   - Use the context menu or a dedicated button to set or remove breakpoints.

4. **Starting Debugging**

   - Click on the **Start** button to begin execution.
   - Use **Next Step** to execute actions one at a time.

5. **Inspecting Variables**

   - At any point, view the current state of variables and the data store.
   - Variables are updated in real-time as actions are executed.

6. **Monitoring Output**

   - The output pane displays logs and device responses.
   - Errors and exceptions are highlighted for easy identification.

**Notes:**

- The debugger is particularly useful for testing and troubleshooting complex automation workflows.
- Ensure that you have the necessary access and permissions to connect to your devices during debugging.

**Sample Code Snippet (`debugger.py`):**

```python
# (Include the code snippet you provided earlier)
```

### Examples

#### Example: Sending a Command

```yaml
- action: "send_command"
  display_name: "Check Device Version"
  command: "show version"
  expect: "#"
  output_path: "./output/{{ hostname }}_version.txt"
  output_mode: "overwrite"
```

#### Example: Looping Through Interfaces

```yaml
- action: "send_command_loop"
  display_name: "Collect Interface Details"
  variable_name: "interfaces"
  key_to_loop: "interface_name"
  command_template: "show interface {{ interface_name }}"
  expect: "#"
  output_path: "./output/{{ hostname }}_interfaces.txt"
  output_mode: "append"
  parse_output: true
```

#### Example: Auditing MTU Settings

```yaml
- action: "audit_loop"
  display_name: "Check MTU for Interfaces"
  policy_name: "MTU Compliance"
  variable_name: "interface_details"
  key_to_check: "mtu"
  target_value: "1500"
  query: '"{{ hostname }}".action_variables.interface_details[*].mtu'
  pass_if:
    - name: "MTU is 1500"
      check_type: "jmespath"
      query: "mtu"
      key_to_check: "mtu"
      operator:
        type: "is_equal"
        value: "1500"
```

### Running the Automation Tool

1. **Prepare the YAML Configuration**

   Use the GUI Editor to create or modify your YAML configuration files. Ensure your configuration YAML file (e.g., `config.yaml`) is properly set up according to the schema.

2. **Prepare the Inventory File**

   Create an inventory YAML file containing your devices, credentials, and other related data.

3. **Execute the Runner Script**

   ```bash
   python runner.py --inventory inventory.yaml --query "SELECT * FROM devices" --driver driver.yaml --vars variables.yaml
   ```

4. **View Outputs**

   Check the `./output/` directory for command outputs and audit results. Logs can be found in the `./log/` directory.

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get involved.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

## Additional Information

### Extending the Schema

You can add custom actions by extending the schema. For example, the `custom_action` allows you to define new behaviors:

```yaml
"custom_action": {
  "fields": [
    {"name": "custom_field1", "type": "text", "label": "Custom Field 1"},
    {"name": "custom_field2", "type": "multiline_text", "label": "Custom Field 2"},
    {"name": "custom_field3", "type": "choice", "label": "Custom Choice Field", "choices": ["option1", "option2", "option3"]}
  ]
}
```

### GUI Usage

#### Editor GUI Tool

The GUI Editor simplifies the process of creating and managing your YAML configuration files. It provides a visual interface where you can add actions, set parameters, and view the resulting YAML code.

**Launching the Editor:**

```bash
python driver_editor.py
```

**Features:**

- **Form-Based Editing**: Edit actions using form fields rather than manually writing YAML.
- **Drag-and-Drop Action Ordering**: Rearrange actions by dragging them in the list.
- **Schema Validation**: Prevents invalid configurations by enforcing required fields.
- **YAML Preview**: Instantly see the YAML representation of your configuration.
- **Integration with Automation Runner**: Run your configurations directly from the editor.

**Notes:**

- Ensure that you have PyQt6 installed to run the GUI tools.
- The editor supports multiple drivers, allowing you to manage configurations for different device types.

#### Debugger GUI Tool

The Debugger GUI tool allows you to visually debug and step through your automation workflows.

**Features:**

- **Step-by-Step Execution**: Execute actions one at a time to observe behavior.
- **Variable Inspection**: View the state of variables and data stores at each step.
- **Breakpoint Setting**: Set breakpoints on specific actions.
- **Output Monitoring**: See real-time output from devices as actions are executed.
- **Error Handling**: Catch and display errors with detailed traceback information.

**Usage Instructions:**

1. **Launching the Debugger**

   ```bash
   python debugger.py
   ```

2. **Loading a Configuration**

   - Open an existing YAML configuration file.
   - The debugger will parse the file and display the actions.

3. **Setting Breakpoints**

   - Click on the action where you want to set a breakpoint.
   - Use the context menu or a dedicated button to set or remove breakpoints.

4. **Starting Debugging**

   - Click on the **Start** button to begin execution.
   - Use **Next Step** to execute actions one at a time.

5. **Inspecting Variables**

   - At any point, view the current state of variables and the data store.
   - Variables are updated in real-time as actions are executed.

6. **Monitoring Output**

   - The output pane displays logs and device responses.
   - Errors and exceptions are highlighted for easy identification.

**Notes:**

- The debugger is particularly useful for testing and troubleshooting complex automation workflows.
- Ensure that you have the necessary access and permissions to connect to your devices during debugging.

### Code Structure and Workflow

The automation solution follows a modular approach, where each component plays a specific role in the overall workflow.

#### Workflow Overview

1. **Inventory Preparation**: Devices and credentials are defined in a YAML file.
2. **Database Creation**: The runner script converts the YAML inventory into a SQLite database.
3. **Device Filtering**: A SQL query filters the devices to target.
4. **Concurrent Execution**: The runner script executes tasks across multiple devices concurrently.
5. **Automation Execution**: For each device, the `simplenet` module executes the defined actions.
6. **Command Execution**: The `execute_commands` function processes each action, interacts with the device, and collects outputs.
7. **Data Storage**: Results are stored in the global data store and can be outputted as JSON or YAML.
8. **Reporting**: Audit results and outputs are saved to files for review.
9. **Debugging**: Use the Debugger GUI tool to step through workflows and troubleshoot issues.

#### File and Module Details

- **`runner.py`**: Orchestrates the automation tasks across multiple devices.
- **`simplenet/cli/simplenet.py`**: Executes automation tasks for individual devices.
- **`simplenet/cli/command_executor2.py`**: Processes and executes each action defined in the driver.
- **`driver_editor.py`**: Provides a graphical interface for creating and editing driver YAML configurations.
- **`debugger.py`**: Allows users to debug automation workflows in a visual environment.

### Troubleshooting

- **Invalid Input Detected**: Ensure that your commands and expectations match the device's responses.
- **Connection Timeouts**: Verify network connectivity and device accessibility.
- **Schema Validation Errors**: Make sure your YAML files conform to the defined schema.
- **Authentication Failures**: Confirm that credentials are correctly associated with devices.
- **GUI Issues**: Ensure PyQt6 is properly installed if the GUI tools do not launch.

### Support

For support or questions, please open an issue on the [GitHub repository](https://github.com/scottpeterman/pysimplenet/issues) or contact us at [support@example.com](mailto:support@example.com).

### Frequently Asked Questions

#### How do I add a new device to the inventory?

Add the device details to your inventory YAML file under the `devices` section. Include all required fields such as `id`, `hostname`, `mgmt_ip`, and associate the appropriate `credential_ids`.

#### Can I use this tool with devices other than Cisco IOS?

Yes, you can extend the schema and driver definitions to support other device types. Define new drivers and actions as needed.

#### How do I handle devices that use different SSH ports?

Currently, the script assumes SSH is on port 22. You can modify the `check_device_reachability` function and the SSH connection setup to specify different ports.

#### Is there support for SNMP or other protocols?

As of now, the tool primarily uses SSH for device communication. Support for other protocols can be added by extending the action handlers and communication modules.

#### How can I contribute to the project?

We welcome contributions! Please refer to the [Contributing](#contributing) section for more details.

---

### Additional Steps to Incorporate Banner Screenshots

1. **Add Images to the Repository**:
   - Create an `images` directory at the root of your project if it doesn't exist:
     ```bash
     mkdir images
     ```
   - Place your banner images (`banner1.png` and `banner2.png`) inside the `images` directory.

2. **Update `MANIFEST.in` to Include Images**:
   Ensure that the images are included in your package by updating your `MANIFEST.in`:

   ```ini
   # MANIFEST.in

   recursive-include simplenet/gui *
   recursive-include project/drivers *.yml *.yaml
   recursive-include project/vars *.yml *.yaml
   recursive-include simplenet/templates *.ttp
   recursive-include simplenet/gui/pyeasyedit/images *.png *.jpg *.ico
   recursive-include images *.png *.jpg *.jpeg *.gif
   include LICENSE
   include README.md
   include README_FULL.md
   include README_cli.md
   ```

3. **Rebuild and Upload the Package**:
   After updating the `README.md` and `MANIFEST.in`, rebuild and upload your package to PyPI:

   ```bash
   python setup.py sdist bdist_wheel
   twine upload dist/*
   ```

