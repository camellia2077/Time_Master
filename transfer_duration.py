import sys

# ANSI escape codes for colors
GREEN = "\033[92m"
RESET = "\033[0m"

# 新增的替换字典
# 您可以在这里添加更多的替换规则
TEXT_REPLACEMENT_MAP = {
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
    "洗漱" : "routine_grooming",
    "拉屎" : "routine_toilet",

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
def format_time(time_str):
    """Converts a 'HHMM' time string to 'HH:MM' format."""
    if len(time_str) == 4 and time_str.isdigit():
        return f"{time_str[:2]}:{time_str[2:]}"
    return time_str

def process_log_data(log_data_str):
    """
    Processes the structured log data string and prints the formatted output,
    including text replacement and blank lines between date blocks.
    """
    lines = log_data_str.strip().split('\n')

    last_interval_start_raw_time = None
    was_previous_event_initial_raw_xing = False
    # 标志位，用于判断是否是第一个日期块，以便在其后添加空行
    is_not_first_date_block = False 

    for line_content in lines:
        line = line_content.strip()
        if not line:
            continue

        if line.isdigit() and len(line) == 3: # Date line
            if is_not_first_date_block:
                print() # 在非第一个日期块之前打印一个空行作为分隔
            
            print(f"{GREEN}{line}{RESET}")
            is_not_first_date_block = True # 标记已处理过至少一个日期块的头部

            # Reset state for the new date block
            last_interval_start_raw_time = None
            was_previous_event_initial_raw_xing = False
        else: # Event line
            if len(line) < 4 or not line[:4].isdigit():
                continue

            raw_time = line[:4]
            original_text = line[4:]
            current_formatted_time = format_time(raw_time)
            display_text = TEXT_REPLACEMENT_MAP.get(original_text, original_text)

            if last_interval_start_raw_time is None: # First event in this date block
                if original_text == "醒":
                    print(f"{raw_time}{display_text}")
                    was_previous_event_initial_raw_xing = True
                    last_interval_start_raw_time = raw_time
                elif original_text == "起床":
                    print(f"{current_formatted_time}{display_text}")
                    last_interval_start_raw_time = raw_time
                    was_previous_event_initial_raw_xing = False
                else: # Other first event
                    print(f"{current_formatted_time}{display_text}")
                    last_interval_start_raw_time = raw_time
                    was_previous_event_initial_raw_xing = False
            else: # Not the first event in the block
                if was_previous_event_initial_raw_xing:
                    print(f"{current_formatted_time}~{current_formatted_time}{display_text}")
                    last_interval_start_raw_time = raw_time
                    was_previous_event_initial_raw_xing = False
                else:
                    start_formatted_time = format_time(last_interval_start_raw_time)
                    print(f"{start_formatted_time}~{current_formatted_time}{display_text}")
                    last_interval_start_raw_time = raw_time
    
    # (可选) 如果需要在整个输出的最后也添加一个空行，即使后面没有更多日期
    # if is_not_first_date_block: # 确保至少处理了一些内容
    #     print() # 这会确保在所有内容之后有一个空行

if __name__ == '__main__':
    file_path = input("请输入txt文件名: ")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            input_data = file.read()
        process_log_data(input_data)
    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 未找到。", file=sys.stderr)
    except Exception as e:
        print(f"处理文件时发生错误: {e}", file=sys.stderr)
