import asyncio
from telegram import Update
from telegram.ext import ContextTypes
# Import monitor_csv_and_notify chỉ khi cần
try:
    from lenh.monitor_csv_and_notify import monitor_csv_and_notify
except ImportError:
    monitor_csv_and_notify = None
from lenh.config import db, remove_from_old_model, logger, ACCOUNT_FILE


async def modelvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running_tasks, model_users
    username = update.message.from_user.username or str(update.message.from_user.id)
    chat_id = update.message.chat_id
    accounts = db.load_json(ACCOUNT_FILE)

    if username not in accounts or accounts[username]["model"] != "vip":
        await update.message.reply_text("Bạn cần mua Model VIP bằng /buymodel vip hoặc sử dụng key!")
        return

    remove_from_old_model(chat_id)
    model_users["vip"].add(chat_id)
    logger.info(f"Đã thêm chat_id {chat_id} vào model_users['vip']. Hiện tại: {model_users['vip']}")
    if "vip" not in running_tasks:
        if monitor_csv_and_notify:
            running_tasks["vip"] = asyncio.create_task(monitor_csv_and_notify(context.bot, "vip"))
            logger.info(f"Đã khởi động task cho model vip")
        else:
            logger.warning(f"monitor_csv_and_notify không khả dụng cho model vip")
    await update.message.reply_text("Bot đã bắt đầu với Model VIP! Đang chờ kết quả và dự đoán...")