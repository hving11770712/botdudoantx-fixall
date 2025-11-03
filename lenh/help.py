from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import SUPPORT_LINK, logger, is_banned, escape_markdown

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /help để hiển thị danh sách lệnh người dùng"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    try:
        # Kiểm tra nếu người dùng bị cấm
        if is_banned(user_id):
            logger.warning(f"User_id {user_id} (@{username}) bị cấm, không thể sử dụng /help")
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Danh sách lệnh người dùng
        help_text = (
            f"📚 *DuyWin*: Danh sách lệnh người dùng:\n"
            f"- `/start`: Đăng ký tài khoản và bắt đầu sử dụng bot\n"
            f"- `/naptien`: Gửi yêu cầu nạp tiền để nạp VNĐ vào tài khoản\n"
            f"- `/model`: Xem danh sách model (Basic, VIP, MD5Hit) và giá\n"
            f"- `/key <mã key>`: Nhập key từ admin để kích hoạt model\n"
            f"- `/taikhoan`: Xem thông tin tài khoản (số dư, model, v.v.)\n"
            f"- `/code <mã code>`: Sử dụng giftcode để nhận VNĐ miễn phí\n"
            f"- `/modelbasic`: Chạy dự đoán Model Basic (yêu cầu mua)\n"
            f"- `/modelvip`: Chạy dự đoán Model VIP (yêu cầu mua)\n"
            f"- `/admin`: Xem danh sách lệnh admin (chỉ dành cho admin)\n"
            f"- `/stop`: Dừng bot và các tác vụ đang chạy\n"
            f"\nLiên hệ hỗ trợ: {SUPPORT_LINK}"
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")
        logger.info(f"User_id {user_id} (@{username}) đã sử dụng lệnh /help")

    except Exception as e:
        logger.error(f"Lỗi trong hàm help_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi hiển thị danh sách lệnh. Liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )