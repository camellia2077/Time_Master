import re
import time

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
    """检查Date行格式，返回是否正确"""
    if not line.startswith('Date:'):
        errors.append(f"第{line_num}行错误:Date行缺少冒号")
        return False
    elif not re.fullmatch(r'Date:\d{8}', line):
        errors.append(f"第{line_num}行错误:Date格式应为YYYYMMDD")
        return False
    return True

def check_status_line(line, line_num, errors):
    """检查Status行格式"""
    if not re.fullmatch(r'Status:(True|False)', line):
        errors.append(f"第{line_num}行错误:Status必须为True或False")

def check_getup_line(line, line_num, errors):
    """检查Getup行格式"""
    if not re.fullmatch(r'Getup:\d{2}:\d{2}', line):
        errors.append(f"第{line_num}行错误:Getup时间格式不正确")
    else:
        time_part = line.split(':')[1] + ':' + line.split(':')[2]
        if not validate_time(time_part):
            errors.append(f"第{line_num}行错误:Getup时间无效")

def check_remark_line(line, line_num, errors):
    """检查Remark行格式"""
    if not line.startswith('Remark:'):
        errors.append(f"第{line_num}行错误:Remark格式不正确")

def check_time_line(line, line_num, errors):
    """检查时间行格式"""
    if not re.match(r'^(\d{2}:\d{2})~(\d{2}:\d{2})[a-zA-Z_-]+$', line):
        errors.append(f"第{line_num}行错误:时间行格式错误")
        return
    time_part = re.findall(r'\d{2}:\d{2}', line)
    if len(time_part) != 2 or not validate_time(time_part[0]) or not validate_time(time_part[1]):
        errors.append(f"第{line_num}行错误:时间值无效")

def main():
    try:
        errors = []
        file_path = input("请输入文本文件的路径:")
        start_time = time.perf_counter()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
        except FileNotFoundError:
            print("文件不存在")
            return

        current_line = 0
        total_lines = len(lines)

        while current_line < total_lines:
            line = lines[current_line]
            if not line:  # 跳过空行
                current_line += 1
                continue
            
            if line.startswith('Date'):  # 检查所有以'Date'开头的行
                if check_date_line(line, current_line + 1, errors):  # Date行正确
                    # 处理Status、Getup、Remark行
                    for header in ['Status', 'Getup', 'Remark']:
                        current_line += 1
                        if current_line >= total_lines:
                            errors.append(f"第{current_line}行错误:文件突然结束")
                            break
                        current_header = lines[current_line]
                        check_functions = {
                            'Status': check_status_line,
                            'Getup': check_getup_line,
                            'Remark': check_remark_line
                        }
                        check_func = check_functions.get(header)
                        if check_func:
                            check_func(current_header, current_line + 1, errors)
                        if not current_header.startswith(f"{header}:"):
                            errors.append(f"第{current_line + 1}行错误:缺少或错误的头部 '{header}:'")
                    
                    # 处理时间行
                    current_line += 1
                    while current_line < total_lines and not lines[current_line].startswith('Date'):
                        time_line = lines[current_line]
                        if time_line:
                            check_time_line(time_line, current_line + 1, errors)
                        current_line += 1
                else:  # Date行错误，跳过至下一个Date行或文件结束
                    current_line += 1
                    while current_line < total_lines and not lines[current_line].startswith('Date'):
                        current_line += 1
            else:
                errors.append(f"第{current_line + 1}行错误:意外的内容或格式错误")
                current_line += 1

        if errors:
            print("\n发现以下错误:")
            for error in errors:
                print(error)
        else:
            print("\n文件格式完全正确！")

    finally:
        end_time = time.perf_counter()
        print(f"\n处理时间:{end_time - start_time:.6f}秒")

if __name__ == "__main__":
    main()