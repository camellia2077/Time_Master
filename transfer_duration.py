import sys

# ANSI escape codes for colors
GREEN = "\033[92m"
RESET = "\033[0m"

def format_time(time_str):
    """Converts a 'HHMM' time string to 'HH:MM' format."""
    if len(time_str) == 4 and time_str.isdigit():
        return f"{time_str[:2]}:{time_str[2:]}"
    # Fallback for any unexpected time format, though input implies 'HHMM'.
    return time_str

def process_log_data(log_data_str):
    """
    Processes the structured log data string and prints the formatted output.
    """
    lines = log_data_str.strip().split('\n')

    last_interval_start_raw_time = None
    # Flag to indicate if the previous event was an initial "醒" printed raw.
    was_previous_event_initial_raw_xing = False

    for line_content in lines:
        line = line_content.strip()
        if not line:
            continue

        # Check if the line is a date (assumed to be 3 digits as per example)
        if line.isdigit() and len(line) == 3:
            print(f"{GREEN}{line}{RESET}")
            # Reset state for the new date block
            last_interval_start_raw_time = None
            was_previous_event_initial_raw_xing = False
        else: # Event line (e.g., "1523醒")
            # Basic validation for event line format
            if len(line) < 4 or not line[:4].isdigit():
                # Skipping malformed lines or handle as an error appropriately
                # print(f"Warning: Skipping malformed event line: {line}", file=sys.stderr)
                continue

            raw_time = line[:4]
            text = line[4:]
            current_formatted_time = format_time(raw_time)

            if last_interval_start_raw_time is None:
                # This is the first event in this date block
                if text == "醒":
                    # Per example ("415" -> "1523醒"), the first "醒" is printed with raw time.
                    print(f"{raw_time}{text}")
                    was_previous_event_initial_raw_xing = True # Mark that initial "醒" occurred.
                    last_interval_start_raw_time = raw_time
                elif text == "起床":
                    # Per example ("416" -> "0802起床"), "起床" is printed with formatted time.
                    print(f"{current_formatted_time}{text}")
                    last_interval_start_raw_time = raw_time
                    # "起床" does not trigger the new special handling for the next line.
                    was_previous_event_initial_raw_xing = False
                else:
                    # Case: First event is neither "醒" nor "起床".
                    # Example does not cover this. Defaulting to print it as a point event.
                    # Its time will be the start for the next interval.
                    print(f"{current_formatted_time}{text}")
                    last_interval_start_raw_time = raw_time
                    was_previous_event_initial_raw_xing = False
            else:
                # Not the first event in the block
                if was_previous_event_initial_raw_xing:
                    # This event immediately follows an initial raw "醒".
                    # Print it as a zero-duration interval using its own text.
                    # e.g., "1523醒" was previous, current is "1536mix".
                    # Output: "15:36~15:36mix"
                    print(f"{current_formatted_time}~{current_formatted_time}{text}")
                    
                    last_interval_start_raw_time = raw_time
                    was_previous_event_initial_raw_xing = False # This special condition is now handled.
                
                else:
                    # This is a standard interval: StartPrevFormatted~EndCurrentFormatted TextCurrent
                    # (Or it follows "起床" or another non-initial-raw-"醒" event)
                    start_formatted_time = format_time(last_interval_start_raw_time)
                    print(f"{start_formatted_time}~{current_formatted_time}{text}")
                    last_interval_start_raw_time = raw_time # Current event's time is start for the next.
                    # was_previous_event_initial_raw_xing remains False

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
