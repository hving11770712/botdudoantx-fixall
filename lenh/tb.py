import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden, RetryAfter
from lenh.config import logger, ADMIN_IDS, ACCOUNT_FILE, BANID_FILE, db, model_users, check_ban, SUPPORT_LINK, escape_markdown_safe, update_username
from datetime import datetime

async def tb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /tb để admin gửi thông báo đến người dùng hoặc nhóm model."""
    if await check_ban(update, context):
        return

    admin_id = update.effective_user.id
    admin_username = update.effective_user.username.lstrip('@') if update.effective_user.username else str(admin_id)
    if admin_id not in ADMIN_IDS:
        await update.message.reply_text(
            f"🚫 *DuyWin*: Chỉ admin mới được dùng lệnh này\\! 🔐",
            parse_mode="MarkdownV2"
        )
        logger.warning(f"User @{admin_username} (user_id: {admin_id}) không phải admin, cố gắng dùng /tb")
        return

    if not context.args:
        usage_message = escape_markdown_safe(
            "📢 *DuyWin*: Vui lòng nhập:\n"
            "🔹 /tb all <nội dung> - Gửi đến tất cả người dùng\n"
            "🔹 /tb basic <nội dung> - Gửi đến người dùng model basic\n"
            "🔹 /tb vip <nội dung> - Gửi đến người dùng model vip\n"
            "🔹 /tb md5hit <nội dung> - Gửi đến người dùng model md5hit\n"
            "🔹 /tb 789club <nội dung> - Gửi đến người dùng model 789club\n"
            "🔹 /tb <chat_id> <nội dung> - Gửi đến một người dùng"
        )
        try:
            await update.message.reply_text(usage_message, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
            plain_message = usage_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
            await update.message.reply_text(plain_message, parse_mode=None)
        return

    target = context.args[0].lower()
    message = " ".join(context.args[1:]) if len(context.args) > 1 else None

    if target == "all" and not message:
        default_message = escape_markdown_safe(
            "📢 *Thông báo quan trọng từ DuyWin* 🚀\n\n"
            "Kính gửi người dùng,\n\n"
            "Chúng tôi đã ra mắt bot mới để mang đến trải nghiệm tốt hơn và hỗ trợ nhanh chóng hơn: @DuyWin_Bot\n\n"
            "👉 *Hãy chuyển sang bot mới ngay hôm nay!*\n\n"
            "Hướng dẫn chuyển đổi:\n"
            "- Nhấn vào link: https://t.me/duywin_bot\n"
            "- Nhấn Start để kích hoạt bot mới\n"
            "- Liên hệ @duyduy221212 nếu cần hỗ trợ\n\n"
            "⚠️ *Lưu ý*: Bot cũ @Sunwinver1_bot sẽ ngừng hoạt động từ *27/04/2025*\n"
            "Hãy chuyển đổi sớm để không bỏ lỡ bất kỳ cập nhật nào!\n\n"
            "Cảm ơn sự đồng hành của bạn! ❤️"
        )
        message = default_message
        logger.debug(f"Prepared default message: {message}")

    if not message:
        error_message = escape_markdown_safe("⚠️ *DuyWin*: Vui lòng cung cấp nội dung thông báo!")
        try:
            await update.message.reply_text(error_message, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
            plain_message = error_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
            await update.message.reply_text(plain_message, parse_mode=None)
        return

    safe_message = escape_markdown_safe(message)
    accounts = db.load_json(ACCOUNT_FILE)
    invalid_chat_ids = set()
    sent_count = 0
    failed_count = 0

    async def send_message_with_delay(chat_id, text):
        nonlocal sent_count, failed_count
        try:
            logger.debug(f"Sending message to chat_id {chat_id}: {text}")
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="MarkdownV2"
            )
            sent_count += 1
            return True
        except Forbidden:
            invalid_chat_ids.add(chat_id)
            username = next((u for u, v in accounts.items() if v.get("chat_id") == chat_id), f"ID_{chat_id}")
            logger.warning(f"Người dùng {username} (chat_id: {chat_id}) đã chặn bot")
            failed_count += 1
            return False
        except RetryAfter as e:
            logger.warning(f"Vượt giới hạn Telegram, chờ {e.retry_after} giây")
            await asyncio.sleep(e.retry_after)
            return await send_message_with_delay(chat_id, text)
        except Exception as e:
            if "Chat not found" in str(e):
                invalid_chat_ids.add(chat_id)
                logger.warning(f"Chat_id {chat_id} không tồn tại")
            else:
                logger.error(f"Lỗi khi gửi tin nhắn đến chat_id {chat_id}: {e}")
            failed_count += 1
            return False

    try:
        if target == "all":
            tasks = []
            for key, info in accounts.items():
                chat_id = info.get("chat_id")
                user_id = info.get("user_id", chat_id)
                if chat_id:
                    # Sử dụng key làm username mặc định, hoặc fallback sang ID_{user_id}
                    current_username = info.get("username", f"ID_{user_id}")
                    update_username(accounts, str(user_id), current_username, user_id)
                    tasks.append((chat_id, safe_message))
            db.save_json(ACCOUNT_FILE, accounts)

            for chat_id, msg in tasks:
                if await send_message_with_delay(chat_id, msg):
                    await asyncio.sleep(0.1)

            report = escape_markdown_safe(
                f"📢 *DuyWin*: Kết quả gửi thông báo đến tất cả người dùng:\n"
                f"✅ Gửi thành công: {sent_count} người dùng\n"
                f"❌ Thất bại: {failed_count} người dùng\n"
            )
            if invalid_chat_ids:
                report += escape_markdown_safe(f"🗑️ Đã xóa {len(invalid_chat_ids)} chat_id không hợp lệ.")
            try:
                await update.message.reply_text(report, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                plain_report = report.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                await update.message.reply_text(plain_report, parse_mode=None)

        elif target in model_users:
            tasks = [(chat_id, safe_message) for chat_id in model_users.get(target, set())]
            for chat_id, msg in tasks:
                if await send_message_with_delay(chat_id, msg):
                    await asyncio.sleep(0.1)

            report = escape_markdown_safe(
                f"📢 *DuyWin*: Kết quả gửi thông báo đến model {target.capitalize()}:\n"
                f"✅ Gửi thành công: {sent_count} người dùng\n"
                f"❌ Thất bại: {failed_count} người dùng\n"
            )
            if invalid_chat_ids:
                report += escape_markdown_safe(f"🗑️ Đã xóa {len(invalid_chat_ids)} chat_id không hợp lệ.")
            try:
                await update.message.reply_text(report, parse_mode="MarkdownV2")
            except Exception as e:
                logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                plain_report = report.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                await update.message.reply_text(plain_report, parse_mode=None)

        else:
            try:
                chat_id = int(target)
                if await send_message_with_delay(chat_id, safe_message):
                    success_message = escape_markdown_safe(f"✅ *DuyWin*: Đã gửi thông báo đến chat_id {chat_id}.")
                    try:
                        await update.message.reply_text(success_message, parse_mode="MarkdownV2")
                    except Exception as e:
                        logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                        plain_message = success_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                        await update.message.reply_text(plain_message, parse_mode=None)
                else:
                    error_message = escape_markdown_safe(f"❌ *DuyWin*: Không thể gửi đến chat_id {chat_id}: Người dùng chặn bot hoặc chat không tồn tại.")
                    try:
                        await update.message.reply_text(error_message, parse_mode="MarkdownV2")
                    except Exception as e:
                        logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                        plain_message = error_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                        await update.message.reply_text(plain_message, parse_mode=None)
            except ValueError:
                error_message = escape_markdown_safe(
                    "⚠️ *DuyWin*: Chat_id không hợp lệ! Vui lòng nhập số hoặc model (all, basic, vip, md5hit, 789club)."
                )
                try:
                    await update.message.reply_text(error_message, parse_mode="MarkdownV2")
                except Exception as e:
                    logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
                    plain_message = error_message.replace('\\*', '').replace('\\_', '').replace('\\`', '').replace('\\', '')
                    await update.message.reply_text(plain_message, parse_mode=None)

        if invalid_chat_ids:
            for key, info in list(accounts.items()):
                if info.get("chat_id") in invalid_chat_ids:
                    logger.info(f"Xóa chat_id {info.get('chat_id')} của {key} khỏi accounts")
                    del accounts[key]
            db.save_json(ACCOUNT_FILE, accounts)

            for model in model_users:
                for chat_id in invalid_chat_ids:
                    if chat_id in model_users[model]:
                        model_users[model].discard(chat_id)
                        logger.info(f"Xóa chat_id {chat_id} khỏi model_users['{model}']. Hiện tại: {model_users[model]}")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /tb cho admin @{admin_username} (user_id: {admin_id}): {e}")
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

    logger.info(f"Admin @{admin_username} (user_id: {admin_id}) đã gửi thông báo đến {target} với nội dung: {message}")