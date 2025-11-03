import os
import pandas as pd
import asyncio
import nest_asyncio
import re 
from telegram import Bot
from telegram.error import Forbidden, NetworkError, TelegramError
from model.hitmd5 import aggregate_md5_results
from lenh.config import (
    ADMIN_IDS, ACCOUNT_FILE, running_tasks, model_users, model_predictions,
    last_processed_phien, db, logger, SUPPORT_LINK
)
from datetime import datetime
from asyncio import Queue

# Áp dụng nest_asyncio để tránh lỗi event loop
nest_asyncio.apply()

# Khóa để đồng bộ truy cập model_users
model_users_lock = asyncio.Lock()

async def send_message_to_users(bot, model, message):
    """Hàm hỗ trợ gửi tin nhắn đến tất cả người dùng của model bằng hàng đợi bất đồng bộ"""
    queue = Queue()
    async with model_users_lock:
        invalid_user_ids = set()
        blocked_user_ids = set()
        accounts = db.load_json(ACCOUNT_FILE)
        now = datetime.now()

        logger.info(f"Danh sách người dùng model_users['{model}']: {model_users.get(model, set())}")
        if not model_users.get(model, set()):
            logger.warning(f"Không có người dùng nào trong model_users['{model}'], không gửi tin nhắn")
            return

        for user_id in model_users[model].copy():
            user_info = next((info for u, info in accounts.items() if info.get("user_id") == user_id or info.get("chat_id") == user_id), None)
            if not user_info:
                invalid_user_ids.add(user_id)
                logger.warning(f"Không tìm thấy tài khoản cho user_id {user_id} trong model {model}")
                continue
            if model not in user_info.get("model", []):
                invalid_user_ids.add(user_id)
                logger.warning(f"User_id {user_id} không có model {model}")
                continue
            expiry = user_info.get("model_expiry", {}).get(model)
            if expiry:
                try:
                    if datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S") < now:
                        invalid_user_ids.add(user_id)
                        logger.info(f"Model {model} của user_id {user_id} đã hết hạn")
                        continue
                except ValueError:
                    logger.error(f"Thời hạn không hợp lệ cho model {model} của user_id {user_id}: {expiry}")
                    invalid_user_ids.add(user_id)
                    continue
            await queue.put((user_id, message))

        if invalid_user_ids:
            model_users[model].difference_update(invalid_user_ids)
            logger.info(f"Đã loại bỏ {len(invalid_user_ids)} user_id không hợp lệ hoặc hết hạn khỏi model {model}")

    async def process_queue():
        while not queue.empty():
            user_id, msg = await queue.get()
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode="Markdown"
                )
                logger.info(f"Đã gửi tin nhắn cho user_id {user_id} trong model {model}")
            except Forbidden:
                blocked_user_ids.add(user_id)
                username = next((u for u, v in accounts.items() if v.get("user_id") == user_id or v.get("chat_id") == user_id), str(user_id))
                logger.warning(f"Người dùng @{username} (user_id: {user_id}) đã chặn bot trong model {model}")
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=f"⚠️ *DuyWin*: Người dùng @{username} (user_id: {user_id}) đã chặn bot trong model {model}",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Lỗi khi gửi thông báo admin {admin_id}: {str(e)}")
            except NetworkError as e:
                logger.warning(f"Lỗi mạng khi gửi tin nhắn cho user_id {user_id} (model {model}): {str(e)}")
                await asyncio.sleep(1)
            except TelegramError as e:
                logger.error(f"Lỗi Telegram khi gửi tin nhắn cho user_id {user_id} (model {model}): {str(e)}")
            queue.task_done()

    await process_queue()

    async with model_users_lock:
        if blocked_user_ids:
            model_users[model].difference_update(blocked_user_ids)
            logger.info(f"Đã loại bỏ {len(blocked_user_ids)} người dùng chặn bot khỏi model {model}")

async def monitor_csv_md5(bot, model="md5hit"):
    """Giám sát file CSV và gửi dự đoán/kết quả đến bot Telegram"""
    global last_processed_phien, model_predictions
    logger.info(f"Bắt đầu giám sát CSV MD5 cho model {model}")
    last_md5_row = None
    csv_path = "taixiu_hitmd5.csv"  # File ở thư mục chính

    while model in running_tasks:
        try:
            logger.debug(f"Kiểm tra file CSV: {csv_path}")
            if not os.path.exists(csv_path):
                logger.error(f"File {csv_path} không tồn tại")
                await asyncio.sleep(5)
                continue

            try:
                df = pd.read_csv(csv_path, dtype={'Phien': str}, usecols=['Phien', 'MD5', 'Xuc_xac_1', 'Xuc_xac_2', 'Xuc_xac_3', 'Tong', 'Ket_qua'])
                logger.debug(f"Đã đọc file CSV, số dòng: {len(df)}")
            except pd.errors.EmptyDataError:
                logger.warning(f"File {csv_path} rỗng hoặc bị hỏng")
                await asyncio.sleep(5)
                continue
            except FileNotFoundError:
                logger.error(f"Không tìm thấy file {csv_path}")
                await asyncio.sleep(5)
                continue
            except Exception as e:
                logger.exception(f"Lỗi khi đọc file CSV {csv_path}: {str(e)}")
                await asyncio.sleep(5)
                continue

            if df.empty:
                logger.warning("File CSV rỗng")
                await asyncio.sleep(2)
                continue

            required_columns = ['Phien', 'MD5']
            if not all(col in df.columns for col in required_columns):
                logger.error(f"File CSV thiếu cột: {set(required_columns) - set(df.columns)}")
                await asyncio.sleep(5)
                continue

            latest_row = df.iloc[-1]
            current_phien = str(latest_row['Phien'])
            logger.debug(f"Phiên hiện tại: {current_phien}, last_processed_phien: {last_processed_phien}, last_md5_row: {last_md5_row.get('Phien') if last_md5_row is not None else None}")

            try:
                int(current_phien)
            except ValueError:
                logger.error(f"Phiên không hợp lệ: {current_phien}")
                await asyncio.sleep(2)
                continue

            logger.debug(f"Dòng mới nhất: {latest_row.to_dict()}")

            if pd.isna(latest_row.get('Xuc_xac_1', None)) and pd.isna(latest_row.get('Xuc_xac_2', None)) and pd.isna(latest_row.get('Xuc_xac_3', None)):
                if last_md5_row is None or str(last_md5_row['Phien']) != current_phien:
                    md5 = latest_row['MD5']
                    try:
                        prediction, explanation = aggregate_md5_results()
                        # Trích xuất xác suất từ explanation
                        try:
                            prob_part = explanation.split("; ")[-1]  # Lấy phần cuối cùng chứa xác suất
                            tai_match = re.search(r"Tài (\d+\.\d+)%", prob_part)
                            xiu_match = re.search(r"Xỉu (\d+\.\d+)%", prob_part)
                            tai_prob = float(tai_match.group(1)) / 100 if tai_match else 0.5
                            xiu_prob = float(xiu_match.group(1)) / 100 if xiu_match else 0.5
                        except Exception as e:
                            logger.error(f"Lỗi khi trích xuất xác suất từ explanation: {str(e)}")
                            tai_prob, xiu_prob = 0.5, 0.5  # Giá trị mặc định nếu lỗi
                        logger.info(f"Dự đoán cho MD5 {md5}: {prediction}, giải thích: {explanation}, Tài: {tai_prob:.2%}, Xỉu: {xiu_prob:.2%}")
                    except Exception as e:
                        logger.exception(f"Lỗi khi chạy aggregate_md5_results cho MD5 {md5}: {str(e)}")
                        await asyncio.sleep(2)
                        continue
                    async with model_users_lock:
                        model_predictions[model] = {
                            "maPhien": current_phien,
                            "result": prediction,
                            "confidence": {"tai": tai_prob, "xiu": xiu_prob}
                        }
                    message = (
                        f"🔄 *DuyWin*: Phiên mới: {current_phien}\n"
                        f"🔒 MD5: {md5}\n"
                        f"🎯 Dự đoán: {prediction}\n"
                        f"📊 Xác suất: Tài {tai_prob:.2%}, Xỉu {xiu_prob:.2%}\n"
                        f"📝 Giải thích: {explanation}"
                    )
                    logger.info(f"Chuẩn bị gửi dự đoán cho phiên {current_phien}: {prediction} (Tài: {tai_prob:.2%}, Xỉu: {xiu_prob:.2%})")
                    await send_message_to_users(bot, model, message)
                    last_md5_row = latest_row
                else:
                    logger.debug(f"Phiên {current_phien} đã được xử lý trước đó")
                await asyncio.sleep(2)
                continue

            try:
                if int(current_phien) > int(last_processed_phien) and not pd.isna(latest_row.get('Xuc_xac_1', None)):
                    dice1 = int(latest_row['Xuc_xac_1'])
                    dice2 = int(latest_row['Xuc_xac_2'])
                    dice3 = int(latest_row['Xuc_xac_3'])
                    total = int(latest_row['Tong'])
                    result_text = latest_row['Ket_qua'].replace('Tai', 'Tài').replace('Xiu', 'Xỉu')

                    message = (
                        f"🎲 *DuyWin*: Phiên {current_phien} kết quả thực tế:\n"
                        f"Xúc xắc: {dice1}-{dice2}-{dice3}\n"
                        f"Tổng: {total} - Kết quả: {result_text}"
                    )

                    async with model_users_lock:
                        if model_predictions.get(model, {}).get("maPhien") == current_phien:
                            prediction = model_predictions[model]["result"]
                            tai_prob = model_predictions[model]["confidence"]["tai"]
                            xiu_prob = model_predictions[model]["confidence"]["xiu"]
                            message += (
                                f"\n🎯 Dự đoán trước: {prediction} (Tài: {tai_prob:.2%}, Xỉu: {xiu_prob:.2%})\n"
                                f"✅ Kết quả: {'Đúng' if prediction == result_text else 'Sai'}"
                            )

                    logger.info(f"Chuẩn bị gửi kết quả cho phiên {current_phien}: {result_text}")
                    await send_message_to_users(bot, model, message)

                    last_processed_phien = current_phien
                    last_md5_row = None
            except ValueError as e:
                logger.error(f"Lỗi khi so sánh Phien: {str(e)}")
                await asyncio.sleep(2)
                continue

            async with model_users_lock:
                if not model_users.get(model, set()) and model in running_tasks:
                    running_tasks[model].cancel()
                    del running_tasks[model]
                    logger.info(f"Đã dừng task cho model {model} vì không còn người dùng")
                    break

            await asyncio.sleep(2)

        except Exception as e:
            logger.exception(f"Lỗi tổng quát khi xử lý model {model}: {str(e)}")
            await asyncio.sleep(5)