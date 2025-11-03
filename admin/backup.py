import os
import shutil
import glob
from datetime import datetime, timedelta
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import logger, ADMIN_IDS, SUPPORT_LINK, escape_markdown_safe

# Định nghĩa thư mục dữ liệu và backup
DATA_DIR = "data"
BACKUP_DIR = "backup"

async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /backup để sao lưu file dữ liệu."""
    user = update.message.from_user
    user_id = user.id
    username = user.username.lstrip('@') if user.username else f"ID_{user_id}"
    safe_username = escape_markdown_safe(username)

    # Kiểm tra quyền admin
    if user_id not in ADMIN_IDS:
        logger.warning(f"User @{username} (user_id: {user_id}) không phải admin, cố gắng dùng /backup")
        await update.message.reply_text(
            f"🚫 *DuyWin*: Chỉ admin mới được dùng lệnh này\\!",
            parse_mode="MarkdownV2"
        )
        return

    try:
        # Tạo thư mục backup nếu chưa tồn tại
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Lấy tham số lệnh
        args = context.args
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backed_up_files = []

        if not args:
            # Không có tham số, gửi hướng dẫn sử dụng
            usage_message = escape_markdown_safe(
                "📁 *DuyWin*: Vui lòng sử dụng:\n"
                "🔹 /backup all - Sao lưu tất cả file trong data/\n"
                "🔹 /backup <tên file> - Sao lưu file cụ thể (ví dụ: taikhoan.json)"
            )
            await update.message.reply_text(usage_message, parse_mode="MarkdownV2")
            return

        if args[0].lower() == "all":
            # Sao lưu tất cả file .json trong data/
            if not os.path.exists(DATA_DIR):
                logger.error(f"Thư mục {DATA_DIR} không tồn tại")
                await update.message.reply_text(
                    f"❌ *DuyWin*: Thư mục dữ liệu không tồn tại\\! Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                    parse_mode="MarkdownV2"
                )
                return

            json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
            if not json_files:
                logger.warning(f"Không tìm thấy file .json nào trong {DATA_DIR}")
                await update.message.reply_text(
                    f"⚠️ *DuyWin*: Không có file .json nào để sao lưu trong {escape_markdown_safe(DATA_DIR)}\\!",
                    parse_mode="MarkdownV2"
                )
                return

            for file_path in json_files:
                file_name = os.path.basename(file_path)
                backup_file = os.path.join(BACKUP_DIR, f"{file_name.rsplit('.', 1)[0]}_{timestamp}.json")
                shutil.copy2(file_path, backup_file)
                backed_up_files.append(backup_file)
                logger.info(f"Đã sao lưu {file_path} thành {backup_file}")

        else:
            # Sao lưu file cụ thể
            file_name = args[0]
            if not file_name.endswith(".json"):
                file_name += ".json"
            file_path = os.path.join(DATA_DIR, file_name)

            if not os.path.exists(file_path):
                logger.warning(f"File {file_path} không tồn tại")
                await update.message.reply_text(
                    f"❌ *DuyWin*: File `{escape_markdown_safe(file_name)}` không tồn tại\\!",
                    parse_mode="MarkdownV2"
                )
                return

            backup_file = os.path.join(BACKUP_DIR, f"{file_name.rsplit('.', 1)[0]}_{timestamp}.json")
            shutil.copy2(file_path, backup_file)
            backed_up_files.append(backup_file)
            logger.info(f"Đã sao lưu {file_path} thành {backup_file}")

        # Gửi thông báo thành công
        file_list = "\n".join([f"\\- `{escape_markdown_safe(f)}`" for f in backed_up_files])
        success_message = escape_markdown_safe(
            f"✅ *DuyWin*: Sao lưu thành công bởi @{safe_username}\\!\n"
            f"📁 File đã sao lưu:\n{file_list}"
        )
        await update.message.reply_text(success_message, parse_mode="MarkdownV2")
        logger.info(f"Admin @{username} (user_id: {user_id}) đã chạy lệnh /backup, sao lưu: {backed_up_files}")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /backup cho @{username} (user_id: {user_id}): {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi sao lưu\\! Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
            parse_mode="MarkdownV2"
        )

async def auto_backup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tự động sao lưu tất cả file trong data/ vào 0h Chủ nhật hàng tuần."""
    try:
        # Tạo thư mục backup nếu chưa tồn tại
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # Lấy thời gian hiện tại
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backed_up_files = []

        # Sao lưu tất cả file .json trong data/
        if not os.path.exists(DATA_DIR):
            logger.error(f"Thư mục {DATA_DIR} không tồn tại trong auto_backup")
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=escape_markdown_safe(
                        f"❌ *DuyWin*: Tự động sao lưu thất bại\\! Thư mục dữ liệu không tồn tại\\! "
                        f"Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}"
                    ),
                    parse_mode="MarkdownV2"
                )
            return

        json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
        if not json_files:
            logger.warning(f"Không tìm thấy file .json nào trong {DATA_DIR} trong auto_backup")
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=escape_markdown_safe(
                        f"⚠️ *DuyWin*: Tự động sao lưu hoàn tất nhưng không có file .json nào trong {escape_markdown_safe(DATA_DIR)}\\!"
                    ),
                    parse_mode="MarkdownV2"
                )
            return

        for file_path in json_files:
            file_name = os.path.basename(file_path)
            backup_file = os.path.join(BACKUP_DIR, f"{file_name.rsplit('.', 1)[0]}_{timestamp}.json")
            shutil.copy2(file_path, backup_file)
            backed_up_files.append(backup_file)
            logger.info(f"Tự động sao lưu {file_path} thành {backup_file}")

        # Gửi thông báo cho admin
        file_list = "\n".join([f"\\- `{escape_markdown_safe(f)}`" for f in backed_up_files])
        success_message = escape_markdown_safe(
            f"✅ *DuyWin*: Tự động sao lưu thành công lúc {timestamp}\\!\n"
            f"📁 File đã sao lưu:\n{file_list}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=success_message,
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                logger.error(f"Lỗi khi gửi thông báo auto_backup tới admin {admin_id}: {str(e)}")

        logger.info(f"Tự động sao lưu hoàn tất, file: {backed_up_files}")

    except Exception as e:
        logger.error(f"Lỗi trong auto_backup: {str(e)}")
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=escape_markdown_safe(
                        f"❌ *DuyWin*: Tự động sao lưu thất bại\\! Lỗi: {escape_markdown_safe(str(e))}\\! "
                        f"Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}"
                    ),
                    parse_mode="MarkdownV2"
                )
            except Exception as e2:
                logger.error(f"Lỗi khi gửi thông báo lỗi auto_backup tới admin {admin_id}: {e2}")

async def schedule_auto_backup(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lên lịch tự động sao lưu vào 0h Chủ nhật hàng tuần."""
    while True:
        now = datetime.now()
        # Tính thời gian đến 0h Chủ nhật tiếp theo
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour < 0:
            days_until_sunday = 7
        next_sunday = (now + timedelta(days=days_until_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_until_sunday = (next_sunday - now).total_seconds()

        logger.info(f"Lên lịch auto_backup vào {next_sunday}")
        await asyncio.sleep(seconds_until_sunday)
        await auto_backup(context)
        # Chờ 1 phút để tránh chạy lại ngay lập tức
        await asyncio.sleep(60)