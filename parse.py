import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
# Assuming parse_colors_config.py exists in the same directory or is in PYTHONPATH
# from parse_colors_config import DEFAULT_COLOR_PALETTE, YELLOW

# Placeholder for color constants if parse_colors_config is not available
DEFAULT_COLOR_PALETTE = ['#ebedf0', '#c6e48b', '#7bc96f', '#239a3b', '#196127']
YELLOW = '#fdd835'

def return_color(study_time):
    hours = study_time / 3600
    if hours == 0:
        return DEFAULT_COLOR_PALETTE[0]
    elif hours < 4:
        return DEFAULT_COLOR_PALETTE[1]
    elif hours < 8:
        return DEFAULT_COLOR_PALETTE[2]
    elif hours < 10:
        return DEFAULT_COLOR_PALETTE[3]
    elif hours < 12:
        return DEFAULT_COLOR_PALETTE[4]
    else:
        return YELLOW

def generate_heatmap(conn, year, output_file):
    from datetime import datetime, timedelta # Ensure these are imported locally if not globally
    study_times = get_study_times(conn, year)

    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)

    first_weekday = start_date.weekday()
    front_empty_days = (6 - first_weekday) % 7 if first_weekday != 6 else 0

    total_days = (end_date - start_date).days + 1
    total_slots = front_empty_days + total_days
    back_empty_days = (7 - (total_slots % 7)) % 7

    heatmap_data = []
    for _ in range(front_empty_days):
        heatmap_data.append((None, 'empty', 0))

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        study_time = study_times.get(date_str, 0)
        color = return_color(study_time)
        heatmap_data.append((current_date, color, study_time))
        current_date += timedelta(days=1)

    for _ in range(back_empty_days):
        heatmap_data.append((None, 'empty', 0))

    cell_size = 12
    spacing = 3
    weeks = 53
    rows = 7

    margin_top = 20
    margin_left = 30
    width = margin_left + weeks * (cell_size + spacing)
    height = margin_top + rows * (cell_size + spacing)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']

    days_of_week = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for i, day in enumerate(days_of_week):
        y = margin_top + i * (cell_size + spacing) + cell_size / 2
        svg.append(f'<text x="0" y="{y}" font-size="10" alignment-baseline="middle">{day}</text>')

    months = calendar.month_abbr[1:] # Using calendar.month_abbr for month names
    month_positions = []
    
    # Corrected month marking logic
    # Store the first week index for each month that appears in the heatmap_data
    month_labels = {} # To store unique month labels and their first week index
    for i, (date_obj, _, _) in enumerate(heatmap_data):
        if date_obj:
            week_index = i // 7
            month_num = date_obj.month
            if month_num not in month_labels:
                 # Only add if it's the start of a new column for the month or first occurrence
                if week_index == 0 or (i > 0 and heatmap_data[i-1][0] is None) or \
                   (i > 0 and heatmap_data[i-1][0] and heatmap_data[i-1][0].month != month_num):
                    month_labels[month_num] = week_index
            # Ensure we capture the first day of the month if it starts mid-week in an existing column
            elif date_obj.day == 1 and week_index < month_labels.get(month_num, float('inf')):
                month_labels[month_num] = week_index


    # More robust month label placement
    # Iterate through months and place labels based on the first day of the month's column
    # We need to find the column (week_index) where each month approximately starts
    # A simpler approach: mark month at the start of its first full week or its actual first day's column
    
    # Reset and use a clearer approach for month labels
    month_markers = {} # month_number: week_column_index
    # Find the first occurrence of each month
    for col in range(weeks):
        # Check the first potential day in this column that is not an empty front day
        day_idx_in_heatmap = col * 7 + front_empty_days # Heuristic: aim for Sunday of the week
        if day_idx_in_heatmap < len(heatmap_data):
            actual_day_tuple = heatmap_data[day_idx_in_heatmap]
            if actual_day_tuple[0] is not None: # If it's a real date
                month = actual_day_tuple[0].month
                if month not in month_markers:
                    month_markers[month] = col
    
    for month_num, week_idx in month_markers.items():
        x = margin_left + week_idx * (cell_size + spacing) + (cell_size / 2) # Centered on the week
        svg.append(f'<text x="{x}" y="{margin_top - 5}" font-size="10" text-anchor="middle">{calendar.month_abbr[month_num]}</text>')


    for i, (date, color, study_time) in enumerate(heatmap_data):
        if date is not None:
            week_index = i // 7
            day_index = i % 7
            x = margin_left + week_index * (cell_size + spacing)
            y = margin_top + day_index * (cell_size + spacing)
            duration_str = time_format_duration(study_time)
            title_text = f"{date.strftime('%Y-%m-%d')}: {duration_str}"
            svg.append(f'<rect width="{cell_size}" height="{cell_size}" x="{x}" y="{y}" fill="{color}" rx="2" ry="2">')
            svg.append(f'    <title>{title_text}</title>')
            svg.append(f'</rect>')

    svg.append('</svg>')

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub Style Heatmap for {year}</title>
    </head>
    <body>
        <div style="padding: 20px;">
        <h2>Study Heatmap for {year}</h2>
        {''.join(svg)}
        </div>
    </body>
    </html>
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

def time_to_seconds(t):
    try:
        if not t: return 0
        h, m = map(int, t.split(':'))
        return h * 3600 + m * 60
    except:
        return 0

def time_format_duration(seconds, avg_days=1):
    '''总时间长度和平均长度函数'''
    if seconds < 0: seconds = 0 # Ensure non-negative

    total_hours = seconds // 3600
    total_minutes = (seconds % 3600) // 60
    time_str = f"{total_hours}h{total_minutes:02d}m" if total_hours > 0 or total_minutes > 0 else "0m"
    if total_hours == 0 and total_minutes == 0 and seconds > 0: # Handle cases like 30s as 0m
         time_str = "<1m" # Or f"{seconds}s" if you prefer seconds for small durations

    if avg_days > 0 and avg_days != 1: # Calculate average only if avg_days is specified and not 1
        avg_seconds_per_day = seconds / avg_days
        avg_hours = int(avg_seconds_per_day // 3600)
        avg_minutes = int((avg_seconds_per_day % 3600) // 60)
        avg_str = f"{avg_hours}h{avg_minutes:02d}m/day"
        return f"{time_str} ({avg_str})"
    else:
        return time_str

def get_study_times(conn, year):
    cursor = conn.cursor()
    start_date_str = f"{year}0101"
    end_date_str = f"{year}1231"
    cursor.execute('''
        SELECT date, SUM(duration)
        FROM time_records
        WHERE date BETWEEN ? AND ?
        AND (project_path = 'study' OR project_path LIKE 'study\_%')
        GROUP BY date
    ''', (start_date_str, end_date_str)) # Ensure variable names match placeholders
    study_times = dict(cursor.fetchall())
    return study_times

def init_db():
    conn = sqlite3.connect('time_tracking.db')
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY,
            status TEXT,
            remark TEXT,
            getup_time TEXT
        );

        CREATE TABLE IF NOT EXISTS time_records (
            date TEXT,
            start TEXT,
            end TEXT,
            project_path TEXT,
            duration INTEGER,
            PRIMARY KEY(date, start)
        );

        CREATE TABLE IF NOT EXISTS parent_child (
            child TEXT PRIMARY KEY,
            parent TEXT
        );

        CREATE TABLE IF NOT EXISTS parent_time (
            date TEXT,
            parent TEXT,
            duration INTEGER,
            PRIMARY KEY(date, parent)
        );
    ''')

    top_level_map = {
        'study': 'STUDY', 'code': 'CODE', 'routine': 'ROUTINE', 'break': 'BREAK',
        'rest': 'REST', 'exercise': 'EXERCISE', 'sleep': 'SLEEP',
        'recreation': 'RECREATION', 'other': 'OTHER', 'meal': 'MEAL',
        'program': 'PROGRAM', 'arrange': 'ARRANGE', # Corrected 'Program' to 'PROGRAM' for consistency
    }

    for child, parent in top_level_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent))

    conn.commit()
    return conn

def parse_file(conn, filepath):
    cursor = conn.cursor()
    current_date = None
    day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
    time_records = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('Date:'):
                    if current_date:
                        cursor.execute('''
                            UPDATE days SET status=?, remark=?, getup_time=?
                            WHERE date=?
                        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
                        for start_r, end_r, project_path_r, duration_r in time_records:
                            cursor.execute('''
                                INSERT OR REPLACE INTO time_records
                                VALUES (?, ?, ?, ?, ?)
                            ''', (current_date, start_r, end_r, project_path_r, duration_r))
                            # Dynamic parent_child population (simplified)
                            parts = project_path_r.split('_')
                            for i in range(len(parts)):
                                child = '_'.join(parts[:i+1])
                                parent_guess = '_'.join(parts[:i]) if i > 0 else parts[0].upper() # Default parent
                                if i == 0: # Top-level
                                     # Use predefined map or default to UPPERCASE
                                    default_parent = child.upper()
                                    cursor.execute('''SELECT parent FROM parent_child WHERE child = ?''', (child,))
                                    existing = cursor.fetchone()
                                    if not existing:
                                         # Look for predefined top-level names like 'study' -> 'STUDY'
                                        cursor.execute('''SELECT parent FROM parent_child WHERE child = ?''', (parts[0],))
                                        predefined_parent_row = cursor.fetchone()
                                        if predefined_parent_row:
                                            parent_guess = predefined_parent_row[0]
                                        else: # if not predefined, child itself is the parent in uppercase form
                                            parent_guess = child.upper() # Ensure top-level has a "parent" (itself in uppercase)
                                        cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)',(child, parent_guess))
                                elif i > 0: # Sub-levels
                                    parent_explicit = '_'.join(parts[:i])
                                    cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent_explicit))


                    day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
                    time_records = []
                    current_date = line[5:].strip()
                    cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (current_date,))
                elif line.startswith('Status:'):
                    day_info['status'] = line[7:].strip()
                elif line.startswith('Remark:'):
                    day_info['remark'] = line[7:].strip()
                elif line.startswith('Getup:'):
                    day_info['getup_time'] = line[6:].strip()
                elif '~' in line:
                    match = re.match(r'^(\d+:\d+)~(\d+:\d+)\s*([a-zA-Z0-9_-]+)', line)
                    if not match:
                        print(f"格式错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                        continue
                    start, end, project_path = match.groups()
                    project_path = project_path.lower().replace('stduy', 'study') # Common typo
                    start_sec = time_to_seconds(start)
                    end_sec = time_to_seconds(end)
                    if end_sec < start_sec: # Handles overnight tasks
                        end_sec += 86400
                    duration = end_sec - start_sec
                    time_records.append((start, end, project_path, duration))
            except Exception as e:
                print(f"解析错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                print(f"错误信息: {str(e)}")
                continue

    if current_date: # Process the last day's records
        cursor.execute('''
            UPDATE days SET status=?, remark=?, getup_time=?
            WHERE date=?
        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
        for start_r, end_r, project_path_r, duration_r in time_records:
            cursor.execute('''
                INSERT OR REPLACE INTO time_records
                VALUES (?, ?, ?, ?, ?)
            ''', (current_date, start_r, end_r, project_path_r, duration_r))
            # Simplified parent_child logic again for the last entry
            parts = project_path_r.split('_')
            for i in range(len(parts)):
                child = '_'.join(parts[:i+1])
                if i == 0:
                    default_parent = child.upper()
                    cursor.execute('''SELECT parent FROM parent_child WHERE child = ?''', (parts[0],))
                    predefined_parent_row = cursor.fetchone()
                    if predefined_parent_row:
                        parent_to_insert = predefined_parent_row[0]
                    else:
                        parent_to_insert = default_parent
                    cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent_to_insert))
                else:
                    parent_explicit = '_'.join(parts[:i])
                    cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent_explicit))
    conn.commit()


def generate_sorted_output(node, avg_days=1, indent=0):
    lines = []
    children = [(k, v) for k, v in node.get('children', {}).items()] # Ensure 'children' key exists
    sorted_children = sorted(children, key=lambda x: x[1].get('duration', 0), reverse=True)

    for key, value in sorted_children:
        duration = value.get('duration', 0)
        # Check if value itself is a dictionary and has 'children' and they are not empty
        has_children = isinstance(value, dict) and 'children' in value and value['children']

        if duration > 0 or has_children:
            lines.append('  ' * indent + f"{key}: {time_format_duration(duration, avg_days)}")
            if has_children:
                lines.extend(generate_sorted_output(value, avg_days, indent + 1))
    return lines

def get_top_level_parent(cursor, project_part):
    """Helper to find the ultimate top-level parent (e.g., STUDY, CODE)."""
    # First, check if project_part itself is a defined top-level category's child
    cursor.execute("SELECT parent FROM parent_child WHERE child = ?", (project_part,))
    res = cursor.fetchone()
    if res:
        # If 'study' maps to 'STUDY', res[0] would be 'STUDY'
        # If 'code_python' maps to 'code', this won't hit directly for 'code_python'
        # We need to trace up if needed, but for the first part, this should be fine.
        return res[0]
    return project_part.upper() # Default to uppercase if not found


def query_day(conn, date):
    '''查询某日'''
    cursor = conn.cursor()
    cursor.execute('SELECT status, remark, getup_time FROM days WHERE date = ?', (date,))
    day_data = cursor.fetchone()

    if not day_data:
        print(f"\n[{date}]\n无相关记录!")
        return

    status, remark, getup = day_data
    output = [f"\nDate:{date}", f"Status:{status}", f"Getup:{getup}"]
    if remark and remark.strip(): # Ensure remark is not None before stripping
        output.append(f"Remark:{remark}")

    # Calculate and add total time first
    cursor.execute('SELECT SUM(duration) FROM time_records WHERE date = ?', (date,))
    total_duration_day = cursor.fetchone()[0] or 0
    output.append(f"Total: {time_format_duration(total_duration_day, avg_days=1)}") # Using avg_days=1

    cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date,))
    records = cursor.fetchall()

    if records:
        tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
        for project_path, duration in records:
            parts = project_path.split('_')
            if not parts:
                continue
            
            top_level_key = get_top_level_parent(cursor, parts[0])
            
            current_level_node = tree[top_level_key]
            current_level_node['duration'] += duration

            for part in parts[1:]: # Iterate through sub-parts if they exist
                # Ensure children is a dict; it should be by defaultdict structure
                if not isinstance(current_level_node['children'], dict):
                     current_level_node['children'] = defaultdict(dict) # Should not happen with defaultdict

                if part not in current_level_node['children']:
                    current_level_node['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
                
                current_level_node['children'][part]['duration'] += duration
                current_level_node = current_level_node['children'][part]


        sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
        for top_level, subtree in sorted_top_level:
            percentage = (subtree['duration'] / total_duration_day * 100) if total_duration_day else 0
            output.append(f"\n{top_level}: {time_format_duration(subtree['duration'])} ({percentage:.2f}%)")
            output.extend(generate_sorted_output(subtree, avg_days=1, indent=1))

    print('\n'.join(output))


def query_period(conn, days_to_query): # Renamed 'days' to 'days_to_query' for clarity
    '''查询最近几天'''
    cursor = conn.cursor()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days_to_query - 1)).strftime("%Y%m%d")

    output_lines = [f"\n[最近{days_to_query}天统计] {start_date} - {end_date}"]

    cursor.execute('''
        SELECT SUM(CASE WHEN status = 'True' THEN 1 ELSE 0 END) as true_count,
               SUM(CASE WHEN status = 'False' THEN 1 ELSE 0 END) as false_count,
               COUNT(*) as total_recorded_days
        FROM days
        WHERE date BETWEEN ? AND ?
    ''', (start_date, end_date))

    status_data = cursor.fetchone()
    true_count = status_data[0] or 0
    false_count = status_data[1] or 0
    total_recorded_days = status_data[2] or 0 # Days with any entry in 'days' table

    output_lines.append(f"有效记录天数 (in days table): {total_recorded_days}天 / {days_to_query}天")
    output_lines.append("状态分布:")
    if total_recorded_days > 0:
        output_lines.append(f" True: {true_count}天 ({(true_count / total_recorded_days * 100):.1f}%)")
        output_lines.append(f" False: {false_count}天 ({(false_count / total_recorded_days * 100):.1f}%)")
    else:
        output_lines.append(" True: 0天 (0.0%)")
        output_lines.append(" False: 0天 (0.0%)")


    cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?',
                   (start_date, end_date))
    records = cursor.fetchall()

    if not records:
        output_lines.append("\n无有效时间记录")
        print('\n'.join(output_lines))
        return

    # Calculate and print Grand Total Time for the period first
    grand_total_duration_period = sum(duration for _, duration in records)
    # Use days_to_query for averaging, assuming we want average over the whole period regardless of recorded days
    output_lines.append(f"\n期间总时间: {time_format_duration(grand_total_duration_period, days_to_query)}")


    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for project_path, duration in records:
        parts = project_path.split('_')
        if not parts:
            continue
        
        top_level_key = get_top_level_parent(cursor, parts[0])
            
        current_level_node = tree[top_level_key]
        current_level_node['duration'] += duration

        for part in parts[1:]:
            if not isinstance(current_level_node['children'], dict):
                 current_level_node['children'] = defaultdict(dict)
            if part not in current_level_node['children']:
                current_level_node['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            
            current_level_node['children'][part]['duration'] += duration
            current_level_node = current_level_node['children'][part]


    sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)

    for top_level, subtree in sorted_top_level:
        category_total_duration = subtree['duration']
        percentage_of_grand_total = (category_total_duration / grand_total_duration_period * 100) if grand_total_duration_period else 0
        output_lines.append(f"\n{top_level}: {time_format_duration(category_total_duration, days_to_query)} ({percentage_of_grand_total:.2f}%)")
        output_lines.extend(generate_sorted_output(subtree, avg_days=days_to_query, indent=1))
    
    print('\n'.join(output_lines))


def query_day_raw(conn, date):
    '''输出一日的原始内容'''
    cursor = conn.cursor()

    cursor.execute('''
        SELECT date, status, getup_time, remark
        FROM days
        WHERE date = ?
    ''', (date,))
    day_data = cursor.fetchone()

    if not day_data:
        print(f"日期 {date} 无记录")
        return

    db_date, status, getup, remark = day_data

    cursor.execute('''
        SELECT start, end, project_path
        FROM time_records
        WHERE date = ?
        ORDER BY start
    ''', (date,))
    records = cursor.fetchall()

    output = [f"Date:{db_date}", f"Status:{status}", f"Getup:{getup}"]
    if remark and remark.strip(): # Check if remark is not None
        output.append(f"Remark:{remark}")
    else:
        output.append("Remark:")


    for start_time, end_time, project in records: # Renamed variables for clarity
        output.append(f"{start_time}~{end_time} {project}") # Added space before project

    print('\n'.join(output))


def query_month_summary(conn, year_month):
    '''查询某月的数据'''
    cursor = conn.cursor()

    if not re.match(r'^\d{6}$', year_month):
        print("月份格式错误,应为YYYYMM")
        return

    year = int(year_month[:4])
    month = int(year_month[4:6])
    
    try:
        _, last_day = calendar.monthrange(year, month)
    except calendar.IllegalMonthError:
        print(f"无效的月份: {month}")
        return
    except calendar.IllegalYearError: # calendar.IllegalYearError does not exist, year is int.
        print(f"无效的年份: {year}") # Should be caught by YYYYMM regex mostly
        return

    actual_days_in_month = last_day

    date_prefix = f"{year}{month:02d}%" # Query for dates starting with YYYYMM
    
    # Fetch all records for the month to calculate grand total and build tree
    cursor.execute('''
        SELECT project_path, SUM(duration)
        FROM time_records
        WHERE date LIKE ?
        GROUP BY project_path 
    ''', (date_prefix,)) # Use date_prefix for LIKE
    
    # The above query already sums duration by project_path for the month.
    # To get a grand total, we sum these sums.
    # Or, more directly for grand total:
    cursor.execute('''
        SELECT SUM(duration)
        FROM time_records
        WHERE date LIKE ?
    ''', (date_prefix,))
    grand_total_month_duration = cursor.fetchone()[0] or 0

    # Now fetch for the tree structure
    cursor.execute('''
        SELECT project_path, SUM(duration) as monthly_duration
        FROM time_records
        WHERE date LIKE ?
        GROUP BY project_path
    ''', (date_prefix,))
    records = cursor.fetchall()


    output = [f"\n[{year_month[:4]}年{int(year_month[4:6])}月 统计 ({actual_days_in_month}天)]"] # More descriptive header

    if not records: # Check if there are any time records
        output.append(f"总时间: {time_format_duration(0, actual_days_in_month)}")
        output.append("本月无有效时间记录")
        print('\n'.join(output))
        return

    # Print Grand Total for the month first
    output.append(f"总时间: {time_format_duration(grand_total_month_duration, actual_days_in_month)}")


    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for project_path, duration in records: # records are (project_path, sum_duration_for_that_path_in_month)
        parts = project_path.split('_')
        if not parts:
            continue
        
        top_level_key = get_top_level_parent(cursor, parts[0])
        
        # The duration here is the total for this specific project_path over the month
        # We need to add this to the correct place in the tree.
        # The tree accumulates durations if multiple specific paths map to the same tree node.

        current_node = tree[top_level_key]
        current_node['duration'] += duration # Add to top-level's total

        # Traverse/create children nodes
        for part in parts[1:]:
            if not isinstance(current_node['children'], dict) : # Should be handled by defaultdict
                current_node['children'] = defaultdict(dict)
            
            if part not in current_node['children']:
                 current_node['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            
            current_node['children'][part]['duration'] += duration # Add to sub-level's total
            current_node = current_node['children'][part]


    sorted_top_level = sorted(tree.items(), key=lambda x: x[1].get('duration', 0), reverse=True)

    for top_level, subtree in sorted_top_level:
        category_total_duration = subtree['duration'] # This is already summed for the month for this category
        percentage_of_grand_total = (category_total_duration / grand_total_month_duration * 100) if grand_total_month_duration else 0
        output.append(f"\n{top_level}: {time_format_duration(category_total_duration, actual_days_in_month)} ({percentage_of_grand_total:.2f}%)")
        output.extend(generate_sorted_output(subtree, avg_days=actual_days_in_month, indent=1))

    print('\n'.join(output))


def main():
    conn = init_db()

    while True:
        print("\n时间追踪分析器")
        print("-" * 20)
        print("0. 处理文件并导入数据")
        print("1. 查询某日统计")
        print("2. 查询最近7天")
        print("3. 查询最近14天")
        print("4. 查询最近30天")
        print("5. 输出某天原始数据")
        print("6. 生成年度学习热力图")
        print("7. 查询月度统计")
        print("8. 退出")
        print("-" * 20)
        choice = input("请选择操作 (0-8)：").strip()

        if choice == '0':
            input_path = input("请输入单个 .txt 文件路径或包含 .txt 文件的目录路径：").strip('"')
            input_path = os.path.normpath(input_path)

            if os.path.isfile(input_path) and input_path.lower().endswith('.txt'):
                print(f"\n处理文件: {input_path}")
                parse_file(conn, input_path)
                print("文件处理完成。")
            elif os.path.isdir(input_path):
                print(f"\n扫描目录: {input_path}")
                file_count = 0
                for root, _, files in os.walk(input_path):
                    for filename in files:
                        if filename.lower().endswith('.txt'):
                            filepath = os.path.join(root, filename)
                            print(f"  处理文件: {filepath}")
                            parse_file(conn, filepath)
                            file_count += 1
                print(f"目录扫描完成，共处理 {file_count} 个数据文件。")
            else:
                print(f"错误：路径 '{input_path}' 不是有效的 .txt 文件或目录。")
        elif choice == '1':
            date_str = input("请输入日期 (格式 YYYYMMDD，例如 20230115): ")
            if re.match(r'^\d{8}$', date_str):
                query_day(conn, date_str)
            else:
                print("日期格式错误，应为 YYYYMMDD。")
        elif choice in ('2', '3', '4'):
            days_map = {'2': 7, '3': 14, '4': 30}
            query_period(conn, days_map[choice])
        elif choice == '5':
            date_str = input("请输入日期 (格式 YYYYMMDD): ")
            if re.match(r'^\d{8}$', date_str):
                query_day_raw(conn, date_str)
            else:
                print("日期格式错误，应为 YYYYMMDD。")
        elif choice == '6':
            year_str = input("请输入年份 (格式 YYYY，例如 2023): ")
            if re.match(r'^\d{4}$', year_str):
                year = int(year_str)
                output_filename = f"heatmap_study_{year}.html"
                try:
                    generate_heatmap(conn, year, output_filename)
                    print(f"学习热力图已生成：{os.path.abspath(output_filename)}")
                except Exception as e:
                    print(f"生成热力图失败: {e}")
            else:
                print("年份格式错误，应为 YYYY。")
        elif choice == '7':
            year_month_str = input("请输入年份和月份 (格式 YYYYMM，例如 202301): ")
            if re.match(r'^\d{6}$', year_month_str):
                query_month_summary(conn, year_month_str)
            else:
                print("年月格式错误，应为 YYYYMM。")
        elif choice == '8':
            print("正在退出程序...")
            break
        else:
            print("无效选项，请输入0到8之间的数字。")

    conn.close()

if __name__ == '__main__':
    main()
