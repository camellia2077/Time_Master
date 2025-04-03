import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
import calendar
GITHUB_GREEN_LIGHT = ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
GITHUB_GREEN_DARK = ['#151b23', '#033a16', '#196c2e', '#2ea043', '#56d364']
BLUE_LIGHT= ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#08306b']
ORANGE_LIGHT = ['#fff8e1', '#ffe082', '#ffd54f', '#ffb300', '#ff8f00']
PINK_LIGHT = ['#fce4ec', '#f8bbd0', '#f48fb1', '#f06292', '#ec407a']
PURPLE_LIGHT = ['#f3e5f5', '#ce93d8', '#ab47bc', '#8e24aa', '#6a1b9a']
BROWN_LIGHT = ['#efebe9', '#d7ccc8', '#bcaaa4', '#8d6e63', '#6d4c41']
LAVA_RED_LIGHT = ['#ffebee', '#ffcdd2', '#ef9a9a', '#e57373', '#ef5350']
GOLD_LIGHT = ['#fff8e1', '#ffe082', '#ffd54f', '#ffb300', '#ff8f00']
BLOOD_RED_LIGHT = ['#fff5f0', '#fee0d2', '#fc9272', '#de2d26', '#a50f15']
DEFAULT_COLOR_PALETTE = GITHUB_GREEN_LIGHT
GOLD = '#FFFF00'

def init_db():
    conn = sqlite3.connect('time_tracking.db')
    cursor = conn.cursor()
    
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS days (
            date TEXT PRIMARY KEY,
            status TEXT,
            remark TEXT,
            getup_time TEXT
        );
        
        CREATE TABLE IF NOT EXISTS time_records (
            date TEXT,
            start TEXT,
            end TEXT,
            project_path TEXT,
            duration INTEGER,
            PRIMARY KEY(date, start)
        );
        
        CREATE TABLE IF NOT EXISTS parent_child (
            child TEXT PRIMARY KEY,
            parent TEXT
        );
        
        CREATE TABLE IF NOT EXISTS parent_time (
            date TEXT,
            parent TEXT,
            duration INTEGER,
            PRIMARY KEY(date, parent)
        );
    ''')
    
    # Predefined top-level mappings (no longer hardcoding all combinations)
    top_level_map = {
        'study': 'STUDY',
        'code': 'CODE',
        'routine': 'ROUTINE',
        'break': 'BREAK',
        'rest': 'REST',
        'exercise': 'EXERCISE',
        'sleep': 'SLEEP',
        'recreation': 'RECREATION',
        'other': 'OTHER',
        'meal': 'MEAL',
        'program':'Program',
        'arrange':'ARRANGE',
    }
    
    # Insert only top-level mappings; sub-levels will be built dynamically
    for child, parent in top_level_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent))
    
    conn.commit()
    return conn
def parse_file(conn, filepath):
    cursor = conn.cursor()
    current_date = None
    day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
    time_records = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('Date:'):
                    if current_date:
                        cursor.execute('''
                            UPDATE days SET status=?, remark=?, getup_time=?
                            WHERE date=?
                        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
                        for start, end, project_path, duration in time_records:
                            cursor.execute('''
                                INSERT OR REPLACE INTO time_records 
                                VALUES (?, ?, ?, ?, ?)
                            ''', (current_date, start, end, project_path, duration))
                            parts = project_path.split('_')
                            for i in range(len(parts)):
                                child = '_'.join(parts[:i+1])
                                parent = '_'.join(parts[:i]) if i > 0 else parts[0]
                                cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent,))
                                parent_result = cursor.fetchone()
                                if parent_result:
                                    parent = parent_result[0]
                                elif i == 0:
                                    cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                                    if not cursor.fetchone():
                                        cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', 
                                                       (child, 'STUDY' if child == 'study' else child.upper()))
                                    continue
                                cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent))
                        day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}
                        time_records = []
                    current_date = line[5:].strip()
                    cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (current_date,))
                elif line.startswith('Status:'):
                    day_info['status'] = line[7:].strip()
                elif line.startswith('Remark:'):
                    day_info['remark'] = line[7:].strip()
                elif line.startswith('Getup:'):
                    day_info['getup_time'] = line[6:].strip()
                elif '~' in line:
                    # 修改正则表达式允许连字符
                    match = re.match(r'^(\d+:\d+)~(\d+:\d+)\s*([a-zA-Z_-]+)', line)  # 关键修改点
                    if not match:
                        print(f"格式错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                        continue
                    start, end, project_path = match.groups()
                    project_path = project_path.lower().replace('stduy', 'study')
                    start_sec = time_to_seconds(start)
                    end_sec = time_to_seconds(end)
                    if end_sec < start_sec:
                        end_sec += 86400
                    duration = end_sec - start_sec
                    time_records.append((start, end, project_path, duration))
            except Exception as e:
                print(f"解析错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                print(f"错误信息: {str(e)}")
                continue

    if current_date:
        cursor.execute('''
            UPDATE days SET status=?, remark=?, getup_time=?
            WHERE date=?
        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
        for start, end, project_path, duration in time_records:
            cursor.execute('''
                INSERT OR REPLACE INTO time_records 
                VALUES (?, ?, ?, ?, ?)
            ''', (current_date, start, end, project_path, duration))
            parts = project_path.split('_')
            for i in range(len(parts)):
                child = '_'.join(parts[:i+1])
                parent = '_'.join(parts[:i]) if i > 0 else parts[0]
                cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent,))
                parent_result = cursor.fetchone()
                if parent_result:
                    parent = parent_result[0]
                elif i == 0:
                    cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                    if not cursor.fetchone():
                        cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', 
                                       (child, 'STUDY' if child == 'study' else child.upper()))
                    continue
                cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent))

    conn.commit()
def get_study_times(conn, year):
    cursor = conn.cursor()
    start_date = f"{year}0101"
    end_date = f"{year}1231"
    cursor.execute('''
        SELECT date, SUM(duration)
        FROM time_records
        WHERE date BETWEEN ? AND ?
        AND (project_path = 'study' OR project_path LIKE 'study_%')
        GROUP BY date
    ''', (start_date, end_date))
    study_times = dict(cursor.fetchall())
    return study_times
def get_color(study_time):
    hours = study_time / 3600
    if hours == 0:
        return DEFAULT_COLOR_PALETTE[0]
    elif hours < 4:
        return DEFAULT_COLOR_PALETTE[1]
    elif hours < 8:
        return DEFAULT_COLOR_PALETTE[2]
    elif hours < 10:
        return DEFAULT_COLOR_PALETTE[3]
    elif hours < 12:
        return DEFAULT_COLOR_PALETTE[4]
    else:
        return GOLD
def generate_heatmap(conn, year, output_file):
    from datetime import datetime, timedelta
    study_times = get_study_times(conn, year)
    
    # 设置起止日期
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    
    # 计算前置空白天数（GitHub 热力图从周日开始）
    first_weekday = start_date.weekday()  # 0=周一, ..., 6=周日
    front_empty_days = (6 - first_weekday) % 7 if first_weekday != 6 else 0
    
    # 计算总天数和后置空白天数
    total_days = (end_date - start_date).days + 1
    total_slots = front_empty_days + total_days
    back_empty_days = (7 - (total_slots % 7)) % 7
    
    # 生成 heatmap_data
    heatmap_data = []
    # 前置空白天
    for _ in range(front_empty_days):
        heatmap_data.append((None, 'empty', 0))
    # 年份内的天
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        study_time = study_times.get(date_str, 0)
        color = get_color(study_time)
        heatmap_data.append((current_date, color, study_time))
        current_date += timedelta(days=1)
    # 后置空白天
    for _ in range(back_empty_days):
        heatmap_data.append((None, 'empty', 0))
    
    # SVG 设置
    cell_size = 12  # 方块大小：12x12 像素
    spacing = 3   # 方块间距：3 像素
    weeks = 53    # 列数：53 周
    rows = 7      # 行数：7 天
    
    # 调整 SVG 尺寸以容纳标记
    margin_top = 20  # 顶部留白（用于月份标记）
    margin_left = 30  # 左侧留白（用于星期标记）
    width = margin_left + weeks * (cell_size + spacing)
    height = margin_top + rows * (cell_size + spacing)
    
    # 生成 SVG
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    
    # 添加星期标记（纵坐标）
    days_of_week = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    for i, day in enumerate(days_of_week):
        y = margin_top + i * (cell_size + spacing) + cell_size / 2
        svg.append(f'<text x="0" y="{y}" font-size="10" alignment-baseline="middle">{day}</text>')
    
    # 添加月份标记（横坐标）
    months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    month_positions = []
    current_month = start_date.month
    for i, (date, _, _) in enumerate(heatmap_data):
        if date and date.month != current_month:
            month_positions.append((current_month, i // 7))
            current_month = date.month
    month_positions.append((current_month, len(heatmap_data) // 7))
    
    for month, week_index in month_positions:
        x = margin_left + week_index * (cell_size + spacing)
        svg.append(f'<text x="{x}" y="{margin_top - 5}" font-size="10" text-anchor="middle">{month}</text>')
    
    # 添加方块
    for i, (date, color, study_time) in enumerate(heatmap_data):
        if date is not None:  # 只为实际日期生成方块
            # 计算方块位置
            week_index = i // 7  # 第几周
            day_index = i % 7   # 星期几（0=周日, ..., 6=周六）
            x = margin_left + week_index * (cell_size + spacing)
            y = margin_top + day_index * (cell_size + spacing)
            # 格式化学习时间
            duration_str = format_duration(study_time)
            title_text = f"{date.strftime('%Y-%m-%d')}: {duration_str}"
            # 添加矩形方块和 <title> 提示
            svg.append(f'<rect width="{cell_size}" height="{cell_size}" x="{x}" y="{y}" fill="{color}" rx="2" ry="2">')
            svg.append(f'    <title>{title_text}</title>')
            svg.append(f'</rect>')
    
    svg.append('</svg>')
    
    # 生成 HTML 文件
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub Style Heatmap</title>
    </head>
    <body>
        <div style="padding: 20px;">
        {''.join(svg)}
        </div>
    </body>
    </html>
    """
    with open(output_file, 'w') as f:
        f.write(html)
def time_to_seconds(t):
    try:
        if not t: return 0
        h, m = map(int, t.split(':'))
        return h * 3600 + m * 60
    except:
        return 0


def format_duration(seconds, avg_days=1):
    # 新增avg_days参数，保留两位小数的小时数
    total_h = seconds / 3600
    avg_h = total_h / avg_days if avg_days > 0 else 0
    
    # 原始格式保持小时+分钟显示
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    # 构建显示字符串
    time_str = f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"
    avg_str = f"{avg_h:.2f}h"  # 平均时间统一用小时显示
    
    return f"{time_str} ({avg_str}/day)" if avg_days > 1 else time_str
def generate_sorted_output(node, avg_days=1, indent=0):
    """递归生成按时间降序排列的输出行"""
    lines = []
    # 过滤出子节点并按duration降序排序
    children = [(k, v) for k, v in node.items() if k != 'duration']
    sorted_children = sorted(children, key=lambda x: x[1].get('duration', 0), reverse=True)
    
    for key, value in sorted_children:
        duration = value.get('duration', 0)
        lines.append('  ' * indent + f"{key}: {format_duration(duration, avg_days)}")
        # 递归处理子节点
        lines.extend(generate_sorted_output(value, avg_days, indent + 1))
    return lines
def query_day(conn, date):
    cursor = conn.cursor()
    cursor.execute('SELECT status, remark, getup_time FROM days WHERE date = ?', (date,))
    day_data = cursor.fetchone()
    
    if not day_data:
        print(f"\n[{date}]\n无相关记录!")
        return
    
    status, remark, getup = day_data
    output = [f"\nDate:{date}", f"Status:{status}", f"Getup:{getup}"]
    if remark.strip():
        output.append(f"Remark:{remark}")
    
    cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date,))
    records = cursor.fetchall()
    
    # 新增总时间计算
    cursor.execute('SELECT SUM(duration) FROM time_records WHERE date = ?', (date,))
    total_duration = cursor.fetchone()[0] or 0
    total_h = total_duration // 3600
    total_m = (total_duration % 3600) // 60
    total_minutes = total_duration // 60
    output.append(f"Total: {total_h}h{total_m:02d}m ({total_minutes} minutes)")
    
    if records:
        tree = defaultdict(lambda: {'duration': 0})
        for project_path, duration in records:
            parts = project_path.split('_')
            if parts:
                top_level = 'STUDY' if parts[0].lower() == 'study' else parts[0].upper()
                tree[top_level]['duration'] += duration
                current = tree[top_level]
                for part in parts[1:]:
                    if part not in current:
                        current[part] = {'duration': 0}
                    current[part]['duration'] += duration
                    current = current[part]
        
        # 按顶层项目总时长排序
        sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
        for top_level, subtree in sorted_top_level:
            percentage = (subtree['duration'] / total_duration * 100) if total_duration else 0
            output.append(f"\n{top_level}: {format_duration(subtree['duration'])} ({percentage:.2f}%)")
            output.extend(generate_sorted_output(subtree, indent=1))
    
    print('\n'.join(output))

def query_period(conn, days):
    cursor = conn.cursor()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days-1)).strftime("%Y%m%d")

    cursor.execute('''
        SELECT 
            SUM(CASE WHEN status = 'True' THEN 1 ELSE 0 END) as true_count,
            SUM(CASE WHEN status = 'False' THEN 1 ELSE 0 END) as false_count,
            COUNT(*) as total_days
        FROM days 
        WHERE date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    status_data = cursor.fetchone()
    true_count = status_data[0] or 0
    false_count = status_data[1] or 0
    total_days = status_data[2] or 0

    print(f"\n[最近{days}天统计]{start_date} - {end_date}")
    print(f"有效记录天数:{total_days}天")
    print("状态分布:")
    print(f" True: {true_count}天 ({(true_count/total_days*100 if total_days>0 else 0):.1f}%)")
    print(f" False: {false_count}天 ({(false_count/total_days*100 if total_days>0 else 0):.1f}%)")

    cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?', 
                   (start_date, end_date))
    records = cursor.fetchall()
    
    if not records:
        print("\n无有效时间记录")
        return
    
    # Build hierarchical tree
    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for project_path, duration in records:
        parts = project_path.split('_')
        if not parts:
            continue
        
         # 处理顶层项目
        top_level = 'STUDY' if parts[0].lower() == 'study' else parts[0].upper()
        tree[top_level]['duration'] += duration
        
        # 处理子层级
        current = tree[top_level]
        for part in parts[1:]:
            if not isinstance(current['children'].get(part), dict):
                current['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            current['children'][part]['duration'] += duration
            current = current['children'][part]

    # 按总时长排序顶层项目
    sorted_top_level = sorted(tree.items(), key=lambda x: x[1]['duration'], reverse=True)
    
    for top_level, subtree in sorted_top_level:
        total_duration = subtree['duration']
        print(f"\n{top_level}: {format_duration(total_duration, days)}")
        # 使用统一的排序输出函数
        print('\n'.join(generate_sorted_output(subtree, avg_days=days, indent=1)))

def query_day_raw(conn, date):
    cursor = conn.cursor()
    
    # 查询基础信息
    cursor.execute('''
        SELECT date, status, getup_time, remark 
        FROM days 
        WHERE date = ?
    ''', (date,))
    day_data = cursor.fetchone()
    
    if not day_data:
        print(f"日期 {date} 无记录")
        return
    
    db_date, status, getup, remark = day_data
    
    # 查询时间记录
    cursor.execute('''
        SELECT start, end, project_path 
        FROM time_records 
        WHERE date = ? 
        ORDER BY start
    ''', (date,))
    records = cursor.fetchall()
    
    # 构建原始格式输出
    output = []
    output.append(f"Date:{db_date}")
    output.append(f"Status:{status}")
    output.append(f"Getup:{getup}")
    output.append(f"Remark:{remark}")
    
    for start, end, project in records:
        output.append(f"{start}~{end}{project}")
    
    print('\n'.join(output))
def query_month_summary(conn, year_month):
    cursor = conn.cursor()
    
    # 解析年月并验证
    if not re.match(r'^\d{6}$', year_month):
        print("月份格式错误，应为YYYYMM")
        return
    
    year = int(year_month[:4])
    month = int(year_month[4:6])
    last_day = calendar.monthrange(year, month)[1]
    actual_days = last_day  # 实际当月天数
    
    date_prefix = f"{year}{month:02d}%"
    cursor.execute('''
        SELECT project_path, SUM(duration)
        FROM time_records
        WHERE date LIKE ?
        GROUP BY project_path
    ''', (date_prefix,))
    records = cursor.fetchall()

    if not records:
        print(f"没有找到{year_month}的记录")
        return

    tree = defaultdict(lambda: {'duration': 0, 'children': defaultdict(dict)})
    for project_path, duration in records:
        parts = project_path.split('_')
        if not parts:
            continue
        
        top_level = 'STUDY' if parts[0].lower() == 'study' else parts[0].upper()
        tree[top_level]['duration'] += duration
        
        current = tree[top_level]
        for part in parts[1:]:
            if not isinstance(current['children'].get(part), dict):
                current['children'][part] = {'duration': 0, 'children': defaultdict(dict)}
            current['children'][part]['duration'] += duration
            current = current['children'][part]

    output = [f"\n[{year_month} 月统计]"]
    
    # 按总时长排序顶层项目
    sorted_top_level = sorted(tree.items(), key=lambda x: x[1].get('duration', 0), reverse=True)
    
    total = 0
    for top_level, subtree in sorted_top_level:
        total_duration = subtree['duration']
        total += total_duration
        output.append(f"{top_level}: {format_duration(total_duration, actual_days)}")
        # 使用统一的排序输出函数
        output.extend(generate_sorted_output(subtree, avg_days=actual_days, indent=1))
    
    # 显示总平均时间
    total_avg = total/actual_days/3600 if actual_days >0 else 0
    output.append(f"\n总时间: {format_duration(total)} ({total_avg:.2f}h)")
    print('\n'.join(output))
def main():
    conn = init_db()
    
    while True:
        print("\n0. 处理文件并导入数据")
        print("1. 查询某日统计")
        print("2. 查询最近7天")
        print("3. 查询最近14天")
        print("4. 查询最近30天")
        print("5. 输出某天原始数据")
        print("6. 生成热力图")
        print("7. 月统计数据")  
        print("8. 退出")       
        choice = input("请选择操作：")
        
        if choice == '0':
            input_path = input("请输入文件或目录路径：").strip('"')  # 移除可能包裹的引号
            input_path = os.path.normpath(input_path)  # 规范化路径格式
            
            # 处理单个文件的情况
            if os.path.isfile(input_path) and input_path.lower().endswith('.txt'):
                print(f"\n处理独立文件: {input_path}")
                parse_file(conn, input_path)
            
            # 处理目录的情况
            elif os.path.isdir(input_path):
                print(f"\n扫描目录: {input_path}")
                file_count = 0
                for root, _, files in os.walk(input_path):
                    for filename in files:
                        if filename.lower().endswith('.txt'):
                            filepath = os.path.join(root, filename)
                            print(f"发现数据文件: {filepath}")
                            parse_file(conn, filepath)
                            file_count += 1
                print(f"共处理 {file_count} 个数据文件")
            
            # 错误路径处理
            else:
                print(f"错误路径: {input_path} (请确认输入的是.txt文件或有效目录)")
        elif choice == '1':
            date = input("请输入日期(如YYYYMMDD):")
            if re.match(r'^\d{8}$', date):
                query_day(conn, date)
            else:
                print("日期格式错误")
        elif choice in ('2', '3', '4'):
            days_map = {'2':7, '3':14, '4':30}
            query_period(conn, days_map[choice])
        elif choice == '5':
            date = input("请输入日期(YYYYMMDD):")
            if re.match(r'^\d{8}$', date):
                query_day_raw(conn, date)
            else:
                print("日期格式错误")
        elif choice == '6':  # Handle heatmap generation
            year = input("请输入年份(YYYY):")
            if re.match(r'^\d{4}$', year):
                output_file = f"heatmap_{year}.html"
                generate_heatmap(conn, int(year), output_file)
                print(f"热力图已生成：{output_file}")
            else:
                print("年份格式错误")
        elif choice == '7':  # 新增月统计处理
            year_month = input("请输入年份和月份(如202502):")
            if re.match(r'^\d{6}$', year_month):
                query_month_summary(conn, year_month)
            else:
                print("月份格式错误")
        elif choice == '8':  # 退出选项改为8
            break
        else:
            print("input int num")
    
    conn.close()

if __name__ == '__main__':
    main()
