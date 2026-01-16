# update_leaders.py
import akshare as ak
import json
from datetime import datetime, timedelta

try:
    with open("auto_concepts.json", "r") as f:
        MONITOR_CONCEPTS = json.load(f)["MONITOR_CONCEPTS"]
except:
    from config import MANUAL_CONCEPTS
    MONITOR_CONCEPTS = MANUAL_CONCEPTS

KEYWORD_TO_CONCEPT = {
    "低空": "低空经济", "eVTOL": "低空经济",
    "AI": "人工智能", "智能": "人工智能",
    "芯片": "半导体", "半导体": "半导体",
    "机器人": "机器人", "人形": "机器人",
    "6G": "6G", "信创": "信创"
}

def get_recent_zt_stocks(days=3):
    date_str = (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")
    try:
        df = ak.stock_zt_pool_em(date=date_str)
        return df[['代码', '名称']]
    except:
        return None

def assign_concept_by_name(df):
    result = {}
    for _, row in df.iterrows():
        code, name = row['代码'], row['名称']
        for kw, concept in KEYWORD_TO_CONCEPT.items():
            if kw in name and concept in MONITOR_CONCEPTS:
                if concept not in result:
                    result[concept] = []
                if code not in result[concept]:
                    result[concept].append(code)
                break
    return result

def main():
    df = get_recent_zt_stocks(3)
    if df is None or df.empty:
        print("❌ 无涨停数据")
        return
    
    leaders = assign_concept_by_name(df)
    with open("auto_leaders.json", "w", encoding="utf-8") as f:
        json.dump(leaders, f, ensure_ascii=False, indent=2)
    print("✅ 自动龙头股已生成:", leaders)

if __name__ == "__main__":
    main()
