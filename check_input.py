import re
import time
import json # 导入 json 模块
import os   # 导入 os 模块，用于检查文件是否存在

# 全局变量，将由加载的配置填充
PARENT_CATEGORIES = {}
DISALLOWED_STANDALONE_CATEGORIES = set()

CONFIG_FILE_PATH = "check_input_config.json" # 定义配置文件的路径

def load_app_config(file_path):
    """从JSON文件加载配置并初始化全局配置变量"""
    global PARENT_CATEGORIES, DISALLOWED_STANDALONE_CATEGORIES

    if not os.path.exists(file_path):
        print(f"错误: 配置文件 '{file_path}' 未找到。程序将使用空配置退出。")
        PARENT_CATEGORIES = {}
        DISALLOWED_STANDALONE_CATEGORIES = set()
        return False # 表示加载失败

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"错误: 解析配置文件 '{file_path}' 失败: {e}。程序将使用空配置退出。")
        PARENT_CATEGORIES = {}
        DISALLOWED_STANDALONE_CATEGORIES = set()
        return False # 表示加载失败
    except Exception as e:
        print(f"读取配置文件 '{file_path}' 时发生未知错误: {e}。程序将使用空配置退出。")
        PARENT_CATEGORIES = {}
        DISALLOWED_STANDALONE_CATEGORIES = set()
        return False # 表示加载失败

    parent_categories_from_json = config_data.get("PARENT_CATEGORIES", {})
    
    loaded_parent_categories_temp = {}
    for category, labels_list in parent_categories_from_json.items():
        if isinstance(labels_list, list):
            loaded_parent_categories_temp[category] = set(labels_list)
        else:
            print(f"警告: 配置文件中类别 '{category}' 的标签格式不正确 (应为列表)，已忽略此类别。")
            loaded_parent_categories_temp[category] = set()
            
    PARENT_CATEGORIES = loaded_parent_categories_temp
    DISALLOWED_STANDALONE_CATEGORIES = set(PARENT_CATEGORIES.keys())
    print(f"配置已从 '{file_path}' 加载。")
    return True # 表示加载成功

def validate_time(time_str):
    try:
        hh, mm = time_str.split(':')
        if len(hh) != 2 or len(mm) != 2:
            return False
        if 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59:
            return True
        return False
    except ValueError:
        return False

def check_date_line(line, line_num, errors):
    if not line.startswith('Date:'):
        errors.append(f"第{line_num}行错误:Date行缺少冒号")
        return False
    elif not re.fullmatch(r'Date:\d{8}', line):
        errors.append(f"第{line_num}行错误:Date格式应为YYYYMMDD")
        return False
    return True

def check_status_line(line, line_num, errors):
    if not re.fullmatch(r'Status:(True|False)', line):
        errors.append(f"第{line_num}行错误:Status必须为True或False")

def check_getup_line(line, line_num, errors):
    if not re.fullmatch(r'Getup:\d{2}:\d{2}', line): 
        errors.append(f"第{line_num}行错误:Getup时间格式不正确 (应为 Getup:HH:MM)")
    else:
        time_part = line[6:] 
        if not validate_time(time_part):
            errors.append(f"第{line_num}行错误:Getup时间无效 ({time_part})")

def check_remark_line(line, line_num, errors):
    if not line.startswith('Remark:'): 
        errors.append(f"第{line_num}行错误:Remark格式不正确 (应以 'Remark:' 开头)")

def check_time_line(line, line_num, errors):
    match = re.match(r'^(\d{2}:\d{2})~(\d{2}:\d{2})([a-zA-Z0-9_-]+)$', line)
    if not match:
        errors.append(f"第{line_num}行错误:时间行格式错误 (应为 HH:MM~HH:MM文本内容)")
        return

    start_time_str, end_time_str, activity_label = match.groups()
    error_added_for_label_check = False 

    if activity_label in DISALLOWED_STANDALONE_CATEGORIES:
        errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 为父级类别，不够具体，不能单独使用。")
        error_added_for_label_check = True
    else:
        found_matching_category = False
        for parent_category, allowed_children in PARENT_CATEGORIES.items():
            if activity_label.startswith(parent_category + "_"):
                found_matching_category = True
                if activity_label not in allowed_children:
                    errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 在类别 '{parent_category}' 中无效。允许的 '{parent_category}' 内容例如: {', '.join(sorted(list(allowed_children))[:3])} 等。")
                    error_added_for_label_check = True
                break 

        if not found_matching_category and not error_added_for_label_check:
            all_examples = []
            for children in PARENT_CATEGORIES.values():
                all_examples.extend(list(children))
            if all_examples: 
                errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。它不属于任何已定义的类别 (如 'code_', 'routine_') 或并非这些类别下允许的具体活动。允许的具体活动例如: {', '.join(sorted(all_examples)[:3])} 等。")
            else: 
                errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。没有定义允许的活动类别。")

    start_valid = validate_time(start_time_str)
    end_valid = validate_time(end_time_str)

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

def process_file_and_validate(file_path):
    """
    Reads and validates the content of the given file according to predefined rules.

    Args:
        file_path (str): The path to the text file to be validated.

    Returns:
        list: A list of error messages. Returns an empty list if the file is valid.
              Returns None if the file cannot be read (e.g., FileNotFoundError).
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
            is_date_line_structurally_valid = check_date_line(line, line_number_for_report, errors)

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
                        check_status_line(current_header_line, header_line_number_for_report, errors)
                    elif header_name == 'Getup':
                        check_getup_line(current_header_line, header_line_number_for_report, errors)
                    elif header_name == 'Remark':
                        check_remark_line(current_header_line, header_line_number_for_report, errors)
                
                if header_check_ok:
                    current_line_idx += 1  
                    while current_line_idx < total_lines and (not lines[current_line_idx].startswith('Date:')):
                        time_line_number_for_report = current_line_idx + 1
                        time_line = lines[current_line_idx]
                        if time_line: 
                            check_time_line(time_line, time_line_number_for_report, errors)
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

def handle_file_processing_and_reporting():
    """
    Handles user input for file path, calls validation, reports results, and times the process.
    """
    process_start_time = None 
    try:
        file_path = input("请输入文本文件的路径:")
        process_start_time = time.perf_counter()

        validation_errors = process_file_and_validate(file_path)

        if validation_errors is None:
            # File reading error occurred; message already printed by process_file_and_validate.
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
    Loads application configuration and then handles file processing and reporting.
    """
    if not load_app_config(CONFIG_FILE_PATH):
        # Configuration loading failed. The load_app_config function already printed an error.
        # Depending on requirements, you might want to exit here or allow proceeding with empty config.
        # Current script behavior is to proceed (pass).
        pass

    handle_file_processing_and_reporting()

if __name__ == "__main__":
    main()
