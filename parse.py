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
            child TEXT,
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
    
    parent_child_map = {
        'study_computer': 'STUDY',
        'study_english': 'STUDY',
        'study_math': 'STUDY', 
        'break_period': 'BREAK',
        'break_allday': 'BREAK',
        'rest_masturbation': 'REST',
        'rest_short': 'REST',
        'exercise_default': 'EXERCISE',
        'exercise_cardio': 'EXERCISE',
        'exercise_anaerobic': 'EXERCISE',
        'sleep_nap': 'SLEEP',
        'sleep_night': 'SLEEP',
        'RECREATION_game': 'RECREATION',
        'RECREATION_bilibili': 'RECREATION',
        'RECREATION_zhihu': 'RECREATION',
        'RECREATION_douyin': 'RECREATION',
        'RECREATION_weibo': 'RECREATION',
        'RECREATION_other': 'RECREATION',
        'other_learndriving': 'OTHER',
        'meal_short': 'MEAL',
        'meal_medium': 'MEAL',
        'meal_long': 'MEAL'
    }
    
    for child, parent in parent_child_map.items():
        cursor.execute('''
            INSERT OR IGNORE INTO parent_child (child, parent)
            VALUES (?, ?)
        ''', (child, parent))
    
    conn.commit()
    return conn

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
                    # 增强型时间解析
                    match = re.match(r'^(\d+:\d+)~(\d+:\d+)\s*([a-zA-Z_]+)', line)
                    if not match:
                        print(f"格式错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                        continue
                        
                    start, end, activity = match.groups()
                    activity = activity.lower().replace('stduy', 'study')

                    start_sec = time_to_seconds(start)
                    end_sec = time_to_seconds(end)
                    if end_sec < start_sec:
                        end_sec += 86400  # 处理跨午夜
                    duration = end_sec - start_sec

                    cursor.execute('''
                        INSERT OR REPLACE INTO time_records 
                        VALUES (?, ?, ?, ?, ?)
                    ''', (current_date, start, end, activity, duration))

            except Exception as e:
                print(f"解析错误在 {os.path.basename(filepath)} 第{line_num}行: {line}")
                print(f"错误信息: {str(e)}")
                continue

    if current_date:
        cursor.execute('''
            UPDATE days SET status=?, remark=?, getup_time=?
            WHERE date=?
        ''', (day_info['status'], day_info['remark'], day_info['getup_time'], current_date))
        
        cursor.execute('''
            INSERT INTO parent_time (date, parent, duration)
            SELECT t.date, pc.parent, SUM(t.duration)
            FROM time_records t
            JOIN parent_child pc ON t.child = pc.child
            WHERE t.date = ?
            GROUP BY t.date, pc.parent
            ON CONFLICT(date, parent) DO UPDATE SET
                duration = excluded.duration
        ''', (current_date,))
    
    conn.commit()

def format_duration(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"

def query_day(conn, date):
    cursor = conn.cursor()
    
    # 获取基础信息
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
    
    # 添加元数据
    output.append(f"状态: {status}")
    output.append(f"起床: {getup}")
    if remark.strip():
        output.append(f"备注: {remark}")
    
    # 获取总时间
    cursor.execute('SELECT SUM(duration) FROM parent_time WHERE date = ?', (date,))
    total = cursor.fetchone()[0] or 0
    
    if total == 0:
        output.append("\n无有效时间记录")
        print('\n'.join(output))
        return
    
    # 添加时间统计
    cursor.execute('''
        SELECT parent, duration 
        FROM parent_time 
        WHERE date = ?
        ORDER BY duration DESC
    ''', (date,))
    
    for parent, duration in cursor.fetchall():
        percent = (duration / total * 100) if total > 0 else 0
        output.append(f"\n{parent}: {format_duration(duration)} ({percent:.1f}%)")
        
        cursor.execute('''
            SELECT t.child, SUM(t.duration)
            FROM time_records t
            JOIN parent_child pc ON t.child = pc.child
            WHERE t.date = ? AND pc.parent = ?
            GROUP BY t.child
            ORDER BY SUM(t.duration) DESC
        ''', (date, parent))
        
        for child, dur in cursor.fetchall():
            output.append(f"  ├─ {child}: {format_duration(dur)}")
    
    print('\n'.join(output))

def query_period(conn, days):
    cursor = conn.cursor()
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days-1)).strftime("%Y%m%d")

    # 状态统计
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

    # 输出统计头信息
    print(f"\n【最近{days}天统计】{start_date} - {end_date}")
    print(f"有效记录天数: {total_days}天")
    print("状态分布:")
    print(f"  True: {true_count}天 ({(true_count/total_days*100 if total_days>0 else 0):.1f}%)")
    print(f"  False: {false_count}天 ({(false_count/total_days*100 if total_days>0 else 0):.1f}%)")

    # 时间分配统计
    cursor.execute('''
        SELECT parent, SUM(duration) 
        FROM parent_time 
        WHERE date BETWEEN ? AND ?
        GROUP BY parent 
        ORDER BY SUM(duration) DESC
    ''', (start_date, end_date))
    
    total = 0
    results = []
    for parent, duration in cursor.fetchall():
        total += duration
        results.append((parent, duration))
    
    if total == 0:
        print("\n无有效时间记录")
        return

    print("\n时间分配:")
    for parent, duration in results:
        percent = (duration / total * 100) if total > 0 else 0
        print(f"\n{parent}: {format_duration(duration)} ({percent:.1f}%)")
        
        cursor.execute('''
            SELECT t.child, SUM(t.duration)
            FROM time_records t
            JOIN parent_child pc ON t.child = pc.child
            WHERE t.date BETWEEN ? AND ? AND pc.parent = ?
            GROUP BY t.child
            ORDER BY SUM(t.duration) DESC
        ''', (start_date, end_date, parent))
        
        for child, dur in cursor.fetchall():
            print(f"  ├─ {child}: {format_duration(dur)}")

def main():
    conn = init_db()
    
    while True:
        print("\n0. 处理文件并导入数据")
        print("1. 查询某日统计")
        print("2. 查询最近7天")
        print("3. 查询最近14天")
        print("4. 查询最近30天")
        print("5. 退出")
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
            break
        else:
            print("无效输入")
    
    conn.close()

if __name__ == '__main__':
    main()