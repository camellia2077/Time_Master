from datetime import datetime, timedelta
from parse_colors_config import DEFAULT_COLOR_PALETTE, YELLOW

def time_format_duration(seconds, avg_days=1):
    """Formats duration in seconds to a string (e.g., XhYYm) and optionally an average."""
    if seconds is None:
        seconds = 0
    
    # Calculate total duration
    total_hours = int(seconds // 3600)
    total_minutes = int((seconds % 3600) // 60)
    time_str = f"{total_hours}h{total_minutes:02d}m" if total_hours > 0 else f"{total_minutes}m"

    # If avg_days > 1, calculate and format average duration
    if avg_days > 1:
        avg_seconds_per_day = seconds / avg_days
        avg_hours = int(avg_seconds_per_day // 3600)
        avg_minutes = int((avg_seconds_per_day % 3600) // 60)
        avg_str = f"{avg_hours}h{avg_minutes:02d}m"
        return f"{time_str} ({avg_str}/day)"
    else:
        return time_str
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

def return_color(study_time):
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
        return YELLOW

def generate_heatmap(conn, year, output_file):
    study_times = get_study_times(conn, year) # Fetched via database_manager

    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)

    first_weekday = start_date.weekday()  # 0=周一, ..., 6=周日
    # GitHub heatmap typically starts on Sunday. weekday() is 0 for Mon, 6 for Sun.
    # If year starts on Monday (0), need 1 empty day.
    # If year starts on Sunday (6), need 0 empty days.
    # Correct logic for front_empty_days: (start_date.weekday() + 1) % 7
    # The original logic was for a week starting Monday, then adjusting.
    # Let's use GitHub's typical Sunday start:
    # Sunday = 0, Monday = 1, ..., Saturday = 6 for this calculation
    # Python's weekday(): Monday = 0, ..., Sunday = 6
    # We want the first column to be Sunday.
    # Number of blank days before the first day of the year:
    front_empty_days = (start_date.isoweekday() % 7) # ISO: Mon=1..Sun=7. So Sun=0 for us.

    total_days = (end_date - start_date).days + 1
    total_slots = front_empty_days + total_days
    back_empty_days = (7 - (total_slots % 7)) % 7

    heatmap_data = []
    for _ in range(front_empty_days):
        heatmap_data.append((None, 'empty', 0))

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        study_time = study_times.get(date_str, 0)
        color = return_color(study_time)
        heatmap_data.append((current_date, color, study_time))
        current_date += timedelta(days=1)

    for _ in range(back_empty_days):
        heatmap_data.append((None, 'empty', 0))

    cell_size = 12
    spacing = 3
    # weeks = (front_empty_days + total_days + back_empty_days) // 7 # Max 53 weeks
    weeks = len(heatmap_data) // 7
    rows = 7

    margin_top = 30 # Increased for month labels
    margin_left = 35 # For day labels
    width = margin_left + weeks * (cell_size + spacing) - spacing # No trailing spacing for width
    height = margin_top + rows * (cell_size + spacing) - spacing # No trailing spacing for height

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="font-family: Arial, sans-serif;">']

    # Add day labels (Sun, Mon, ..., Sat) - GitHub shows Mon, Wed, Fri
    # days_of_week = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    day_labels_display = {1: 'Mon', 3: 'Wed', 5: 'Fri'} # Display only for Mon, Wed, Fri
    for i in range(rows): # 0=Sun, 1=Mon...
        if i in day_labels_display:
            # y = margin_top + i * (cell_size + spacing) + cell_size / 2 # Centered
            y = margin_top + i * (cell_size + spacing) + cell_size - 2 # Align with top of cells better
            svg.append(f'<text x="0" y="{y}" font-size="10px" fill="#767676" alignment-baseline="middle">{day_labels_display[i]}</text>')


    # Add month labels
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    last_month_drawn = -1
    for week_idx in range(weeks):
        # Get the date corresponding to the first day (Sunday) of this week column
        # The first actual date in heatmap_data might be after front_empty_days
        first_day_of_week_idx_in_data = week_idx * 7 + front_empty_days
        # Find the first actual date in this column
        actual_date_in_col = None
        for i in range(7):
            idx = week_idx * 7 + i
            if idx < len(heatmap_data) and heatmap_data[idx][0] is not None:
                actual_date_in_col = heatmap_data[idx][0]
                break
        
        if actual_date_in_col:
            month_idx = actual_date_in_col.month -1 # 0-11
            # Draw month label if it's the first time we see this month in a new column
            # or if it's the first column and it's a new month.
            if month_idx != last_month_drawn:
                 # Only draw if it's a new month AND it's roughly the start of the month in this column
                if actual_date_in_col.day < 8 or week_idx == 0 : # Heuristic to place month label
                    x_pos = margin_left + week_idx * (cell_size + spacing)
                    svg.append(f'<text x="{x_pos}" y="{margin_top - 10}" font-size="10px" fill="#767676">{month_names[month_idx]}</text>')
                    last_month_drawn = month_idx


    # Add data cells (squares)
    for i, (date_obj, color, study_time) in enumerate(heatmap_data):
        col_idx = i // 7  # Week index
        row_idx = i % 7   # Day index (0=Sunday, ..., 6=Saturday)

        x = margin_left + col_idx * (cell_size + spacing)
        y = margin_top + row_idx * (cell_size + spacing)

        if date_obj is not None:
            duration_str = time_format_duration(study_time) # Formatted via database_manager
            title_text = f"{date_obj.strftime('%Y-%m-%d')}: {duration_str}"
            svg.append(f'  <rect width="{cell_size}" height="{cell_size}" x="{x}" y="{y}" fill="{color}" rx="2" ry="2">')
            svg.append(f'    <title>{title_text}</title>')
            svg.append(f'  </rect>')
        # else: # Optional: draw empty cells differently if needed
            # svg.append(f'<rect width="{cell_size}" height="{cell_size}" x="{x}" y="{y}" fill="#ebedf0" rx="2" ry="2" opacity="0.5"/>')


    svg.append('</svg>')

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Study Heatmap {year}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"; }}
            .heatmap-container {{
                display: inline-block;
                padding: 15px;
                border: 1px solid #d0d7de;
                border-radius: 6px;
                background-color: #ffffff; /* Or #0d1117 for dark mode if adaptable */
            }}
             h2 {{ margin-left: 35px; font-weight: 400; color: #24292f;}}
        </style>
    </head>
    <body>
        <div class="heatmap-container">
        <h2>Study Activity for {year}</h2>
        {''.join(svg)}
        </div>
    </body>
    </html>
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
