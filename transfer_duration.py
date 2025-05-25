import sys
import datetime # Kept for potential future dynamic year

class LogProcessor:
    """
    Processes structured log data, formats it, and prints the output.
    Handles text replacement, dynamic status, and formatting for time intervals.
    """

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"  # Added for Getup:null
    RESET = "\033[0m"

    TEXT_REPLACEMENT_MAP = {
        "word":"study_english_word",
        # 您可以在这里扩展替换字典，当前根据您的最新提示，只保留了word的例子
        # 例如：
        # "单词":"study_english_word",
        # "code":"code_time-master",
        # ... 等等
    }

    def __init__(self, year: int = 2025):
        self.year_to_use = year
        # 用于处理单个日期块内事件的状态变量
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False
        # 用于管理 process_log_data 中日期块之间换行的状态变量
        self._printed_at_least_one_block = False


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
        month_str = date_line_content[0]
        day_str = date_line_content[1:]
        formatted_date_output_str = f"Date:{self.year_to_use}{int(month_str):02d}{day_str}"
        
        # 2. 初始化事件处理所需变量
        day_has_study_event = False
        # 此列表将存储 Getup/Remark 以及所有后续格式化的事件行
        event_related_output_lines = [] 
        
        self._reset_date_block_processing_state() # 为此特定块的事件重置状态

        # 3. 根据实际的第一个事件决定并添加 Getup/Remark 行
        is_first_event_actual_getup_type = False
        first_event_true_formatted_time = None

        if event_lines_content:  # 检查当天是否有任何事件
            # 预查看第一个事件以决定 Getup 行的格式
            first_event_line_peek_str = event_lines_content[0]
            # 对预查看的行进行基本验证 (假设格式为 "HHMM文本")
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
            # 第一个事件已被 "Getup:HH:MM" 行“消耗”
            #将其时间设置为下一个区间的开始，并检查其是否包含 "study"
            consumed_event_raw_time = event_lines_content[0][:4]
            consumed_event_original_text = event_lines_content[0][4:]

            self._last_interval_start_raw_time = consumed_event_raw_time
            if consumed_event_original_text == "醒":
                self._was_previous_event_initial_raw_xing = True
            else:  # "起床"
                self._was_previous_event_initial_raw_xing = False
            
            # 检查这个被“消耗”的起床事件的 display_text 是否包含 "study"
            consumed_display_text = self.TEXT_REPLACEMENT_MAP.get(consumed_event_original_text, consumed_event_original_text)
            if "study" in consumed_display_text:
                day_has_study_event = True
            
            start_processing_from_index = 1 # 实际活动从下一个事件开始处理

        # 循环处理代表实际活动的事件行
        for i in range(start_processing_from_index, len(event_lines_content)):
            event_line_str = event_lines_content[i]
            
            raw_time = event_line_str[:4]
            original_text = event_line_str[4:]
            current_formatted_time = self._format_time(raw_time)
            display_text = self.TEXT_REPLACEMENT_MAP.get(original_text, original_text)

            if "study" in display_text:
                day_has_study_event = True
            
            # 格式化事件行本身
            if self._last_interval_start_raw_time is None: # 这是记录的第一个实际活动
                event_related_output_lines.append(f"{current_formatted_time}{display_text}")
                self._last_interval_start_raw_time = raw_time
                # 对于非“醒”的第一个实际活动，默认为 False
                self._was_previous_event_initial_raw_xing = False 
            else: # 这是后续的记录活动
                if self._was_previous_event_initial_raw_xing: # 如果前一个实际活动是 "醒"
                    event_related_output_lines.append(f"{current_formatted_time}{display_text}")
                    self._was_previous_event_initial_raw_xing = False # 使用后重置
                else: # 从前一个实际活动开始的正常区间
                    start_formatted_time = self._format_time(self._last_interval_start_raw_time)
                    event_related_output_lines.append(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                self._last_interval_start_raw_time = raw_time # 更新最后一个活动的原始时间
        
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
        self._printed_at_least_one_block = False # 为此次运行重置

        for line_content in lines:
            line = line_content.strip()
            if not line:
                continue

            if line.isdigit() and len(line) == 3:  # 新的日期行
                if current_date_raw_content is not None: # 处理先前收集的块
                    if self._printed_at_least_one_block: # 如果不是第一个要打印的块，则添加换行符
                        print() 
                    self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)
                    self._printed_at_least_one_block = True
                
                # 开始新块
                current_date_raw_content = line
                current_event_lines_for_block = []
            else:  # 事件行
                # 对事件行结构的基本验证
                if len(line) >= 4 and line[:4].isdigit():
                     current_event_lines_for_block.append(line)
                # 格式错误的事件行或其他文本将被忽略，除非添加进一步处理

        # 循环结束后处理最后一个收集的块
        if current_date_raw_content is not None:
            if self._printed_at_least_one_block:
                 print()
            self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)

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
