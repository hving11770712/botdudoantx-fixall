import asyncio
import json  # Added for manual JSON handling
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

# Import monitor_csv_and_notify with try for safety (though not used since auto-run is removed)
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
    """Xem lịch sử mua model của người dùng"""
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    user = update.message.from_user
    username = user.username or f"ID_{user.id}"
    user_id = user.id
    user_id_str = str(user_id)
    
    try:
        # Manual load for buymodel.json to avoid config.py issues
        try:
            with open(BUYMODEL_FILE, 'r') as f:
                buymodel_history = json.load(f)
        except FileNotFoundError:
            buymodel_history = {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {BUYMODEL_FILE}")
            buymodel_history = {}
        
        # Kiểm tra kiểu dữ liệu
        if not isinstance(buymodel_history, dict):
            logger.error(f"buymodel_history không phải là dict: {type(buymodel_history)} - {buymodel_history}")
            await update.message.reply_text(
                f"😓 *DuyWin*: Lỗi dữ liệu lịch sử! Vui lòng liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Get lịch sử trực tiếp bằng user_id_str
        user_history = buymodel_history.get(user_id_str, [])
        if not isinstance(user_history, list):
            logger.error(f"user_history không phải là list cho {user_id_str}: {user_history}")
            user_history = []

        if not user_history:
            await update.message.reply_text(
                f"📜 *DuyWin*: Bạn chưa có lịch sử mua model nào!",
                parse_mode="Markdown"
            )
            return

        history_text = f"📜 *DuyWin*: Lịch sử mua model của bạn:\n\n"
        for entry in user_history:
            if not isinstance(entry, dict):
                logger.error(f"Entry không phải là dict: {type(entry)} - {entry}")
                continue
                
            history_text += (
                f"🔹 *Model*: {entry.get('model', 'N/A').capitalize()}\n"
                f"  - Gói: {entry.get('days', 'N/A')} ngày\n"
                f"  - Giá: {entry.get('price', 0):,} VNĐ\n"
                f"  - Mua lúc: {entry.get('purchase_time', 'N/A')}\n"
                f"  - Hết hạn: {entry.get('expiry_time', 'N/A')}\n"
                f"  - Trạng thái: {entry.get('status', 'N/A')}\n\n"
            )

        await update.message.reply_text(history_text, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Lỗi trong hàm history cho {username}: {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )

async def model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xem danh sách model và giá"""
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    try:
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
        
    except Exception as e:
        logger.error(f"Lỗi trong hàm model: {e}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )

async def buymodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mua model cho người dùng"""
    # Kiểm tra xem người dùng có bị cấm không
    if await check_ban(update, context):
        return

    try:
        # Lấy thông tin người dùng
        user = update.message.from_user
        user_id = user.id
        user_id_str = str(user_id)
        username = user.username or f"ID_{user_id}"
        is_group = update.message.chat_id < 0  # Kiểm tra xem có phải nhóm không
        
        # Sử dụng user_id làm key chính để tìm tài khoản
        account_key = user_id_str
        
        # Load dữ liệu accounts (keep db.load_json as it's for ACCOUNT_FILE)
        logger.debug(f"Loading ACCOUNT_FILE: {ACCOUNT_FILE}")
        accounts = db.load_json(ACCOUNT_FILE)
        logger.debug(f"Loaded accounts type: {type(accounts)}")
        
        # Manual load for buymodel.json to avoid config.py issues
        logger.debug(f"Loading BUYMODEL_FILE: {BUYMODEL_FILE}")
        try:
            with open(BUYMODEL_FILE, 'r') as f:
                buymodel_history = json.load(f)
        except FileNotFoundError:
            buymodel_history = {}
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {BUYMODEL_FILE}")
            buymodel_history = {}
        logger.debug(f"Loaded buymodel_history type: {type(buymodel_history)}")
        
        # Kiểm tra kiểu dữ liệu accounts
        if not isinstance(accounts, dict):
            logger.error(f"accounts không phải là dict: {type(accounts)} - {accounts}")
            await update.message.reply_text(
                f"😓 *DuyWin*: Lỗi dữ liệu tài khoản! Vui lòng liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return
        
        # Kiểm tra kiểu dữ liệu buymodel_history
        if not isinstance(buymodel_history, dict):
            logger.error(f"buymodel_history không phải là dict: {type(buymodel_history)} - {buymodel_history}")
            buymodel_history = {}

        # Kiểm tra tham số
        if len(context.args) != 2:
            await update.message.reply_text(
                f"📢 *DuyWin*: Vui lòng nhập đúng cú pháp: /buymodel <model> <số ngày>\nVí dụ: /buymodel basic 7",
                parse_mode="Markdown"
            )
            return

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
        model_prices = MODEL_PRICES_WITH_DAYS_buymodel.get(model, [])
        if not isinstance(model_prices, list):
            logger.error(f"MODEL_PRICES_WITH_DAYS_buymodel['{model}'] is not a list: {model_prices}")
            await update.message.reply_text(
                f"😓 *DuyWin*: Lỗi cấu hình hệ thống! Vui lòng liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Tìm giá dựa trên số ngày
        price = None
        for d, p in model_prices:
            if d == days:
                price = p
                break

        # Kiểm tra số ngày hợp lệ
        if price is None:
            valid_days = [str(d) for d, p in model_prices]
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Số ngày không hợp lệ cho model {model}! Chỉ hỗ trợ: {', '.join(valid_days)} ngày",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra tài khoản tồn tại
        if account_key not in accounts:
            await update.message.reply_text(
                f"⚠️ *DuyWin*: Tài khoản chưa được khởi tạo. Vui lòng dùng /start trước! 🚀",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra cấu trúc tài khoản
        if not isinstance(accounts[account_key], dict):
            logger.error(f"accounts['{account_key}'] không phải là dict: {type(accounts[account_key])} - {accounts[account_key]}")
            await update.message.reply_text(
                f"😓 *DuyWin*: Lỗi dữ liệu tài khoản! Vui lòng liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return

        # Kiểm tra số dư
        if "balance" not in accounts[account_key]:
            logger.error(f"accounts['{account_key}'] thiếu trường 'balance': {accounts[account_key]}")
            await update.message.reply_text(
                f"😓 *DuyWin*: Lỗi dữ liệu tài khoản! Vui lòng liên hệ hỗ trợ: {SUPPORT_LINK}",
                parse_mode="Markdown"
            )
            return
            
        balance = accounts[account_key]["balance"]
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
        
        # Đảm bảo các trường cần thiết tồn tại
        if "model" not in accounts[account_key]:
            accounts[account_key]["model"] = []
        if "model_expiry" not in accounts[account_key]:
            accounts[account_key]["model_expiry"] = {}

        # Tính toán thời gian hết hạn
        current_time = datetime.now()
        
        # Kiểm tra an toàn cho model_expiry
        model_expiry = accounts[account_key].get("model_expiry", {})
        if not isinstance(model_expiry, dict):
            logger.error(f"model_expiry không phải là dict cho {account_key}: {type(model_expiry)} - {model_expiry}")
            model_expiry = {}
            accounts[account_key]["model_expiry"] = model_expiry
        
        if model in accounts[account_key].get("model", []) and model_expiry.get(model):
            # Nếu model còn hạn, cộng thêm thời gian
            try:
                current_expiry_str = model_expiry[model]
                if not isinstance(current_expiry_str, str):
                    logger.error(f"Thời hạn không phải là string cho model {model} của {username}: {type(current_expiry_str)} - {current_expiry_str}")
                    current_expiry_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
                
                current_expiry = datetime.strptime(current_expiry_str, "%Y-%m-%d %H:%M:%S")
                if current_expiry > current_time:
                    # Cộng thêm số ngày vào thời gian hiện tại của hạn sử dụng
                    expiry_time = (current_expiry + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # Nếu đã hết hạn, tính từ hiện tại
                    expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError as e:
                logger.error(f"Thời hạn không hợp lệ cho model {model} của {username}: {model_expiry.get(model)} - {e}")
                expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            # Nếu chưa có model hoặc không còn hạn, tính từ hiện tại
            expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        # Cập nhật tài khoản
        accounts[account_key]["balance"] -= price
        if model not in accounts[account_key].get("model", []):
            accounts[account_key]["model"] = accounts[account_key].get("model", []) + [model]
        
        # Đảm bảo model_expiry là dict trước khi cập nhật
        if "model_expiry" not in accounts[account_key]:
            accounts[account_key]["model_expiry"] = {}
        elif not isinstance(accounts[account_key]["model_expiry"], dict):
            logger.error(f"model_expiry không phải là dict khi cập nhật cho {account_key}: {type(accounts[account_key]['model_expiry'])} - {accounts[account_key]['model_expiry']}")
            accounts[account_key]["model_expiry"] = {}
        
        accounts[account_key]["model_expiry"][model] = expiry_time
        db.save_json(ACCOUNT_FILE, accounts)

        # Ghi lịch sử mua vào buymodel.json với key = user_id_str
        if user_id_str not in buymodel_history:
            buymodel_history[user_id_str] = []
        
        # Đảm bảo buymodel_history[user_id_str] là list
        if not isinstance(buymodel_history[user_id_str], list):
            logger.error(f"buymodel_history['{user_id_str}'] không phải là list: {buymodel_history[user_id_str]}")
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
        
        # Manual save for buymodel.json
        with open(BUYMODEL_FILE, 'w') as f:
            json.dump(buymodel_history, f, indent=4, ensure_ascii=False)

        # Cập nhật model_users
        remove_from_old_model(user_id)
        
        # Đảm bảo model_users được khởi tạo đúng cách
        from lenh.config import ensure_model_users_initialized
        ensure_model_users_initialized()
        
        # Đảm bảo model_users[model] tồn tại và là set
        if model not in model_users:
            model_users[model] = set()
        if not isinstance(model_users[model], set):
            model_users[model] = set()
            
        model_users[model].add(user_id)
        logger.info(f"Đã thêm user_id {user_id} vào model_users['{model}'] sau khi mua. Hiện tại: {model_users[model]}")

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
        import traceback
        logger.error(f"Lỗi khi xử lý lệnh /buymodel cho @{username} (ID: {user_id}): {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text(
            f"😓 *DuyWin*: Đã có lỗi xảy ra! Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {SUPPORT_LINK}",
            parse_mode="Markdown"
        )
