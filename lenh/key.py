from datetime import datetime, timedelta
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from lenh.config import (
    check_ban, clean_expired_keys, db, remove_from_old_model, model_users, logger,
    running_tasks, ACCOUNT_FILE, KEY_FILE, KEY_CTV_FILE, MODEL_PRICES_WITH_DAYS, SUPPORT_LINK, 
    ADMIN_IDS, escape_markdown_safev2, validate_markdown_v2, update_username, backup_data
)
# Import monitor_csv_and_notify chỉ khi cần (không dùng cho model basic)
try:
    from lenh.monitor_csv_and_notify import monitor_csv_and_notify
except ImportError:
    monitor_csv_and_notify = None

async def key_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /key để người dùng nhập mã key (từ cả key.json và keyctv.json)."""
    if not update.message or not update.message.from_user:
        logger.warning("Update không chứa message hoặc from_user trong lệnh /key")
        return

    user = update.message.from_user
    user_id = user.id
    user_id_str = str(user_id)  # Sử dụng user_id dạng chuỗi làm khóa chính
    chat_id = update.message.chat_id
    raw_username = user.username.lstrip('@') if user.username else f"ID_{user_id}"

    try:
        # Kiểm tra nếu người dùng bị cấm
        if await check_ban(update, context):
            logger.warning(f"User_id {user_id} (@{raw_username}) bị cấm, không thể sử dụng /key")
            return

        # Kiểm tra tham số đầu vào
        if not context.args:
            logger.warning(f"User_id {user_id} (@{raw_username}) không cung cấp mã key")
            error_message = f"❌ *DuyWin*: Vui lòng nhập mã key: `/key <mã key>`"
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Vui lòng nhập mã key: /key <mã key>"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        key_code = context.args[0]

        # --- Tải dữ liệu key từ cả 2 file ---
        keys_main = clean_expired_keys()            # key.json
        keys_ctv = db.load_json(KEY_CTV_FILE)       # keyctv.json

        key_info = None
        keys = None
        key_file = None

        if key_code in keys_main:
            key_info = keys_main[key_code]
            keys = keys_main
            key_file = KEY_FILE
        elif key_code in keys_ctv:
            key_info = keys_ctv[key_code]
            keys = keys_ctv
            key_file = KEY_CTV_FILE
        else:
            logger.warning(f"Mã key {key_code} không hợp lệ từ user_id {user_id}")
            error_message = f"❌ *DuyWin*: Mã key `{escape_markdown_safev2(key_code)}` không hợp lệ\\!"
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Mã key {key_code} không hợp lệ!"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Load tài khoản
        accounts = db.load_json(ACCOUNT_FILE)

        # Kiểm tra tài khoản với user_id
        if user_id_str not in accounts:
            logger.warning(f"Tài khoản user_id: {user_id} (@{raw_username}) chưa đăng ký")
            error_message = f"❌ *DuyWin*: Tài khoản của bạn chưa được đăng ký\\! Hãy sử dụng /start để đăng ký\\."
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Tài khoản của bạn chưa được đăng ký! Hãy sử dụng /start để đăng ký."
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra chat_id có khớp không
        if accounts[user_id_str].get("chat_id") and accounts[user_id_str]["chat_id"] != chat_id:
            logger.warning(f"Chat_id {chat_id} không khớp với chat_id đã đăng ký {accounts[user_id_str]['chat_id']} cho user_id {user_id}")
            error_message = (
                f"❌ *DuyWin*: Bạn chỉ có thể sử dụng lệnh này từ chat đã đăng ký\\. "
                f"Liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
            )
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Bạn chỉ có thể sử dụng lệnh này từ chat đã đăng ký. Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Cập nhật username
        update_username(accounts, user_id_str, raw_username, user_id)

        model = key_info.get("model")

        # Kiểm tra model hợp lệ
        if not model or model not in MODEL_PRICES_WITH_DAYS:
            logger.warning(f"Model không hợp lệ trong key {key_code}: {model} từ user_id {user_id}")
            error_message = (
                f"❌ *DuyWin*: Model trong key không hợp lệ\\! "
                f"Liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
            )
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Model trong key không hợp lệ! Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra thời hạn và tính số ngày
        expiry_str = key_info.get("expiry")
        days = key_info.get("days")
        current_time = datetime.now()

        if days is None and expiry_str:
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                if current_time > expiry:
                    logger.warning(f"Mã key {key_code} đã hết hạn, từ user_id {user_id}")
                    error_message = (
                        f"❌ *DuyWin*: Mã key `{escape_markdown_safev2(key_code)}` đã hết hạn vào `{escape_markdown_safev2(expiry_str)}`\\!"
                    )
                    parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
                    if not parse_mode:
                        error_message = f"❌ DuyWin: Mã key {key_code} đã hết hạn vào {expiry_str}!"
                    await update.message.reply_text(error_message, parse_mode=parse_mode)
                    del keys[key_code]
                    db.save_json(key_file, keys)
                    return
                days = max(1, (expiry - current_time).days)
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho mã key {key_code}: {expiry_str}")
                error_message = (
                    f"❌ *DuyWin*: Lỗi dữ liệu thời hạn mã key\\. "
                    f"Liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
                )
                parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
                if not parse_mode:
                    error_message = f"❌ DuyWin: Lỗi dữ liệu thời hạn mã key. Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
                await update.message.reply_text(error_message, parse_mode=parse_mode)
                return
        elif not isinstance(days, (int, float)) or days <= 0:
            logger.warning(f"Số ngày không hợp lệ trong key {key_code}: {days} từ user_id {user_id}")
            error_message = (
                f"❌ *DuyWin*: Số ngày trong key không hợp lệ\\! "
                f"Liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
            )
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Số ngày trong key không hợp lệ! Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra số lần sử dụng
        if key_info.get("uses", 0) <= 0:
            logger.warning(f"Mã key {key_code} đã hết lượt sử dụng, từ user_id {user_id}")
            error_message = f"❌ *DuyWin*: Mã key `{escape_markdown_safev2(key_code)}` đã hết lượt sử dụng\\!"
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Mã key {key_code} đã hết lượt sử dụng!"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Kiểm tra key đã được người dùng sử dụng chưa
        if "used_keys" not in accounts[user_id_str] or not isinstance(accounts[user_id_str]["used_keys"], list):
            accounts[user_id_str]["used_keys"] = []
            logger.info(f"Khởi tạo danh sách used_keys cho user_id {user_id_str}")
        if key_code in accounts[user_id_str]["used_keys"]:
            logger.warning(f"User_id {user_id} (@{raw_username}) đã sử dụng mã key {key_code} trước đó")
            error_message = f"❌ *DuyWin*: Bạn đã sử dụng mã key `{escape_markdown_safev2(key_code)}` trước đó\\!"
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = f"❌ DuyWin: Bạn đã sử dụng mã key {key_code} trước đó!"
            await update.message.reply_text(error_message, parse_mode=parse_mode)
            return

        # Đảm bảo used_by là danh sách
        if "used_by" not in key_info or not isinstance(key_info["used_by"], list):
            key_info["used_by"] = []
            logger.info(f"Khởi tạo danh sách used_by cho mã key {key_code}")

        # Sao lưu dữ liệu
        backup_data()

        # Cập nhật thời hạn model
        if "model" not in accounts[user_id_str] or not isinstance(accounts[user_id_str]["model"], list):
            accounts[user_id_str]["model"] = []
            logger.info(f"Khởi tạo danh sách model cho user_id {user_id_str}")
        if "model_expiry" not in accounts[user_id_str] or not isinstance(accounts[user_id_str]["model_expiry"], dict):
            accounts[user_id_str]["model_expiry"] = {}
            logger.info(f"Khởi tạo từ điển model_expiry cho user_id {user_id_str}")

        new_expiry = current_time + timedelta(days=days)
        if model in accounts[user_id_str]["model_expiry"]:
            try:
                current_expiry = datetime.strptime(accounts[user_id_str]["model_expiry"][model], "%Y-%m-%d %H:%M:%S")
                if current_expiry > current_time:
                    new_expiry = current_expiry + timedelta(days=days)
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho model {model} của user_id {user_id_str}: {accounts[user_id_str]['model_expiry'][model]}")

        accounts[user_id_str]["model_expiry"][model] = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
        if model not in accounts[user_id_str]["model"]:
            accounts[user_id_str]["model"].append(model)
        accounts[user_id_str]["chat_id"] = chat_id
        accounts[user_id_str]["used_keys"].append(key_code)
        key_info["used_by"].append(user_id_str)
        key_info["uses"] -= 1

        # Xóa key nếu hết lượt sử dụng
        if key_info["uses"] <= 0:
            del keys[key_code]
            logger.info(f"Mã key {key_code} đã hết lượt sử dụng và được xóa")

        # Lưu dữ liệu
        db.save_json(ACCOUNT_FILE, accounts)
        db.save_json(key_file, keys)
        logger.info(f"User_id {user_id} (@{raw_username}) đã sử dụng mã key {key_code} cho model {model}, còn {key_info['uses']} lượt, thời hạn mới: {new_expiry}")

        # Gửi thông báo cho người dùng
        expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")
        user_message = (
            f"✅ *DuyWin*: Mã key `{escape_markdown_safev2(key_code)}` hợp lệ\\! \n"
            f"Bạn đã được cấp quyền sử dụng model `{escape_markdown_safev2(model)}` đến `{escape_markdown_safev2(expiry_str)}`\\."
        )
        if key_info["uses"] == 0:
            user_message += "\nKey này đã hết lượt sử dụng\\!"
        parse_mode = "MarkdownV2" if validate_markdown_v2(user_message) else None
        if not parse_mode:
            user_message = (
                f"✅ DuyWin: Mã key {key_code} hợp lệ! \n"
                f"Bạn đã được cấp quyền sử dụng model {model} đến {expiry_str}."
            )
            if key_info["uses"] == 0:
                user_message += "\nKey này đã hết lượt sử dụng!"
        await update.message.reply_text(user_message, parse_mode=parse_mode)

        # Thông báo cho admin
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        admin_message = (
            f"📩 *DuyWin*: Người dùng @{escape_markdown_safev2(raw_username)} \\(ID: {escape_markdown_safev2(user_id_str)}\\) "
            f"đã sử dụng mã key `{escape_markdown_safev2(key_code)}`\\.\n"
            f"\\- *Model*: {escape_markdown_safev2(model)}\n"
            f"\\- *Hạn sử dụng*: {escape_markdown_safev2(expiry_str)}\n"
            f"\\- *Thời gian*: {escape_markdown_safev2(current_time_str)}\n"
            f"\\- *Lượt còn lại*: {key_info['uses']}"
        )
        parse_mode_admin = "MarkdownV2" if validate_markdown_v2(admin_message) else None
        if not parse_mode_admin:
            admin_message = (
                f"📩 DuyWin: Người dùng @{raw_username} (ID: {user_id_str}) "
                f"đã sử dụng mã key {key_code}.\n"
                f"- Model: {model}\n"
                f"- Hạn sử dụng: {expiry_str}\n"
                f"- Thời gian: {current_time_str}\n"
                f"- Lượt còn lại: {key_info['uses']}"
            )

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode=parse_mode_admin
                )
                logger.info(f"Đã gửi thông báo cho admin {admin_id}")
            except Exception as e:
                logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
                safe_fallback_message = (
                    f"📩 DuyWin: Người dùng @{raw_username} (ID: {user_id_str}) "
                    f"đã sử dụng mã key {key_code}.\n"
                    f"- Model: {model}\n"
                    f"- Hạn sử dụng: {expiry_str}\n"
                    f"- Thời gian: {current_time_str}\n"
                    f"- Lượt còn lại: {key_info['uses']}"
                )
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=safe_fallback_message
                    )
                    logger.info(f"Đã gửi thông báo fallback cho admin {admin_id}")
                except Exception as e2:
                    logger.error(f"Lỗi khi gửi thông báo fallback admin {admin_id}: {str(e2)}")

        # Cập nhật model_users
        try:
            remove_from_old_model(chat_id)
            model_users.setdefault(model, set()).add(chat_id)
            logger.info(f"Đã thêm chat_id {chat_id} vào model_users['{model}']. Hiện tại: {model_users[model]}")
            
            # Model "basic" được xử lý bởi modelbasic.py với API, không dùng monitor_csv_and_notify
            if model == "basic":
                # Import monitor_api_basic từ modelbasic.py
                try:
                    from game.sunwin.modelbasic import monitor_api_basic
                    if model not in running_tasks or (model in running_tasks and running_tasks[model].done()):
                        if model in running_tasks and not running_tasks[model].done():
                            running_tasks[model].cancel()
                            logger.info(f"Đã hủy task cũ cho model {model}")
                        running_tasks[model] = asyncio.create_task(monitor_api_basic(context.bot, model))
                        logger.info(f"Đã khởi động task API cho model {model}")
                except ImportError:
                    logger.error(f"Không thể import monitor_api_basic cho model {model}")
            else:
                # Các model khác dùng monitor_csv_and_notify (nếu có)
                if monitor_csv_and_notify:
                    if model not in running_tasks or (model in running_tasks and running_tasks[model].done()):
                        if model in running_tasks and not running_tasks[model].done():
                            running_tasks[model].cancel()
                            logger.info(f"Đã hủy task cũ cho model {model}")
                        running_tasks[model] = asyncio.create_task(monitor_csv_and_notify(context.bot, model))
                        logger.info(f"Đã khởi động task mới cho model {model}")
                else:
                    logger.warning(f"monitor_csv_and_notify không khả dụng cho model {model}")
        except Exception as e:
            logger.error(f"Lỗi khi cập nhật model_users hoặc running_tasks cho user_id {user_id}: {str(e)}")
            error_message = (
                f"❌ *DuyWin*: Lỗi khi thêm vào model `{escape_markdown_safev2(model)}`: `{escape_markdown_safev2(str(e))}`\\. "
                f"Liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
            )
            parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
            if not parse_mode:
                error_message = (
                    f"❌ DuyWin: Lỗi khi thêm vào model {model}: {str(e)}. "
                    f"Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
                )
            await update.message.reply_text(error_message, parse_mode=parse_mode)

    except Exception as e:
        logger.error(f"Lỗi trong hàm key_command cho user_id {user_id} (@{raw_username}): {str(e)}")
        error_message = (
            f"❌ *DuyWin*: Đã xảy ra lỗi khi sử dụng mã key\\. "
            f"Vui lòng thử lại sau hoặc liên hệ hỗ trợ: `{escape_markdown_safev2(SUPPORT_LINK.rstrip('!'))}`\\!"
        )
        parse_mode = "MarkdownV2" if validate_markdown_v2(error_message) else None
        if not parse_mode:
            error_message = f"❌ DuyWin: Đã xảy ra lỗi khi sử dụng mã key. Liên hệ hỗ trợ: {SUPPORT_LINK.rstrip('!')}!"
        await update.message.reply_text(error_message, parse_mode=parse_mode)
