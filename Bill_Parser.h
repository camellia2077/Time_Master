#ifndef BILL_PARSER_H
#define BILL_PARSER_H

#include <string>
#include <vector>
#include <regex>
#include <functional> // --- CHANGE: Required for std::function
#include "ParsedRecord.h"

/**
 * @class Bill_Parser
 * @brief 一个用于解析特定格式账单文件的解析器。
 */
class Bill_Parser {
public:
    /**
     * @brief 构造函数。
     */
    Bill_Parser();

    /**
     * @brief 解析指定的账单文件，并对每条解析出的记录调用回调函数。
     * @param filename 要解析的文件路径。
     * @param callback 一个函数，用于处理每条解析出的 ParsedRecord。
     * @throws std::runtime_error 如果文件无法打开。
     */
    void parseFile(const std::string& filename, std::function<void(const ParsedRecord&)> callback); // --- CHANGE: Signature updated

    /**
     * @brief 重置解析器的内部状态，以便解析新文件。
     */
    void reset();

private:
    /**
     * @brief 解析单行文本，并在成功时调用回调函数。
     * @param line 要解析的字符串。
     * @param callback 要调用的回调函数。
     */
    void parseLine(const std::string& line, std::function<void(const ParsedRecord&)> callback); // --- CHANGE: Signature updated

    /**
     * @brief 辅助函数，用于去除字符串两端的空白字符。
     * @param s 输入字符串。
     * @return 去除空白后的字符串。
     */
    std::string trim(const std::string& s);

    // --- CHANGE: The internal vector is no longer needed ---
    // std::vector<ParsedRecord> records_; 

    // 内部状态
    int lineNumber_;
    int parentCounter_;
    int childCounter_;
    int itemCounter_;

    // 上下文追踪
    int currentParentOrder_;
    int currentChildOrder_;

    // 正则表达式定义
    static const std::regex dateRegex_;
    static const std::regex remarkRegex_;
    static const std::regex parentRegex_;
    static const std::regex childRegex_;
    static const std::regex itemRegex_;
};

#endif // BILL_PARSER_H