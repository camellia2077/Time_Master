import sys
import datetime # Kept for potential future dynamic year
import json     # 新增：导入json模块
import os       # 新增：导入os模块，用于检查文件是否存在

class LogProcessor:
    """
    Processes structured log data, formats it, and prints the output.
    Handles text replacement, dynamic status, and formatting for time intervals.
    """

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"  # Added for Getup:null
    RESET = "\033[0m"

    def __init__(self, year: int = 2025, replacement_map_file: str = "end2duration.json"):
        self.year_to_use = year
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False
        self._printed_at_least_one_block = False
        self.TEXT_REPLACEMENT_MAP = self._load_replacement_map(replacement_map_file)

    def _load_replacement_map(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            print(f"警告: 文本替换映射文件 '{file_path}' 未找到。将使用空的替换映射。", file=sys.stderr)
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    print(f"警告: 文本替换映射文件 '{file_path}' 的内容不是一个有效的JSON对象 (字典)。将使用空的替换映射。", file=sys.stderr)
                    return {}
                return data
        except json.JSONDecodeError:
            print(f"警告: 解析文本替换映射文件 '{file_path}' 失败。请确保它是有效的JSON格式。将使用空的替换映射。", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"读取文本替换映射文件 '{file_path}' 时发生未知错误: {e}。将使用空的替换映射。", file=sys.stderr)
            return {}

    @staticmethod
    def _format_time(time_str: str) -> str:
        if len(time_str) == 4 and time_str.isdigit():
            return f"{time_str[:2]}:{time_str[2:]}"
        return time_str

    def _reset_date_block_processing_state(self):
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False

    def _process_and_print_date_block(self, date_line_content: str, event_lines_content: list):
        # 1. 格式化日期字符串 (MODIFIED for 4-digit date)
        # Assumes date_line_content is MMDD, e.g., "0115" for Jan 15
        if len(date_line_content) == 4 and date_line_content.isdigit():
            month_chars = date_line_content[0:2]
            day_chars = date_line_content[2:4]
            try:
                # Validate month and day (optional but good practice)
                month_int = int(month_chars)
                day_int = int(day_chars)
                # Basic validation, more complex validation (days in month) could be added
                if not (1 <= month_int <= 12 and 1 <= day_int <= 31):
                    print(f"警告: 无效的日期部分 '{date_line_content}'. 跳过此日期块。", file=sys.stderr)
                    return
                formatted_month_str = f"{month_int:02d}"
                formatted_day_str = f"{day_int:02d}"
            except ValueError:
                print(f"警告: 无法将日期部分 '{date_line_content}' 解析为数字。跳过此日期块。", file=sys.stderr)
                return
        else:
            # This case should ideally not be reached if process_log_data filters correctly
            print(f"警告: 日期行格式无效 '{date_line_content}'. 跳过此日期块。", file=sys.stderr)
            return

        formatted_date_output_str = f"Date:{self.year_to_use}{formatted_month_str}{formatted_day_str}"
        
        day_has_study_event = False
        event_related_output_lines = [] 
        
        self._reset_date_block_processing_state()

        is_first_event_actual_getup_type = False
        first_event_true_formatted_time = None

        if event_lines_content:
            first_event_line_peek_str = event_lines_content[0]
            if len(first_event_line_peek_str) >= 4 and first_event_line_peek_str[:4].isdigit():
                first_event_peek_raw_time = first_event_line_peek_str[:4]
                first_event_peek_original_text = first_event_line_peek_str[4:]
                if first_event_peek_original_text in ["醒", "起床"]:
                    is_first_event_actual_getup_type = True
                    first_event_true_formatted_time = self._format_time(first_event_peek_raw_time)
        
        if is_first_event_actual_getup_type:
            event_related_output_lines.append(f"Getup:{first_event_true_formatted_time}")
            event_related_output_lines.append("Remark:")
        else:
            event_related_output_lines.append(f"Getup:{self.YELLOW}null{self.RESET}")
            event_related_output_lines.append("Remark:")

        start_processing_from_index = 0
        if is_first_event_actual_getup_type:
            consumed_event_raw_time = event_lines_content[0][:4]
            consumed_event_original_text = event_lines_content[0][4:]
            self._last_interval_start_raw_time = consumed_event_raw_time
            self._was_previous_event_initial_raw_xing = (consumed_event_original_text == "醒")
            
            consumed_display_text = self.TEXT_REPLACEMENT_MAP.get(consumed_event_original_text, consumed_event_original_text)
            if "study" in consumed_display_text:
                day_has_study_event = True
            start_processing_from_index = 1

        for i in range(start_processing_from_index, len(event_lines_content)):
            event_line_str = event_lines_content[i]
            raw_time = event_line_str[:4]
            original_text = event_line_str[4:]
            current_formatted_time = self._format_time(raw_time)
            display_text = self.TEXT_REPLACEMENT_MAP.get(original_text, original_text)

            if "study" in display_text:
                day_has_study_event = True
            
            if self._last_interval_start_raw_time is None: # Should only happen if the first event wasn't a "getup" type
                event_related_output_lines.append(f"{current_formatted_time}{display_text}") # This assumes first non-getup event is a start point
                self._last_interval_start_raw_time = raw_time
                self._was_previous_event_initial_raw_xing = False 
            else: 
                start_formatted_time = self._format_time(self._last_interval_start_raw_time)
                event_related_output_lines.append(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                self._was_previous_event_initial_raw_xing = False 
                self._last_interval_start_raw_time = raw_time
        
        print(formatted_date_output_str)
        if day_has_study_event:
            print(f"{self.GREEN}Status:True{self.RESET}")
        else:
            print(f"{self.RED}Status:False{self.RESET}")
        
        for out_line in event_related_output_lines:
            print(out_line)

    def process_log_data(self, log_data_str: str):
        lines = log_data_str.strip().split('\n')
        
        current_date_raw_content = None
        current_event_lines_for_block = []
        self._printed_at_least_one_block = False 

        for line_content in lines:
            line = line_content.strip()
            if not line:
                continue

            # MODIFIED: Check for 4-digit date lines
            if line.isdigit() and len(line) == 4: # e.g., "0115" for Jan 15
                if current_date_raw_content is not None: 
                    if self._printed_at_least_one_block: 
                        print() 
                    self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)
                    self._printed_at_least_one_block = True
                
                current_date_raw_content = line
                current_event_lines_for_block = []
            else:  
                # This assumes event lines start with 4 digits for time
                if len(line) >= 4 and line[:4].isdigit():
                    current_event_lines_for_block.append(line)
                # Optional: else: print(f"Skipping unrecognized line format: {line}", file=sys.stderr)


        if current_date_raw_content is not None:
            if self._printed_at_least_one_block:
                print()
            self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)

if __name__ == '__main__':
    file_path = input("请输入txt文件名: ")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            input_data = file.read()
        
        # Example of using a specific year and replacement map
        # processor = LogProcessor(year=2024, replacement_map_file="custom_map.json")
        processor = LogProcessor() # Uses default year 2025 and "end2duration.json"
        processor.process_log_data(input_data)

    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 未找到。", file=sys.stderr)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
