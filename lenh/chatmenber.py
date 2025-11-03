from datetime import datetime
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from lenh.config import db, logger, ADMIN_IDS, SUPPORT_LINK, is_banned

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        member = update.my_chat_member
        chat = member.chat
        inviter = update.effective_user
        inviter_id = inviter.id
        inviter_username = inviter.username or f"ID_{inviter_id}"

        # Kiểm tra xem người thêm bot có bị cấm không
        if is_banned(inviter_id):
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"🔒 *DuyWin*: Tài khoản @{inviter_username} đã bị khóa và không thể thêm bot vào nhóm! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            await context.bot.leave_chat(chat.id)
            logger.info(f"Người dùng bị cấm @{inviter_username} (ID: {inviter_id}) cố thêm bot vào nhóm {chat.title} (ID: {chat.id})")
            return

        # Kiểm tra trạng thái bot trong nhóm
        if member.new_chat_member.status == ChatMember.MEMBER:
            # Nếu nhóm bị chặn, lưu thông tin trước khi rời
            if chat.id in db.blocked_groups:
                db.group_info[str(chat.id)] = {
                    "title": chat.title or "Không rõ",
                    "added_by": inviter_username,
                    "added_at": datetime.now().isoformat(),
                    "type": chat.type
                }
                db.save_group_info()
                await context.bot.send_message(
                    chat_id=chat.id,
                    text=f"🔌 *DuyWin*: Nhóm này đã bị chặn bởi admin. Bot sẽ rời nhóm. 👋",
                    parse_mode="Markdown"
                )
                await context.bot.leave_chat(chat.id)
                logger.info(f"Bot rời nhóm bị chặn {chat.title} (ID: {chat.id})")
                return

            # Lưu thông tin nhóm
            db.group_info[str(chat.id)] = {
                "title": chat.title or "Không rõ",
                "added_by": inviter_username,
                "added_at": datetime.now().isoformat(),
                "type": chat.type
            }
            db.save_group_info()

            # Thông báo cho admin
            msg = (
                f"🎉 *DuyWin*: Bot được thêm vào nhóm: {chat.title} (ID: {chat.id})\n"
                f"🏷️ *Loại*: {chat.type}\n"
                f"👤 *Mời bởi*: @{inviter_username} (ID: {inviter_id})\n"
                f"💡 Dùng /out {chat.id} để xóa bot khỏi nhóm."
            )
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=msg,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Không thể gửi thông báo tới admin {admin_id}: {e}")

            # Gửi thông báo chào mừng trong nhóm
            welcome_msg = (
                f"👋 *Xin chào!* Mình là *DuyWin* - bot quản lý nhóm! 😊\n"
                "Mình hỗ trợ quản lý và cung cấp dự đoán chính xác.\n"
                "🔹 Admin có thể dùng /help để xem các lệnh.\n"
                "🔹 Người dùng có thể dùng /start để đăng ký."
            )
            await context.bot.send_message(
                chat_id=chat.id,
                text=welcome_msg,
                parse_mode="Markdown"
            )

            # Ghi log
            logger.info(f"Bot được thêm vào nhóm {chat.title} (ID: {chat.id}) bởi @{inviter_username} (ID: {inviter_id})")

    except Exception as e:
        logger.error(f"Lỗi trong on_my_chat_member cho nhóm {chat.id if 'chat' in locals() else 'không rõ'}: {e}")
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"😓 *DuyWin*: Lỗi xử lý cập nhật nhóm: {e}",
                    parse_mode="Markdown"
                )
            except Exception as e2:
                logger.error(f"Không thể gửi thông báo lỗi tới admin {admin_id}: {e2}")