import os
import pandas as pd
import asyncio
from telegram.error import Forbidden
from model.modelfree import phanTich
from lenh.config import ADMIN_IDS, ACCOUNT_FILE, running_tasks, model_users, model_predictions, last_processed_phien, db, logger, SUPPORT_LINK
from datetime import datetime

async def notify_789club(bot, model):
    global model_predictions
    logger.info(f"Bắt đầu giám sát CSV cho model {model}")
    
    # Chỉ xử lý model 789club
    if model != "789club":
        logger.error(f"Model {model} không được hỗ trợ trong monitor_csv_and_notify.py")
        return
    
    # File CSV cho 789club
    csv_file = "taixiu_789club.csv"
    
    # Khởi tạo last_processed_phien cho model nếu chưa có
    if model not in last_processed_phien:
        last_processed_phien[model] = 0
    
    while model in running_tasks:
        try:
            if os.path.exists(csv_file):
                df = pd.read_csv(csv_file)
                if not df.empty:
                    latest_row = df.iloc[-1]
                    current_phien = latest_row['Phien']

                    if current_phien > last_processed_phien[model]:
                        dice1, dice2, dice3 = latest_row['Xuc_xac_1'], latest_row['Xuc_xac_2'], latest_row['Xuc_xac_3']
                        total = latest_row['Tong']
                        result_text = latest_row['Ket_qua'].replace('Tai', 'Tài').replace('Xiu', 'Xỉu')

                        message = (
                            f"🎲 *DuyWin*: Phiên {current_phien} kết quả thực tế:\n"
                            f"Xúc xắc: {dice1}-{dice2}-{dice3}\n"
                            f"Tổng: {total} - Kết quả: {result_text}"
                        )

                        # Dự đoán cho model 789club
                        if len(df) >= 4:
                            if model_predictions["789club"]["maPhien"] != current_phien + 1:
                                recent_rolls = df[['Xuc_xac_1', 'Xuc_xac_2', 'Xuc_xac_3']].tail(1).values.tolist()[0]
                                next_duDoan = phanTich(current_phien, recent_rolls[0], recent_rolls[1], recent_rolls[2])
                                if next_duDoan == 0:
                                    model_predictions["789club"]["result"] = "Bỏ qua cầu này"
                                else:
                                    model_predictions["789club"]["result"] = "Tài" if next_duDoan == 1 else "Xỉu"
                                model_predictions["789club"]["maPhien"] = current_phien + 1
                            message += f"\n🎯 Dự đoán phiên {current_phien + 1}: {model_predictions['789club']['result']} (Model 789club)"

                        tasks = []
                        invalid_user_ids = set()
                        blocked_user_ids = set()
                        accounts = db.load_json(ACCOUNT_FILE)
                        now = datetime.now()

                        logger.info(f"model_users['{model}'] trước khi gửi: {model_users[model]}")
                        for user_id in model_users[model].copy():
                            # Kiểm tra tài khoản và model còn hạn
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
                            try:
                                tasks.append(bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown"))
                            except Exception as e:
                                logger.error(f"Lỗi khi thêm task cho user_id {user_id}: {e}")
                                invalid_user_ids.add(user_id)

                        if invalid_user_ids:
                            model_users[model].difference_update(invalid_user_ids)
                            logger.info(f"Đã loại bỏ {len(invalid_user_ids)} user_id không hợp lệ hoặc hết hạn khỏi model {model}")

                        for task in asyncio.as_completed(tasks):
                            try:
                                await task
                            except Forbidden:
                                user_id = task._coro.cr_frame.f_locals.get('chat_id')
                                if user_id:
                                    blocked_user_ids.add(user_id)
                                    username = next((u for u, v in accounts.items() if v.get("user_id") == user_id or v.get("chat_id") == user_id), str(user_id))
                                    logger.warning(f"Người dùng @{username} (user_id: {user_id}) đã chặn bot trong model {model}")
                                    for admin_id in ADMIN_IDS:
                                        await bot.send_message(
                                            chat_id=admin_id,
                                            text=f"⚠️ *DuyWin*: Người dùng @{username} (user_id: {user_id}) đã chặn bot trong model {model}",
                                            parse_mode="Markdown"
                                        )
                            except Exception as e:
                                logger.error(f"Lỗi khác khi gửi tin nhắn: {e}")

                        if blocked_user_ids:
                            model_users[model].difference_update(blocked_user_ids)
                            logger.info(f"Đã loại bỏ {len(blocked_user_ids)} người dùng chặn bot khỏi model {model}")

                        last_processed_phien[model] = current_phien
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Lỗi khi đọc CSV hoặc xử lý model {model}: {e}")
            await asyncio.sleep(5)