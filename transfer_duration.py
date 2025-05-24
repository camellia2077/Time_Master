import os

# 读取日志文件，将时间戳转换为时间段，检查时间顺序，翻译事件，并打印结果
# 定义文本对应的翻译字典
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
RESET = '\033[0m'   # 重置颜色

# 用于把快速记录的时间转换成时间段
def format_time(time_str):
    """将 HHMM 格式的字符串转换为 HH:MM 格式"""
    if len(time_str) == 4 and time_str.isdigit():
        return f"{time_str[:2]}:{time_str[2:]}"
    else:
        # 如果格式不正确，返回 None 以便后续检查
        print(f"警告：发现无效的时间格式 '{time_str}'\n")
        return None  # 返回 None 更清晰地表示失败

def process_log_file(input_filepath):
    """
    读取日志文件，将时间戳转换为时间段，检查时间顺序，翻译事件，并打印结果。
    新增功能：保留日期行（绿色显示并在其前加空行），保留包含“醒”或“起床”的行。
    """
    output_lines = []
    lines_read_successfully = False
    lines = []
    try:
        with open(input_filepath, 'r', encoding='utf-8') as infile:
            lines = [line.strip() for line in infile if line.strip()]
            lines_read_successfully = True
    except FileNotFoundError:
        print(f"错误：文件 '{input_filepath}' 未找到。")
        return
    except UnicodeDecodeError:
        try:
            print("尝试使用 GBK 编码重新读取文件...")
            with open(input_filepath, 'r', encoding='gbk') as infile:
                lines = [line.strip() for line in infile if line.strip()]
                lines_read_successfully = True
        except Exception as e:
            print(f"错误：读取文件时出错（尝试了 UTF-8 和 GBK):{e}")
            return
    except Exception as e:
        print(f"读取文件时发生未知错误：{e}")
        return

    if not lines_read_successfully:
        return

    if not lines: # 如果文件为空或只有空行
        print("文件中没有可处理的内容。")
        # return # 根据需要决定是否在此处返回

    print("\n开始处理文件内容")

    idx = 0
    while idx < len(lines):
        current_line = lines[idx]
        line_number = idx + 1

        # --- 新增功能：处理日期行 ---
        is_date_line = current_line.isdigit() and (len(current_line) in [2, 3, 4])
        if is_date_line:
            # 如果 output_lines 不为空，则在日期前添加一个空行用于分隔
            if output_lines:
                output_lines.append("")
            output_lines.append(current_line) # 日期本身会被加入，打印时再着色
            idx += 1
            continue

        # --- 新增功能：处理包含“醒”或“起床”的行 ---
        if "醒" in current_line or "起床" in current_line:
            output_lines.append(current_line)
            idx += 1
            continue

        # --- 原有逻辑：处理时间段 ---
        if idx + 1 < len(lines):
            next_line = lines[idx+1]
            next_line_number = idx + 2

            is_next_line_date = next_line.isdigit() and (len(next_line) in [2, 3, 4])
            is_next_line_keyword = "醒" in next_line or "起床" in next_line

            if is_next_line_date or is_next_line_keyword:
                if len(current_line) >= 4 and current_line[:4].isdigit():
                    print(f"信息：行 {line_number} ('{current_line}') 无法与后续的特殊行 {next_line_number} ('{next_line}') 形成时间段。该行 '{current_line}' 将被跳过。")
                idx += 1
                continue

            is_current_valid_for_period = len(current_line) >= 4 and current_line[:4].isdigit()
            is_next_valid_for_period = len(next_line) >= 4 and next_line[:4].isdigit()

            if is_current_valid_for_period and is_next_valid_for_period:
                start_time_str = current_line[:4]
                end_time_str = next_line[:4]
                original_event = next_line[4:]

                # 检查时间字符串是否可以安全地转换为整数
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
                        print(f"警告：时间顺序错误。行 {next_line_number} ('{next_line}') 的时间 '{formatted_end_time_warn}' ({end_time_str}) "
                              f"不大于行 {line_number} ('{current_line}') 的时间 '{formatted_start_time_warn}' ({start_time_str})。已跳过此时间段的生成。")
                else:
                    # 如果时间字符串不是纯数字（理论上被 is_current_valid_for_period 等检查覆盖，但作为额外保险）
                    print(f"警告：行 {line_number} ('{current_line}') 或行 {next_line_number} ('{next_line}') 包含无效的时间数字格式。")

            else:
                if not is_current_valid_for_period:
                    print(f"警告：行 {line_number} ('{current_line}') 格式不符合 'HHMM[事件]' 作为时间段起始。")
                if not is_next_valid_for_period:
                    print(f"警告：行 {next_line_number} ('{next_line}') 格式不符合 'HHMM[事件]' 作为时间段结束。")
            
            idx += 1
        
        else:
            if len(current_line) > 0:
                if len(current_line) >= 4 and current_line[:4].isdigit():
                    print(f"信息：文件末尾行 {line_number} ('{current_line}') 无法形成时间段，将被忽略。")
                else:
                    print(f"信息：文件末尾行 {line_number} ('{current_line}') 非特殊格式且无法形成时间段，将被忽略。")
            idx += 1

    # 打印最终处理结果
    print("\n处理结果:")
    if not output_lines:
        print("（没有生成任何输出行）")
    else:
        for line_to_print in output_lines:
            # 检查此行是否为之前存入的日期（纯数字且特定长度）
            # 空字符串 "" 用于产生空行，它不是日期
            if line_to_print.isdigit() and (len(line_to_print) in [2, 3, 4]):
                print(f"{GREEN}{line_to_print}{RESET}")
            else:
                print(line_to_print) # 其他行（包括空行 ""）正常打印

if __name__ == "__main__":
    while True:
        file_path = input("请输入 txt 文件的完整路径 (或输入 'q' 退出): ")
        if file_path.lower() == 'q':
            break
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            process_log_file(file_path)
        else:
            print(f"错误：路径 '{file_path}' 不存在或不是一个文件，请重新输入。")
    print("\n程序结束。")
