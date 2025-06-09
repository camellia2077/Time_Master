#include "Bill_Parser.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <algorithm>

// 正则表达式初始化保持不变
const std::regex Bill_Parser::dateRegex_(R"(^DATE:(\d{6})$)");
const std::regex Bill_Parser::remarkRegex_(R"(^REMARK:(.*)$)");
const std::regex Bill_Parser::parentRegex_(R"(^([A-Z].*)$)");
const std::regex Bill_Parser::childRegex_(R"(^([a-z_]+)$)");
const std::regex Bill_Parser::itemRegex_(R"(^(\d+(?:\.\d+)?)\s*(.*)$)");

Bill_Parser::Bill_Parser() {
    reset();
}

void Bill_Parser::reset() {
    // records_.clear(); // --- CHANGE: Removed as records_ no longer exists
    lineNumber_ = 0;
    parentCounter_ = 0;
    childCounter_ = 0;
    itemCounter_ = 0;
    currentParentOrder_ = 0;
    currentChildOrder_ = 0;
}

std::string Bill_Parser::trim(const std::string& s) {
    auto start = s.begin();
    while (start != s.end() && std::isspace(static_cast<unsigned char>(*start))) {
        start++;
    }
    auto end = s.end();
    if (start != end) {
        do {
            end--;
        } while (std::distance(start, end) > 0 && std::isspace(static_cast<unsigned char>(*end)));
    }
    return std::string(start, end == s.end() ? end : end + 1);
}

// --- CHANGE: Method signature and implementation updated ---
void Bill_Parser::parseFile(const std::string& filename, std::function<void(const ParsedRecord&)> callback) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Could not open file: " + filename);
    }

    reset(); // Reset state before starting

    // --- CHANGE: Pre-allocation logic is no longer needed ---

    std::string line;
    while (std::getline(file, line)) {
        parseLine(line, callback); // Pass the callback down
    }
}

// --- CHANGE: getRecords() method is completely removed ---

// --- CHANGE: Method signature and implementation updated ---
void Bill_Parser::parseLine(const std::string& line, std::function<void(const ParsedRecord&)> callback) {
    lineNumber_++;
    std::string trimmedLine = trim(line);

    if (trimmedLine.empty()) {
        return;
    }

    std::smatch matches;

    // 1. Match DATE
    if (std::regex_match(trimmedLine, matches, dateRegex_)) {
        parentCounter_ = 0;
        childCounter_ = 0;
        itemCounter_ = 0;
        currentParentOrder_ = 0;
        currentChildOrder_ = 0;
        
        ParsedRecord rec; // Create a temporary record
        rec.type = "date";
        rec.lineNumber = lineNumber_;
        rec.content = matches[1].str();
        callback(rec); // --- CHANGE: Call the callback instead of push_back/emplace_back
    }
    // 2. Match REMARK
    else if (std::regex_match(trimmedLine, matches, remarkRegex_)) {
        ParsedRecord rec;
        rec.type = "remark";
        rec.lineNumber = lineNumber_;
        rec.content = trim(matches[1].str());
        callback(rec); // --- CHANGE: Call the callback
    }
    // 3. Match ITEM
    else if (std::regex_match(trimmedLine, matches, itemRegex_)) {
        if (currentParentOrder_ > 0 && currentChildOrder_ > 0) {
            itemCounter_++;
            ParsedRecord rec;
            rec.type = "item";
            rec.lineNumber = lineNumber_;
            rec.order = itemCounter_;
            rec.parentOrder = currentParentOrder_;
            rec.childOrder = currentChildOrder_;
            rec.amount = std::stod(matches[1].str());
            rec.description = trim(matches[2].str());
            callback(rec); // --- CHANGE: Call the callback
        } else {
            std::cerr << "Warning: Item on line " << lineNumber_ << " is not under a valid child category. Skipping." << std::endl;
        }
    }
    // 4. Match CHILD
    else if (std::regex_match(trimmedLine, matches, childRegex_)) {
        if (currentParentOrder_ > 0) {
            childCounter_++;
            itemCounter_ = 0;
            currentChildOrder_ = childCounter_;
            ParsedRecord rec;
            rec.type = "child";
            rec.lineNumber = lineNumber_;
            rec.order = childCounter_;
            rec.parentOrder = currentParentOrder_;
            rec.content = matches[1].str();
            callback(rec); // --- CHANGE: Call the callback
        } else {
            std::cerr << "Warning: Child category on line " << lineNumber_ << " is not under a valid parent category. Skipping." << std::endl;
        }
    }
    // 5. Match PARENT
    else if (std::regex_match(trimmedLine, matches, parentRegex_)) {
        parentCounter_++;
        childCounter_ = 0;
        itemCounter_ = 0;
        currentParentOrder_ = parentCounter_;
        currentChildOrder_ = 0;
        ParsedRecord rec;
        rec.type = "parent";
        rec.lineNumber = lineNumber_;
        rec.order = parentCounter_;
        rec.content = matches[1].str();
        callback(rec); // --- CHANGE: Call the callback
    }
    else {
        std::cerr << "Warning: Unrecognized line format on line " << lineNumber_ << ": '" << trimmedLine << "'. Skipping." << std::endl;
    }
}