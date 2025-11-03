import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
# Import monitor_csv_and_notify chỉ khi cần
try:
    from lenh.monitor_csv_and_notify import monitor_csv_and_notify
except ImportError:
    monitor_csv_and_notify = None
from lenh.config import (
    ACCOUNT_FILE, MODEL_PRICES_WITH_DAYS_buymodel, running_tasks, model_users,
    remove_from_old_model, check_ban, db, logger, SUPPORT_LINK
)

# Đường dẫn tới file lưu lịch sử mua
BUYMODEL_FILE = "data/buymodel.json"

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    user = update.message.from_user
    user_id = user.id
    user_id_str = str(user_id)
    buymodel_history = db.load_json(BUYMODEL_FILE, default={})

    if user_id_str not in buymodel_history or not buymodel_history[user_id_str]:
        await update.message.reply_text(
            f"📜 *DuyWin*: Bạn chưa có lịch sử mua model nào!",
            parse_mode="Markdown"
        )
        return

    history_text = f"📜 *DuyWin*: Lịch sử mua model của bạn:\n\n"
    for entry in buymodel_history[user_id_str]:
        history_text += (
            f"🔹 *Model*: {entry['model'].capitalize()}\n"
            f"  - Gói: {entry['days']} ngày\n"
            f"  - Giá: {entry['price']:,} VNĐ\n"
            f"  - Mua lúc: {entry['purchase_time']}\n"
            f"  - Hết hạn: {entry['expiry_time']}\n"
            f"  - Trạng thái: {entry['status']}\n\n"
        )

    await update.message.reply_text(history_text, parse_mode="Markdown")

async def model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Tạo danh sách model với giá theo ngày
    model_list = ""
    for model, prices in MODEL_PRICES_WITH_DAYS_buymodel.items():
        if isinstance(prices, list) and prices:
            model_list += f"🔹 *{model.capitalize()}*:\n"
            for days, price in prices:
                model_list += f"  - {days} ngày: {price:,} VNĐ\n"
        else:
            model_list += f"🔹 *{model.capitalize()}*: Chưa bán\n"

    await update.message.reply_text(
        f"📋 *DuyWin*: Danh sách model và giá:\n\n{model_list}\n\n💡 Dùng /buymodel <model> <số ngày> để mua (7 hoặc 30 ngày).",
        parse_mode="Markdown"
    )

async def buymodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    # Lấy thông tin người dùng
    user = update.message.from_user
    user_id = user.id
    user_id_str = str(user_id)  # Sử dụng user_id dạng string làm key chính
    username = user.username or f"ID_{user_id}"
    chat_id = update.message.chat_id
    is_group = chat_id < 0  # Kiểm tra xem có phải nhóm không
    accounts = db.load_json(ACCOUNT_FILE)
    buymodel_history = db.load_json(BUYMODEL_FILE, default={})

    # Kiểm tra tham số
    if len(context.args) != 2:
        await update.message.reply_text(
            f"📢 *DuyWin*: Vui lòng nhập đúng cú pháp: /buymodel <model> <số ngày>\nVí dụ: /buymodel basic 7",
            parse_mode="Markdown"
        )
        return

    try:
        model = context.args[0].lower()
        days = int(context.args[1])

        # Kiểm tra model hợp lệ
        if model not in MODEL_PRICES_WITH_DAYS_buymodel:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Model không hợp lệ! Vui lòng chọn: {', '.join(MODEL_PRICES_WITH_DAYS_buymodel.keys())}",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra model vip
        if model == "vip":
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Model *VIP* chưa được bán!",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra cấu trúc của MODEL_PRICES_WITH_DAYS_buymodel[model]
        if not isinstance(MODEL_PRICES_WITH_DAYS_buymodel[model], list):
            logger.error(f"MODEL_PRICES_WITH_DAYS_buymodel['{model}'] is not a list: {MODEL_PRICES_WITH_DAYS_buymodel[model]}")
            await update.message.reply_text(
                f"😓 *DuyWin*: Lỗi cấu hình hệ thống! Vui lòng liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Tìm giá dựa trên số ngày
        price = None
        for d, p in MODEL_PRICES_WITH_DAYS_buymodel[model]:
            if d == days:
                price = p
                break

        # Kiểm tra số ngày hợp lệ
        if price is None:
            valid_days = [str(d) for d, p in MODEL_PRICES_WITH_DAYS_buymodel[model]]
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Số ngày không hợp lệ cho model {model}! Chỉ hỗ trợ: {', '.join(valid_days)} ngày",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra tài khoản tồn tại (tìm bằng user_id)
        account_key = None
        for key, info in accounts.items():
            if info.get("user_id") == user_id:
                account_key = key
                break
        
        if account_key is None:
            # Nếu không tìm thấy bằng user_id, thử tìm bằng user_id_str
            if user_id_str in accounts:
                account_key = user_id_str
            else:
                await update.message.reply_text(
                    f"⚠️ *DuyWin*: Tài khoản chưa được khởi tạo. Vui lòng dùng /start trước! 🚀",
                    parse_mode="Markdown"
                )
                return

        # Đảm bảo user_id và chat_id được cập nhật
        accounts[account_key]["user_id"] = user_id
        accounts[account_key]["chat_id"] = chat_id

        # Kiểm tra số dư
        balance = accounts[account_key].get("balance", 0)
        if balance < price:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Số dư không đủ ({balance:,} VNĐ) để mua model {model} ({days} ngày, {price:,} VNĐ)!",
                parse_mode="Markdown"
            )
            return

        # Chuyển đổi cấu trúc cũ nếu cần
        if isinstance(accounts[account_key].get("model"), str):
            old_model = accounts[account_key].get("model", "none")
            old_expiry = accounts[account_key].get("model_expiry")
            accounts[account_key]["model"] = [old_model] if old_model != "none" else []
            accounts[account_key]["model_expiry"] = {old_model: old_expiry} if old_model != "none" and old_expiry else {}

        # Tính toán thời gian hết hạn
        current_time = datetime.now()
        if model in accounts[account_key].get("model", []) and accounts[account_key].get("model_expiry", {}).get(model):
            # Nếu model còn hạn, cộng thêm thời gian
            try:
                current_expiry = datetime.strptime(accounts[account_key]["model_expiry"][model], "%Y-%m-%d %H:%M:%S")
                if current_expiry > current_time:
                    # Cộng thêm số ngày vào thời gian hiện tại của hạn sử dụng
                    expiry_time = (current_expiry + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # Nếu đã hết hạn, tính từ hiện tại
                    expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho model {model} của {username}: {accounts[account_key].get('model_expiry', {}).get(model)}")
                expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Nếu chưa có model hoặc không còn hạn, tính từ hiện tại
            expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        # Cập nhật tài khoản
        accounts[account_key]["balance"] -= price
        if model not in accounts[account_key].get("model", []):
            accounts[account_key]["model"] = accounts[account_key].get("model", []) + [model]
        if "model_expiry" not in accounts[account_key]:
            accounts[account_key]["model_expiry"] = {}
        accounts[account_key]["model_expiry"][model] = expiry_time
        db.save_json(ACCOUNT_FILE, accounts)

        # Ghi lịch sử mua vào buymodel.json (dùng user_id_str làm key)
        if user_id_str not in buymodel_history:
            buymodel_history[user_id_str] = []
        buymodel_history[user_id_str].append({
            "user_id": user_id,
            "model": model,
            "days": days,
            "price": price,
            "purchase_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_time": expiry_time,
            "status": "success"
        })
        db.save_json(BUYMODEL_FILE, buymodel_history)

        # Cập nhật model_users (dùng chat_id)
        remove_from_old_model(chat_id, current_model=model)
        model_users.setdefault(model, set()).add(chat_id)
        logger.info(f"Đã thêm chat_id {chat_id} vào model_users['{model}'] sau khi mua. Hiện tại: {model_users[model]}")

        # Khởi động task nếu cần
        if model not in running_tasks or (model in running_tasks and running_tasks[model].done()):
            if model == "basic":
                # Model basic dùng API
                try:
                    from game.sunwin.modelbasic import monitor_api_basic
                    if model in running_tasks and not running_tasks[model].done():
                        running_tasks[model].cancel()
                        logger.info(f"Đã hủy task cũ cho model {model}")
                    running_tasks[model] = asyncio.create_task(monitor_api_basic(context.bot, model))
                    logger.info(f"Đã khởi động task API cho model {model}")
                except ImportError:
                    logger.error(f"Không thể import monitor_api_basic cho model {model}")
            elif monitor_csv_and_notify:
                if model in running_tasks and not running_tasks[model].done():
                    running_tasks[model].cancel()
                    logger.info(f"Đã hủy task cũ cho model {model}")
                running_tasks[model] = asyncio.create_task(monitor_csv_and_notify(context.bot, model))
                logger.info(f"Đã khởi động task cho model {model}")
            else:
                logger.warning(f"monitor_csv_and_notify không khả dụng cho model {model}")

        # Thông báo thành công
        await update.message.reply_text(
            f"✅ *DuyWin*: Bạn đã mua model *{model.capitalize()}* ({days} ngày) thành công! {'(Nhóm)' if is_group else ''}\n"
            f"⏰ Hết hạn: {expiry_time}\n"
            f"💰 Số dư còn: {accounts[account_key]['balance']:,} VNĐ",
            parse_mode="Markdown"
        )

        # Ghi log
        logger.info(f"@{username} (ID: {user_id}) đã mua model {model} ({days} ngày, giá: {price:,} VNĐ, hết hạn: {expiry_time}, số dư còn: {accounts[account_key]['balance']:,} VNĐ)")

    except ValueError:
        await update.message.reply_text(
            f"⚠️ *DuyWin*: Số ngày phải là số nguyên (7 hoặc 30)!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Lỗi khi xử lý lệnh /buymodel cho @{username} (ID: {user_id}): {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )