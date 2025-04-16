import os

#定义文本对应的翻译字典
EVENT_TRANSLATION_MAP = {
    "吃饭短": "meal_short",
    "吃饭中": "meal_medium",
    "吃饭长": "meal_long",
    
    "抖音": "recreation_douyin",
    "守望先锋":"recreation_game_overwatch",
    "mix":"recreation_mix",
    

}

# 用于把快速记录的时间转换成时间段
def format_time(time_str):
  """将 HHMM 格式的字符串转换为 HH:MM 格式"""
  if len(time_str) == 4 and time_str.isdigit():
    return f"{time_str[:2]}:{time_str[2:]}"
  else:
    # 如果格式不正确，返回 None 以便后续检查
    print(f"警告：发现无效的时间格式 '{time_str}'")
    return None # 返回 None 更清晰地表示失败

def process_log_file(input_filepath):
  """
  读取日志文件，将时间戳转换为时间段，检查时间顺序，翻译事件，并打印结果。
  """
  output_lines = []
  lines_read_successfully = False # 标记是否成功读取了行
  lines = [] # 初始化为空列表

  try:
    # 尝试使用 utf-8 打开文件
    with open(input_filepath, 'r', encoding='utf-8') as infile:
      lines = [line.strip() for line in infile if line.strip()] # 读取所有非空行并去除首尾空白
      lines_read_successfully = True
  except FileNotFoundError:
    print(f"错误：文件 '{input_filepath}' 未找到。")
    return
  except UnicodeDecodeError:
    # 如果 utf-8 解码失败，尝试 gbk 编码
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

  # 只有在成功读取行后才继续处理
  if not lines_read_successfully:
      return # 如果读取失败，则退出函数

  if len(lines) < 2:
    print("文件中至少需要两行数据才能生成时间段。")
    return

  print("\n开始处理文件内容")
  # 遍历从第一行到倒数第二行
  for i in range(len(lines) - 1):
    current_line = lines[i]
    next_line = lines[i+1]

    # 1. 基本格式检查
    is_current_valid = len(current_line) >= 4 and current_line[:4].isdigit()
    is_next_valid = len(next_line) >= 4 and next_line[:4].isdigit()

    if is_current_valid and is_next_valid:
      # 两个时间格式都基本有效，提取时间
      start_time_str = current_line[:4]
      end_time_str = next_line[:4]
      original_event = next_line[4:] # 事件来自下一行

      # 2. 时间顺序检查 (将 HHMM 视为整数进行比较)
      if int(end_time_str) > int(start_time_str):
        # 时间顺序正确，格式化时间
        formatted_start_time = format_time(start_time_str)
        formatted_end_time = format_time(end_time_str)

        # 确保 format_time 成功返回了格式化后的时间 (不是 None)
        if formatted_start_time and formatted_end_time:
          # --- 新增：进行事件翻译 ---
          # 使用字典的 get 方法：
          # 如果 original_event 在字典中，则返回对应的英文值
          # 如果不在字典中，则返回第二个参数（这里是 original_event 本身）
          translated_event = EVENT_TRANSLATION_MAP.get(original_event, original_event)
          # --- 结束新增 ---

          # 使用翻译后的事件构建输出行
          output_lines.append(f"{formatted_start_time}~{formatted_end_time}{translated_event}")
        else:
             # 如果时间格式化失败，这里可以选择跳过或记录错误
             # format_time 函数内部已经打印了警告，这里不再重复打印
             pass # 跳过这个时间段的生成

      else:
        # 时间顺序错误，打印警告
        # 尝试格式化时间以用于警告信息，如果失败则使用原始字符串
        formatted_start_time_warn = format_time(start_time_str) or start_time_str
        formatted_end_time_warn = format_time(end_time_str) or end_time_str
        print(f"警告：时间顺序错误。第 {i+2} 行的时间 '{formatted_end_time_warn}' ({end_time_str}) "
              f"不大于 第 {i+1} 行的时间 '{formatted_start_time_warn}' ({start_time_str})。已跳过此时间段的生成。")

    else:
      # 打印基本格式的警告信息
      if not is_current_valid:
        print(f"警告：跳过。第 {i+1} 行格式不符合 'HHMM[事件]':'{current_line}'")
      # 即使当前行有效，下一行也可能无效，影响这个配对
      if not is_next_valid:
         print(f"警告：跳过。第 {i+2} 行格式不符合 'HHMM[事件]':'{next_line}'")

  # 打印最终处理结果
  print("\n处理结果:")
  if not output_lines:
      print("（没有生成有效的时间段）")
  else:
      for line in output_lines:
          print(line)


if __name__ == "__main__":
  while True:
    file_path = input("请输入 txt 文件的完整路径 (或输入 'q' 退出): ")
    if file_path.lower() == 'q':
        break
    # 检查用户输入的路径是否存在
    if os.path.exists(file_path) and os.path.isfile(file_path):
      process_log_file(file_path)
      # 处理完一个文件后可以选择退出或继续处理其他文件
      break
    else:
      print(f"错误：路径 '{file_path}' 不存在或不是一个文件，请重新输入。")

  print("\n程序结束。")
