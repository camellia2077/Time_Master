import sqlite3
import re
from collections import defaultdict
from datetime import datetime, timedelta
import time

# 创建数据库连接
conn = sqlite3.connect('time_tracking.db')
cursor = conn.cursor()

# 创建数据库表（添加weekday字段）
cursor.executescript('''
    CREATE TABLE IF NOT EXISTS raw_entries (
        date TEXT,
        start_time TEXT,
        end_time TEXT,
        activity TEXT,
        entry_order INTEGER,
        PRIMARY KEY (date, entry_order)
    );
    
    CREATE TABLE IF NOT EXISTS parent_times (
        date TEXT,
        parent TEXT,
        duration INTEGER,
        weekday TEXT,
        PRIMARY KEY (date, parent)
    );
    
    CREATE TABLE IF NOT EXISTS child_times (
        date TEXT,
        child TEXT,
        duration INTEGER,
        weekday TEXT,
        PRIMARY KEY (date, child)
    );
    
    CREATE TABLE IF NOT EXISTS parent_child (
        child TEXT PRIMARY KEY,
        parent TEXT
    );
''')

# 定义父项子项映射关系（保持不变）
parent_child_map = {
    'break_pause':'PAUSE',
    'study_computer': 'STUDY',
    'study_english': 'STUDY',
    'stduy_math': 'STUDY',
    'break_1': 'BREAK',
    'rest_jerkoff': 'REST',
    'exercise': 'EXERCISE',
    'sleep_nap': 'SLEEP',
    'sleep_night': 'SLEEP',
    'entertainmain_game': 'ENTERTAINMAIN',
    'entertainmain_bilibili': 'ENTERTAINMAIN',
    'entertainmain_zhihu': 'ENTERTAINMAIN',
    'other_learndriving': 'OTHER',
    'meal_short': 'MEAL',
    'meal_medium': 'MEAL',
    'meal_long': 'MEAL'
}

# 初始化映射表（保持不变）
for child, parent in parent_child_map.items():
    cursor.execute('''
        INSERT OR IGNORE INTO parent_child (child, parent)
        VALUES (?, ?)
    ''', (child, parent))
conn.commit()

def seconds_to_hhmm(seconds):
    """将秒数转换为HH:MM格式"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"

def parse_file():
    current_date = None
    current_weekday = None
    child_durations = defaultdict(int)
    parent_durations = defaultdict(int)
    entry_order = 0

    with open('date.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if re.match(r'^\d{8}$', line):
                if current_date:
                    save_data(current_date, child_durations, parent_durations, current_weekday)
                    child_durations.clear()
                    parent_durations.clear()
                    entry_order = 0
                
                current_date = line
                date_obj = datetime.strptime(current_date, "%Y%m%d")
                current_weekday = date_obj.strftime("%A")
                
                cursor.execute('DELETE FROM raw_entries WHERE date = ?', (current_date,))
                cursor.execute('DELETE FROM child_times WHERE date = ?', (current_date,))
                cursor.execute('DELETE FROM parent_times WHERE date = ?', (current_date,))
                conn.commit()
            else:
                if not current_date:
                    continue
                
                match = re.match(r'^(\d+:\d+)~(\d+:\d+)(.+)$', line)
                if not match:
                    continue
                
                start_time, end_time, activity = match.groups()
                activity = activity.strip()
                
                cursor.execute('''
                    INSERT INTO raw_entries VALUES (?, ?, ?, ?, ?)
                ''', (current_date, start_time, end_time, activity, entry_order))
                entry_order += 1
                
                child_match = re.search(r'([a-z_]+)$', activity)
                if not child_match:
                    continue
                child = child_match.group(1)
                
                def to_minutes(t):
                    h, m = map(int, t.split(':'))
                    return h * 60 + m
                
                start_min = to_minutes(start_time)
                end_min = to_minutes(end_time)
                duration = (end_min - start_min) * 60 if end_min >= start_min else (end_min + 1440 - start_min) * 60
                
                child_durations[child] += duration
                parent = parent_child_map.get(child, 'OTHER')
                parent_durations[parent] += duration
        
        if current_date:
            save_data(current_date, child_durations, parent_durations, current_weekday)

def save_data(date, child_data, parent_data, weekday):
    for child, duration in child_data.items():
        cursor.execute('''
            INSERT INTO child_times VALUES (?, ?, ?, ?)
        ''', (date, child, duration, weekday))
    
    for parent, duration in parent_data.items():
        cursor.execute('''
            INSERT INTO parent_times VALUES (?, ?, ?, ?)
        ''', (date, parent, duration, weekday))
    conn.commit()

def option1():
    date = input("请输入日期（格式YYYYMMDD）：")
    cursor.execute('''
        SELECT start_time, end_time, activity 
        FROM raw_entries 
        WHERE date = ? 
        ORDER BY entry_order
    ''', (date,))
    results = cursor.fetchall()
    
    if not results:
        print("无记录")
        return
    
    print(date)
    for start, end, act in results:
        print(f"{start}~{end}{act}")

def option2():
    date = input("请输入日期（格式YYYYMMDD）：")
    
    cursor.execute('SELECT SUM(duration) FROM parent_times WHERE date = ?', (date,))
    total_duration = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT parent, duration 
        FROM parent_times 
        WHERE date = ?
        ORDER BY duration DESC
    ''', (date,))
    parents = cursor.fetchall()
    
    if not parents:
        print("无记录")
        return
    
    print(f"\n【{date} 时间统计】")
    for parent, duration in parents:
        percentage = (duration / total_duration * 100) if total_duration > 0 else 0
        print(f"{parent}: {seconds_to_hhmm(duration)} ({percentage:.2f}%)")
        
        cursor.execute('''
            SELECT c.child, c.duration
            FROM child_times c
            JOIN parent_child p ON c.child = p.child
            WHERE c.date = ? AND p.parent = ?
            ORDER BY c.duration DESC
        ''', (date, parent))
        children = cursor.fetchall()
        
        for child, dur in children:
            print(f"  └ {child}: {seconds_to_hhmm(dur)}")

def option3():
    month = input("请输入年月（格式YYYYMM）：")
    cursor.execute('''
        SELECT parent, SUM(duration)
        FROM parent_times
        WHERE substr(date, 1, 6) = ?
        GROUP BY parent
        ORDER BY SUM(duration) DESC
    ''', (month,))
    parents = cursor.fetchall()
    
    if not parents:
        print("无记录")
        return
    
    total = sum(dur for _, dur in parents)
    total_hours = total / 3600
    
    print(f"\n【{month}月统计】")
    print(f"总时间: {total_hours:.2f}小时")
    for parent, dur in parents:
        percentage = (dur / total * 100) if total > 0 else 0
        print(f"{parent}: {seconds_to_hhmm(dur)} ({percentage:.2f}%)")

def option4():
    nums = int(input("请输入周数："))
    cursor.execute('SELECT DISTINCT date FROM parent_times')
    dates = [row[0] for row in cursor.fetchall()]
    
    weeks = set()
    for date_str in dates:
        date_obj = datetime.strptime(date_str, "%Y%m%d")
        start = date_obj - timedelta(days=date_obj.weekday())
        end = start + timedelta(days=6)
        weeks.add((start.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
    
    sorted_weeks = sorted(weeks, key=lambda x: x[1], reverse=True)[:nums]
    
    for i, (start, end) in enumerate(sorted_weeks, 1):
        dates_in_week = []
        current = datetime.strptime(start, "%Y%m%d")
        end_date = datetime.strptime(end, "%Y%m%d")
        while current <= end_date:
            dates_in_week.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        
        placeholders = ','.join(['?']*len(dates_in_week))
        cursor.execute(f'''
            SELECT parent, SUM(duration)
            FROM parent_times
            WHERE date IN ({placeholders})
            GROUP BY parent
            ORDER BY SUM(duration) DESC
        ''', dates_in_week)
        parents = cursor.fetchall()
        
        if not parents:
            continue
        
        total = sum(dur for _, dur in parents)
        total_hours = total / 3600
        
        print(f"\n第{i}周 ({start} - {end})")
        print(f"总时间: {total_hours:.2f}小时")
        for parent, dur in parents:
            percentage = (dur / total * 100) if total > 0 else 0
            print(f"{parent}: {seconds_to_hhmm(dur)} ({percentage:.2f}%)")

if __name__ == '__main__':
    start_time = time.time()  # 记录开始时间
    parse_file()
    end_time = time.time()  # 记录结束时间
    print(f"\n数据处理完成，耗时 {end_time - start_time:.2f} 秒")  # 新增耗时提示
    
    while True:
        print("\n1. 输出某日原始记录")
        print("2. 输出某日统计信息")
        print("3. 按月统计")
        print("4. 按周统计")
        print("5. 退出")
        choice = input("请选择操作：")
        
        if choice == '1':
            option1()
        elif choice == '2':
            option2()
        elif choice == '3':
            option3()
        elif choice == '4':
            option4()
        elif choice == '5':
            break
        else:
            print("无效输入")

conn.close()