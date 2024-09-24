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
        if ttp_path not in self.data:
            self.data[ttp_path] = {}
        self.data[ttp_path][action_index] = parsed_data

    def get_device_data(self):
        return dict(self.data)

    def add_audit_report(self, audit_result):
        self.audit_report.append(audit_result)

    def get_audit_report(self):
        return list(self.audit_report)

    def set_variable(self, variable_name, value):
        self.action_variables[variable_name] = value
        if debug:
            logging.debug(f"Set variable '{variable_name}' with value: {value} in device session.")

    def get_variable(self, variable_name):
        return self.action_variables.get(variable_name)


class SessionBasedDataStore:
    def __init__(self):
        self.sessions = {}

    def get_or_create_session(self, device_name):
        if device_name not in self.sessions:
            self.sessions[device_name] = DeviceSession()
        return self.sessions[device_name]

    def update(self, device_name, ttp_path, action_index, parsed_data):
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
        return session.get_variable(variable_name)


class GlobalDataStoreWrapper(QObject):
    _instance = None  # Class-level variable to hold the Singleton instance

    signal_global_data_updated = pyqtSignal(str)

    def __new__(cls, *args, **kwargs):
        # Ensure only one instance is created (Singleton pattern)
        if cls._instance is None:
            cls._instance = super(GlobalDataStoreWrapper, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        # Ensure that QObject is initialized once
        if not hasattr(self, '_initialized'):  # Prevent __init__ from being called multiple times
            super().__init__()  # Ensure QObject is initialized
            self.session_store = SessionBasedDataStore()
            self.current_device = None
            if debug:
                logging.debug("GlobalDataStoreWrapper initialized")
            self._initialized = True  # Mark this instance as initialized

    def update(self, device_name, ttp_path, action_index, parsed_data):
        if debug:
            logging.debug(f"Updating data for device: {device_name}, ttp_path: {ttp_path}, action_index: {action_index}")
        self.session_store.update(device_name, ttp_path, action_index, parsed_data)

        session = self.session_store.get_or_create_session(device_name)
        if debug:
            logging.debug(f"Updated data structure for {device_name}: {session.get_device_data()}")
            logging.debug(f"Full session store after update: {self.session_store.get_all_data()}")

    def set_current_device(self, device_name):
        if debug:
            logging.debug(f"Setting current device to: {device_name}")
        self.current_device = device_name

    def add_command_result(self, device_name, command, output):
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
        session = self.session_store.get_or_create_session(device_name)
        data = session.get_device_data()

        # Ensure action_variables are included in the output
        if 'action_variables' not in data:
            data['action_variables'] = session.action_variables

        return data

    def get_all_data(self):
        if debug:
            logging.debug("Getting all data")

        # Retrieve all sessions
        all_data = self.session_store.get_all_data()

        # Ensure action_variables are included in each device's session
        for device, session_data in all_data.items():
            session = self.session_store.get_or_create_session(device)

            # If action_variables are missing, add them from the session
            if 'action_variables' not in session_data:
                session_data['action_variables'] = session.action_variables

            if debug:
                logging.debug(f"Data for device {device}: {session_data}")

        if debug:
            logging.debug(f"Final all data: {all_data}")

        return all_data

    def add_audit_report(self, audit_result):
        if self.current_device is None:
            logging.error("Current device not set. Call set_current_device() first.")
            raise ValueError("Current device not set. Call set_current_device() first.")
        if debug:
            logging.debug(f"Adding audit report for current device: {self.current_device}")
        self.session_store.add_audit_report(self.current_device, audit_result)
        self.signal_global_data_updated.emit(json.dumps(audit_result, indent=2))

    def get_audit_report(self, device_name=None):
        if device_name is None:
            device_name = self.current_device
        if device_name is None:
            logging.error("Device name not provided and current device not set.")
            raise ValueError("Device name not provided and current device not set.")
        logging.debug(f"Getting audit report for device: {device_name}")
        return self.session_store.get_audit_report(device_name)

    def set_variable(self, variable_name, value):
        if self.current_device is None:
            logging.error("Current device not set. Call set_current_device() first.")
            raise ValueError("Current device not set. Call set_current_device() first.")

        # Store the variable in the device session
        self.session_store.set_variable(self.current_device, variable_name, value)

        # Ensure action_variables is explicitly added to the data dictionary
        session = self.session_store.get_or_create_session(self.current_device)
        if 'action_variables' not in session.data:
            session.data['action_variables'] = {}

        # Update the action variable directly in the global data store
        session.data['action_variables'][variable_name] = value

        if debug:
            logging.debug(f"Set variable '{variable_name}' with value: {value} for device {self.current_device}")

    def get_variable(self, variable_name):
        if self.current_device is None:
            logging.error("Current device not set. Call set_current_device() first.")
            raise ValueError("Current device not set. Call set_current_device() first.")
        return self.session_store.get_variable(self.current_device, variable_name)
