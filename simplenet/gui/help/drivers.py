from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser


def show_drivers_help(parent):
    # Create a full-screen dialog
    drivers_dialog = QDialog(parent)
    drivers_dialog.setWindowTitle("Drivers Help")
    drivers_dialog.setWindowState(drivers_dialog.windowState() | Qt.WindowState.WindowMaximized)  # Fullscreen

    layout = QVBoxLayout(drivers_dialog)

    # Create a QTextBrowser for the drivers documentation
    text_browser = QTextBrowser(drivers_dialog)

    # Render a sample markdown string for drivers documentation, using HTML for code blocks
    drivers_html = """
    <h1>Introduction to Drivers in PySimpleNet</h1>
    <p>In <i>PySimpleNet</i>, drivers play a crucial role in defining how network automation tasks interact with various network devices. A driver represents a set of configurations and commands specific to a vendor or platform, enabling the tool to perform automation tasks, such as sending commands, gathering output, and auditing devices in a structured and reusable way.</p>

    <p>Each driver typically includes actions like sending commands, processing data, and applying templates for structured data parsing. <i>PySimpleNet</i> allows these actions to be defined using a YAML file, making the automation process both flexible and highly customizable.</p>

    <p>Drivers also handle error detection, output management, and conditional command execution, ensuring robust interactions with devices while reducing the chances of errors. By specifying drivers, users can standardize how they automate different device platforms while using common configuration files.</p>

    <h2>Explanation of the Example Driver File</h2>
    <p>The following driver file defines actions for interacting with Cisco IOS devices, with a focus on running CDP-related commands and processing the output.</p>

    <pre><code>drivers:
  cisco_ios:
    display_name: "cdp one command"
    error_string: "Invalid input detected"
    output_path: "./output/{{ hostname }}_version_check.txt"
    output_mode: "append"
    prompt_count: 4
    actions:
      - action: "send_command"
        display_name: "send_command"
        command: "term len 0"
        expect: "#"
      - action: "send_command"
        display_name: "send_command"
        command: "show cdp neighbors detail"
        expect: "#"
        output_path: "./output/{{ hostname }}_cdp_neighbors.txt"
        output_mode: "overwrite"
        ttp_path: "./project/templates/ios_show_cdp_neighbors.ttp"
        store_query:
          query: "[][]"
          variable_name: "cdp_neighbors"
      - action: "dump_datastore"
        display_name: "dump data"
        output_as: "both"
        format: "json"
        output_file_path: "./output/cdp_one_command_datastore_output.json"
    </code></pre>

    <h2>Detailed Breakdown</h2>
    <ol>
      <li><b>Driver Name (<i>cisco_ios</i>)</b>: This section defines a driver for Cisco IOS devices. Each driver under <i>drivers</i> defines how PySimpleNet interacts with a specific type of network device.</li>
      <li><b>Driver Properties</b>:
        <ul>
          <li><b>display_name</b>: The human-readable name of the driver ("<i>cdp one command</i>" in this case). This is used to describe the purpose of the driver.</li>
          <li><b>error_string</b>: This string is used to detect errors in device output. If "<i>Invalid input detected</i>" appears in the output, it signals that an error has occurred, and PySimpleNet will handle it accordingly.</li>
          <li><b>output_path</b>: The path where the output of the commands will be stored. The use of <code>{{ hostname }}</code> indicates that this field supports templating, allowing the output to be dynamically saved based on the hostname of the device.</li>
          <li><b>output_mode</b>: This option ("<i>append</i>") specifies how the output will be written to the file. In this case, new data is appended to the file.</li>
          <li><b>prompt_count</b>: Defines how many prompts (e.g., <code>#</code>) to expect before executing commands. This ensures that the tool waits for the device's readiness to receive commands.</li>
        </ul>
      </li>
      <li><b>Actions</b>: The <i>actions</i> list defines the specific tasks that PySimpleNet will perform. Each action corresponds to a command or data operation on the device.</li>
    </ol>

    <h3>Action 1: send_command</h3>
    <ul>
      <li><b>action</b>: Specifies that this is a "send_command" action.</li>
      <li><b>command</b>: The command to send to the device, "<i>term len 0</i>". This command sets the terminal length to 0, which prevents pagination in command outputs.</li>
      <li><b>expect</b>: Specifies the expected prompt ("<code>#</code>"), indicating that the command has been successfully executed and PySimpleNet should continue to the next step.</li>
    </ul>

    <h3>Action 2: send_command</h3>
    <ul>
      <li><b>command</b>: Sends the command "<i>show cdp neighbors detail</i>" to the device, gathering detailed information about neighbors discovered via CDP (Cisco Discovery Protocol).</li>
      <li><b>output_path</b>: The path to save the command's output, dynamically created using the device's hostname ("<code>./output/{{ hostname }}_cdp_neighbors.txt</code>").</li>
      <li><b>ttp_path</b>: Specifies a TTP (Template Text Parser) template located at <code>./project/templates/ios_show_cdp_neighbors.ttp</code>. This template will be used to parse the structured output of the command.</li>
      <li><b>store_query</b>: Defines a query to extract data from the parsed output and store it under a variable name ("<i>cdp_neighbors</i>").</li>
    </ul>

    <h3>Action 3: dump_datastore</h3>
    <ul>
      <li><b>action</b>: Specifies the "dump_datastore" action.</li>
      <li><b>output_as</b>: This option is set to "<i>both</i>", meaning the output will be dumped in both JSON and YAML formats.</li>
      <li><b>output_file_path</b>: The path where the datastore output will be saved (<code>./output/cdp_one_command_datastore_output.json</code>).</li>
    </ul>
    
   <pre> Sample TTP Template 
   <template name="cisco_ios_cdp_neighbors">
Device ID: {{ neighbor_id }}
  IP address: {{ ip_address }}
  Platform: {{ platform }},  Capabilities: {{ capabilities }}
Interface: {{ local_interface }},  Port ID (outgoing port): {{ remote_interface }}
</template></pre>

<h5> Inventory File Example </h5>
<pre>credentials:
- id: 1
  name: default
  username: cisco
  password: cisco
devices:
- credential_ids:
  - 1
  hostname: usa1-rtr-1
  id: 1
  mgmt_ip: 172.16.101.100
  model: Unknown Model
  platform_id: 2
  role_id: 3
  serial_number: Unknown SN
  site_id: 1
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa1-core-02
  id: 2
  mgmt_ip: 172.16.101.1
  model: Unknown Model
  platform_id: 2
  role_id: 2
  serial_number: Unknown SN
  site_id: 1
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa1-core-01
  id: 3
  mgmt_ip: 172.16.101.2
  model: Unknown Model
  platform_id: 2
  role_id: 2
  serial_number: Unknown SN
  site_id: 1
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa2-rtr-1
  id: 4
  mgmt_ip: 172.16.201.1
  model: Unknown Model
  platform_id: 2
  role_id: 3
  serial_number: Unknown SN
  site_id: 2
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa1-access-02
  id: 5
  mgmt_ip: Unknown
  model: Unknown Model
  platform_id: 3
  role_id: 1
  serial_number: Unknown SN
  site_id: 1
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa2-core-01
  id: 6
  mgmt_ip: 172.16.201.2
  model: Unknown Model
  platform_id: 2
  role_id: 2
  serial_number: Unknown SN
  site_id: 2
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa2-core-02
  id: 7
  mgmt_ip: 172.16.201.1
  model: Unknown Model
  platform_id: 2
  role_id: 2
  serial_number: Unknown SN
  site_id: 2
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa2-access-02
  id: 8
  mgmt_ip: 172.16.201.1
  model: Unknown Model
  platform_id: 2
  role_id: 1
  serial_number: Unknown SN
  site_id: 2
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
- credential_ids:
  - 1
  hostname: usa2-access-01
  id: 9
  mgmt_ip: 172.16.201.1
  model: Unknown Model
  platform_id: 2
  role_id: 1
  serial_number: Unknown SN
  site_id: 2
  timestamp: '2023-08-24 10:00:00'
  vendor_id: 1
platforms:
- id: 1
  name: Unknown
- id: 2
  name: unknown
- id: 3
  name: Unknown Platform
roles:
- id: 1
  name: access
- id: 2
  name: core
- id: 3
  name: rtr
sites:
- id: 1
  location: Unknown Location
  name: usa1
- id: 2
  location: Unknown Location
  name: usa2
vendors:
- id: 1
  name: Cisco
</pre>
    """

    # Set the generated HTML to the text browser
    text_browser.setHtml(drivers_html)

    layout.addWidget(text_browser)
    drivers_dialog.setLayout(layout)

    # Show the dialog in full-screen mode
    drivers_dialog.exec()
