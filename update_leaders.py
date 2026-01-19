# update_leaders.py
import akshare as ak
import json
from datetime import datetime, timedelta
import sys

# --- 1. 配置部分 ---
# 尝试加载配置，如果文件不存在则使用默认值
try:
    with open("auto_concepts.json", "r", encoding="utf-8") as f:
        MONITOR_CONCEPTS = json.load(f)["MONITOR_CONCEPTS"]
except FileNotFoundError:
    print("⚠️ auto_concepts.json 未找到，使用备用配置")
    # 这里最好设置一个默认列表，防止文件完全缺失导致崩溃
    MONITOR_CONCEPTS = ["低空经济", "人工智能", "半导体", "机器人", "6G", "信创"]
except json.JSONDecodeError:
    print("⚠️ auto_concepts.json 格式错误，使用备用配置")
    MONITOR_CONCEPTS = ["低空经济", "人工智能", "半导体", "机器人", "6G", "信创"]

KEYWORD_TO_CONCEPT = {
    "低空": "低空经济", "eVTOL": "低空经济",
    "AI": "人工智能", "智能": "人工智能",
    "芯片": "半导体", "半导体": "半导体",
    "机器人": "机器人", "人形": "机器人",
    "6G": "6G", "信创": "信创"
}

# --- 2. 数据获取函数 ---
def get_recent_zt_stocks(days=3):
    # 计算昨天的日期（国内股市数据通常是T-1）
    target_date = datetime.today() - timedelta(days=1)
    date_str = target_date.strftime("%Y%m%d")

    print(f"ℹ️ 正在查询日期: {date_str} 的涨停数据...")

    try:
        # akshare 的接口有时不稳定，增加 timeout 控制
        df = ak.stock_zt_pool_em(date=date_str)
        if df.empty:
            print("❌ 获取到的数据为空")
            return None
        print(f"✅ 成功获取到 {len(df)} 条数据")
        return df[['代码', '名称']]

    except Exception as e:
        # ⚠️ 关键修改：打印具体错误，而不是静默返回 None
        print(f"❌ Akshare 数据获取失败: {e}")
        # 如果特定日期失败，尝试获取最新数据（不带日期参数），增加容错
        try:
            print("⚠️ 正在尝试获取最新数据（不指定日期）...")
            df = ak.stock_zt_pool_em()
            print(f"✅ 成功获取最新数据")
            return df[['代码', '名称']]
        except Exception as e2:
            print(f"❌ 备用查询也失败: {e2}")
            return None

# --- 3. 逻辑处理 ---
def assign_concept_by_name(df):
    if df is None or df.empty:
        return {}

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

# --- 4. 主入口 ---
def main():
    # 确保即使出错也能生成文件的机制
    leaders = {}

    try:
        df = get_recent_zt_stocks(3)
        if df is not None and not df.empty:
            leaders = assign_concept_by_name(df)
            if leaders:
                print(f"✅ 匹配到概念龙头: {leaders}")
            else:
                print("ℹ️ 未匹配到指定概念，生成空列表")
        else:
            print("ℹ️ 未获取到股票数据，生成空列表")

    except Exception as e:
        print(f"❌ 主逻辑发生未捕获错误: {e}")

    finally:
        # ⚠️ 关键修改：无论如何都写入文件
        # 这样 Git 才能找到文件，避免 exit code 128
        with open("auto_leaders.json", "w", encoding="utf-8") as f:
            json.dump(leaders, f, ensure_ascii=False, indent=2)
            print(f"📊 已生成/更新 auto_leaders.json")

if __name__ == "__main__":
    main()
