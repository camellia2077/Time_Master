import sqlite3
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict

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
        'break': 'BREAK',
        'rest': 'REST',
        'exercise': 'EXERCISE',
        'sleep': 'SLEEP',
        'recreation': 'RECREATION',
        'other': 'OTHER',
        'meal': 'MEAL'
    }
    
    # Insert only top-level mappings; sub-levels will be built dynamically
    for child, parent in top_level_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent))
    
    conn.commit()
    return conn
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
        return '#ebedf0'
    elif hours < 4:
        return '#9be9a8'
    elif hours < 8:
        return '#40c463'
    elif hours < 12:
        return '#30a14e'
    else:
        return '#216e39'
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
        heatmap_data.append((None, 'empty'))
    # 年份内的天
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        study_time = study_times.get(date_str, 0)
        color = get_color(study_time)
        heatmap_data.append((current_date, color))
        current_date += timedelta(days=1)
    # 后置空白天
    for _ in range(back_empty_days):
        heatmap_data.append((None, 'empty'))
    
    # SVG 设置
    cell_size = 12  # 方块大小：12x12 像素
    spacing = 3   # 方块间距：3 像素
    weeks = 53    # 列数：53 周
    rows = 7      # 行数：7 天
    width = weeks * (cell_size + spacing)  # 宽度：795 像素
    height = rows * (cell_size + spacing)  # 高度：105 像素
    
    # 生成 SVG
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">']
    for i, (date, color) in enumerate(heatmap_data):
        if color != 'empty':
            # 计算方块位置
            week_index = i // 7  # 第几周
            day_index = i % 7   # 星期几（0=周日, ..., 6=周六）
            x = week_index * (cell_size + spacing)
            y = day_index * (cell_size + spacing)
            # 添加矩形方块
            svg.append(f'<rect width="{cell_size}" height="{cell_size}" x="{x}" y="{y}" fill="{color}" rx="2" ry="2" title="{date.strftime("%Y-%m-%d")}"/>')
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

def parse_file(conn, filepath):
    cursor = conn.cursor()
    current_date = None
    day_info = {'status': 'False', 'remark': '', 'getup_time': '00:00'}

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                line = line.strip()
                if not line: continue

                if line.startswith('Date:'):
                    current_date = line[5:].strip()
                    cursor.execute('INSERT OR IGNORE INTO days (date) VALUES (?)', (current_date,))
                    
                elif line.startswith('Status:'):
                    day_info['status'] = line[7:].strip()
                elif line.startswith('Remark:'):
                    day_info['remark'] = line[7:].strip()
                elif line.startswith('Getup:'):
                    day_info['getup_time'] = line[6:].strip()
                
                elif '~' in line:
                    match = re.match(r'^(\d+:\d+)~(\d+:\d+)\s*([a-zA-Z_]+)', line)
                    if not match:
                        print(f"格式错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                        continue
                        
                    start, end, project_path = match.groups()
                    project_path = project_path.lower().replace('stduy', 'study')

                    start_sec = time_to_seconds(start)
                    end_sec = time_to_seconds(end)
                    if end_sec < start_sec:
                        end_sec += 86400  # Handle midnight crossover
                    duration = end_sec - start_sec

                    # Store the full project path
                    cursor.execute('''
                        INSERT OR REPLACE INTO time_records 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (current_date, start, end, project_path, duration))

                    # Dynamically build hierarchy
                    parts = project_path.split('_')
                    for i in range(len(parts)):
                        child = '_'.join(parts[:i+1])
                        parent = '_'.join(parts[:i]) if i > 0 else parts[0]  # First level maps to top-level later
                        # Check if parent exists in parent_child; if not, assume top-level
                        cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (parent,))
                        parent_result = cursor.fetchone()
                        if parent_result:
                            parent = parent_result[0]
                        elif i == 0:
                            # Map first part to top-level if not already mapped
                            cursor.execute('SELECT parent FROM parent_child WHERE child = ?', (child,))
                            if not cursor.fetchone():
                                cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', 
                                               (child, 'STUDY' if child == 'study' else child.upper()))
                            continue
                        cursor.execute('INSERT OR IGNORE INTO parent_child (child, parent) VALUES (?, ?)', (child, parent))

            except Exception as e:
                print(f"解析错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                print(f"错误信息: {str(e)}")
                continue

    if current_date:
        cursor.execute('''
            UPDATE days SET status=?, remark=?, getup_time=?
            WHERE date=?
        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
    
    conn.commit()

def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"

def query_day(conn, date):
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT status, remark, getup_time 
        FROM days 
        WHERE date = ?
    ''', (date,))
    day_data = cursor.fetchone()
    
    if not day_data:
        print(f"\n【{date}】\n无相关记录")
        return
    
    status, remark, getup = day_data
    output = [f"\n【{date} 时间统计】"]
    output.append(f"状态: {status}")
    output.append(f"起床: {getup}")
    if remark.strip():
        output.append(f"备注: {remark}")
    
    cursor.execute('SELECT project_path, duration FROM time_records WHERE date = ?', (date,))
    records = cursor.fetchall()
    
    if not records:
        output.append("\n无有效时间记录")
        print('\n'.join(output))
        return
    
    # Build hierarchical tree
    tree = defaultdict(lambda: defaultdict(int))
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
            if part not in current:
                current[part] = defaultdict(int)
            current[part]['duration'] += duration
            current = current[part]
    
    # Print tree
    def print_subtree(node, indent=0, prefix=""):
        lines = []
        for key, value in node.items():
            if key != 'duration':
                duration = value['duration']
                name = f"{prefix}{key}" if prefix else key
                lines.append('  ' * indent + f"{name}: {format_duration(duration)}")
                lines.extend(print_subtree(value, indent + 1, f"{name}_" if indent > 0 else ""))
        return lines
    
    for top_level, subtree in tree.items():
        total_duration = subtree['duration']
        output.append(f"\n{top_level}: {format_duration(total_duration)}")
        output.extend(print_subtree(subtree, 1))
    
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

    print(f"\n【最近{days}天统计】{start_date} - {end_date}")
    print(f"有效记录天数: {total_days}天")
    print("状态分布:")
    print(f"  True: {true_count}天 ({(true_count/total_days*100 if total_days>0 else 0):.1f}%)")
    print(f"  False: {false_count}天 ({(false_count/total_days*100 if total_days>0 else 0):.1f}%)")

    cursor.execute('SELECT project_path, duration FROM time_records WHERE date BETWEEN ? AND ?', 
                   (start_date, end_date))
    records = cursor.fetchall()
    
    if not records:
        print("\n无有效时间记录")
        return
    
    # Build hierarchical tree
    tree = defaultdict(lambda: defaultdict(int))
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
            if part not in current:
                current[part] = defaultdict(int)
            current[part]['duration'] += duration
            current = current[part]
    
    # Print tree
    def print_subtree(node, indent=0, prefix=""):
        lines = []
        for key, value in node.items():
            if key != 'duration':
                duration = value['duration']
                name = f"{prefix}{key}" if prefix else key
                lines.append('  ' * indent + f"{name}: {format_duration(duration)}")
                lines.extend(print_subtree(value, indent + 1, f"{name}_" if indent > 0 else ""))
        return lines
    
    for top_level, subtree in tree.items():
        total_duration = subtree['duration']
        print(f"\n{top_level}: {format_duration(total_duration)}")
        print('\n'.join(print_subtree(subtree, 1)))
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
def main():
    conn = init_db()
    
    while True:
        print("\n0. 处理文件并导入数据")
        print("1. 查询某日统计")
        print("2. 查询最近7天")
        print("3. 查询最近14天")
        print("4. 查询最近30天")
        print("5. 输出某天原始数据")
        print("6. 生成热力图")  # New option
        print("7. 退出")        # Exit option shifted from 6 to 7
        choice = input("请选择操作：")
        
        if choice == '0':
            folder = input("请输入文件目录：")
            for filename in os.listdir(folder):
                if filename.lower().endswith(".txt"):
                    print(f"正在处理文件: {filename}")
                    parse_file(conn, os.path.join(folder, filename))
        elif choice == '1':
            date = input("请输入日期（YYYYMMDD）：")
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
            year = input("请输入年份（YYYY）：")
            if re.match(r'^\d{4}$', year):
                output_file = f"heatmap_{year}.html"
                generate_heatmap(conn, int(year), output_file)
                print(f"热力图已生成：{output_file}")
            else:
                print("年份格式错误")
        elif choice == '7':  # Updated exit condition
            break
        else:
            print("请输入数字")
    
    conn.close()

if __name__ == '__main__':
    main()
