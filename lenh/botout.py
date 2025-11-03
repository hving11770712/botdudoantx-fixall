from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import db, logger, ADMIN_IDS, SUPPORT_LINK, check_ban

async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Kiểm tra quyền admin
    user = update.effective_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *DuyWin*: Chỉ admin mới được dùng lệnh này! 🔐",
            parse_mode="Markdown"
        )
        return

    # Kiểm tra tham số
    if not context.args:
        await update.message.reply_text(
            "📢 *DuyWin*: Vui lòng nhập ID nhóm hoặc @tên nhóm! 📋",
            parse_mode="Markdown"
        )
        return

    target = context.args[0]
    try:
        # Lấy thông tin nhóm
        chat = await context.bot.get_chat(target)
        group_id = chat.id
        group_title = chat.title or "Không rõ"

        # Thêm nhóm vào danh sách chặn
        db.blocked_groups.add(group_id)
        db.save_blocked_groups()

        # Gửi thông báo rời nhóm
        leave_message = "🔌 *DuyWin*: Bot sẽ rời nhóm theo yêu cầu của admin. 👋"
        try:
            await context.bot.send_message(chat_id=group_id, text=leave_message, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Không thể gửi tin nhắn rời tới nhóm {group_id}: {e}")

        # Rời nhóm
        await context.bot.leave_chat(group_id)

        # Xóa thông tin nhóm khỏi group_info
        if str(group_id) in db.group_info:
            del db.group_info[str(group_id)]
            db.save_group_info()

        # Thông báo thành công
        response = f"✅ *DuyWin*: Đã rời nhóm: {group_title} (ID: {group_id})"
        await update.message.reply_text(response, parse_mode="Markdown")

        # Thông báo cho admin khác
        for admin_id in ADMIN_IDS:
            if admin_id != user_id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"🛑 *DuyWin*: Admin @{username} đã cho bot rời nhóm {group_title} (ID: {group_id})!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Không thể gửi thông báo tới admin {admin_id}: {e}")

        # Ghi log
        logger.info(f"Admin @{username} (ID: {user_id}) đã cho bot rời nhóm {group_title} (ID: {group_id})")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /out bởi @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Lỗi khi xử lý nhóm: {e}. Vui lòng thử lại hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )

async def unout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Kiểm tra quyền admin
    user = update.effective_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *DuyWin*: Chỉ admin mới được dùng lệnh này! 🔐",
            parse_mode="Markdown"
        )
        return

    # Kiểm tra tham số
    if not context.args:
        await update.message.reply_text(
            "📢 *DuyWin*: Vui lòng nhập ID nhóm! 📋",
            parse_mode="Markdown"
        )
        return

    target = context.args[0]
    try:
        group_id = int(target)
        if group_id in db.blocked_groups:
            db.blocked_groups.remove(group_id)
            db.save_blocked_groups()
            response = f"✅ *DuyWin*: Đã gỡ chặn nhóm ID: {group_id}"
            await update.message.reply_text(response, parse_mode="Markdown")

            # Thông báo cho admin khác
            for admin_id in ADMIN_IDS:
                if admin_id != user_id:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"🟢 *DuyWin*: Admin @{username} đã gỡ chặn nhóm ID: {group_id}!",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Không thể gửi thông báo tới admin {admin_id}: {e}")

            # Ghi log
            logger.info(f"Admin @{username} (ID: {user_id}) đã gỡ chặn nhóm ID: {group_id}")
        else:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Nhóm ID {group_id} không bị chặn. 🤔",
                parse_mode="Markdown"
            )

    except ValueError:
        await update.message.reply_text(
            f"⚠️ *DuyWin*: ID nhóm không hợp lệ! 😓",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /unout bởi @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Lỗi: {e}. Vui lòng thử lại hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )

async def list_blocked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Kiểm tra quyền admin
    user = update.effective_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *DuyWin*: Chỉ admin mới được dùng lệnh này! 🔐",
            parse_mode="Markdown"
        )
        return

    try:
        if not db.blocked_groups:
            await update.message.reply_text(
                "✅ *DuyWin*: Không có nhóm nào bị chặn! 😊",
                parse_mode="Markdown"
            )
            return

        text = "📋 *Danh sách nhóm bị chặn*:\n\n"
        for gid in db.blocked_groups:
            group_info = db.group_info.get(str(gid), {})
            title = group_info.get("title", "Không rõ")
            text += f"🔒 ID: {gid} - Tên: {title}\n"

        await update.message.reply_text(text, parse_mode="Markdown")
        logger.info(f"Admin @{username} (ID: {user_id}) đã xem danh sách nhóm bị chặn")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /list_blocked bởi @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Lỗi khi liệt kê nhóm: {e}. Vui lòng thử lại hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )

async def groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Kiểm tra quyền admin
    user = update.effective_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 *DuyWin*: Chỉ admin mới được dùng lệnh này! 🔐",
            parse_mode="Markdown"
        )
        return

    try:
        if not db.group_info:
            await update.message.reply_text(
                "✅ *DuyWin*: Bot không ở trong nhóm nào! 😔",
                parse_mode="Markdown"
            )
            return

        text = "📋 *Danh sách nhóm hiện tại*:\n\n"
        for gid, info in db.group_info.items():
            text += (
                f"🔹 *ID*: {gid}\n"
                f"📛 *Tên*: {info.get('title', 'Không rõ')}\n"
                f"🏷️ *Loại*: {info.get('type', 'Không rõ')}\n"
                f"👤 *Thêm bởi*: {info.get('added_by', 'Không rõ')}\n"
                f"⏰ *Thời gian thêm*: {info.get('added_at', 'Không rõ')}\n"
                f"🚫 *Bị chặn*: {'Có' if int(gid) in db.blocked_groups else 'Không'}\n\n"
            )

        await update.message.reply_text(text[:4000], parse_mode="Markdown")
        logger.info(f"Admin @{username} (ID: {user_id}) đã xem danh sách nhóm")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /groups bởi @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Lỗi khi liệt kê nhóm: {e}. Vui lòng thử lại hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )