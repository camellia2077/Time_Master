import sys

class LogProcessor:
    """
    Processes structured log data, formats it, and prints the output.
    Handles text replacement and formatting for time intervals.
    """

    # ANSI escape codes for colors
    GREEN = "\033[92m"
    RESET = "\033[0m"

    # Text replacement map
    TEXT_REPLACEMENT_MAP = {
        "word": "study_english_word",
        "单词": "study_english_word",
        "code": "code_time-master",
        # REST
        "rest0": "rest_short",
        "rest1": "rest_medium",
    }

    def __init__(self):
        """
        Initializes the LogProcessor.
        State variables are managed within the process_log_data method
        as they are specific to each processing run or date block.
        """
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False
        self._is_not_first_date_block = False


    @staticmethod
    def _format_time(time_str: str) -> str:
        """Converts a 'HHMM' time string to 'HH:MM' format."""
        if len(time_str) == 4 and time_str.isdigit():
            return f"{time_str[:2]}:{time_str[2:]}"
        return time_str

    def _reset_date_block_state(self):
        """Resets the state variables for a new date block."""
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False

    def process_log_data(self, log_data_str: str):
        """
        Processes the structured log data string and prints the formatted output,
        including text replacement and blank lines between date blocks.
        """
        lines = log_data_str.strip().split('\n')

        # Reset main state for this processing call
        self._is_not_first_date_block = False
        self._reset_date_block_state() # Initial reset for the first potential block

        for line_content in lines:
            line = line_content.strip()
            if not line:
                continue

            if line.isdigit() and len(line) == 3:  # Date line
                if self._is_not_first_date_block:
                    print()  # Add blank line before new date block (not the first)
                
                print(f"{self.GREEN}{line}{self.RESET}")
                self._is_not_first_date_block = True # Mark that at least one date block header has been processed

                # Reset state for the new date block
                self._reset_date_block_state()
            
            else:  # Event line
                if len(line) < 4 or not line[:4].isdigit():
                    continue

                raw_time = line[:4]
                original_text = line[4:]
                current_formatted_time = self._format_time(raw_time)
                display_text = self.TEXT_REPLACEMENT_MAP.get(original_text, original_text)

                if self._last_interval_start_raw_time is None:  # First event in this date block
                    if original_text == "醒":
                        print(f"{raw_time}{display_text}")
                        self._was_previous_event_initial_raw_xing = True
                        self._last_interval_start_raw_time = raw_time
                    elif original_text == "起床":
                        print(f"{current_formatted_time}{display_text}")
                        self._last_interval_start_raw_time = raw_time
                        self._was_previous_event_initial_raw_xing = False
                    else:  # Other first event
                        print(f"{current_formatted_time}{display_text}")
                        self._last_interval_start_raw_time = raw_time
                        self._was_previous_event_initial_raw_xing = False
                else:  # Not the first event in the block
                    if self._was_previous_event_initial_raw_xing:
                        # If previous was "醒" (raw time), the interval starts with current time formatted
                        print(f"{current_formatted_time}~{current_formatted_time}{display_text}")
                        self._last_interval_start_raw_time = raw_time
                        self._was_previous_event_initial_raw_xing = False
                    else:
                        start_formatted_time = self._format_time(self._last_interval_start_raw_time)
                        print(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                        self._last_interval_start_raw_time = raw_time
        
        # Optional: if a blank line is desired at the very end of all output
        # if self._is_not_first_date_block:
        #     print()

if __name__ == '__main__':
    file_path = input("请输入txt文件名: ")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            input_data = file.read()
        
        # Create an instance of LogProcessor and process the data
        processor = LogProcessor()
        processor.process_log_data(input_data)

    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 未找到。", file=sys.stderr)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
