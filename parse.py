import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

from parse_colors_config import DEFAULT_COLOR_PALETTE, YELLOW

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

    current_date_iter = start_date # Renamed to avoid conflict with outer scope variables
    while current_date_iter <= end_date:
        date_str = current_date_iter.strftime("%Y%m%d")
        study_time = study_times.get(date_str, 0)
        color = return_color(study_time)
        heatmap_data.append((current_date_iter, color, study_time))
        current_date_iter += timedelta(days=1)

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
        y_pos = margin_top + i * (cell_size + spacing) + cell_size / 2 # Renamed y to y_pos
        svg.append(f'<text x="0" y="{y_pos}" font-size="10" alignment-baseline="middle">{day}</text>')
    
    month_markers = {} 
    for col in range(weeks):
        day_idx_in_heatmap = col * 7 
        # Adjust for front_empty_days if heatmap starts with empty slots for first week alignment
        # This finds the *actual* data index for the start of a week column.
        # However, we need to map this to heatmap_data which *includes* front_empty_days
        
        # Let's find the first *actual date* in each column of the displayed grid
        # The 'col' variable represents the visual column index in the heatmap grid.
        # The first data point in this visual column is at heatmap_data[col*7] if no front_empty_days.
        # If there are front_empty_days, these are at the beginning of heatmap_data.
        # The crucial part is how heatmap_data maps to the grid.
        # The grid is 7 rows. `i // 7` gives the week_index (column).
        
        first_day_in_col_idx = col * 7 # index in the conceptual 53x7 grid
        if first_day_in_col_idx < len(heatmap_data):
            date_obj, _, _ = heatmap_data[first_day_in_col_idx]
            if date_obj: # Ensure it's not an empty padding day
                month_num = date_obj.month
                if month_num not in month_markers:
                     # Check if this column is indeed where the month visually starts or is prominent
                    is_first_of_month = date_obj.day == 1
                    # Heuristic: if the first day of month is in this column, or it's the first time we see this month
                    if is_first_of_month or col == 0 or \
                       (heatmap_data[first_day_in_col_idx - 7][0] and heatmap_data[first_day_in_col_idx - 7][0].month != month_num):
                        month_markers[month_num] = col


    for month_num, week_idx in month_markers.items():
        x_pos = margin_left + week_idx * (cell_size + spacing) + (cell_size / 2) 
        svg.append(f'<text x="{x_pos}" y="{margin_top - 5}" font-size="10" text-anchor="middle">{calendar.month_abbr[month_num]}</text>')


    for i, (date_val, color_val, study_time_val) in enumerate(heatmap_data): # Renamed variables
        if date_val is not None:
            week_index = i // 7
            day_index = i % 7
            x_pos = margin_left + week_index * (cell_size + spacing)
            y_pos = margin_top + day_index * (cell_size + spacing)
            duration_str = time_format_duration(study_time_val)
            title_text = f"{date_val.strftime('%Y-%m-%d')}: {duration_str}"
            svg.append(f'<rect width="{cell_size}" height="{cell_size}" x="{x_pos}" y="{y_pos}" fill="{color_val}" rx="2" ry="2">')
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
    except ValueError: # More specific exception
        return 0

def time_format_duration(seconds, avg_days=1):
    if not isinstance(seconds, (int, float)) or not isinstance(avg_days, (int, float)):
        return "Invalid input" # Basic type check
    if seconds < 0: seconds = 0 

    total_hours = int(seconds // 3600)
    total_minutes = int((seconds % 3600) // 60)
    
    time_str = f"{total_hours}h{total_minutes:02d}m"
    if total_hours == 0 and total_minutes == 0 :
        if seconds > 0:
             time_str = "<1m" 
        else:
             time_str = "0m"


    if avg_days > 0 and avg_days != 1: 
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
    ''', (start_date_str, end_date_str)) 
    study_times = dict(cursor.fetchall())
    return study_times

def init_db():
    conn = sqlite3.connect('time_tracking.db', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row # Optional: access columns by name
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
            duration INTEGER, /* in seconds */
            FOREIGN KEY(date) REFERENCES days(date) ON DELETE CASCADE, 
            PRIMARY KEY(date, start)
        );

        CREATE TABLE IF NOT EXISTS parent_child (
            child TEXT PRIMARY KEY,
            parent TEXT
        );
        /* parent_time table seems unused in the provided queries, consider removing if not needed elsewhere */
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
        'program': 'PROGRAM', 'arrange': 'ARRANGE', 
    }

    for child, parent_val in top_level_map.items(): # Renamed parent to parent_val
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent_val))

    conn.commit()
    return conn

def _reset_day_info():
    """Returns a new dictionary with default values for a day's information."""
    return {'status': 'False', 'remark': '', 'getup_time': '00:00'}

def _parse_time_log_line(line_content, filepath, line_num):
    """
    Parses a time log line (e.g., '08:00~09:00 study_math').
    Returns a tuple (start, end, project_path, duration) or None on failure.
    """
    match = re.match(r'^(\d{1,2}:\d{2})~(\d{1,2}:\d{2})\s*([a-zA-Z0-9_-]+)', line_content)
    if not match:
        print(f"格式错误在 {os.path.basename(filepath)} 第{line_num}行 (时间记录格式无效): {line_content}")
        return None
    
    start_str, end_str, project_path = match.groups()
    project_path = project_path.lower().replace('stduy', 'study')  # Correct common typo

    start_sec = time_to_seconds(start_str)
    end_sec = time_to_seconds(end_str)

    if end_sec < start_sec:  # Handles tasks that cross midnight
        end_sec += 86400  # Add 24 hours in seconds
    
    duration = end_sec - start_sec
    if duration < 0: # Should not happen if logic is correct, but as a safeguard
        print(f"警告: 计算得到的时长为负数在 {os.path.basename(filepath)} 第{line_num}行: {line_content}. 时长设为0.")
        duration = 0
        
    return start_str, end_str, project_path, duration

def _update_project_hierarchy(cursor, project_path):
    """Updates the parent_child table based on the project_path."""
    parts = project_path.split('_')
    for i in range(len(parts)):
        child_proj = '_'.join(parts[:i + 1])
        
        if i == 0:  # Top-level project part (e.g., 'study', 'code')
            # Check if this top-level part has a predefined parent (e.g., 'study' -> 'STUDY')
            cursor.execute("SELECT parent FROM parent_child WHERE child = ?", (parts[0],))
            predefined_parent_row = cursor.fetchone()
            if predefined_parent_row:
                parent_proj = predefined_parent_row[0]
            else:
                # If not predefined, its "parent" is itself in uppercase,
                # and this child ('study') also needs an entry mapping to this uppercase parent.
                parent_proj = child_proj.upper() 
            # Ensure the child_proj ('study') itself is in the table, pointing to its determined parent_proj ('STUDY')
            cursor.execute("INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)", (child_proj, parent_proj))
        else:  # Sub-level project part (e.g., 'study_math', 'code_python_project1')
            parent_proj = '_'.join(parts[:i])  # The parent is the path one level up
            cursor.execute("INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)", (child_proj, parent_proj))

def _commit_day_entries(cursor, current_date_val, day_info_val, time_records_list):
    """Commits all processed entries for a given day to the database."""
    if not current_date_val:
        return

    # Update day's status, remark, getup_time
    cursor.execute('''
        UPDATE days SET status=?, remark=?, getup_time=?
        WHERE date=?
    ''', (day_info_val['status'], day_info_val['remark'], day_info_val['getup_time'], current_date_val))

    # Insert time records and update project hierarchy
    for start_r, end_r, project_path_r, duration_r in time_records_list:
        cursor.execute('''
            INSERT OR REPLACE INTO time_records (date, start, end, project_path, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (current_date_val, start_r, end_r, project_path_r, duration_r))
        _update_project_hierarchy(cursor, project_path_r)

def parse_file(conn, filepath):
    """
    Parses a time tracking file and imports data into the SQLite database.
    Refactored for better readability and modularity.
    """
    cursor = conn.cursor()
    current_date = None
    day_info = _reset_day_info()
    time_records = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line_text in enumerate(f, 1):
                line_text = line_text.strip()
                if not line_text:
                    continue

                try:
                    if line_text.startswith('Date:'):
                        # Commit previous day's data before starting a new one
                        if current_date:
                            _commit_day_entries(cursor, current_date, day_info, time_records)
                        
                        # Reset for the new day
                        current_date = line_text[5:].strip()
                        day_info = _reset_day_info()
                        time_records = []
                        cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (current_date,))
                    
                    elif line_text.startswith('Status:'):
                        if current_date: day_info['status'] = line_text[7:].strip()
                        else: print(f"警告: 在 {os.path.basename(filepath)} 第{line_num}行找到 'Status' 但日期未设定。")
                    
                    elif line_text.startswith('Remark:'):
                        if current_date: day_info['remark'] = line_text[7:].strip()
                        else: print(f"警告: 在 {os.path.basename(filepath)} 第{line_num}行找到 'Remark' 但日期未设定。")

                    elif line_text.startswith('Getup:'):
                        if current_date: day_info['getup_time'] = line_text[6:].strip()
                        else: print(f"警告: 在 {os.path.basename(filepath)} 第{line_num}行找到 'Getup' 但日期未设定。")
                    
                    elif '~' in line_text:
                        if current_date:
                            parsed_entry = _parse_time_log_line(line_text, filepath, line_num)
                            if parsed_entry:
                                time_records.append(parsed_entry)
                        else:
                             print(f"警告: 在 {os.path.basename(filepath)} 第{line_num}行找到时间记录但日期未设定: {line_text}")
                    
                    # else:
                        # Optionally handle lines that don't match any known format
                        # print(f"信息: 在 {os.path.basename(filepath)} 第{line_num}行发现未知格式行: {line_text}")


                except Exception as e_line: # Catch errors during individual line processing
                    print(f"处理行时发生错误在 {os.path.basename(filepath)} 第{line_num}行: '{line_text}'")
                    print(f"错误详情: {str(e_line)}")
                    # Decide if you want to continue processing other lines or stop for this file
                    continue 
        
        # After the loop, commit the last processed day's entries
        if current_date:
            _commit_day_entries(cursor, current_date, day_info, time_records)
        
        conn.commit()

    except FileNotFoundError:
        print(f"错误: 文件未找到 '{filepath}'")
    except Exception as e_file: # Catch broader errors like file read issues
        print(f"解析文件 '{filepath}' 时发生严重错误: {str(e_file)}")
        conn.rollback() # Rollback any partial commits if a larger error occurs

# --- Other functions (generate_sorted_output, get_top_level_parent, query_day, query_period, etc.) ---
# --- should be placed here or imported if they are in separate files. ---
# --- For this example, I'll assume they are defined as in your original complete script. ---

def generate_sorted_output(node, avg_days=1, indent=0):
    lines = []
    # Ensure 'children' exists and is a dictionary before iterating
    children_items = node.get('children', {})
    if not isinstance(children_items, dict): # Should ideally be a dict due to defaultdict
        children_items = {}

    children = [(k, v) for k, v in children_items.items()]
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

def get_top_level_parent(cursor, project_part_str): # Renamed project_part to project_part_str
    """Helper to find the ultimate top-level parent (e.g., STUDY, CODE)."""
    cursor.execute("SELECT parent FROM parent_child WHERE child = ?", (project_part_str,))
    res = cursor.fetchone()
    if res:
        return res[0] # res is a Row object if row_factory is used, access by index or key
    return project_part_str.upper() 

def query_day(conn, date_query): # Renamed date to date_query
    '''查询某日'''
    cursor = conn.cursor()
    cursor.execute('SELECT status, remark, getup_time FROM days WHERE date = ?', (date_query,))
    day_data = cursor.fetchone()

    if not day_data:
        print(f"\n[{date_query}]\n无相关记录!")
        return

    status, remark_val, getup = day_data['status'], day_data['remark'], day_data['getup_time'] # Using column names if row_factory is set
    output = [f"\nDate:{date_query}", f"Status:{status}", f"Getup:{getup}"]
    if remark_val and remark_val.strip(): 
        output.append(f"Remark:{remark_val}")

    cursor.execute('SELECT SUM(duration) as total_duration FROM time_records WHERE date = ?', (date_query,)) # Alias sum
    total_duration_day_row = cursor.fetchone()
    total_duration_day = total_duration_day_row['total_duration'] if total_duration_day_row and total_duration_day_row['total_duration'] is not None else 0
    
    output.append(f"Total: {time_format_duration(total_duration_day, avg_days=1)}") 

    cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date_query,))
    records = cursor.fetchall()

    if records:
        tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
        for record in records: # Iterate through Row objects
            project_path, duration_val = record['project_path'], record['duration']
            parts = project_path.split('_')
            if not parts:
                continue
            
            top_level_key = get_top_level_parent(cursor, parts[0])
            
            current_level_node = tree[top_level_key]
            current_level_node['duration'] += duration_val

            for part in parts[1:]: 
                if not isinstance(current_level_node.get('children'), dict):
                     current_level_node['children'] = defaultdict(dict) 

                if part not in current_level_node['children']:
                    current_level_node['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
                
                current_level_node['children'][part]['duration'] += duration_val
                current_level_node = current_level_node['children'][part]

        sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
        for top_level, subtree in sorted_top_level:
            percentage = (subtree['duration'] / total_duration_day * 100) if total_duration_day else 0
            output.append(f"\n{top_level}: {time_format_duration(subtree['duration'])} ({percentage:.2f}%)")
            output.extend(generate_sorted_output(subtree, avg_days=1, indent=1))

    print('\n'.join(output))


def query_period(conn, days_to_query): 
    cursor = conn.cursor()
    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=days_to_query - 1)
    end_date_str_q = end_date_dt.strftime("%Y%m%d") # Renamed end_date to avoid conflict
    start_date_str_q = start_date_dt.strftime("%Y%m%d") # Renamed start_date

    output_lines = [f"\n[最近{days_to_query}天统计] {start_date_str_q} - {end_date_str_q}"]

    cursor.execute('''
        SELECT SUM(CASE WHEN status = 'True' THEN 1 ELSE 0 END) as true_count,
               SUM(CASE WHEN status = 'False' THEN 1 ELSE 0 END) as false_count,
               COUNT(DISTINCT date) as total_recorded_days 
        FROM days
        WHERE date BETWEEN ? AND ?
    ''', (start_date_str_q, end_date_str_q)) # Use renamed variables

    status_data = cursor.fetchone()
    true_count = status_data['true_count'] if status_data and status_data['true_count'] is not None else 0
    false_count = status_data['false_count'] if status_data and status_data['false_count'] is not None else 0
    total_recorded_days = status_data['total_recorded_days'] if status_data and status_data['total_recorded_days'] is not None else 0

    output_lines.append(f"有状态记录天数: {total_recorded_days}天 / {days_to_query}天") # Clarified meaning
    output_lines.append("状态分布 (基于有记录的天数):")
    if total_recorded_days > 0:
        output_lines.append(f" True: {true_count}天 ({(true_count / total_recorded_days * 100):.1f}%)")
        output_lines.append(f" False: {false_count}天 ({(false_count / total_recorded_days * 100):.1f}%)")
    else:
        output_lines.append(" True: 0天 (0.0%)")
        output_lines.append(" False: 0天 (0.0%)")


    cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?',
                   (start_date_str_q, end_date_str_q)) # Use renamed variables
    records = cursor.fetchall()

    if not records:
        output_lines.append("\n期间无有效时间记录")
        print('\n'.join(output_lines))
        return

    grand_total_duration_period = sum(rec['duration'] for rec in records if rec['duration'] is not None)
    output_lines.append(f"\n期间总时间: {time_format_duration(grand_total_duration_period, days_to_query)}")


    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for record_item in records: # Renamed record to record_item
        project_path, duration_val = record_item['project_path'], record_item['duration']
        parts = project_path.split('_')
        if not parts:
            continue
        
        top_level_key = get_top_level_parent(cursor, parts[0])
            
        current_level_node = tree[top_level_key]
        current_level_node['duration'] += duration_val

        for part in parts[1:]:
            if not isinstance(current_level_node.get('children'), dict):
                 current_level_node['children'] = defaultdict(dict)
            if part not in current_level_node['children']:
                current_level_node['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            
            current_level_node['children'][part]['duration'] += duration_val
            current_level_node = current_level_node['children'][part]

    sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)

    for top_level, subtree in sorted_top_level:
        category_total_duration = subtree['duration']
        percentage_of_grand_total = (category_total_duration / grand_total_duration_period * 100) if grand_total_duration_period else 0
        output_lines.append(f"\n{top_level}: {time_format_duration(category_total_duration, days_to_query)} ({percentage_of_grand_total:.2f}%)")
        output_lines.extend(generate_sorted_output(subtree, avg_days=days_to_query, indent=1))
    
    print('\n'.join(output_lines))


def query_day_raw(conn, date_query_raw): # Renamed date to date_query_raw
    cursor = conn.cursor()

    cursor.execute('''
        SELECT date, status, getup_time, remark
        FROM days
        WHERE date = ?
    ''', (date_query_raw,)) # Use renamed variable
    day_data = cursor.fetchone()

    if not day_data:
        print(f"日期 {date_query_raw} 无记录")
        return

    db_date, status_val, getup_val, remark_val = day_data['date'], day_data['status'], day_data['getup_time'], day_data['remark']

    cursor.execute('''
        SELECT start, end, project_path
        FROM time_records
        WHERE date = ?
        ORDER BY start ASC /* Explicitly order by start time */
    ''', (date_query_raw,)) # Use renamed variable
    records = cursor.fetchall()

    output = [f"Date:{db_date}", f"Status:{status_val}", f"Getup:{getup_val}"]
    if remark_val and remark_val.strip(): 
        output.append(f"Remark:{remark_val}")
    else:
        output.append("Remark:") # Keep Remark label even if empty for consistent raw output

    for record_detail in records: # Renamed record to record_detail
        output.append(f"{record_detail['start']}~{record_detail['end']} {record_detail['project_path']}") 

    print('\n'.join(output))


def query_month_summary(conn, year_month_str_q): # Renamed year_month
    cursor = conn.cursor()

    if not re.match(r'^\d{6}$', year_month_str_q):
        print("月份格式错误,应为YYYYMM")
        return

    year_val = int(year_month_str_q[:4]) # Renamed year
    month_val = int(year_month_str_q[4:6]) # Renamed month
    
    try:
        _, last_day = calendar.monthrange(year_val, month_val)
    except calendar.IllegalMonthError:
        print(f"无效的月份: {month_val}")
        return
    
    actual_days_in_month = last_day
    date_prefix = f"{year_val}{month_val:02d}%" 
    
    cursor.execute('''
        SELECT SUM(duration) as total_duration
        FROM time_records
        WHERE date LIKE ?
    ''', (date_prefix,))
    grand_total_row = cursor.fetchone()
    grand_total_month_duration = grand_total_row['total_duration'] if grand_total_row and grand_total_row['total_duration'] is not None else 0


    cursor.execute('''
        SELECT project_path, SUM(duration) as monthly_duration
        FROM time_records
        WHERE date LIKE ?
        GROUP BY project_path
    ''', (date_prefix,))
    records = cursor.fetchall()

    output = [f"\n[{year_val}年{month_val}月 统计 ({actual_days_in_month}天)]"] 

    # Always print total time, even if zero
    output.append(f"总时间: {time_format_duration(grand_total_month_duration, actual_days_in_month)}")

    if not records and grand_total_month_duration == 0 : # Check if there are any time records
        output.append("本月无有效时间记录")
        print('\n'.join(output))
        return
    
    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    # Populate tree using the records which are already grouped by project_path with summed durations for the month
    for record_summary in records: # Renamed record to record_summary
        project_path, duration_sum = record_summary['project_path'], record_summary['monthly_duration']
        parts = project_path.split('_')
        if not parts:
            continue
        
        top_level_key = get_top_level_parent(cursor, parts[0])
        
        current_node = tree[top_level_key]
        current_node['duration'] += duration_sum # This adds the pre-summed duration for this path

        # For sub-parts, we also add the full duration_sum of the specific project_path
        # to each node in its hierarchy. This is because `duration_sum` is the total for `project_path`.
        temp_node_for_subparts = current_node 
        for part_idx, part in enumerate(parts[1:]):
            # Ensure children dict exists
            if not isinstance(temp_node_for_subparts.get('children'), dict):
                temp_node_for_subparts['children'] = defaultdict(dict)
            
            # Create child node if it doesn't exist
            if part not in temp_node_for_subparts['children']:
                temp_node_for_subparts['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            
            # Add the full duration of the specific path to this sub-node as well
            # because this sub-node contributes to the total of `project_path`.
            # This seems to be the existing logic: each node in the hierarchy gets the full duration of the leaf.
            # If a sub-node should *only* get durations from its direct children, the logic needs to be different.
            # Current logic: study_math contributes its total to 'study' and to 'math' (under study)
            temp_node_for_subparts['children'][part]['duration'] += duration_sum
            temp_node_for_subparts = temp_node_for_subparts['children'][part]


    sorted_top_level = sorted(tree.items(), key=lambda x: x[1].get('duration', 0), reverse=True)

    for top_level, subtree in sorted_top_level:
        category_total_duration = subtree['duration'] 
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
                parse_file(conn, input_path) # Using the refactored parse_file
                print("文件处理完成。")
            elif os.path.isdir(input_path):
                print(f"\n扫描目录: {input_path}")
                file_count = 0
                for root, _, files in os.walk(input_path):
                    for filename in files:
                        if filename.lower().endswith('.txt'):
                            filepath = os.path.join(root, filename)
                            print(f"  处理文件: {filepath}")
                            parse_file(conn, filepath) # Using the refactored parse_file
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
            year_str_main = input("请输入年份 (格式 YYYY，例如 2023): ") # Renamed year_str
            if re.match(r'^\d{4}$', year_str_main):
                year_val_main = int(year_str_main) # Renamed year
                output_filename = f"heatmap_study_{year_val_main}.html"
                try:
                    generate_heatmap(conn, year_val_main, output_filename)
                    print(f"学习热力图已生成：{os.path.abspath(output_filename)}")
                except Exception as e:
                    print(f"生成热力图失败: {e}")
            else:
                print("年份格式错误，应为 YYYY。")
        elif choice == '7':
            year_month_str_main = input("请输入年份和月份 (格式 YYYYMM，例如 202301): ") # Renamed year_month_str
            if re.match(r'^\d{6}$', year_month_str_main):
                query_month_summary(conn, year_month_str_main)
            else:
                print("年月格式错误，应为 YYYYMM。")
        elif choice == '8':
            print("正在退出程序...")
            break
        else:
            print("无效选项，请输入0到8之间的数字。")

    if conn:
        conn.close()

if __name__ == '__main__':
    main()
