from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import check_ban, logger, model_users, running_tasks, ADMIN_IDS, escape_markdown_safe, SUPPORT_LINK

async def stopall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_ban(update, context):
        return

    user = update.message.from_user
    chat_id = update.message.chat_id
    username = user.username or f"ID_{user.id}"
    args = context.args
    is_admin = user.id in ADMIN_IDS

    try:
        if is_admin and args and args[0].isdigit():
            target_chat_id = int(args[0])
            models_to_stop = args[1:] if len(args) > 1 else []
            return await stop_models_for_user(update, context, target_chat_id, models_to_stop, username, is_admin=True)
        return await stop_models_for_user(update, context, chat_id, args, username, is_admin=False)

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /stopall cho {username} (chat_id: {chat_id}): {e}")
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

async def stop_models_for_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_chat_id: int, models_to_stop: list, username: str, is_admin: bool):
    valid_models = set(model_users.keys())
    stopped_models = []
    invalid_models = []

    if not models_to_stop:
        for model in valid_models:
            if target_chat_id in model_users[model]:
                model_users[model].discard(target_chat_id)
                stopped_models.append(model)
                logger.info(f"Đã xóa chat_id {target_chat_id} khỏi model_users['{model}']. Hiện tại: {model_users[model]}")
                if not model_users[model] and model in running_tasks:
                    running_tasks[model].cancel()
                    del running_tasks[model]
                    logger.info(f"Đã hủy task cho model {model}")
    else:
        for model in models_to_stop:
            model = model.lower()
            if model in valid_models:
                if target_chat_id in model_users[model]:
                    model_users[model].discard(target_chat_id)
                    stopped_models.append(model)
                    logger.info(f"Đã xóa chat_id {target_chat_id} khỏi model_users['{model}']. Hiện tại: {model_users[model]}")
                    if not model_users[model] and model in running_tasks:
                        running_tasks[model].cancel()
                        del running_tasks[model]
                        logger.info(f"Đã hủy task cho model {model}")
            else:
                invalid_models.append(model)

    response = ""
    if stopped_models:
        models_str = escape_markdown_safe(", ".join(stopped_models).capitalize())
        if is_admin:
            response += escape_markdown_safe(f"✅ *DuyWin*: Đã dừng các model *{models_str}* cho chat_id {target_chat_id}!")
        else:
            response += escape_markdown_safe(f"✅ *DuyWin*: Đã dừng các model *{models_str}* cho bạn!")
    if invalid_models:
        response += escape_markdown_safe(f"⚠️ *Các model không hợp lệ*: {', '.join(invalid_models)}")
    
    if not stopped_models and not invalid_models:
        if is_admin:
            response = escape_markdown_safe(f"🤔 *DuyWin*: Không có model nào đang chạy cho chat_id {target_chat_id}!")
        else:
            response = escape_markdown_safe(f"🤔 *DuyWin*: Bạn chưa kích hoạt model nào! Dùng /kichhoat để kích hoạt.")

    try:
        await update.message.reply_text(response, parse_mode="MarkdownV2")
    except Exception as e:
        logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
        plain_response = response.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
        await update.message.reply_text(plain_response, parse_mode=None)

    if is_admin and stopped_models:
        safe_models_str = escape_markdown_safe(", ".join(stopped_models).capitalize())
        for admin_id in ADMIN_IDS:
            if admin_id != update.message.from_user.id:
                admin_message = escape_markdown_safe(
                    f"🛑 Admin @{username} đã dừng các model *{safe_models_str}* cho chat_id {target_chat_id}!"
                )
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                    plain_message = admin_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=plain_message,
                        parse_mode=None
                    )