from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import (
    check_ban, db, ACCOUNT_FILE, logger, SUPPORT_LINK, MODEL_PRICES_WITH_DAYS, update_username, escape_markdown_safe, NAP_CONTENT
)
from datetime import datetime, timedelta

def sanitize_string(text: str) -> str:
    """Làm sạch chuỗi, loại bỏ ký tự không hợp lệ hoặc thay thế bằng chuỗi an toàn."""
    if not isinstance(text, str):
        return str(text)
    return text.replace("\n", " ").strip()

def format_model_expiry(models, model_expiry):
    """Định dạng văn bản hiển thị thời hạn model với thông tin chi tiết."""
    expiry_text = ""
    now = datetime.now()
    if model_expiry and models:
        for model in models:
            model = sanitize_string(model)
            if model in model_expiry:
                try:
                    expiry = datetime.strptime(model_expiry[model], "%Y-%m-%d %H:%M:%S")
                    if now < expiry:
                        days_left = (expiry - now).days
                        hours_left = (expiry - now).seconds // 3600
                        expiry_text += (
                            f"  \\- {escape_markdown_safe(model.capitalize())}: "
                            f"{escape_markdown_safe(model_expiry[model])} "
                            f"\\(Còn {days_left} ngày, {hours_left} giờ\\)\n"
                        )
                    else:
                        expiry_text += f"  \\- {escape_markdown_safe(model.capitalize())}: Đã hết hạn\n"
                except ValueError:
                    expiry_text += f"  \\- {escape_markdown_safe(model.capitalize())}: Thời hạn không hợp lệ\n"
            else:
                expiry_text += f"  \\- {escape_markdown_safe(model.capitalize())}: Vĩnh viễn\n"
    else:
        expiry_text = "Chưa kích hoạt gói\n"
    return expiry_text

def format_username_history(username_history):
    """Định dạng lịch sử thay đổi username."""
    if not username_history:
        return "Không có lịch sử thay đổi\n"
    history_text = ""
    for entry in username_history:
        username = sanitize_string(entry.get('username', 'Không rõ'))
        updated_at = sanitize_string(entry.get('updated_at', 'Không rõ'))
        history_text += (
            f"  \\- @{escape_markdown_safe(username)} "
            f"\\(Cập nhật: {escape_markdown_safe(updated_at)}\\)\n"
        )
    return history_text

def get_referral_stats(accounts, referral_code):
    """Thống kê số lượng người dùng được mời và tổng số dư từ mã giới thiệu."""
    referred_count = 0
    total_referred_balance = 0
    for account in accounts.values():
        if account.get("referred_by") == referral_code:
            referred_count += 1
            total_referred_balance += account.get("balance", 0)
    return referred_count, total_referred_balance

def get_usage_stats(account):
    """Lấy thống kê sử dụng model (giả lập số lần sử dụng)."""
    usage_text = ""
    models = account.get("model", [])
    for model in models:
        model = sanitize_string(model)
        usage_count = account.get("usage_stats", {}).get(model, 0)
        usage_text += f"  \\- {escape_markdown_safe(model.capitalize())}: Đã sử dụng {usage_count} lần\n"
    return usage_text if usage_text else "Chưa có thống kê sử dụng\n"

async def taikhoan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /taikhoan để hiển thị thông tin tài khoản."""
    if await check_ban(update, context):
        return

    user = update.message.from_user
    user_id = user.id
    raw_username = sanitize_string(user.username.lstrip('@') if user.username else str(user_id))
    current_username = escape_markdown_safe(raw_username)
    accounts = db.load_json(ACCOUNT_FILE)

    try:
        # Tìm bản ghi tài khoản dựa trên user_id
        account_key = None
        for key, info in accounts.items():
            if info.get("user_id") == user_id:
                account_key = key
                break

        if account_key is None:
            await update.message.reply_text(
                f"*DuyWin*: Tài khoản chưa được khởi tạo\\! Vui lòng dùng /start để đăng ký\\! 🚀",
                parse_mode="MarkdownV2"
            )
            return

        # Cập nhật referral_code và nap_content nếu chưa có
        if "referral_code" not in accounts[account_key]:
            accounts[account_key]["referral_code"] = f"REF{user_id}"
            logger.info(f"Đã cập nhật referral_code cho @{raw_username}")
        if "nap_content" not in accounts[account_key]:
            accounts[account_key]["nap_content"] = f"{NAP_CONTENT}{user_id}"
            logger.info(f"Đã cập nhật nap_content cho @{raw_username}: {accounts[account_key]['nap_content']}")
        accounts[account_key]["user_id"] = user_id
        accounts[account_key]["chat_id"] = user_id  # Luôn update về user_id
        update_username(accounts, account_key, raw_username, user_id)

        db.save_json(ACCOUNT_FILE, accounts)

        info = accounts[account_key]
        balance = info.get("balance", 0)
        models = info.get("model", [])
        model_expiry = info.get("model_expiry", {})
        created_at = sanitize_string(info.get("created_at", "Không rõ"))
        referral_code = sanitize_string(info.get("referral_code", "Không có"))
        nap_content = sanitize_string(info.get("nap_content", f"{NAP_CONTENT}{user_id}"))
        username_history = info.get("username_history", [])
        referred_by = sanitize_string(info.get("referred_by", "Không có"))

        model_text = escape_markdown_safe(", ".join([sanitize_string(m).capitalize() for m in models]) if models else "Chưa kích hoạt")
        expiry_text = format_model_expiry(models, model_expiry)
        history_text = format_username_history(username_history)
        referred_count, total_referred_balance = get_referral_stats(accounts, referral_code)
        usage_text = get_usage_stats(info)

        message = (
            f"*Thông tin tài khoản* 📋\n\n"
            f"👤 *Tên*: @{current_username}\n"
            f"🆔 *Chat ID*: {escape_markdown_safe(str(user_id))}\n"
            f"💰 *Số dư*: {escape_markdown_safe(f'{balance:,}'.replace(',', '.'))} VNĐ\n"
            f"📊 *Gói dự đoán*: {model_text}\n"
            f"⏰ *Hết hạn gói*:\n{expiry_text}"
            f"📅 *Ngày tham gia*: {escape_markdown_safe(created_at)}\n"
            f"📩 *Mã mời bạn bè*: {escape_markdown_safe(referral_code)}\n"
            f"💸 *Nội dung nạp*: {escape_markdown_safe(nap_content)}\n"
            f"👥 *Người mời*: {escape_markdown_safe(referred_by)}\n"
            f"📈 *Thống kê mời*:\n  \\- Số người mời được: {referred_count}\n"
            f"  \\- Tổng số dư từ người mời: {escape_markdown_safe(f'{total_referred_balance:,}'.replace(',', '.'))} VNĐ\n"
            f"📜 *Lịch sử tên*:\n{history_text}"
            f"📊 *Thống kê sử dụng*:\n{usage_text}"
        )

        logger.debug(f"Gửi tin nhắn tài khoản: {message}")
        try:
            await update.message.reply_text(message, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
            plain_message = (
                message.replace('\\*', '').replace('\\_', '').replace('\\`', '')
                       .replace('\\-', '-').replace('\\(', '(').replace('\\)', ')')
                       .replace('\\', '')
            )
            await update.message.reply_text(plain_message, parse_mode=None)

        logger.info(f"Lệnh /taikhoan được gọi bởi @{raw_username} (user_id: {user_id}, nap_content: {nap_content})")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /taikhoan cho @{raw_username} (user_id: {user_id}): {e}")
        try:
            await update.message.reply_text(
                f"*DuyWin*: Đã có lỗi xảy ra\\! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
        except Exception as e2:
            logger.error(f"Phân tích MarkdownV2 thất bại trong thông báo lỗi: {e2}. Gửi văn bản thuần túy.")
            await update.message.reply_text(
                f"DuyWin: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode=None
            )
