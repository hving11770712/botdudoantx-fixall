from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import ADMIN_IDS, ACCOUNT_FILE, BANID_FILE, SUPPORT_LINK, check_ban, load_json, save_json, logger, remove_from_old_model

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Kiểm tra quyền admin
    user = update.message.from_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
            parse_mode="Markdown"
        )
        return

    # Kiểm tra tham số
    if not context.args:
        await update.message.reply_text(
            "📢 *DuyWin*: Vui lòng cung cấp ID hoặc username:\n"
            "🔹 /ban <id hoặc username>",
            parse_mode="Markdown"
        )
        return

    target = context.args[0]
    accounts = load_json(ACCOUNT_FILE)
    banned_users = load_json(BANID_FILE)

    # Đảm bảo banned_users là dictionary
    if not isinstance(banned_users, dict):
        logger.warning("ban.json không phải dictionary, khởi tạo lại thành {}")
        banned_users = {}

    try:
        # Kiểm tra xem target là ID hay username
        target_id = None
        target_username = None

        if target.isdigit():
            target_id = int(target)
            for uname, info in accounts.items():
                if info.get("chat_id") == target_id:
                    target_username = uname
                    break
        else:
            target_username = target.lstrip("@")  # Xóa @ nếu có
            if target_username in accounts:
                target_id = accounts[target_username].get("chat_id")
            else:
                await update.message.reply_text(
                    f"⚠️ *DuyWin*: Không tìm thấy người dùng {target}!",
                    parse_mode="Markdown"
                )
                return

        if target_id is None or target_username is None:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Không tìm thấy người dùng {target}!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra xem đã bị khóa chưa
        if str(target_id) in banned_users:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Tài khoản @{target_username} (ID: {target_id}) đã bị khóa trước đó!",
                parse_mode="Markdown"
            )
            return

        # Thêm vào danh sách banned (dùng chat_id dạng chuỗi)
        banned_users[str(target_id)] = {"username": target_username, "banned_by": user_id}
        save_json(BANID_FILE, banned_users)

        # Xóa khỏi model_users
        remove_from_old_model(target_id)

        # Thông báo thành công
        await update.message.reply_text(
            f"✅ *DuyWin*: Đã khóa tài khoản @{target_username} (ID: {target_id})!",
            parse_mode="Markdown"
        )

        # Thông báo tới người dùng bị khóa
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Không thể gửi tin nhắn tới {target_id}: {e}")
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Đã khóa nhưng không thể thông báo tới @{target_username} (có thể đã chặn bot).",
                parse_mode="Markdown"
            )

        # Thông báo cho admin khác
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🛑 *DuyWin*: Admin @{username} đã khóa tài khoản @{target_username} (ID: {target_id})!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Không thể gửi thông báo tới admin {admin_id}: {e}")

        # Ghi log
        logger.info(f"Admin @{username} (ID: {user_id}) đã khóa tài khoản @{target_username} (ID: {target_id})")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /ban bởi @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Kiểm tra quyền admin
    user = update.message.from_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *DuyWin*: Bạn không có quyền sử dụng lệnh này!",
            parse_mode="Markdown"
        )
        return

    # Kiểm tra tham số
    if not context.args:
        await update.message.reply_text(
            "📢 *DuyWin*: Vui lòng cung cấp ID hoặc username:\n"
            "🔹 /unban <id hoặc username>",
            parse_mode="Markdown"
        )
        return

    target = context.args[0]
    accounts = load_json(ACCOUNT_FILE)
    banned_users = load_json(BANID_FILE)

    # Đảm bảo banned_users là dictionary
    if not isinstance(banned_users, dict):
        logger.warning("ban.json không phải dictionary, khởi tạo lại thành {}")
        banned_users = {}

    try:
        # Kiểm tra xem target là ID hay username
        target_id = None
        target_username = None

        if target.isdigit():
            target_id = int(target)
            if str(target_id) in banned_users:
                target_username = banned_users[str(target_id)]["username"]
        else:
            target_username = target.lstrip("@")  # Xóa @ nếu có
            for cid, info in banned_users.items():
                if info["username"] == target_username:
                    target_id = int(cid)
                    break

        if target_id is None or str(target_id) not in banned_users:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Tài khoản {target} không bị khóa!",
                parse_mode="Markdown"
            )
            return

        # Xóa khỏi danh sách banned
        del banned_users[str(target_id)]
        save_json(BANID_FILE, banned_users)

        # Thông báo thành công
        await update.message.reply_text(
            f"✅ *DuyWin*: Đã mở khóa tài khoản @{target_username} (ID: {target_id})!",
            parse_mode="Markdown"
        )

        # Thông báo tới người dùng được mở khóa
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🔓 *DuyWin*: Tài khoản của bạn đã được mở khóa! Liên hệ hỗ trợ nếu cần: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Không thể gửi tin nhắn tới {target_id}: {e}")
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Đã mở khóa nhưng không thể thông báo tới @{target_username} (có thể đã chặn bot).",
                parse_mode="Markdown"
            )

        # Thông báo cho admin khác
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🟢 *DuyWin*: Admin @{username} đã mở khóa tài khoản @{target_username} (ID: {target_id})!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Không thể gửi thông báo tới admin {admin_id}: {e}")

        # Ghi log
        logger.info(f"Admin @{username} (ID: {user_id}) đã mở khóa tài khoản @{target_username} (ID: {target_id})")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /unban bởi @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )