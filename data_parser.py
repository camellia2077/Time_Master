import sqlite3
import re
import os

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

    # Standardized top-level categories and their canonical parent names
    top_level_map = {
        'study': 'STUDY', 'code': 'CODE', 'routine': 'ROUTINE', 'break': 'BREAK',
        'rest': 'REST', 'exercise': 'EXERCISE', 'sleep': 'SLEEP',
        'recreation': 'RECREATION', 'other': 'OTHER', 'meal': 'MEAL',
        'program': 'PROGRAM', 'arrange': 'ARRANGE', # Ensured uppercase for canonical parents
    }

    for child, parent_val in top_level_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent_val))

    conn.commit()
    return conn

class FileDataParser:
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.current_date = None
        self.day_info = {}
        self.time_records = []
        # This map defines canonical parent names for top-level activities.
        # It's used by _update_parent_child_hierarchy to determine the parent
        # for top-level items or new categories.
        self.top_level_map = {
            'study': 'STUDY', 'code': 'CODE', 'routine': 'ROUTINE', 'break': 'BREAK',
            'rest': 'REST', 'exercise': 'EXERCISE', 'sleep': 'SLEEP',
            'recreation': 'RECREATION', 'other': 'OTHER', 'meal': 'MEAL',
            'program': 'PROGRAM', 'arrange': 'ARRANGE',
        }

    def _reset_daily_data(self):
        """Resets data structures for a new date."""
        self.day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
        self.time_records = []

    def _store_previous_date_data(self):
        """Stores collected data for self.current_date into the database."""
        if not self.current_date:
            return

        self.cursor.execute('''
            UPDATE days SET status=?, remark=?, getup_time=?
            WHERE date=?
        ''', (self.day_info['status'], self.day_info['remark'], self.day_info['getup_time'], self.current_date))

        for start, end, project_path, duration in self.time_records:
            self.cursor.execute('''
                INSERT OR REPLACE INTO time_records
                VALUES (?, ?, ?, ?, ?)
            ''', (self.current_date, start, end, project_path, duration))
            self._update_parent_child_hierarchy(project_path)

    def _update_parent_child_hierarchy(self, project_path):
        """Updates the parent_child table based on the project_path.
           Ensures direct parent-child relationships are stored.
           Example: 'study_topic_sub' -> parent 'study_topic'
                    'study_topic' -> parent 'study'
                    'study' -> parent 'STUDY' (from top_level_map or default uppercase)
        """
        parts = project_path.split('_')
        for i in range(len(parts)):
            child_name = '_'.join(parts[:i+1]) # Current full path of the child

            if i == 0: # This is a top-level component (e.g., "study", "new_project")
                # Determine its parent: use top_level_map or default to its uppercase form.
                parent_name = self.top_level_map.get(child_name, child_name.upper())
            else: # This is a sub-component (e.g., "study_topic1")
                # Its parent is the path one level up (e.g., "study").
                parent_name = '_'.join(parts[:i])

            self.cursor.execute('''
                INSERT OR IGNORE INTO parent_child (child, parent)
                VALUES (?, ?)
            ''', (child_name, parent_name))

    def _handle_date_line(self, line_content):
        """Handles a 'Date:' line."""
        if self.current_date: # If there's data from a previous date block
            self._store_previous_date_data()

        self.current_date = line_content
        self._reset_daily_data()
        # Ensure the date exists in the 'days' table.
        # Initial values are set here; they'll be updated by _store_previous_date_data
        # if Status, Remark, or Getup lines provide different values.
        self.cursor.execute('INSERT OR IGNORE INTO days (date, status, remark, getup_time) VALUES (?, ?, ?, ?)',
                           (self.current_date, 'False', '', '00:00'))

    def _handle_status_line(self, line_content):
        """Handles a 'Status:' line."""
        if self.current_date:
            self.day_info['status'] = line_content

    def _handle_remark_line(self, line_content):
        """Handles a 'Remark:' line."""
        if self.current_date:
            self.day_info['remark'] = line_content

    def _handle_getup_line(self, line_content):
        """Handles a 'Getup:' line."""
        if self.current_date:
            self.day_info['getup_time'] = line_content

    def _handle_time_record_line(self, line_content, filepath, line_num):
        """Handles a time record line (e.g., 'HH:MM~HH:MM project')."""
        if not self.current_date:
            print(f"Warning: Time record found without a preceding Date: in {os.path.basename(filepath)} line {line_num}: {line_content}")
            return

        match = re.match(r'^(\d{1,2}:\d{2})~(\d{1,2}:\d{2})\s*([a-zA-Z0-9_-]+)', line_content)
        if not match:
            print(f"Format error in {os.path.basename(filepath)} line {line_num}: {line_content}")
            return

        start, end, project_path = match.groups()
        project_path = project_path.lower().replace('stduy', 'study') # Typo correction

        start_sec = time_to_seconds(start)
        end_sec = time_to_seconds(end)
        if end_sec < start_sec: # Handles overnight records
            end_sec += 86400 # 24 * 3600
        duration = end_sec - start_sec

        self.time_records.append((start, end, project_path, duration))

    def process_file_contents(self, filepath):
        """Parses a single input text file and stores data in the database."""
        # Reset instance variables for a new file, ensuring parser is clean if reused.
        self.current_date = None
        self._reset_daily_data() # Initialize day_info and time_records

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line_text in enumerate(f, 1):
                    try:
                        stripped_line = line_text.strip()
                        if not stripped_line:
                            continue

                        if stripped_line.startswith('Date:'):
                            self._handle_date_line(stripped_line[5:].strip())
                        elif stripped_line.startswith('Status:'):
                            self._handle_status_line(stripped_line[7:].strip())
                        elif stripped_line.startswith('Remark:'):
                            self._handle_remark_line(stripped_line[7:].strip())
                        elif stripped_line.startswith('Getup:'):
                            self._handle_getup_line(stripped_line[6:].strip())
                        elif '~' in stripped_line:
                            self._handle_time_record_line(stripped_line, filepath, line_num)
                        # else: unknown line format, could be logged or ignored
                    except Exception as e:
                        print(f"Error parsing line {line_num} in {os.path.basename(filepath)}: '{stripped_line}'")
                        print(f"Specific error: {str(e)}")
                        continue # Skip to next line

            # After processing all lines, store data for the last date encountered in the file.
            if self.current_date:
                self._store_previous_date_data()

            self.conn.commit() # Commit changes after successful processing of the entire file.

        except FileNotFoundError:
            print(f"Error: File not found at {filepath}")
        except Exception as e:
            print(f"An unexpected error occurred while processing {filepath}: {str(e)}")
            # Depending on transaction strategy, a rollback might be considered here for database consistency.
            # However, commits are generally happening after logical blocks (date data or full file).

# The parse_file function now uses the FileDataParser class.
# Its public interface remains the same, so main_app.py does not need to change its call.
def parse_file(conn, filepath):
    """
    Parses a single input text file and stores data in the database
    by instantiating and using the FileDataParser class.
    """
    parser = FileDataParser(conn)
    parser.process_file_contents(filepath)
