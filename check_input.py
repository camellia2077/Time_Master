import re
import time
import json # 导入 json 模块
import os   # 导入 os 模块，用于检查文件是否存在


class Colors:
    GREEN = '\033[92m'  # 亮绿色
    RED = '\033[91m'    # 亮红色
    # YELLOW = '\033[93m' # 亮黄色 (如果需要用于警告)
    RESET = '\033[0m'   # 重置颜色

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
                loaded_parent_categories_temp[category] = set()

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
    def __init__(self, line_validator: 'LineValidator'): # Forward reference LineValidator if defined later
        self.validator = line_validator

    def process_and_validate_file_contents(self, file_path):
        errors = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            return None # Indicates file reading error
        except Exception as e:
            # print(f"读取文件 '{file_path}' 时发生错误: {e}") # Debugging, handled by caller
            return None # Indicates file reading error

        current_outer_line_idx = 0 # Index for the main loop iterating through Date blocks
        total_lines = len(lines)
        processed_any_valid_date_header = False

        while current_outer_line_idx < total_lines:
            line_number_for_report = current_outer_line_idx + 1
            line_content_current_outer = lines[current_outer_line_idx]

            if not line_content_current_outer: # Skip empty lines between Date blocks
                current_outer_line_idx += 1
                continue

            if line_content_current_outer.startswith('Date:'):
                processed_any_valid_date_header = True
                date_block_start_actual_line_num = line_number_for_report
                
                is_date_line_valid = self.validator.check_date_line(line_content_current_outer, date_block_start_actual_line_num, errors)
                if not is_date_line_valid:
                    # Date line is bad, try to find next Date or EOF
                    idx_after_bad_date = current_outer_line_idx + 1
                    while idx_after_bad_date < total_lines and \
                          (not lines[idx_after_bad_date].startswith('Date:') if lines[idx_after_bad_date] else True): # Skip empty lines too
                        idx_after_bad_date += 1
                    current_outer_line_idx = idx_after_bad_date
                    continue # To the next iteration of the main while loop

                # Date line is structurally valid, proceed with this block
                status_line_content_for_day = None
                status_line_number_for_day = -1
                day_contains_study_activity = False
                
                # --- Header Processing ---
                # Expected headers relative to the Date line
                # Date line is at current_outer_line_idx
                # Status should be at current_outer_line_idx + 1
                # Getup should be at current_outer_line_idx + 2
                # Remark should be at current_outer_line_idx + 3
                
                headers_structurally_present = True # Assume headers are present initially

                # Status Header
                status_idx_in_lines = current_outer_line_idx + 1
                if status_idx_in_lines >= total_lines:
                    errors.append(f"文件在第{date_block_start_actual_line_num}行的Date块后意外结束，缺少 Status 行。")
                    headers_structurally_present = False
                else:
                    status_line_content_for_day = lines[status_idx_in_lines]
                    status_line_number_for_day = status_idx_in_lines + 1
                    if not status_line_content_for_day.startswith("Status:"):
                        errors.append(f"第{status_line_number_for_day}行错误:应为 'Status:' 开头，实际为 '{status_line_content_for_day[:30]}...'")
                        # Note: check_status_line will also report if format is wrong (e.g. Status:true instead of Status:True)
                    self.validator.check_status_line(status_line_content_for_day, status_line_number_for_day, errors)

                # Getup Header (only check if previous was considered present for structure)
                getup_idx_in_lines = current_outer_line_idx + 2
                if headers_structurally_present: # Check this flag before proceeding to next header
                    if getup_idx_in_lines >= total_lines:
                        errors.append(f"文件在第{date_block_start_actual_line_num}行的Date块后意外结束，缺少 Getup 行。")
                        headers_structurally_present = False
                    else:
                        getup_line_content = lines[getup_idx_in_lines]
                        getup_line_number = getup_idx_in_lines + 1
                        if not getup_line_content.startswith("Getup:"):
                            errors.append(f"第{getup_line_number}行错误:应为 'Getup:' 开头，实际为 '{getup_line_content[:30]}...'")
                        self.validator.check_getup_line(getup_line_content, getup_line_number, errors)
                
                # Remark Header
                remark_idx_in_lines = current_outer_line_idx + 3
                if headers_structurally_present:
                    if remark_idx_in_lines >= total_lines:
                        errors.append(f"文件在第{date_block_start_actual_line_num}行的Date块后意外结束，缺少 Remark 行。")
                        headers_structurally_present = False
                    else:
                        remark_line_content = lines[remark_idx_in_lines]
                        remark_line_number = remark_idx_in_lines + 1
                        if not remark_line_content.startswith("Remark:"):
                            errors.append(f"第{remark_line_number}行错误:应为 'Remark:' 开头，实际为 '{remark_line_content[:30]}...'")
                        self.validator.check_remark_line(remark_line_content, remark_line_number, errors)

                # If headers were not structurally present (e.g., file ended prematurely), skip to next Date block
                if not headers_structurally_present:
                    idx_scanner = current_outer_line_idx + 1
                    while idx_scanner < total_lines and \
                          (not lines[idx_scanner].startswith('Date:') if lines[idx_scanner] else True):
                        idx_scanner += 1
                    current_outer_line_idx = idx_scanner
                    continue

                # --- Activity Line Processing (if headers were structurally present) ---
                first_activity_line_idx_in_lines = current_outer_line_idx + 4 # Line after Date, Status, Getup, Remark
                
                current_activity_processing_idx = first_activity_line_idx_in_lines
                activity_lines_data_for_validation = [] # Store {'content': ..., 'num': ...}

                while current_activity_processing_idx < total_lines and \
                      (not lines[current_activity_processing_idx].startswith('Date:')):
                    
                    activity_content = lines[current_activity_processing_idx]
                    activity_num = current_activity_processing_idx + 1

                    if activity_content: # Only process non-empty lines as activity lines
                        activity_lines_data_for_validation.append({'content': activity_content, 'num': activity_num})
                        
                        # For "study" check, extract text part from activity line
                        # Format is HH:MM~HH:MMtext
                        match = re.match(r'^\d{2}:\d{2}~\d{2}:\d{2}(.*)$', activity_content)
                        if match:
                            activity_text_part = match.group(1)
                            if "study" in activity_text_part: # Case-sensitive "study"
                                day_contains_study_activity = True
                    
                    current_activity_processing_idx += 1
                
                # Apply the new "study"-based Status rule
                if status_line_content_for_day is not None and status_line_number_for_day != -1:
                    # Check if Status line has a valid True/False format first
                    actual_status_match = re.fullmatch(r'Status:(True|False)', status_line_content_for_day)
                    if actual_status_match:
                        actual_status_bool = actual_status_match.group(1) == "True"
                        expected_status_bool = day_contains_study_activity

                        if actual_status_bool != expected_status_bool:
                            reason_verb = "包含" if day_contains_study_activity else "不包含"
                            errors.append(
                                f"第{status_line_number_for_day}行错误: Status应为 Status:{str(expected_status_bool)} (因活动{reason_verb} 'study')，但找到 Status:{actual_status_match.group(1)}。"
                            )
                    # If actual_status_match is None, it means the Status line is malformed (e.g., "Status:Maybe").
                    # This structural error is already caught by self.validator.check_status_line.
                    # The new rule applies only if the Status itself is parseable as True or False.
                
                # Perform original validation on collected activity lines
                for act_line_info in activity_lines_data_for_validation:
                    self.validator.check_time_line(act_line_info['content'], act_line_info['num'], errors)

                # Advance outer_line_idx to the start of the next block (which is current_activity_processing_idx)
                current_outer_line_idx = current_activity_processing_idx
                continue # To the next iteration of the main while loop for Date blocks
                
            else: # Line does not start with 'Date:' (and is not an empty line skipped at the beginning of the loop)
                if not processed_any_valid_date_header and line_content_current_outer: # Must be non-empty to trigger this
                    errors.append(f"第{line_number_for_report}行错误: 文件应以 'Date:YYYYMMDD' 格式的行开始。当前行为: '{line_content_current_outer[:50]}...'")
                    processed_any_valid_date_header = True # Avoid repeating this for every leading non-Date line
                    
                    # Consume lines until the next 'Date:' or EOF
                    idx_scanner = current_outer_line_idx + 1
                    while idx_scanner < total_lines and \
                          (not lines[idx_scanner].startswith('Date:') if lines[idx_scanner] else True):
                        idx_scanner += 1
                    current_outer_line_idx = idx_scanner
                    continue

                elif line_content_current_outer: # An unexpected non-empty line when a 'Date:' block was expected
                    errors.append(f"第{line_number_for_report}行错误: 意外的内容，此处应为新的 'Date:' 块。内容: '{line_content_current_outer[:50]}...'")
                    idx_scanner = current_outer_line_idx + 1
                    while idx_scanner < total_lines and \
                          (not lines[idx_scanner].startswith('Date:') if lines[idx_scanner] else True):
                        idx_scanner += 1
                    current_outer_line_idx = idx_scanner
                    continue
                else: 
                    # This case should ideally not be reached if initial `if not line_content_current_outer:` handles it.
                    # As a safeguard, advance index if it's an empty line that somehow got here.
                    current_outer_line_idx += 1


        # Final check if no Date blocks were found at all but the file had content
        if not processed_any_valid_date_header and any(l.strip() for l in lines):
            is_first_line_error_present = any("文件应以 'Date:YYYYMMDD' 格式的行开始" in err for err in errors)
            if not is_first_line_error_present:
                 errors.append(f"错误: 文件不包含任何以 'Date:YYYYMMDD' 开头的有效数据块。")
        
        return errors

def handle_file_processing_and_reporting(file_processor: FileProcessor):
    """
    Handles user input for file or directory path, validates content, reports results, and times processes.
    Returns False to signal program exit, True to continue.
    """
    try:
        user_input_str = input("请输入文本文件路径或目录路径 (或输入 'q' 退出): ")
        if user_input_str.lower() == 'q':
            return False

        if not user_input_str:
            print("未输入路径。请重新输入。")
            return True

        files_to_process = []
        is_directory_scan = False

        if not os.path.exists(user_input_str):
            print(f"错误: 路径 '{user_input_str}' 不存在。")
            return True

        if os.path.isdir(user_input_str):
            is_directory_scan = True
            print(f"\n{Colors.GREEN}正在递归扫描目录 '{user_input_str}' 及其所有子目录...{Colors.RESET}") # 更新提示信息
            for dirpath, dirnames, filenames in os.walk(user_input_str):
                for filename in filenames:
                    if filename.lower().endswith(".txt"):
                        full_path = os.path.join(dirpath, filename)
                        files_to_process.append(full_path)
            
            if not files_to_process:
                print(f"在目录 '{user_input_str}' 及其子目录中未找到 .txt 文件。")
                return True
            else:
                print(f"\n在目录 '{user_input_str}' 及其子目录中找到 {len(files_to_process)} 个 .txt 文件准备处理。")

        elif os.path.isfile(user_input_str):
            if user_input_str.lower().endswith(".txt"):
                files_to_process.append(user_input_str)
            else:
                print(f"错误: 文件 '{user_input_str}' 不是一个 .txt 文件。")
                return True
        else:
            print(f"错误: 路径 '{user_input_str}' 不是一个有效的文件或目录。")
            return True
        
        batch_overall_start_time = time.perf_counter()
        total_files_in_batch = len(files_to_process)
        files_processed_count = 0
        files_with_errors_count_in_batch = 0 

        for i, current_file_path in enumerate(files_to_process):
            file_process_start_time = time.perf_counter()
            
            validation_errors = file_processor.process_and_validate_file_contents(current_file_path)
            files_processed_count += 1

            current_file_has_errors = False
            if validation_errors is None: 
                files_with_errors_count_in_batch += 1
                current_file_has_errors = True
            elif validation_errors: 
                files_with_errors_count_in_batch += 1
                current_file_has_errors = True
            
            indicator_color = Colors.RED if current_file_has_errors else Colors.GREEN
            progress_indicator = f"[{i+1}/{total_files_in_batch}]"
            # 打印文件路径时，考虑相对路径或仅文件名，如果完整路径太长
            # simplified_path = os.path.relpath(current_file_path, user_input_str) if is_directory_scan and current_file_path.startswith(os.path.abspath(user_input_str)) else current_file_path
            # print(f"\n{indicator_color}{progress_indicator}{Colors.RESET} 开始处理文件: {simplified_path}")
            print(f"\n{indicator_color}{progress_indicator}{Colors.RESET} 开始处理文件: {current_file_path}")


            if validation_errors is None:
                 print(f"注意: 文件 '{current_file_path}' 读取失败或无法访问。")
            elif validation_errors:
                print(f"文件 '{current_file_path}' 发现以下错误:")
                unique_errors = sorted(list(set(validation_errors)), key=lambda x: int(re.search(r'第(\d+)行', x).group(1)) if re.search(r'第(\d+)行', x) else 0)
                for error in unique_errors:
                    print(f"  {error}")
            else: 
                print(f"文件 '{current_file_path}' 格式完全正确！")

            file_process_end_time = time.perf_counter()
            print(f"处理文件 '{current_file_path}' 时间: {file_process_end_time - file_process_start_time:.6f} 秒")
            if i < total_files_in_batch - 1:
                 print("---") 

        if is_directory_scan and files_processed_count > 0:
            batch_overall_end_time = time.perf_counter()
            print("\n--- 目录扫描总结 ---")
            print(f"总共扫描并尝试处理 {files_processed_count} 个 .txt 文件 (在目录 '{user_input_str}' 及其子目录中)。")
            if files_with_errors_count_in_batch > 0:
                print(f"{Colors.RED}其中 {files_with_errors_count_in_batch} 个文件存在格式错误或读取问题。{Colors.RESET}")
            else:
                print(f"{Colors.GREEN}所有扫描到的文件均格式正确。{Colors.RESET}")
            print(f"目录扫描和处理总耗时: {batch_overall_end_time - batch_overall_start_time:.6f} 秒")
        elif not is_directory_scan and files_processed_count == 1 :
             if files_with_errors_count_in_batch > 0:
                 print(f"{Colors.RED}该文件存在错误。{Colors.RESET}")
    
    except EOFError:
        print("\n检测到EOF，程序即将退出。")
        return False
    except KeyboardInterrupt:
        print("\n用户中断，程序即将退出。")
        return False
    except Exception as e:
        print(f"\n程序执行过程中发生致命错误: {e}")
        import traceback
        traceback.print_exc()
    
    return True

def main():
    """
    Main function to run the script.
    """
    config_manager = ConfigManager(CONFIG_FILE_PATH)
    if not config_manager.load():
        print("警告: 配置加载失败或文件未找到。程序将继续，但某些校验规则可能无法应用。")

    line_validator = LineValidator(config_manager)
    file_processor = FileProcessor(line_validator)

    print("欢迎使用TXT文件校验工具。")
    while True:
        print("\n========================================")
        should_continue = handle_file_processing_and_reporting(file_processor)
        if not should_continue:
            break
    print("程序已退出。")

if __name__ == "__main__":
    main()
