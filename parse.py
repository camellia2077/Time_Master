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

class TimeTrackerDB:
    """Manages database interactions for the time tracking application."""

    def __init__(self, db_path='time_tracking.db'):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._init_schema()
        self._init_predefined_parents()

    def _connect(self):
        """Establishes a database connection."""
        self.conn = sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row

    def _init_schema(self):
        """Initializes the database schema if tables don't exist."""
        cursor = self.conn.cursor()
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
        ''')
        self.conn.commit()

    def _init_predefined_parents(self):
        """Initializes predefined top-level parent-child mappings."""
        cursor = self.conn.cursor()
        top_level_map = {
            'study': 'STUDY', 'code': 'CODE', 'routine': 'ROUTINE', 'break': 'BREAK',
            'rest': 'REST', 'exercise': 'EXERCISE', 'sleep': 'SLEEP',
            'recreation': 'RECREATION', 'other': 'OTHER', 'meal': 'MEAL',
            'program': 'PROGRAM', 'arrange': 'ARRANGE',
        }
        for child, parent_val in top_level_map.items():
            cursor.execute("INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)", (child, parent_val))
        self.conn.commit()

    def get_cursor(self):
        """Returns a database cursor."""
        if not self.conn:
            self._connect()
        return self.conn.cursor()

    def commit(self):
        """Commits the current transaction."""
        if self.conn:
            self.conn.commit()

    def rollback(self):
        """Rolls back the current transaction."""
        if self.conn:
            self.conn.rollback()

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def insert_day_record_if_not_exists(self, date_val):
        cursor = self.get_cursor()
        cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (date_val,))
        # No commit here, will be handled by calling function or LogFileParser

    def update_day_details(self, date_val, status, remark, getup_time):
        cursor = self.get_cursor()
        cursor.execute('UPDATE days SET status=?, remark=?, getup_time=? WHERE date=?',
                       (status, remark, getup_time, date_val))

    def insert_time_record(self, date_val, start_r, end_r, project_path_r, duration_r):
        cursor = self.get_cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO time_records (date, start, end, project_path, duration)
            VALUES (?, ?, ?, ?, ?)
        ''', (date_val, start_r, end_r, project_path_r, duration_r))

    def update_project_hierarchy(self, project_path):
        """Updates the parent_child table based on the project_path."""
        cursor = self.get_cursor()
        parts = project_path.split('_')
        for i in range(len(parts)):
            child_proj = '_'.join(parts[:i + 1])
            if i == 0:
                cursor.execute("SELECT parent FROM parent_child WHERE child = ?", (parts[0],))
                predefined_parent_row = cursor.fetchone()
                parent_proj = predefined_parent_row['parent'] if predefined_parent_row else child_proj.upper()
                cursor.execute("INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)", (child_proj, parent_proj))
            else:
                parent_proj = '_'.join(parts[:i])
                cursor.execute("INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)", (child_proj, parent_proj))
    
    def get_top_level_parent_for_project(self, project_part_str):
        cursor = self.get_cursor()
        cursor.execute("SELECT parent FROM parent_child WHERE child = ?", (project_part_str,))
        res = cursor.fetchone()
        return res['parent'] if res else project_part_str.upper()

    def get_study_times_for_year(self, year):
        cursor = self.get_cursor()
        start_date_str = f"{year}0101"
        end_date_str = f"{year}1231"
        cursor.execute('''
            SELECT date, SUM(duration) as total_duration
            FROM time_records
            WHERE date BETWEEN ? AND ?
            AND (project_path = 'study' OR project_path LIKE 'study\_%')
            GROUP BY date
        ''', (start_date_str, end_date_str))
        return {row['date']: row['total_duration'] for row in cursor.fetchall()}

    def get_day_info(self, date_query):
        cursor = self.get_cursor()
        cursor.execute('SELECT status, remark, getup_time FROM days WHERE date = ?', (date_query,))
        return cursor.fetchone()

    def get_day_total_duration(self, date_query):
        cursor = self.get_cursor()
        cursor.execute('SELECT SUM(duration) as total_duration FROM time_records WHERE date = ?', (date_query,))
        row = cursor.fetchone()
        return row['total_duration'] if row and row['total_duration'] is not None else 0
        
    def get_day_time_records(self, date_query):
        cursor = self.get_cursor()
        cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date_query,))
        return cursor.fetchall()

    def get_period_status_summary(self, start_date, end_date):
        cursor = self.get_cursor()
        cursor.execute('''
            SELECT SUM(CASE WHEN status = 'True' THEN 1 ELSE 0 END) as true_count,
                   SUM(CASE WHEN status = 'False' THEN 1 ELSE 0 END) as false_count,
                   COUNT(DISTINCT date) as total_recorded_days
            FROM days WHERE date BETWEEN ? AND ?
        ''', (start_date, end_date))
        return cursor.fetchone()

    def get_period_time_records(self, start_date, end_date):
        cursor = self.get_cursor()
        cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?', (start_date, end_date))
        return cursor.fetchall()

    def get_raw_day_records(self, date_query_raw):
        cursor = self.get_cursor()
        cursor.execute('SELECT start, end, project_path FROM time_records WHERE date = ? ORDER BY start ASC', (date_query_raw,))
        return cursor.fetchall()

    def get_monthly_aggregated_records(self, date_prefix):
        cursor = self.get_cursor()
        cursor.execute('''
            SELECT project_path, SUM(duration) as monthly_duration
            FROM time_records WHERE date LIKE ? GROUP BY project_path
        ''', (date_prefix,))
        return cursor.fetchall()

    def get_monthly_total_duration(self, date_prefix):
        cursor = self.get_cursor()
        cursor.execute('SELECT SUM(duration) as total_duration FROM time_records WHERE date LIKE ?', (date_prefix,))
        row = cursor.fetchone()
        return row['total_duration'] if row and row['total_duration'] is not None else 0

class LogFileParser:
    """Parses time tracking log files and stores data using TimeTrackerDB."""

    def __init__(self, db_manager: TimeTrackerDB):
        self.db_manager = db_manager

    @staticmethod
    def _time_to_seconds(t_str):
        try:
            if not t_str: return 0
            h, m = map(int, t_str.split(':'))
            return h * 3600 + m * 60
        except ValueError:
            return 0 # Or raise an error

    @staticmethod
    def _reset_day_info():
        return {'status': 'False', 'remark': '', 'getup_time': '00:00'}

    def _parse_time_log_line(self, line_content, filepath, line_num):
        match = re.match(r'^(\d{1,2}:\d{2})~(\d{1,2}:\d{2})\s*([a-zA-Z0-9_-]+)', line_content)
        if not match:
            print(f"格式错误在 {os.path.basename(filepath)} 第{line_num}行 (时间记录格式无效): {line_content}")
            return None
        
        start_str, end_str, project_path = match.groups()
        project_path = project_path.lower().replace('stduy', 'study')

        start_sec = self._time_to_seconds(start_str)
        end_sec = self._time_to_seconds(end_str)

        if end_sec < start_sec:
            end_sec += 86400
        
        duration = end_sec - start_sec
        if duration < 0:
            print(f"警告: 计算得到的时长为负数在 {os.path.basename(filepath)} 第{line_num}行: {line_content}. 时长设为0.")
            duration = 0
        return start_str, end_str, project_path, duration

    def _commit_day_entries_to_db(self, current_date_val, day_info_val, time_records_list):
        if not current_date_val:
            return
        self.db_manager.update_day_details(current_date_val, day_info_val['status'], day_info_val['remark'], day_info_val['getup_time'])
        for start_r, end_r, project_path_r, duration_r in time_records_list:
            self.db_manager.insert_time_record(current_date_val, start_r, end_r, project_path_r, duration_r)
            self.db_manager.update_project_hierarchy(project_path_r) # Uses db_manager's method

    def parse_file(self, filepath):
        current_date = None
        day_info = self._reset_day_info()
        time_records = []

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line_text in enumerate(f, 1):
                    line_text = line_text.strip()
                    if not line_text: continue

                    try:
                        if line_text.startswith('Date:'):
                            if current_date:
                                self._commit_day_entries_to_db(current_date, day_info, time_records)
                            current_date = line_text[5:].strip()
                            day_info = self._reset_day_info()
                            time_records = []
                            self.db_manager.insert_day_record_if_not_exists(current_date)
                        elif line_text.startswith('Status:'):
                            if current_date: day_info['status'] = line_text[7:].strip()
                        elif line_text.startswith('Remark:'):
                            if current_date: day_info['remark'] = line_text[7:].strip()
                        elif line_text.startswith('Getup:'):
                            if current_date: day_info['getup_time'] = line_text[6:].strip()
                        elif '~' in line_text:
                            if current_date:
                                parsed_entry = self._parse_time_log_line(line_text, filepath, line_num)
                                if parsed_entry: time_records.append(parsed_entry)
                    except Exception as e_line:
                        print(f"处理行时发生错误在 {os.path.basename(filepath)} 第{line_num}行: '{line_text}'. 错误: {e_line}")
                        continue
            if current_date:
                self._commit_day_entries_to_db(current_date, day_info, time_records)
            self.db_manager.commit()
        except FileNotFoundError:
            print(f"错误: 文件未找到 '{filepath}'")
            self.db_manager.rollback()
        except Exception as e_file:
            print(f"解析文件 '{filepath}' 时发生严重错误: {e_file}")
            self.db_manager.rollback()


class ReportFormatter:
    """Formats and prints reports based on data from TimeTrackerDB."""

    def __init__(self, db_manager: TimeTrackerDB):
        self.db_manager = db_manager

    @staticmethod
    def _format_duration(seconds, avg_days=1):
        if not isinstance(seconds, (int, float)) or not isinstance(avg_days, (int, float)):
            return "Invalid input"
        if seconds < 0: seconds = 0

        total_hours = int(seconds // 3600)
        total_minutes = int((seconds % 3600) // 60)
        
        time_str = f"{total_hours}h{total_minutes:02d}m"
        if total_hours == 0 and total_minutes == 0:
            time_str = "<1m" if seconds > 0 else "0m"

        if avg_days > 0 and avg_days != 1:
            avg_seconds_per_day = seconds / avg_days
            avg_hours = int(avg_seconds_per_day // 3600)
            avg_minutes = int((avg_seconds_per_day % 3600) // 60)
            avg_str = f"{avg_hours}h{avg_minutes:02d}m/day"
            return f"{time_str} ({avg_str})"
        return time_str

    def _generate_sorted_output_lines(self, node, avg_days=1, indent=0):
        lines = []
        children_items = node.get('children', {})
        if not isinstance(children_items, dict): children_items = {}
        
        children = sorted(children_items.items(), key=lambda x: x[1].get('duration', 0), reverse=True)

        for key, value in children:
            duration = value.get('duration', 0)
            has_children = isinstance(value, dict) and value.get('children')
            if duration > 0 or has_children:
                lines.append('  ' * indent + f"{key}: {self._format_duration(duration, avg_days)}")
                if has_children:
                    lines.extend(self._generate_sorted_output_lines(value, avg_days, indent + 1))
        return lines

    def _build_project_tree(self, records):
        tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
        for record in records:
            project_path, duration_val = record['project_path'], record['duration']
            parts = project_path.split('_')
            if not parts: continue

            top_level_key = self.db_manager.get_top_level_parent_for_project(parts[0])
            current_level_node = tree[top_level_key]
            current_level_node['duration'] += duration_val

            for part in parts[1:]:
                if not isinstance(current_level_node.get('children'), dict):
                    current_level_node['children'] = defaultdict(dict)
                if part not in current_level_node['children']:
                    current_level_node['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
                current_level_node['children'][part]['duration'] += duration_val
                current_level_node = current_level_node['children'][part]
        return tree

    def print_day_report(self, date_query):
        day_data = self.db_manager.get_day_info(date_query)
        if not day_data:
            print(f"\n[{date_query}]\n无相关记录!")
            return

        output = [f"\nDate:{date_query}", f"Status:{day_data['status']}", f"Getup:{day_data['getup_time']}"]
        if day_data['remark'] and day_data['remark'].strip():
            output.append(f"Remark:{day_data['remark']}")

        total_duration_day = self.db_manager.get_day_total_duration(date_query)
        output.append(f"Total: {self._format_duration(total_duration_day, avg_days=1)}")

        records = self.db_manager.get_day_time_records(date_query)
        if records:
            tree = self._build_project_tree(records)
            sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
            for top_level, subtree in sorted_top_level:
                percentage = (subtree['duration'] / total_duration_day * 100) if total_duration_day else 0
                output.append(f"\n{top_level}: {self._format_duration(subtree['duration'])} ({percentage:.2f}%)")
                output.extend(self._generate_sorted_output_lines(subtree, avg_days=1, indent=1))
        print('\n'.join(output))

    def print_period_report(self, days_to_query):
        end_date_dt = datetime.now()
        start_date_dt = end_date_dt - timedelta(days=days_to_query - 1)
        end_date_str_q = end_date_dt.strftime("%Y%m%d")
        start_date_str_q = start_date_dt.strftime("%Y%m%d")

        output_lines = [f"\n[最近{days_to_query}天统计] {start_date_str_q} - {end_date_str_q}"]
        status_data = self.db_manager.get_period_status_summary(start_date_str_q, end_date_str_q)
        
        true_count = status_data['true_count'] if status_data else 0
        false_count = status_data['false_count'] if status_data else 0
        total_recorded_days = status_data['total_recorded_days'] if status_data else 0

        output_lines.append(f"有状态记录天数: {total_recorded_days}天 / {days_to_query}天")
        output_lines.append("状态分布 (基于有记录的天数):")
        if total_recorded_days > 0:
            output_lines.append(f" True: {true_count}天 ({(true_count / total_recorded_days * 100):.1f}%)")
            output_lines.append(f" False: {false_count}天 ({(false_count / total_recorded_days * 100):.1f}%)")
        else:
            output_lines.extend([" True: 0天 (0.0%)", " False: 0天 (0.0%)"])

        records = self.db_manager.get_period_time_records(start_date_str_q, end_date_str_q)
        if not records:
            output_lines.append("\n期间无有效时间记录")
            print('\n'.join(output_lines))
            return

        grand_total_duration = sum(rec['duration'] for rec in records if rec['duration'] is not None)
        output_lines.append(f"\n期间总时间: {self._format_duration(grand_total_duration, days_to_query)}")

        tree = self._build_project_tree(records)
        sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
        for top_level, subtree in sorted_top_level:
            cat_total = subtree['duration']
            percentage = (cat_total / grand_total_duration * 100) if grand_total_duration else 0
            output_lines.append(f"\n{top_level}: {self._format_duration(cat_total, days_to_query)} ({percentage:.2f}%)")
            output_lines.extend(self._generate_sorted_output_lines(subtree, avg_days=days_to_query, indent=1))
        print('\n'.join(output_lines))

    def print_raw_day_report(self, date_query_raw):
        day_data = self.db_manager.get_day_info(date_query_raw)
        if not day_data:
            print(f"日期 {date_query_raw} 无记录")
            return

        output = [f"Date:{date_query_raw}", f"Status:{day_data['status']}", f"Getup:{day_data['getup_time']}"]
        output.append(f"Remark:{day_data['remark'] if day_data['remark'] and day_data['remark'].strip() else ''}")
        
        records = self.db_manager.get_raw_day_records(date_query_raw)
        for rec in records:
            output.append(f"{rec['start']}~{rec['end']} {rec['project_path']}")
        print('\n'.join(output))

    def print_month_report(self, year_month_str_q):
        if not re.match(r'^\d{6}$', year_month_str_q):
            print("月份格式错误,应为YYYYMM")
            return

        year_val, month_val = int(year_month_str_q[:4]), int(year_month_str_q[4:6])
        try:
            _, last_day = calendar.monthrange(year_val, month_val)
        except calendar.IllegalMonthError:
            print(f"无效的月份: {month_val}"); return
        
        actual_days = last_day
        date_prefix = f"{year_val}{month_val:02d}%"
        
        grand_total_duration = self.db_manager.get_monthly_total_duration(date_prefix)
        records = self.db_manager.get_monthly_aggregated_records(date_prefix) # These are already sum(duration) by project_path

        output = [f"\n[{year_val}年{month_val}月 统计 ({actual_days}天)]"]
        output.append(f"总时间: {self._format_duration(grand_total_duration, actual_days)}")

        if not records and grand_total_duration == 0:
            output.append("本月无有效时间记录")
            print('\n'.join(output))
            return
        
        # Build tree from aggregated records (project_path, monthly_duration)
        tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
        for record in records: # record is like {'project_path': 'study_math', 'monthly_duration': 3600}
            project_path, duration_sum = record['project_path'], record['monthly_duration']
            parts = project_path.split('_')
            if not parts: continue

            top_level_key = self.db_manager.get_top_level_parent_for_project(parts[0])
            current_node = tree[top_level_key]
            current_node['duration'] += duration_sum 

            temp_node_for_subparts = current_node
            for part in parts[1:]:
                if not isinstance(temp_node_for_subparts.get('children'), dict):
                    temp_node_for_subparts['children'] = defaultdict(dict)
                if part not in temp_node_for_subparts['children']:
                    temp_node_for_subparts['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
                temp_node_for_subparts['children'][part]['duration'] += duration_sum
                temp_node_for_subparts = temp_node_for_subparts['children'][part]
        
        sorted_top_level = sorted(tree.items(), key=lambda x: x[1].get('duration', 0), reverse=True)
        for top_level, subtree in sorted_top_level:
            cat_total = subtree['duration']
            percentage = (cat_total / grand_total_duration * 100) if grand_total_duration else 0
            output.append(f"\n{top_level}: {self._format_duration(cat_total, actual_days)} ({percentage:.2f}%)")
            output.extend(self._generate_sorted_output_lines(subtree, avg_days=actual_days, indent=1))
        print('\n'.join(output))


class HeatmapVisualizer:
    """Generates HTML heatmaps for study times."""

    def __init__(self, db_manager: TimeTrackerDB):
        self.db_manager = db_manager

    @staticmethod
    def _return_color(study_time_seconds):
        hours = study_time_seconds / 3600
        if hours == 0: return DEFAULT_COLOR_PALETTE[0]
        if hours < 4: return DEFAULT_COLOR_PALETTE[1]
        if hours < 8: return DEFAULT_COLOR_PALETTE[2]
        if hours < 10: return DEFAULT_COLOR_PALETTE[3]
        if hours < 12: return DEFAULT_COLOR_PALETTE[4]
        return YELLOW

    def generate_yearly_heatmap(self, year, output_file):
        study_times = self.db_manager.get_study_times_for_year(year) # Fetches {date_str: duration}

        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
        first_weekday = start_date.weekday() # Monday is 0 and Sunday is 6
        # GitHub starts week on Sunday. If Monday=0, Sunday=6. (6 - first_weekday_mon_0) % 7 if not Sun.
        # If Sunday is 0 (Python default for strftime %w), then (0 - first_weekday_sun_0) % 7 doesn't make sense for front_empty
        # Let's use Python's weekday() where Mon=0..Sun=6. GitHub display starts Sunday.
        # So, number of empty days at start of first week = first_weekday if Sunday is 0, or (first_weekday + 1) % 7 if Sunday is considered 0.
        # If the year starts on Monday (0), we need 1 empty day (Sunday).
        # If year starts on Sunday (6), we need 0 empty days.
        # So, (first_weekday_python + 1) % 7 gives num empty days before the first day if week starts Sunday.
        # Or, simpler, if Sunday is cell 0: empty_days = (start_date.isoweekday() % 7)
        # ISO weekday: Mon=1..Sun=7. So, start_date.isoweekday() % 7 gives 0 for Sun, 1 for Mon, etc.
        # This is the number of cells to skip to get to the first day of the month on a Sunday-start week.

        front_empty_days = (start_date.isoweekday()) % 7 # 0 for Sunday, 1 for Monday, ..., 6 for Saturday
                                                        # This means if year starts on Mon, 1 empty cell (Sun)

        heatmap_data = []
        for _ in range(front_empty_days):
            heatmap_data.append((None, 'empty', 0))

        current_date_iter = start_date
        while current_date_iter <= end_date:
            date_str = current_date_iter.strftime("%Y%m%d")
            study_duration = study_times.get(date_str, 0)
            color = self._return_color(study_duration)
            heatmap_data.append((current_date_iter, color, study_duration))
            current_date_iter += timedelta(days=1)

        total_cells_filled = front_empty_days + (end_date - start_date).days + 1
        back_empty_days = (7 - (total_cells_filled % 7)) % 7
        for _ in range(back_empty_days):
            heatmap_data.append((None, 'empty', 0))

        cell_size, spacing, weeks, rows = 12, 3, (len(heatmap_data) // 7) , 7
        margin_top, margin_left = 20, 35 # Increased left margin for day names
        width = margin_left + weeks * (cell_size + spacing) - spacing # No trailing space
        height = margin_top + rows * (cell_size + spacing) - spacing

        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
        days_of_week_labels = ["", "Mon", "", "Wed", "", "Fri", ""] # GitHub style: M, W, F
        
        for i, day_label in enumerate(days_of_week_labels):
            if day_label: # Only print M, W, F
                 y_pos = margin_top + i * (cell_size + spacing) + cell_size * 0.7 # Adjusted for baseline
                 svg.append(f'<text x="{margin_left-10}" y="{y_pos}" font-size="9" text-anchor="end" alignment-baseline="middle">{day_label}</text>')
        
        month_markers = {}
        for i, (date_obj, _, _) in enumerate(heatmap_data):
            if date_obj:
                week_idx = i // 7
                month_num = date_obj.month
                if date_obj.day == 1 and month_num not in month_markers : # Simplified: mark first day of month's column
                     # check if this column already has a marker or if previous column was different month
                    if not any(m_col == week_idx for m_col in month_markers.values()):
                        month_markers[month_num] = week_idx
        
        for month_num, week_idx in month_markers.items():
            x_pos = margin_left + week_idx * (cell_size + spacing)
            svg.append(f'<text x="{x_pos}" y="{margin_top - 8}" font-size="10" text-anchor="start">{calendar.month_abbr[month_num]}</text>')

        for i, (date_val, color_val, study_duration_val) in enumerate(heatmap_data):
            if date_val is not None: # Skip 'empty' placeholders for drawing rects
                week_index = i // 7
                day_index = i % 7 # 0=Sunday, 1=Monday.. for the grid
                x_pos = margin_left + week_index * (cell_size + spacing)
                y_pos = margin_top + day_index * (cell_size + spacing)
                duration_str = ReportFormatter._format_duration(study_duration_val) # Use static method
                title_text = f"{date_val.strftime('%Y-%m-%d')}: {duration_str}"
                svg.append(f'<rect width="{cell_size}" height="{cell_size}" x="{x_pos}" y="{y_pos}" fill="{color_val}" rx="2" ry="2">')
                svg.append(f'    <title>{title_text}</title>')
                svg.append(f'</rect>')
        svg.append('</svg>')

        html = f"""<!DOCTYPE html><html><head><title>Study Heatmap {year}</title></head>
                 <body><div style="padding:20px;"><h2>Study Heatmap for {year}</h2>{''.join(svg)}</div></body></html>"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)


class TimeTrackingApp:
    """Main application class to orchestrate operations."""

    def __init__(self):
        self.db_manager = TimeTrackerDB()
        self.parser = LogFileParser(self.db_manager)
        self.reporter = ReportFormatter(self.db_manager)
        self.visualizer = HeatmapVisualizer(self.db_manager)

    def run(self):
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
                    self.parser.parse_file(input_path)
                    print("文件处理完成。")
                elif os.path.isdir(input_path):
                    print(f"\n扫描目录: {input_path}")
                    file_count = 0
                    for root, _, files in os.walk(input_path):
                        for filename in files:
                            if filename.lower().endswith('.txt'):
                                filepath = os.path.join(root, filename)
                                print(f"  处理文件: {filepath}")
                                self.parser.parse_file(filepath)
                                file_count += 1
                    print(f"目录扫描完成，共处理 {file_count} 个数据文件。")
                else:
                    print(f"错误：路径 '{input_path}' 不是有效的 .txt 文件或目录。")
            elif choice == '1':
                date_str = input("请输入日期 (格式 YYYYMMDD): ")
                if re.match(r'^\d{8}$', date_str): self.reporter.print_day_report(date_str)
                else: print("日期格式错误。")
            elif choice in ('2', '3', '4'):
                days_map = {'2': 7, '3': 14, '4': 30}
                self.reporter.print_period_report(days_map[choice])
            elif choice == '5':
                date_str = input("请输入日期 (格式 YYYYMMDD): ")
                if re.match(r'^\d{8}$', date_str): self.reporter.print_raw_day_report(date_str)
                else: print("日期格式错误。")
            elif choice == '6':
                year_str = input("请输入年份 (格式 YYYY): ")
                if re.match(r'^\d{4}$', year_str):
                    output_filename = f"heatmap_study_{year_str}.html"
                    try:
                        self.visualizer.generate_yearly_heatmap(int(year_str), output_filename)
                        print(f"学习热力图已生成：{os.path.abspath(output_filename)}")
                    except Exception as e: print(f"生成热力图失败: {e}")
                else: print("年份格式错误。")
            elif choice == '7':
                year_month_str = input("请输入年月 (格式 YYYYMM): ")
                if re.match(r'^\d{6}$', year_month_str): self.reporter.print_month_report(year_month_str)
                else: print("年月格式错误。")
            elif choice == '8':
                print("正在退出程序...")
                break
            else:
                print("无效选项。")
        self.db_manager.close()

if __name__ == '__main__':
    app = TimeTrackingApp()
    app.run()
