import sqlite3
import re
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
# 这个程序用于数据库查询
# --- Utility Functions ---
def time_format_duration(seconds, avg_days=1):
    """Formats duration in seconds to a string (e.g., XhYYm) and optionally an average."""
    if seconds is None:
        seconds = 0
    
    # Calculate total duration
    total_hours = int(seconds // 3600)
    total_minutes = int((seconds % 3600) // 60)
    time_str = f"{total_hours}h{total_minutes:02d}m" if total_hours > 0 else f"{total_minutes}m"

    # If avg_days > 1, calculate and format average duration
    if avg_days > 1:
        avg_seconds_per_day = seconds / avg_days
        avg_hours = int(avg_seconds_per_day // 3600)
        avg_minutes = int((avg_seconds_per_day % 3600) // 60)
        avg_str = f"{avg_hours}h{avg_minutes:02d}m"
        return f"{time_str} ({avg_str}/day)"
    else:
        return time_str

def generate_sorted_output(node, avg_days=1, indent=0):
    """Recursively generates sorted output lines for project hierarchies."""
    lines = []
    # Get children from the 'children' key, ensuring it exists
    children_items = node.get('children', {}).items()
    # Sort children by duration in descending order
    sorted_children = sorted(children_items, key=lambda x: x[1].get('duration', 0), reverse=True)

    for key, value in sorted_children:
        duration = value.get('duration', 0)
        # Check if there are further nested children
        has_children = bool(value.get('children')) # True if 'children' exists and is not empty

        # Output if duration > 0 or if it's a category with sub-items (even if its own duration is 0)
        if duration > 0 or has_children:
            lines.append('  ' * indent + f"- {key}: {time_format_duration(duration, avg_days)}")
            # Recursively process children if they exist
            if has_children:
                lines.extend(generate_sorted_output(value, avg_days, indent + 1))
    return lines


# --- Database Query Functions ---
def get_study_times(conn, year):
    """Fetches daily study times for a given year for heatmap generation."""
    cursor = conn.cursor()
    start_date = f"{year}0101"
    end_date = f"{year}1231"
    cursor.execute('''
        SELECT date, SUM(duration)
        FROM time_records
        WHERE date BETWEEN ? AND ?
        AND (project_path = 'study' OR project_path LIKE 'study_%')
        GROUP BY date
    ''', (start_date, end_date))
    study_times = {date: duration for date, duration in cursor.fetchall()}
    return study_times

def query_day(conn, date):
    """Queries and displays statistics for a specific day."""
    cursor = conn.cursor()
    cursor.execute('SELECT status, remark, getup_time FROM days WHERE date = ?', (date,))
    day_data = cursor.fetchone()

    if not day_data:
        print(f"\n[{date}]\nNo records found for this date.")
        return

    status, remark, getup = day_data
    
    # Calculate and prepare total duration string first
    cursor.execute('SELECT SUM(duration) FROM time_records WHERE date = ?', (date,))
    total_duration_result = cursor.fetchone()
    total_duration = total_duration_result[0] if total_duration_result and total_duration_result[0] is not None else 0
    
    output = [f"\nDate: {date}"]
    output.append(f"Total Time: {time_format_duration(total_duration)} ({total_duration // 60} minutes)") # Total for the day
    output.append(f"Status: {status}")
    output.append(f"Getup: {getup}")
    if remark and remark.strip():
        output.append(f"Remark: {remark}")

    cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date,))
    records = cursor.fetchall()

    if records:
        # Build the project tree
        tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})})
        
        # Fetch parent mappings
        cursor.execute("SELECT child, parent FROM parent_child")
        parent_map = {child: parent_val for child, parent_val in cursor.fetchall()}

        for project_path, duration_val in records: # Renamed duration to duration_val to avoid conflict
            parts = project_path.split('_')
            if not parts: continue

            current_level_path = parts[0]
            top_level_category = parent_map.get(current_level_path, current_level_path.upper())

            if top_level_category not in tree:
                tree[top_level_category] = {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})}
            tree[top_level_category]['duration'] += duration_val
            
            current_node = tree[top_level_category]
            for i in range(len(parts)): 
                if i > 0 : 
                    child_name = parts[i]
                    if child_name not in current_node['children']:
                         current_node['children'][child_name] = {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})}
                    current_node['children'][child_name]['duration'] += duration_val
                    current_node = current_node['children'][child_name]
                elif len(parts) == 1 : 
                    pass 

        sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
        for top_level, subtree_data in sorted_top_level:
            percentage = (subtree_data['duration'] / total_duration * 100) if total_duration else 0
            output.append(f"\n{top_level}: {time_format_duration(subtree_data['duration'])} ({percentage:.2f}%)")
            output.extend(generate_sorted_output(subtree_data, avg_days=1, indent=1))
    else:
        output.append("No time records for this day.")

    print('\n'.join(output))


def query_period(conn, days_to_query):
    """Queries and displays statistics for a recent period (last N days)."""
    cursor = conn.cursor()
    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=days_to_query - 1)
    
    end_date_str = end_date_dt.strftime("%Y%m%d")
    start_date_str = start_date_dt.strftime("%Y%m%d")

    print(f"\n[Last {days_to_query} Days Statistics] ({start_date_str} - {end_date_str})")

    # Fetch all records for the period to calculate total duration first
    cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?',
                   (start_date_str, end_date_str))
    records = cursor.fetchall()

    # Get number of days with actual time records for accurate averaging
    cursor.execute('''
        SELECT COUNT(DISTINCT date)
        FROM time_records
        WHERE date BETWEEN ? AND ?
    ''', (start_date_str, end_date_str))
    actual_days_with_time_records = cursor.fetchone()[0] or 0
    
    overall_total_duration_seconds = sum(item[1] for item in records)
    # Use actual_days_with_time_records for averaging, default to 1 to avoid division by zero
    avg_days_for_calc = actual_days_with_time_records if actual_days_with_time_records > 0 else 1
    
    print(f"Overall Total Time: {time_format_duration(overall_total_duration_seconds, avg_days_for_calc)}")
    print(f"Days with time records: {actual_days_with_time_records} day(s)")

    # Get status counts
    cursor.execute('''
        SELECT
            SUM(CASE WHEN status = 'True' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'False' THEN 1 ELSE 0 END)
        FROM days
        WHERE date BETWEEN ? AND ?
    ''', (start_date_str, end_date_str))
    status_data = cursor.fetchone()
    true_count = status_data[0] if status_data and status_data[0] is not None else 0
    false_count = status_data[1] if status_data and status_data[1] is not None else 0

    if actual_days_with_time_records > 0:
        print("Status Distribution (for days with records):")
        print(f"  True: {true_count} day(s) ({(true_count / actual_days_with_time_records * 100):.1f}%)")
        print(f"  False: {false_count} day(s) ({(false_count / actual_days_with_time_records * 100):.1f}%)")
    else:
        recorded_status_days = true_count + false_count
        if recorded_status_days > 0:
            print("Status Distribution (overall days with status entries):")
            print(f"  True: {true_count} day(s)")
            print(f"  False: {false_count} day(s)")
        else:
            print("Status Distribution: No status information available for this period.")


    if not records:
        print("\nNo time records found for this period.")
        return

    # Build project tree
    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})})
    cursor.execute("SELECT child, parent FROM parent_child")
    parent_map = {child: parent_val for child, parent_val in cursor.fetchall()}

    for project_path, duration in records:
        parts = project_path.split('_')
        if not parts: continue

        current_level_path = parts[0]
        top_level_category = parent_map.get(current_level_path, current_level_path.upper())
        
        if top_level_category not in tree:
            tree[top_level_category] = {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})}
        tree[top_level_category]['duration'] += duration
        
        current_node = tree[top_level_category]
        for i in range(len(parts)):
            if i > 0 :
                child_name = parts[i]
                if child_name not in current_node['children']:
                    current_node['children'][child_name] = {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})}
                current_node['children'][child_name]['duration'] += duration
                current_node = current_node['children'][child_name]
            elif len(parts) == 1:
                pass

    sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)

    for top_level, subtree_data in sorted_top_level:
        output_lines = [f"\n{top_level}: {time_format_duration(subtree_data['duration'], avg_days_for_calc)}"]
        output_lines.extend(generate_sorted_output(subtree_data, avg_days=avg_days_for_calc, indent=1))
        print('\n'.join(output_lines))


def query_day_raw(conn, date):
    """Outputs raw data for a specific day as it would appear in a text file."""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, status, getup_time, remark
        FROM days
        WHERE date = ?
    ''', (date,))
    day_data = cursor.fetchone()

    if not day_data:
        print(f"No records found for date {date}")
        return

    db_date, status, getup, remark = day_data
    
    # Get total duration for the day
    cursor.execute('SELECT SUM(duration) FROM time_records WHERE date = ?', (date,))
    total_duration_result = cursor.fetchone()
    total_duration_day = total_duration_result[0] if total_duration_result and total_duration_result[0] is not None else 0

    output = [f"Date:{db_date}"]
    output.append(f"Total Time:{time_format_duration(total_duration_day)}") # Added total time here
    output.append(f"Status:{status}")
    output.append(f"Getup:{getup}")
    output.append(f"Remark:{remark if remark and remark.strip() else ''}")

    cursor.execute('''
        SELECT start, end, project_path
        FROM time_records
        WHERE date = ?
        ORDER BY start
    ''', (date,))
    records = cursor.fetchall()

    for start, end, project in records:
        output.append(f"{start}~{end} {project}") 

    print('\n'.join(output))


def query_month_summary(conn, year_month):
    """Queries and displays statistics for a specific month."""
    cursor = conn.cursor()

    if not re.match(r'^\d{6}$', year_month):
        print("Invalid month format. Please use YYYYMM.")
        return

    year = int(year_month[:4])
    month = int(year_month[4:6])
    
    try:
        # num_days_in_month = calendar.monthrange(year, month)[1] # Not directly used for avg calc anymore
        pass
    except calendar.IllegalMonthError:
        print(f"Invalid month: {month}")
        return
        
    date_prefix = f"{year}{month:02d}%" # For LIKE query

    # Fetch all records for the month to calculate total duration first
    cursor.execute('''
        SELECT project_path, SUM(duration) as total_duration_for_project
        FROM time_records
        WHERE date LIKE ?
        GROUP BY project_path
    ''', (date_prefix,))
    records_grouped = cursor.fetchall() # These are project_path, sum(duration) for that project

    # Get number of days with actual time records for accurate averaging
    cursor.execute('''
        SELECT COUNT(DISTINCT date)
        FROM time_records
        WHERE date LIKE ?
    ''', (date_prefix,))
    actual_days_with_time_records = cursor.fetchone()[0] or 0
    
    avg_days_for_calc = actual_days_with_time_records if actual_days_with_time_records > 0 else 1
    
    # Calculate overall total duration for the month from the grouped records
    month_total_duration_seconds = sum(item[1] for item in records_grouped)

    output = [f"\n[{year_month} Monthly Statistics ({actual_days_with_time_records} day(s) with records)]"]
    output.append(f"Overall Total Time: {time_format_duration(month_total_duration_seconds, avg_days_for_calc)}")


    if not records_grouped: # Check if any records were found
        print('\n'.join(output)) # Print header and total time (which will be 0m)
        print(f"No records found for {year_month}.")
        return

    # Build project tree
    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})})
    cursor.execute("SELECT child, parent FROM parent_child")
    parent_map = {child: parent_val for child, parent_val in cursor.fetchall()}

    # Re-fetch individual records for tree building if needed, or use records_grouped if structure is appropriate
    # The current tree building logic expects (project_path, duration) for each entry,
    # not (project_path, sum_duration_for_project).
    # So we need to fetch the individual records again, or adapt the tree building.
    # For simplicity and consistency with other functions, let's use the full records for tree building logic.
    # However, the prompt's original code already iterated `records` which was `GROUP BY project_path`.
    # This implies the tree building logic was intended to work with summed durations per project_path for the month.
    # Let's stick to the original logic for tree building using the grouped records.

    for project_path, duration in records_grouped: # project_path here is unique for the month
        parts = project_path.split('_')
        if not parts: continue

        current_level_path = parts[0]
        top_level_category = parent_map.get(current_level_path, current_level_path.upper())

        if top_level_category not in tree:
            tree[top_level_category] = {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})}
        
        # Since duration is already SUM(duration) for this project_path for the entire month,
        # we add it to the top-level and potentially to one child if path is compound.
        # The original logic seems to sum durations again, which might be incorrect if `records`
        # already contains summed durations.
        # Correct approach for monthly summary based on `GROUP BY project_path`:
        
        # Add total duration for this project_path to the top-level category
        tree[top_level_category]['duration'] += duration 
        
        current_node = tree[top_level_category]
        # If project_path is compound (e.g., study_ml), add this duration to the sub-category as well.
        # The duration is for the *entire* project_path, not just the part.
        
        # The original loop structure for parts was designed for individual time entries.
        # For monthly summary with pre-grouped project_paths, the logic needs adjustment
        # if we want to build a fine-grained tree from individual records.
        # However, the current structure of query_month_summary's tree building iterates through `parts`
        # as if building a hierarchy from a single `project_path` string that represents the entire month's
        # activity for that specific path. This means if `project_path` is `study_ml`, `study` gets the duration,
        # and then `ml` (as a child of `study`) also gets that same duration. This is how it was.
        # To make it more accurate for a summary view:
        # The duration for 'study_ml' should contribute to 'study' (top-level) and then 'ml' (child).
        # The current code correctly adds to `tree[top_level_category]['duration']`.
        # Then, for sub-parts:
        
        temp_node_for_path_traversal = tree[top_level_category]
        if len(parts) > 1: # Only if there are sub-parts like 'study_ml'
            for i in range(1, len(parts)): # Start from the first sub-part
                child_name = parts[i]
                if child_name not in temp_node_for_path_traversal['children']:
                    temp_node_for_path_traversal['children'][child_name] = {'duration': 0, 'children': defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})}
                # The duration here is the total for project_path for the month
                temp_node_for_path_traversal['children'][child_name]['duration'] += duration 
                temp_node_for_path_traversal = temp_node_for_path_traversal['children'][child_name]


    sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
    for top_level, subtree_data in sorted_top_level:
        output_lines_detail = [f"\n{top_level}: {time_format_duration(subtree_data['duration'], avg_days_for_calc)}"]
        # Pass the correct subtree_data to generate_sorted_output
        output_lines_detail.extend(generate_sorted_output(subtree_data, avg_days=avg_days_for_calc, indent=1))
        output.append('\n'.join(output_lines_detail)) # Append to the main output list
    
    print('\n'.join(output))
