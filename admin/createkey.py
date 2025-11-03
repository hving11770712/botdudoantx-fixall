from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, MODEL_PRICES_WITH_DAYS, KEY_FILE, db, logger, SUPPORT_LINK, is_banned

async def createkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /createkey để tạo key cho model"""
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
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /createkey")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra tham số đầu vào
        if len(context.args) < 4:
            await update.message.reply_text(
                f"❌ *DuyWin*: Vui lòng nhập: `/createkey <model> <mã key> <lượt sử dụng> <số ngày>`",
                parse_mode="Markdown"
            )
            return

        model, key_code, uses, days = context.args[0].lower(), context.args[1], context.args[2], context.args[3]

        # Kiểm tra model hợp lệ
        if model not in MODEL_PRICES_WITH_DAYS:
            logger.warning(f"Model không hợp lệ: {model} từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Model không hợp lệ! Các model khả dụng: {', '.join(MODEL_PRICES_WITH_DAYS.keys())}",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra số lần sử dụng
        if not uses.isdigit() or int(uses) <= 0:
            logger.warning(f"Số lượng sử dụng không hợp lệ: {uses} từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Số lượng sử dụng phải là số nguyên dương!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra số ngày
        if not days.isdigit() or int(days) <= 0:
            logger.warning(f"Số ngày không hợp lệ: {days} từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Số ngày phải là số nguyên dương!",
                parse_mode="Markdown"
            )
            return

        # Tải danh sách key hiện tại
        keys = db.load_json(KEY_FILE)

        # Kiểm tra mã key trùng lặp
        if key_code in keys:
            logger.warning(f"Mã key {key_code} đã tồn tại, từ chối tạo mới từ user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Mã key `{key_code}` đã tồn tại! Vui lòng chọn mã khác.",
                parse_mode="Markdown"
            )
            return

        # Tính thời gian hết hạn
        current_time = datetime.now()
        expiry_time = current_time + timedelta(days=int(days))
        expiry_str = expiry_time.strftime("%Y-%m-%d %H:%M:%S")

        # Lưu key mới
        keys[key_code] = {
            "model": model,
            "uses": int(uses),
            "expiry": expiry_str,
            "created_at": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "created_by": user_id
        }
        db.save_json(KEY_FILE, keys)
        logger.info(f"User_id {user_id} (@{username}) đã tạo key {key_code} cho model {model} với {uses} lần sử dụng, hết hạn {expiry_str}")

        # Gửi thông báo thành công
        await update.message.reply_text(
            f"✅ *DuyWin*: Key\n\n"
            f"Đã tạo key: `{key_code}`\n"
            f"Model: `{model}`\n"
            f"Số lần sủ dụng: `{uses}`\n"
            f"Ngày hết hạn: `{expiry_str}`!",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Lỗi trong hàm createkey_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi tạo key. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )