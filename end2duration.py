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

    # 移除了硬编码的 TEXT_REPLACEMENT_MAP
    # 它将在 __init__ 中作为实例变量加载

    def __init__(self, year: int = 2025, replacement_map_file: str = "end2duration.json"):
        self.year_to_use = year
        # 用于处理单个日期块内事件的状态变量
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False
        # 用于管理 process_log_data 中日期块之间换行的状态变量
        self._printed_at_least_one_block = False
        # 加载文本替换映射
        self.TEXT_REPLACEMENT_MAP = self._load_replacement_map(replacement_map_file)

    def _load_replacement_map(self, file_path: str) -> dict:
        """从指定的JSON文件加载文本替换映射。"""
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
        """重置处理单个日期块内事件的特定状态变量。"""
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False

    def _process_and_print_date_block(self, date_line_content: str, event_lines_content: list):
        # 1. 格式化日期字符串
        month_char = date_line_content[0]
        day_chars = date_line_content[1:]
        formatted_month_str = f"{int(month_char):02d}"
        formatted_day_str = f"{int(day_chars):02d}"
        formatted_date_output_str = f"Date:{self.year_to_use}{formatted_month_str}{formatted_day_str}"
        
        # 2. 初始化事件处理所需变量
        day_has_study_event = False
        event_related_output_lines = [] 
        
        self._reset_date_block_processing_state()

        # 3. 根据实际的第一个事件决定并添加 Getup/Remark 行
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

        # 4. 处理所有事件行以记录活动并检查 "study"
        start_processing_from_index = 0
        if is_first_event_actual_getup_type:
            consumed_event_raw_time = event_lines_content[0][:4]
            consumed_event_original_text = event_lines_content[0][4:]

            self._last_interval_start_raw_time = consumed_event_raw_time
            if consumed_event_original_text == "醒":
                self._was_previous_event_initial_raw_xing = True
            else:
                self._was_previous_event_initial_raw_xing = False
            
            # 使用 self.TEXT_REPLACEMENT_MAP
            consumed_display_text = self.TEXT_REPLACEMENT_MAP.get(consumed_event_original_text, consumed_event_original_text)
            if "study" in consumed_display_text:
                day_has_study_event = True
            
            start_processing_from_index = 1

        for i in range(start_processing_from_index, len(event_lines_content)):
            event_line_str = event_lines_content[i]
            
            raw_time = event_line_str[:4]
            original_text = event_line_str[4:]
            current_formatted_time = self._format_time(raw_time)
            # 使用 self.TEXT_REPLACEMENT_MAP
            display_text = self.TEXT_REPLACEMENT_MAP.get(original_text, original_text)

            if "study" in display_text:
                day_has_study_event = True
            
            if self._last_interval_start_raw_time is None:
                event_related_output_lines.append(f"{current_formatted_time}{display_text}")
                self._last_interval_start_raw_time = raw_time
                self._was_previous_event_initial_raw_xing = False 
            else: 
                start_formatted_time = self._format_time(self._last_interval_start_raw_time)
                event_related_output_lines.append(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                self._was_previous_event_initial_raw_xing = False 
                self._last_interval_start_raw_time = raw_time
        
        # 5. 打印日期，然后是状态，最后是所有与事件相关的行
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

            if line.isdigit() and (len(line) == 2 or len(line) == 3):
                if current_date_raw_content is not None: 
                    if self._printed_at_least_one_block: 
                        print() 
                    self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)
                    self._printed_at_least_one_block = True
                
                current_date_raw_content = line
                current_event_lines_for_block = []
            else:  
                if len(line) >= 4 and line[:4].isdigit():
                     current_event_lines_for_block.append(line)

        if current_date_raw_content is not None:
            if self._printed_at_least_one_block:
                 print()
            self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)

if __name__ == '__main__':
    file_path = input("请输入txt文件名: ")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            input_data = file.read()
        
        # 您可以在这里传递不同的替换映射文件名，如果需要的话：
        # processor = LogProcessor(replacement_map_file="custom_map.json")
        processor = LogProcessor() # 将使用默认的 "text_replacement_map.json"
        processor.process_log_data(input_data)

    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 未找到。", file=sys.stderr)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
