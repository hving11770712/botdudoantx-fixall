import os
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, ACCOUNT_FILE, db, logger, SUPPORT_LINK, escape_markdown_safev2, validate_markdown_v2, is_banned

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /check <user_id> để admin tra cứu thông tin tài khoản người dùng"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"ID_{user_id}"

    try:
        # Kiểm tra nếu admin bị cấm
        if is_banned(user_id):
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {escape_markdown_safev2(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra quyền admin
        if user_id not in ADMIN_IDS:
            logger.warning(f"User_id {user_id} (@{username}) không có quyền sử dụng /check")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra tham số đầu vào
        if len(context.args) != 1 or not context.args[0].isdigit():
            logger.warning(f"User_id {user_id} (@{username}) không cung cấp user_id hợp lệ")
            await update.message.reply_text(
                f"❌ *DuyWin*: Vui lòng nhập: `/check <user_id>`",
                parse_mode="MarkdownV2"
            )
            return

        target_user_id = context.args[0]

        # Tải danh sách tài khoản
        if not os.path.exists(ACCOUNT_FILE):
            logger.warning(f"File {ACCOUNT_FILE} không tồn tại")
            await update.message.reply_text(
                f"❌ *DuyWin*: Không tìm thấy dữ liệu tài khoản!",
                parse_mode="MarkdownV2"
            )
            return

        accounts = db.load_json(ACCOUNT_FILE)
        target_user_id_str = str(target_user_id)
        if target_user_id_str not in accounts:
            logger.warning(f"Tài khoản user_id {target_user_id_str} không tồn tại trong {ACCOUNT_FILE}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Tài khoản `ID_{escape_markdown_safev2(target_user_id_str)}` không tồn tại!",
                parse_mode="MarkdownV2"
            )
            return

        # Lấy thông tin tài khoản
        account = accounts[target_user_id_str]
        safe_user_id = escape_markdown_safev2(target_user_id_str)
        safe_username = escape_markdown_safev2(account.get("username", f"ID_{target_user_id_str}"))
        safe_balance = escape_markdown_safev2(str(account.get("balance", 0)))
        safe_model = escape_markdown_safev2(", ".join(account.get("model", [])) or "Không có")
        safe_model_expiry = escape_markdown_safev2(
            "; ".join([f"{k}: {v}" for k, v in account.get("model_expiry", {}).items()]) or "Không có"
        )
        safe_created_at = escape_markdown_safev2(account.get("created_at", "Không có"))
        safe_referral_code = escape_markdown_safev2(account.get("referral_code", "Không có"))
        safe_nap_content = escape_markdown_safev2(account.get("nap_content", "Không có"))
        safe_referral_commission = escape_markdown_safev2(str(account.get("referral_commission", 0)))
        safe_withdrawn_commission = escape_markdown_safev2(str(account.get("withdrawn_commission", 0)))

        # Tạo thông báo
        message = (
            f"📋 *DuyWin*: Thông tin tài khoản `ID_{safe_user_id}`:\n"
            f"👤 Tên người dùng: @{safe_username}\n"
            f"💰 Số dư: `{safe_balance}` VNĐ\n"
            f"📦 Mô hình: `{safe_model}`\n"
            f"⏰ Hết hạn mô hình: `{safe_model_expiry}`\n"
            f"🕒 Tạo lúc: `{safe_created_at}`\n"
            f"🔗 Mã giới thiệu: `{safe_referral_code}`\n"
            f"📝 Nội dung nạp: `{safe_nap_content}`\n"
            f"💸 Hoa hồng giới thiệu: `{safe_referral_commission}` VNĐ\n"
            f"💳 Hoa hồng đã rút: `{safe_withdrawn_commission}` VNĐ"
        )

        # Kiểm tra cú pháp MarkdownV2
        if not validate_markdown_v2(message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong message: {message}")
            message = (
                f"📋 DuyWin: Thông tin tài khoản ID_{target_user_id_str}:\n"
                f"👤 Tên người dùng: @{account.get('username', f'ID_{target_user_id_str}')}\n"
                f"💰 Số dư: {account.get('balance', 0)} VNĐ\n"
                f"📦 Mô hình: {', '.join(account.get('model', [])) or 'Không có'}\n"
                f"⏰ Hết hạn mô hình: {'; '.join([f'{k}: {v}' for k, v in account.get('model_expiry', {}).items()]) or 'Không có'}\n"
                f"🕒 Tạo lúc: {account.get('created_at', 'Không có')}\n"
                f"🔗 Mã giới thiệu: {account.get('referral_code', 'Không có')}\n"
                f"📝 Nội dung nạp: {account.get('nap_content', 'Không có')}\n"
                f"💸 Hoa hồng giới thiệu: {account.get('referral_commission', 0)} VNĐ\n"
                f"💳 Hoa hồng đã rút: {account.get('withdrawn_commission', 0)} VNĐ"
            )
            parse_mode = None
        else:
            parse_mode = "MarkdownV2"

        # Gửi thông báo
        await update.message.reply_text(message, parse_mode=parse_mode)
        logger.info(f"User_id {user_id} (@{username}) đã tra cứu thông tin tài khoản user_id {target_user_id_str}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm check_command cho user_id {user_id}: {str(e)}")
        error_message = (
            f"❌ *DuyWin*: Đã xảy ra lỗi khi tra cứu tài khoản. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safev2(SUPPORT_LINK)}"
        )
        if not validate_markdown_v2(error_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong error_message: {error_message}")
            error_message = (
                f"❌ DuyWin: Đã xảy ra lỗi khi tra cứu tài khoản. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}"
            )
            error_parse_mode = None
        else:
            error_parse_mode = "MarkdownV2"
        await update.message.reply_text(error_message, parse_mode=error_parse_mode)