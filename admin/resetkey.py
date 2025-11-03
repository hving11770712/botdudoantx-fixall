from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, KEY_FILE, db, logger, SUPPORT_LINK, is_banned, escape_markdown

async def resetkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /resetkey để admin gia hạn thời hạn của key"""
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
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /resetkey")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra tham số đầu vào
        if len(context.args) < 2:
            await update.message.reply_text(
                f"❌ *DuyWin*: Vui lòng nhập: `/resetkey <mã key> <số ngày gia hạn>`",
                parse_mode="Markdown"
            )
            return

        key_code, days = context.args[0], context.args[1]

        # Kiểm tra số ngày gia hạn
        if not days.isdigit() or int(days) <= 0:
            logger.warning(f"Số ngày gia hạn {days} không hợp lệ từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Số ngày gia hạn phải là số nguyên dương!",
                parse_mode="Markdown"
            )
            return

        # Tải danh sách key
        keys = db.load_json(KEY_FILE)

        # Kiểm tra mã key tồn tại
        if key_code not in keys:
            logger.warning(f"Mã key {key_code} không tồn tại, từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Mã key `{escape_markdown(key_code)}` không tồn tại!",
                parse_mode="Markdown"
            )
            return

        # Lấy thời hạn hiện tại
        old_expiry = keys[key_code]["expiry"]
        current_time = datetime.now()
        try:
            old_expiry_time = datetime.strptime(old_expiry, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.error(f"Thời hạn không hợp lệ cho mã key {key_code}: {old_expiry}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Lỗi dữ liệu thời hạn mã key. Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Tính thời hạn mới
        if old_expiry_time > current_time:
            # Key chưa hết hạn: Gia hạn từ thời hạn hiện tại
            new_expiry_time = old_expiry_time + timedelta(days=int(days))
        else:
            # Key đã hết hạn: Gia hạn từ hôm nay, đến 23:59:59 của ngày cuối
            new_expiry_time = (current_time + timedelta(days=int(days))).replace(hour=23, minute=59, second=59, microsecond=0)
        
        new_expiry_str = new_expiry_time.strftime("%Y-%m-%d %H:%M:%S")

        # Cập nhật thời hạn
        keys[key_code]["expiry"] = new_expiry_str
        db.save_json(KEY_FILE, keys)
        logger.info(f"User_id {user_id} (@{username}) đã gia hạn key {key_code} từ {old_expiry} đến {new_expiry_str}")

        # Gửi thông báo thành công
        safe_key_code = escape_markdown(key_code)
        safe_old_expiry = escape_markdown(old_expiry)
        safe_new_expiry = escape_markdown(new_expiry_str)
        await update.message.reply_text(
            f"✅ *DuyWin*: Đã gia hạn key `{safe_key_code}`. Hết hạn cũ: `{safe_old_expiry}`. Hết hạn mới: `{safe_new_expiry}`!",
            parse_mode="Markdown"
        )

        # Thông báo cho các admin khác
        safe_username = escape_markdown(username)
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:  # Không gửi cho chính người thực hiện
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📩 *DuyWin*: Admin @{safe_username} (user_id: {user_id}) đã gia hạn key `{safe_key_code}` "
                             f"từ `{safe_old_expiry}` đến `{safe_new_expiry}`.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
                    # Fallback: Gửi văn bản thường
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"📩 DuyWin: Admin @{username} (user_id: {user_id}) đã gia hạn key {key_code} "
                                 f"từ {old_expiry} đến {new_expiry_str}."
                        )
                        logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                    except Exception as e2:
                        logger.error(f"Lỗi khi gửi thông báo fallback admin {admin_id}: {str(e2)}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm resetkey_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi gia hạn key. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )