import json
import sys
import time
import traceback

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QListWidget, QTextEdit, \
    QLabel, QFrame, QToolBar, QFileDialog, QListWidgetItem, QStyle, QInputDialog, QMessageBox, QDialog, QPushButton, \
    QTabWidget
from PyQt6.QtGui import QIcon, QAction, QTextCursor, QColor
from simplenet.gui.driver_loader import populate_action_list
from simplenet.gui.driver_loader import load_driver_file as load_driver_file_from_yaml
from simplenet.gui.terminal.term_widget import SSHTerminalWidget

from simplenet.gui.visual_actions import display_action_details
from simplenet.gui.runner_form import RunnerForm
from simplenet.gui.simplenet_wrapper import AutomationWrapper
global_data_store_content = ""
debugging = False

class NoClickListWidget(QListWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, event):
        # Ignore the mouse press event to disable item selection by clicking
        event.ignore()

class VisualDebugger(QMainWindow):
    audit_data_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.action_completion_state = {}  # Store action completion states
        self.setWindowTitle("Visual Debugger")
        self.setGeometry(100, 100, 800, 500)
        self.current_driver_data = None
        self.current_driver_name = None
        self.automation_wrapper = None
        self.driver_file_path = None
        self.global_data_store_buffer = ""  # Initialize a global buffer to store the data


        try:
            # Initialize the icon map with built-in Qt icons
            self.icon_map = {
                'start': self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay),
                'send_command': self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward),
                'send_config': self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView),
                'dump_datastore': self.style().standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon),
                'audit': self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation),
                'print_audit': self.style().standardIcon(QStyle.StandardPixmap.SP_CustomBase),
                'python_script': self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon),
                'sleep': self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause),
                'end': self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
            }

            # self.icon_map = {
            #     'start': QIcon('assets/icons/start.png'),  # Replace with your custom icon path
            #     'send_command': QIcon('assets/icons/send_command.png'),
            #     'send_config': QIcon('assets/icons/send_config.png'),
            #     'dump_datastore': QIcon('assets/icons/dump_datastore.png'),
            #     'audit': QIcon('assets/icons/audit.png'),
            #     'print_audit': QIcon('assets/icons/print_audit.png'),
            #     'python_script': QIcon('assets/icons/python_script.png'),
            #     'sleep': QIcon('assets/icons/sleep.png'),
            #     'end': QIcon('assets/icons/end.png')
            # }
            # Central widget
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)

            # Main vertical layout
            main_layout = QVBoxLayout(central_widget)

            # Toolbar
            self.toolbar = QToolBar("Main Toolbar", self)
            self.addToolBar(self.toolbar)

            # Open File action
            open_action = QAction(QIcon.fromTheme("document-open"), "Open Driver File", self)
            open_action.setStatusTip("Open a YAML driver file")
            open_action.triggered.connect(self.open_file_dialog)
            self.toolbar.addAction(open_action)

            # Run Automation action
            run_action = QAction(QIcon.fromTheme("media-playback-start"), "Run Automation", self)
            run_action.setStatusTip("Run the automation script")
            run_action.triggered.connect(self.run_automation)
            self.toolbar.addAction(run_action)

            # Main splitter
            main_splitter = QSplitter(self)
            main_layout.addWidget(main_splitter)

            # Action List Panel
            action_list_frame = QFrame()
            action_list_layout = QVBoxLayout(action_list_frame)
            action_list_label = QLabel("Action List")

            # Styling for action list widget
            self.action_list_widget = NoClickListWidget()
            self.action_list_widget.setStyleSheet("""
                        QListWidget {
                            background-color: #333333;
                            color: #FFFFFF;
                            font-size: 12px;
                            border: 1px solid #4DA6FF;
                            padding: 5px;
                        }
                        QListWidget::item {
                            padding: 10px;
                            margin: 2px;
                        }
                        QListWidget::item:selected {
                            background-color: #4DA6FF;  /* Original blue for selection */
                            color: #FFFFFF;
                            outline: none;
                        }
                        QListWidget::item:focus {
                            outline: none;
                        }
                        QListWidget::item:hover {
                            outline: none;
                        }
                    """)
            self.action_list_widget.itemClicked.connect(self.on_action_selected)
            action_list_layout.addWidget(action_list_label)
            action_list_layout.addWidget(self.action_list_widget)
            main_splitter.addWidget(action_list_frame)
            self.action_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)  # Disable selection mode
            self.action_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Disable focus from mouse/keyboard

            # Detail and Results Splitter
            detail_result_splitter = QSplitter()
            detail_result_splitter.setOrientation(Qt.Orientation.Vertical)
            main_splitter.addWidget(detail_result_splitter)

            # Action Details Panel with Tabs
            action_details_frame = QFrame()
            self.action_details_layout = QVBoxLayout(action_details_frame)

            # Create a QTabWidget for Action Details and Data Store View
            self.details_tab_widget = QTabWidget(self)

            # Add the "Action Details" tab
            action_details_label = QLabel("Action Details")
            self.action_details_widget = QTextEdit()
            self.action_details_widget.setReadOnly(True)
            self.action_details_widget.setStyleSheet("""
                        QTextEdit {
                            background-color: #1E1E1E;
                            color: #FFFFFF;
                            font-size: 12px;
                            padding: 5px;
                        }
                    """)
            self.details_tab_widget.addTab(self.action_details_widget, "Action Details")

            # Add the "Global Data Store" tab
            self.global_data_store_widget = QTextEdit()
            self.global_data_store_widget.setReadOnly(True)
            self.global_data_store_widget.setStyleSheet("""
                        QTextEdit {
                            background-color: #1E1E1E;
                            color: #FFFFFF;
                            font-size: 12px;
                            padding: 5px;
                        }
                    """)
            self.details_tab_widget.addTab(self.global_data_store_widget, "Global Data Store")

            # Add the TabWidget to the action details layout
            self.action_details_layout.addWidget(self.details_tab_widget)
            detail_result_splitter.addWidget(action_details_frame)

            # Execution Results Panel
            self.execution_results_text = QTextEdit()
            self.execution_results_text.setReadOnly(True)
            self.execution_results_text.setStyleSheet("""
                        QTextEdit {
                            background-color: #1E1E1E;
                            color: #FFFFFF;
                            font-size: 12px;
                            padding: 5px;
                        }
                    """)
            self.tab_widget = QTabWidget(self)

            self.tab_widget.addTab(self.execution_results_text, "Execution Results")
            detail_result_splitter.addWidget(self.tab_widget)

            # Add Step Buttons
            self.step_button = QPushButton("Step Next Action", self)
            self.step_button.clicked.connect(self.step_next_action)
            self.toolbar.addWidget(self.step_button)
            self.step_button.setEnabled(False)

            # Terminal Button
            self.open_terminal_button = QPushButton("Open Terminal", self)
            self.open_terminal_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
            self.open_terminal_button.setStatusTip("Open Terminal with current SSH session")
            self.open_terminal_button.clicked.connect(self.open_terminal_window)
            self.toolbar.addWidget(self.open_terminal_button)

            # Set initial proportions
            main_splitter.setSizes([300, 800])
            detail_result_splitter.setSizes([400, 200])
            # Not instantiated yet
            # self.automation_wrapper.global_data_store.signal_global_data_updated.connect(self.display_audit_results)
            self.center_form()


        except Exception as e:
            print("Error in initialization:")
            traceback.print_exc()

    def center_form(self):
        """
        Center the form on the screen.
        """
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        form_size = self.geometry()
        x = (screen_geometry.width() - form_size.width()) // 2
        y = (screen_geometry.height() - form_size.height()) // 2
        self.move(x, y)

    # Slot to handle the display of audit results
    # def display_audit_results(self, audit_json):
    #     """
    #     Display the audit results in the GUI.
    #     """
    #     # Update the text widget with the audit results
    #     self.update_global_data_store_display()
    #     self.append_to_execution_results("\n" + audit_json)
    def display_audit_results(self, audit_json):
        """
        Display the audit results in the GUI formatted as a table.
        """
        # Parse the JSON string
        try:
            print(f"DEBUG: Raw audit JSON: {audit_json}")
            audit_data = json.loads(audit_json)
            print(f"DEBUG: Parsed audit data: {audit_data}")
        except json.JSONDecodeError:
            # If there's an error decoding JSON, just display the raw text
            self.append_to_execution_results("Invalid JSON format:\n" + audit_json)
            return

        # Begin formatting the output as an HTML table
        formatted_results = """
        <table border="1" cellspacing="0" cellpadding="3">
            <thead>
                <tr>
                    <th style="color: white; background-color: #333;">Policy Name</th>
                    <th style="color: white; background-color: #333;">Condition</th>
                    <th style="color: white; background-color: #333;">Condition Met</th>
                    <th style="color: white; background-color: #333;">Details</th>
                </tr>
            </thead>
            <tbody>
        """

        try:
            # Ensure audit_data is a dictionary
            if not isinstance(audit_data, dict):
                raise ValueError("Invalid audit data structure. Expected a dictionary.")

            for key, entry in audit_data.items():
                print(f"DEBUG: Processing audit entry with key: {key}")
                print(f"DEBUG: Audit entry content: {entry}")

                # Extract top-level fields from each entry
                policy_name = entry.get("policy_name", "Unknown Policy")
                results = entry.get("results", [])

                print(f"DEBUG: Policy Name: {policy_name}")
                print(f"DEBUG: Results: {results}")

                # Ensure results is a list
                if not isinstance(results, list):
                    raise ValueError(f"Invalid results structure for policy: {policy_name}. Expected a list.")

                for result in results:
                    # Ensure each result is a dictionary
                    if not isinstance(result, dict):
                        raise ValueError(
                            f"Invalid structure for result in policy: {policy_name}. Expected a dictionary.")

                    condition = result.get("condition", "Unknown Condition")
                    condition_met = result.get("condition_met", False)
                    color = "green" if condition_met else "red"

                    print(f"DEBUG: Condition: {condition}, Condition Met: {condition_met}")

                    # Create a formatted details string
                    details = result.get("details", {})
                    if not isinstance(details, dict):
                        raise ValueError(
                            f"Invalid details structure for result in policy: {policy_name}. Expected a dictionary.")

                    details_html = "<br>".join(f"<b>{key}</b>: {value}" for key, value in details.items())

                    # Add a row for each result
                    formatted_results += f"""
                        <tr>
                            <td>{policy_name}</td>
                            <td>{condition}</td>
                            <td style="color: {color};">{condition_met}</td>
                            <td>{details_html}</td>
                        </tr>
                    """

            # Close the table
            formatted_results += """
                </tbody>
            </table>
            """
        except Exception as e:
            print(f"DEBUG: Error occurred: {e}")
            traceback.print_exc()
            self.append_to_execution_results(f"Error: {str(e)}")
            return

        # Append the formatted results to the execution results
        self.append_to_execution_results(formatted_results, is_html=True)

    # At the beginning of your script or class
    global_data_store_content = ""

    def update_global_data_store_display(self):
        """
        Update the global data store display in the GUI.
        Append the new data to the existing content with separators for different actions.
        """
        global global_data_store_content

        try:
            if self.automation_wrapper:
                print("Refreshing Global Data view...")

                # Fetch all the data from the global data store
                global_data = self.automation_wrapper.global_data_store.get_all_data()

                # Convert the global data to a formatted JSON string
                formatted_data = json.dumps(global_data, indent=4)

                # Debug output
                print(f"Formatted Data:\n{formatted_data}")

                # Append the new data to the global content with a separator
                separator = f"\n\n=== Update at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n"
                global_data_store_content += separator + formatted_data
                print("="*40)
                print("global_data_store_content")
                print(global_data_store_content)
                print("=" * 40)

                # Update the text widget with the new content from the buffer
                if debugging:
                    self.global_data_store_widget.setPlainText(global_data_store_content)
                else:
                    self.global_data_store_widget.setPlainText(formatted_data)

                # Move the cursor to the end
                cursor = self.global_data_store_widget.textCursor()  # Get the current text cursor
                cursor.movePosition(QTextCursor.MoveOperation.End)  # Move the cursor to the end
                self.global_data_store_widget.setTextCursor(cursor)  # Set the cursor back to the widget

        except Exception as e:
            print("Error updating global data store display:")
            traceback.print_exc()

    def open_terminal_window(self):
        """
        Open the terminal in a new tab within the tab widget.
        """
        try:
            # Check if the AutomationWrapper has an active SSH connection
            if self.automation_wrapper and self.automation_wrapper.ssh_conn:
                # Get the live SSH channel
                ssh_channel = self.automation_wrapper.ssh_conn.channel

                # Create the terminal widget
                terminal_widget = SSHTerminalWidget(parent=self, channel=ssh_channel)

                # Check if a terminal tab already exists
                terminal_index = self.tab_widget.indexOf(terminal_widget)
                if terminal_index == -1:
                    # Add a new tab for the terminal
                    self.tab_widget.addTab(terminal_widget, "Terminal")

                # Switch to the terminal tab
                self.tab_widget.setCurrentWidget(terminal_widget)
            else:
                QMessageBox.warning(self, "No Active Connection", "No active SSH connection available.")
        except Exception as e:
            print(f"Error opening terminal window: {e}")
            traceback.print_exc()

    def load_mock_action(self):
        try:
            mock_action = {
                "action": "",  # Keeping fields empty for the mock display
            }

            # Create a QListWidgetItem for the mock action
            mock_item = QListWidgetItem("")
            mock_item.setData(256, mock_action)

            # Add mock item to the action list
            self.action_list_widget.addItem(mock_item)
            self.action_list_widget.setCurrentItem(mock_item)
            self.on_action_selected(mock_item)

        except Exception as e:
            print("Error in load_mock_action:")
            traceback.print_exc()

    def on_action_selected(self, item):
        try:
            display_action_details(self.action_details_layout, item)
        except Exception as e:
            print("Error in on_action_selected:")
            traceback.print_exc()

    def open_file_dialog(self):
        try:
            file_name, _ = QFileDialog.getOpenFileName(self, "Open YAML Driver File", "", "YAML Files (*.yml *.yaml)")
            if file_name:
                self.driver_file_path = file_name  # Store the driver file path
                self.load_driver_file(file_name)
        except Exception as e:
            print("Error in open_file_dialog:")
            traceback.print_exc()

    def load_driver_file(self, file_path):
        try:
            self.driver_file_path = file_path
            yaml_data = load_driver_file_from_yaml(file_path)
            if yaml_data:
                drivers = yaml_data.get('drivers', {})
                if len(drivers) > 1:
                    # Prompt user to select a driver if more than one is available
                    driver_name, ok = QInputDialog.getItem(self, "Select Driver", "Choose a driver:",
                                                           list(drivers.keys()), 0, False)
                    if ok and driver_name:
                        self.current_driver_name = driver_name
                        self.current_driver_data = {driver_name: drivers[driver_name]}
                    else:
                        QMessageBox.warning(self, "Driver Selection", "Driver selection cancelled or invalid.")
                        return
                else:
                    # Use the only driver if there is only one
                    self.current_driver_name = list(drivers.keys())[0]
                    self.current_driver_data = drivers

                # Populate the action list with selected driver actions between "Start" and "End"
                populate_action_list(self.action_list_widget, self.current_driver_data, self.icon_map)
                self.action_list_widget.item(0).setBackground(QColor("#4DA6FF"))
                self.action_list_widget.item(0).setForeground(Qt.GlobalColor.white)

                # Select the "Start" action by default
                self.action_list_widget.setCurrentRow(0)

            else:
                print("Failed to load driver file.")
        except Exception as e:
            print("Error in load_driver_file:")
            traceback.print_exc()

    def display_action_details_in_debugger(self, item):
        """
        Update the action details pane with information from the given item.
        """
        try:
            # Directly call the function to update the action details without overwriting the layout or widgets.
            display_action_details(
                self.action_details_layout,
                self.global_data_store_widget,  # Correct reference to the existing QTextEdit widget
                item,
                self.automation_wrapper.global_data_store
            )
        except Exception as e:
            print("Error displaying action details in debugger:")
            traceback.print_exc()

    def step_next_action(self):
        """
        Trigger the execution of the next action.
        """
        try:
            current_index = self.action_list_widget.currentRow()

            # Check if we're at the "Start" action
            if current_index == 0:  # "Start" is at index 0
                print("Starting automation...")
                if not self.automation_wrapper:
                    self.run_automation()  # Initialize and start the process
                else:
                    # Move to the first real action after "Start"
                    self.action_list_widget.setCurrentRow(1)
                    self.highlight_current_action(0)  # Highlight the "Start" action in blue

                    # Automatically update action details for the next item
                    next_item = self.action_list_widget.item(1)
                    self.display_action_details_in_debugger(next_item)
                return

            # Proceed if automation is already initialized
            if self.automation_wrapper:
                next_index = current_index + 1  # Calculate the next index

                # Ensure we do not skip the last action
                if next_index < self.action_list_widget.count():
                    self.highlight_current_action(current_index)  # Highlight the completed action
                    self.action_list_widget.setCurrentRow(next_index)  # Move to the next action
                    self.automation_wrapper.run_next_action()  # Execute the next action

                    # Automatically update action details for the next item
                    next_item = self.action_list_widget.item(next_index)
                    self.display_action_details_in_debugger(next_item)

                    # Update Global Data Store Tab
                    if self.automation_wrapper and self.automation_wrapper.global_data_store:
                        global_data_json = json.dumps(self.automation_wrapper.global_data_store.get_all_data(),
                                                      indent=4)
                        # self.global_data_store_widget.setPlainText(global_data_json)  # Corrected attribute reference
                else:
                    # Mark the last real action as completed
                    self.highlight_current_action(current_index)

                    # Highlight "End" item
                    self.action_list_widget.setCurrentRow(self.action_list_widget.count() - 1)  # Move to "End"
                    self.highlight_current_action(current_index, highlight_end=True)
                    print("No more actions to execute.")
                    num_of_items = self.action_list_widget.count()
                    self.action_list_widget.item(num_of_items - 1).setForeground(Qt.GlobalColor.darkGray)

            else:
                print("Automation wrapper is not initialized.")
        except Exception as e:
            print("Error in step_next_action:")
            traceback.print_exc()

    def run_automation(self):
        try:
            # Load the driver data already in memory
            driver_data = self.current_driver_data  # Assuming driver data is stored in this variable after loading

            # Open the RunnerForm to get the automation parameters
            runner_form = RunnerForm(self, driver_data=driver_data)
            if runner_form.exec() == QDialog.DialogCode.Accepted:
                # If the form is accepted, get the parameters
                params = runner_form.form_data  # Collect data directly from RunnerForm

                # Pass the driver file path to the parameters
                params['driver_file'] = self.driver_file_path  # Pass the stored driver file path

                # Now handle the automation workflow
                # self.automation_wrapper.ssh_conn.channel
                self.start_automation(params)
        except Exception as e:
            print("Error in run_automation:")
            traceback.print_exc()

    def start_automation(self, params):
        """
        Start the automation workflow based on user inputs.
        Args:
            params (dict): The parameters collected from the RunnerForm.
        """
        try:
            # Instantiate AutomationWrapper
            self.automation_wrapper = AutomationWrapper(**params)
            self.automation_wrapper.global_data_updated.connect(self.update_global_data_store_display)

            self.automation_wrapper.audit_result_received.connect(self.display_audit_results)



            # Connect signals to GUI update functions
            self.automation_wrapper.progress.connect(self.handle_progress_update)
            self.automation_wrapper.action_complete.connect(self.handle_automation_result)
            self.step_button.setEnabled(True)

            # Begin the automation process
            self.automation_wrapper.run_automation()

            # Check for SSH connection and provide visual feedback
            if self.automation_wrapper.ssh_conn and self.automation_wrapper.ssh_conn.is_connected:
                self.action_list_widget.item(0).setForeground(
                    Qt.GlobalColor.green)  # Set to green if connection succeeds
            else:
                self.action_list_widget.item(0).setBackground(QColor("#FF0000"))  # Red background for failure
                self.action_list_widget.item(0).setForeground(Qt.GlobalColor.white)  # White text for better contrast
                print("Error: Connection to device failed.")
        except Exception as e:
            print("Error in start_automation:")
            traceback.print_exc()

    def run_all_actions(self):
        """
        Trigger the execution of all actions.
        """
        try:
            if self.automation_wrapper:
                self.automation_wrapper.run_all_actions()
        except Exception as e:
            print("Error in run_all_actions:")
            traceback.print_exc()

    def highlight_current_action(self, completed_index, highlight_end=False):
        """
        Highlight the completed action and set the next action to be executed.
        Args:
            completed_index (int): The index of the action that has just been completed.
            highlight_end (bool): Whether to highlight the "End" item.
        """
        try:
            if completed_index < self.action_list_widget.count():
                # Mark the action as completed
                self.action_completion_state[completed_index] = 'completed'

                # Reset all items' background and font color
                for i in range(self.action_list_widget.count()):
                    item = self.action_list_widget.item(i)

                    if self.action_completion_state.get(i) == 'completed':
                        # Completed action styling
                        item.setBackground(QColor("#555555"))  # Light grey
                        item.setForeground(QColor("#E0E0E0"))  # Dark font color
                    else:
                        # Reset to default for non-completed items
                        item.setBackground(Qt.GlobalColor.transparent)
                        item.setForeground(Qt.GlobalColor.white)  # Default font color

                if highlight_end:
                    # Highlight the "End" item in blue
                    end_item = self.action_list_widget.item(self.action_list_widget.count() - 1)
                    end_item.setBackground(Qt.GlobalColor.darkGray)  # Blue color
                    end_item.setForeground(Qt.GlobalColor.white)  # White font color for the active action
                    self.step_button.setEnabled(False)

                else:
                    # Highlight the next action in blue
                    if completed_index + 1 < self.action_list_widget.count() - 1:
                        next_item = self.action_list_widget.item(completed_index + 1)
                        next_item.setBackground(QColor("#4DA6FF"))  # Blue color
                        next_item.setForeground(Qt.GlobalColor.white)  # White font color for the active action
                    elif completed_index == 0:
                        # Ensure "Start" action is highlighted correctly
                        start_item = self.action_list_widget.item(0)
                        start_item.setBackground(QColor("#4DA6FF"))  # Blue color
                        start_item.setForeground(Qt.GlobalColor.white)  # White font color

        except Exception as e:
            print("Error in highlight_current_action:")
            traceback.print_exc()

    def handle_progress_update(self, message):
        try:
            # Update progress in the UI
            self.append_to_execution_results(f"Progress: {message}")
            if "Ready to start executing actions" in message:
                self.action_list_widget.item(0).setBackground(Qt.GlobalColor.green)

        except Exception as e:
            print("Error in handle_progress_update:")
            traceback.print_exc()

    def handle_automation_result(self, message, output):
        try:
            # Handle and display the results
            self.append_to_execution_results(f"Automation Result: {message} - {output}")
        except Exception as e:
            print("Error in handle_automation_result:")
            traceback.print_exc()

    def append_to_execution_results(self, text, is_html=False):
        """
        Append text or HTML formatted text to the execution results box.
        """
        try:
            # Move the cursor to the end of the text
            self.execution_results_text.moveCursor(QTextCursor.MoveOperation.End)

            if is_html:
                # Insert the HTML content
                self.execution_results_text.insertHtml(text + '<br>')
            else:
                # Insert plain text content
                self.execution_results_text.insertPlainText(text + '\n')

            self.execution_results_text.ensureCursorVisible()
        except Exception as e:
            print("Error in append_to_execution_results:")
            traceback.print_exc()

    def load_file_callback(self, file_type):
        """
        Callback to load file paths for the runner form.

        Args:
            file_type (str): Type of file to load ("inventory", "driver", "vars").

        Returns:
            str: The selected file path.
        """
        try:
            if file_type == "inventory":
                return QFileDialog.getOpenFileName(self, "Select Inventory File", "", "SQLite Files (*.sqlite)")[0]
            elif file_type == "driver":
                return QFileDialog.getOpenFileName(self, "Select Driver File", "", "YAML Files (*.yml *.yaml)")[0]
            elif file_type == "vars":
                return QFileDialog.getOpenFileName(self, "Select Vars File", "", "YAML Files (*.yml *.yaml)")[0]
        except Exception as e:
            print("Error in load_file_callback:")
            traceback.print_exc()
        return ""

def main():
    try:
        app = QApplication(sys.argv)
        debugger = VisualDebugger()
        debugger.show()
        sys.exit(app.exec())
    except Exception as e:
        print("Error in main execution:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
