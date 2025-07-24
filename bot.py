import os
from telegram.ext import ApplicationBuilder, CommandHandler

# 从环境变量读 TG_BOT_TOKEN（Railway 里配的变量名）
TOKEN = os.getenv("TG_BOT_TOKEN")  

# 初始化机器人
app = ApplicationBuilder().token(TOKEN).build()  

# 定义 /start 命令：用户发 /start 时回复
async def start(update, context):
    await update.message.reply_text("Bot 已部署成功！发 /start 测试～")

# 注册命令处理器
app.add_handler(CommandHandler("start", start))  

# 启动机器人（轮询监听 TG 消息）
if __name__ == "__main__":
    app.run_polling()
