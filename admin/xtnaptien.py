import os
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import (
    ADMIN_IDS,
    ACCOUNT_FILE,
    NAPTIEN_FILE,
    db,
    logger,
    SUPPORT_LINK,
    escape_markdown_safev2,
    validate_markdown_v2,
    is_banned
)

async def xtnaptien_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /xtnaptien để admin xác nhận hoặc từ chối yêu cầu nạp tiền"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"ID_{user_id}"

    try:
        # Kiểm tra nếu admin bị cấm
        if is_banned(user_id):
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa\\! Liên hệ hỗ trợ: {escape_markdown_safev2(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra quyền admin
        if user_id not in ADMIN_IDS:
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /xtnaptien")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                "❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra tham số đầu vào
        if len(context.args) < 2 or not context.args[0].isdigit() or context.args[1] not in ["accept", "reject"]:
            await update.message.reply_text(
                "❌ *DuyWin*: Vui lòng nhập: `/xtnaptien <dòng> <accept/reject>`",
                parse_mode="MarkdownV2"
            )
            return

        line_num = int(context.args[0]) - 1
        action = context.args[1]

        if not os.path.exists(NAPTIEN_FILE):
            logger.warning(f"File {NAPTIEN_FILE} không tồn tại")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                "❌ *DuyWin*: Không có yêu cầu nạp tiền nào\\!",
                parse_mode="MarkdownV2"
            )
            return

        with open(NAPTIEN_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line_num < 0 or line_num >= len(lines):
            logger.warning(f"Số dòng {line_num + 1} không hợp lệ từ user_id {user_id}")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                f"❌ *DuyWin*: Số dòng `{escape_markdown_safev2(str(line_num + 1))}` không hợp lệ\\!",
                parse_mode="MarkdownV2"
            )
            return

        line = lines[line_num].strip()
        parts = line.split("|")
        if len(parts) < 4 or not parts[1].isdigit() or not parts[2].isdigit():
            logger.error(f"Dòng {line_num + 1} trong {NAPTIEN_FILE} không hợp lệ: {line}")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                f"❌ *DuyWin*: Dữ liệu dòng `{escape_markdown_safev2(str(line_num + 1))}` không hợp lệ\\!",
                parse_mode="MarkdownV2"
            )
            return

        req_user_id, amount = parts[1], int(parts[2])
        current_status = parts[3]

        if current_status != "Chưa xác nhận":
            logger.warning(f"Yêu cầu dòng {line_num + 1} đã được xử lý: {current_status}")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                f"❌ *DuyWin*: Yêu cầu dòng `{escape_markdown_safev2(str(line_num + 1))}` đã được xử lý: `{escape_markdown_safev2(current_status)}`\\!",
                parse_mode="MarkdownV2"
            )
            return

        accounts = db.load_json(ACCOUNT_FILE)
        req_user_id_str = str(req_user_id)
        if req_user_id_str not in accounts:
            logger.warning(f"Tài khoản user_id {req_user_id_str} không tồn tại trong {ACCOUNT_FILE}")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                f"❌ *DuyWin*: Tài khoản `ID_{escape_markdown_safev2(req_user_id_str)}` không tồn tại\\!",
                parse_mode="MarkdownV2"
            )
            return

        req_username = accounts[req_user_id_str].get("username", f"ID_{req_user_id_str}")

        new_status = "Đã xác nhận" if action == "accept" else "Đã từ chối"
        
        # CẢI TIẾN: Thống nhất định dạng số tiền có dấu chấm và thoát ký tự
        formatted_amount = f"{amount:,}".replace(",", ".")
        safe_amount = escape_markdown_safev2(formatted_amount)
        safe_user_id = escape_markdown_safev2(req_user_id_str)
        safe_username = escape_markdown_safev2(req_username)
        safe_line_num = escape_markdown_safev2(str(line_num + 1))

        if action == "accept":
            accounts[req_user_id_str]["balance"] += amount
            db.save_json(ACCOUNT_FILE, accounts)
            logger.info(f"User_id {user_id} (@{username}) đã xác nhận nạp {amount} VNĐ cho user_id {req_user_id_str} (@{req_username}), dòng {line_num + 1}")

        lines[line_num] = f"{line_num + 1}|{req_user_id}|{amount}|{new_status}\n"
        with open(NAPTIEN_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

        action_text = "xác nhận" if action == "accept" else "từ chối"
        # SỬA LỖI: Thoát ký tự '!'
        admin_message = (
            f"✅ *DuyWin*: Xác thực nạp tiền \n"
            f"Đã {action_text} nạp `{safe_amount}` VNĐ \n"
            f"`@{safe_username}` \\ \n"
            f"ID: {safe_user_id}\\ \n"
            f"Dòng `{safe_line_num}`\\"
        )
        if not validate_markdown_v2(admin_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong admin_message: {admin_message}")
            admin_message = f"✅ DuyWin: Đã {action_text} nạp {formatted_amount} VNĐ cho @{req_username} (ID_{req_user_id_str}, dòng {line_num + 1})."
            admin_parse_mode = None
        else:
            admin_parse_mode = "MarkdownV2"
        await update.message.reply_text(admin_message, parse_mode=admin_parse_mode)

        # Gửi thông báo cho người dùng
        target_user_id = int(req_user_id_str)
        try:
            if action == "accept":
                new_balance = accounts[req_user_id_str]['balance']
                formatted_balance = f"{new_balance:,}".replace(",", ".")
                safe_balance = escape_markdown_safev2(formatted_balance)
                # SỬA LỖI: Thoát ký tự '!' và '.'
                user_message = (
                    f"✅ *DuyWin*: Nhận tiền\n"
                    f"Yêu cầu nạp: `{safe_amount}` VNĐ của bạn đã được xác nhận\\! \n"
                    f"Số dư mới: `{safe_balance}` VNĐ\\."
                )
            else: # action == "reject"
                # SỬA LỖI: Thoát ký tự '.'
                user_message = (
                    f"❌ *DuyWin*: Yêu cầu nạp `{safe_amount}` VNĐ của bạn đã bị từ chối\\. "
                    f"Liên hệ hỗ trợ: {escape_markdown_safev2(SUPPORT_LINK)}"
                )
            
            if not validate_markdown_v2(user_message):
                 logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong user_message: {user_message}")
                 user_message = (f"✅ DuyWin: Yêu cầu nạp {formatted_amount} VNĐ của bạn đã được xác nhận! Số dư mới: {accounts[req_user_id_str]['balance']:,} VNĐ.") if action == "accept" else (f"❌ DuyWin: Yêu cầu nạp {formatted_amount} VNĐ của bạn đã bị từ chối. Liên hệ hỗ trợ: {SUPPORT_LINK}")
                 user_parse_mode = None
            else:
                 user_parse_mode = "MarkdownV2"

            await context.bot.send_message(chat_id=target_user_id, text=user_message, parse_mode=user_parse_mode)
        except Exception as e:
            logger.error(f"Lỗi khi gửi thông báo cho user_id {target_user_id}: {str(e)}")
            # SỬA LỖI: Thoát ký tự '.' và '!'
            error_message = (
                f"⚠️ *DuyWin*: Không thể gửi thông báo cho `@{safe_username}` \\(ID_{safe_user_id}\\)\\. Vui lòng kiểm tra thủ công\\!"
            )
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong error_message: {error_message}")
                error_message = f"⚠️ DuyWin: Không thể gửi thông báo cho @{req_username} (ID_{req_user_id_str}). Vui lòng kiểm tra thủ công!"
                error_parse_mode = None
            else:
                error_parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=error_parse_mode)

        # Thông báo cho các admin khác
        admin_username = escape_markdown_safev2(username)
        # SỬA LỖI: Thoát ký tự '.'
        other_admin_message = (
            f"📩 *DuyWin*: Admin @{admin_username} \\(ID_{escape_markdown_safev2(str(user_id))}\\) đã {action_text} nạp "
            f"`{safe_amount}` VNĐ cho `@{safe_username}` \\(ID_{safe_user_id}\\), dòng `{safe_line_num}`\\."
        )
        if not validate_markdown_v2(other_admin_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong other_admin_message: {other_admin_message}")
            other_admin_message = (f"📩 DuyWin: Admin @{username} (ID_{user_id}) đã {action_text} nạp {formatted_amount} VNĐ "
                                 f"cho @{req_username} (ID_{req_user_id_str}, dòng {line_num + 1}).")
            other_admin_parse_mode = None
        else:
            other_admin_parse_mode = "MarkdownV2"
            
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id, text=other_admin_message, parse_mode=other_admin_parse_mode
                    )
                except Exception as e:
                    logger.error(f"Lỗi khi gửi thông báo cho admin {admin_id}: {str(e)}")
                    try:
                        fallback_text = (f"📩 DuyWin: Admin @{username} (ID_{user_id}) đã {action_text} nạp {formatted_amount} VNĐ "
                                         f"cho @{req_username} (ID_{req_user_id_str}, dòng {line_num + 1}).")
                        await context.bot.send_message(chat_id=admin_id, text=fallback_text)
                        logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                    except Exception as e2:
                        logger.error(f"Lỗi khi gửi thông báo fallback cho admin {admin_id}: {str(e2)}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm xtnaptien_command cho user_id {user_id}: {e}", exc_info=True)
        # SỬA LỖI: Thoát ký tự '.'
        error_message = (
            f"❌ *DuyWin*: Đã xảy ra lỗi khi xử lý yêu cầu\\. "
            f"Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safev2(SUPPORT_LINK)}"
        )
        if not validate_markdown_v2(error_message):
             logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong error_message: {error_message}")
             error_message = f"❌ DuyWin: Đã xảy ra lỗi khi xử lý yêu cầu. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}"
             error_parse_mode = None
        else:
             error_parse_mode = "MarkdownV2"
        await update.message.reply_text(error_message, parse_mode=error_parse_mode)
