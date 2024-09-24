import json
import logging
import time
import jmespath
from ruamel.yaml import YAML as yaml
from colorama import Fore, Style
debug_output = True

def print_pretty(pretty, timestamps, msg, color=Fore.WHITE):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S') if timestamps else ''
    if pretty:
        print(f"{timestamp} {color + msg + Style.RESET_ALL}")
    else:
        print(f"{timestamp} {msg}")

def execute_audit_action(action, global_data_store, current_device_name, pretty=False, timestamps=False):
    """
    Executes an audit action against a device and updates the global audit report.
    """
    current_device_data = global_data_store.get_device_data(current_device_name)
    if debug_output:
        logging.debug(f"Current device data structure:")
        logging.debug(json.dumps(current_device_data, indent=2))

    policy_name = action.get('policy_name', 'Unnamed Policy')
    display_name = action.get('display_name', 'Unnamed Audit')

    if debug_output:
        print_pretty(pretty, timestamps, f"Executing audit action: {display_name}", Fore.CYAN)
        print(f"DEBUG: Current device data: {json.dumps(current_device_data, indent=2)}")

    audit_results = []
    conditions = {
        'pass_if': action.get('pass_if', []),  # Expecting a list of conditions
        'pass_if_not': action.get('pass_if_not', []),
        'fail_if': action.get('fail_if', []),
        'fail_if_not': action.get('fail_if_not', [])
    }

    audit_context = {
        'global_data_store': global_data_store,
        'current_device_name': current_device_name,
        'all_devices': global_data_store.get_all_data(),
        'current_device': current_device_data
    }

    for condition_name, condition_list in conditions.items():
        for condition in condition_list:
            if condition:
                if debug_output:
                    print(f"DEBUG: Evaluating condition: {condition_name}")
                    print(f"DEBUG: Condition details: {json.dumps(condition, indent=2)}")

                query = condition.get('query')
                parsed_result = None
                new_current_data = None
                if query:
                    try:
                        new_current_data = {}
                        for ttp_path, action_data in current_device_data.items():
                            for action_index, parsed_data in action_data.items():
                                key = ttp_path.split('/')[-1].replace('.ttp', '')
                                new_current_data[key] = parsed_data

                        if debug_output:
                            print(f"DEBUG: Flattened data for JSMespath: {json.dumps(new_current_data, indent=2)}")
                        parsed_result = jmespath.search(str(query).strip(), new_current_data)
                        jpath_data_dump = action.get('jpath_data_dump', None)
                        if jpath_data_dump:
                            try:
                                with open(jpath_data_dump, "w") as fhj:
                                    fhj.write(json.dumps(new_current_data, indent=2))
                            except Exception as e:
                                print_pretty(pretty,timestamps,str(e),Fore.RED)
                        print(f"DEBUG: JMESPath query result: {parsed_result}")

                    except jmespath.exceptions.JMESPathError as e:
                        print_pretty(pretty, timestamps, f"Error in JMESPath query '{query}': {str(e)}", Fore.RED)

                audit_context['parsed_result'] = parsed_result
                condition_met = check_run_if_condition(
                    new_current_data if new_current_data else audit_context['current_device'], condition)
                print(f"DEBUG: Condition met: {condition_met}")

                result = {
                    'condition': condition_name,
                    'condition_met': condition_met,
                    'details': condition,
                    'parsed_result': parsed_result
                }
                audit_results.append(result)

                # Do not break the loop for pass_if conditions to allow evaluation of all criteria
                if condition_name in ['fail_if'] and condition_met:
                    print(f"DEBUG: Breaking loop due to {condition_name} condition being met")
                    break
                elif condition_name in ['fail_if_not'] and not condition_met:
                    print(f"DEBUG: Breaking loop due to {condition_name} condition not being met")
                    break

    # Determine the overall result based on all pass_if and fail_if conditions
    audit_passed = all(r['condition_met'] for r in audit_results if r['condition'] in ['pass_if']) and \
                   not any(r['condition_met'] for r in audit_results if r['condition'] in ['fail_if', 'fail_if_not'])

    overall_result = "PASSED" if audit_passed else "FAILED"
    print(f"DEBUG: Audit results: {json.dumps(audit_results, indent=2)}")
    print(f"DEBUG: Overall result: {overall_result}")

    audit_report_entry = {
        'policy_name': policy_name,
        'display_name': display_name,
        'device_name': current_device_name,
        'results': audit_results,
        'overall_result': overall_result
    }
    global_data_store.add_audit_report(audit_report_entry)

    print_pretty(pretty, timestamps, f"Overall Audit Result: {overall_result}",
                 Fore.GREEN if audit_passed else Fore.RED)

    if not audit_passed:
        print_pretty(pretty, timestamps, "Audit policy failed. Consider taking remediation actions.", Fore.YELLOW)

    return audit_report_entry


def handle_audit_action(action, global_data_store, global_audit, pretty, timestamps):
    """
    Handle an 'audit' action by evaluating the specified checks.
    """
    variable_name = action.get('variable_name')
    key_to_check = action.get('key_to_check')
    query = action.get('query')
    policy_name = action.get('policy_name')
    pass_if = action.get('pass_if')

    # Retrieve the list of dictionaries from the global data store
    entry_list = global_data_store.get_variable(variable_name)

    if not entry_list:
        print_pretty(pretty, timestamps, f"ERROR: No entries found for variable '{variable_name}' in audit.", Fore.RED)
        return {}

    audit_results = []

    # Iterate over each entry and perform the specified checks
    for entry in entry_list:
        check_value = entry.get(key_to_check)
        if check_value is None:
            print_pretty(pretty, timestamps, f"ERROR: Key '{key_to_check}' not found in entry: {entry}", Fore.RED)
            continue

        for check in pass_if:
            check_name = check.get('name')
            check_type = check.get('check_type')
            check_query = check.get('query')
            operator_type = check.get('operator', {}).get('type')
            operator_value = check.get('operator', {}).get('value')

            # Evaluate check using JMESPath or other methods
            query_result = jmespath.search(check_query, entry) if check_type == 'jmespath' else None
            check_passed = (query_result == operator_value) if operator_type == 'is_equal' else False

            audit_results.append({
                'policy_name': policy_name,
                'check_name': check_name,
                'check_passed': check_passed,
                'query_result': query_result,
                'expected_value': operator_value,
                'actual_value': query_result,
                'entry': entry,
            })

            if debug_output:
                print(f"DEBUG: Audit check '{check_name}' for '{key_to_check}' resulted in {check_passed}")

    # Update global audit store
    global_audit[policy_name] = audit_results
    return audit_results


def check_run_if_condition(current_device_data, run_if):
    """
    Checks whether the 'run_if' condition is met for the current device context.
    """
    check_type = run_if.get('check_type')
    operator = run_if.get('operator', {})
    operator_type = operator.get('type')
    operator_value = operator.get('value')

    print(f"DEBUG: Checking run_if condition - Type: {check_type}, Operator: {operator_type}")

    # Handle raw string checks
    if check_type == 'raw_string':
        template = run_if.get('template')
        index = int(run_if.get('index', 0))
        data = current_device_data.get(template, [])
        target_data = data[index] if index < len(data) else None

        if target_data and 'parsed_output' in target_data:
            target_str = json.dumps(target_data['parsed_output'])

            if operator_type == 'string_in':
                return operator_value in target_str
            elif operator_type == 'string_not_in':
                return operator_value not in target_str
            elif operator_type == 'is_equal':
                return target_str == operator_value

    # Handle JMESPath checks
    elif check_type == 'jmespath':
        query = run_if.get('query')
        target_value = jmespath.search(query, current_device_data)

        if target_value is None:
            print(f"DEBUG: JMESPath query '{query}' did not return any results.")
            return False

        # Convert target_value to string for string comparisons or to float for numeric comparisons
        result = False
        if operator_type == 'string_in':
            result = operator_value in str(target_value)
        elif operator_type == 'string_not_in':
            result = operator_value not in str(target_value)
        elif operator_type == 'is_equal':
            result = str(target_value) == operator_value
        elif operator_type in ['is_gt', 'is_lt', 'is_equal', 'is_ge', 'is_le']:
            try:
                target_value_float = float(target_value)
                operator_value_float = float(operator_value)
                if operator_type == 'is_gt':
                    result = target_value_float > operator_value_float
                elif operator_type == 'is_lt':
                    result = target_value_float < operator_value_float
                elif operator_type == 'is_ge':
                    result = target_value_float >= operator_value_float
                elif operator_type == 'is_le':
                    result = target_value_float <= operator_value_float
                elif operator_type == 'is_equal':
                    result = target_value_float == operator_value_float
            except ValueError:
                print(f"DEBUG: Unable to compare values as floats: {target_value} and {operator_value}")
                return False

        print(f"DEBUG: JMESPath check result: {result}")
        return result

    print(f"DEBUG: Unsupported check type or operator: {check_type}, {operator_type}")
    return False


from ruamel.yaml import YAML
from io import StringIO

def handle_print_audit_action(action, global_audit, pretty, timestamps):
    """
    Handles the print_audit action.
    """
    print_pretty(pretty, timestamps, "Executing print_audit action", Fore.CYAN)
    output_type = action.get('output_type', 'console')
    output_format = action.get('output_format', 'yaml')
    output_file_path = action.get('output_file_path', '')

    # Ensure global_audit is not empty
    if global_audit:
        # Create a deep copy of global_audit to avoid YAML anchors/references
        audit_copy = json.loads(json.dumps(global_audit))

        # Generate audit output based on requested format
        if output_format == 'json':
            audit_output = json.dumps(audit_copy, indent=2)
        else:  # Default to YAML format
            # Create a YAML instance
            yaml_instance = YAML()
            yaml_instance.default_flow_style = False  # Set the flow style
            yaml_instance.preserve_quotes = True      # Preserve quotes if needed

            # Use StringIO to capture the output
            stream = StringIO()
            yaml_instance.dump(audit_copy, stream)
            audit_output = stream.getvalue()

        # Output to console if requested
        if output_type in ('console', 'both'):
            try:
                print_pretty(pretty, timestamps, f"Audit results:\n{audit_output}", Fore.CYAN)
            except Exception as e:
                print(f"Error printing audit results: {str(e)}")

        # Output to file if requested
        if output_file_path:
            try:
                with open(output_file_path, 'w') as f:
                    f.write(audit_output)
                    f.flush()
            except Exception as e:
                print(f"Audit save failed: {e}")
    else:
        print_pretty(pretty, timestamps, "No audit results to print.", Fore.YELLOW)
