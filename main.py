# main.py
import os
import re
import time
import data_parser as dp
import database_importer as di
import database_querier as dq
import heatmap_generator as hg

def print_menu():
    """Prints the main menu options to the console."""
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

def handle_menu_choice(choice, conn):
    """Handles the user's menu choice."""
    if choice == '0':
        input_path = input("Enter the path to a .txt file or a directory: ").strip().strip('"')
        input_path = os.path.normpath(input_path)
        start_time = time.time()
        
        def process_and_import(filepath):
            print(f"Parsing file: {filepath}")
            parsed_data = dp.parse_file(filepath)
            
            if parsed_data:
                print(f"Importing data from {os.path.basename(filepath)} into database...")
                di.import_to_db(conn, parsed_data)
                return True
            else:
                print(f"No data was parsed from {filepath}. Nothing to import.")
                return False

        if os.path.isfile(input_path) and input_path.lower().endswith('.txt'):
            if process_and_import(input_path):
                print("File processing complete.")
        elif os.path.isdir(input_path):
            print(f"\nScanning directory: {input_path}")
            file_count = 0
            for root, _, files in os.walk(input_path):
                for filename in files:
                    if filename.lower().endswith('.txt'):
                        filepath = os.path.join(root, filename)
                        if process_and_import(filepath):
                            file_count += 1
            if file_count > 0:
                print(f"\nDirectory scanning complete. Processed and imported {file_count} file(s).")
            else:
                print(f"No .txt files found or successfully processed in {input_path}")
        else:
            print(f"Error: Invalid path. Please provide a valid .txt file or directory: {input_path}")
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Time taken for processing: {elapsed_time:.2f} seconds")

    elif choice == '1': 
        date_str = input("Enter date (YYYYMMDD): ")
        if re.match(r'^\d{8}$', date_str): 
            dq.query_day(conn, date_str)
        else: 
            print("Invalid date format. Please use YYYYMMDD.")

    elif choice in ('2', '3', '4'):
        days_map = {'2': 7, '3': 14, '4': 30}
        dq.query_period(conn, days_map[choice])

    elif choice == '5':
        date_str = input("Enter date (YYYYMMDD): ")
        if re.match(r'^\d{8}$', date_str):
            dq.query_day_raw(conn, date_str)
        else:
            print("Invalid date format. Please use YYYYMMDD.")

    elif choice == '6':
        year_str = input("Enter year for heatmap (YYYY): ")
        if re.match(r'^\d{4}$', year_str):
            year = int(year_str)
            output_file = f"study_heatmap_{year}.html"
            
            # Step 1: Fetch data from the database.
            fetcher = hg.HeatmapDataFetcher(conn)
            study_data = fetcher.fetch_yearly_study_times(year)
            
            # Step 2: Generate the heatmap using the fetched data.
            generator = hg.HeatmapGenerator(year, study_data)
            generator.generate_html_output(output_file)
            
            print(f"Study heatmap generated: {output_file}")
        else:
            print("Invalid year format. Please use YYYY.")

    elif choice == '7':
        year_month_str = input("Enter year and month (YYYYMM): ")
        if re.match(r'^\d{6}$', year_month_str):
            dq.query_month_summary(conn, year_month_str)
        else:
            print("Invalid year-month format. Please use YYYYMM.")

    elif choice == '8':
        print("Exiting application.")
        return False
    else:
        print("Invalid choice. Please enter a number from the menu.")
    
    return True

def main():
    conn = di.init_db()

    try:
        while True:
            print_menu()
            choice = input("Please select an option: ")
            if not handle_menu_choice(choice, conn):
                break
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    main()
