from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, GIFTCODE_FILE, db, logger, SUPPORT_LINK, is_banned, escape_markdown

async def giftcode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /giftcode để admin tạo giftcode"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    try:
        # Kiểm tra nếu người dùng bị cấm
        if is_banned(user_id):
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra quyền admin
        if user_id not in ADMIN_IDS:
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /giftcode")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra tham số đầu vào
        if len(context.args) < 4:
            await update.message.reply_text(
                f"❌ *DuyWin*: Vui lòng nhập: `/giftcode <mã code> <số tiền> <lượt> <số ngày>`",
                parse_mode="Markdown"
            )
            return

        code_str, amount, uses, days = context.args[0], context.args[1], context.args[2], context.args[3]

        # Kiểm tra số tiền và lượt sử dụng
        if not amount.isdigit() or not uses.isdigit() or int(amount) <= 0 or int(uses) <= 0:
            logger.warning(f"Số tiền {amount} hoặc lượt sử dụng {uses} không hợp lệ từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Số tiền và lượt sử dụng phải là số nguyên dương!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra số ngày
        if not days.isdigit() or int(days) <= 0:
            logger.warning(f"Số ngày {days} không hợp lệ từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Số ngày phải là số nguyên dương!",
                parse_mode="Markdown"
            )
            return

        # Tính thời hạn đến 23:59:59 của ngày cuối cùng
        current_time = datetime.now()
        expiry_date = (current_time + timedelta(days=int(days))).replace(hour=23, minute=59, second=59, microsecond=0)
        expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")

        # Tải danh sách giftcode
        giftcodes = db.load_json(GIFTCODE_FILE)

        # Kiểm tra mã giftcode trùng lặp
        if code_str in giftcodes:
            logger.warning(f"Mã giftcode {code_str} đã tồn tại, từ chối tạo mới từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Mã giftcode `{escape_markdown(code_str)}` đã tồn tại! Vui lòng chọn mã khác.",
                parse_mode="Markdown"
            )
            return

        # Lưu giftcode mới
        giftcodes[code_str] = {
            "amount": int(amount),
            "uses": int(uses),
            "expiry": expiry_str,
            "used_by": [],
            "created_by": user_id,
            "created_at": current_time.strftime("%Y-%m-%d %H:%M:%S")
        }
        db.save_json(GIFTCODE_FILE, giftcodes)
        logger.info(f"User_id {user_id} (@{username}) đã tạo giftcode {code_str} với {amount} VNĐ, {uses} lượt, hạn {expiry_str}")

        # Gửi thông báo thành công
        await update.message.reply_text(
            f"✅ *DuyWin*: Đã tạo giftcode `{escape_markdown(code_str)}` với `{amount}` VNĐ, `{uses}` lượt, hạn đến `{escape_markdown(expiry_str)}`!",
            parse_mode="Markdown"
        )

        # Thông báo cho các admin khác
        safe_username = escape_markdown(username)
        safe_code_str = escape_markdown(code_str)
        safe_amount = escape_markdown(str(amount))
        safe_uses = escape_markdown(str(uses))
        safe_expiry = escape_markdown(expiry_str)
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:  # Không gửi cho chính người tạo
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📩 *DuyWin*: Admin @{safe_username} (user_id: {user_id}) đã tạo giftcode `{safe_code_str}` "
                             f"với `{safe_amount}` VNĐ, `{safe_uses}` lượt, hạn đến `{safe_expiry}`.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
                    # Fallback: Gửi văn bản thường
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"📩 DuyWin: Admin @{username} (user_id: {user_id}) đã tạo giftcode {code_str} "
                                 f"với {amount} VNĐ, {uses} lượt, hạn đến {expiry_str}."
                        )
                        logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                    except Exception as e2:
                        logger.error(f"Lỗi khi gửi thông báo fallback admin {admin_id}: {str(e2)}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm giftcode_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi tạo giftcode. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )