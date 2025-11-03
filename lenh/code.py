from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import check_ban, db, ACCOUNT_FILE, GIFTCODE_FILE, logger, SUPPORT_LINK, ADMIN_IDS, escape_markdown_safev2, validate_markdown_v2

# Định nghĩa file lưu lịch sử sử dụng giftcode
CODE_HISTORY_FILE = "data/code.json"

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /code để người dùng nhập giftcode"""
    if not update.message or not update.message.from_user:
        logger.warning("Update không chứa message hoặc from_user trong lệnh /code")
        return

    user_id = update.message.from_user.id
    user_id_str = str(user_id)  # Sử dụng user_id dạng chuỗi làm khóa chính
    raw_username = update.message.from_user.username.lstrip('@') if update.message.from_user.username else user_id_str

    try:
        # Kiểm tra nếu người dùng bị cấm
        if await check_ban(update, context):
            logger.warning(f"User_id {user_id} (@{raw_username}) bị cấm, không thể sử dụng /code")
            return

        # Kiểm tra tham số đầu vào
        if not context.args:
            logger.warning(f"User_id {user_id} (@{raw_username}) không cung cấp mã code")
            error_message = f"❌ *DuyWin*: Vui lòng nhập mã code: `/code <mã code>`"
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                error_message = f"❌ DuyWin: Vui lòng nhập mã code: /code <mã code>"
                parse_mode = None
            else:
                parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        code_str = context.args[0]

        # Tải dữ liệu giftcode và tài khoản
        giftcodes = db.load_json(GIFTCODE_FILE)
        accounts = db.load_json(ACCOUNT_FILE)
        code_history = db.load_json(CODE_HISTORY_FILE)

        # Đảm bảo code_history[user_id_str] là danh sách
        if user_id_str not in code_history or not isinstance(code_history[user_id_str], list):
            code_history[user_id_str] = []
            logger.info(f"Khởi tạo lịch sử giftcode cho user_id {user_id_str}")

        # Kiểm tra tài khoản tồn tại
        if user_id_str not in accounts:
            logger.warning(f"Tài khoản user_id {user_id_str} (@{raw_username}) chưa đăng ký")
            error_message = f"❌ *DuyWin*: Tài khoản của bạn chưa được đăng ký! Hãy sử dụng /start để đăng ký\\."
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                error_message = f"❌ DuyWin: Tài khoản của bạn chưa được đăng ký! Hãy sử dụng /start để đăng ký."
                parse_mode = None
            else:
                parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra mã giftcode hợp lệ
        if code_str not in giftcodes:
            logger.warning(f"Mã code {code_str} không hợp lệ từ user_id {user_id_str}")
            error_message = f"❌ *DuyWin*: Mã code `{escape_markdown_safev2(code_str)}` không hợp lệ\\!"
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                error_message = f"❌ DuyWin: Mã code {code_str} không hợp lệ!"
                parse_mode = None
            else:
                parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        gift = giftcodes[code_str]

        # Đảm bảo used_by là danh sách
        if "used_by" not in gift or not isinstance(gift["used_by"], list):
            gift["used_by"] = []
            logger.info(f"Khởi tạo danh sách used_by cho mã code {code_str}")

        # Kiểm tra đã sử dụng
        if user_id_str in gift["used_by"]:
            logger.warning(f"User_id {user_id_str} (@{raw_username}) đã sử dụng mã code {code_str}")
            error_message = f"❌ *DuyWin*: Bạn đã sử dụng mã code `{escape_markdown_safev2(code_str)}` trước đó\\!"
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                error_message = f"❌ DuyWin: Bạn đã sử dụng mã code {code_str} trước đó!"
                parse_mode = None
            else:
                parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra số lần sử dụng
        if gift["uses"] <= 0:
            logger.warning(f"Mã code {code_str} đã hết lượt sử dụng, từ user_id {user_id_str}")
            error_message = f"❌ *DuyWin*: Mã code `{escape_markdown_safev2(code_str)}` đã hết lượt sử dụng\\!"
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                error_message = f"❌ DuyWin: Mã code {code_str} đã hết lượt sử dụng!"
                parse_mode = None
            else:
                parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra thời hạn
        try:
            expiry = datetime.strptime(gift["expiry"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiry:
                logger.warning(f"Mã code {code_str} đã hết hạn, từ user_id {user_id_str}")
                error_message = f"❌ *DuyWin*: Mã code `{escape_markdown_safev2(code_str)}` đã hết hạn vào `{escape_markdown_safev2(gift['expiry'])}`\\!"
                if not validate_markdown_v2(error_message):
                    logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                    error_message = f"❌ DuyWin: Mã code {code_str} đã hết hạn vào {gift['expiry']}!"
                    parse_mode = None
                else:
                    parse_mode = "MarkdownV2"
                await update.message.reply_text(error_message, parse_mode=parse_mode)
                return
        except ValueError:
            logger.error(f"Thời hạn không hợp lệ cho mã code {code_str}: {gift.get('expiry')}")
            error_message = (
                f"❌ *DuyWin*: Lỗi dữ liệu thời hạn mã code\\. "
                f"Liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
            )
            if not validate_markdown_v2(error_message):
                logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
                error_message = f"❌ DuyWin: Lỗi dữ liệu thời hạn mã code. Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
                parse_mode = None
            else:
                parse_mode = "MarkdownV2"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Áp dụng giftcode
        from lenh.config import backup_data
        backup_data()  # Sao lưu dữ liệu trước khi ghi

        gift["uses"] -= 1
        gift["used_by"].append(user_id_str)  # Lưu user_id thay vì username
        accounts[user_id_str]["balance"] = accounts[user_id_str].get("balance", 0) + gift["amount"]

        # Ghi lịch sử sử dụng giftcode vào code_history
        used_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        code_history[user_id_str].append({
            "code": code_str,
            "amount": gift["amount"],
            "used_at": used_at
        })

        # Lưu dữ liệu
        db.save_json(ACCOUNT_FILE, accounts)
        db.save_json(GIFTCODE_FILE, giftcodes)
        db.save_json(CODE_HISTORY_FILE, code_history)
        logger.info(f"User_id {user_id_str} (@{raw_username}) đã sử dụng mã code {code_str}, nhận {gift['amount']} VNĐ")

        # Gửi thông báo cho người dùng
        balance_str = f"{accounts[user_id_str]['balance']:,}".replace(",", ".")
        user_message = (
            f"✅ *DuyWin*: Đã áp dụng mã `{escape_markdown_safev2(code_str)}`\\! "
            f"Bạn nhận được `{gift['amount']:,}` VNĐ\\. Số dư mới: `{escape_markdown_safev2(balance_str)}` VNĐ\\."
        )
        if not validate_markdown_v2(user_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {user_message}")
            user_message = (
                f"✅ DuyWin: Đã áp dụng mã {code_str}! "
                f"Bạn nhận được {gift['amount']:,} VNĐ. Số dư mới: {balance_str} VNĐ."
            )
            parse_mode = None
        else:
            parse_mode = "MarkdownV2"
        await update.message.reply_text(user_message, parse_mode=parse_mode)

        # Thông báo cho admin
        admin_message = (
            f"📩 *DuyWin*: Người dùng @{escape_markdown_safev2(raw_username)} \\(ID: `{escape_markdown_safev2(user_id_str)}`\\) "
            f"đã sử dụng mã code `{escape_markdown_safev2(code_str)}` và nhận `{gift['amount']:,}` VNĐ\\."
        )
        if not validate_markdown_v2(admin_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {admin_message}")
            admin_message = (
                f"📩 DuyWin: Người dùng @{raw_username} (ID: {user_id_str}) "
                f"đã sử dụng mã code {code_str} và nhận {gift['amount']:,} VNĐ."
            )
            admin_parse_mode = None
        else:
            admin_parse_mode = "MarkdownV2"

        for admin_id in ADMIN_IDS:
            if not db.is_banned(admin_id):
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode=admin_parse_mode
                    )
                    logger.info(f"Đã gửi thông báo cho admin {admin_id}")
                except Exception as e:
                    logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
                    safe_fallback_message = (
                        f"📩 DuyWin: Người dùng @{raw_username} (ID: {user_id_str}) "
                        f"đã sử dụng mã code {code_str} và nhận {gift['amount']:,} VNĐ."
                    )
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=safe_fallback_message
                        )
                        logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                    except Exception as e2:
                        logger.error(f"Lỗi khi gửi thông báo fallback admin {admin_id}: {str(e2)}")

    except Exception as e:
        logger.error(f"Lỗi trong hàm code_command cho user_id {user_id_str}: {str(e)}")
        error_message = (
            f"❌ *DuyWin*: Đã xảy ra lỗi khi áp dụng mã code\\. "
            f"Vui lòng thử lại sau hoặc liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
        )
        if not validate_markdown_v2(error_message):
            logger.warning(f"Cú pháp MarkdownV2 không hợp lệ: {error_message}")
            error_message = (
                f"❌ DuyWin: Đã xảy ra lỗi khi áp dụng mã code. "
                f"Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
            )
            parse_mode = None
        else:
            parse_mode = "MarkdownV2"
        await update.message.reply_text(error_message, parse_mode=parse_mode)