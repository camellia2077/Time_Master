import os
EVENT_TRANSLATION_MAP = {
    "word":"study_english_word",
    "单词":"study_english_word",
    "code":"code_time-master",
    #REST
    "rest0":"rest_short",
    "rest1":"rest_medium",
    "rest2":"rest_long",

    #ROUTINE
    "洗澡" : "routine_bath",
    "快递" : "routine_express",

    "短": "meal_short",
    "中": "meal_medium",
    "长": "meal_long",
    "short": "meal_short",
    "medium": "meal_medium",
    "long": "meal_long",

    #RECREATION
    "zh": "recreation_zhihu",
    "知乎": "recreation_zhihu",
    "dy": "recreation_douyin",
    "抖音": "recreation_douyin",
    "守望先锋":"recreation_game_overwatch",
    "bili" : "recreation_bilibili",
    "mix":"recreation_mix",
    "b":"recreation_bilibili",

    #REST
    "撸" : "rest_masturbation",

    "school" : "other_school",

    "有氧" : "exercise_cardio",
    "无氧" : "exercise_anaerobic",
}

# ANSI 转义码用于颜色输出
GREEN = '\033[92m'  # 亮绿色
RED = '\033[91m'    # 亮红色
RESET = '\033[0m'   # 重置颜色

# 用于把快速记录的时间转换成时间段
def format_time(time_str):
    """将 HHMM 格式的字符串转换为 HH:MM 格式"""
    if len(time_str) == 4 and time_str.isdigit():
        return f"{time_str[:2]}:{time_str[2:]}"
    else:
        # 修改点：只将“警告”二字用红色包裹
        print(f"{RED}警告{RESET}：发现无效的时间格式 '{time_str}'\n")
        return None

def process_log_file(input_filepath):
    """
    读取日志文件，将时间戳转换为时间段，检查时间顺序，翻译事件，并打印结果。
    新增功能：保留日期行（绿色显示并在其前加空行），保留包含“醒”或“起床”的行。
    *** 修改：现在会正确报告原始文件的行号 ***
    """
    output_lines = []
    lines_read_successfully = False
    
    # 修改：不再使用简单的 'lines' 列表，而是使用包含 (行号, 内容) 的元组列表
    lines_with_numbers = [] 
    
    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            # 使用 enumerate 来同时获取原始行号（从1开始）和内容
            all_lines = [(i + 1, line.strip()) for i, line in enumerate(infile)]
            # 过滤掉空行，但保留了非空行的原始行号
            lines_with_numbers = [item for item in all_lines if item[1]]
            lines_read_successfully = True
    except FileNotFoundError:
        print(f"错误：文件 '{input_filepath}' 未找到。\n")
        return
    except UnicodeDecodeError:
        try:
            print("尝试使用 GBK 编码重新读取文件...\n")
            with open(input_filepath, 'r', encoding='gbk') as infile:
                all_lines = [(i + 1, line.strip()) for i, line in enumerate(infile)]
                lines_with_numbers = [item for item in all_lines if item[1]]
                lines_read_successfully = True
        except Exception as e:
            print(f"错误：读取文件时出错（尝试了 UTF-8 和 GBK):{e}\n")
            return
    except Exception as e:
        print(f"读取文件时发生未知错误：{e}\n")
        return

    if not lines_read_successfully:
        return

    # 修改：检查新的列表变量
    if not lines_with_numbers:
        print("文件中没有可处理的内容。\n")
        return

    print("\n开始处理文件内容\n")
    print("\n")

    idx = 0
    # 修改：循环遍历新的列表变量
    while idx < len(lines_with_numbers):
        # 修改：从元组中解包，直接获取真实的行号和内容
        line_number, current_line = lines_with_numbers[idx]

        is_date_line = current_line.isdigit() and (len(current_line) in [2, 3, 4])
        if is_date_line:
            if output_lines:
                output_lines.append("")
            output_lines.append(current_line)
            idx += 1
            continue

        if "醒" in current_line or "起床" in current_line:
            output_lines.append(current_line)
            idx += 1
            continue

        # 修改：检查新的列表变量
        if idx + 1 < len(lines_with_numbers):
            # 修改：从元组中解包，直接获取下一行的真实行号和内容
            next_line_number, next_line = lines_with_numbers[idx+1]

            is_next_line_date = next_line.isdigit() and (len(next_line) in [2, 3, 4])
            is_next_line_keyword = "醒" in next_line or "起床" in next_line

            if is_next_line_date or is_next_line_keyword:
                idx += 1 
                continue

            is_current_valid_for_period = len(current_line) >= 4 and current_line[:4].isdigit()
            is_next_valid_for_period = len(next_line) >= 4 and next_line[:4].isdigit()

            if is_current_valid_for_period and is_next_valid_for_period:
                start_time_str = current_line[:4]
                original_event = current_line[4:] 
                end_time_str = next_line[:4]
                
                # 注意：后续所有使用 line_number 和 next_line_number 的 print 语句都无需更改，
                # 因为这两个变量现在已经包含了正确的值。
                if start_time_str.isdigit() and end_time_str.isdigit():
                    if int(end_time_str) > int(start_time_str):
                        formatted_start_time = format_time(start_time_str)
                        formatted_end_time = format_time(end_time_str)
                        if formatted_start_time and formatted_end_time:
                            translated_event = EVENT_TRANSLATION_MAP.get(original_event, original_event)
                            output_lines.append(f"{formatted_start_time}~{formatted_end_time}{translated_event}")
                    else:
                        formatted_start_time_warn = format_time(start_time_str) or start_time_str
                        formatted_end_time_warn = format_time(end_time_str) or end_time_str
                        print(f"{RED}警告{RESET}：时间顺序错误。行 {next_line_number} ('{next_line}') 的时间 '{formatted_end_time_warn}' ({end_time_str}) "
                              f"不大于行 {line_number} ('{current_line}') 的时间 '{formatted_start_time_warn}' ({start_time_str})。已跳过此时间段的生成。\n")
                else:
                    print(f"{RED}警告{RESET}：行 {line_number} ('{current_line}') 或行 {next_line_number} ('{next_line}') 包含无效的时间数字格式。\n")
                idx += 1 
            
            else: 
                if not is_current_valid_for_period:
                    print(f"{RED}警告{RESET}：行 {line_number} ('{current_line}') 格式不符合 'HHMM[事件]' 作为时间段起始。\n")
                if is_current_valid_for_period and not is_next_valid_for_period:
                    print(f"{RED}警告{RESET}：行 {next_line_number} ('{next_line}') 格式不符合 'HHMM[事件]' 作为时间段结束，无法与前有效行形成时间段。\n")
                idx += 1
                continue 

            idx += 1

        else: 
            if len(current_line) > 0:
                if len(current_line) >= 4 and current_line[:4].isdigit():
                    print(f"信息：文件末尾行 {line_number} ('{current_line}') 无法形成时间段，将被忽略。\n")
                else:
                    print(f"信息：文件末尾行 {line_number} ('{current_line}') 非特殊格式且无法形成时间段，将被忽略。\n")
            idx += 1

    print("\n处理结果:")
    if not output_lines:
        print("（没有生成任何输出行）\n")
    else:
        for line_to_print in output_lines:
            if line_to_print.isdigit() and (len(line_to_print) in [2, 3, 4]):
                print(f"{GREEN}{line_to_print}{RESET}")
            else:
                print(line_to_print)

if __name__ == "__main__":
    while True:
        file_path = input("请输入 txt 文件的完整路径 (或输入 'q' 退出): ")
        if file_path.lower() == 'q':
            break
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            process_log_file(file_path)
        else:
            # 错误信息也可以考虑用红色
            print(f"错误：路径 '{file_path}' 不存在或不是一个文件，请重新输入。\n")
    print("\n程序结束。")
