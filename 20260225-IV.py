# coding=utf-8
"""
普通版QMT专用 · 长端IV大小盘轮动 · 全自动实盘策略
适用：迅投QMT普通版/个人版
功能：每日定时运行、IV计算、自动调仓、全风控、微信推送
"""

import numpy as np
import pandas as pd
import datetime
import time
import requests
from scipy.stats import norm
from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant

# ====================== 【必填配置】 ======================
ACCOUNT_ID     = "你的资金账号"       # 填你的资金账号
PUSHPLUS_TOKEN = "你的pushplus token" # 微信推送token
# 策略参数
RISK_FREE_RATE = 0.02
LONG_TERM_DAYS = 90
IV_RATIO_HIGH  = 1.3
IV_RATIO_LOW   = 1.05

# 标的
LOW_VOL  = ["510050.SH", "510300.SH"]
HIGH_VOL = ["510500.SH", "588000.SH"]
ALL_TARGET = LOW_VOL + HIGH_VOL

# 风控
CASH_RATIO      = 0.1
STOP_LOSS_PCT   = 0.07
MAX_POSITION    = 0.95

# ====================== BS期权定价 & IV ======================
def bs_price(S, K, T, r, sigma, opt_type='call'):
    if sigma <= 0:
        return 0.0
    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    d2 = d1 - sigma*np.sqrt(T)
    if opt_type == 'call':
        return S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
    else:
        return K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)

def calculate_iv(price, S, K, T, r, opt_type='call'):
    if T <= 0 or price <= 0:
        return np.nan
    sig_low, sig_high = 0.001, 5.0
    for _ in range(80):
        sig = (sig_low + sig_high) / 2
        p = bs_price(S, K, T, r, sig, opt_type)
        if abs(p - price) < 1e-4:
            return sig
        sig_high = sig if p > price else sig_low
    return (sig_low + sig_high) / 2

# ====================== 指数IV计算 ======================
def get_index_iv(underlying, opt_prefix):
    options = xtdata.get_instrument_list(opt_prefix)
    S = xtdata.get_last_price(underlying)
    if S <= 0 or not options:
        return np.nan

    ivs, weights = [], []
    now = datetime.datetime.now()

    for code in options:
        info = xtdata.get_instrument_detail(code)
        if not info:
            continue
        opt_t = info.get('OptionType')
        strike = info.get('StrikePrice')
        expire = str(info.get('ExpireDate'))
        price = xtdata.get_last_price(code)

        try:
            edt = datetime.datetime.strptime(expire, '%Y%m%d')
            days = (edt - now).days
        except:
            continue

        if abs(days - LONG_TERM_DAYS) > 20:
            continue

        T = days / 365
        iv = calculate_iv(price, S, strike, T, RISK_FREE_RATE,
                          'call' if opt_t == 1 else 'put')
        if np.isnan(iv) or iv <= 0:
            continue

        w = 1.0 / (abs(np.log(S/strike)) + 0.001)
        ivs.append(iv)
        weights.append(w)

    if not ivs:
        return np.nan
    return np.sum(np.array(ivs) * np.array(weights)) / np.sum(weights)

# ====================== 信号生成 ======================
def get_signal_and_weight():
    iv50  = get_index_iv("000016.SH", "HO")
    iv300 = get_index_iv("000300.SH", "IO")
    iv1000= get_index_iv("000852.SH", "MO")

    if np.isnan(iv300) or np.isnan(iv1000):
        return "IV数据获取失败", 0.5, iv50, iv300, iv1000

    ratio = iv1000 / iv300
    if ratio >= IV_RATIO_HIGH:
        return f"小盘IV过高({ratio:.2f}) → 重仓低波", 0.1, iv50, iv300, iv1000
    elif ratio <= IV_RATIO_LOW:
        return f"小盘IV偏低({ratio:.2f}) → 加仓小盘", 0.8, iv50, iv300, iv1000
    else:
        return f"均衡配置({ratio:.2f})", 0.5, iv50, iv300, iv1000

# ====================== 自动调仓 ======================
def rebalance(xt, acc, high_weight):
    asset = xt.query_stock_asset(acc)
    total_asset = asset.total_asset
    cash = asset.cash
    invest_amt = total_asset * (1 - CASH_RATIO)
    low_weight = 1 - high_weight

    # 清仓非目标持仓
    for pos in xt.query_stock_positions(acc):
        code = pos.stock_code
        vol = pos.can_use_volume
        if code not in ALL_TARGET and vol > 0:
            xt.order_stock(acc, code, xtconstant.STOCK_SELL, vol, 0, 0, 0, "清仓", "")

    # 止损
    for pos in xt.query_stock_positions(acc):
        code = pos.stock_code
        cost = pos.avg_price
        vol = pos.can_use_volume
        if cost <= 0 or vol <= 0:
            continue
        nowp = xtdata.get_last_price(code)
        if nowp / cost - 1 < -STOP_LOSS_PCT:
            xt.order_stock(acc, code, xtconstant.STOCK_SELL, vol, 0,0,0,"止损","")

    # 全部卖出再平衡
    for pos in xt.query_stock_positions(acc):
        code = pos.stock_code
        vol = pos.can_use_volume
        if code in ALL_TARGET and vol > 0:
            xt.order_stock(acc, code, xtconstant.STOCK_SELL, vol, 0,0,0,"再平衡","")
    time.sleep(1)

    # 买入低波
    for code in LOW_VOL:
        amt = invest_amt * low_weight / len(LOW_VOL)
        p = xtdata.get_last_price(code)
        if p > 0:
            vol = int(amt / p // 100 * 100)
            if vol >= 100:
                xt.order_stock(acc, code, xtconstant.STOCK_BUY, vol, 0,0,0,"买入低波","")

    # 买入高波
    for code in HIGH_VOL:
        amt = invest_amt * high_weight / len(HIGH_VOL)
        p = xtdata.get_last_price(code)
        if p > 0:
            vol = int(amt / p // 100 * 100)
            if vol >= 100:
                xt.order_stock(acc, code, xtconstant.STOCK_BUY, vol, 0,0,0,"买入高波","")

    return "调仓完成"

# ====================== 每日执行任务 ======================
def daily_task():
    print("\n========================================")
    print("策略运行时间：", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("========================================")

    # 计算信号
    try:
        signal_msg, high_w, iv50, iv300, iv1000 = get_signal_and_weight()
    except Exception as e:
        print(f"信号计算失败: {e}")
        return

    # 准备推送内容
    content = f"""
【QMT-IV轮动策略日报】
时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
信号：{signal_msg}
上证50IV：{iv50:.4f}
沪深300IV：{iv300:.4f}
中证1000IV：{iv1000:.4f}
小盘权重：{high_w:.0%}
"""
    print(content)

    # 检查账号
    if ACCOUNT_ID == "你的资金账号":
        print("[提示] ACCOUNT_ID 未配置，跳过实盘调仓。")
        return

    # 连接QMT并调仓
    try:
        print("正在连接QMT执行调仓...")
        xt = XtQuantTrader()
        cb = XtQuantTraderCallback()
        xt.register(cb)
        xt.connect()
        
        acc = StockAccount(ACCOUNT_ID, "STOCK")
        result = rebalance(xt, acc, high_w)
        xt.disconnect()
        
        print(f"执行结果: {result}")
        content += f"执行结果：{result}\n"
    except Exception as e:
        print(f"调仓执行失败: {e}")
        content += f"执行结果：调仓失败({e})\n"

# ====================== 主入口 ======================
if __name__ == '__main__':
    try:
        daily_task()
    except Exception as e:
        print(f"\n[错误] 策略运行出错: {e}")
    print("\n[完成] 一次性运行结束。")
