import asyncio
from telegram import Update
from telegram.ext import ContextTypes
# Import monitor_csv_and_notify chỉ khi cần
try:
    from lenh.monitor_csv_and_notify import monitor_csv_and_notify
except ImportError:
    monitor_csv_and_notify = None
from lenh.config import db, remove_from_old_model, logger, ACCOUNT_FILE, MODEL_PRICES, MODEL_PRICES_WITH_DAYS, model_users, running_tasks, SUPPORT_LINK, is_banned
from datetime import datetime

async def model789club_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /model789club"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or str(user_id)

    try:
        # Kiểm tra nếu người dùng bị cấm
        if is_banned(user_id):
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Tải danh sách tài khoản
        accounts = db.load_json(ACCOUNT_FILE)

        # Tìm thông tin tài khoản
        user_info = next((info for u, info in accounts.items() if info.get("user_id") == user_id or info.get("chat_id") == user_id), None)
        if not user_info:
            await update.message.reply_text(
                f"❌ *DuyWin*: Tài khoản của bạn chưa được đăng ký! Hãy sử dụng /start để đăng ký.",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra quyền truy cập model "789club"
        if "789club" not in user_info.get("model", []):
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn cần mua Model 789club bằng /buymodel 789club hoặc sử dụng key! Giá: {MODEL_PRICES['789club']} VNĐ (hoặc {MODEL_PRICES_WITH_DAYS['789club'][7]} VNĐ/7 ngày, {MODEL_PRICES_WITH_DAYS['789club'][30]} VNĐ/30 ngày).",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra thời hạn model
        expiry = user_info.get("model_expiry", {}).get("789club")
        now = datetime.now()
        if expiry:
            try:
                if datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S") < now:
                    await update.message.reply_text(
                        f"❌ *DuyWin*: Model 789club của bạn đã hết hạn! Mua lại bằng /buymodel 789club.",
                        parse_mode="Markdown"
                    )
                    return
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho model 789club của {username}: {expiry}")
                await update.message.reply_text(
                    f"❌ *DuyWin*: Lỗi dữ liệu thời hạn model. Liên hệ hỗ trợ: {SUPPORT_LINK}",
                    parse_mode="Markdown"
                )
                return

        # Xóa user_id khỏi model cũ (nếu có)
        remove_from_old_model(user_id)

        # Thêm user_id vào danh sách người dùng model "789club"
        model_users.setdefault("789club", set()).add(user_id)
        logger.info(f"Đã thêm user_id {user_id} vào model_users['789club']. Hiện tại: {model_users['789club']}")

        # Khởi động task giám sát nếu chưa có
        if "789club" not in running_tasks:
            if monitor_csv_and_notify:
                running_tasks["789club"] = asyncio.create_task(monitor_csv_and_notify(context.bot, "789club"))
                logger.info(f"Đã khởi động task cho model 789club")
            else:
                logger.warning(f"monitor_csv_and_notify không khả dụng cho model 789club")

        # Gửi thông báo thành công
        await update.message.reply_text(
            f"✅ *DuyWin*: Bạn đã tham gia Model 789club! Bạn sẽ nhận được dự đoán từ bot.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Lỗi trong hàm model789club_command cho user_id {user_id}: {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi khởi động Model 789club. Vui lòng thử lại sau.",
            parse_mode="Markdown"
        )