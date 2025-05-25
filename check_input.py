import re
import time
from check_input_config import PARENT_CATEGORIES

# 2. 定义不允许单独作为活动标签的父级类别名称
DISALLOWED_STANDALONE_CATEGORIES = set(PARENT_CATEGORIES.keys()) # 这会自动得到 {"code", "routine"}

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
    if not re.fullmatch(r'Getup:\d{2}:\d{2}', line): # 确保是 Getup:HH:MM
        errors.append(f"第{line_num}行错误:Getup时间格式不正确 (应为 Getup:HH:MM)")
    else:
        time_part = line[6:] # 从 "Getup:" 后提取 "HH:MM"
        if not validate_time(time_part):
            errors.append(f"第{line_num}行错误:Getup时间无效 ({time_part})")

def check_remark_line(line, line_num, errors):
    if not line.startswith('Remark:'): # Remark 行可以为空内容，但必须有 "Remark:" 前缀
        errors.append(f"第{line_num}行错误:Remark格式不正确 (应以 'Remark:' 开头)")

def check_time_line(line, line_num, errors): # 不再需要 labels 参数
    match = re.match(r'^(\d{2}:\d{2})~(\d{2}:\d{2})([a-zA-Z0-9_-]+)$', line)
    if not match:
        errors.append(f"第{line_num}行错误:时间行格式错误 (应为 HH:MM~HH:MM文本内容)")
        return

    start_time_str, end_time_str, activity_label = match.groups()

    # 新的层级化活动标签校验逻辑
    label_is_structurally_valid = False # 标记标签是否通过了层级校验或被判定为无效
    error_added_for_label = False

    if activity_label in DISALLOWED_STANDALONE_CATEGORIES:
        errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 为父级类别，不够具体，不能单独使用。")
        error_added_for_label = True
    else:
        found_matching_category = False
        for parent_category, allowed_children in PARENT_CATEGORIES.items():
            if activity_label.startswith(parent_category + "_"):
                found_matching_category = True
                if activity_label in allowed_children:
                    label_is_structurally_valid = True # 标签有效
                else:
                    errors.append(f"第{line_num}行错误:文本内容 '{activity_label}' 在类别 '{parent_category}' 中无效。允许的 '{parent_category}' 内容例如: {', '.join(sorted(list(allowed_children))[:3])} 等。")
                    error_added_for_label = True
                break # 一旦找到匹配的前缀，就根据该前缀的规则进行判断，不再检查其他父类别

        if not found_matching_category and not error_added_for_label:
            # 如果标签不以任何已定义的父类别前缀开头，则它是无效的
            # (因为要求所有内容都必须来自预定义的类别)
            all_examples = []
            for children in PARENT_CATEGORIES.values():
                all_examples.extend(list(children))
            errors.append(f"第{line_num}行错误:无效的文本内容 '{activity_label}'。它不属于任何已定义的类别 (如 'code_', 'routine_') 或并非这些类别下允许的具体活动。允许的具体活动例如: {', '.join(sorted(all_examples)[:3])} 等。")
            error_added_for_label = True # 标记错误已添加

    # --- 时间格式和逻辑校验 ---
    start_valid = validate_time(start_time_str)
    end_valid = validate_time(end_time_str)

    if not start_valid:
        errors.append(f"第{line_num}行错误:开始时间值无效 ({start_time_str})")
    if not end_valid:
        errors.append(f"第{line_num}行错误:结束时间值无效 ({end_time_str})")

    if not (start_valid and end_valid): # 如果任一时间无效，则后续比较无意义
        return

    start_h, start_m = map(int, start_time_str.split(':'))
    end_h, end_m = map(int, end_time_str.split(':'))
    if start_h == end_h and end_m < start_m:
        errors.append(f"第{line_num}行错误:当小时相同时，结束时间分钟数({end_m:02d})不应小于开始时间分钟数({start_m:02d})")


def main():
    try:
        errors = []
        file_path = input("请输入文本文件的路径:")
        process_start_time = time.perf_counter() # 移到 try 内部，确保文件操作前计时
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            print(f"错误: 文件 '{file_path}' 未找到。")
            # 在 finally 中处理计时结束，即使这里 return
            process_end_time = time.perf_counter()
            # print(f"\n处理时间:{process_end_time - process_start_time:.6f}秒") # process_start_time 可能未定义
            return
        except Exception as e:
            print(f"读取文件 '{file_path}' 时发生错误: {e}")
            process_end_time = time.perf_counter()
            # print(f"\n处理时间:{process_end_time - process_start_time:.6f}秒")
            return

        current_line_idx = 0
        total_lines = len(lines)
        processed_any_valid_date_header = False # 用于文件开头的非Date行检查

        while current_line_idx < total_lines:
            line_number_for_report = current_line_idx + 1
            line = lines[current_line_idx]

            if not line: # 跳过空行
                current_line_idx += 1
                continue
            
            if line.startswith('Date:'):
                processed_any_valid_date_header = True # 遇到Date行，标记一下
                if check_date_line(line, line_number_for_report, errors):
                    # Date行有效，继续检查后续的 Status, Getup, Remark
                    expected_headers = ['Status', 'Getup', 'Remark']
                    header_check_ok = True
                    for i, header_name in enumerate(expected_headers):
                        current_line_idx += 1 # 移动到预期的头部行
                        header_line_number_for_report = current_line_idx + 1
                        if current_line_idx >= total_lines:
                            errors.append(f"文件在第{line_number_for_report}行的Date块后意外结束，缺少 {header_name} 行。")
                            header_check_ok = False
                            break # 中断头部检查

                        current_header_line = lines[current_line_idx]
                        if not current_header_line.startswith(f"{header_name}:"):
                            errors.append(f"第{header_line_number_for_report}行错误:应为 '{header_name}:' 开头，实际为 '{current_header_line[:30]}...'") # 显示部分内容避免过长
                            header_check_ok = False # 标记头部结构错误
                            # 即使一个头部错误，也尝试定位到下一个预期的头部或时间行开始的位置
                            # 但不再严格依赖后续头部顺序，因为结构已破坏
                            # 此处可以选择直接跳过此Date块的后续内容，或继续尝试解析
                            # 为了简单，我们记录错误，并尝试继续（但可能导致更多连锁错误）
                            continue # 继续检查下一个预期的头部（可能已错位）
                        
                        # 调用对应的检查函数
                        if header_name == 'Status':
                            check_status_line(current_header_line, header_line_number_for_report, errors)
                        elif header_name == 'Getup':
                            check_getup_line(current_header_line, header_line_number_for_report, errors)
                        elif header_name == 'Remark':
                            check_remark_line(current_header_line, header_line_number_for_report, errors)
                    
                    if header_check_ok: # 只有在所有预期头部都至少以正确前缀存在时，才处理时间行
                        current_line_idx += 1 # 移动到时间记录行或下一个Date行
                        while current_line_idx < total_lines and (not lines[current_line_idx].startswith('Date:')):
                            time_line_number_for_report = current_line_idx + 1
                            time_line = lines[current_line_idx]
                            if time_line: # 检查非空的时间行
                                check_time_line(time_line, time_line_number_for_report, errors)
                            current_line_idx += 1
                        continue # Date块的时间行处理完毕（或没有时间行），继续外层while
                    else: # 头部检查中途失败 (如文件提前结束或头部前缀不对)
                        # current_line_idx 此时可能指向错误的头部行或文件末尾
                        # 如果文件未结束，需要确保 current_line_idx 向前推进以避免死循环
                        if current_line_idx < total_lines and not lines[current_line_idx].startswith('Date:'):
                             current_line_idx +=1 # 尝试跳过当前问题行
                        continue # 继续外层循环寻找下一个Date

                else: # Date行本身格式就有问题
                    errors.append(f"第{line_number_for_report}行错误: Date行格式不正确，跳过此Date块的后续内容。")
                    current_line_idx += 1
                    # 跳过此错误Date块的后续内容，直到找到下一个Date或文件末尾
                    while current_line_idx < total_lines and not lines[current_line_idx].startswith('Date:'):
                        current_line_idx += 1
                    continue # 继续外层while循环
            
            else: # 行不是以 'Date:' 开头
                if not processed_any_valid_date_header: # 如果文件开头就不是Date
                     errors.append(f"第{line_number_for_report}行错误: 文件应以 'Date:YYYYMMDD' 格式的行开始。当前行为: '{line[:50]}...'")
                     # 为了避免对后续每一行都报这个错，一旦报过就认为头部问题已知
                     processed_any_valid_date_header = True # 标记已处理（或指出了）文件开头问题
                else: # 在一个Date块之后，或文件中有非Date开头的孤立行
                    errors.append(f"第{line_number_for_report}行错误: 意外的内容，此处应为新的 'Date:' 块。内容: '{line[:50]}...'")
                current_line_idx += 1 # 必须推进索引以避免死循环

        if errors:
            print("\n发现以下错误:")
            # 去重并按行号排序错误信息（近似，因为错误信息包含行号）
            unique_errors = sorted(list(set(errors)), key=lambda x: int(re.search(r'第(\d+)行', x).group(1)) if re.search(r'第(\d+)行', x) else 0)
            for error in unique_errors:
                print(error)
        else:
            print("\n文件格式完全正确！")

    except Exception as e:
        print(f"\n程序执行过程中发生致命错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        process_end_time = time.perf_counter()
        if 'process_start_time' in locals(): # 确保 process_start_time 已定义
            print(f"\n处理时间:{process_end_time - process_start_time:.6f}秒")
        else: # 如果在 process_start_time 定义前就出错了
            print(f"\n处理时间: 无法计算 (计时开始前发生错误)")


if __name__ == "__main__":
    main()
