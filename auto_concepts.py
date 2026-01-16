# auto_concepts.py
import akshare as ak
import pandas as pd
import json
from collections import Counter

INDUSTRY_KEYWORDS = {
    "电力设备": "新能源",
    "汽车零部件": "低空经济",
    "计算机设备": "人工智能",
    "半导体": "半导体",
    "通用设备": "机器人",
    "通信设备": "6G",
    "软件开发": "信创",
    "医疗器械": "医药",
    "光学光电子": "消费电子",
}

def get_top_concepts(days=3, top_n=4):
    concept_counter = Counter()
    
    for i in range(days):
        try:
            date_str = (pd.Timestamp.today() - pd.Timedelta(days=i+1)).strftime("%Y%m%d")
            df = ak.stock_zt_pool_em(date=date_str)
            if df is None or df.empty:
                continue
            
            for _, row in df.iterrows():
                industry = str(row.get('所属行业', ''))
                matched = False
                for kw, concept in INDUSTRY_KEYWORDS.items():
                    if kw in industry:
                        concept_counter[concept] += 1
                        matched = True
                        break
                if not matched:
                    name = str(row.get('名称', ''))
                    if 'AI' in name or '智能' in name:
                        concept_counter["人工智能"] += 1
                    elif '机器人' in name or '人形' in name:
                        concept_counter["机器人"] += 1
        except:
            continue
    
    top_concepts = [concept for concept, _ in concept_counter.most_common(top_n)]
    if len(top_concepts) < 4:
        default = ["低空经济", "人工智能", "半导体", "机器人"]
        for c in default:
            if c not in top_concepts:
                top_concepts.append(c)
            if len(top_concepts) >= 4:
                break
    
    return top_concepts[:4]

def main():
    concepts = get_top_concepts()
    result = {"MONITOR_CONCEPTS": concepts}
    with open("auto_concepts.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ 自动识别主线: {concepts}")

if __name__ == "__main__":
    main()
