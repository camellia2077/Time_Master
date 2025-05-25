# 1. 定义父级类别及其允许的子活动标签
# PARENT_CATEGORIES 结构: { "父类别前缀": {"完整的子标签1", "完整的子标签2", ...} }

PARENT_CATEGORIES = {
    "code": {
        "code_time-master",
        "code_weibo",
        "code_binary",
        "code_ascii",
    },
    "routine": 
    {
        "routine_grooming",
        "routine_bath",
        "routine_toilet",
        "routine_washing",
        "routine_express",
    },
    "study": 
    {
        "study_computer_algorithm",
        "study_computer_composition",
        "study_computer_os",
        "study_computer_config",
        "study_english_word",

        "study_english_article",
        "study_english_translate",
        "study_english_listening",
        "study_english_method",

        "study_math_calculus",
        "study_math_calculus_derivative",
        "study_math_calculus_definite-integral",
        "study_math_linear-algebra",
        "study_math_probability",
        "study_math_calculus_lhospital",
        "study_math_calculus_taylor"
    },
    "break": 
    {
        "break_unknown",
        "break_allday",
    },

    "rest": 
    {
        "rest_masturbation",
        "rest_short",
        "rest_medium",
        "rest_long",
    },

    "exercise": 
    {
        "exercise_cardio",
        "exercise_anaerobic",
        "exercise_both",
    },

    "sleep": 
    {
        "sleep_day",
        "sleep_night",
    },


    "insomnia": 
    {
        "insomnia_medium",
        "insomnia_short",
        "insomnia_long",
    },

    "recreation": 
    {
        "recreation_game_clash-royale",
        "recreation_game_overwatch",
        "recreation_game_minecraft",

        "recreation_bilibili",
        "recreation_zhihu",
        "recreation_douyin",
        "recreation_weibo",
        "recreation_qq",
        "recreation_mix",
        "recreation_pet",
        "recreation_movie",
        "recreation_other",
    },

    "arrange": 
    {
        "arrange_onenote_time",
        "arrange_file",
        "arrange_packingup",
    },

    "other": 
    {
        "other_learndriving",
        "other_school",
        "other_transfer-book-to-pdf",
        "other_housework",
        "other_searching_redmibuds4pro",
        "other_fix",
    },

    "meal": 
    {
        "meal_short",
        "meal_medium",
        "meal_long",
        "meal_feast",
    },

    # 注意：根据您的要求，所有有效的活动标签都必须属于这里定义的类别。
    # 如果有其他类别的标签（如 study_xxx, rest_xxx），您也需要在这里定义它们，
    # 或者调整下面的校验逻辑以允许不在这些特定父类别下的其他标签（如果需要）。
    # 目前的逻辑是：只有 PARENT_CATEGORIES 中定义的 code_* 和 routine_* 是有效的。
}