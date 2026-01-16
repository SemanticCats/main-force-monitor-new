# monitor_v3.py
import os
import json
import akshare as ak
import pandas as pd
import numpy as np
import requests

# 加载配置
from config import SERVERCHAN_SENDKEY, MANUAL_CONCEPTS, MAX_STOCKS_PER_CONCEPT

# 判断是否为手动查询模式
MANUAL_MODE = os.getenv("MANUAL_QUERY", "false").lower() == "true"

# 自动加载监控板块
if os.path.exists("auto_concepts.json"):
    with open("auto_concepts.json", "r") as f:
        MONITOR_CONCEPTS = json.load(f)["MONITOR_CONCEPTS"]
    print(f"🔥 使用自动主线: {MONITOR_CONCEPTS}")
else:
    MONITOR_CONCEPTS = MANUAL_CONCEPTS
    print(f"🟡 使用手动主线: {MONITOR_CONCEPTS}")

def send_wechat(title: str, desp: str = ""):
    if not SERVERCHAN_SENDKEY or "SCT" not in SERVERCHAN_SENDKEY:
        print("⚠️ 未设置有效的 SERVERCHAN_SENDKEY")
        return
    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send",
            data={"title": title, "desp": desp[:3000]}
        )
        print(f"推送结果: {resp.json()}")
    except Exception as e:
        print("推送失败:", e)

def calculate_rsi(series, window=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def detect_stage(symbol, df):
    if len(df) < 60:
        return None, {}, None
    
    close = df['收盘']
    high = df['最高']
    low = df['最低']
    volume = df['成交量']
    
    # 尝试获取流通股本（用于估算换手率）
    turnover_rate = 0
    try:
        stock_info = ak.stock_individual_info_em(symbol=symbol)
        circulating_str = stock_info[stock_info['item'] == '流通股']['value'].iloc[0]
        if '亿' in circulating_str:
            circulating_shares = float(circulating_str.replace('亿', '')) * 1e8
            turnover_rate = (volume.iloc[-1] / circulating_shares) * 100
    except:
        pass  # 无法获取时保持0
    
    # 计算指标
    rsi = calculate_rsi(close).iloc[-1]
    vol_20_avg = volume.tail(20).mean()
    vol_100_avg = volume.rolling(100).mean().iloc[-1] if len(volume) >= 100 else vol_20_avg * 1.2
    
    # ATR(14) 衡量波动
    tr = pd.DataFrame({
        'h-l': high - low,
        'h-pc': abs(high - close.shift(1)),
        'l-pc': abs(low - close.shift(1))
    }).max(axis=1)
    atr_14 = tr.rolling(14).mean().iloc[-1]
    atr_14_prev = tr.rolling(14).mean().iloc[-4]
    atr_expanding = (atr_14 > atr_14_prev * 1.2)
    
    # 估算主力成本区（近30日成交量最大10天）
    recent_30 = df.tail(30).copy()
    top10_vol = recent_30.nlargest(10, '成交量')
    if top10_vol.empty:
        return None, {}, None
    cost_low = top10_vol['收盘'].min()
    cost_high = top10_vol['收盘'].max()
    cost_center = (cost_low + cost_high) / 2
    
    # 近10日成交量加权均价
    recent_10 = df.tail(10)
    weighted_price_10 = (recent_10['收盘'] * recent_10['成交量']).sum() / recent_10['成交量'].sum()
    
    # SCR 近似：价格围绕成本的离散度
    price_std = recent_30['收盘'].std()
    scr_approx = (price_std / cost_center) * 100 if cost_center != 0 else 999
    
    current = close.iloc[-1]
    high_60 = high.tail(60).max()
    
    signals = {
        'symbol': symbol,
        'current': round(current, 2),
        'cost_zone': f"{round(cost_low,2)}–{round(cost_high,2)}",
        'drawdown': round(cost_low * 0.9, 2),
        'target': round(cost_high * 1.3, 2),
        'rsi': round(rsi, 1),
        'scr_approx': round(scr_approx, 1),
        'turnover': round(turnover_rate, 1)
    }
    
    # === 🚀 拉升启动（PDF标准）===
    is_lifting = (
        scr_approx < 12 and
        weighted_price_10 > cost_center * 1.01 and
        current > cost_high * 1.01 and
        volume.iloc[-1] > vol_20_avg * 1.5
    )
    if is_lifting:
        return "🚀 拉升启动", signals, "加仓至80%，设止损于成本区下沿"
    
    # === 📉 主力出货（PDF标准）===
    is_high_position = current > high_60 * 0.95
    high_turnover = turnover_rate > 20
    huge_volume = volume.iloc[-1] > vol_100_avg * 2.5
    price_stagnant = current < high_60 * 1.02
    
    is_distributing = (
        is_high_position and
        atr_expanding and
        (high_turnover or huge_volume) and
        price_stagnant
    )
    if is_distributing:
        action = "⚠️ 出货确认！减仓50%" if turnover_rate < 30 else "🔥 巨量出货！立即清仓"
        return "📉 主力出货", signals, action
    
    # === 其他阶段 ===
    recent_vol = volume.tail(3).mean()
    high_20 = high.iloc[-21:-1].max()
    breakout = (high.tail(3).max() > high_20) and (recent_vol > vol_20_avg * 1.5)
    in_cost = cost_low <= current <= cost_high
    if breakout and in_cost and scr_approx < 15:
        return "📈 主力建仓", signals, "试仓30%"
    
    near_support = current >= cost_low * 0.97
    low_vol = volume.iloc[-1] <= vol_100_avg
    if near_support and rsi <= 50 and low_vol:
        return "🔄 洗盘买点", signals, "加仓20%"
    
    if current < cost_low * 0.95:
        return "💥 破位清仓", signals, "全部卖出"
    
    return None, {}, None

# 加载龙头股
if os.path.exists("auto_leaders.json"):
    with open("auto_leaders.json", "r", encoding="utf-8") as f:
        CONCEPT_LEADERS = json.load(f)
    print("🟢 使用自动龙头股")
else:
    CONCEPT_LEADERS = {
        "低空经济": ["002085", "000099", "300975"],
        "人工智能": ["002230", "300603", "688256"],
        "半导体": ["603986", "688981", "600703"],
        "机器人": ["002380", "300024", "688165"]
    }
    print("🟡 使用手动龙头股")

def main():
    all_signals = []
    full_status = []

    for concept in MONITOR_CONCEPTS:
        stocks = CONCEPT_LEADERS.get(concept, [])
        for symbol in stocks[:MAX_STOCKS_PER_CONCEPT]:
            try:
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
                if df is None or df.empty:
                    continue
                
                stage, sig_data, action = detect_stage(symbol, df)
                status_line = (
                    f"{symbol}（{concept}）| "
                    f"现价:{sig_data.get('current','N/A')} | "
                    f"SCR≈{sig_data.get('scr_approx','N/A')}% | "
                    f"阶段: {stage or '观望'}"
                )
                full_status.append(status_line)
                
                if stage:
                    msg = (
                        f"【{stage}】{symbol}（{concept}）\n"
                        f"现价: {sig_data['current']}元\n"
                        f"主力成本: {sig_data['cost_zone']}元\n"
                        f"最大回撤位: {sig_data['drawdown']}元\n"
                        f"最小目标位: {sig_data['target']}元\n"
                        f"RSI: {sig_data['rsi']} | SCR≈{sig_data['scr_approx']}% | 换手: {sig_data['turnover']}%\n"
                        f"👉 {action}"
                    )
                    all_signals.append(msg)
            except Exception as e:
                error_msg = f"{symbol} 分析失败: {str(e)[:50]}"
                full_status.append(error_msg)

    if MANUAL_MODE:
        title = "【手动查询】主力监控全清单"
        desp = "📊 监控池状态（共{}只）:\n\n".format(len(full_status)) + "\n".join(full_status)
        send_wechat(title, desp)
    else:
        if all_signals:
            title = f"【主力监控】发现 {len(all_signals)} 个信号"
            desp = "\n\n".join(all_signals)
            send_wechat(title, desp)
        else:
            send_wechat("【主力监控】今日无信号", "市场平静，耐心等待。")

if __name__ == "__main__":
    main()
