import os
import re
from datetime import datetime
from urllib.parse import quote
from telegram import Update
from telegram.ext import ContextTypes

# Giả sử các hằng số và hàm này được import chính xác từ tệp config của bạn.
# Tôi đã sử dụng tên hàm `escape_markdown_safe` như bạn đã cung cấp.
# Hãy chắc chắn rằng tên hàm khớp với tệp config của bạn (ví dụ: escape_markdown_safev2).
from lenh.config import (
    ADMIN_IDS,
    NAPTIEN_FILE,
    check_ban,
    logger,
    SUPPORT_LINK,
    BANK_NAME,
    ACCOUNT_NO,
    ACCOUNT_NAME,
    escape_markdown_safe, # Đổi tên từ escape_markdown_safev2 để khớp với hàm bạn cung cấp
    validate_markdown_v2
)

async def naptien_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /naptien để người dùng gửi yêu cầu nạp tiền"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"ID_{user_id}"

    try:
        # Kiểm tra nếu người dùng bị cấm
        if await check_ban(update, context):
            logger.warning(f"User_id {user_id} (@{username}) bị cấm, không thể sử dụng /naptien")
            return

        # Kiểm tra tham số đầu vào
        if not context.args or not context.args[0].isdigit():
            logger.warning(f"User_id {user_id} (@{username}) không cung cấp số tiền hợp lệ")
            await update.message.reply_text(
                "❌ *DuyWin*: Vui lòng nhập số tiền hợp lệ: `/naptien <số tiền>`",
                parse_mode="MarkdownV2"
            )
            return

        amount = int(context.args[0])
        if amount <= 0:
            logger.warning(f"User_id {user_id} (@{username}) nhập số tiền không hợp lệ: {amount}")
            # SỬA LỖI: Thoát ký tự '!'
            await update.message.reply_text(
                "❌ *DuyWin*: Số tiền phải là số nguyên dương\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Tạo nội dung chuyển khoản
        transfer_context = f"DW{user_id}"

        # Tạo link QR code (giữ nguyên URL của bạn)
        qr_url = (
            f"https://api.vietqr.io/{BANK_NAME}/{ACCOUNT_NO}/{amount}/{transfer_context}/vietqr_net_2.jpg"
            f"?accountName={quote(ACCOUNT_NAME)}"
        )

        # Tạo thông tin thanh toán
        # SỬA LỖI: Định dạng số tiền và thoát ký tự '.'
        safe_amount = escape_markdown_safe(f"{amount:,}".replace(",", "."))
        safe_bank_name = escape_markdown_safe(BANK_NAME)
        safe_account_no = escape_markdown_safe(ACCOUNT_NO)
        safe_account_name = escape_markdown_safe(ACCOUNT_NAME)
        safe_transfer_context = escape_markdown_safe(transfer_context)

        # SỬA LỖI: Thoát các ký tự đặc biệt '!' và '-' trong phần văn bản tĩnh.
        # Nội dung của URL trong [text](url) không cần thoát.
        payment_info = (
            f"✅ *DuyWin*: Yêu cầu nạp `{safe_amount}` VNĐ đã được gửi\\!\n"
            f"**Thông tin thanh toán**:\n"
            f"\\- Ngân hàng: {safe_bank_name}\n"
            f"\\- STK: `{safe_account_no}`\n"
            f"\\- Chủ TK: {safe_account_name}\n"
            f"\\- Nội dung: `{safe_transfer_context}`\n"
            f"\\- Quét mã QR: [QR Code]({qr_url})\n"
            f"Vui lòng chuyển khoản và đợi admin xác nhận\\!"
        )

        # Logic kiểm tra và fallback là một thói quen tốt, giữ nguyên.
        if not validate_markdown_v2(payment_info):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong payment_info: {payment_info}")
            payment_info = (
                f"✅ DuyWin: Yêu cầu nạp {amount:,} VNĐ đã được gửi!\n"
                f"Thông tin thanh toán:\n"
                f"- Ngân hàng: {BANK_NAME}\n"
                f"- STK: {ACCOUNT_NO}\n"
                f"- Chủ TK: {ACCOUNT_NAME}\n"
                f"- Nội dung: {transfer_context}\n"
                f"- Quét mã QR: {qr_url}\n"
                f"Vui lòng chuyển khoản và đợi admin xác nhận!"
            )
            parse_mode = None
        else:
            parse_mode = "MarkdownV2"

        await update.message.reply_text(payment_info, parse_mode=parse_mode, disable_web_page_preview=False)

        # Ghi yêu cầu nạp tiền vào file
        os.makedirs(os.path.dirname(NAPTIEN_FILE), exist_ok=True)
        line_count = sum(1 for _ in open(NAPTIEN_FILE, "r", encoding="utf-8")) if os.path.exists(NAPTIEN_FILE) else 0
        with open(NAPTIEN_FILE, "a", encoding="utf-8") as f:
            f.write(f"{line_count + 1}|{user_id}|{amount}|Chưa xác nhận\n")
        logger.info(f"User_id {user_id} (@{username}) đã gửi yêu cầu nạp {amount} VNĐ, dòng {line_count + 1}")

        # Thông báo cho admin
        safe_username = escape_markdown_safe(username)
        formatted_amount = f"{amount:,}".replace(",", ".")
        safe_formatted_amount = escape_markdown_safe(formatted_amount)
        request_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_request_time = escape_markdown_safe(request_time)
        safe_line_count = escape_markdown_safe(str(line_count + 1))
        safe_user_id = escape_markdown_safe(str(user_id))

        # Cải thiện: Gộp ID vào dòng người dùng cho gọn
        admin_message = (
            f"📩 *DuyWin*: Yêu cầu nạp tiền:\n"
            f"👤 Người dùng: @{safe_username} \\(ID: {safe_user_id}\\)\n"
            f"💰 Nạp: `{safe_formatted_amount}` VNĐ\n"
            f"📝 Nội dung CK: `{safe_transfer_context}`\n"
            f"⏰ Thời gian: `{safe_request_time}`\n"
            f"📑 Dòng: `{safe_line_count}`"
        )

        if not validate_markdown_v2(admin_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong admin_message: {admin_message}")
            admin_message = (
                f"📩 DuyWin: Yêu cầu nạp tiền:\n"
                f"👤 Người dùng: @{username} (ID: {user_id})\n"
                f"💰 Nạp: {formatted_amount} VNĐ\n"
                f"📝 Nội dung CK: {transfer_context}\n"
                f"⏰ Thời gian: {request_time}\n"
                f"📑 Dòng: {line_count + 1}"
            )
            admin_parse_mode = None
        else:
            admin_parse_mode = "MarkdownV2"

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode=admin_parse_mode
                )
            except Exception as e:
                logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
                try:
                    fallback_text = (
                        f"📩 DuyWin: Yêu cầu nạp tiền:\n"
                        f"👤 Người dùng: @{username} (ID: {user_id})\n"
                        f"💰 Nạp: {formatted_amount} VNĐ\n"
                        f"📝 Nội dung CK: {transfer_context}\n"
                        f"⏰ Thời gian: {request_time}\n"
                        f"📑 Dòng: {line_count + 1}"
                    )
                    await context.bot.send_message(chat_id=admin_id, text=fallback_text)
                    logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                except Exception as e2:
                    logger.error(f"Lỗi khi gửi thông báo fallback admin {admin_id}: {str(e2)}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm naptien_command cho user_id {user_id}: {str(e)}")
        # SỬA LỖI: Thoát ký tự '.' trong tin nhắn báo lỗi
        error_message = (
            f"❌ *DuyWin*: Đã xảy ra lỗi khi gửi yêu cầu nạp tiền\\.\n"
            f"Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}"
        )
        if not validate_markdown_v2(error_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ trong error_message: {error_message}")
            error_message = (
                f"❌ DuyWin: Đã xảy ra lỗi khi gửi yêu cầu nạp tiền. "
                f"Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}"
            )
            error_parse_mode = None
        else:
            error_parse_mode = "MarkdownV2"
        await update.message.reply_text(error_message, parse_mode=error_parse_mode)
