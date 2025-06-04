import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
import calendar

# --- Utility Functions ---
def time_to_seconds(t):
    try:
        if not t: return 0
        h, m = map(int, t.split(':'))
        return h * 3600 + m * 60
    except:
        return 0

def time_format_duration(seconds, avg_days=1):
    '''总时间长度和平均长度函数'''
    # 计算总时长
    total_hours = seconds // 3600
    total_minutes = (seconds % 3600) // 60
    time_str = f"{total_hours}h{total_minutes:02d}m" if total_hours > 0 else f"{total_minutes}m"

    # 如果 avg_days > 1，计算并格式化平均时长
    if avg_days > 1:
        total_h = seconds / 3600  # 总小时数
        avg_h = total_h / avg_days  # 平均小时数
        avg_hours = int(avg_h)  # 整数小时部分
        fractional_hours = avg_h - avg_hours  # 小数小时部分
        avg_minutes = int(fractional_hours * 60 + 0.5)  # 转换为分钟并四舍五入
        avg_str = f"{avg_hours}h{avg_minutes:02d}m"  # 平均时长字符串
        return f"{time_str} ({avg_str}/day)"
    else:
        return time_str

def generate_sorted_output(node, avg_days=1, indent=0):
    """递归生成按时间降序排列的输出行，仅输出有有效数据的子节点"""
    lines = []
    # 从 'children' 键中获取子项目
    children = [(k, v) for k, v in node['children'].items()] if 'children' in node else []
    # 按时长降序排序
    sorted_children = sorted(children, key=lambda x: x[1].get('duration', 0), reverse=True)

    for key, value in sorted_children:
        duration = value.get('duration', 0)
        has_children = 'children' in value and value['children']
        # 仅当 duration > 0 或有子节点时输出
        if duration > 0 or has_children:
            lines.append('  ' * indent + f"{key}: {time_format_duration(duration, avg_days)}")
            # 递归处理子节点
            if has_children:
                lines.extend(generate_sorted_output(value, avg_days, indent + 1))
    return lines

# --- Database Core Functions ---
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
        'program':'Program', 'arrange':'ARRANGE',
    }

    for child, parent in top_level_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent))

    conn.commit()
    return conn

def parse_file(conn, filepath):
    '''解析文输入的文件'''
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
                        for start, end, project_path, duration in time_records:
                            cursor.execute('''
                                INSERT OR REPLACE INTO time_records
                                VALUES (?, ?, ?, ?, ?)
                            ''', (current_date, start, end, project_path, duration))
                            parts = project_path.split('_')
                            for i in range(len(parts)):
                                child = '_'.join(parts[:i+1])
                                parent = '_'.join(parts[:i]) if i > 0 else parts[0]
                                cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent,))
                                parent_result = cursor.fetchone()
                                if parent_result:
                                    parent = parent_result[0]
                                elif i == 0:
                                    cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                                    if not cursor.fetchone():
                                        cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)',
                                                       (child, 'STUDY' if child == 'study' else child.upper()))
                                    continue
                                cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent))
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
                    project_path = project_path.lower().replace('stduy', 'study')
                    start_sec = time_to_seconds(start)
                    end_sec = time_to_seconds(end)
                    if end_sec < start_sec:
                        end_sec += 86400
                    duration = end_sec - start_sec
                    time_records.append((start, end, project_path, duration))
            except Exception as e:
                print(f"解析错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                print(f"错误信息: {str(e)}")
                continue

    if current_date:
        cursor.execute('''
            UPDATE days SET status=?, remark=?, getup_time=?
            WHERE date=?
        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
        for start, end, project_path, duration in time_records:
            cursor.execute('''
                INSERT OR REPLACE INTO time_records
                VALUES (?, ?, ?, ?, ?)
            ''', (current_date, start, end, project_path, duration))
            parts = project_path.split('_')
            for i in range(len(parts)):
                child = '_'.join(parts[:i+1])
                parent = '_'.join(parts[:i]) if i > 0 else parts[0]
                cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent,))
                parent_result = cursor.fetchone()
                if parent_result:
                    parent = parent_result[0]
                elif i == 0:
                    cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                    if not cursor.fetchone():
                        cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)',
                                       (child, 'STUDY' if child == 'study' else child.upper()))
                    continue
                cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent))
    conn.commit()

def get_study_times(conn, year):
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
    study_times = dict(cursor.fetchall())
    return study_times

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
    if remark.strip():
        output.append(f"Remark:{remark}")

    cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date,))
    records = cursor.fetchall()

    cursor.execute('SELECT SUM(duration) FROM time_records WHERE date = ?', (date,))
    total_duration = cursor.fetchone()[0] or 0
    total_h = total_duration // 3600
    total_m = (total_duration % 3600) // 60
    total_minutes = total_duration // 60
    output.append(f"Total: {total_h}h{total_m:02d}m ({total_minutes} minutes)")

    if records:
        tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
        for project_path, duration in records:
            parts = project_path.split('_')
            if not parts:
                continue
            top_level = 'STUDY' if parts[0].lower() == 'study' else parts[0].upper()
            tree[top_level]['duration'] += duration
            current = tree[top_level]
            for part in parts[1:]:
                if not isinstance(current['children'].get(part), dict):
                    current['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
                current['children'][part]['duration'] += duration
                current = current['children'][part]

        sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
        for top_level, subtree in sorted_top_level:
            percentage = (subtree['duration'] / total_duration * 100) if total_duration else 0
            output.append(f"\n{top_level}: {time_format_duration(subtree['duration'])} ({percentage:.2f}%)")
            output.extend(generate_sorted_output(subtree, avg_days=1, indent=1))

    print('\n'.join(output))

def query_period(conn, days):
    '''查询最近几天'''
    cursor = conn.cursor()
    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=days-1)
    
    end_date_str = end_date_dt.strftime("%Y%m%d")
    start_date_str = start_date_dt.strftime("%Y%m%d")

    cursor.execute('''
        SELECT
            SUM(CASE WHEN status = 'True' THEN 1 ELSE 0 END) as true_count,
            SUM(CASE WHEN status = 'False' THEN 1 ELSE 0 END) as false_count,
            COUNT(DISTINCT date) as total_recorded_days
        FROM days
        WHERE date BETWEEN ? AND ?
    ''', (start_date_str, end_date_str))

    status_data = cursor.fetchone()
    true_count = status_data[0] or 0
    false_count = status_data[1] or 0
    # total_days_with_status_records = status_data[2] or 0 # Days with entries in 'days' table

    # Fetch distinct days from time_records to accurately count active days for time averaging
    cursor.execute('''
        SELECT COUNT(DISTINCT date)
        FROM time_records
        WHERE date BETWEEN ? AND ?
    ''', (start_date_str, end_date_str))
    actual_days_with_time_records = cursor.fetchone()[0] or 0


    print(f"\n[最近{days}天统计] {start_date_str} - {end_date_str}")
    # print(f"期间总天数: {days}天")
    print(f"有效记录天数 (有时间条目): {actual_days_with_time_records}天")


    if actual_days_with_time_records > 0: # Use actual_days_with_time_records for meaningful status distribution if desired
        print("状态分布 (基于有时间记录的天数):") # Or clarify if it's based on 'days' table entries
        print(f" True: {true_count}天 ({(true_count/actual_days_with_time_records*100 if actual_days_with_time_records > 0 else 0):.1f}%)")
        print(f" False: {false_count}天 ({(false_count/actual_days_with_time_records*100 if actual_days_with_time_records > 0 else 0):.1f}%)")
    else:
        print("状态分布: 无时间记录天数无法计算百分比")
        print(f" True: {true_count}天")
        print(f" False: {false_count}天")


    cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?',
                   (start_date_str, end_date_str))
    records = cursor.fetchall()

    if not records:
        print("\n无有效时间记录")
        return

    overall_total_duration_seconds = sum(item[1] for item in records)
    avg_days_for_calc = actual_days_with_time_records if actual_days_with_time_records > 0 else 1 # Avoid division by zero

    print(f"\n总时间: {time_format_duration(overall_total_duration_seconds, avg_days_for_calc)}")

    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for project_path, duration in records:
        parts = project_path.split('_')
        if not parts:
            continue
        top_level = 'STUDY' if parts[0].lower() == 'study' else parts[0].upper()
        tree[top_level]['duration'] += duration
        current = tree[top_level]
        for part in parts[1:]:
            if not isinstance(current['children'].get(part), dict):
                current['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            current['children'][part]['duration'] += duration
            current = current['children'][part]

    sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)

    for top_level, subtree in sorted_top_level:
        total_duration_category = subtree['duration']
        print(f"\n{top_level}: {time_format_duration(total_duration_category, avg_days_for_calc)}")
        print('\n'.join(generate_sorted_output(subtree, avg_days=avg_days_for_calc, indent=1)))


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
    if remark and remark.strip(): # Ensure remark is not None and not just whitespace
        output.append(f"Remark:{remark}")
    else:
        output.append("Remark:")


    for start, end, project in records:
        output.append(f"{start}~{end}{project}")

    print('\n'.join(output))

def query_month_summary(conn, year_month):
    '''查询某月的数据'''
    cursor = conn.cursor()

    if not re.match(r'^\d{6}$', year_month):
        print("月份格式错误,应为YYYYMM")
        return

    year = int(year_month[:4])
    month = int(year_month[4:6])
    
    # Determine the number of days in the month
    num_days_in_month = calendar.monthrange(year, month)[1]

    start_date = f"{year}{month:02d}01"
    end_date = f"{year}{month:02d}{num_days_in_month}"
    
    date_prefix = f"{year}{month:02d}%" # For LIKE query

    # Get distinct days with time records in the month for accurate averaging
    cursor.execute('''
        SELECT COUNT(DISTINCT date)
        FROM time_records
        WHERE date LIKE ?
    ''', (date_prefix,))
    actual_days_with_time_records = cursor.fetchone()[0] or 0
    
    avg_days_for_calc = actual_days_with_time_records if actual_days_with_time_records > 0 else 1


    cursor.execute('''
        SELECT project_path, SUM(duration)
        FROM time_records
        WHERE date LIKE ?
        GROUP BY project_path
    ''', (date_prefix,))
    records = cursor.fetchall()

    if not records:
        print(f"没有找到 {year_month} 的记录")
        return

    month_total_duration_seconds = sum(item[1] for item in records)
    output = [f"\n[{year_month} 月统计 ({actual_days_with_time_records}天有记录)]"]

    output.append(f"总时间: {time_format_duration(month_total_duration_seconds, avg_days_for_calc)}")

    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for project_path, duration in records:
        parts = project_path.split('_')
        if not parts:
            continue
        top_level = 'STUDY' if parts[0].lower() == 'study' else parts[0].upper()
        tree[top_level]['duration'] += duration
        current = tree[top_level]
        for part in parts[1:]:
            if not isinstance(current['children'].get(part), dict):
                current['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            current['children'][part]['duration'] += duration
            current = current['children'][part]

    sorted_top_level = sorted(tree.items(), key=lambda x: x[1].get('duration', 0), reverse=True)
    for top_level, subtree in sorted_top_level:
        total_duration_category = subtree['duration']
        output.append(f"\n{top_level}: {time_format_duration(total_duration_category, avg_days_for_calc)}")
        output.extend(generate_sorted_output(subtree, avg_days=avg_days_for_calc, indent=1))
    print('\n'.join(output))