# 导入所需模块
import re   # 正则表达式模块，用于文本匹配和解析
import time  # 时间模块，用于计时操作
import json  # JSON模块，用于处理JSON格式的配置文件
import os   # 操作系统模块，用于文件和目录路径操作
import argparse # 导入 argparse 模块

# 定义一个类，用于在控制台输出带颜色的文本，以增强可读性
class Colors:
    GREEN = '\033[92m'  # ANSI转义码：亮绿色
    RED = '\033[91m'    # ANSI转义码：亮红色
    YELLOW = '\033[93m' # ANSI转义码：亮黄色
    RESET = '\033[0m'   # ANSI转义码：重置颜色，恢复到默认终端颜色

# 定义配置文件的路径常量
CONFIG_FILE_PATH = "activity_validator_config.json"

# 定义配置管理类，负责加载和管理程序的配置信息
class ConfigManager:
    def __init__(self, config_file_path):
        """
        构造函数，初始化配置管理器。
        :param config_file_path: 配置文件的路径。
        """
        self.config_file_path = config_file_path  # 存储配置文件路径
        self.parent_categories = {}  # 用于存储父类别及其允许的子标签集合的字典
        self.disallowed_standalone_categories = set() # 用于存储不允许单独使用的父类别名称的集合

    def load(self):
        """
        从JSON文件加载配置，并填充实例属性 (parent_categories, disallowed_standalone_categories)。
        :return: True表示加载成功，False表示加载失败。
        """
        # 检查配置文件是否存在
        if not os.path.exists(self.config_file_path):
            print(f"错误: 配置文件 '{self.config_file_path}' 未找到。程序将使用空配置退出。")
            return False # 文件不存在，加载失败

        try:
            #尝试打开并读取JSON配置文件
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f) # 解析JSON数据
        except json.JSONDecodeError as e: #捕获JSON解析错误
            print(f"错误: 解析配置文件 '{self.config_file_path}' 失败: {e}。程序将使用空配置退出。")
            return False # JSON格式错误，加载失败
        except Exception as e: # 捕获其他可能的读取错误
            print(f"读取配置文件 '{self.config_file_path}' 时发生未知错误: {e}。程序将使用空配置退出。")
            return False # 其他未知错误，加载失败

        # 从配置数据中获取 "PARENT_CATEGORIES" 部分，如果不存在则默认为空字典
        parent_categories_from_json = config_data.get("PARENT_CATEGORIES", {})
        loaded_parent_categories_temp = {} # 临时字典存储加载的父类别
        # 遍历从JSON中读取的父类别
        for category, labels_list in parent_categories_from_json.items():
            if isinstance(labels_list, list): # 检查标签列表是否真的是列表类型
                loaded_parent_categories_temp[category] = set(labels_list) # 将列表转换为集合以提高查找效率
            else:
                # 如果格式不正确，打印警告并为此类别设置一个空集合
                print(f"警告: 配置文件中类别 '{category}' 的标签格式不正确 (应为列表)，已忽略此类别。")
                loaded_parent_categories_temp[category] = set()

        self.parent_categories = loaded_parent_categories_temp # 更新实例的父类别字典
        # 不允许单独使用的类别即为所有父类别的名称
        self.disallowed_standalone_categories = set(self.parent_categories.keys())
        print(f"配置已从 '{self.config_file_path}' 加载。")
        return True # 配置加载成功

# 定义行校验器类，负责校验文件中每一行的格式和内容
class LineValidator:
    def __init__(self, config_manager: ConfigManager):
        """
        构造函数，初始化行校验器。
        :param config_manager: ConfigManager的实例，用于获取类别配置信息。
        """
        self.config_manager = config_manager # 存储配置管理器实例

    @staticmethod # 声明为静态方法，因为此方法不依赖于实例的状态
    def validate_time_format(time_str):
        """
        校验时间字符串是否为有效的HH:MM格式 (00:00 - 23:59)。
        :param time_str: 要校验的时间字符串。
        :return: True表示有效，False表示无效。
        """
        try:
            hh, mm = time_str.split(':') # 按冒号分割小时和分钟
            if len(hh) != 2 or len(mm) != 2: # 检查小时和分钟是否都是两位数
                return False
            if 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59: # 检查小时和分钟的范围
                return True
            return False # 时间值超出范围
        except ValueError: # 如果分割或转换整数失败（例如，"aa:bb"）
            return False

    def check_date_line(self, line, line_num, errors):
        """
        校验日期行 (Date:YYYYMMDD)。
        :param line: 要校验的行内容。
        :param line_num: 当前行号。
        :param errors: 用于收集错误信息的列表。
        :return: True表示此行是有效的日期行结构（不保证日期本身逻辑正确，只保证格式），False表示结构错误。
        """
        if not line.startswith('Date:'): # 检查是否以 "Date:" 开头
            errors.append(f"第{line_num}行错误:Date行缺少冒号或前缀不正确")
            return False
        elif not re.fullmatch(r'Date:\d{8}', line): # 使用正则表达式完整匹配 "Date:" 后跟8位数字
            errors.append(f"第{line_num}行错误:Date格式应为YYYYMMDD")
            return False
        return True # 格式正确

    def check_status_line(self, line, line_num, errors):
        """
        校验状态行 (Status:True 或 Status:False)。
        :param line: 要校验的行内容。
        :param line_num: 当前行号。
        :param errors: 用于收集错误信息的列表。
        """
        # 使用正则表达式完整匹配 "Status:" 后跟 "True" 或 "False"
        if not re.fullmatch(r'Status:(True|False)', line):
            errors.append(f"第{line_num}行错误:Status必须为True或False")

    def check_getup_line(self, line, line_num, errors):
        """
        校验起床时间行 (Getup:HH:MM)。
        :param line: 要校验的行内容。
        :param line_num: 当前行号。
        :param errors: 用于收集错误信息的列表。
        """
        # 使用正则表达式匹配 "Getup:" 后跟 HH:MM 格式
        if not re.fullmatch(r'Getup:\d{2}:\d{2}', line):
            errors.append(f"第{line_num}行错误:Getup时间格式不正确 (应为 Getup:HH:MM)")
        else:
            time_part = line[6:] # 提取时间部分 (HH:MM)
            if not self.validate_time_format(time_part): # 使用静态方法校验时间值的有效性
                errors.append(f"第{line_num}行错误:Getup时间无效 ({time_part})")

    def check_remark_line(self, line, line_num, errors):
        """
        校验备注行 (Remark:...)。
        :param line: 要校验的行内容。
        :param line_num: 当前行号。
        :param errors: 用于收集错误信息的列表。
        """
        if not line.startswith('Remark:'): # 检查是否以 "Remark:" 开头
            errors.append(f"第{line_num}行错误:Remark格式不正确 (应以 'Remark:' 开头)")

    def check_time_line(self, line, line_num, errors):
        """
        校验时间记录行 (HH:MM~HH:MM文本内容)。
        这包括时间格式、时间逻辑、以及文本内容是否符合配置中的类别规则。
        :param line: 要校验的行内容。
        :param line_num: 当前行号。
        :param errors: 用于收集错误信息的列表。
        """
        # 正则表达式匹配 "HH:MM~HH:MM文本内容"
        # ^(\d{2}:\d{2}) : 匹配开头的 HH:MM (开始时间)
        # ~ : 匹配波浪号分隔符
        # (\d{2}:\d{2}) : 匹配 HH:MM (结束时间)
        # ([a-zA-Z0-9_-]+)$ : 匹配由字母、数字、下划线、连字符组成的文本内容，直到行尾
        match = re.match(r'^(\d{2}:\d{2})~(\d{2}:\d{2})([a-zA-Z0-9_-]+)$', line)
        if not match: # 如果不匹配指定格式
            errors.append(f"第{line_num}行错误:时间行格式错误 (应为 HH:MM~HH:MM文本内容)")
            return # 格式错误，后续校验无意义

        start_time_str, end_time_str, activity_label = match.groups() # 获取匹配到的开始时间、结束时间、活动标签
        error_added_for_label_check = False # 标记是否已因标签检查添加了错误

        # 检查活动标签是否是不允许单独使用的父类别
        if activity_label in self.config_manager.disallowed_standalone_categories:
            errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 为父级类别，不够具体，不能单独使用。")
            error_added_for_label_check = True
        else:
            # 如果不是禁止单独使用的父类别，则检查它是否是某个父类别下的有效子标签
            found_matching_category = False # 标记是否找到了匹配的父类别
            for parent_category, allowed_children in self.config_manager.parent_categories.items():
                # 如果活动标签以 "父类别_" 开头 (例如 "code_python")
                if activity_label.startswith(parent_category + "_"):
                    found_matching_category = True
                    # 检查此活动标签是否在允许的子标签集合中
                    if activity_label not in allowed_children:
                        # 如果不在，则报错，并给出一些允许的示例
                        errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 在类别 '{parent_category}' 中无效。允许的 '{parent_category}' 内容例如: {', '.join(sorted(list(allowed_children))[:3])} 等。")
                        error_added_for_label_check = True
                    break # 找到对应的父类别前缀后，无需再检查其他父类别

            # 如果没有找到匹配的父类别前缀，并且之前没有因为标签问题报错
            if not found_matching_category and not error_added_for_label_check:
                all_examples = [] # 收集所有配置中定义的子标签作为示例
                for children in self.config_manager.parent_categories.values():
                    all_examples.extend(list(children))
                if all_examples:
                    # 如果有配置的子标签，报错并给出示例
                    errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。它不属于任何已定义的类别 (如 'code_', 'routine_') 或并非这些类别下允许的具体活动。允许的具体活动例如: {', '.join(sorted(all_examples)[:3])} 等。")
                else:
                    # 如果配置中没有任何子标签定义
                    errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。没有定义允许的活动类别。")

        # 校验开始时间和结束时间的时间格式
        start_valid = self.validate_time_format(start_time_str)
        end_valid = self.validate_time_format(end_time_str)

        if not start_valid:
            errors.append(f"第{line_num}行错误:开始时间值无效 ({start_time_str})")
        if not end_valid:
            errors.append(f"第{line_num}行错误:结束时间值无效 ({end_time_str})")

        # 如果开始或结束时间格式无效，则后续的时间逻辑比较无意义
        if not (start_valid and end_valid):
            return

        # 将时间字符串转换为整数进行比较
        start_h, start_m = map(int, start_time_str.split(':'))
        end_h, end_m = map(int, end_time_str.split(':'))
        # 检查时间逻辑：如果小时相同，结束时间的分钟数不应小于开始时间的分钟数
        # (注意：这里没有检查结束时间小于开始时间的情况，例如 10:00~09:00，这可能是一个更复杂的业务逻辑，当前脚本未处理跨天或整体时间顺序)
        if start_h == end_h and end_m < start_m:
            errors.append(f"第{line_num}行错误:当小时相同时，结束时间分钟数({end_m:02d})不应小于开始时间分钟数({start_m:02d})")

# 定义文件处理器类，负责读取文件内容并调用行校验器进行校验
class FileProcessor:
    def __init__(self, line_validator: 'LineValidator'): # 使用前向引用类型注解 LineValidator
        """
        构造函数，初始化文件处理器。
        :param line_validator: LineValidator的实例。
        """
        self.validator = line_validator # 存储行校验器实例

    def process_and_validate_file_contents(self, file_path):
        """
        处理并校验指定文件的内容。
        文件结构预期为：
        Date:YYYYMMDD
        Status:True/False
        Getup:HH:MM
        Remark:任意文本
        HH:MM~HH:MM活动1
        HH:MM~HH:MM活动2
        ...
        (空行)
        Date:YYYYMMDD
        ...

        :param file_path: 要处理的文件的路径。
        :return: 一个包含所有错误信息的列表。如果文件读取失败，则返回None。
        """
        errors = [] # 初始化错误列表
        try:
            # 打开文件并读取所有行，去除每行末尾的空白字符
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            # print(f"错误: 文件 '{file_path}' 未找到。") # 调用者会处理这个
            return None # 文件未找到，返回None表示读取错误
        except Exception as e: # 捕获其他可能的读取错误
            # print(f"读取文件 '{file_path}' 时发生错误: {e}") # 调试信息，由调用者处理
            return None # 其他读取错误，返回None

        current_outer_line_idx = 0 # 主循环的当前行索引，用于遍历以"Date:"开头的块
        total_lines = len(lines) # 文件总行数
        processed_any_valid_date_header = False # 标记是否已处理过至少一个有效的 "Date:" 头部

        # 主循环，按 "Date:" 块处理文件
        while current_outer_line_idx < total_lines:
            line_number_for_report = current_outer_line_idx + 1 # 用于报告的行号 (从1开始)
            line_content_current_outer = lines[current_outer_line_idx] # 当前行的内容

            # 跳过 "Date:" 块之间的空行
            if not line_content_current_outer:
                current_outer_line_idx += 1
                continue

            # 如果当前行以 "Date:" 开头，说明是一个新的日期记录块
            if line_content_current_outer.startswith('Date:'):
                processed_any_valid_date_header = True # 标记已处理过Date头
                date_block_start_actual_line_num = line_number_for_report # 记录此Date块开始的实际行号

                # 校验Date行的格式
                is_date_line_valid = self.validator.check_date_line(line_content_current_outer, date_block_start_actual_line_num, errors)
                if not is_date_line_valid: # 如果Date行格式无效
                    # 跳过这个无效的Date块，直到找到下一个 "Date:" 行或文件末尾
                    idx_after_bad_date = current_outer_line_idx + 1
                    while idx_after_bad_date < total_lines and \
                            (not lines[idx_after_bad_date].startswith('Date:') if lines[idx_after_bad_date] else True): # 空行也跳过
                        idx_after_bad_date += 1
                    current_outer_line_idx = idx_after_bad_date # 更新主循环索引到下一个Date块或文件尾
                    continue # 继续主循环的下一次迭代

                # Date行结构有效，继续处理这个块内的其他行
                status_line_content_for_day = None # 当天Status行的内容
                status_line_number_for_day = -1 # 当天Status行的行号
                day_contains_study_activity = False # 标记当天活动是否包含 "study"

                headers_structurally_present = True # 假设头部（Status, Getup, Remark）结构上都存在

                # 检查 Status 头部 (Date行后的第一行)
                status_idx_in_lines = current_outer_line_idx + 1
                if status_idx_in_lines >= total_lines: # 如果文件在Date行后就结束了
                    errors.append(f"文件在第{date_block_start_actual_line_num}行的Date块后意外结束，缺少 Status 行。")
                    headers_structurally_present = False
                else:
                    status_line_content_for_day = lines[status_idx_in_lines]
                    status_line_number_for_day = status_idx_in_lines + 1
                    if not status_line_content_for_day.startswith("Status:"): # 检查前缀
                        errors.append(f"第{status_line_number_for_day}行错误:应为 'Status:' 开头，实际为 '{status_line_content_for_day[:30]}...'")
                    # 即使前缀可能错误，仍然调用check_status_line来检查 "Status:True/False" 格式
                    self.validator.check_status_line(status_line_content_for_day, status_line_number_for_day, errors)

                # 检查 Getup 头部 (Date行后的第二行)
                getup_idx_in_lines = current_outer_line_idx + 2
                if headers_structurally_present: # 仅当之前的头部（Status）被认为结构上存在时才检查
                    if getup_idx_in_lines >= total_lines:
                        errors.append(f"文件在第{date_block_start_actual_line_num}行的Date块后意外结束，缺少 Getup 行。")
                        headers_structurally_present = False
                    else:
                        getup_line_content = lines[getup_idx_in_lines]
                        getup_line_number = getup_idx_in_lines + 1
                        if not getup_line_content.startswith("Getup:"):
                            errors.append(f"第{getup_line_number}行错误:应为 'Getup:' 开头，实际为 '{getup_line_content[:30]}...'")
                        self.validator.check_getup_line(getup_line_content, getup_line_number, errors)

                # 检查 Remark 头部 (Date行后的第三行)
                remark_idx_in_lines = current_outer_line_idx + 3
                if headers_structurally_present: # 仅当之前的头部（Status, Getup）被认为结构上存在时才检查
                    if remark_idx_in_lines >= total_lines:
                        errors.append(f"文件在第{date_block_start_actual_line_num}行的Date块后意外结束，缺少 Remark 行。")
                        headers_structurally_present = False
                    else:
                        remark_line_content = lines[remark_idx_in_lines]
                        remark_line_number = remark_idx_in_lines + 1
                        if not remark_line_content.startswith("Remark:"):
                            errors.append(f"第{remark_line_number}行错误:应为 'Remark:' 开头，实际为 '{remark_line_content[:30]}...'")
                        # Remark行通常只需要检查前缀，check_remark_line只做这个
                        self.validator.check_remark_line(remark_line_content, remark_line_number, errors)

                # 如果头部结构不完整 (例如，文件提前结束)，则跳过此Date块的后续活动行处理
                if not headers_structurally_present:
                    idx_scanner = current_outer_line_idx + 1 # 从Date行之后开始扫描
                    # 跳到下一个Date行或文件末尾
                    while idx_scanner < total_lines and \
                            (not lines[idx_scanner].startswith('Date:') if lines[idx_scanner] else True):
                        idx_scanner += 1
                    current_outer_line_idx = idx_scanner
                    continue # 继续主循环

                # --- 活动行处理 (仅当头部结构完整时) ---
                first_activity_line_idx_in_lines = current_outer_line_idx + 4 # Date, Status, Getup, Remark 之后的行

                current_activity_processing_idx = first_activity_line_idx_in_lines
                activity_lines_data_for_validation = [] # 存储待校验的活动行及其行号

                # 循环读取属于当前Date块的活动行
                while current_activity_processing_idx < total_lines and \
                        (not lines[current_activity_processing_idx].startswith('Date:')): # 直到遇到下一个Date行或文件末尾
                    
                    activity_content = lines[current_activity_processing_idx]
                    activity_num = current_activity_processing_idx + 1

                    if activity_content: # 只处理非空行作为活动行
                        activity_lines_data_for_validation.append({'content': activity_content, 'num': activity_num})
                        
                        # 检查活动行是否包含 "study"，用于后续的Status校验规则
                        # 活动行格式: HH:MM~HH:MM文本内容
                        match = re.match(r'^\d{2}:\d{2}~\d{2}:\d{2}(.*)$', activity_content)
                        if match:
                            activity_text_part = match.group(1) # 提取文本内容部分
                            if "study" in activity_text_part: # 大小写敏感地查找 "study"
                                day_contains_study_activity = True
                    
                    current_activity_processing_idx += 1 # 处理下一行
                
                # 应用新的基于 "study" 的 Status 校验规则
                # 此规则仅在 Status 行本身格式为 "Status:True" 或 "Status:False" 时应用
                if status_line_content_for_day is not None and status_line_number_for_day != -1:
                    # 再次确认Status行格式是否为 Status:True 或 Status:False
                    actual_status_match = re.fullmatch(r'Status:(True|False)', status_line_content_for_day)
                    if actual_status_match: # 如果Status行格式正确
                        actual_status_bool = actual_status_match.group(1) == "True" # 将Status值转为布尔型
                        expected_status_bool = day_contains_study_activity # 期望的Status值取决于当天是否有study活动

                        if actual_status_bool != expected_status_bool: # 如果实际值与期望值不符
                            reason_verb = "包含" if day_contains_study_activity else "不包含"
                            errors.append(
                                f"第{status_line_number_for_day}行错误: Status应为 Status:{str(expected_status_bool)} (因活动{reason_verb} 'study')，但找到 Status:{actual_status_match.group(1)}。"
                            )
                    # 如果 actual_status_match 为 None，表示 Status 行格式本身就有问题 (例如 "Status:Maybe")
                    # 这种结构性错误已由 self.validator.check_status_line 捕获。
                    # 新的 "study" 规则只在Status本身可以被解析为 True 或 False 时才应用。
                
                # 对收集到的所有活动行进行逐行校验
                for act_line_info in activity_lines_data_for_validation:
                    self.validator.check_time_line(act_line_info['content'], act_line_info['num'], errors)

                # 更新主循环的索引到下一个块的开始位置 (即当前活动块的结束位置)
                current_outer_line_idx = current_activity_processing_idx
                continue # 继续主循环处理下一个 "Date:" 块
                
            else: # 当前行不是以 "Date:" 开头 (也不是在主循环开头被跳过的空行)
                # 如果这是文件开头的一些非 "Date:" 行 (且非空)
                if not processed_any_valid_date_header and line_content_current_outer:
                    errors.append(f"第{line_number_for_report}行错误: 文件应以 'Date:YYYYMMDD' 格式的行开始。当前行为: '{line_content_current_outer[:50]}...'")
                    processed_any_valid_date_header = True # 标记此错误已报告，避免对后续每个前导非Date行都报告
                    
                    # 跳过这些无效的前导行，直到找到第一个 "Date:" 或文件末尾
                    idx_scanner = current_outer_line_idx + 1
                    while idx_scanner < total_lines and \
                            (not lines[idx_scanner].startswith('Date:') if lines[idx_scanner] else True):
                        idx_scanner += 1
                    current_outer_line_idx = idx_scanner
                    continue # 继续主循环

                # 如果已经处理过Date块，但现在又遇到一个非空且非Date开头的行
                # 这意味着在一个Date块结束后，下一个Date块开始前，出现了不应有的内容
                elif line_content_current_outer:
                    errors.append(f"第{line_number_for_report}行错误: 意外的内容，此处应为新的 'Date:' 块或文件末尾。内容: '{line_content_current_outer[:50]}...'")
                    # 跳过这些意外内容，直到找到下一个 "Date:" 或文件末尾
                    idx_scanner = current_outer_line_idx + 1
                    while idx_scanner < total_lines and \
                            (not lines[idx_scanner].startswith('Date:') if lines[idx_scanner] else True):
                        idx_scanner += 1
                    current_outer_line_idx = idx_scanner
                    continue # 继续主循环
                else: 
                    # 此情况理论上不应到达，因为主循环开头的 `if not line_content_current_outer:` 会处理空行。
                    # 作为安全措施，如果是一个空行到达这里，则前进索引。
                    current_outer_line_idx += 1


        # 文件处理完毕后的最终检查
        # 如果文件有内容，但从未处理过任何有效的 "Date:" 头部 (例如，文件全是垃圾数据或只有空行)
        if not processed_any_valid_date_header and any(l.strip() for l in lines): # `any(l.strip() for l in lines)` 检查文件是否真的有非空内容
            # 检查是否已经因为第一行不是Date而报过错了
            is_first_line_error_present = any("文件应以 'Date:YYYYMMDD' 格式的行开始" in err for err in errors)
            if not is_first_line_error_present: # 如果没有报过第一行错误，则补充一个总的错误
                errors.append(f"错误: 文件不包含任何以 'Date:YYYYMMDD' 开头的有效数据块。")
        
        return errors # 返回收集到的所有错误信息

def main():
    """
    主函数，程序的入口点。
    """
    # 设置命令行参数解析器
    parser = argparse.ArgumentParser(description="校验TXT日志文件的格式和内容。")
    parser.add_argument("input_path", help="要校验的TXT文件路径或包含TXT文件的目录路径。")
    args = parser.parse_args()
    target_path = args.input_path

    # 初始化配置管理器并加载配置
    config_manager = ConfigManager(CONFIG_FILE_PATH)
    if not config_manager.load(): # 如果配置加载失败
        print("警告: 配置加载失败或文件未找到。程序将继续，但某些校验规则可能无法应用。")

    # 初始化行校验器和文件处理器
    line_validator = LineValidator(config_manager)
    file_processor = FileProcessor(line_validator)

    print("欢迎使用TXT文件校验工具。")
    print("========================================")

    files_to_process = [] # 存储待处理的文件路径列表
    is_directory_scan = False # 标记是否是目录扫描

    # 检查路径是否存在
    if not os.path.exists(target_path):
        print(f"错误: 路径 '{target_path}' 不存在。程序将退出。")
        return

    # 如果输入的是目录
    if os.path.isdir(target_path):
        is_directory_scan = True
        print(f"\n{Colors.GREEN}正在递归扫描目录 '{target_path}' 及其所有子目录...{Colors.RESET}")
        # 遍历目录及其所有子目录
        for dirpath, _, filenames in os.walk(target_path): # dirnames 未使用，用 _ 代替
            for filename in filenames:
                if filename.lower().endswith(".txt"): # 只处理 .txt 文件
                    full_path = os.path.join(dirpath, filename) # 获取完整文件路径
                    files_to_process.append(full_path)
        
        if not files_to_process: # 如果目录中没有找到 .txt 文件
            print(f"在目录 '{target_path}' 及其子目录中未找到 .txt 文件。程序将退出。")
            return
        else:
            print(f"\n在目录 '{target_path}' 及其子目录中找到 {len(files_to_process)} 个 .txt 文件准备处理。")

    # 如果输入的是文件
    elif os.path.isfile(target_path):
        if target_path.lower().endswith(".txt"): # 检查是否是 .txt 文件
            files_to_process.append(target_path)
        else:
            print(f"错误: 文件 '{target_path}' 不是一个 .txt 文件。程序将退出。")
            return
    else: # 如果输入的既不是文件也不是目录
        print(f"错误: 路径 '{target_path}' 不是一个有效的文件或目录。程序将退出。")
        return
    
    # 开始批量处理计时
    batch_overall_start_time = time.perf_counter()
    total_files_in_batch = len(files_to_process)
    files_with_errors_count_in_batch = 0 # 批处理中有错误的文件计数

    try:
        # 遍历所有待处理的文件
        for i, current_file_path in enumerate(files_to_process):
            file_process_start_time = time.perf_counter() # 单个文件处理开始计时
            
            # 调用FileProcessor处理并校验文件内容
            validation_errors = file_processor.process_and_validate_file_contents(current_file_path)

            current_file_has_errors = False # 标记当前文件是否有错误
            if validation_errors is None: # 文件读取失败
                files_with_errors_count_in_batch += 1
                current_file_has_errors = True
            elif validation_errors: # 文件有格式错误
                files_with_errors_count_in_batch += 1
                current_file_has_errors = True
            
            # 根据是否有错误设置输出颜色和进度指示
            indicator_color = Colors.RED if current_file_has_errors else Colors.GREEN
            progress_indicator = f"[{i+1}/{total_files_in_batch}]" # 例如: [1/5]
            print(f"\n{indicator_color}{progress_indicator}{Colors.RESET} 开始处理文件: {current_file_path}")


            if validation_errors is None: # 文件读取失败
                print(f"注意: 文件 '{current_file_path}' 读取失败或无法访问。")
            elif validation_errors: # 文件有格式错误
                print(f"文件 '{current_file_path}' 发现以下错误:")
                # 对错误信息去重并按行号排序
                # 使用正则表达式从错误信息中提取行号用于排序
                unique_errors = sorted(list(set(validation_errors)), 
                                    key=lambda x: int(re.search(r'第(\d+)行', x).group(1)) if re.search(r'第(\d+)行', x) else 0)
                for error in unique_errors:
                    print(f"  {error}") # 缩进显示错误信息
            else: # 文件格式完全正确
                print(f"文件 '{current_file_path}' 格式完全正确！")

            file_process_end_time = time.perf_counter() # 单个文件处理结束计时
            print(f"处理文件 '{current_file_path}' 时间: {file_process_end_time - file_process_start_time:.6f} 秒")
            if i < total_files_in_batch - 1: # 如果不是最后一个文件，打印分隔线
                print("---") 

        # 如果处理了至少一个文件，打印总结信息
        if total_files_in_batch > 0:
            batch_overall_end_time = time.perf_counter() # 批处理结束计时
            print("\n--- 处理总结 ---")
            print(f"总共处理 {total_files_in_batch} 个 .txt 文件。")
            if files_with_errors_count_in_batch > 0:
                print(f"{Colors.RED}其中 {files_with_errors_count_in_batch} 个文件存在格式错误或读取问题。{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}所有处理的文件均格式正确。{Colors.RESET}") # 已修正：确保此消息在无错误时显示
            print(f"所有文件处理总耗时: {batch_overall_end_time - batch_overall_start_time:.6f} 秒")

    except KeyboardInterrupt: # 捕获 Ctrl+C
        print("\n用户中断，程序已部分执行后退出。")
    except Exception as e: # 捕获其他意外的致命错误
        print(f"\n程序执行过程中发生致命错误: {e}")
        import traceback # 导入traceback模块以打印详细的堆栈信息
        traceback.print_exc() # 打印异常的堆栈跟踪
    finally:
        print("程序已退出。")

# Python的惯用写法，确保当脚本被直接执行时，main()函数会被调用
# 如果脚本作为模块被导入到其他脚本中，则main()不会自动执行
if __name__ == "__main__":
    main()
