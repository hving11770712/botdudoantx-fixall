from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, KEY_FILE, db, logger, SUPPORT_LINK, is_banned

async def listkeys_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /listkeys để admin xem danh sách key"""
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
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /listkeys")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
                parse_mode="Markdown"
            )
            return

        # Tải danh sách key
        keys = db.load_json(KEY_FILE)
        if not keys:
            logger.info(f"User_id {user_id} (@{username}) yêu cầu /listkeys, nhưng không có key nào")
            await update.message.reply_text(
                f"❌ *DuyWin*: Hiện không có key nào!",
                parse_mode="Markdown"
            )
            return

        # Tạo thông báo danh sách key
        message = "📜 *DuyWin*: Danh sách key:\n"
        for key_code, info in keys.items():
            message += (
                f"- `{key_code}`: Model `{info['model']}`, `{info['uses']}` lần, "
                f"hết hạn `{info['expiry']}`, tạo bởi `{info.get('created_by', 'Unknown')}`\n"
            )
        logger.info(f"User_id {user_id} (@{username}) đã xem danh sách key")
        await update.message.reply_text(message, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Lỗi trong hàm listkeys_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi liệt kê key. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )