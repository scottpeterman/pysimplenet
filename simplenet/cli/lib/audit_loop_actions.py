import json
import traceback
from colorama import Fore
from simplenet.cli.lib.audit_actions import print_pretty
import jmespath

def check_run_if_condition(current_device_data, run_if, pretty, timestamps):
    """
    Checks whether the 'run_if' condition is met for the current device context.
    Returns a detailed result dictionary including the condition, the parsed value, and the result.
    """
    try:
        # Extract condition parameters
        check_type = run_if.get('check_type')
        operator = run_if.get('operator', {})
        operator_type = operator.get('type')
        operator_value = operator.get('value')
        key_to_check = run_if.get('key_to_check')

        # Validate 'key_to_check'
        if not key_to_check:
            print_pretty(pretty, timestamps, "ERROR: 'key_to_check' is missing in the condition.", Fore.RED)
            return {
                'condition': run_if,
                'parsed_value': None,
                'condition_met': False
            }

        print(f"DEBUG: Checking run_if condition - Type: {check_type}, Operator: {operator_type}, Key to Check: {key_to_check}")

        # Initialize result dictionary
        result_details = {
            'condition': run_if,
            'parsed_value': None,
            'condition_met': False
        }

        # Handle JMESPath checks
        if check_type == 'jmespath':
            query = run_if.get('query')

            # Validate 'query'
            if not query:
                print_pretty(pretty, timestamps, "ERROR: 'query' is missing in the condition.", Fore.RED)
                return result_details

            print(f"DEBUG: Executing JMESPath query: {query}")

            try:
                # Execute JMESPath query
                parsed_result = jmespath.search(query, current_device_data.get('parsed_result', {}))
                print(f"DEBUG: JMESPath query result: {parsed_result}")
            except jmespath.exceptions.JMESPathError as jp_err:
                print_pretty(pretty, timestamps, f"JMESPath Error in query '{query}': {str(jp_err)}", Fore.RED)
                print(traceback.format_exc())
                return result_details

            # Validate query result type
            if not isinstance(parsed_result, dict):
                print_pretty(pretty, timestamps, f"ERROR: Expected dictionary result from JMESPath query '{query}', got {type(parsed_result).__name__}.", Fore.RED)
                return result_details

            # Extract 'target_value' using 'key_to_check'
            target_value = parsed_result.get(key_to_check)

            if target_value is None:
                print_pretty(pretty, timestamps, f"ERROR: Key '{key_to_check}' not found in the result of JMESPath query '{query}'.", Fore.RED)
                return result_details

            print(f"DEBUG: Target value for key '{key_to_check}': {target_value}")
            result_details['parsed_value'] = target_value

            # Perform comparison based on the operator type
            if operator_type == 'string_in':
                result_details['condition_met'] = operator_value in str(target_value)
            elif operator_type == 'string_not_in':
                result_details['condition_met'] = operator_value not in str(target_value)
            elif operator_type == 'is_equal':
                result_details['condition_met'] = str(target_value) == operator_value
            elif operator_type in ['is_gt', 'is_lt', 'is_ge', 'is_le']:
                try:
                    target_value_float = float(target_value)
                    operator_value_float = float(operator_value)
                    if operator_type == 'is_gt':
                        result_details['condition_met'] = target_value_float > operator_value_float
                    elif operator_type == 'is_lt':
                        result_details['condition_met'] = target_value_float < operator_value_float
                    elif operator_type == 'is_ge':
                        result_details['condition_met'] = target_value_float >= operator_value_float
                    elif operator_type == 'is_le':
                        result_details['condition_met'] = target_value_float <= operator_value_float
                except ValueError:
                    print_pretty(pretty, timestamps, f"ERROR: Unable to convert values to float for comparison: '{target_value}' and '{operator_value}'.", Fore.RED)
                    result_details['condition_met'] = False

            print(f"DEBUG: JMESPath check result: {result_details['condition_met']}")

        else:
            # Unsupported check type or operator
            print_pretty(pretty, timestamps, f"ERROR: Unsupported check type '{check_type}' or operator '{operator_type}'.", Fore.RED)

        print(f"Returning results: {result_details}")
        # Single return statement for non-error paths
        return result_details

    except Exception as e:
        # Catch-all for unexpected exceptions
        print_pretty(pretty, timestamps, f"Exception in check_run_if_condition: {str(e)}\n{traceback.format_exc()}", Fore.RED)
        return {
            'condition': run_if,
            'parsed_value': None,
            'condition_met': False
        }

def handle_audit_action_loop(action, global_data_store, global_audit, pretty, timestamps, debug_output, variables):
    """
    Handle an 'audit_loop' action by repeatedly evaluating checks for multiple entries.
    """
    try:
        # Safely get values from the action dictionary
        variable_name = action.get('variable_name')
        policy_name = action.get('policy_name', 'Unnamed Policy')
        display_name = action.get('display_name', 'Unnamed Audit')
        audit_results = []  # Store results for this particular audit loop

        # Ensure the variable name exists
        if not variable_name:
            print_pretty(pretty, timestamps, "ERROR: 'variable_name' is missing in the action.", Fore.RED)
            return

        # Get the list of entries from the global data store using the provided variable name
        entry_list = global_data_store.get_variable(variable_name)

        if not entry_list:
            print_pretty(pretty, timestamps, f"ERROR: No entries found for variable '{variable_name}' in audit loop.", Fore.RED)
            return

        conditions = []

        # Collect conditions to process
        condition_types = ['pass_if', 'pass_if_not', 'fail_if', 'fail_if_not']
        for condition_type in condition_types:
            condition_list = action.get(condition_type, [])
            if not isinstance(condition_list, list):
                print_pretty(pretty, timestamps, f"ERROR: '{condition_type}' should be a list but got {type(condition_list).__name__}.", Fore.RED)
                continue
            for condition in condition_list:
                if not isinstance(condition, dict):
                    print_pretty(pretty, timestamps, f"ERROR: Invalid condition format. Expected a dictionary but got {type(condition).__name__}.", Fore.RED)
                    continue
                if 'query' not in condition or not condition.get('query'):
                    print_pretty(pretty, timestamps, f"ERROR: Missing query in condition: {json.dumps(condition, indent=2)}", Fore.RED)
                    continue
                if 'key_to_check' not in condition or not condition.get('key_to_check'):
                    print_pretty(pretty, timestamps, f"ERROR: Missing 'key_to_check' in condition: {json.dumps(condition, indent=2)}", Fore.RED)
                    continue
                conditions.append(condition)

        print(f"DEBUG: Conditions to process: {json.dumps(conditions, indent=2)}")

        audit_passed = True  # Assume audit passes unless a fail condition is met

        # Loop over each entry in the entry list from the global data store
        for entry_index, entry in enumerate(entry_list):
            try:


                print(f"DEBUG: Processing entry {entry_index + 1} out of {len(entry_list)}")
                print(f"DEBUG: Entry data before processing: {json.dumps(entry, indent=2)}")

                # Loop over each item in the main parsed result
                try:
                    # Process each condition
                    for condition in conditions:
                        condition_name = condition.get('name', 'Unnamed Condition')
                        # Determine the condition type (pass_if, pass_if_not, fail_if, fail_if_not)
                        condition_type_main = next(
                            (ctype for ctype in condition_types if ctype in condition), 'unknown_condition'
                        ).lower()

                        print(f"DEBUG: Evaluating condition: {condition_name} with query: {condition.get('query')}")

                        condition_result = check_run_if_condition(
                            current_device_data={'parsed_result': entry},
                            run_if=condition,
                            pretty=pretty,
                            timestamps=timestamps
                        )

                        print(f"DEBUG: Condition result: {json.dumps(condition_result, indent=2)}")

                        # Ensure all necessary keys are present in the result
                        result = {
                            'condition': condition_name,
                            'condition_met': condition_result.get('condition_met', False),
                            'details': condition_result.get('condition', {}),
                            'parsed_result': condition_result.get('parsed_value')
                        }
                        audit_results.append(result)
                        print(f"DEBUG: Appended result: {json.dumps(result, indent=2)}")

                        # Determine if a fail condition is met
                        if condition_type_main == 'fail_if' and condition_result['condition_met']:
                            print(f"DEBUG: Fail condition '{condition_name}' met. Marking audit as FAILED.")
                            audit_passed = False
                            break
                        elif condition_type_main == 'fail_if_not' and not condition_result['condition_met']:
                            print(f"DEBUG: Fail-if-not condition '{condition_name}' met. Marking audit as FAILED.")
                            audit_passed = False
                            break
                        elif condition_type_main == 'pass_if_not' and not condition_result['condition_met']:
                            print(f"DEBUG: Pass-if-not condition '{condition_name}' met. Marking audit as FAILED.")
                            audit_passed = False
                            break
                        elif condition_type_main == 'pass_if' and condition_result['condition_met']:
                            print(f"DEBUG: Pass-if condition '{condition_name}' met.")

                    # Break condition loop if audit has failed
                    if not audit_passed:
                        break

                except Exception as item_e:
                    print_pretty(pretty, timestamps, f"Exception while processing item {str(item_e)}\n{traceback.format_exc()}", Fore.RED)
                    continue

                # Break entry loop if audit has failed
                if not audit_passed:
                    break

            except Exception as entry_e:
                print_pretty(pretty, timestamps, f"Exception while processing entry {entry_index + 1}: {str(entry_e)}\n{traceback.format_exc()}", Fore.RED)
                continue

        # Determine the overall result
        overall_result = "PASSED" if audit_passed else "FAILED"
        print(f"DEBUG: Overall Audit Result: {overall_result}")
        print(f"DEBUG: Final Audit Results: {json.dumps(audit_results, indent=2)}")

        # Save the audit results into the global audit storage
        audit_entry_key = f"{policy_name}_{len(global_audit) + 1}"
        audit_report_entry = {
            'policy_name': policy_name,
            'display_name': display_name,
            'results': audit_results,
            'overall_result': overall_result,
            'variables': variables,
            'parsed_data': entry_list
        }
        global_audit[audit_entry_key] = audit_report_entry

        # Print the final result
        color = Fore.GREEN if audit_passed else Fore.RED
        print_pretty(pretty, timestamps, f"Overall Audit Result: {overall_result}", color)

        # Print remediation advice if the audit failed
        if not audit_passed:
            print_pretty(pretty, timestamps, "Audit policy failed. Consider taking remediation actions.", Fore.YELLOW)

        return audit_report_entry

    except Exception as main_e:
        print_pretty(pretty, timestamps, f"Exception in handle_audit_action_loop: {str(main_e)}\n{traceback.format_exc()}", Fore.RED)
        return None
