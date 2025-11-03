from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import check_ban, logger, model_users, running_tasks, escape_markdown_safe, SUPPORT_LINK

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return

    user = update.message.from_user
    chat_id = update.message.chat_id
    username = user.username or f"ID_{user.id}"

    try:
        stopped = False
        for model in model_users:
            if chat_id in model_users[model]:
                model_users[model].discard(chat_id)
                logger.info(f"Đã xóa chat_id {chat_id} khỏi model_users['{model}']. Hiện tại: {model_users[model]}")
                if not model_users[model] and model in running_tasks:
                    running_tasks[model].cancel()
                    del running_tasks[model]
                    logger.info(f"Đã hủy task cho model {model}")
                stopped = True

        if stopped:
            success_message = escape_markdown_safe("✅ *DuyWin*: Bot đã dừng gửi tin nhắn dự đoán cho bạn!")
            try:
                await update.message.reply_text(success_message, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                plain_message = success_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                await update.message.reply_text(plain_message, parse_mode=None)
        else:
            error_message = escape_markdown_safe("🤔 *DuyWin*: Bot chưa được kích hoạt gửi dự đoán cho bạn!")
            try:
                await update.message.reply_text(error_message, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                plain_message = error_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                await update.message.reply_text(plain_message, parse_mode=None)

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /stop cho {username} (chat_id: {chat_id}): {e}")
        error_message = escape_markdown_safe(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}"
        )
        try:
            await update.message.reply_text(error_message, parse_mode="MarkdownV2")
        except Exception as e2:
            logger.error(f"Phân tích MarkdownV2 thất bại trong thông báo lỗi: {e2}. Gửi văn bản thuần túy.")
            await update.message.reply_text(
                f"😓 DuyWin: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode=None
            )