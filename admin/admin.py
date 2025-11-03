from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, SUPPORT_LINK, logger, is_banned, escape_markdown

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /admin để hiển thị danh sách lệnh admin"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    try:
        # Kiểm tra nếu admin bị cấm
        if is_banned(user_id):
            logger.warning(f"User_id {user_id} (@{username}) bị cấm, không thể sử dụng /admin")
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra quyền admin
        if user_id not in ADMIN_IDS:
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /admin")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
                parse_mode="Markdown"
            )
            return

        # Danh sách lệnh admin
        admin_help = (
            f"🔧 *DuyWin*: Danh sách lệnh admin:\n"
            f"- `/admin`: Xem danh sách lệnh admin\n"
            f"- `/createkey <model> <mã key> <lượt> <ngày>`: Tạo key cho model (Basic, VIP, MD5Hit)\n"
            f"- `/resetkey <mã key> <số ngày>`: Gia hạn thời hạn của key\n"
            f"- `/balance <id> <số tiền> <nội dung>`: Cộng trù tiền người dùng"
            f"- `/listkeys`: Liệt kê tất cả key hiện có\n"
            f"- `/giftcode <mã code> <số tiền> <lượt> <hạn>`: Tạo giftcode để người dùng nhận VNĐ\n"
            f"- `/xtnaptien <dòng> <accept/reject>`: Xác nhận hoặc từ chối yêu cầu nạp tiền\n"
            f"- `/listnaptien`: Liệt kê tất cả yêu cầu nạp tiền\n"
            f"- `/tb all <nội dung>`: Gửi thông báo đến tất cả người dùng\n"
            f"- `/tb <chat_id> <nội dung>`: Gửi thông báo đến người dùng cụ thể\n"
            f"- `/out <group_id>`: Xóa bot khỏi nhóm và chặn nhóm 🚫\n"
            f"- `/unout <group_id>`: Gỡ chặn nhóm ✅\n"
            f"- `/list`: Liệt kê tất cả nhóm bị chặn 📋\n"
            f"- `/groups`: Liệt kê tất cả nhóm bot đang tham gia 🌐\n"
            f"\nLiên hệ hỗ trợ: {SUPPORT_LINK}"
        )

        await update.message.reply_text(admin_help, parse_mode="Markdown")
        logger.info(f"User_id {user_id} (@{username}) đã sử dụng lệnh /admin")

    except Exception as e:
        logger.error(f"Lỗi trong hàm admin_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi hiển thị danh sách lệnh admin. Liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )