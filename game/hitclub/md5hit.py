import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from game.hitclub.notify_hitmd5 import monitor_csv_md5
from lenh.config import (
    db, remove_from_old_model, logger, ACCOUNT_FILE,
    model_users, running_tasks, SUPPORT_LINK, is_banned
)
from datetime import datetime

# Khóa để đồng bộ truy cập model_users và running_tasks
model_users_lock = asyncio.Lock()

async def md5hit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /md5hit"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    try:
        if is_banned(user_id):
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        accounts = db.load_json(ACCOUNT_FILE)
        user_info = next(
            (info for u, info in accounts.items() if info.get("user_id") == user_id or info.get("chat_id") == user_id),
            None
        )
        if not user_info:
            await update.message.reply_text(
                f"❌ *DuyWin*: Tài khoản của bạn chưa được đăng ký! Hãy sử dụng /start để đăng ký.",
                parse_mode="Markdown"
            )
            return

        if "md5hit" not in user_info.get("model", []):
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn cần mua Model md5hit bằng /buymodel md5hit hoặc sử dụng key!",
                parse_mode="Markdown"
            )
            return

        expiry = user_info.get("model_expiry", {}).get("md5hit")
        now = datetime.now()
        if expiry:
            try:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                if expiry_date < now:
                    await update.message.reply_text(
                        f"❌ *DuyWin*: Model md5hit của bạn đã hết hạn vào {expiry}! Mua lại bằng /buymodel md5hit.",
                        parse_mode="Markdown"
                    )
                    return
                logger.info(f"Model md5hit của user_id {user_id} còn hạn đến {expiry}")
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho model md5hit của {username}: {expiry}")
                await update.message.reply_text(
                    f"❌ *DuyWin*: Lỗi dữ liệu thời hạn model. Liên hệ hỗ trợ: {SUPPORT_LINK}",
                    parse_mode="Markdown"
                )
                return

        remove_from_old_model(user_id)

        async with model_users_lock:
            model_users.setdefault("md5hit", set()).add(user_id)
            logger.info(f"Đã thêm user_id {user_id} vào model_users['md5hit']. Hiện tại: {model_users['md5hit']}")

            if "md5hit" not in running_tasks:
                running_tasks["md5hit"] = asyncio.create_task(monitor_csv_md5(context.bot, "md5hit"))
                logger.info(f"Đã khởi động task cho model md5hit")
            else:
                logger.info(f"Task cho model md5hit đã tồn tại: {running_tasks['md5hit']}")

        await update.message.reply_text(
            f"✅ *DuyWin*: Bạn đã tham gia Model md5hit! Bạn sẽ nhận được dự đoán MD5 với xác suất bẻ cầu từ bot.",
            parse_mode="Markdown"
        )
 
    except Exception as e:
        logger.exception(f"Lỗi trong hàm md5hit_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi khởi động Model md5hit. Vui lòng thử lại sau hoặc liên hệ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )