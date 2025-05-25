import sys
import datetime # Kept for potential future dynamic year

class LogProcessor:
    """
    Processes structured log data, formats it, and prints the output.
    Handles text replacement, dynamic status, and formatting for time intervals.
    """

    GREEN = "\033[92m"
    RED = "\033[91m"  # Added for Status:False
    RESET = "\033[0m"

    TEXT_REPLACEMENT_MAP = {
        "word":"study_english_word",
        "单词":"study_english_word",
        "code":"code_time-master",
        "rest0":"rest_short",
        "rest1":"rest_medium",
        "rest2":"rest_long",
        "洗澡" : "routine_bath",
        "快递" : "routine_express",
        "洗漱" : "routine_grooming",
        "拉屎" : "routine_toilet",
        "meal0": "meal_short",
        "meal1": "meal_medium",
        "meal2": "meal_long",
        "zh": "recreation_zhihu",
        "知乎": "recreation_zhihu",
        "dy": "recreation_douyin",
        "抖音": "recreation_douyin",
        "守望先锋":"recreation_game_overwatch",
        "bili" : "recreation_bilibili",
        "mix":"recreation_mix",
        "b":"recreation_bilibili",
        "电影" : "recreation_movie",
        "撸" : "rest_masturbation",
        "school" : "other_school",
        "有氧" : "exercise_cardio",
        "无氧" : "exercise_anaerobic",
        "运动" : "exercise_both",
    }

    def __init__(self, year: int = 2025):
        self.year_to_use = year
        # State variables for processing within a single date block, reset by _reset_date_block_state
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False
        # State variable for managing newlines between blocks in process_log_data
        self._printed_at_least_one_block = False


    @staticmethod
    def _format_time(time_str: str) -> str:
        if len(time_str) == 4 and time_str.isdigit():
            return f"{time_str[:2]}:{time_str[2:]}"
        return time_str

    def _reset_date_block_processing_state(self):
        """Resets state variables specific to processing events within one date block."""
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False

    def _process_and_print_date_block(self, date_line_content: str, event_lines_content: list):
        # 1. Format Date string
        month_str = date_line_content[0]
        day_str = date_line_content[1:]
        formatted_date_output_str = f"Date:{self.year_to_use}{int(month_str):02d}{day_str}"
        
        # 2. Process event lines to determine status and collect formatted event strings
        day_has_study_event = False
        formatted_event_output_lines = []
        
        self._reset_date_block_processing_state() # Reset for the events of this specific block

        for event_line_str in event_lines_content:
            # Basic parsing (assuming event_line_str is already pre-validated somewhat)
            raw_time = event_line_str[:4]
            original_text = event_line_str[4:]
            current_formatted_time = self._format_time(raw_time)
            display_text = self.TEXT_REPLACEMENT_MAP.get(original_text, original_text)

            if "study" in display_text:
                day_has_study_event = True

            # Logic for formatting event line based on type and sequence
            if self._last_interval_start_raw_time is None:  # First event in this date block
                if original_text in ["醒", "起床"]:
                    formatted_event_output_lines.append(f"Getup:{current_formatted_time}")
                    formatted_event_output_lines.append("Remark:")
                    if original_text == "醒":
                        self._was_previous_event_initial_raw_xing = True
                    else: # "起床"
                        self._was_previous_event_initial_raw_xing = False
                    self._last_interval_start_raw_time = raw_time
                else:  # Other first event
                    formatted_event_output_lines.append(f"{current_formatted_time}{display_text}")
                    self._last_interval_start_raw_time = raw_time
                    self._was_previous_event_initial_raw_xing = False
            else:  # Not the first event in the block
                if self._was_previous_event_initial_raw_xing:
                    # Event following an initial "醒"
                    formatted_event_output_lines.append(f"{current_formatted_time}{display_text}")
                    self._last_interval_start_raw_time = raw_time
                    self._was_previous_event_initial_raw_xing = False # Reset after handling
                else:
                    start_formatted_time = self._format_time(self._last_interval_start_raw_time)
                    formatted_event_output_lines.append(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                    self._last_interval_start_raw_time = raw_time
        
        # 3. Print the assembled block
        print(formatted_date_output_str)
        if day_has_study_event:
            print(f"{self.GREEN}Status:True{self.RESET}")
        else:
            print(f"{self.RED}Status:False{self.RESET}")
        
        for out_line in formatted_event_output_lines:
            print(out_line)

    def process_log_data(self, log_data_str: str):
        lines = log_data_str.strip().split('\n')
        
        current_date_raw_content = None
        current_event_lines_for_block = []
        self._printed_at_least_one_block = False # Reset for this run

        for line_content in lines:
            line = line_content.strip()
            if not line:
                continue

            if line.isdigit() and len(line) == 3:  # New Date Line
                if current_date_raw_content is not None: # Process the previously collected block
                    if self._printed_at_least_one_block: # Add newline if not the very first block
                        print() 
                    self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)
                    self._printed_at_least_one_block = True
                
                # Start new block
                current_date_raw_content = line
                current_event_lines_for_block = []
            else:  # Event line
                # Basic validation for event line structure
                if len(line) >= 4 and line[:4].isdigit():
                     current_event_lines_for_block.append(line)
                # Malformed event lines or other text will be ignored unless further handling is added

        # Process the last collected block after the loop finishes
        if current_date_raw_content is not None:
            if self._printed_at_least_one_block:
                 print()
            self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)
            # self._printed_at_least_one_block = True # Not strictly needed here

if __name__ == '__main__':
    file_path = input("请输入txt文件名: ")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            input_data = file.read()
        
        processor = LogProcessor() 
        processor.process_log_data(input_data)

    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 未找到。", file=sys.stderr)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
