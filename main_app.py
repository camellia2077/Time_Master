import os
import re
import database_manager as db # database_manager.py is in the same directory
import heatmap_generator as hg # heatmap_generator.py is in the same directory

def main():
    conn = db.init_db()

    while True:
        print("\n--- Time Tracking Menu ---")
        print("0. Process file(s) and import data")
        print("1. Query daily statistics")
        print("2. Query last 7 days")
        print("3. Query last 14 days")
        print("4. Query last 30 days")
        print("5. Output raw data for a day")
        print("6. Generate study heatmap for a year")
        print("7. Query monthly statistics")
        print("8. Exit")
        choice = input("Please select an option: ")

        if choice == '0':
            input_path = input("Enter the path to a .txt file or a directory containing .txt files: ").strip().strip('"')
            input_path = os.path.normpath(input_path)

            if os.path.isfile(input_path) and input_path.lower().endswith('.txt'):
                print(f"\nProcessing single file: {input_path}")
                db.parse_file(conn, input_path)
                print(f"File processing complete for {input_path}")
            elif os.path.isdir(input_path):
                print(f"\nScanning directory: {input_path}")
                file_count = 0
                for root, _, files in os.walk(input_path):
                    for filename in files:
                        if filename.lower().endswith('.txt'):
                            filepath = os.path.join(root, filename)
                            print(f"Found data file: {filepath}")
                            db.parse_file(conn, filepath)
                            file_count += 1
                if file_count > 0:
                    print(f"Directory scanning complete. Processed {file_count} data file(s).")
                else:
                    print(f"No .txt files found in directory: {input_path}")
            else:
                print(f"Error: Invalid path. Please provide a valid .txt file or directory path: {input_path}")

        elif choice == '1':
            date_str = input("Enter date (YYYYMMDD): ")
            if re.match(r'^\d{8}$', date_str):
                db.query_day(conn, date_str)
            else:
                print("Invalid date format. Please use YYYYMMDD.")

        elif choice in ('2', '3', '4'):
            days_map = {'2': 7, '3': 14, '4': 30}
            db.query_period(conn, days_map[choice])

        elif choice == '5':
            date_str = input("Enter date (YYYYMMDD): ")
            if re.match(r'^\d{8}$', date_str):
                db.query_day_raw(conn, date_str)
            else:
                print("Invalid date format. Please use YYYYMMDD.")

        elif choice == '6':
            year_str = input("Enter year for heatmap (YYYY): ")
            if re.match(r'^\d{4}$', year_str):
                year = int(year_str)
                output_file = f"study_heatmap_{year}.html"
                hg.generate_heatmap(conn, year, output_file)
                print(f"Study heatmap generated: {output_file}")
            else:
                print("Invalid year format. Please use YYYY.")

        elif choice == '7':
            year_month_str = input("Enter year and month (YYYYMM): ")
            if re.match(r'^\d{6}$', year_month_str):
                db.query_month_summary(conn, year_month_str)
            else:
                print("Invalid year-month format. Please use YYYYMM.")

        elif choice == '8':
            print("Exiting application.")
            break
        else:
            print("Invalid choice. Please enter a number from the menu.")

    conn.close()

if __name__ == '__main__':
    main()