# database_importer.py
import sqlite3

class DatabaseImporter:
    """Handles all database operations: initialization and data import."""
    def __init__(self, conn):
        self.conn = conn
        self.cursor = conn.cursor()
        self.top_level_map = self._get_canonical_parents()

    def _get_canonical_parents(self):
        """Fetches the initial child-to-parent mapping from the database."""
        self.cursor.execute('SELECT child, parent FROM parent_child')
        return {child: parent for child, parent in self.cursor.fetchall()}

    def _update_parent_child_hierarchy(self, project_path):
        """
        Updates the parent_child table based on the project_path.
        Example: 'study_topic_sub' ensures 'study_topic' and 'study' are mapped.
        """
        parts = project_path.split('_')
        for i in range(len(parts)):
            child_name = '_'.join(parts[:i+1])

            if child_name in self.top_level_map: # Already processed
                continue

            if i == 0:
                parent_name = child_name.upper()
            else:
                parent_name = '_'.join(parts[:i])
            
            self.cursor.execute('''
                INSERT OR IGNORE INTO parent_child (child, parent)
                VALUES (?, ?)
            ''', (child_name, parent_name))
            self.top_level_map[child_name] = parent_name # Cache the new entry

    def import_data(self, parsed_data):
        """
        Imports a list of parsed day objects into the database.

        Args:
            parsed_data (list): The intermediate data from FileDataParser.
        """
        for day_data in parsed_data:
            date = day_data['date']
            info = day_data['day_info']
            
            # Insert or ignore the date first to ensure it exists
            self.cursor.execute(
                'INSERT OR IGNORE INTO days (date, status, remark, getup_time) VALUES (?, ?, ?, ?)',
                (date, 'False', '', '00:00')
            )
            # Then update it with the parsed details
            self.cursor.execute(
                'UPDATE days SET status=?, remark=?, getup_time=? WHERE date=?',
                (info['status'], info['remark'], info['getup_time'], date)
            )

            for start, end, project_path, duration in day_data['time_records']:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO time_records
                    VALUES (?, ?, ?, ?, ?)
                ''', (date, start, end, project_path, duration))
                self._update_parent_child_hierarchy(project_path)
        
        self.conn.commit()

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = sqlite3.connect('time_data.db')
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY, status TEXT, remark TEXT, getup_time TEXT
        );
        CREATE TABLE IF NOT EXISTS time_records (
            date TEXT, start TEXT, end TEXT, project_path TEXT, duration INTEGER,
            PRIMARY KEY(date, start)
        );
        CREATE TABLE IF NOT EXISTS parent_child (
            child TEXT PRIMARY KEY, parent TEXT
        );
        CREATE TABLE IF NOT EXISTS parent_time (
            date TEXT, parent TEXT, duration INTEGER, PRIMARY KEY(date, parent)
        );
    ''')

    top_level_map = {
        'study': 'STUDY', 'code': 'CODE', 'routine': 'ROUTINE', 'break': 'BREAK',
        'rest': 'REST', 'exercise': 'EXERCISE', 'sleep': 'SLEEP',
        'recreation': 'RECREATION', 'other': 'OTHER', 'meal': 'MEAL',
        'program': 'PROGRAM', 'arrange': 'ARRANGE', 'insomnia': 'INSOMNIA'
    }
    for child, parent in top_level_map.items():
        cursor.execute(
            'INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)',
            (child, parent)
        )
    conn.commit()
    return conn

def import_to_db(conn, parsed_data):
    """
    Public function to import parsed data using the DatabaseImporter class.
    """
    importer = DatabaseImporter(conn)
    importer.import_data(parsed_data)