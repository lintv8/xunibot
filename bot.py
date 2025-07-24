import os
import time
import requests
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, Update
)

# 配置（替换为你的真实信息）
TOKEN = os.getenv("TG_BOT_TOKEN")
PLISIO_API_KEY = "你的Plisio API密钥"  # Plisio后台获取
PLISIO_WALLET = "你的USDT钱包地址"     # 收USDT的地址
BASE_URL = "https://plisio.net/api/v1"  # Plisio API

# 商品数据（虚拟/实物）
SHOP_ITEMS = {
    1: {
        "name": "虚拟商品A",
        "type": "virtual",  # virtual=虚拟，physical=实物
        "price_usdt": 1.0,
        "desc": "自动发货：激活码 ABC123",
    },
    2: {
        "name": "实物商品B",
        "type": "physical",
        "price_usdt": 5.0,
        "desc": "需管理员手动填物流发货",
    }
}

# 订单存储（结构：order_id: {user_id, item_id, status, tx_id, 物流信息}）
ORDERS = {}  # 生产环境建议用数据库（SQLite/MySQL）


### --- 1. 基础命令 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "欢迎使用 USDT 商店机器人！\n"
        "/menu 看商品 → /order 编号 下单 → 支付后等发货～"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "商品列表（USDT 支付）：\n"
    for item_id, item in SHOP_ITEMS.items():
        text += (
            f"编号 {item_id}：{item['name']}\n"
            f"价格：{item['price_usdt']} USDT\n"
            f"描述：{item['desc']}\n\n"
        )
    await update.message.reply_text(text)


### --- 2. 下单 & Plisio 支付 ---
async def create_plisio_payment(amount_usdt, order_id):
    """调用 Plisio API 生成支付链接"""
    data = {
        "api_key": PLISIO_API_KEY,
        "amount": amount_usdt,
        "currency": "USDT",
        "wallet": PLISIO_WALLET,
        "order_id": order_id,
        "description": f"订单 {order_id} 支付",
    }
    try:
        res = requests.post(f"{BASE_URL}/invoices/create", data=data)
        return res.json().get("data", {}).get("invoice_url")
    except Exception as e:
        print(f"Plisio 调用失败: {e}")
        return None

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法：/order 商品编号（如 /order 1）")
        return
    item_id = int(context.args[0])
    if item_id not in SHOP_ITEMS:
        await update.message.reply_text("商品不存在！看 /menu 重新选～")
        return

    user_id = update.effective_user.id
    order_id = f"ORDER_{int(time.time())}"  # 简单生成订单号
    item = SHOP_ITEMS[item_id]

    # 记录待支付订单
    ORDERS[order_id] = {
        "user_id": user_id,
        "item_id": item_id,
        "status": "pending",  # pending/paid/shipped
        "tracking": None,     # 物流信息（实物商品需填）
        "tx_id": None,        # Plisio 交易ID
    }

    # 生成支付链接
    payment_url = await create_plisio_payment(item["price_usdt"], order_id)
    if not payment_url:
        await update.message.reply_text("支付链接创建失败，请重试！")
        del ORDERS[order_id]
        return

    await update.message.reply_text(
        f"请支付 {item['price_usdt']} USDT 完成订单：\n"
        f"→ 支付链接：{payment_url}\n"
        "支付后联系管理员发货（实物需填物流）～"
    )


### --- 3. 管理员操作：确认支付 & 填物流 ---
async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理员指令：/confirm 订单号（标记为已支付）"""
    if not context.args:
        await update.message.reply_text("用法：/confirm 订单号（如 /confirm ORDER_123）")
        return
    order_id = context.args[0]
    if order_id not in ORDERS:
        await update.message.reply_text("订单不存在！")
        return

    ORDERS[order_id]["status"] = "paid"
    await update.message.reply_text(f"订单 {order_id} 已标记为『已支付』，可 /ship 填物流～")

async def ship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理员指令：/ship 订单号 物流单号（实物商品发货）"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("用法：/ship 订单号 物流单号（如 /ship ORDER_123 123456）")
        return
    order_id, tracking_num = context.args[0], context.args[1]
    if order_id not in ORDERS:
        await update.message.reply_text("订单不存在！")
        return

    ORDERS[order_id]["status"] = "shipped"
    ORDERS[order_id]["tracking"] = tracking_num
    user_id = ORDERS[order_id]["user_id"]

    # 通知用户物流信息
    await context.bot.send_message(
        chat_id=user_id,
        text=f"你的订单 {order_id} 已发货！\n"
        f"物流单号：{tracking_num}\n"
        "查询物流：/track 订单号"
    )
    await update.message.reply_text(f"订单 {order_id} 已填物流并通知用户～")


### --- 4. 用户查询物流 ---
async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户指令：/track 订单号（查物流）"""
    if not context.args:
        await update.message.reply_text("用法：/track 订单号（如 /track ORDER_123）")
        return
    order_id = context.args[0]
    if order_id not in ORDERS:
        await update.message.reply_text("订单不存在！")
        return

    tracking_num = ORDERS[order_id].get("tracking")
    if not tracking_num:
        await update.message.reply_text("物流单号未填写，请联系管理员～")
        return

    await update.message.reply_text(f"订单 {order_id} 物流单号：{tracking_num}")


### --- 5. 启动机器人 ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    # 注册命令
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("confirm", confirm_payment))  # 管理员确认支付
    app.add_handler(CommandHandler("ship", ship))                # 管理员填物流
    app.add_handler(CommandHandler("track", track))              # 用户查物流
    
    app.run_polling()
