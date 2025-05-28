import sys
import datetime # Retained as per original
import json
import os
import time
import argparse # Added for command-line argument parsing

class LogProcessor:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

    def __init__(self, year: int = 2025, replacement_map_file: str = "interval_processor.json", output_file_stream=None):
        self.year_to_use = year
        self._last_interval_start_raw_time = None # Internal state for current day block processing
        self._was_previous_event_initial_raw_xing = False # Internal state for current day block processing
        self._printed_at_least_one_block = False # Overall state for process_log_data method
        self.TEXT_REPLACEMENT_MAP = self._load_replacement_map(replacement_map_file)
        self.output_file_stream = output_file_stream

    def _output(self, message: str):
        if self.output_file_stream:
            plain_message = (message.replace(self.GREEN, "")
                                  .replace(self.RED, "")
                                  .replace(self.YELLOW, "")
                                  .replace(self.RESET, ""))
            self.output_file_stream.write(plain_message + "\n")
        else:
            # This path would only be taken if LogProcessor is instantiated elsewhere 
            # without an output_file_stream. In the context of main(), a stream is always provided.
            print(message) 

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
        # Resets state specific to a single date block's internal event processing
        self._last_interval_start_raw_time = None
        self._was_previous_event_initial_raw_xing = False

    # Modified to accept next_day_initial_wakeup_raw_time
    def _process_and_print_date_block(self, date_line_content: str, event_lines_content: list, next_day_initial_wakeup_raw_time: str = None):
        if len(date_line_content) == 4 and date_line_content.isdigit():
            month_chars = date_line_content[0:2]
            day_chars = date_line_content[2:4]
            try:
                month_int = int(month_chars)
                day_int = int(day_chars)
                if not (1 <= month_int <= 12 and 1 <= day_int <= 31):
                    print(f"警告: 无效的日期部分 '{date_line_content}'. 跳过此日期块。", file=sys.stderr)
                    return
                formatted_month_str = f"{month_int:02d}"
                formatted_day_str = f"{day_int:02d}"
            except ValueError:
                print(f"警告: 无法将日期部分 '{date_line_content}' 解析为数字。跳过此日期块。", file=sys.stderr)
                return
        else:
            print(f"警告: 日期行格式无效 '{date_line_content}'. 跳过此日期块。", file=sys.stderr)
            return

        formatted_date_output_str = f"Date:{self.year_to_use}{formatted_month_str}{formatted_day_str}"
        day_has_study_event = False
        event_related_output_lines = []
        
        self._reset_date_block_processing_state() # Resets self._last_interval_start_raw_time for this block

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
            event_related_output_lines.append(f"Getup:null") 
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
            
            if self._last_interval_start_raw_time is None:
                event_related_output_lines.append(f"{current_formatted_time}{display_text}")
                self._last_interval_start_raw_time = raw_time
                self._was_previous_event_initial_raw_xing = False 
            else:
                start_formatted_time = self._format_time(self._last_interval_start_raw_time)
                event_related_output_lines.append(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                self._was_previous_event_initial_raw_xing = False
                self._last_interval_start_raw_time = raw_time

        # Add sleep_night entry if applicable
        if next_day_initial_wakeup_raw_time and self._last_interval_start_raw_time:
            last_event_time_current_day_formatted = self._format_time(self._last_interval_start_raw_time)
            next_day_wakeup_time_formatted = self._format_time(next_day_initial_wakeup_raw_time)
            event_related_output_lines.append(f"{last_event_time_current_day_formatted}~{next_day_wakeup_time_formatted}sleep_night")

        self._output(formatted_date_output_str)
        if day_has_study_event:
            self._output(f"Status:True")
        else:
            self._output(f"Status:False")

        for out_line in event_related_output_lines:
            self._output(out_line)

    def process_log_data(self, log_data_str: str):
        lines = log_data_str.strip().split('\n')
        
        all_blocks = []
        current_date_raw_content_temp = None
        current_event_lines_for_block_temp = []

        for line_content in lines:
            line = line_content.strip()
            if not line:
                continue
            
            # A line is a date if it's exactly 4 digits.
            is_date_line = line.isdigit() and len(line) == 4
            # An event line starts with 4 digits but isn't *just* 4 digits (to distinguish from date lines if context is lost)
            # However, the structure implies date lines are processed first, then subsequent lines are events for that date.
            # The original logic for else branch after date check implies this:
            is_event_line = False
            if not is_date_line and len(line) >= 4 and line[:4].isdigit():
                 is_event_line = True


            if is_date_line:
                if current_date_raw_content_temp is not None: 
                    all_blocks.append({
                        'date': current_date_raw_content_temp,
                        'events': list(current_event_lines_for_block_temp) 
                    })
                current_date_raw_content_temp = line
                current_event_lines_for_block_temp = []
            elif is_event_line:
                if current_date_raw_content_temp is not None:
                    current_event_lines_for_block_temp.append(line)
                else:
                    print(f"警告: 发现事件行 '{line}' 但没有活动的日期块。此行将被忽略。", file=sys.stderr)
            # else:
                # print(f"信息: 忽略格式不符的行: '{line}'", file=sys.stderr)


        # Process the last accumulated block
        if current_date_raw_content_temp is not None:
            all_blocks.append({
                'date': current_date_raw_content_temp,
                'events': list(current_event_lines_for_block_temp)
            })

        self._printed_at_least_one_block = False # Reset for the printing loop below

        num_blocks = len(all_blocks)
        for i, block_data in enumerate(all_blocks):
            current_date_raw_content = block_data['date']
            current_event_lines_for_block = block_data['events']
            next_day_initial_wakeup_raw_time = None

            if i + 1 < num_blocks: # If there is a next day block
                next_day_event_lines = all_blocks[i+1]['events']
                for event_line_str in next_day_event_lines:
                    if len(event_line_str) >= 4 and event_line_str[:4].isdigit():
                        raw_time_next = event_line_str[:4]
                        text_next = event_line_str[4:]
                        if text_next in ["醒", "起床"]:
                            next_day_initial_wakeup_raw_time = raw_time_next
                            break 
            
            if self._printed_at_least_one_block:
                self._output("") 
            
            self._process_and_print_date_block(
                current_date_raw_content,
                current_event_lines_for_block,
                next_day_initial_wakeup_raw_time 
            )
            self._printed_at_least_one_block = True


def main():
    parser = argparse.ArgumentParser(description="Process log files and output formatted duration data.")
    parser.add_argument("filepath", help="Path to the input txt file.")
    parser.add_argument("-o", "--output", help="Path to the output file. If not specified, output is saved to 'Duration_<input_file_stem>.txt'.")
    parser.add_argument("--year", type=int, default=2025, help="Year to use for date formatting (default: 2025).")
    parser.add_argument("--config", default="duration_config.json", help="Path to the text replacement map JSON file (default: duration_config.json).")

    args = parser.parse_args()

    file_path_input = args.filepath
    user_specified_output_file = args.output 
    year_to_use = args.year
    config_file_path = args.config
    
    output_file_stream = None
    actual_output_filename = ""

    try:
        with open(file_path_input, 'r', encoding='utf-8') as file:
            input_data = file.read()
        
        if user_specified_output_file:
            actual_output_filename = user_specified_output_file
            print(f"Output will be saved to user-specified file: {actual_output_filename}")
        else:
            base_input_filename = os.path.basename(file_path_input)
            input_filename_stem, _ = os.path.splitext(base_input_filename)
            actual_output_filename = f"Duration_{input_filename_stem}.txt"
            print(f"Output will be saved to default file: {actual_output_filename}")
        
        output_file_stream = open(actual_output_filename, 'w', encoding='utf-8')
            
        processor = LogProcessor(year=year_to_use, replacement_map_file=config_file_path, output_file_stream=output_file_stream)
        
        start_time = time.perf_counter()
        processor.process_log_data(input_data)
        end_time = time.perf_counter()
        
        processing_duration = end_time - start_time

        print(f"Processing complete. Output has been saved to: {actual_output_filename}")
        print(f"Processing input content took: {processing_duration:.6f} seconds")
            
    except FileNotFoundError:
        print(f"错误: 输入文件 '{file_path_input}' 未找到。", file=sys.stderr)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
    finally:
        if output_file_stream:
            output_file_stream.close()

if __name__ == '__main__':
    main()
