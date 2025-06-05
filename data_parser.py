# data_parser.py
import re
import os

def time_to_seconds(t):
    """Converts HH:MM time string to seconds."""
    try:
        if not t: return 0
        h, m = map(int, t.split(':'))
        return h * 3600 + m * 60
    except (ValueError, AttributeError):
        return 0

class FileDataParser:
    """
    Parses time-tracking text files into a structured, intermediate
    Python dictionary format, without any database interaction.
    """
    def __init__(self):
        self.current_date = None
        self.day_info = {}
        self.time_records = []
        self.parsed_data = [] # Stores the final list of parsed day objects

    def _reset_daily_data(self):
        """Resets data structures for a new date block."""
        self.day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
        self.time_records = []

    def _package_previous_date_data(self):
        """Packages the collected data for the current date into a dictionary."""
        if not self.current_date:
            return

        day_data = {
            'date': self.current_date,
            'day_info': self.day_info.copy(),
            'time_records': self.time_records.copy()
        }
        self.parsed_data.append(day_data)

    def _handle_date_line(self, line_content):
        """Handles a 'Date:' line."""
        if self.current_date:
            self._package_previous_date_data()

        self.current_date = line_content
        self._reset_daily_data()

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
        project_path = project_path.lower().replace('stduy', 'study')

        start_sec = time_to_seconds(start)
        end_sec = time_to_seconds(end)
        if end_sec < start_sec: # Handles overnight records
            end_sec += 86400
        duration = end_sec - start_sec

        self.time_records.append((start, end, project_path, duration))

    def _process_line(self, line_text, filepath, line_num):
        """Processes a single line by dispatching to the appropriate handler."""
        stripped_line = line_text.strip()
        if not stripped_line:
            return

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

    def process_file_contents(self, filepath):
        """
        Parses a single input text file and returns its data.

        Returns:
            list: A list of dictionaries, where each dictionary represents
                  a day's data from the file.
        """
        self.current_date = None
        self.parsed_data = []
        self._reset_daily_data()

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line_text in enumerate(f, 1):
                    try:
                        self._process_line(line_text, filepath, line_num)
                    except Exception as e:
                        print(f"Error parsing line {line_num} in {os.path.basename(filepath)}: '{line_text.strip()}'")
                        print(f"Specific error: {str(e)}")

            if self.current_date:
                self._package_previous_date_data()

            return self.parsed_data

        except FileNotFoundError:
            print(f"Error: File not found at {filepath}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while processing {filepath}: {str(e)}")
            return []

def parse_file(filepath):
    """
    Public function to parse a file using the FileDataParser class.
    """
    parser = FileDataParser()
    return parser.process_file_contents(filepath)