import akshare as ak
import json
from datetime import datetime, timedelta, timezone

# ================= 配置区域 =================
# 尝试加载监控概念列表
try:
    with open("auto_concepts.json", "r", encoding="utf-8") as f:
        MONITOR_CONCEPTS = json.load(f)["MONITOR_CONCEPTS"]
    print(f"✅ 成功加载 auto_concepts.json，监控概念: {MONITOR_CONCEPTS}")
except FileNotFoundError:
    print("⚠️ 未找到 auto_concepts.json，使用默认概念列表")
    MONITOR_CONCEPTS = [
        "低空经济", "人工智能", "半导体", "机器人", "6G", "信创"
    ]

# 关键词映射
KEYWORD_TO_CONCEPT = {
    "低空": "低空经济", "eVTOL": "低空经济",
    "AI": "人工智能", "智能": "人工智能",
    "芯片": "半导体", "半导体": "半导体",
    "机器人": "机器人", "人形": "机器人",
    "6G": "6G", "信创": "信创"
}

# ================= 函数定义 =================
def get_recent_zt_stocks(days=3):
    """
    获取最近 days 天内的涨停股数据
    使用北京时间，避免时区问题
    """
    # 强制设置为北京时间
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz)
    
    # 循环查找最近有数据的交易日（防止周末或节假日无数据）
    for i in range(1, days + 1):
        target_date = today - timedelta(days=i)
        date_str = target_date.strftime("%Y%m%d")
        
        print(f"🔍 正在尝试获取日期数据: {date_str} ...")
        try:
            # Akshare 的接口有时不稳定，加上超时处理
            df = ak.stock_zt_pool_em(date=date_str)
            if not df.empty:
                print(f"✅ 获取到 {len(df)} 条涨停数据")
                return df[['代码', '名称']]
        except Exception as e:
            print(f"❌ 获取 {date_str} 数据失败: {e}")
    
    print("ℹ️ 近期无涨停数据")
    return None

def assign_concept_by_name(df):
    """根据名称匹配概念"""
    result = {}
    if df is None:
        return result
        
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

# ================= 主程序 =================
def main():
    leaders = {} # 默认结果为空字典
    
    try:
        df = get_recent_zt_stocks(5) # 增加查找范围到5天，提高成功率
        leaders = assign_concept_by_name(df)
        
    except Exception as e:
        print(f"❌ 脚本执行发生严重错误: {e}")
        # 即使报错，也确保生成文件，防止 Git 报错
        leaders = {}

    # 强制写入文件
    filename = "auto_leaders.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(leaders, f, ensure_ascii=False, indent=2)
    
    if leaders:
        print(f"✅ 成功生成文件: {filename}")
        print(f"📊 内容: {leaders}")
    else:
        print(f"🟡 生成空文件 (可能是休市或网络原因): {filename}")

if __name__ == "__main__":
    main()
