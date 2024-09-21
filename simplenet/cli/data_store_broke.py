import json
import logging

from PyQt6.QtCore import pyqtSignal, QObject

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
debug = False
class DeviceSession:
    def __init__(self):
        self.data = {}  # Store data associated with TTP paths and action indices
        self.audit_report = []
        self.action_variables = {}  # Store action variables (results of store_query)

    def update(self, ttp_path, action_index, parsed_data):
        """
        Update the session with parsed data.

        Args:
            ttp_path (str): The path of the TTP template or identifier.
            action_index (int): The index of the action being executed.
            parsed_data (any): The parsed data to store.
        """
        if ttp_path not in self.data:
            self.data[ttp_path] = {}
        self.data[ttp_path][action_index] = parsed_data

    def get_device_data(self):
        """
        Get all data for the device session.

        Returns:
            dict: A dictionary representing the device data.
        """
        return dict(self.data)

    def add_audit_report(self, audit_result):
        """
        Add an audit report result to the session.

        Args:
            audit_result (any): The audit result to store.
        """
        self.audit_report.append(audit_result)

    def get_audit_report(self):
        """
        Retrieve all audit reports.

        Returns:
            list: A list of audit reports.
        """
        return list(self.audit_report)

    def set_variable(self, variable_name, value):
        """
        Store a variable in the session data store.

        Args:
            variable_name (str): The name of the variable.
            value: The value to store.
        """
        self.action_variables[variable_name] = value
        if debug:
            logging.debug(f"Set variable '{variable_name}' with value: {value} in device session.")

    def get_variable(self, variable_name):
        """
        Retrieve a variable from the session data store.

        Args:
            variable_name (str): The name of the variable to retrieve.

        Returns:
            The value of the variable if found; otherwise, None.
        """
        var_fetch = self.action_variables.get(variable_name)

        print(f"get_variable for [{variable_name}] returned {var_fetch}")
        return var_fetch


class SessionBasedDataStore:
    def __init__(self):
        self.sessions = {}

    def get_or_create_session(self, device_name):
        if device_name not in self.sessions:
            self.sessions[device_name] = DeviceSession()
        return self.sessions[device_name]

    def update(self, device_name, ttp_path, action_index, parsed_data):
        """
        Update the session for the specified device with parsed data.

        Args:
            device_name (str): The name of the device.
            ttp_path (str): The TTP path or identifier.
            action_index (int): The index of the action.
            parsed_data (any): The parsed data to store.
        """
        session = self.get_or_create_session(device_name)
        session.update(ttp_path, action_index, parsed_data)

    def get_device_data(self, device_name):
        session = self.get_or_create_session(device_name)
        return session.get_device_data()

    def get_all_data(self):
        return {device: session.get_device_data() for device, session in self.sessions.items()}

    def add_audit_report(self, device_name, audit_result):
        session = self.get_or_create_session(device_name)
        session.add_audit_report(audit_result)

    def get_audit_report(self, device_name):
        session = self.get_or_create_session(device_name)
        return session.get_audit_report()

    def set_variable(self, device_name, variable_name, value):
        session = self.get_or_create_session(device_name)
        session.set_variable(variable_name, value)



    def get_variable(self, device_name, variable_name):
        session = self.get_or_create_session(device_name)
        var_fetch = session.get_variable(variable_name)
        return var_fetch


class GlobalDataStoreWrapper(QObject):
    signal_global_data_updated = pyqtSignal(str)

    def __init__(self):
        super().__init__()  # Ensure QObject is initialized

        self.session_store = SessionBasedDataStore()
        self.current_device = None
        if debug:
            logging.debug("GlobalDataStoreWrapper initialized")

    def toDict(self):
        """
        Convert the GlobalDataStoreWrapper and its contents to a dictionary.

        Returns:
            dict: A dictionary representation of the global data store.
        """
        return {
            'session_store': self.session_store.get_all_data(),
            'current_device': self.current_device
        }

    def __iter__(self):
        """
        Make the object iterable, so it can be used with dict().
        """
        return iter(self.toDict().items())

    def items(self):
        """
        Return the items for use in dict() conversion.
        """
        return self.toDict().items()

    def update(self, device_name, ttp_path, action_index, parsed_data):
        if debug:
            logging.debug(
                f"Updating data for device: {device_name}, ttp_path: {ttp_path}, action_index: {action_index}")
        self.session_store.update(device_name, ttp_path, action_index, parsed_data)

        session = self.session_store.get_or_create_session(device_name)
        if debug:
            logging.debug(f"Updated data structure for {device_name}: {session.get_device_data()}")
            logging.debug(f"Full session store after update: {self.session_store.get_all_data()}")

    def set_current_device(self, device_name):
        """
        Set the current device for operations.

        Args:
            device_name (str): The name of the device to set as current.
        """
        if debug:
            logging.debug(f"Setting current device to: {device_name}")
        self.current_device = device_name

    def add_command_result(self, device_name, command, output):
        """
        Add a command result for a device.

        Args:
            device_name (str): The name of the device.
            command (str): The command executed.
            output (str): The output of the command.
        """
        if debug:
            logging.debug(f"Adding command result for device: {device_name}")
        session = self.session_store.get_or_create_session(device_name)
        if 'command_results' not in session.data:
            session.data['command_results'] = []
        session.data['command_results'].append({
            'command': command,
            'output': output
        })
        if debug:
            logging.debug(f"Command result added for {device_name}")

    def get_device_data(self, device_name):
        """
        Retrieve all data for a specified device.

        Args:
            device_name (str): The name of the device.

        Returns:
            dict: The data for the device.
        """
        if debug:
            logging.debug(f"Getting data for device: {device_name}")
        session = self.session_store.get_or_create_session(device_name)
        data = session.data
        if debug:
            logging.debug(f"Retrieved data: {data}")
        return data

    def get_all_data(self):
        """
        Retrieve all data from all devices.

        Returns:
            dict: A dictionary of all device data.
        """
        if debug:
            logging.debug("Getting all data")
        all_data = self.session_store.get_all_data()
        if debug:
            logging.debug(f"All data: {all_data}")
        return all_data

    def add_audit_report(self, audit_result):
        """
        Add an audit report for the current device.

        Args:
            audit_result (any): The audit result to store.
        """
        if self.current_device is None:
            logging.error("Current device not set. Call set_current_device() first.")
            raise ValueError("Current device not set. Call set_current_device() first.")
        if debug:
            logging.debug(f"Adding audit report for current device: {self.current_device}")
        self.session_store.add_audit_report(self.current_device, audit_result)
        self.signal_global_data_updated.emit(json.dumps(audit_result, indent=2))

    def get_audit_report(self, device_name=None):
        """
        Retrieve audit reports for a specified device.

        Args:
            device_name (str, optional): The name of the device. If None, use the current device.

        Returns:
            list: A list of audit reports.
        """
        if device_name is None:
            device_name = self.current_device
        if device_name is None:
            logging.error("Device name not provided and current device not set.")
            raise ValueError("Device name not provided and current device not set.")
        if debug:
            logging.debug(f"Getting audit report for device: {device_name}")
        return self.session_store.get_audit_report(device_name)

    def set_variable(self, variable_name, value):
        """
        Store a variable in the global data store for the current device.

        Args:
            variable_name (str): The name of the variable.
            value: The value to store.
        """
        if self.current_device is None:
            logging.error("Current device not set. Call set_current_device() first.")
            raise ValueError("Current device not set. Call set_current_device() first.")

        # Store the variable in the device session
        self.session_store.set_variable(self.current_device, variable_name, value)

        if debug:
            logging.debug(f"Set variable '{variable_name}' with value: {value} for device {self.current_device}.")

    def get_variable(self, variable_name):
        """
        Retrieve a variable from the global data store for the current device.

        Args:
            variable_name (str): The name of the variable to retrieve.

        Returns:
            The value of the variable if found; otherwise, None.
        """
        if self.current_device is None:
            logging.error("Current device not set. Call set_current_device() first.")
            raise ValueError("Current device not set. Call set_current_device() first.")

        var_fetch = self.session_store.get_variable(self.current_device, variable_name)

        if debug:
            logging.debug(
                f"Retrieved variable '{variable_name}' with value: {var_fetch} for device {self.current_device}.")

        return var_fetch