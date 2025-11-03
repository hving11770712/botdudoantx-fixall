from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import (
    check_ban, db, ACCOUNT_FILE, logger, SUPPORT_LINK, ADMIN_IDS,
    escape_markdown_safe, update_username, is_banned, NAP_CONTENT, sync_model_users
)
from datetime import datetime

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý lệnh /start để đăng ký hoặc hiển thị thông tin tài khoản."""
    if await check_ban(update, context):
        return

    user = update.message.from_user
    user_id = user.id
    display_username = user.username.lstrip('@') if user.username else f"ID_{user_id}"
    current_username = escape_markdown_safe(display_username)
    accounts = db.load_json(ACCOUNT_FILE)

    # Xử lý tham số referral từ lệnh /start
    referred_by = None
    if context.args and len(context.args) > 0:
        referred_by = context.args[0]  # Lấy ID người mời từ tham số
        if referred_by == str(user_id):
            referred_by = None  # Ngăn người dùng tự mời chính mình
            logger.info(f"User {user_id} cố gắng tự mời chính mình.")

    try:
        # Tìm bản ghi hiện có dựa trên user_id
        existing_account_key = None
        for key, info in accounts.items():
            if info.get("user_id") == user_id:
                existing_account_key = key
                break

        # Luôn sử dụng user_id làm khóa chính cho tài khoản
        account_key = str(user_id)
        is_new_user = existing_account_key is None

        # Tạo nội dung nạp
        nap_content = f"{NAP_CONTENT}{user_id}"

        if is_new_user:
            # Tạo tài khoản mới với account_key là user_id
            accounts[account_key] = {
                "balance": 0,
                "model": [],
                "model_expiry": {},
                "user_id": user_id,
                "username": display_username,
                "chat_id": user_id,  # Luôn luôn là user_id, không cần phân biệt nhóm/cá nhân
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "referral_code": f"REF{user_id}",
                "referred_by": referred_by,
                "referred_users": [],
                "referral_commission": 0,
                "withdrawn_commission": 0,
                "username_history": [],
                "nap_content": nap_content
            }
            logger.info(f"Đã tạo tài khoản mới cho @{display_username} (user_id: {user_id}, nap_content: {nap_content}, referred_by: {referred_by})")
            
            # Cập nhật danh sách referred_users của người mời
            if referred_by and referred_by in accounts:
                accounts[referred_by]["referred_users"].append(account_key)
                logger.info(f"Đã thêm {account_key} vào danh sách referred_users của {referred_by}")
        else:
            # Cập nhật tài khoản hiện có
            account_key = existing_account_key
            if "referral_code" not in accounts[account_key]:
                accounts[account_key]["referral_code"] = f"REF{user_id}"
                logger.info(f"Đã cập nhật referral_code cho @{display_username}")
            if "nap_content" not in accounts[account_key]:
                accounts[account_key]["nap_content"] = nap_content
                logger.info(f"Đã cập nhật nap_content cho @{display_username}: {nap_content}")
            if "referred_by" not in accounts[account_key]:
                accounts[account_key]["referred_by"] = None
            if "referred_users" not in accounts[account_key]:
                accounts[account_key]["referred_users"] = []
            if "referral_commission" not in accounts[account_key]:
                accounts[account_key]["referral_commission"] = 0
            if "withdrawn_commission" not in accounts[account_key]:
                accounts[account_key]["withdrawn_commission"] = 0
            if "model_expiry" not in accounts[account_key]:
                accounts[account_key]["model_expiry"] = {}
            accounts[account_key]["user_id"] = user_id
            accounts[account_key]["chat_id"] = user_id  # Luôn update về user_id
            update_username(accounts, account_key, display_username, user_id)
            # Chuyển model cũ sang dạng list nếu là string
            if isinstance(accounts[account_key].get("model"), str):
                old_model = accounts[account_key].get("model", "none")
                old_expiry = accounts[account_key].get("model_expiry")
                accounts[account_key]["model"] = [old_model] if old_model != "none" else []
                accounts[account_key]["model_expiry"] = {old_model: old_expiry} if old_model != "none" and old_expiry else {}

        db.save_json(ACCOUNT_FILE, accounts)
        sync_model_users()  # Đồng bộ model_users sau khi cập nhật tài khoản

        user_info = accounts[account_key]
        balance = user_info.get("balance", 0)
        models = user_info.get("model", [])
        created_at = escape_markdown_safe(user_info.get("created_at", "Không rõ"))
        nap_content = escape_markdown_safe(user_info.get("nap_content", "Không rõ"))
        model_text = escape_markdown_safe(", ".join([m.capitalize() for m in models]) if models else "Chưa kích hoạt")
        referred_users_count = len(user_info.get("referred_users", []))
        referral_commission = user_info.get("referral_commission", 0)
        withdrawn_commission = user_info.get("withdrawn_commission", 0)

        # Thêm thông tin thời hạn model nếu có
        expiry_text = ""
        if models and "model_expiry" in user_info:
            expiry_text = "\n".join([
                f"⏰ *Hạn {m.capitalize()}*: {escape_markdown_safe(user_info['model_expiry'].get(m, 'Không rõ'))}"
                for m in models if user_info['model_expiry'].get(m)
            ])
            if expiry_text:
                expiry_text = f"\n{expiry_text}"

        if is_new_user:
            welcome_message = (
                f"🎉 *Chào mừng bạn đến với DuyWin\\!* 🎉\n\n"
                f"🔍 *Thông tin tài khoản*:\n"
                f"👤 *Tên*: @{current_username}\n"
                f"💰 *Số dư*: {escape_markdown_safe(f'{balance:,}')} VNĐ\n"
                f"📊 *Gói dự đoán*: {model_text}\n"
                f"{expiry_text}\n"
                f"📅 *Ngày tham gia*: {created_at}\n"
                f"📩 *Mã mời bạn bè*: {escape_markdown_safe(user_info['referral_code'])}\n"
                f"💸 *Nội dung nạp*: {nap_content}\n"
                f"👥 *Bạn bè đã mời*: {referred_users_count}\n"
                f"💰 *Hoa hồng hiện tại*: {escape_markdown_safe(f'{referral_commission:,}')} VNĐ\n"
                f"💸 *Hoa hồng đã rút*: {escape_markdown_safe(f'{withdrawn_commission:,}')} VNĐ\n\n"
                f"💡 *Dùng bot để nhận dự đoán chính xác và kiếm lợi nhuận\\!*\n"
                f"👇 Dùng /help để xem chi tiết các lệnh hoặc /ref để xem thông tin mời bạn bè\\."
            )
        else:
            welcome_message = (
                f"👋 *Chào mừng @{current_username} quay trở lại với DuyWin\\!* 🎉\n\n"
                f"🔍 *Thông tin tài khoản*:\n"
                f"💰 *Số dư*: {escape_markdown_safe(f'{balance:,}')} VNĐ\n"
                f"📊 *Gói dự đoán*: {model_text}\n"
                f"{expiry_text}\n"
                f"💸 *Nội dung nạp*: {nap_content}\n"
                f"👥 *Bạn bè đã mời*: {referred_users_count}\n"
                f"💰 *Hoa hồng hiện tại*: {escape_markdown_safe(f'{referral_commission:,}')} VNĐ\n"
                f"💸 *Hoa hồng đã rút*: {escape_markdown_safe(f'{withdrawn_commission:,}')} VNĐ\n\n"
                f"💡 Dùng /help để xem các lệnh hoặc /ref để xem thông tin mời bạn bè\\!"
            )

        logger.debug(f"Gửi tin nhắn chào mừng: {welcome_message}")
        try:
            await update.message.reply_text(welcome_message, parse_mode="MarkdownV2")
        except Exception as e:
            logger.error(f"Phân tích MarkdownV2 thất bại: {e}. Gửi văn bản thuần túy.")
            plain_message = welcome_message.replace('\\*', '*').replace('\\_', '_').replace('\\`', '`').replace('\\-', '-').replace('\\(', '(').replace('\\)', ')').replace('\\', '')
            await update.message.reply_text(plain_message, parse_mode=None)

        if is_new_user:
            for admin_id in ADMIN_IDS:
                if not is_banned(admin_id):
                    try:
                        admin_message = (
                            f"*DuyWin🆕*\n\n"
                            f"Người dùng mới: @{escape_markdown_safe(display_username)}\n"
                            f"ID: {escape_markdown_safe(str(user_id))}\n"
                            f"Chat ID: {escape_markdown_safe(str(user_id))}\n"
                            f"Nội dung nạp: {nap_content}\n"
                            f"Người mời: {escape_markdown_safe(accounts.get(referred_by, {}).get('username', 'Không có')) if referred_by else 'Không có'}\n"
                            f"Đã tham gia!"
                        )
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message,
                            parse_mode="MarkdownV2"
                        )
                    except Exception as e:
                        logger.error(f"Không thể gửi thông báo tới admin {admin_id}: {e}")
                        try:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"DuyWin🆕\n"
                                     f"Người dùng mới: @{display_username}\n"
                                     f"ID: {user_id}\n"
                                     f"Chat ID: {user_id}\n"
                                     f"Nội dung nạp: {nap_content}\n"
                                     f"Người mời: {accounts.get(referred_by, {}).get('username', 'Không có') if referred_by else 'Không có'}\n"
                                     f"Đã tham gia!"
                            )
                        except Exception as e2:
                            logger.error(f"Lỗi gửi thông báo fallback tới admin {admin_id}: {e2}")

        logger.info(f"Lệnh /start được gọi bởi @{display_username} (user_id: {user_id}, nap_content: {nap_content}, referred_by: {referred_by})")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /start cho @{display_username} (user_id: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra\\! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
            parse_mode="MarkdownV2"
        )
