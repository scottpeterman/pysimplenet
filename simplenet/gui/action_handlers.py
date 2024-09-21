# action_handlers.py
import json
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTextCursor
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox

from simplenet.gui.visual_actions import display_action_details


def on_action_selected(action_details_layout, item):
    """
    Handle the selection of an action in the action list widget.

    Args:
        action_details_layout (QVBoxLayout): The layout to display action details.
        item (QListWidgetItem): The selected item representing the action.
    """
    try:
        # Display action details based on the selected action type
        action = item.data(256)  # Assuming action details are stored with role 256
        action_type = action.get("action", "").lower()

        # Display different details depending on the action type
        if action_type in ['send_command', 'send_command_loop', 'send_config', 'send_config_loop', 'audit', 'audit_loop', 'print_audit']:
            display_action_details(action_details_layout, item)
        else:
            print(f"Unknown action type: {action_type}")
    except Exception as e:
        print("Error in on_action_selected:")
        traceback.print_exc()


def display_action_details_in_debugger(action_details_layout, global_data_store_widget, item, global_data_store):
    """
    Update the action details pane with information from the given item.

    Args:
        action_details_layout (QVBoxLayout): The layout to display action details.
        global_data_store_widget (QTextEdit): Widget to display the global data store.
        item (QListWidgetItem): The selected action item.
        global_data_store (dict): The global data store object to pull data from.
    """
    try:
        # Get action details from the item
        action = item.data(256)
        action_type = action.get("action", "").lower()

        # Display specific details depending on the action type
        if action_type in ['send_command', 'send_command_loop', 'send_config', 'send_config_loop', 'audit', 'audit_loop', 'print_audit']:
            display_action_details(
                action_details_layout,
                global_data_store_widget,
                item,
                global_data_store
            )
        else:
            print(f"Unknown action type: {action_type}")
    except Exception as e:
        print("Error displaying action details in debugger:")
        traceback.print_exc()

# action_handlers.py

def highlight_current_action(visual_debugger_instance, completed_index, highlight_end=False):
    """
    Highlight the completed action and set the next action to be executed.

    Args:
        visual_debugger_instance (VisualDebugger): The instance of the VisualDebugger class.
        completed_index (int): The index of the action that has just been completed.
        highlight_end (bool): Whether to highlight the "End" item.
    """
    try:
        action_list_widget = visual_debugger_instance.action_list_widget
        action_completion_state = visual_debugger_instance.action_completion_state

        if completed_index < action_list_widget.count():
            action_completion_state[completed_index] = 'completed'

            # Reset all items' background and font color
            for i in range(action_list_widget.count()):
                item = action_list_widget.item(i)

                if action_completion_state.get(i) == 'completed':
                    item.setBackground(QColor("#555555"))  # Light grey
                    item.setForeground(QColor("#E0E0E0"))  # Dark font color
                else:
                    item.setBackground(QColor(Qt.GlobalColor.transparent))
                    item.setForeground(QColor(Qt.GlobalColor.white))  # Default font color

            if highlight_end:
                end_item = action_list_widget.item(action_list_widget.count() - 1)
                end_item.setBackground(QColor(Qt.GlobalColor.darkGray))  # Dark grey
                end_item.setForeground(QColor(Qt.GlobalColor.white))  # White font color
            else:
                if completed_index + 1 < action_list_widget.count() - 1:
                    next_item = action_list_widget.item(completed_index + 1)
                    next_item.setBackground(QColor("#4DA6FF"))  # Blue color
                    next_item.setForeground(QColor(Qt.GlobalColor.white))  # White font color
                elif completed_index == 0:
                    start_item = action_list_widget.item(0)
                    start_item.setBackground(QColor("#4DA6FF"))  # Blue color
                    start_item.setForeground(QColor(Qt.GlobalColor.white))  # White font color

    except Exception as e:
        print("Error in highlight_current_action:")
        traceback.print_exc()

# action_handlers.py

def append_to_execution_results(visual_debugger_instance, text, is_html=False):
    """
    Append text or HTML formatted text to the execution results box.

    Args:
        visual_debugger_instance (VisualDebugger): The instance of the VisualDebugger class.
        text (str): The text to append.
        is_html (bool): Whether the text is HTML formatted.
    """
    try:
        # Access the execution_results_text widget from the instance
        execution_results_text = visual_debugger_instance.execution_results_text

        # Move the cursor to the end of the text
        execution_results_text.moveCursor(QTextCursor.MoveOperation.End)

        if is_html:
            # Insert the HTML content
            execution_results_text.insertHtml(text + '<br>')
        else:
            # Insert plain text content
            execution_results_text.insertPlainText(text + '\n')

        execution_results_text.ensureCursorVisible()
    except Exception as e:
        print("Error in append_to_execution_results:")
        traceback.print_exc()

# action_handlers.py

def display_audit_results(visual_debugger_instance, audit_json):
    """
    Display the audit results in the GUI formatted as a table.

    Args:
        visual_debugger_instance (VisualDebugger): The instance of the VisualDebugger class.
        audit_json (str): JSON string of audit results.
    """
    try:
        # Access the execution_results_text widget from the instance
        execution_results_text = visual_debugger_instance.execution_results_text

        audit_data = json.loads(audit_json)
    except json.JSONDecodeError:
        # If there's an error decoding JSON, just display the raw text
        append_to_execution_results(visual_debugger_instance, "Invalid JSON format:\n" + audit_json)
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
        # Extract top-level fields from audit_data
        policy_name = audit_data.get("policy_name", "Unknown Policy")
        results = audit_data.get("results", [])

        if not isinstance(results, list):
            raise ValueError(f"Invalid results structure for policy: {policy_name}. Expected a list.")

        for result in results:
            if not isinstance(result, dict):
                raise ValueError(f"Invalid structure for result in policy: {policy_name}. Expected a dictionary.")

            condition = result.get("condition", "Unknown Condition")
            condition_met = result.get("condition_met", False)
            color = "green" if condition_met else "red"

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
        print(e)
        traceback.print_exc()
        append_to_execution_results(visual_debugger_instance, f"Error: {str(e)}")
        return

    # Append the formatted results to the execution results
    append_to_execution_results(visual_debugger_instance, formatted_results, is_html=True)
