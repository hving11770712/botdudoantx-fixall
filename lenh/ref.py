from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import (
    check_ban, db, ACCOUNT_FILE, logger, SUPPORT_LINK, escape_markdown_safev2,
    REFERRAL_COMMISSION_PERCENTAGE
)
import os
from datetime import datetime

# Định nghĩa file lưu thông tin ref
REF_FILE = "data/ref.json"

# Đảm bảo thư mục data tồn tại
os.makedirs("data", exist_ok=True)

def validate_markdown_v2(text: str) -> bool:
    """Kiểm tra cú pháp MarkdownV2 có hợp lệ không."""
    stack = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2  
            continue
        if text[i] in ["_", "*", "`"]:
            if stack and stack[-1] == text[i]:
                stack.pop()  # Đóng định dạng
            else:
                stack.append(text[i])  # Mở định dạng
        i += 1
    
    # Log thông tin khi cú pháp không hợp lệ
    if len(stack) != 0:
        print(f"MarkdownV2 validation failed! Open tags: {stack}")
    
    return len(stack) == 0


async def ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hiển thị thông tin mời bạn bè và lưu thông tin ref con."""
    if await check_ban(update, context):
        return

    user = update.message.from_user
    user_id = user.id
    chat_id = update.message.chat_id
    display_username = user.username.lstrip('@') if user.username else f"ID_{user_id}"
    current_username = escape_markdown_safev2(display_username)
    is_group = chat_id < 0
    accounts = db.load_json(ACCOUNT_FILE)
    ref_data = db.load_json(REF_FILE, default={})

    try:
        account_key = str(user_id)
        if account_key not in accounts:
            await update.message.reply_text(
                f"😓 *DuyWin*: Tài khoản của bạn chưa được đăng ký\\! Vui lòng dùng /start để đăng ký\\.",
                parse_mode="MarkdownV2"
            )
            return

        user_info = accounts[account_key]
        # Đảm bảo referral_code tồn tại
        referral_code = escape_markdown_safev2(user_info.get("referral_code", f"REF{user_id}"))
        bot_username = escape_markdown_safev2(context.bot.username or "DuyWinBot")
        referral_link = escape_markdown_safev2(f"https://t.me/{bot_username}?start={referral_code}")
        referred_users = user_info.get("referred_users", [])
        referred_users_count = len(referred_users)
        referral_commission = user_info.get("referral_commission", 0)
        withdrawn_commission = user_info.get("withdrawn_commission", 0)
        group_text = escape_markdown_safev2("(Nhóm)") if is_group else ""

        # Lấy thông tin chi tiết về ref con từ ref_data
        referred_users_text = ""
        if referred_users_count > 0:
            referred_users_info = []
            for ref_id in referred_users:
                ref_info = ref_data.get(ref_id, {})
                ref_username = escape_markdown_safev2(accounts.get(ref_id, {}).get("username", f"ID_{ref_id}"))
                ref_time = escape_markdown_safev2(ref_info.get("referred_at", "Không rõ"))
                referred_users_info.append(f"@{ref_username} \\(ID: {escape_markdown_safev2(ref_id)}, Thời gian: {ref_time}\\)")
            referred_users_text = f"📋 *Danh sách bạn bè đã mời*:\n{'\n'.join(referred_users_info)}\n"

        ref_message = (
            f"📩 *Thông tin mời bạn bè của @{current_username}*{group_text} 📩\n\n"
            f"🔗 *Link mời của bạn*: {referral_link}\n"
            f"💸 Nhận ngay *{escape_markdown_safev2(str(REFERRAL_COMMISSION_PERCENTAGE))}%* hoa hồng cho mỗi lượt nạp tiền từ người dùng bạn giới thiệu\\.\n"
            f"👥 *Bạn bè đã mời*: {referred_users_count}\n"
            f"{referred_users_text}"
            f"💰 *Hoa hồng hiện tại*: {escape_markdown_safev2(f'{referral_commission:,}')} VNĐ\n"
            f"💸 *Hoa hồng đã rút*: {escape_markdown_safev2(f'{withdrawn_commission:,}')} VNĐ\n\n"
            f"💡 *Chia sẻ link mời để nhận thêm hoa hồng\\!*\n"
            f"👇 Liên hệ hỗ trợ nếu cần: {escape_markdown_safev2(SUPPORT_LINK)}"
        )

        # Ghi log chi tiết để kiểm tra
        logger.debug(f"Nội dung ref_message: {ref_message}")
        logger.debug(f"Inputs - current_username: {current_username}, referral_link: {referral_link}, referred_users_text: {referred_users_text}")

        # Kiểm tra cú pháp MarkdownV2
        if not validate_markdown_v2(ref_message):
            logger.error("Cú pháp MarkdownV2 không hợp lệ, chuyển sang văn bản thuần túy.")
            plain_message = ref_message.replace('\\*', '*').replace('\\_', '_').replace('\\`', '`').replace('\\-', '-').replace('\\(', '(').replace('\\)', ')').replace('\\\\', '')
            await update.message.reply_text(plain_message, parse_mode=None)
            return

        try:
            await update.message.reply_text(ref_message, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
            plain_message = ref_message.replace('\\*', '*').replace('\\_', '_').replace('\\`', '`').replace('\\-', '-').replace('\\(', '(').replace('\\)', ')').replace('\\\\', '')
            await update.message.reply_text(plain_message, parse_mode=None)

        logger.info(f"Lệnh /ref được gọi bởi @{display_username} (chat_id: {chat_id}, user_id: {user_id}, group: {is_group})")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /ref cho @{display_username} (chat_id: {chat_id}, user_id: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra\\! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safev2(SUPPORT_LINK)}",
            parse_mode="MarkdownV2"
        )

def save_ref_data(referred_by_id, referred_user_id, referred_username):
    """Lưu thông tin ref con vào file data/ref.json."""
    ref_data = db.load_json(REF_FILE, default={})
    referred_by_username = escape_markdown_safev2(db.load_json(ACCOUNT_FILE).get(referred_by_id, {}).get("username", f"ID_{referred_by_id}"))
    ref_data[referred_user_id] = {
        "referred_by_id": referred_by_id,
        "referred_by_username": referred_by_username,
        "referred_username": escape_markdown_safev2(referred_username),
        "referred_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "active"
    }
    db.save_json(REF_FILE, ref_data)
    logger.info(f"Đã lưu thông tin ref: {referred_user_id} được mời bởi {referred_by_id}")