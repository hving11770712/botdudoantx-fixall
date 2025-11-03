import asyncio
import aiohttp
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden, RetryAfter
from lenh.config import db, remove_from_old_model, logger, ACCOUNT_FILE, model_users, running_tasks, SUPPORT_LINK, check_ban, escape_markdown_safe, update_model_expiry, ADMIN_IDS
from datetime import datetime

# API endpoint
API_URL = "https://apihit-dudoan.onrender.com/api/hitclub"

# Lưu trữ session đã xử lý để tránh gửi trùng
last_processed_session = {"basic": 0}

async def monitor_api_basic(bot, model="basic"):
    """Giám sát API và gửi dự đoán đến người dùng."""
    global last_processed_session
    logger.info(f"Bắt đầu giám sát API cho model {model}")
    
    async with aiohttp.ClientSession() as session:
        while model in running_tasks:
            try:
                # Gọi API
                async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Lấy next_session và prediction
                        try:
                            next_session = int(data.get("next_session", 0))
                        except (ValueError, TypeError):
                            logger.warning(f"next_session không hợp lệ: {data.get('next_session')}")
                            await asyncio.sleep(1)
                            continue
                            
                        prediction = data.get("prediction", "")
                        current_result = data.get("current_result", "")
                        current_session = data.get("current_session", 0)
                        reason = data.get("reason", "")
                        current_time = data.get("current_time", "")
                        
                        logger.debug(f"API response: next_session={next_session}, prediction={prediction}")
                        
                        # Kiểm tra phiên mới
                        if next_session and next_session > last_processed_session.get(model, 0):
                            logger.info(f"Phiên mới phát hiện: {next_session}, prediction: {prediction}")
                            
                            # Chuẩn bị tin nhắn
                            safe_next_session = escape_markdown_safe(str(next_session))
                            safe_prediction = escape_markdown_safe(prediction)
                            safe_reason = escape_markdown_safe(reason) if reason else "Không có"
                            safe_current_time = escape_markdown_safe(current_time) if current_time else ""
                            
                            message = (
                                f"🎯 *DuyWin*: Dự đoán phiên {safe_next_session}\n"
                                f"🔮 *Dự đoán*: {safe_prediction}\n"
                                f"📝 *Lý do*: {safe_reason}"
                            )
                            if safe_current_time:
                                message += f"\n⏰ *Thời gian*: {safe_current_time}"
                            
                            # Gửi tin nhắn đến tất cả người dùng
                            accounts = db.load_json(ACCOUNT_FILE)
                            now = datetime.now()
                            invalid_chat_ids = set()
                            blocked_chat_ids = set()
                            
                            logger.info(f"model_users['{model}'] trước khi gửi: {model_users.get(model, set())}")
                            
                            for chat_id in model_users.get(model, set()).copy():
                                # Kiểm tra tài khoản
                                user_info = next((info for u, info in accounts.items() if info.get("chat_id") == chat_id), None)
                                if not user_info:
                                    invalid_chat_ids.add(chat_id)
                                    logger.warning(f"Không tìm thấy tài khoản cho chat_id {chat_id} trong model {model}")
                                    continue
                                
                                # Kiểm tra thời hạn
                                expiry = user_info.get("model_expiry", {}).get(model)
                                if expiry:
                                    try:
                                        if datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S") < now:
                                            invalid_chat_ids.add(chat_id)
                                            logger.info(f"Model {model} của chat_id {chat_id} đã hết hạn")
                                            try:
                                                await bot.send_message(
                                                    chat_id=chat_id,
                                                    text=f"❌ *DuyWin*: Model {escape_markdown_safe(model)} của bạn đã hết hạn\\. Mua lại bằng /buymodel {model}\\.",
                                                    parse_mode="MarkdownV2"
                                                )
                                            except Exception as e:
                                                logger.error(f"Lỗi khi gửi thông báo hết hạn cho chat_id {chat_id}: {e}")
                                            continue
                                    except ValueError:
                                        logger.error(f"Thời hạn không hợp lệ cho model {model} của chat_id {chat_id}: {expiry}")
                                        invalid_chat_ids.add(chat_id)
                                        continue
                                
                                # Gửi tin nhắn
                                try:
                                    await bot.send_message(
                                        chat_id=chat_id,
                                        text=message,
                                        parse_mode="MarkdownV2"
                                    )
                                    logger.info(f"Đã gửi dự đoán phiên {next_session} đến chat_id {chat_id} (model: {model})")
                                except Forbidden:
                                    blocked_chat_ids.add(chat_id)
                                    username = next((u for u, v in accounts.items() if v.get("chat_id") == chat_id), f"ID_{chat_id}")
                                    safe_username = escape_markdown_safe(username)
                                    logger.warning(f"Người dùng @{safe_username} (chat_id: {chat_id}) đã chặn bot")
                                    for admin_id in ADMIN_IDS:
                                        try:
                                            await bot.send_message(
                                                chat_id=admin_id,
                                                text=f"⚠️ *DuyWin*: Người dùng @{safe_username} \\(chat_id: {chat_id}\\) đã chặn bot trong model {model}",
                                                parse_mode="MarkdownV2"
                                            )
                                        except Exception as e:
                                            logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {e}")
                                except RetryAfter as e:
                                    logger.warning(f"Vượt giới hạn Telegram cho chat_id {chat_id}, chờ {e.retry_after} giây")
                                    await asyncio.sleep(e.retry_after)
                                    try:
                                        await bot.send_message(chat_id=chat_id, text=message, parse_mode="MarkdownV2")
                                        logger.info(f"Đã gửi lại dự đoán phiên {next_session} đến chat_id {chat_id}")
                                    except Exception as e2:
                                        logger.error(f"Lỗi khi gửi lại tin nhắn cho chat_id {chat_id}: {e2}")
                                except Exception as e:
                                    logger.error(f"Lỗi khi gửi tin nhắn đến chat_id {chat_id}: {e}")
                            
                            # Xóa các chat_id không hợp lệ hoặc chặn bot
                            if invalid_chat_ids:
                                model_users[model].difference_update(invalid_chat_ids)
                                logger.info(f"Đã loại bỏ {len(invalid_chat_ids)} chat_id không hợp lệ khỏi model_users['{model}']")
                            
                            if blocked_chat_ids:
                                model_users[model].difference_update(blocked_chat_ids)
                                logger.info(f"Đã loại bỏ {len(blocked_chat_ids)} người dùng chặn bot khỏi model_users['{model}']")
                            
                            # Cập nhật session đã xử lý
                            last_processed_session[model] = next_session
                            logger.info(f"Đã cập nhật last_processed_session[{model}] = {next_session}")
                    
                    else:
                        logger.warning(f"API trả về status {response.status}")
                        
            except aiohttp.ClientError as e:
                logger.error(f"Lỗi khi gọi API: {e}")
            except Exception as e:
                logger.error(f"Lỗi không xác định khi xử lý API: {e}")
            
            # Chờ 1 giây trước khi gọi lại
            await asyncio.sleep(1)
            
            # Kiểm tra nếu không còn người dùng thì dừng task
            if not model_users.get(model, set()) and model in running_tasks:
                running_tasks[model].cancel()
                del running_tasks[model]
                logger.info(f"Đã dừng task cho model {model} vì không còn người dùng")
                break

async def modelbasic_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý lệnh /modelbasic để kích hoạt Model Basic."""
    user = update.message.from_user
    user_id = user.id
    chat_id = update.message.chat_id
    username = user.username.lstrip('@') if user.username else f"ID_{user_id}"
    safe_username = escape_markdown_safe(username)

    try:
        # Kiểm tra nếu người dùng bị cấm
        if await check_ban(update, context):
            logger.warning(f"User @{username} (user_id: {user_id}) bị cấm, không thể sử dụng /modelbasic")
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa\\! Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
            return

        # Tải dữ liệu tài khoản
        accounts = db.load_json(ACCOUNT_FILE)
        account_key = str(user_id)

        if account_key not in accounts:
            logger.warning(f"Tài khoản user_id: {user_id} (@{username}) chưa đăng ký")
            await update.message.reply_text(
                f"❌ *DuyWin*: Tài khoản của bạn chưa được đăng ký\\! Hãy sử dụng /start để đăng ký\\.",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra chat_id có khớp không
        if accounts[account_key].get("chat_id") and accounts[account_key]["chat_id"] != chat_id:
            logger.warning(f"Chat_id {chat_id} không khớp với chat_id đã đăng ký {accounts[account_key]['chat_id']} cho user_id {user_id}")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn chỉ có thể sử dụng lệnh này từ chat đã đăng ký\\. Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
            return

        user_info = accounts[account_key]
        if "model" not in user_info:
            user_info["model"] = []
        if "model_expiry" not in user_info:
            user_info["model_expiry"] = {}

        # Kiểm tra quyền truy cập Model Basic
        if "basic" not in user_info["model"]:
            logger.warning(f"User @{username} (user_id: {user_id}) không có quyền truy cập Model Basic")
            await update.message.reply_text(
                f"❌ *DuyWin*: Bạn cần mua Model Basic bằng /buymodel basic hoặc sử dụng key\\!",
                parse_mode="MarkdownV2"
            )
            return

        # Kiểm tra thời hạn
        expiry = user_info["model_expiry"].get("basic")
        now = datetime.now()
        if expiry:
            try:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
                if expiry_date < now:
                    logger.warning(f"Model Basic của user @{username} (user_id: {user_id}) đã hết hạn vào {expiry}")
                    await update.message.reply_text(
                        f"❌ *DuyWin*: Model Basic của bạn đã hết hạn\\! Mua lại bằng /buymodel basic\\.",
                        parse_mode="MarkdownV2"
                    )
                    return
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho model basic của @{username} (user_id: {user_id}): {expiry}")
                await update.message.reply_text(
                    f"❌ *DuyWin*: Lỗi dữ liệu thời hạn model\\. Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                    parse_mode="MarkdownV2"
                )
                return

        # Cập nhật taikhoan.json
        if "basic" not in user_info["model"]:
            user_info["model"].append("basic")
            user_info["model_expiry"]["basic"] = update_model_expiry(user_info, "basic", 30)  # Mặc định 30 ngày
            db.save_json(ACCOUNT_FILE, accounts)
            logger.info(f"Đã thêm model basic và expiry vào taikhoan.json cho user @{username} (user_id: {user_id})")

        # Xóa khỏi model khác và thêm vào model_users['basic']
        remove_from_old_model(chat_id, current_model="basic")
        model_users.setdefault("basic", set()).add(chat_id)
        logger.info(f"Đã thêm chat_id {chat_id} vào model_users['basic']. Danh sách hiện tại: {model_users['basic']}")

        # Kiểm tra và khởi động task
        if "basic" not in running_tasks or running_tasks["basic"].done():
            running_tasks["basic"] = asyncio.create_task(monitor_api_basic(context.bot, "basic"))
            logger.info(f"Đã khởi động task mới cho model basic (đọc từ API)")
        else:
            logger.info(f"Task cho model basic đã tồn tại và đang chạy: {running_tasks['basic']}")

        # Gửi thông báo thành công
        success_message = escape_markdown_safe("Bạn đã tham gia Model Basic! Bạn sẽ nhận được dự đoán từ bot.")
        await update.message.reply_text(
            f"✅ *DuyWin*: {success_message}",
            parse_mode="MarkdownV2"
        )
        logger.info(f"User @{username} (user_id: {user_id}, chat_id: {chat_id}) đã kích hoạt Model Basic thành công")

    except Exception as e:
        logger.error(f"Lỗi trong hàm modelbasic_command cho user @{username} (user_id: {user_id}): {str(e)}")
        await update.message.reply_text(
            f"❌ *DuyWin*: Đã xảy ra lỗi khi khởi động Model Basic\\. Vui lòng thử lại sau hoặc liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
            parse_mode="MarkdownV2"
        )