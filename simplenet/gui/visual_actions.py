import json
import traceback

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QFrame, QScrollArea, QGridLayout, QWidget, QSpacerItem, QSizePolicy, \
    QPushButton, QTabWidget
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


def create_collapsible_frame(nested_data, title):
    """
    Create a collapsible QFrame widget to display nested dictionary data.

    Args:
        nested_data (dict): The dictionary data to be displayed in a collapsible structure.
        title (str): The title for the collapsible section.

    Returns:
        QFrame: A collapsible QFrame widget containing the structured visualization.
    """
    collapsible_frame = QFrame()
    collapsible_frame.setFrameShape(QFrame.Shape.Box)
    collapsible_frame.setStyleSheet("background-color: #2C2C2C; border: 1px solid #4DA6FF; padding: 5px; margin: 5px;")  # Microsoft blue for border

    collapsible_layout = QVBoxLayout()
    collapsible_frame.setLayout(collapsible_layout)

    toggle_button = QPushButton(f"▼ {title}")
    toggle_button.setStyleSheet("text-align: left; font-weight: bold; color: #4DA6FF; margin-bottom: 2px;")  # Microsoft blue for text
    toggle_button.setCheckable(True)
    toggle_button.setChecked(True)

    content_frame = QFrame()
    content_layout = QVBoxLayout(content_frame)

    for sub_key, sub_value in nested_data.items():
        sub_key_label = QLabel(f"{sub_key}:")
        sub_key_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        sub_key_label.setStyleSheet("color: #4DA6FF; padding: 2px; margin-bottom: 2px;")  # Microsoft blue for keys
        content_layout.addWidget(sub_key_label)

        if isinstance(sub_value, dict):
            sub_frame = create_collapsible_frame(sub_value, sub_key)
            content_layout.addWidget(sub_frame)
        else:
            sub_value_label = QLabel(f"{sub_value}")
            sub_value_label.setFont(QFont("Arial", 9))
            sub_value_label.setStyleSheet("color: #FFFFFF; background-color: #333333; padding: 2px; margin-bottom: 2px;")  # Distinct color for values
            content_layout.addWidget(sub_value_label)

    collapsible_layout.addWidget(toggle_button)
    collapsible_layout.addWidget(content_frame)
    toggle_button.toggled.connect(lambda checked: content_frame.setVisible(checked))

    return collapsible_frame

def create_collapsible_list_frame(list_data, title):
    """
    Create a collapsible QFrame widget to display list data.

    Args:
        list_data (list): The list data to be displayed in a collapsible structure.
        title (str): The title for the collapsible section.

    Returns:
        QFrame: A collapsible QFrame widget containing the structured visualization.
    """
    collapsible_frame = QFrame()
    collapsible_frame.setFrameShape(QFrame.Shape.Box)
    collapsible_frame.setStyleSheet("background-color: #3C3C3C; border: 1px solid #555555; padding: 5px; margin: 5px;")  # Added margin for better separation

    # Layout for the collapsible content
    collapsible_layout = QVBoxLayout()
    collapsible_frame.setLayout(collapsible_layout)

    # Toggle button to expand/collapse
    toggle_button = QPushButton(f"▼ {title}")
    toggle_button.setStyleSheet("text-align: left; font-weight: bold; color: #FFFFFF; margin-bottom: 2px;")  # Added bottom margin for separation
    toggle_button.setCheckable(True)
    toggle_button.setChecked(True)

    # Nested content frame
    content_frame = QFrame()
    content_layout = QVBoxLayout(content_frame)

    # Populate nested content
    for i, item in enumerate(list_data):
        item_label = QLabel(f"Item {i + 1}:")
        item_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        item_label.setStyleSheet("color: #FFFFFF; padding: 2px; margin-bottom: 2px;")  # Added bottom margin for separation
        content_layout.addWidget(item_label)

        if isinstance(item, dict):
            nested_frame = create_collapsible_frame(item, f"Item {i + 1}")
            content_layout.addWidget(nested_frame)
        else:
            value_label = QLabel(f"{item}")
            value_label.setFont(QFont("Arial", 9))
            value_label.setStyleSheet("color: #AAAAAA; padding: 2px; margin-bottom: 2px;")  # Added bottom margin for separation
            content_layout.addWidget(value_label)

    collapsible_layout.addWidget(toggle_button)
    collapsible_layout.addWidget(content_frame)

    # Connect toggle button to show/hide content
    toggle_button.toggled.connect(lambda checked: content_frame.setVisible(checked))

    return collapsible_frame



from PyQt6.QtWidgets import QSizePolicy  # Ensure this import is present


def display_action_details(action_details_layout, global_data_store_text, item, global_data_store):
    """
    Display the details of the selected action in the Action Details panel with a structured visualization
    and update the Global Data Store view.

    Args:
        action_details_layout (QVBoxLayout): The layout in the Action Details panel to populate.
        global_data_store_text (QTextEdit): The text widget for displaying the global data store as JSON.
        item (QListWidgetItem): The selected item from the action list.
        global_data_store (GlobalDataStoreWrapper): The global data store object.
    """
    try:
        # Retrieve stored action data from the item using the UserRole
        action_data = item.data(Qt.ItemDataRole.UserRole)
        if action_data is None:
            action_data = {}

        # Get the action type from action_data
        action_type = action_data.get('action', 'Unknown')

        # Find the existing QTabWidget in the action_details_layout
        details_tab_widget = None
        for i in range(action_details_layout.count()):
            widget = action_details_layout.itemAt(i).widget()
            if isinstance(widget, QTabWidget):
                details_tab_widget = widget
                break

        if not details_tab_widget:
            print("Error: QTabWidget not found in layout")
            return

        # Get the 'Action Details' tab widget (assuming it's the first tab)
        action_details_widget = details_tab_widget.widget(0)
        if not action_details_widget:
            print("Error: Action Details widget not found in tab")
            return

        # Access the layout of the action_details_widget
        layout = action_details_widget.layout()
        if layout is None:
            layout = QVBoxLayout()
            action_details_widget.setLayout(layout)

        # Clear previous content of the Action Details tab
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Use specific display function based on action type
        if action_type == 'send_command_loop':
            display_send_command_loop_details(layout, action_data)
        else:
            display_generic_action_details(layout, action_data)

        # Update the Global Data Store tab with JSON content if needed
        global_data_json = json.dumps(global_data_store.get_all_data(), indent=4)
        global_data_store_text.setPlainText(global_data_json)

    except Exception as e:
        print(f"Error displaying action details: {e}")
        traceback.print_exc()

def display_generic_action_details(layout, action_data):
    """
    Display generic details for any action type that does not have a specific display function.

    Args:
        layout (QVBoxLayout): The layout to populate with generic action details.
        action_data (dict): The action data to display.
    """
    try:
        # Clear existing widgets from the layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Create a scroll area and content widget
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)

        # Set a grid layout for the scroll content
        grid_layout = QGridLayout(scroll_content)
        scroll_content.setLayout(grid_layout)
        grid_layout.setSpacing(4)  # Compact layout

        row = 0
        for key, value in action_data.items():
            # Create a label for the key
            key_label = QLabel(f"{key}:")
            key_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            key_label.setStyleSheet("color: #4DA6FF; padding: 2px;")
            grid_layout.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignRight)

            # Display value with appropriate formatting
            if isinstance(value, dict):
                nested_frame = create_collapsible_frame(value, key)
                grid_layout.addWidget(nested_frame, row, 1, Qt.AlignmentFlag.AlignLeft)
            elif isinstance(value, list):
                list_frame = create_collapsible_list_frame(value, key)
                grid_layout.addWidget(list_frame, row, 1, Qt.AlignmentFlag.AlignLeft)
            else:
                value_label = QLabel(str(value))
                value_label.setFont(QFont("Arial", 10))
                value_label.setStyleSheet("color: #FFFFFF; background-color: #333333; padding: 4px;")
                grid_layout.addWidget(value_label, row, 1, Qt.AlignmentFlag.AlignLeft)

            row += 1

        # Add a spacer item to maintain layout structure
        grid_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), row, 0)

        # Add the scroll area to the layout
        layout.addWidget(scroll_area)

    except Exception as e:
        print(f"Error displaying generic action details: {e}")
        traceback.print_exc()


def display_send_command_loop_details(layout, action_data):
    """
    Display the details for a 'send_command_loop' action.

    Args:
        layout (QVBoxLayout): The layout to populate with details.
        action_data (dict): The action data to display.
    """
    try:
        # Clear existing widgets from the layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Add a grid layout for the action details
        grid_layout = QGridLayout()
        layout.addLayout(grid_layout)

        row = 0
        for key, value in action_data.items():
            key_label = QLabel(f"{key}:")
            key_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            key_label.setStyleSheet("color: #4DA6FF; padding: 2px;")
            grid_layout.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignRight)

            # Display value with appropriate formatting
            value_label = QLabel(str(value))
            value_label.setFont(QFont("Arial", 10))
            value_label.setStyleSheet("color: #FFFFFF; background-color: #333333; padding: 4px;")
            grid_layout.addWidget(value_label, row, 1, Qt.AlignmentFlag.AlignLeft)

            row += 1

    except Exception as e:
        print(f"Error displaying send_command_loop details: {e}")
        traceback.print_exc()


from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
import json

def display_audit_loop_details(layout, action_data):
    """
    Display the details specific to an 'audit_loop' action.

    Args:
        layout (QVBoxLayout): The layout to populate with audit loop details.
        action_data (dict): The action data to display.
    """
    try:
        # Clear existing widgets from the layout
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # Display the action's attributes
        attributes = [
            f"Display Name: {action_data.get('display_name', '')}",
            f"Policy Name: {action_data.get('policy_name', '')}",
            f"Variable Name: {action_data.get('variable_name', '')}",
            f"Key to Check: {action_data.get('key_to_check', '')}",
            f"Target Value: {action_data.get('target_value', '')}",
            f"Query: {action_data.get('query', '')}",
            f"Pass If Conditions: {json.dumps(action_data.get('pass_if', []), indent=4)}"
        ]

        for attr in attributes:
            attr_label = QLabel(attr)
            layout.addWidget(attr_label)

    except Exception as e:
        print(f"Error displaying audit loop details: {e}")
        traceback.print_exc()

def create_nested_frame(nested_data):
    """
    Create a QFrame widget to display nested dictionary data.

    Args:
        nested_data (dict): The dictionary data to be displayed in a nested structure.

    Returns:
        QFrame: A QFrame widget containing the structured visualization.
    """
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.Box)
    frame.setStyleSheet("background-color: #2C2C2C; border: 1px solid #444444; padding: 5px;")

    layout = QVBoxLayout(frame)

    for sub_key, sub_value in nested_data.items():
        sub_key_label = QLabel(f"{sub_key}:")
        sub_key_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        sub_key_label.setStyleSheet("color: #FFFFFF; padding: 2px;")
        layout.addWidget(sub_key_label)

        if isinstance(sub_value, dict):
            sub_frame = create_nested_frame(sub_value)
            layout.addWidget(sub_frame)
        else:
            sub_value_label = QLabel(f"{sub_value}")
            sub_value_label.setFont(QFont("Arial", 9))
            sub_value_label.setStyleSheet("color: #AAAAAA; padding: 2px;")
            layout.addWidget(sub_value_label)

    return frame


def create_list_frame(list_data):
    """
    Create a QFrame widget to display list data.

    Args:
        list_data (list): The list data to be displayed.

    Returns:
        QFrame: A QFrame widget containing the structured visualization.
    """
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.Box)
    frame.setStyleSheet("background-color: #3C3C3C; border: 1px solid #555555; padding: 5px;")

    layout = QVBoxLayout(frame)

    for i, item in enumerate(list_data):
        item_label = QLabel(f"Item {i + 1}:")
        item_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        item_label.setStyleSheet("color: #FFFFFF; padding: 2px;")
        layout.addWidget(item_label)

        if isinstance(item, dict):
            nested_frame = create_nested_frame(item)
            layout.addWidget(nested_frame)
        else:
            value_label = QLabel(f"{item}")
            value_label.setFont(QFont("Arial", 9))
            value_label.setStyleSheet("color: #AAAAAA; padding: 2px;")
            layout.addWidget(value_label)

    return frame


def clear_layout(layout):
    """
    Clear all widgets from a layout.

    Args:
        layout (QLayout): The layout to clear.
    """
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()
