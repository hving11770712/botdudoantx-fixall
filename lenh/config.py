import logging
import json
import os
from datetime import datetime, timedelta
from telegram.ext import ContextTypes
from telegram import Update, Bot
from urllib.parse import quote
import re
from filelock import FileLock
import shutil

# Cấu hình logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Token của bot Telegram
TOKEN = "8091089865:AAHwKrtO0RTPK8x7AvnZ529Akg5QaaJgpgA"

# Đề xuất mới: Xác thực token khi khởi tạo
async def validate_token(token):
    """Kiểm tra tính hợp lệ của token Telegram."""
    try:
        bot = Bot(token=token)
        await bot.get_me()  # Sử dụng await cho coroutine
        logger.info("Token Telegram hợp lệ")
        return True
    except Exception as e:
        logger.error(f"Token Telegram không hợp lệ: {str(e)}")
        return False

# Lưu ý: Không validate token ở top level vì sẽ tạo xung đột event loop
# Token sẽ được validate khi bot khởi động thực sự

# Danh sách ID Admin và CTV
ADMIN_IDS = [7761915412]
CTV_IDS = []

# Thông tin ngân hàng
BANK_NAME = "ACB"
ACCOUNT_NO = "16190021"
ACCOUNT_NAME = "VI KHANH DUY"
# Nội dung nạp
NAP_CONTENT = "DW"

# Cấu hình file dữ liệu
DIR = "data"
KEY_CTV_FILE = F"{DIR}/keyctv.json"
ACCOUNT_FILE = f"{DIR}/taikhoan.json"
KEY_FILE = f"{DIR}/key.json"
GIFTCODE_FILE = f"{DIR}/giftcode.json"
NAPTIEN_FILE = f"{DIR}/naptien.txt"
BANID_FILE = f"{DIR}/ban.json"
BLOCKED_GROUPS_FILE = f"{DIR}/blocked_groups.json"
BLOCKED_INFO_FILE = f"{DIR}/group_info.json"
CONFIG_FILE = f"{DIR}/config.json"
BUYMODEL_FILE = f"{DIR}/buymodel.json"
UPDATE_BALANCE = f"{DIR}/updatebalance.txt"

# Link hỗ trợ
SUPPORT_LINK = "https://t.me/duyduy221212"

# Tạo thư mục data nếu chưa tồn tại
os.makedirs(DIR, exist_ok=True)

MODEL_PRICES = {
    "basic": 150000,
    "vip": 350000,
    "md5hit": 150000,
    "789club": 150000
}

# Đề xuất mới: Mở rộng MODEL_PRICES_WITH_DAYS cho tất cả model
MODEL_PRICES_WITH_DAYS = {
    "basic": {7: 80000, 30: 150000},
    "vip": {7: 200000, 30: 350000},
    "md5hit": {7: 80000, 30: 150000},
    "789club": {7: 80000, 30: 150000}
}

MODEL_PRICES_WITH_DAYS_buymodel = {
    "basic": [(7, 80000), (30, 150000)],
    "vip": [(7, 200000), (30, 350000)],
    "md5hit": [(7, 80000), (30, 150000)],
    "789club": [(7, 80000), (30, 150000)]
}

# Biến toàn cục
running_tasks = {}
model_users = {
    "basic": set(),
    "vip": set(),
    "md5hit": set(),
    "789club": set()
}
model_predictions = {
    "basic": {"result": None, "maPhien": 0},
    "vip": {"result": None, "maPhien": 0},
    "md5hit": {"result": None, "maPhien": 0},
    "789club": {"result": None, "maPhien": 0}
}
last_processed_phien = 0
notified_keys = set()  # Lưu key đã thông báo để chống spam

# Hàm thoát ký tự Markdown
def escape_markdown(text: str) -> str:
    """Thoát tất cả ký tự đặc biệt trong MarkdownV2 để gửi văn bản thuần."""
    if text is None:
        return ""
    text = str(text)
    special_chars = ["\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text

def escape_markdown_safe(text: str) -> str:
    """Thoát ký tự đặc biệt trong MarkdownV2, bảo vệ định dạng như *bold*, [text](link), và thoát ký tự '.'."""
    if not text:
        return ""
    special_chars = ["\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]

    def escape_special_chars(match):
        token = match.group(0)
        if (
            (token.startswith("*") and token.endswith("*") and len(token) >= 3) or
            (token.startswith("_") and token.endswith("_") and len(token) >= 3) or
            (token.startswith("`") and token.endswith("`") and len(token) >= 3) or
            (token.startswith("~") and token.endswith("~") and len(token) >= 4) or
            (token.startswith("[") and token.endswith(")") and "](" in token)
        ):
            return token
        for char in special_chars:
            token = token.replace(char, f"\\{char}")
        return token

    pattern = r"\*[^\*]+\*|_[\s\S]+?_|\[[^\]]+\]\([^\)]+\)|`[^`]+`|~[\s\S]+?~|[^\*_`\[\]~]+"
    result = re.sub(pattern, escape_special_chars, text, flags=re.MULTILINE)
    return result

def validate_markdown_v2(text: str) -> bool:
    """Kiểm tra cú pháp MarkdownV2 có hợp lệ không."""
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    stack = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] in ["_", "*", "`"]:
            if stack and stack[-1] == text[i]:
                stack.pop()
            else:
                stack.append(text[i])
        i += 1
    return len(stack) == 0

def escape_markdown_safev2(text: str) -> str:
    """
    Thoát ký tự đặc biệt trong MarkdownV2, cố gắng bảo vệ các định dạng Markdown đã có sẵn
    như *bold*, [text](link), `code`, ~strikethrough~, và _italic_ (nếu đúng cú pháp).
    Đồng thời đảm bảo các ký tự như '.', '!', '(' và ')' được thoát an toàn khi không phải là định dạng.
    """
    if not text:
        return ""

    # Bước 1: Thoát ký tự backslash trước tiên. Điều này là tối quan trọng.
    text = text.replace('\\', '\\\\')

    # Bước 2: Tìm và tạm thời thay thế các khối MarkdownV2 đã có.
    # Sử dụng một placeholder duy nhất cho mỗi khối để tránh xung đột.
    PLACEHOLDER_PREFIX = "__MD_BLOCK_"
    markdown_blocks = []
    
    # Regex để bắt các khối MarkdownV2 chính xác hơn:
    # - *bold text* (không bắt **bold**)
    # - _italic text_ (không bắt __italic__)
    # - `code`
    # - ~strikethrough~
    # - [text](url) hoặc [text](url "title")
    # - ||spoiler|| (nếu bạn sử dụng)
    # Các nhóm bắt: (?:...) để không tạo nhóm bắt thừa
    # Lưu ý: re.VERBOSE để dễ đọc regex hơn (nếu cần)
    markdown_pattern = re.compile(
        r'(\*(?:[^*]|\*(?!\*))+\*)'    # 1. Bold: *text* (matches single asterisks, not double)
        r'|(\_(?:[^_]|\_(?!_))(?<!\\)\_)' # 2. Italic: _text_ (matches single underscores, handles escaped)
        r'|(\`[^\`]+\`)'               # 3. Code: `code`
        r'|(\~[^\~]+\~)'               # 4. Strikethrough: ~text~
        r'|(\|[\|][^\|]+\|[\|])'       # 5. Spoiler: ||text||
        r'|(\[[^\]]+\]\([^\)]+\))'     # 6. Link: [text](link)
    )

    def replace_block(match):
        block = match.group(0)
        placeholder = f"{PLACEHOLDER_PREFIX}{len(markdown_blocks)}__"
        markdown_blocks.append(block)
        return placeholder

    # Thay thế các khối Markdown bằng placeholder
    processed_text = markdown_pattern.sub(replace_block, text)

    # Bước 3: Thoát các ký tự đặc biệt còn lại trong văn bản "thường" (đã có placeholder).
    # Các ký tự này phải được thoát khi chúng không nằm trong ngữ cảnh định dạng Markdown.
    # Đặc biệt quan tâm đến `.` và `!`
    # Đảm bảo các ký tự này không bị thoát hai lần nếu chúng đã là một phần của placeholder
    # hoặc đã được xử lý bởi regex.
    chars_to_escape_in_plain = r'[][()~`>#+-=|{}!.!]' # Đã bao gồm '!'
    
    escaped_plain_text = ""
    for char in processed_text:
        # Kiểm tra xem ký tự có trong danh sách cần thoát VÀ nó không phải là ký tự của placeholder
        # (Để đơn giản, chúng ta sẽ dựa vào việc các placeholder đã được tạo ở bước 2).
        # Cách tiếp cận này giả định rằng ký tự '!' hoặc '.' chỉ xuất hiện bên ngoài các khối markdown đã được bắt.
        if char in chars_to_escape_in_plain:
            escaped_plain_text += f'\\{char}'
        else:
            escaped_plain_text += char

    # Bước 4: Khôi phục các khối Markdown từ placeholder
    final_text = escaped_plain_text
    for i, block in enumerate(markdown_blocks):
        placeholder = f"{PLACEHOLDER_PREFIX}{i}__"
        final_text = final_text.replace(placeholder, block)

    return final_text


def load_json(file_path, default={}):
    """Tải dữ liệu từ file JSON, khởi tạo các trường referral nếu thiếu."""
    with FileLock(f"{file_path}.lock"):
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    try:
                        data = json.loads(content)
                        for account_key, info in data.items():
                            if "referred_by" not in info:
                                info["referred_by"] = None
                            if "referred_users" not in info:
                                info["referred_users"] = []
                            if "referral_commission" not in info:
                                info["referral_commission"] = 0
                            if "withdrawn_commission" not in info:
                                info["withdrawn_commission"] = 0
                        return data
                    except json.JSONDecodeError as e:
                        logger.error(f"Lỗi định dạng JSON trong {file_path}: {e}. Trả về giá trị mặc định.")
                        for admin_id in ADMIN_IDS:
                            if not is_banned(admin_id):
                                try:
                                    bot = Bot(token=TOKEN)
                                    bot.send_message(
                                        chat_id=admin_id,
                                        text=f"⚠️ *DuyWin*: Lỗi định dạng JSON trong {file_path}: {str(e)}",
                                        parse_mode="MarkdownV2"
                                    )
                                except Exception as e:
                                    logger.error(f"Lỗi khi thông báo admin {admin_id}: {str(e)}")
                        return default
        return default

# Đề xuất mới: Tải phần trăm hoa hồng từ file cấu hình
def load_config():
    """Tải cấu hình từ file config.json."""
    return load_json(CONFIG_FILE, {"referral_commission_percentage": 5})

REFERRAL_COMMISSION_PERCENTAGE = load_config().get("referral_commission_percentage", 5)

def save_json(file_path, data):
    """Lưu dữ liệu vào file JSON với mã hóa UTF-8."""
    with FileLock(f"{file_path}.lock"):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Lỗi khi ghi file {file_path}: {e}")
            raise

# Đề xuất mới: Hàm kiểm tra quyền admin và CTV
def is_admin(user_id):
    """Kiểm tra xem user_id có phải là admin hay không."""
    return user_id in ADMIN_IDS

def is_ctv(user_id):
    """Kiểm tra xem user_id có phải là CTV hay không."""
    return user_id in CTV_IDS

# Hàm cập nhật username
def update_username(accounts, account_key, new_username, user_id):
    """Cập nhật username và lưu lịch sử username."""
    if not isinstance(user_id, int):
        logger.error(f"user_id không hợp lệ: {user_id}")
        return
    if account_key not in accounts:
        logger.error(f"Tài khoản {account_key} không tồn tại khi cập nhật username")
        return
    if not new_username or new_username == f"ID_{user_id}":
        new_username = f"ID_{user_id}"
    if "username" not in accounts[account_key]:
        accounts[account_key]["username"] = new_username
        logger.info(f"Khởi tạo username cho {account_key}: {new_username} (user_id: {user_id})")
    elif accounts[account_key]["username"] != new_username:
        old_username = accounts[account_key]["username"]
        if "username_history" not in accounts[account_key]:
            accounts[account_key]["username_history"] = []
        accounts[account_key]["username_history"].append({
            "username": old_username,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        accounts[account_key]["username"] = new_username
        logger.info(f"Đã cập nhật username từ {old_username} sang {new_username} (user_id: {user_id})")

# Hàm cập nhật thời hạn model
def update_model_expiry(account, model, days):
    """Cập nhật thời hạn cho model, gia hạn nếu đã có hoặc tạo mới."""
    if not isinstance(days, (int, float)) or days <= 0:
        logger.error(f"Số ngày không hợp lệ: {days}")
        return None
    current_time = datetime.now()
    if model in account.get("model_expiry", {}) and account["model_expiry"][model]:
        try:
            current_expiry = datetime.strptime(account["model_expiry"][model], "%Y-%m-%d %H:%M:%S")
            expiry_time = (current_expiry + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S") if current_expiry > current_time else (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.error(f"Thời hạn không hợp lệ cho model {model}: {account['model_expiry'][model]}")
            expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        expiry_time = (current_time + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    return expiry_time

# Hàm kiểm tra và xóa key/model hết hạn
def clean_expired_keys():
    """Xóa các key đã hết hạn và lưu lại file nếu có thay đổi."""
    keys = db.load_json(KEY_FILE)
    current_time = datetime.now()
    updated = False
    for key_code in list(keys.keys()):
        expiry_str = keys[key_code].get("expiry")
        if expiry_str:
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                if current_time > expiry:
                    del keys[key_code]
                    updated = True
                    logger.info(f"Đã xóa key {key_code} vì đã hết hạn")
            except ValueError:
                logger.error(f"Thời hạn không hợp lệ cho key {key_code}: {expiry_str}")
                del keys[key_code]
                updated = True
    if updated:
        db.save_json(KEY_FILE, keys)
    return keys

def clean_expired_models():
    """Xóa các model đã hết hạn và tài khoản thiếu chat_id, lưu lại file nếu có thay đổi."""
    accounts = db.load_json(ACCOUNT_FILE)
    current_time = datetime.now()
    updated = False
    for username in list(accounts.keys()):  # Đề xuất mới: Sử dụng list để tránh lỗi khi xóa
        info = accounts[username]
        if "chat_id" not in info:
            logger.error(f"Tài khoản {username} thiếu chat_id, xóa tài khoản: {info}")
            del accounts[username]
            updated = True
            continue
        if "model_expiry" in info and isinstance(info["model_expiry"], dict):
            for model in list(info.get("model", [])):
                expiry_str = info["model_expiry"].get(model)
                if expiry_str:
                    try:
                        expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                        if current_time > expiry:
                            info["model"].remove(model)
                            del info["model_expiry"][model]
                            remove_from_old_model(info["chat_id"], None)
                            updated = True
                            logger.info(f"Đã xóa model {model} của {username} vì hết hạn")
                    except ValueError:
                        logger.error(f"Thời hạn không hợp lệ cho model {model} của {username}: {expiry_str}")
                        del info["model_expiry"][model]
                        info["model"].remove(model)
                        updated = True
    if updated:
        db.save_json(ACCOUNT_FILE, accounts)
    return accounts

def remove_from_old_model(chat_id, current_model=None):
    """Xóa chat_id khỏi các model không phải current_model và hủy task nếu cần."""
    global model_users, running_tasks
    for model in model_users:
        if model != current_model and chat_id in model_users[model]:
            model_users[model].discard(chat_id)
            logger.info(f"Đã xóa chat_id {chat_id} (nếu tồn tại) khỏi model_users['{model}']. Hiện tại: {model_users[model]}")
            if not model_users[model] and model in running_tasks:
                try:
                    running_tasks[model].cancel()
                    del running_tasks[model]
                    logger.info(f"Đã hủy task cho model {model}")
                except Exception as e:
                    logger.error(f"Lỗi khi hủy task cho model {model}: {str(e)}")

def initialize_model_users():
    """Khởi tạo model_users từ dữ dữ liệu tài khoản."""
    global model_users
    accounts = db.load_json(ACCOUNT_FILE)
    current_time = datetime.now()
    model_users = {"basic": set(), "vip": set(), "md5hit": set(), "789club": set()}
    logger.info("Đã reset model_users")
    for username, info in accounts.items():
        if "chat_id" not in info:
            logger.error(f"Tài khoản {username} thiếu chat_id: {info}")
            continue
        chat_id = info["chat_id"]
        if "model" in info:
            models = info["model"] if isinstance(info["model"], list) else []
            for model in models:
                expiry = info.get("model_expiry", {}).get(model)
                if expiry:
                    try:
                        if datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S") > current_time:
                            model_users[model].add(chat_id)
                            logger.info(f"Thêm chat_id {chat_id} vào model_users['{model}']")
                        else:
                            logger.info(f"Model {model} của {username} (chat_id: {chat_id}) đã hết hạn")
                    except ValueError:
                        logger.error(f"Thời hạn không hợp lệ cho model {model} của {username}: {expiry}")
                else:
                    model_users[model].add(chat_id)
                    logger.info(f"Thêm chat_id {chat_id} vào model_users['{model}'] (không có expiry)")
    logger.info(f"model_users sau khởi tạo: {model_users}")

# Đề xuất mới: Đồng bộ model_users với accounts
def sync_model_users():
    """Đồng bộ model_users với dữ liệu tài khoản hiện tại."""
    initialize_model_users()
    logger.info("Đã đồng bộ model_users với accounts")

async def notify_expiring_keys(bot):
    """Thông báo cho admin về các key sắp hết hạn."""
    global notified_keys
    keys = db.load_json(KEY_FILE)
    now = datetime.now()
    updated = False
    for key_code, info in keys.items():
        if key_code in notified_keys:
            continue
        try:
            expiry = datetime.strptime(info["expiry"], "%Y-%m-%d %H:%M:%S")
            if now < expiry < now + timedelta(days=1):
                for admin_id in ADMIN_IDS:
                    if not is_banned(admin_id):
                        for attempt in range(3):  # Đề xuất mới: Thử lại tối đa 3 lần
                            try:
                                safe_key_code = escape_markdown_safe(key_code)
                                safe_model = escape_markdown_safe(info["model"])
                                safe_expiry = escape_markdown_safe(info["expiry"])
                                await bot.send_message(
                                    chat_id=admin_id,
                                    text=f"⚠️ *DuyWin*: Key `{safe_key_code}` (model `{safe_model}`) sẽ hết hạn vào `{safe_expiry}`!",
                                    parse_mode="MarkdownV2"
                                )
                                logger.info(f"Đã gửi thông báo key {key_code} sắp hết hạn cho admin {admin_id}")
                                break
                            except Exception as e:
                                logger.error(f"Lỗi khi gửi thông báo admin {admin_id} về key {key_code} (lần {attempt + 1}): {str(e)}")
                                if attempt == 2:
                                    logger.error(f"Thất bại sau 3 lần thử gửi thông báo cho admin {admin_id}")
                notified_keys.add(key_code)
        except ValueError:
            logger.error(f"Thời hạn không hợp lệ cho key {key_code}: {info.get('expiry')}")
            del keys[key_code]
            updated = True
    if updated:
        db.save_json(KEY_FILE, keys)

# Đề xuất mới: Hàm sao lưu dữ liệu
def backup_data():
    """Sao lưu tất cả file dữ liệu vào thư mục backup với dấu thời gian."""
    backup_dir = f"{DIR}/backup/{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    for file in [ACCOUNT_FILE, KEY_FILE, GIFTCODE_FILE, NAPTIEN_FILE, BANID_FILE, BLOCKED_GROUPS_FILE, BLOCKED_INFO_FILE, CONFIG_FILE, BUYMODEL_FILE, UPDATE_BALANCE]:
        if os.path.exists(file):
            shutil.copy(file, backup_dir)
            logger.info(f"Đã sao lưu {file} vào {backup_dir}")

# Đề xuất mới: Hàm thống kê
def get_stats():
    """Trả về thống kê về số lượng người dùng, key và model đang hoạt động."""
    accounts = load_json(ACCOUNT_FILE)
    keys = load_json(KEY_FILE)
    stats = {
        "total_users": len(accounts),
        "total_keys": len(keys),
        "active_models": {model: len(users) for model, users in model_users.items()}
    }
    return stats

def is_banned(user_id):
    """Kiểm tra xem user_id có bị cấm hay không."""
    banned_users = load_json(BANID_FILE)
    user_id_str = str(user_id)
    return user_id_str in banned_users

async def check_ban(update: Update, context: ContextTypes) -> bool:
    """Kiểm tra xem người dùng hoặc nhóm có bị cấm hay không."""
    user_id = None
    chat_id = None
    if update.message:
        if update.message.from_user:
            user_id = update.message.from_user.id
        chat_id = update.message.chat_id
    elif update.callback_query:
        if update.callback_query.from_user:
            user_id = update.callback_query.from_user.id
        chat_id = update.callback_query.message.chat_id if update.callback_query.message else None
    elif update.channel_post:
        chat_id = update.channel_post.chat_id
    else:
        logger.warning(f"Update không hỗ trợ: {update}")
        return False

    if user_id and is_banned(user_id):
        if update.message:
            await update.message.reply_text(
                f"🔒 *DuyWin*: Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
        elif update.callback_query:
            await update.callback_query.answer(
                f"Tài khoản của bạn đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                show_alert=True
            )
        logger.info(f"User {user_id} bị cấm")
        return True

    if chat_id and is_banned(chat_id):
        if update.message:
            await update.message.reply_text(
                f"🔒 *DuyWin*: Nhóm này đã bị khóa! Liên hệ hỗ trợ: {escape_markdown_safe(SUPPORT_LINK)}",
                parse_mode="MarkdownV2"
            )
        elif update.callback_query:
            await update.callback_query.answer(
                f"Nhóm này đã bị khóa! Liên hệ hỗ trợ: {SUPPORT_LINK}",
                show_alert=True
            )
        logger.info(f"Chat {chat_id} bị cấm")
        return True

    return False

async def error_handler(update: Update, context: ContextTypes):
    """Xử lý lỗi và thông báo cho admin."""
    logger.error(f"Cập nhật {update} gây lỗi {context.error}")
    for admin_id in ADMIN_IDS:
        if not is_banned(admin_id):
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"Lỗi bot: {context.error} 😞",
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                logger.error(f"Lỗi khi gửi thông báo lỗi cho admin {admin_id}: {str(e)}")

# Lớp quản lý dữ liệu
class BotDatabase:
    def __init__(self):
        self.blocked_groups = self.load_blocked_groups()
        self.group_info = self.load_group_info()
        self.accounts = self.load_json(ACCOUNT_FILE)

    def load_blocked_groups(self):
        """Tải danh sách các nhóm bị chặn từ file JSON."""
        with FileLock(f"{BLOCKED_GROUPS_FILE}.lock"):
            try:
                with open(BLOCKED_GROUPS_FILE, "r", encoding="utf-8") as f:
                    return set(json.load(f))
            except (FileNotFoundError, json.JSONDecodeError):
                logger.error("Lỗi khi tải blocked_groups.json")
                return set()

    def load_group_info(self):
        """Tải thông tin nhóm từ file JSON."""
        with FileLock(f"{BLOCKED_INFO_FILE}.lock"):
            try:
                with open(BLOCKED_INFO_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                logger.error("Lỗi khi tải group_info.json")
                return {}

    def load_json(self, file_path, default=None):
        """Tải dữ liệu từ file JSON sử dụng hàm load_json."""
        return load_json(file_path, default if default is not None else {})

    def save_blocked_groups(self):
        """Lưu danh sách các nhóm bị chặn vào file JSON."""
        with FileLock(f"{BLOCKED_GROUPS_FILE}.lock"):
            try:
                with open(BLOCKED_GROUPS_FILE, "w", encoding="utf-8") as f:
                    json.dump(list(self.blocked_groups), f)
            except Exception as e:
                logger.error(f"Lỗi khi lưu blocked_groups: {e}")

    def save_group_info(self):
        """Lưu thông tin nhóm vào file JSON."""
        with FileLock(f"{BLOCKED_INFO_FILE}.lock"):
            try:
                with open(BLOCKED_INFO_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.group_info, f)
            except Exception as e:
                logger.error(f"Lỗi khi lưu group_info: {e}")

    def save_json(self, file_path, data):
        """Lưu dữ liệu vào file JSON sử dụng hàm save_json."""
        save_json(file_path, data)

db = BotDatabase()