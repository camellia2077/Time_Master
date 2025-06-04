import sqlite3
import re
import os
# 这个程序用来建立数据库与解析输入文件
# --- Utility Functions ---
def time_to_seconds(t):
    """Converts HH:MM time string to seconds."""
    try:
        if not t: return 0
        h, m = map(int, t.split(':'))
        return h * 3600 + m * 60
    except ValueError: # Handles cases where split doesn't return 2 values or non-integer parts
        return 0
    except AttributeError: # Handles cases where t is not a string (e.g., None)
        return 0


# --- Database Core Functions ---
def init_db():
    """Initializes the database and creates tables if they don't exist."""
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

    for child, parent_val in top_level_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent_val))

    conn.commit()
    return conn

def parse_file(conn, filepath):
    """Parses a single input text file and stores data in the database."""
    cursor = conn.cursor()
    current_date = None
    day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
    time_records = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    line = line.strip()
                    if not line:
                        continue

                    if line.startswith('Date:'):
                        if current_date: # Process previous date's collected data
                            cursor.execute('''
                                UPDATE days SET status=?, remark=?, getup_time=?
                                WHERE date=?
                            ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
                            for start, end, project_path, duration in time_records:
                                cursor.execute('''
                                    INSERT OR REPLACE INTO time_records
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (current_date, start, end, project_path, duration))
                                # Update parent_child hierarchy
                                parts = project_path.split('_')
                                for i in range(len(parts)):
                                    child = '_'.join(parts[:i+1])
                                    parent_val = '_'.join(parts[:i]) if i > 0 else parts[0]
                                    cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent_val,))
                                    parent_result = cursor.fetchone()
                                    if parent_result:
                                        parent_val = parent_result[0]
                                    elif i == 0: # Top-level item
                                        cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                                        if not cursor.fetchone(): # If not in pre-defined map or already inserted
                                            # Default to uppercase or specific 'STUDY' for 'study'
                                            default_parent = 'STUDY' if child == 'study' else child.upper()
                                            cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)',
                                                           (child, default_parent))
                                        # No further parent to insert for the top-level item itself in this loop
                                        continue # Go to next part of the project_path
                                    # For sub-items, insert their relationship if parent_val was determined
                                    cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent_val))

                        # Reset for new date
                        current_date = line[5:].strip()
                        day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
                        time_records = []
                        cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (current_date,))
                    elif line.startswith('Status:'):
                        day_info['status'] = line[7:].strip()
                    elif line.startswith('Remark:'):
                        day_info['remark'] = line[7:].strip()
                    elif line.startswith('Getup:'):
                        day_info['getup_time'] = line[6:].strip()
                    elif '~' in line:
                        match = re.match(r'^(\d{1,2}:\d{2})~(\d{1,2}:\d{2})\s*([a-zA-Z0-9_-]+)', line)
                        if not match:
                            print(f"Format error in {os.path.basename(filepath)} line {line_num}: {line}")
                            continue
                        start, end, project_path = match.groups()
                        project_path = project_path.lower().replace('stduy', 'study') # Typo correction
                        start_sec = time_to_seconds(start)
                        end_sec = time_to_seconds(end)
                        if end_sec < start_sec: # Handles overnight records
                            end_sec += 86400
                        duration = end_sec - start_sec
                        time_records.append((start, end, project_path, duration))
                except Exception as e:
                    print(f"Error parsing line {line_num} in {os.path.basename(filepath)}: {line}")
                    print(f"Specific error: {str(e)}")
                    continue
        
        # Process the last date entry in the file
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
                    parent_val = '_'.join(parts[:i]) if i > 0 else parts[0]
                    cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent_val,))
                    parent_result = cursor.fetchone()
                    if parent_result:
                        parent_val = parent_result[0]
                    elif i == 0:
                        cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                        if not cursor.fetchone():
                            default_parent = 'STUDY' if child == 'study' else child.upper()
                            cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)',
                                           (child, default_parent))
                        continue
                    cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent_val))

    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
    except Exception as e:
        print(f"An unexpected error occurred while processing {filepath}: {str(e)}")
    finally:
        conn.commit()