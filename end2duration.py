import sys # 导入sys模块，用于访问与Python解释器紧密相关的变量和函数，例如标准输入输出流。
import datetime # 导入datetime模块，用于处理日期和时间。虽然在此版本中可能仅用于潜在的未来动态年份，但保留它。
import json      # 新增：导入json模块，用于处理JSON数据（例如，读取配置文件）。
import os        # 新增：导入os模块，用于与操作系统交互，如此处用于检查文件是否存在。

class LogProcessor: # 定义一个名为 LogProcessor 的类。
    """
    处理结构化的日志数据，对其进行格式化，并打印输出。
    处理文本替换、动态状态（基于是否包含"study"事件）以及时间间隔的格式化。
    """
    # 定义用于在终端输出中添加颜色的ANSI转义码常量。
    GREEN = "\033[92m"  # 绿色，通常用于表示成功或"True"状态。
    RED = "\033[91m"    # 红色，通常用于表示失败或"False"状态。
    YELLOW = "\033[93m" # 黄色，新增用于"Getup:null"的情况。
    RESET = "\033[0m"   # 重置颜色，恢复到终端的默认文本颜色。
    def __init__(self, year: int = 2025, replacement_map_file: str = "end2duration.json"):
        """
        LogProcessor的构造函数。
        :param year: 要用于日期格式化的年份，默认为2025。
        :param replacement_map_file: 文本替换映射JSON文件的路径，默认为"end2duration.json"。
        """
        self.year_to_use = year  # 存储要用于日期处理的年份。
        self._last_interval_start_raw_time = None # 存储上一个时间间隔的原始开始时间（例如，"0800"）。用于计算时间段。
        self._was_previous_event_initial_raw_xing = False # 标记上一个事件是否为原始文本"醒"。 （此变量在当前代码逻辑中似乎未被充分使用或其用途不明确）
        self._printed_at_least_one_block = False # 标记是否至少已打印过一个日期块，用于在多个日期块之间添加空行。
        self.TEXT_REPLACEMENT_MAP = self._load_replacement_map(replacement_map_file) # 加载文本替换映射。

    def _load_replacement_map(self, file_path: str) -> dict:
        """
        从指定的JSON文件加载文本替换映射。
        :param file_path: 文本替换映射JSON文件的路径。
        :return: 一个字典，其中键是原始文本，值是替换后的文本。如果文件未找到或无效，则返回空字典。
        """
        if not os.path.exists(file_path): # 检查替换映射文件是否存在。
            # 如果文件不存在，打印警告信息到标准错误流，并返回一个空字典。
            print(f"警告: 文本替换映射文件 '{file_path}' 未找到。将使用空的替换映射。", file=sys.stderr)
            return {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f: #尝试以只读模式打开文件，使用UTF-8编码。
                data = json.load(f) # 解析JSON文件内容。
                if not isinstance(data, dict): # 检查解析后的数据是否为字典类型。
                    # 如果不是字典，打印警告并返回空字典。
                    print(f"警告: 文本替换映射文件 '{file_path}' 的内容不是一个有效的JSON对象 (字典)。将使用空的替换映射。", file=sys.stderr)
                    return {}
                return data # 返回加载的替换映射字典。
        except json.JSONDecodeError: # 捕获JSON解析错误。
            # 如果JSON格式无效，打印警告并返回空字典。
            print(f"警告: 解析文本替换映射文件 '{file_path}' 失败。请确保它是有效的JSON格式。将使用空的替换映射。", file=sys.stderr)
            return {}
        except Exception as e: # 捕获其他可能的读取文件或处理过程中的异常。
            # 发生其他错误时，打印错误信息和警告，并返回空字典。
            print(f"读取文本替换映射文件 '{file_path}' 时发生未知错误: {e}。将使用空的替换映射。", file=sys.stderr)
            return {}

    @staticmethod # 将此方法声明为静态方法，因为它不依赖于类的实例状态。
    def _format_time(time_str: str) -> str:
        """
        将4位数字的时间字符串（例如 "0800"）格式化为 "HH:MM"（例如 "08:00"）。
        :param time_str: 原始的4位时间字符串。
        :return: 格式化后的时间字符串，或在格式不匹配时返回原始字符串。
        """
        if len(time_str) == 4 and time_str.isdigit(): # 检查字符串是否为4位数字。
            return f"{time_str[:2]}:{time_str[2:]}" # 将其格式化为 HH:MM。
        return time_str # 如果不符合条件，返回原字符串。

    def _reset_date_block_processing_state(self):
        """
        重置处理单个日期块时使用的内部状态变量。
        这确保了每个日期块的处理都是从干净的状态开始的。
        """
        self._last_interval_start_raw_time = None # 重置上一个时间间隔的开始时间。
        self._was_previous_event_initial_raw_xing = False # 重置关于前一个事件是否为"醒"的标志。

    def _process_and_print_date_block(self, date_line_content: str, event_lines_content: list):
        """
        处理并打印单个日期块的数据。
        一个日期块包括日期本身以及该日期下的所有事件行。
        :param date_line_content: 代表日期的原始字符串内容 (例如, "0115" 代表1月15日)。
        :param event_lines_content: 一个包含该日期所有事件行字符串的列表。
        """
        # 1. 格式化日期字符串 (针对4位日期进行了修改)
        # 假设 date_line_content 是 MMDD 格式, 例如, "0115" 代表 1月15日。
        if len(date_line_content) == 4 and date_line_content.isdigit(): # 检查日期内容是否为4位数字。
            month_chars = date_line_content[0:2] # 提取月份部分。
            day_chars = date_line_content[2:4]   # 提取日期部分。
            try:
                # 验证月份和日期 (可选，但是良好的实践)
                month_int = int(month_chars) # 将月份字符串转换为整数。
                day_int = int(day_chars)     # 将日期字符串转换为整数。
                # 基本验证，可以添加更复杂的验证 (例如，月份中的天数)
                if not (1 <= month_int <= 12 and 1 <= day_int <= 31): # 验证月份和日期是否在有效范围内。
                    print(f"警告: 无效的日期部分 '{date_line_content}'. 跳过此日期块。", file=sys.stderr)
                    return # 如果无效，则打印警告并跳过此日期块。
                # 将月份和日期格式化为两位数，不足则补零。
                formatted_month_str = f"{month_int:02d}"
                formatted_day_str = f"{day_int:02d}"
            except ValueError: # 捕获转换整数时可能发生的错误。
                print(f"警告: 无法将日期部分 '{date_line_content}' 解析为数字。跳过此日期块。", file=sys.stderr)
                return # 如果转换失败，则打印警告并跳过。
        else:
            # 如果 process_log_data 的过滤正确，则理想情况下不应达到此情况。
            print(f"警告: 日期行格式无效 '{date_line_content}'. 跳过此日期块。", file=sys.stderr)
            return # 如果日期格式不正确，则打印警告并跳过。

        # 构建最终的日期输出字符串，格式为 "Date:YYYYMMDD"。
        formatted_date_output_str = f"Date:{self.year_to_use}{formatted_month_str}{formatted_day_str}"

        day_has_study_event = False          # 标记当天是否有"study"相关的事件。
        event_related_output_lines = []      # 用于存储处理后的事件相关输出行。

        self._reset_date_block_processing_state() # 在处理新的日期块之前重置状态。

        is_first_event_actual_getup_type = False # 标记第一个事件是否为实际的起床类型 ("醒" 或 "起床")。
        first_event_true_formatted_time = None   # 存储第一个起床事件的格式化时间。

        if event_lines_content: # 检查是否有事件行。
            first_event_line_peek_str = event_lines_content[0] # 获取第一个事件行以进行预检。
            # 检查第一个事件行是否至少有4个字符且前4个字符是数字（时间）。
            if len(first_event_line_peek_str) >= 4 and first_event_line_peek_str[:4].isdigit():
                first_event_peek_raw_time = first_event_line_peek_str[:4]     # 提取原始时间。
                first_event_peek_original_text = first_event_line_peek_str[4:] # 提取原始文本。
                if first_event_peek_original_text in ["醒", "起床"]: # 判断是否为起床事件。
                    is_first_event_actual_getup_type = True # 标记为起床事件。
                    first_event_true_formatted_time = self._format_time(first_event_peek_raw_time) # 格式化起床时间。

        # 根据第一个事件是否为起床类型，准备 "Getup:" 和 "Remark:" 行。
        if is_first_event_actual_getup_type:
            event_related_output_lines.append(f"Getup:{first_event_true_formatted_time}") # 添加格式化的起床时间。
            event_related_output_lines.append("Remark:") # 添加空的 Remark 行。
        else:
            # 如果第一个事件不是起床类型，则 Getup 时间标记为黄色 "null"。
            event_related_output_lines.append(f"Getup:{self.YELLOW}null{self.RESET}")
            event_related_output_lines.append("Remark:") # 添加空的 Remark 行。

        start_processing_from_index = 0 # 初始化事件列表的处理起始索引。
        if is_first_event_actual_getup_type: # 如果第一个事件是起床事件。
            # 消费（处理）第一个事件（起床事件）。
            consumed_event_raw_time = event_lines_content[0][:4]      # 获取原始时间。
            consumed_event_original_text = event_lines_content[0][4:] # 获取原始文本。

            # 将此起床事件的原始时间设置为 "上一个时间间隔的开始时间"。
            # 这是因为起床事件本身不形成一个结束的时间段，它标记了一天的开始。
            # 后续的第一个非起床事件将使用这个时间作为其区间的开始。
            self._last_interval_start_raw_time = consumed_event_raw_time
            # 标记前一个事件是否为原始的"醒"字。
            self._was_previous_event_initial_raw_xing = (consumed_event_original_text == "醒")

            # 获取起床事件的显示文本（可能经过替换映射处理）。
            consumed_display_text = self.TEXT_REPLACEMENT_MAP.get(consumed_event_original_text, consumed_event_original_text)
            if "study" in consumed_display_text: # 检查显示文本中是否包含 "study"。
                day_has_study_event = True # 如果包含，则标记当天有学习事件。
            start_processing_from_index = 1 # 因为第一个事件已被处理，所以从索引1开始处理后续事件。

        # 遍历（剩余的）事件行。
        for i in range(start_processing_from_index, len(event_lines_content)):
            event_line_str = event_lines_content[i] # 当前事件行。
            raw_time = event_line_str[:4]             # 提取当前事件的原始时间。
            original_text = event_line_str[4:]        # 提取当前事件的原始文本。
            current_formatted_time = self._format_time(raw_time) # 格式化当前事件的时间。
            # 获取当前事件的显示文本（可能经过替换映射处理）。
            display_text = self.TEXT_REPLACEMENT_MAP.get(original_text, original_text)

            if "study" in display_text: # 检查显示文本中是否包含 "study"。
                day_has_study_event = True # 如果包含，则标记当天有学习事件。

            # _last_interval_start_raw_time 存储的是上一个事件的时间点，
            # 它将作为当前时间段的开始时间。
            # current_formatted_time 是当前事件的时间点，它将作为当前时间段的结束时间。
            # display_text 是当前事件的描述，它描述的是从 _last_interval_start_raw_time 到 current_formatted_time 这个时间段内发生的活动。

            if self._last_interval_start_raw_time is None: # 这种情况只应在第一个事件不是"起床"类型时发生。
                # 这意味着这是我们遇到的第一个有效的时间点事件，它将作为后续时间段的起点。
                # 但它本身不形成一个完整的 HH:MM~HH:MM时间段，而是打印为 HH:MM活动描述。
                # （这种处理方式可能需要根据具体需求调整，例如，是否应该允许没有起始点的活动）
                event_related_output_lines.append(f"{current_formatted_time}{display_text}") # 将事件作为时间点事件添加。
                self._last_interval_start_raw_time = raw_time # 将当前事件时间设为下一个时间段的开始时间。
                self._was_previous_event_initial_raw_xing = False # 重置"醒"标记。
            else:
                # 如果有上一个时间间隔的开始时间，则形成一个完整的时间段。
                start_formatted_time = self._format_time(self._last_interval_start_raw_time) # 格式化开始时间。
                # 添加格式为 "开始时间~结束时间活动描述" 的行。
                event_related_output_lines.append(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                self._was_previous_event_initial_raw_xing = False # 重置"醒"标记。
                self._last_interval_start_raw_time = raw_time # 更新上一个时间间隔的开始时间为当前事件的时间。

        # 打印日期行。
        print(formatted_date_output_str)
        # 根据当天是否有学习事件，打印带颜色的状态行。
        if day_has_study_event:
            print(f"{self.GREEN}Status:True{self.RESET}")
        else:
            print(f"{self.RED}Status:False{self.RESET}")

        # 打印所有处理过的事件相关行。
        for out_line in event_related_output_lines:
            print(out_line)

    def process_log_data(self, log_data_str: str):
        """
        处理整个日志数据字符串。
        它将日志数据按日期块分割，并对每个块调用 _process_and_print_date_block。
        :param log_data_str: 包含所有日志条目的完整字符串。
        """
        lines = log_data_str.strip().split('\n') #去除首尾空白并按行分割日志数据。

        current_date_raw_content = None      # 用于存储当前正在处理的日期块的原始日期内容。
        current_event_lines_for_block = []   # 用于存储当前日期块的事件行。
        self._printed_at_least_one_block = False # 重置标记，为每次调用 process_log_data。

        # 遍历日志中的每一行。
        for line_content in lines:
            line = line_content.strip() # 去除当前行的首尾空白。
            if not line: # 如果是空行，则跳过。
                continue

            # 修改：检查是否为4位数字的日期行（例如："0115" 代表1月15日）。
            if line.isdigit() and len(line) == 4:
                # 如果当前已有正在处理的日期块内容 (current_date_raw_content 不为 None)，
                # 并且现在遇到了新的日期行，说明上一个日期块已经结束。
                if current_date_raw_content is not None:
                    if self._printed_at_least_one_block: # 如果之前已打印过日期块。
                        print() # 在处理过的日期块之间添加一个空行以提高可读性。
                    # 处理并打印上一个收集到的日期块。
                    self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)
                    self._printed_at_least_one_block = True # 标记已打印过至少一个块。

                # 开始新的日期块。
                current_date_raw_content = line       # 将当前行内容存为新的日期块的日期。
                current_event_lines_for_block = []    # 清空事件行列表，为新的日期块做准备。
            else:
                # 此处假设事件行以4位数字（时间）开头。
                if len(line) >= 4 and line[:4].isdigit():
                    if current_date_raw_content is not None: # 仅当已开始一个日期块时才添加事件行。
                        current_event_lines_for_block.append(line) # 将当前行添加到当前日期块的事件列表中。
                    else:
                        # 如果发现事件行但没有活动的日期块，则打印警告。
                        print(f"警告: 发现事件行 '{line}' 但没有活动的日期块。此行将被忽略。", file=sys.stderr)
                # 可选: else: print(f"跳过无法识别的行格式: {line}", file=sys.stderr) # 处理其他格式的行。


        # 处理日志数据中最后一个日期块 (如果在循环结束后 current_date_raw_content 仍有数据)。
        if current_date_raw_content is not None:
            # 只有在之前打印过块 并且 当前块有事件内容时 才添加空行
            if self._printed_at_least_one_block and current_event_lines_for_block:
                print() # 添加空行。
            self._process_and_print_date_block(current_date_raw_content, current_event_lines_for_block)

def main(): # 定义主函数。
    """
    运行日志处理器的主函数。
    提示用户输入文件名，读取文件，并处理其内容。
    循环直到用户输入 'q' 退出。
    """
    while True: # 无限循环，直到用户选择退出。
        file_path_input = input("请输入txt文件名 (或输入 'q' 退出): ") # 提示用户输入。
        if file_path_input.lower() == 'q': # 如果用户输入 'q' (不区分大小写)。
            print("程序退出。") # 打印退出信息。
            break # 跳出循环，结束程序。
        
        if not file_path_input: # 如果用户没有输入任何内容（直接回车）。
            print("未输入文件名，请重新输入。", file=sys.stderr) # 打印错误信息到标准错误流。
            print("-" * 30) # 打印分隔线。
            continue # 继续下一次循环，要求用户重新输入。
        try:
            # 尝试以只读模式打开用户指定的文件，使用UTF-8编码。
            with open(file_path_input, 'r', encoding='utf-8') as file:
                input_data = file.read() # 读取文件的全部内容。
            
            processor = LogProcessor() # 创建LogProcessor的实例（使用默认年份2025和"end2duration.json"）。
            print("-" * 30) # 打印分隔线，准备开始输出处理结果。
            processor.process_log_data(input_data) # 调用实例的process_log_data方法处理文件内容。
            print("-" * 30) # 打印分隔线，处理结束。
        except FileNotFoundError: # 如果文件未找到。
            print(f"错误: 文件 '{file_path_input}' 未找到。", file=sys.stderr) # 打印文件未找到的错误信息。
            print("-" * 30) # 打印分隔线。
        except Exception as e: # 捕获其他在文件处理过程中可能发生的异常。
            print(f"处理文件时发生错误: {e}", file=sys.stderr) # 打印通用错误信息。
            print("-" * 30) # 打印分隔线。

if __name__ == '__main__': # 确保以下代码只在脚本作为主程序直接运行时执行。
    main() # 调用主函数。
