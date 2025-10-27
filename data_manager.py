# data_manager.py

import os
import json
import logging
from datetime import datetime, timedelta

# --- تنظیمات مسیر فایل‌ها ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "bot_data.json")
LOG_FILE = os.path.join(BASE_DIR, "bot.log")

# --- کش داده‌های گلوبال ---
DATA = {
    "users": {},
    "banned_users": set(),
    "stats": {
        "total_messages": 0,
        "total_users": 0,
        "avg_response_time": 0.0,
        "max_response_time": 0.0,
        "min_response_time": float('inf'),
        "total_responses": 0
    },
    "welcome_message": "سلام {user_mention}! 🤖\n\nمن یک ربات مدیریت گروه هستم. با دستور /help از قابلیت‌های من مطلع شوید.",
    "goodbye_message": "کاربر {user_mention} گروه را ترک کرد. خداحافظ!",
    "maintenance_mode": False,
    "blocked_words": [],
    "scheduled_broadcasts": [],
    "bot_start_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "warnings": {},
    "group_rules": {},
    # ویژگی‌های جدید
    "auto_welcome": True,
    "auto_goodbye": True,
    "user_points": {},
    "custom_commands": {},
    "group_stats": {},
    "allowed_domains": [],
    "link_check_enabled": False,
    "anti_spam_enabled": False,
    "spam_threshold": 5,
    "spam_timeframe": 60,  # ثانیه
    "user_message_counts": {},
    "admin_levels": {},
    "default_admin_level": 1,
    "max_admin_level": 5
}

logger = logging.getLogger(__name__)

def load_data():
    """داده‌ها را از فایل JSON بارگذاری کرده و در کش گلوبال ذخیره می‌کند."""
    global DATA
    try:
        if not os.path.exists(DATA_FILE):
            logger.info(f"فایل داده در {DATA_FILE} یافت نشد. یک فایل جدید ایجاد می‌شود.")
            save_data()
            return

        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            loaded_data['banned_users'] = set(loaded_data.get('banned_users', []))
            
            # اطمینان از وجود کلیدهای جدید در فایل‌های قدیمی
            if 'blocked_words' not in loaded_data: loaded_data['blocked_words'] = []
            if 'scheduled_broadcasts' not in loaded_data: loaded_data['scheduled_broadcasts'] = []
            if 'maintenance_mode' not in loaded_data: loaded_data['maintenance_mode'] = False
            if 'bot_start_time' not in loaded_data: loaded_data['bot_start_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            if 'avg_response_time' not in loaded_data['stats']:
                loaded_data['stats']['avg_response_time'] = 0.0
                loaded_data['stats']['max_response_time'] = 0.0
                loaded_data['stats']['min_response_time'] = float('inf')
                loaded_data['stats']['total_responses'] = 0
            if 'warnings' not in loaded_data: loaded_data['warnings'] = {}
            if 'group_rules' not in loaded_data: loaded_data['group_rules'] = {}
            
            # ویژگی‌های جدید
            if 'auto_welcome' not in loaded_data: loaded_data['auto_welcome'] = True
            if 'auto_goodbye' not in loaded_data: loaded_data['auto_goodbye'] = True
            if 'user_points' not in loaded_data: loaded_data['user_points'] = {}
            if 'custom_commands' not in loaded_data: loaded_data['custom_commands'] = {}
            if 'group_stats' not in loaded_data: loaded_data['group_stats'] = {}
            if 'allowed_domains' not in loaded_data: loaded_data['allowed_domains'] = []
            if 'link_check_enabled' not in loaded_data: loaded_data['link_check_enabled'] = False
            if 'anti_spam_enabled' not in loaded_data: loaded_data['anti_spam_enabled'] = False
            if 'spam_threshold' not in loaded_data: loaded_data['spam_threshold'] = 5
            if 'spam_timeframe' not in loaded_data: loaded_data['spam_timeframe'] = 60
            if 'user_message_counts' not in loaded_data: loaded_data['user_message_counts'] = {}
            if 'admin_levels' not in loaded_data: loaded_data['admin_levels'] = {}
            if 'default_admin_level' not in loaded_data: loaded_data['default_admin_level'] = 1
            if 'max_admin_level' not in loaded_data: loaded_data['max_admin_level'] = 5

            DATA.update(loaded_data)
            logger.info(f"داده‌ها با موفقیت از {DATA_FILE} بارگذاری شدند.")

    except json.JSONDecodeError as e:
        logger.error(f"خطا در خواندن JSON از {DATA_FILE}: {e}. ربات با داده‌های اولیه شروع به کار می‌کند.")
    except Exception as e:
        logger.error(f"خطای غیرمنتظره هنگام بارگذاری داده‌ها: {e}. ربات با داده‌های اولیه شروع به کار می‌کند.")

def save_data():
    """کش گلوبال داده‌ها را در فایل JSON ذخیره می‌کند."""
    global DATA
    try:
        data_to_save = DATA.copy()
        data_to_save['banned_users'] = list(DATA['banned_users'])
        
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        logger.debug(f"داده‌ها با موفقیت در {DATA_FILE} ذخیره شدند.")
    except Exception as e:
        logger.error(f"خطای مهلک: امکان ذخیره داده‌ها در {DATA_FILE} وجود ندارد. خطا: {e}")

def update_user_stats(user_id: int, user):
    """آمار کاربر را پس از هر پیام به‌روز کرده و داده‌ها را ذخیره می‌کند."""
    global DATA
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_id_str = str(user_id)
    
    if user_id_str not in DATA['users']:
        DATA['users'][user_id_str] = {
            'first_name': user.first_name,
            'username': user.username,
            'first_seen': now_str,
            'message_count': 0
        }
        DATA['stats']['total_users'] += 1
        logger.info(f"کاربر جدید ثبت شد: {user_id} ({user.first_name})")
        
        # مقداردهی اولیه امتیاز کاربر
        if user_id_str not in DATA['user_points']:
            DATA['user_points'][user_id_str] = {
                'points': 0,
                'last_activity': now_str,
                'level': 1,
                'daily_messages': 0,
                'last_reset_date': datetime.now().strftime('%Y-%m-%d')
            }

    DATA['users'][user_id_str]['last_seen'] = now_str
    DATA['users'][user_id_str]['message_count'] += 1
    DATA['stats']['total_messages'] += 1
    
    # به‌روزرسانی امتیاز کاربر
    update_user_points(user_id)
    
    # به‌روزرسانی شمارنده پیام‌ها برای ضد اسپم
    update_user_message_count(user_id)
    
    save_data()

def update_user_points(user_id: int):
    """امتیاز کاربر را به‌روز می‌کند."""
    global DATA
    user_id_str = str(user_id)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')
    
    if user_id_str not in DATA['user_points']:
        DATA['user_points'][user_id_str] = {
            'points': 0,
            'last_activity': now_str,
            'level': 1,
            'daily_messages': 0,
            'last_reset_date': today
        }
    
    # ریست شمارنده پیام‌های روزانه در صورت لزوم
    if DATA['user_points'][user_id_str]['last_reset_date'] != today:
        DATA['user_points'][user_id_str]['daily_messages'] = 0
        DATA['user_points'][user_id_str]['last_reset_date'] = today
    
    # افزایش امتیاز
    DATA['user_points'][user_id_str]['points'] += 1
    DATA['user_points'][user_id_str]['daily_messages'] += 1
    DATA['user_points'][user_id_str]['last_activity'] = now_str
    
    # بررسی سطح جدید
    points = DATA['user_points'][user_id_str]['points']
    new_level = 1 + (points // 100)  # هر 100 امتیاز یک سطح جدید
    
    if new_level > DATA['user_points'][user_id_str]['level']:
        DATA['user_points'][user_id_str]['level'] = new_level
        return True  # بازگشت True برای نشان دادن ارتقاء سطح
    
    return False

def update_user_message_count(user_id: int):
    """شمارنده پیام‌های کاربر را برای ضد اسپم به‌روز می‌کند."""
    global DATA
    user_id_str = str(user_id)
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    if user_id_str not in DATA['user_message_counts']:
        DATA['user_message_counts'][user_id_str] = []
    
    # حذف پیام‌های قدیمی‌تر از بازه زمانی اسپم
    cutoff_time = now - timedelta(seconds=DATA['spam_timeframe'])
    DATA['user_message_counts'][user_id_str] = [
        msg_time for msg_time in DATA['user_message_counts'][user_id_str]
        if datetime.strptime(msg_time, '%Y-%m-%d %H:%M:%S') > cutoff_time
    ]
    
    # افزودن پیام جدید
    DATA['user_message_counts'][user_id_str].append(now_str)

def is_user_spamming(user_id: int) -> bool:
    """بررسی می‌کند آیا کاربر در حال اسپم کردن است یا خیر."""
    if not DATA.get('anti_spam_enabled', False):
        return False
    
    user_id_str = str(user_id)
    if user_id_str not in DATA['user_message_counts']:
        return False
    
    return len(DATA['user_message_counts'][user_id_str]) > DATA['spam_threshold']

def update_group_stats(chat_id: int, message_type: str):
    """آمار گروه را به‌روز می‌کند."""
    global DATA
    chat_id_str = str(chat_id)
    today = datetime.now().strftime('%Y-%m-%d')
    
    if chat_id_str not in DATA['group_stats']:
        DATA['group_stats'][chat_id_str] = {}
    
    if today not in DATA['group_stats'][chat_id_str]:
        DATA['group_stats'][chat_id_str][today] = {
            'total_messages': 0,
            'text_messages': 0,
            'photo_messages': 0,
            'video_messages': 0,
            'sticker_messages': 0,
            'voice_messages': 0,
            'new_members': 0,
            'left_members': 0
        }
    
    DATA['group_stats'][chat_id_str][today]['total_messages'] += 1
    DATA['group_stats'][chat_id_str][today][f'{message_type}_messages'] += 1

def update_response_stats(response_time: float):
    """آمار زمان پاسخگویی را به‌روز می‌کند."""
    global DATA
    
    if DATA['stats']['total_responses'] == 0:
        DATA['stats']['min_response_time'] = response_time

    DATA['stats']['total_responses'] += 1
    
    # محاسبه میانگین جدید
    current_avg = DATA['stats']['avg_response_time']
    total_responses = DATA['stats']['total_responses']
    new_avg = ((current_avg * (total_responses - 1)) + response_time) / total_responses
    DATA['stats']['avg_response_time'] = new_avg
    
    # به‌روزرسانی حداکثر و حداقل زمان پاسخگویی
    if response_time > DATA['stats']['max_response_time']:
        DATA['stats']['max_response_time'] = response_time
    
    if response_time < DATA['stats']['min_response_time']:
        DATA['stats']['min_response_time'] = response_time
    
    save_data()

def is_user_banned(user_id: int) -> bool:
    """بررسی می‌کند آیا کاربر مسدود شده است یا خیر."""
    return user_id in DATA['banned_users']

def ban_user(user_id: int):
    """کاربر را مسدود کرده و ذخیره می‌کند."""
    DATA['banned_users'].add(user_id)
    save_data()

def unban_user(user_id: int):
    """مسدودیت کاربر را برداشته و ذخیره می‌کند."""
    DATA['banned_users'].discard(user_id)
    save_data()

def contains_blocked_words(text: str) -> bool:
    """بررسی می‌کند آیا متن حاوی کلمات مسدود شده است یا خیر."""
    if not DATA['blocked_words']:
        return False
    
    text_lower = text.lower()
    for word in DATA['blocked_words']:
        if word in text_lower:
            return True
    
    return False

def check_link_safety(text: str) -> bool:
    """بررسی می‌کند آیا لینک‌های موجود در متن امن هستند یا خیر."""
    if not DATA.get('link_check_enabled', False):
        return True
    
    import re
    url_pattern = re.compile(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+')
    urls = url_pattern.findall(text)
    
    if not urls:
        return True
    
    allowed_domains = DATA.get('allowed_domains', [])
    
    for url in urls:
        domain = url.split('//')[-1].split('/')[0].lower()
        if not any(domain.endswith(allowed) for allowed in allowed_domains):
            return False
    
    return True

def get_active_users(days: int) -> list:
    """لیست کاربران فعال در بازه زمانی مشخص را برمی‌گرداند."""
    now = datetime.now()
    cutoff_date = now - timedelta(days=days)
    
    active_users = []
    for user_id, user_info in DATA['users'].items():
        if 'last_seen' in user_info:
            try:
                last_seen = datetime.strptime(user_info['last_seen'], '%Y-%m-%d %H:%M:%S')
                if last_seen >= cutoff_date:
                    active_users.append(int(user_id))
            except ValueError:
                continue
    
    return active_users

def get_users_by_message_count(min_count: int) -> list:
    """لیست کاربران با تعداد پیام بیشتر یا مساوی مقدار مشخص را برمی‌گرداند."""
    users = []
    for user_id, user_info in DATA['users'].items():
        if user_info.get('message_count', 0) >= min_count:
            users.append(int(user_id))
    
    return users

def get_user_points(user_id: int) -> dict:
    """اطلاعات امتیاز کاربر را برمی‌گرداند."""
    user_id_str = str(user_id)
    return DATA.get('user_points', {}).get(user_id_str, {
        'points': 0,
        'last_activity': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'level': 1,
        'daily_messages': 0,
        'last_reset_date': datetime.now().strftime('%Y-%m-%d')
    })

def get_top_users_by_points(limit: int = 10) -> list:
    """لیست کاربران برتر بر اساس امتیاز را برمی‌گرداند."""
    users_points = []
    
    for user_id_str, points_data in DATA.get('user_points', {}).items():
        user_id = int(user_id_str)
        user_info = DATA.get('users', {}).get(user_id_str, {})
        
        users_points.append({
            'user_id': user_id,
            'points': points_data.get('points', 0),
            'level': points_data.get('level', 1),
            'name': user_info.get('first_name', 'Unknown')
        })
    
    # مرتب‌سازی بر اساس امتیاز
    users_points.sort(key=lambda x: x['points'], reverse=True)
    
    return users_points[:limit]

def get_custom_command(command: str) -> str:
    """متن دستور سفارشی را برمی‌گرداند."""
    return DATA.get('custom_commands', {}).get(command.lower(), "")

def set_custom_command(command: str, response: str):
    """دستور سفارشی جدید را تنظیم می‌کند."""
    if 'custom_commands' not in DATA:
        DATA['custom_commands'] = {}
    
    DATA['custom_commands'][command.lower()] = response
    save_data()

def delete_custom_command(command: str):
    """دستور سفارشی را حذف می‌کند."""
    if 'custom_commands' in DATA and command.lower() in DATA['custom_commands']:
        del DATA['custom_commands'][command.lower()]
        save_data()

def get_group_stats(chat_id: int, days: int = 7) -> dict:
    """آمار گروه را برای بازه زمانی مشخص برمی‌گرداند."""
    chat_id_str = str(chat_id)
    if chat_id_str not in DATA.get('group_stats', {}):
        return {}
    
    now = datetime.now()
    cutoff_date = now - timedelta(days=days)
    
    stats = {
        'total_messages': 0,
        'text_messages': 0,
        'photo_messages': 0,
        'video_messages': 0,
        'sticker_messages': 0,
        'voice_messages': 0,
        'new_members': 0,
        'left_members': 0,
        'daily_stats': {}
    }
    
    for date_str, day_stats in DATA['group_stats'][chat_id_str].items():
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if date >= cutoff_date:
                stats['total_messages'] += day_stats.get('total_messages', 0)
                stats['text_messages'] += day_stats.get('text_messages', 0)
                stats['photo_messages'] += day_stats.get('photo_messages', 0)
                stats['video_messages'] += day_stats.get('video_messages', 0)
                stats['sticker_messages'] += day_stats.get('sticker_messages', 0)
                stats['voice_messages'] += day_stats.get('voice_messages', 0)
                stats['new_members'] += day_stats.get('new_members', 0)
                stats['left_members'] += day_stats.get('left_members', 0)
                
                stats['daily_stats'][date_str] = day_stats.copy()
        except ValueError:
            continue
    
    return stats

def get_admin_level(user_id: int) -> int:
    """سطح ادمین کاربر را برمی‌گرداند."""
    user_id_str = str(user_id)
    return DATA.get('admin_levels', {}).get(user_id_str, 0)

def set_admin_level(user_id: int, level: int):
    """سطح ادمین کاربر را تنظیم می‌کند."""
    user_id_str = str(user_id)
    max_level = DATA.get('max_admin_level', 5)
    
    if level < 0:
        level = 0
    elif level > max_level:
        level = max_level
    
    if 'admin_levels' not in DATA:
        DATA['admin_levels'] = {}
    
    DATA['admin_levels'][user_id_str] = level
    save_data()

def get_admins_by_level(min_level: int = 1) -> list:
    """لیست ادمین‌ها با سطح حداقل مشخص را برمی‌گرداند."""
    admins = []
    
    for user_id_str, level in DATA.get('admin_levels', {}).items():
        if level >= min_level:
            user_id = int(user_id_str)
            user_info = DATA.get('users', {}).get(user_id_str, {})
            
            admins.append({
                'user_id': user_id,
                'level': level,
                'name': user_info.get('first_name', 'Unknown'),
                'username': user_info.get('username', '')
            })
    
    return admins

# بارگذاری اولیه داده‌ها در زمان ایمپورت شدن ماژول
load_data()
