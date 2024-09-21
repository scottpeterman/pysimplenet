import traceback

from ruamel.yaml import YAML as yaml
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox, QListWidget
from PyQt6.QtGui import QIcon


from ruamel.yaml import YAML, YAMLError

def load_driver_file(file_path):
    try:
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True
        with open(file_path, 'r') as file:
            yaml_data = yaml_loader.load(file)
            # Convert to a regular dictionary
            yaml_data = dict(yaml_data)
            print("DEBUG: Loaded YAML data:")
            print(yaml_data)
            return yaml_data
    except YAMLError as e:
        print(f"Error parsing YAML file: {e}")
        return None
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def populate_action_list(action_list_widget, yaml_data, icon_map):
    """
    Populate the action list in the UI with data from the YAML file for a specific driver.

    Args:
        action_list_widget (QListWidget): The QListWidget to populate with actions.
        yaml_data (dict): The parsed YAML data containing the actions for the selected driver.
        icon_map (dict): Mapping of action types to icons.
    """
    try:
        # Clear the existing action list
        action_list_widget.clear()

        # Add "Start" action first
        start_action = QListWidgetItem("Start")
        start_action.setData(256, {"action": "start"})
        start_action.setIcon(icon_map.get('start', QIcon.fromTheme("dialog-information")))
        action_list_widget.addItem(start_action)

        # Get the single driver data
        driver_name, driver_content = next(iter(yaml_data.items()))

        actions = driver_content.get('actions', [])
        if not actions:
            QMessageBox.warning(action_list_widget, "No Actions", f"No actions found for driver '{driver_name}'.")
            return

        # Populate actions between "Start" and "End"
        for action in actions:
            # Generate a display name for the action
            action_display_name = action.get('display_name', action.get('action', 'Unknown Action'))
            item = QListWidgetItem(f"{driver_name}: {action_display_name}")

            # Set an icon based on the action type
            action_type = action.get('action', '')
            icon = icon_map.get(action_type, QIcon.fromTheme("dialog-question"))
            item.setIcon(icon)
            item.setData(256, action)  # Store the entire action object for easy access later

            # Insert action between "Start" and "End"
            action_list_widget.addItem(item)

        # Add "End" action last
        end_action = QListWidgetItem("End")
        end_action.setData(256, {"action": "end"})
        end_action.setIcon(icon_map.get('end', QIcon.fromTheme("dialog-ok")))
        action_list_widget.addItem(end_action)
        action_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)  # Disable selection mode
        action_list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Disable focus from mouse/keyboard


    except Exception as e:
        traceback.print_exc()
        QMessageBox.critical(action_list_widget, "Error", f"Failed to populate action list: {e}")


def get_action_icon(action_type):
    """
    Get the appropriate icon for a given action type.

    Args:
        action_type (str): The type of the action.

    Returns:
        QIcon: The icon corresponding to the action type.
    """
    icon_map = {
        'send_command': QIcon.fromTheme("network-server"),  # Represents a network server or connection
        'send_config': QIcon.fromTheme("document-save"),  # Represents saving or applying changes to a document/config
        'dump_datastore': QIcon.fromTheme("document-export"),  # Represents exporting data
        'audit': QIcon.fromTheme("security-high"),  # Represents a security or auditing action
        'print_audit': QIcon.fromTheme("printer"),  # Represents printing action, a clearer representation for print
        'python_script': QIcon.fromTheme("utilities-terminal"),  # Represents running scripts or terminal commands
        'sleep': QIcon.fromTheme("system-sleep"),  # Represents a sleep or suspend action
    }
    return icon_map.get(action_type, QIcon.fromTheme("dialog-question"))  # Default icon if type is unknown
