import re
import time
import json # 导入 json 模块
import os   # 导入 os 模块，用于检查文件是否存在

# 定义配置文件的路径 (remains a global constant or could be part of App setup)
CONFIG_FILE_PATH = "check_input_config.json" 

class ConfigManager:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.parent_categories = {}
        self.disallowed_standalone_categories = set()

    def load(self):
        """从JSON文件加载配置并填充实例属性"""
        if not os.path.exists(self.config_file_path):
            print(f"错误: 配置文件 '{self.config_file_path}' 未找到。程序将使用空配置退出。")
            # self.parent_categories and self.disallowed_standalone_categories remain empty as initialized
            return False 

        try:
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"错误: 解析配置文件 '{self.config_file_path}' 失败: {e}。程序将使用空配置退出。")
            return False
        except Exception as e:
            print(f"读取配置文件 '{self.config_file_path}' 时发生未知错误: {e}。程序将使用空配置退出。")
            return False

        parent_categories_from_json = config_data.get("PARENT_CATEGORIES", {})
        
        loaded_parent_categories_temp = {}
        for category, labels_list in parent_categories_from_json.items():
            if isinstance(labels_list, list):
                loaded_parent_categories_temp[category] = set(labels_list)
            else:
                print(f"警告: 配置文件中类别 '{category}' 的标签格式不正确 (应为列表)，已忽略此类别。")
                loaded_parent_categories_temp[category] = set() # Ensure category is added with empty set
            
        self.parent_categories = loaded_parent_categories_temp
        self.disallowed_standalone_categories = set(self.parent_categories.keys())
        print(f"配置已从 '{self.config_file_path}' 加载。")
        return True

class LineValidator:
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager

    @staticmethod
    def validate_time_format(time_str):
        try:
            hh, mm = time_str.split(':')
            if len(hh) != 2 or len(mm) != 2:
                return False
            if 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59:
                return True
            return False
        except ValueError:
            return False

    def check_date_line(self, line, line_num, errors):
        if not line.startswith('Date:'):
            errors.append(f"第{line_num}行错误:Date行缺少冒号")
            return False
        elif not re.fullmatch(r'Date:\d{8}', line):
            errors.append(f"第{line_num}行错误:Date格式应为YYYYMMDD")
            return False
        return True

    def check_status_line(self, line, line_num, errors):
        if not re.fullmatch(r'Status:(True|False)', line):
            errors.append(f"第{line_num}行错误:Status必须为True或False")

    def check_getup_line(self, line, line_num, errors):
        if not re.fullmatch(r'Getup:\d{2}:\d{2}', line): 
            errors.append(f"第{line_num}行错误:Getup时间格式不正确 (应为 Getup:HH:MM)")
        else:
            time_part = line[6:] 
            if not self.validate_time_format(time_part):
                errors.append(f"第{line_num}行错误:Getup时间无效 ({time_part})")

    def check_remark_line(self, line, line_num, errors):
        if not line.startswith('Remark:'): 
            errors.append(f"第{line_num}行错误:Remark格式不正确 (应以 'Remark:' 开头)")

    def check_time_line(self, line, line_num, errors):
        match = re.match(r'^(\d{2}:\d{2})~(\d{2}:\d{2})([a-zA-Z0-9_-]+)$', line)
        if not match:
            errors.append(f"第{line_num}行错误:时间行格式错误 (应为 HH:MM~HH:MM文本内容)")
            return

        start_time_str, end_time_str, activity_label = match.groups()
        error_added_for_label_check = False 

        if activity_label in self.config_manager.disallowed_standalone_categories:
            errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 为父级类别，不够具体，不能单独使用。")
            error_added_for_label_check = True
        else:
            found_matching_category = False
            for parent_category, allowed_children in self.config_manager.parent_categories.items():
                if activity_label.startswith(parent_category + "_"):
                    found_matching_category = True
                    if activity_label not in allowed_children:
                        errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 在类别 '{parent_category}' 中无效。允许的 '{parent_category}' 内容例如: {', '.join(sorted(list(allowed_children))[:3])} 等。")
                        error_added_for_label_check = True
                    break 

            if not found_matching_category and not error_added_for_label_check:
                all_examples = []
                for children in self.config_manager.parent_categories.values():
                    all_examples.extend(list(children))
                if all_examples: 
                    errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。它不属于任何已定义的类别 (如 'code_', 'routine_') 或并非这些类别下允许的具体活动。允许的具体活动例如: {', '.join(sorted(all_examples)[:3])} 等。")
                else: 
                    errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。没有定义允许的活动类别。")

        start_valid = self.validate_time_format(start_time_str)
        end_valid = self.validate_time_format(end_time_str)

        if not start_valid:
            errors.append(f"第{line_num}行错误:开始时间值无效 ({start_time_str})")
        if not end_valid:
            errors.append(f"第{line_num}行错误:结束时间值无效 ({end_time_str})")

        if not (start_valid and end_valid):
            return

        start_h, start_m = map(int, start_time_str.split(':'))
        end_h, end_m = map(int, end_time_str.split(':'))
        if start_h == end_h and end_m < start_m:
            errors.append(f"第{line_num}行错误:当小时相同时，结束时间分钟数({end_m:02d})不应小于开始时间分钟数({start_m:02d})")

class FileProcessor:
    def __init__(self, line_validator: LineValidator):
        self.validator = line_validator

    def process_and_validate_file_contents(self, file_path):
        """
        Reads and validates the content of the given file according to predefined rules.
        This method was previously the top-level process_file_and_validate function.
        """
        errors = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            print(f"错误: 文件 '{file_path}' 未找到。")
            return None
        except Exception as e:
            print(f"读取文件 '{file_path}' 时发生错误: {e}")
            return None

        current_line_idx = 0
        total_lines = len(lines)
        processed_any_valid_date_header = False

        while current_line_idx < total_lines:
            line_number_for_report = current_line_idx + 1
            line = lines[current_line_idx]

            if not line: 
                current_line_idx += 1
                continue
            
            if line.startswith('Date:'):
                processed_any_valid_date_header = True
                is_date_line_structurally_valid = self.validator.check_date_line(line, line_number_for_report, errors)

                if is_date_line_structurally_valid:
                    expected_headers = ['Status', 'Getup', 'Remark']
                    header_check_ok = True
                    date_block_start_line_number = line_number_for_report 

                    for i, header_name in enumerate(expected_headers):
                        current_line_idx += 1 
                        header_line_number_for_report = current_line_idx + 1

                        if current_line_idx >= total_lines:
                            errors.append(f"文件在第{date_block_start_line_number}行的Date块后意外结束，缺少 {header_name} 行。")
                            header_check_ok = False
                            break  

                        current_header_line = lines[current_line_idx]
                        if not current_header_line.startswith(f"{header_name}:"):
                            errors.append(f"第{header_line_number_for_report}行错误:应为 '{header_name}:' 开头，实际为 '{current_header_line[:30]}...'")
                            header_check_ok = False
                        
                        if header_name == 'Status':
                            self.validator.check_status_line(current_header_line, header_line_number_for_report, errors)
                        elif header_name == 'Getup':
                            self.validator.check_getup_line(current_header_line, header_line_number_for_report, errors)
                        elif header_name == 'Remark':
                            self.validator.check_remark_line(current_header_line, header_line_number_for_report, errors)
                    
                    if header_check_ok:
                        current_line_idx += 1  
                        while current_line_idx < total_lines and (not lines[current_line_idx].startswith('Date:')):
                            time_line_number_for_report = current_line_idx + 1
                            time_line = lines[current_line_idx]
                            if time_line: 
                                self.validator.check_time_line(time_line, time_line_number_for_report, errors)
                            current_line_idx += 1
                        continue 
                    else: 
                        if current_line_idx < total_lines and not lines[current_line_idx].startswith('Date:'):
                            current_line_idx += 1 
                        continue 
                else: 
                    errors.append(f"第{line_number_for_report}行错误: Date行格式不正确，尝试查找下一个Date块。")
                    current_line_idx += 1 
                    while current_line_idx < total_lines and not lines[current_line_idx].startswith('Date:'):
                        current_line_idx += 1 
                    continue 
            else: 
                if not processed_any_valid_date_header and line: 
                    errors.append(f"第{line_number_for_report}行错误: 文件应以 'Date:YYYYMMDD' 格式的行开始。当前行为: '{line[:50]}...'")
                    processed_any_valid_date_header = True 
                elif line : 
                    errors.append(f"第{line_number_for_report}行错误: 意外的内容，此处应为新的 'Date:' 块。内容: '{line[:50]}...'")
                current_line_idx += 1 
        return errors

def handle_file_processing_and_reporting(file_processor: FileProcessor):
    """
    Handles user input for file path, calls validation using the file_processor, 
    reports results, and times the process.
    """
    process_start_time = None 
    try:
        file_path = input("请输入文本文件的路径:")
        process_start_time = time.perf_counter()

        validation_errors = file_processor.process_and_validate_file_contents(file_path)

        if validation_errors is None:
            # File reading error occurred; message already printed by process_and_validate_file_contents.
            pass
        elif validation_errors: # Errors were found during validation
            print("\n发现以下错误:")
            # Sort errors by line number for readability
            unique_errors = sorted(list(set(validation_errors)), key=lambda x: int(re.search(r'第(\d+)行', x).group(1)) if re.search(r'第(\d+)行', x) else 0)
            for error in unique_errors:
                print(f"\n{error}")
        else: # No errors found (validation_errors is an empty list)
            print("\n文件格式完全正确！")

    except Exception as e: # Catches errors from input() or other unexpected issues
        print(f"\n程序执行过程中发生致命错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        process_end_time = time.perf_counter()
        if process_start_time is not None: # Check if timing actually started
            print(f"\n处理时间:{process_end_time - process_start_time:.6f}秒")
        else:
            print(f"\n处理时间: 无法计算 (计时可能未开始或过早出错)")

def main():
    """
    Main function to run the script.
    Initializes necessary components and starts the file processing workflow.
    """
    config_manager = ConfigManager(CONFIG_FILE_PATH)
    if not config_manager.load():
        # Config loading failed. Messages are printed by ConfigManager.
        # The application will proceed with default (empty) configurations
        # as ConfigManager attributes are initialized to empty.
        print("警告: 配置加载失败或文件未找到。程序将继续，但某些校验规则可能无法应用。")
    
    line_validator = LineValidator(config_manager)
    file_processor = FileProcessor(line_validator)

    handle_file_processing_and_reporting(file_processor)

if __name__ == "__main__":
    main()
