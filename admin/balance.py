import os
from telegram import Update
from telegram.ext import ContextTypes
from filelock import FileLock
from lenh.config import (
    ADMIN_IDS, ACCOUNT_FILE, UPDATE_BALANCE, UPDATE_BALANCE, db, logger, SUPPORT_LINK, escape_markdown_safe
)
from datetime import datetime

# Hàm đơn giản: Kiểm tra định dạng số tiền
def validate_amount(amount_str: str) -> tuple[bool, int]:
    """Kiểm tra định dạng số tiền (+/- số). Trả về (is_valid, amount)."""
    if not amount_str.startswith(('+', '-')) or not amount_str[1:].isdigit():
        return False, 0
    return True, int(amount_str[1:]) if amount_str.startswith('+') else -int(amount_str[1:])

# Hàm đơn giản: Kiểm tra lý do hợp lệ
def validate_reason(reason: str) -> bool:
    """Kiểm tra lý do có hợp lệ (không rỗng và không quá dài)."""
    return bool(reason.strip()) and len(reason.strip()) <= 200

# Hàm trung bình: Ghi lịch sử giao dịch vào taikhoan.json
def log_transaction(accounts: dict, account_key: str, amount: int, reason: str, admin_id: int, timestamp: str) -> None:
    """Lưu giao dịch vào transaction_history trong tài khoản."""
    if "transaction_history" not in accounts[account_key]:
        accounts[account_key]["transaction_history"] = []
    accounts[account_key]["transaction_history"].append({
        "amount": amount,
        "reason": reason,
        "admin_id": admin_id,
        "timestamp": timestamp
    })
    # Giới hạn lịch sử giao dịch (ví dụ: 50 giao dịch gần nhất)
    accounts[account_key]["transaction_history"] = accounts[account_key]["transaction_history"][-50:]

# Hàm nâng cao: Lấy lịch sử giao dịch gần đây
def get_recent_transactions(accounts: dict, account_key: str, limit: int = 5) -> str:
    """Trả về chuỗi lịch sử giao dịch gần đây cho tài khoản."""
    history = accounts[account_key].get("transaction_history", [])
    if not history:
        return "Không có lịch sử giao dịch\n"
    history_text = ""
    for entry in history[-limit:]:
        amount = entry.get("amount", 0)
        formatted_amount = escape_markdown_safe(f"{abs(amount):,}".replace(",", "."))
        action = "Cộng" if amount >= 0 else "Trừ"
        reason = escape_markdown_safe(entry.get("reason", "Không rõ"))
        timestamp = escape_markdown_safe(entry.get("timestamp", "Không rõ"))
        admin_id = escape_markdown_safe(str(entry.get("admin_id", "Không rõ")))
        history_text += (
            f"\\- {action} `{formatted_amount}` VNĐ, Lý do: `{reason}`, "
            f"Admin ID: `{admin_id}`, Thời gian: `{timestamp}`\n"
        )
    return history_text

# Hàm nâng cao: Kiểm tra giới hạn giao dịch
def check_transaction_limits(amount: int) -> tuple[bool, str]:
    """Kiểm tra giới hạn giao dịch tối thiểu/tối đa."""
    MIN_AMOUNT = 10000  # Tối thiểu 10,000 VNĐ
    MAX_AMOUNT = 100000000  # Tối đa 100,000,000 VNĐ
    abs_amount = abs(amount)
    if abs_amount < MIN_AMOUNT:
        return False, f"Số tiền phải ít nhất `{MIN_AMOUNT:,}` VNĐ"
    if abs_amount > MAX_AMOUNT:
        return False, f"Số tiền không được vượt quá `{MAX_AMOUNT:,}` VNĐ"
    return True, ""

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /xtnaptien để admin cộng hoặc trừ tiền vào tài khoản người dùng."""
    user = update.message.from_user
    user_id = user.id
    raw_username = user.username.lstrip('@') if user.username else str(user_id)
    display_username = escape_markdown_safe(raw_username)

    try:
        # Kiểm tra quyền admin
        if user_id not in ADMIN_IDS:
            logger.warning(f"User_id {user_id} (@{raw_username}) không có quyền sử dụng /xtnaptien")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn không có quyền sử dụng lệnh này\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra cú pháp lệnh
        if len(context.args) < 3 or not context.args[0].isdigit() or not validate_amount(context.args[1])[0]:
            await update.message.reply_text(
                f"❌ *DuyWin*: Vui lòng nhập: `/xtnaptien <user_id> <(+,-)số tiền> <nội dung (lý do)>`",
                parse_mode="MarkdownV2"
            )
            return

        target_user_id = int(context.args[0])
        amount_str = context.args[1]
        reason = ' '.join(context.args[2:]).strip() or "Không có lý do"
        is_valid_amount, amount = validate_amount(amount_str)
        safe_reason = escape_markdown_safe(reason)

        # Kiểm tra lý do hợp lệ
        if not validate_reason(reason):
            logger.warning(f"Lý do không hợp lệ từ user_id {user_id}: {reason}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Lý do không hợp lệ hoặc quá dài (tối đa 200 ký tự)\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra giới hạn giao dịch
        is_valid_transaction, error_msg = check_transaction_limits(amount)
        if not is_valid_transaction:
            logger.warning(f"Giao dịch không hợp lệ từ user_id {user_id}: {error_msg}")
            await update.message.reply_text(
                f"❌ *DuyWin*: {escape_markdown_safe(error_msg)}\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra tài khoản người dùng
        accounts = db.load_json(ACCOUNT_FILE)
        account_key = str(target_user_id)
        if account_key not in accounts:
            logger.warning(f"Tài khoản user_id {target_user_id} không tồn tại trong {ACCOUNT_FILE}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Tài khoản với ID `{escape_markdown_safe(str(target_user_id))}` không tồn tại\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra số dư âm
        new_balance = accounts[account_key].get("balance", 0) + amount
        if new_balance < 0:
            logger.warning(f"Số dư âm sau khi xử lý cho user_id {target_user_id}: {new_balance}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Số dư sẽ âm sau khi xử lý\\! Số dư hiện tại: `{escape_markdown_safe(str(accounts[account_key]['balance']))}` VNĐ\\.",
                parse_mode="MarkdownV2"
            )
            return

        # Cập nhật số dư và lưu lịch sử giao dịch
        accounts[account_key]["balance"] = new_balance
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_transaction(accounts, account_key, amount, reason, user_id, timestamp)
        db.save_json(ACCOUNT_FILE, accounts)

        req_username = accounts[account_key]["username"]
        safe_username = escape_markdown_safe(req_username)
        formatted_amount = escape_markdown_safe(f"{abs(amount):,}".replace(",", "."))
        action_text = "cộng" if amount >= 0 else "trừ"

        # Ghi giao dịch vào naptien.txt
        os.makedirs(os.path.dirname(UPDATE_BALANCE), exist_ok=True)
        with FileLock(f"{UPDATE_BALANCE}.lock"):
            line_count = sum(1 for _ in open(UPDATE_BALANCE, "r", encoding="utf-8")) if os.path.exists(UPDATE_BALANCE) else 0
            with open(UPDATE_BALANCE, "a", encoding="utf-8") as f:
                f.write(f"{line_count + 1}|{target_user_id}|{amount}|{reason}|{timestamp}\n")
        logger.info(f"User_id {user_id} (@{raw_username}) đã {action_text} {abs(amount)} VNĐ cho user_id {target_user_id} (@{req_username}), lý do: {reason}")

        # Gửi thông báo cho admin thực hiện lệnh
        recent_transactions = get_recent_transactions(accounts, account_key)
        await update.message.reply_text(
            f"✅ *DuyWin*: Đã {action_text} `{formatted_amount}` VNĐ\n"
            f"Cho: `@{safe_username}` \\(ID: {escape_markdown_safe(str(target_user_id))}\\)\n"
            f"Lý do: `{safe_reason}`\n"
            f"📜 *Lịch sử giao dịch gần đây*:\n{recent_transactions}",
            parse_mode="MarkdownV2"
        )

        # Gửi thông báo cho người dùng
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"✅ *DuyWin*: Số dư \n"
                    f"Tài khoản của bạn đã được {action_text} `{formatted_amount}` VNĐ\\!\n"
                    f"Số dư mới: `{escape_markdown_safe(str(accounts[account_key]['balance']))}` VNĐ\n"
                    f"Lý do: `{safe_reason}`"
                ),
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            logger.error(f"Lỗi khi gửi thông báo cho user_id {target_user_id}: {str(e)}")
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Không thể gửi thông báo cho `@{safe_username}` \\(user_id: {target_user_id}\\). Vui lòng kiểm tra thủ công\\!",
                parse_mode="MarkdownV2"
            )

        # Gửi thông báo cho admin khác
        admin_username = escape_markdown_safe(raw_username)
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"📩 *DuyWin*: Admin @{admin_username} \\(user_id: {user_id}\\) \n"
                            f"Đã {action_text} `{formatted_amount}` VNĐ cho `@{safe_username}` \\(ID: {target_user_id}\\)\n"
                            f"Lý do: `{safe_reason}`\n"
                            f"📜 *Lịch sử giao dịch gần đây*:\n{recent_transactions}"
                        ),
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=(
                                f"📩 DuyWin: Admin @{raw_username} (user_id: {user_id}) đã {action_text} "
                                f"{abs(amount):,} VNĐ cho @{req_username} (ID: {target_user_id})\n"
                                f"Lý do: {reason}\n"
                                f"Lịch sử giao dịch gần đây:\n{recent_transactions.replace('\\', '')}"
                            )
                        )
                        logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                    except Exception as e2:
                        logger.error(f"Lỗi khi gửi thông báo fallback admin {admin_id}: {str(e2)}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm xtnaptien_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi xử lý yêu cầu\\. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
            parse_mode="MarkdownV2"
        )