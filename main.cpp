#include <iostream>
#include <string>
#include <vector>
#include <limits>
#include <stdexcept>
#include <filesystem> // For C++17 file system operations
#include <chrono>     // For high-precision timing
#include <iomanip>    // For std::setprecision
#include <algorithm>  // For std::all_of
#include <cctype>     // For ::isdigit


// Add the Windows header for console functions.
#ifdef _WIN32
#include <windows.h>
#endif

#include "Bill_Parser.h"
#include "DatabaseInserter.h"
#include "BillReporter.h"

// C++17 filesystem alias
namespace fs = std::filesystem;

// Function to display the menu to the user
void show_menu() {
    std::cout << "\n===== Bill Management System =====\n";
    std::cout << "0. Import data from .txt file(s)\n";
    std::cout << "1. Annual consumption summary\n";
    std::cout << "2. Detailed monthly bill\n";
    std::cout << "3. Export monthly bill (machine-readable)\n";
    std::cout << "4. Annual category statistics\n";
    std::cout << "5. Exit\n";
    std::cout << "==================================\n";
    std::cout << "Enter your choice: ";
}

// Function to clear input buffer in case of invalid input
void clear_cin() {
    std::cin.clear();
    std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
}

/**
 * @brief Handles the import process by prompting for a path and reports detailed statistics.
 * --- MODIFIED: Now uses a single transaction for all files to ensure atomicity. ---
 * @param db_file The path to the SQLite database file.
 */
void handle_import_process(const std::string& db_file) {
    std::string user_path_str;
    std::cout << "Enter the path to a .txt file or a directory: ";
    std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    std::getline(std::cin, user_path_str);

    fs::path user_path(user_path_str);
    std::vector<fs::path> files_to_process;

    try {
        if (!fs::exists(user_path)) {
            std::cerr << "Error: Path does not exist: " << user_path.string() << std::endl;
            return;
        }

        if (fs::is_regular_file(user_path)) {
            if (user_path.extension() == ".txt") files_to_process.push_back(user_path);
            else std::cerr << "Error: The provided file is not a .txt file." << std::endl;
        } else if (fs::is_directory(user_path)) {
            for (const auto& entry : fs::recursive_directory_iterator(user_path)) {
                if (entry.is_regular_file() && entry.path().extension() == ".txt") {
                    files_to_process.push_back(entry.path());
                }
            }
        } else {
            std::cerr << "Error: The provided path is not a regular file or directory." << std::endl;
            return;
        }
    } catch (const fs::filesystem_error& e) {
        std::cerr << "Filesystem error: " << e.what() << std::endl;
        return;
    }

    if (files_to_process.empty()) {
        std::cout << "No .txt files found to process." << std::endl;
        return;
    }

    int successful_files = 0;
    int failed_files = 0;
    auto total_parsing_duration = std::chrono::nanoseconds(0);
    auto total_insertion_duration = std::chrono::nanoseconds(0);

    // Create inserter and parser outside the main try block for broader scope
    DatabaseInserter inserter(db_file);
    Bill_Parser parser;
    bool transaction_active = false;

    try {
        inserter.create_database();
        
        inserter.begin_transaction(); // <<< Start transaction before processing any files
        transaction_active = true;

        for (const auto& file_path : files_to_process) {
            std::cout << "Processing file: " << file_path.string() << std::endl;
            parser.reset();

            // --- CHANGE: A local vector to store records for the current file ---
            std::vector<ParsedRecord> current_file_records;

            auto parse_start = std::chrono::high_resolution_clock::now();
            
            // --- CHANGE: Call parseFile with a lambda to populate the local vector ---
            parser.parseFile(file_path.string(), 
                [&current_file_records](const ParsedRecord& record) {
                    current_file_records.push_back(record);
                }
            );

            auto parse_end = std::chrono::high_resolution_clock::now();
            total_parsing_duration += (parse_end - parse_start);

            // --- CHANGE: Check the local vector instead of parser.getRecords() ---
            if (current_file_records.empty()) {
                std::cout << "  -> No valid records found. Skipped." << std::endl;
                continue; 
            }
            
            auto insert_start = std::chrono::high_resolution_clock::now();
            // --- CHANGE: Insert from the local vector ---
            inserter.insert_data_stream(current_file_records);
            auto insert_end = std::chrono::high_resolution_clock::now();
            total_insertion_duration += (insert_end - insert_start);

            successful_files++;
        }

        std::cout << "\nAll files processed successfully. Committing changes to the database..." << std::endl;
        inserter.commit_transaction(); // <<< Commit transaction ONLY if all files succeed
        transaction_active = false;

        failed_files = files_to_process.size() - successful_files;

        // --- Final Success Report ---
        std::cout << "\n----------------------------------------\n";
        std::cout << "Import process finished successfully.\n\n";
        std::cout << "Successfully processed files: " << successful_files << std::endl;
        if(failed_files > 0) std::cout << "Skipped empty/invalid files: " << failed_files << std::endl;
        std::cout << "----------------------------------------\n";
        auto parsing_ms = std::chrono::duration_cast<std::chrono::milliseconds>(total_parsing_duration).count();
        double parsing_s = parsing_ms / 1000.0;
        std::cout << "Total text parsing time:        "
                  << parsing_ms << " ms (" << std::fixed << std::setprecision(3) << parsing_s << " s)\n";
        auto insertion_ms = std::chrono::duration_cast<std::chrono::milliseconds>(total_insertion_duration).count();
        double insertion_s = insertion_ms / 1000.0;
        std::cout << "Total database insertion time:  "
                  << insertion_ms << " ms (" << std::fixed << std::setprecision(3) << insertion_s << " s)\n";
        std::cout << "----------------------------------------\n";

    } catch (const std::runtime_error& e) {
        // This block executes if ANY file fails during parsing or insertion
        if (transaction_active) {
            std::cerr << "\nAn error occurred. Rolling back all changes..." << std::endl;
            inserter.rollback_transaction();
        }
        
        // --- Final Failure Report ---
        std::cerr << "\n----------------------------------------\n";
        std::cerr << "Import process FAILED. No data was saved to the database.\n\n";
        std::cerr << "Error detail: " << e.what() << std::endl;
        std::cerr << "----------------------------------------\n";
    }
}


int main() {
    // Set console output to UTF-8 on Windows to correctly display Chinese characters and prevent hanging.
    #ifdef _WIN32
        SetConsoleOutputCP(CP_UTF8);
    #endif

    const std::string db_file = "bills.db";
    int choice = -1;

    // The main loop continues until the user chooses to exit (5)
    while (choice != 5) {
        show_menu();
        std::cin >> choice;

        if (std::cin.fail() || choice < 0 || choice > 5) {
            std::cout << "Invalid input. Please enter a number between 0 and 5.\n";
            clear_cin();
            choice = -1; 
            continue;
        }

        try {
            if (choice == 0) {
                handle_import_process(db_file);
            } else if (choice > 0 && choice < 5) {
                BillReporter reporter(db_file);
                std::string year, category;

                switch (choice) {
                    case 1: // Annual summary
                        std::cout << "Enter year (e.g., 2025): ";
                        std::cin >> year;
                        reporter.query_1(year);
                        break;
                    case 2: // Detailed monthly bill
                    case 3: // Export monthly bill
                    { 
                        std::string year_month_str;
                        std::cout << "Enter year and month as a 6-digit number (e.g., 202501): ";
                        std::cin >> year_month_str;

                        if (year_month_str.length() != 6 || !std::all_of(year_month_str.begin(), year_month_str.end(), ::isdigit)) {
                            std::cerr << "Error: Invalid format. Please enter exactly 6 digits." << std::endl;
                        } else {
                            std::string input_year = year_month_str.substr(0, 4);
                            std::string input_month = year_month_str.substr(4, 2);
                            if (choice == 2) reporter.query_2(input_year, input_month);
                            else reporter.query_3(input_year, input_month);
                        }
                        break;
                    }
                    case 4: // Annual category statistics
                        std::cout << "Enter year (e.g., 2025): ";
                        std::cin >> year;
                        std::cout << "Enter parent category name (e.g., MEAL吃饭): ";
                        std::cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
                        std::getline(std::cin, category);
                        reporter.query_4(year, category);
                        break;
                }
            } else if (choice == 5) {
                std::cout << "Exiting program. Wish you a happy day! Goodbye!\n";
            }
        } catch (const std::runtime_error& e) {
            std::cerr << "\nAn error occurred: " << e.what() << std::endl;
        }
    }

    return 0;
}