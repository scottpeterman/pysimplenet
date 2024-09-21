# action_schema.py

schema = {
    "drivers": {
        "type": "dictionary",
        "label": "Drivers",
        "required": True,
        "keys": {
            "type": "text",
            "label": "Driver Name",
            "required": True
        },
        "values": {
            "type": "nested",
            "label": "Driver Configuration",
            "fields": [
                {"name": "error_string", "type": "text", "label": "Error String", "required": False},
                {"name": "output_path", "type": "file", "label": "Output Path", "required": False},
                {"name": "output_mode", "type": "choice", "label": "Output Mode", "choices": ["append", "overwrite"], "required": False},
                {"name": "prompt_count", "type": "number", "label": "Prompt Count", "required": False},
                {
                    "name": "actions",
                    "type": "list",
                    "label": "Actions",
                    "required": True,
                    "fields": [
                        {
                            "name": "action",
                            "type": "choice",
                            "label": "Action Type",
                            "choices": ["send_command", "send_command_loop", "audit_loop", "send_config", "send_config_loop", "print_audit", "dump_datastore", "custom_action", "audit"],
                            "required": True
                        },
                        {
                            "name": "parameters",
                            "type": "nested",
                            "label": "Parameters",
                            "required": True,
                            # The fields here depend on the action selected and are defined in the "actions" schema below.
                        }
                    ]
                }
            ]
        }
    },
    "actions": {
        # New 'python_script' action added below
        "python_script": {
            "fields": [
                {
                    "name": "use_parent_path",
                    "type": "checkbox",
                    "label": "Use Parent Path for Python Interpreter",
                    "required": False,
                    "default": False
                },
                {
                    "name": "path_to_python",
                    "type": "file",
                    "label": "Path to Python Interpreter",
                    "required": False,
                    "description": "Leave empty to use the system default Python interpreter if 'Use Parent Path' is checked."
                },
                {
                    "name": "path_to_script",
                    "type": "file",
                    "label": "Path to Python Script",
                    "required": True,
                    "description": "Full path to the Python script to execute."
                },
                {
                    "name": "arguments_string",
                    "type": "text",
                    "label": "Arguments",
                    "required": False,
                    "description": "Arguments to pass to the Python script."
                },
                {
                    "name": "log_file",
                    "type": "file",
                    "label": "Log File Path",
                    "required": True,
                    "description": "Path to the log file where script output and errors will be recorded."
                }
            ]
        },
        "send_command": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": False},
                {"name": "command", "type": "text", "label": "Command", "required": True},
                {"name": "expect", "type": "text", "label": "Expected Output", "required": False},
                {"name": "output_path", "type": "file", "label": "Output Path", "required": False},
                {"name": "output_mode", "type": "choice", "label": "Output Mode", "choices": ["append", "overwrite"], "required": False},
                {"name": "output_format", "type": "choice", "label": "Output Format", "choices": ["text", "both"], "required": False},
                {"name": "ttp_path", "type": "file", "label": "TTP Template Path", "required": False},
                {
                    "name": "store_query",
                    "type": "nested",
                    "label": "Store Query",
                    "required": False,
                    "fields": [
                        {"name": "query", "type": "text", "label": "Query", "required": True},
                        {"name": "variable_name", "type": "text", "label": "Variable Name", "required": True}
                    ]
                }
            ]
        },
        "send_command_loop": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": False},
                {"name": "variable_name", "type": "text", "label": "Variable Name", "required": True},
                {"name": "key_to_loop", "type": "text", "label": "Key to Loop", "required": True},
                {"name": "command_template", "type": "multiline_text", "label": "Command Template", "required": True},
                {"name": "expect", "type": "text", "label": "Expected Output", "required": True},
                {"name": "output_path", "type": "file", "label": "Output Path", "required": False},
                {"name": "output_mode", "type": "choice", "label": "Output Mode", "choices": ["append", "overwrite"], "required": False},
                {"name": "parse_output", "type": "checkbox", "label": "Parse Output", "required": False},
                {"name": "ttp_path", "type": "file", "label": "TTP Template Path", "required": False},
                {
                    "name": "store_query",
                    "type": "nested",
                    "label": "Store Query",
                    "required": False,
                    "fields": [
                        {"name": "query", "type": "text", "label": "Query", "required": True},
                        {"name": "variable_name", "type": "text", "label": "Variable Name", "required": True}
                    ]
                },
                {
                    "name": "use_named_list",
                    "type": "nested",
                    "label": "Use Named List",
                    "required": False,
                    "fields": [
                        {"name": "list_name", "type": "text", "label": "List Name", "required": True},
                        {"name": "item_key", "type": "text", "label": "Item Key", "required": True},
                        {"name": "ttp_path", "type": "file", "label": "TTP Path", "required": True},
                        {
                            "name": "store_query",
                            "type": "nested",
                            "label": "Store Query",
                            "required": True,
                            "fields": [
                                {"name": "query", "type": "text", "label": "Query", "required": True},
                                {"name": "variable_name", "type": "text", "label": "Variable Name", "required": True},
                            ],
                        },
                    ],
                },
            ]
        },
        "audit_loop": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": True},
                {"name": "policy_name", "type": "text", "label": "Policy Name", "required": True},
                {"name": "variable_name", "type": "text", "label": "Variable Name", "required": True},
                {"name": "key_to_check", "type": "text", "label": "Key to Check", "required": True},
                {"name": "target_value", "type": "text", "label": "Target Value", "required": False},
                {"name": "query", "type": "text", "label": "Query", "required": False},
                {
                    "name": "pass_if",
                    "type": "list",
                    "label": "Pass If Conditions",
                    "required": False,
                    "fields": [
                        {"name": "name", "type": "text", "label": "Condition Name", "required": True},
                        {"name": "check_type", "type": "choice", "label": "Check Type", "choices": ["jmespath", "regex"], "required": True},
                        {"name": "query", "type": "text", "label": "Query", "required": True},
                        {"name": "key_to_check", "type": "text", "label": "Key to Check", "required": False},
                        {
                            "name": "operator",
                            "type": "nested",
                            "label": "Operator",
                            "required": True,
                            "fields": [
                                {
                                    "name": "type",
                                    "type": "choice",
                                    "label": "Operator Type",
                                    "choices": ["is_equal", "not_equal", "greater_than", "less_than", "contains", "matches_regex", "string_in"],
                                    "required": True
                                },
                                {"name": "value", "type": "text", "label": "Value", "required": True},
                            ],
                        },
                    ],
                },
            ]
        },
        "send_config": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": True},
                {"name": "config", "type": "multiline_text", "label": "Configuration", "required": False},
                {"name": "config_template_path", "type": "file", "label": "Config Template Path", "required": False},
                {"name": "variables_path", "type": "file", "label": "Variables Path", "required": False},
                {"name": "expect", "type": "text", "label": "Expected Output", "required": False},
                {"name": "error_string", "type": "text", "label": "Error String", "required": False},
            ]
        },
        "send_config_loop": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": False},
                {"name": "variable_name", "type": "text", "label": "Variable Name", "required": True},
                {"name": "key_to_loop", "type": "text", "label": "Key to Loop", "required": True},
                {"name": "command_template", "type": "multiline_text", "label": "Command Template", "required": True},
                {"name": "expect", "type": "text", "label": "Expected Output", "required": False},
                {"name": "output_path", "type": "file", "label": "Output Path", "required": False},
                {"name": "output_mode", "type": "choice", "label": "Output Mode", "choices": ["append", "overwrite"], "required": False},
                {
                    "name": "use_condition",
                    "type": "nested",
                    "label": "Use Condition",
                    "required": False,
                    "fields": [
                        {"name": "condition_name", "type": "text", "label": "Condition Name", "required": True},
                        {"name": "condition_type", "type": "choice", "label": "Condition Type", "choices": ["fail_if_not", "pass_if"], "required": True},
                        {"name": "condition_query", "type": "text", "label": "Condition Query", "required": True},
                        {
                            "name": "operator",
                            "type": "nested",
                            "label": "Operator",
                            "required": True,
                            "fields": [
                                {
                                    "name": "type",
                                    "type": "choice",
                                    "label": "Operator Type",
                                    "choices": ["is_equal", "not_equal", "greater_than", "less_than", "contains", "matches_regex"],
                                    "required": True
                                },
                                {"name": "value", "type": "text", "label": "Value", "required": True},
                            ],
                        },
                    ],
                },
            ]
        },
        "print_audit": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": True},
                {"name": "output_file_path", "type": "file", "label": "Output File Path", "required": True},
                {"name": "format", "type": "choice", "label": "Format", "choices": ["yaml", "json", "both"], "required": True},
            ]
        },
        "dump_datastore": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": False},
                {"name": "output_as", "type": "choice", "label": "Output As", "choices": ["both", "single"], "required": True},
                {"name": "format", "type": "choice", "label": "Format", "choices": ["json", "yaml"], "required": True},
                {"name": "output_file_path", "type": "file", "label": "Output File Path", "required": True}
            ]
        },
        "audit": {
            "fields": [
                {"name": "display_name", "type": "text", "label": "Display Name", "required": True},
                {"name": "policy_name", "type": "text", "label": "Policy Name", "required": True},
                {
                    "name": "pass_if",
                    "type": "list",
                    "label": "Pass If Conditions",
                    "required": True,
                    "fields": [
                        {"name": "name", "type": "text", "label": "Condition Name", "required": True},
                        {"name": "check_type", "type": "choice", "label": "Check Type", "choices": ["jmespath", "regex"], "required": True},
                        {"name": "query", "type": "text", "label": "Query", "required": True},
                        {
                            "name": "operator",
                            "type": "nested",
                            "label": "Operator",
                            "required": True,
                            "fields": [
                                {
                                    "name": "type",
                                    "type": "choice",
                                    "label": "Operator Type",
                                    "choices": ["is_equal", "not_equal", "greater_than", "less_than", "contains", "matches_regex", "string_in"],
                                    "required": True
                                },
                                {"name": "value", "type": "text", "label": "Value", "required": True},
                            ],
                        },
                    ],
                },
            ]
        },
        "custom_action": {
            "fields": [
                {"name": "custom_field1", "type": "text", "label": "Custom Field 1", "required": False},
                {"name": "custom_field2", "type": "multiline_text", "label": "Custom Field 2", "required": False},
                {
                    "name": "custom_field3",
                    "type": "choice",
                    "label": "Custom Choice Field",
                    "choices": ["option1", "option2", "option3"],
                    "required": False
                },
            ]
        }
    }
}