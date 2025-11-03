from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import load_json, logger, model_users, model_predictions, running_tasks, last_processed_phien, ADMIN_IDS, ACCOUNT_FILE, BANID_FILE, check_ban

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Lấy thông tin người dùng
    user = update.message.from_user
    user_id = user.id
    username = user.username or f"ID_{user_id}"

    # Kiểm tra quyền admin
    if user_id not in ADMIN_IDS:
        await update.message.reply_text(
            "🚫 DuyWin: Chỉ admin mới có quyền sử dụng lệnh này!"
        )
        return

    try:
        # Load dữ liệu tài khoản và danh sách ban
        accounts = load_json(ACCOUNT_FILE)
        banned_users = load_json(BANID_FILE)

        # Xây dựng thông báo trạng thái
        status_msg = f"📊 DuyWin: Trạng thái Quản trị Bot - @{username}\n\n"

        # Phần 1: Tổng quan hệ thống và trạng thái model
        status_msg += "🌐 Tổng quan hệ thống:\n"
        status_msg += f"📅 Phiên cuối cùng: {last_processed_phien}\n"
        status_msg += f"👥 Tổng số người dùng đăng ký: {len(accounts)}\n"
        status_msg += f"👤 Tổng số người dùng đang hoạt động: {sum(len(users) for users in model_users.values())}\n"
        status_msg += f"🚫 Số người dùng bị cấm: {len(banned_users)}\n\n"

        status_msg += "🤖 Trạng thái các Model:\n"
        blocked_users = set()

        for model in model_users.keys():  # Chỉ lặp qua basic, vip, md5hit, 789club
            active_users_count = len(model_users.get(model, set()))
            # Đếm số người dùng đăng ký model, xử lý cấu trúc mới (model là list)
            registered_users_count = sum(1 for u in accounts.values() if model in u.get("model", []))
            is_running = model in running_tasks
            next_prediction = str(model_predictions.get(model, {}).get("result", "Chưa có"))
            # Sửa lỗi: Chuyển đổi maPhien thành int, xử lý key MaPhien cho md5hit
            next_phien_raw = model_predictions.get(model, {}).get("maPhien") or model_predictions.get(model, {}).get("MaPhien", 0)
            try:
                next_phien = int(next_phien_raw) if next_phien_raw is not None else 0
            except (ValueError, TypeError):
                next_phien = 0
                logger.warning(f"maPhien không hợp lệ cho model {model}: {next_phien_raw}")

            status_msg += (
                f"- {model.capitalize()}: "
                f"{'✅' if is_running else '❌'} "
                f"({active_users_count}/{registered_users_count} người dùng hoạt động/đăng ký)\n"
            )
            if is_running and next_phien > last_processed_phien:
                status_msg += f"  Dự đoán phiên {next_phien}: {next_prediction}\n"

            # Kiểm tra người dùng chặn bot
            if is_running:
                model_chat_ids = model_users.get(model, set()).copy()
                for cid in model_chat_ids:
                    try:
                        await context.bot.send_chat_action(chat_id=cid, action="typing")
                    except Exception as e:
                        if "Forbidden" in str(e):
                            blocked_users.add(cid)
                            user_info = next((u for u, v in accounts.items() if v.get("chat_id") == cid), "Không xác định")
                            status_msg += f"  ⚠️ @{user_info} (chat_id: {cid}) đã chặn bot trong model {model}\n"
                            model_users[model].discard(cid)
                            for admin_id in ADMIN_IDS:
                                await context.bot.send_message(
                                    chat_id=admin_id,
                                    text=f"⚠️ DuyWin: Người dùng @{user_info} (chat_id: {cid}) đã chặn bot trong model {model}"
                                )

        # Danh sách người dùng đang hoạt động
        status_msg += "\n👤 Danh sách người dùng đang hoạt động:\n"
        active_users = []
        for model, users in model_users.items():
            for cid in users:
                user_info = next((u for u, v in accounts.items() if v.get("chat_id") == cid), "Không xác định")
                active_users.append(f"@{user_info} ({model})")

        # Log nội dung active_users để debug
        logger.info(f"active_users trước khi nối: {active_users}")

        if active_users:
            status_msg += "\n".join(active_users)
        else:
            status_msg += "Không có người dùng nào đang hoạt động"

        # Phần 2: Trạng thái người dùng bị cấm
        status_msg += "\n\n🚫 Trạng thái người dùng bị cấm:\n"
        status_msg += f"Tổng số người dùng bị cấm: {len(banned_users)}\n"

        if not banned_users:
            status_msg += "Không có người dùng nào bị cấm."
        else:
            unreachable_users = []
            for banned_username in banned_users.keys():
                chat_id = accounts.get(banned_username, {}).get("chat_id", None)
                status_line = f"- @{banned_username}"
                if chat_id:
                    try:
                        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                        status_line += " ✅ (Bot vẫn liên lạc được)"
                    except Exception as e:
                        if "Forbidden" in str(e):
                            status_line += " ❌ (Bot bị chặn hoặc không phản hồi được)"
                            unreachable_users.append(banned_username)
                        else:
                            status_line += f" ⚠️ (Lỗi: {str(e)})"
                else:
                    status_line += " ❓ (Không có chat_id)"
                status_msg += status_line + "\n"

            if unreachable_users:
                status_msg += f"\n⚠️ Tổng số người dùng bị cấm mà bot không phản hồi được: {len(unreachable_users)}\n"
                status_msg += "Danh sách: " + ", ".join([f"@{u}" for u in unreachable_users])

        # Tổng kết người dùng chặn bot
        if blocked_users:
            blocked_usernames = []
            for cid in blocked_users:
                username = next((u for u, v in accounts.items() if v.get("chat_id") == cid), "Không xác định")
                blocked_usernames.append(f"@{username}")
            status_msg += f"\n\n⚠️ Tổng số người dùng đang dùng model đã chặn bot: {len(blocked_users)}\n"
            status_msg += f"Danh sách: {', '.join(blocked_usernames)}"

        # Log nội dung status_msg để debug
        logger.info(f"Nội dung status_msg trước khi gửi: {status_msg}")

        # Gửi thông báo trạng thái
        await update.message.reply_text(status_msg)

        # Ghi log hành động
        logger.info(f"Admin @{username} (user_id: {user_id}) đã kiểm tra trạng thái bot")

    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /status cho @{username} (user_id: {user_id}): {str(e)}")
        await update.message.reply_text(
            f"😓 DuyWin: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ! 😞"
        )