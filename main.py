# main.py

import os
import logging
import asyncio
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# وارد کردن مدیر داده‌ها و پنل ادمین
import data_manager
import admin_panel

# --- بهبود لاگینگ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    filename=data_manager.LOG_FILE, 
    filemode='a'
)
logger = logging.getLogger(__name__)

try:
    with open(data_manager.LOG_FILE, 'a') as f:
        f.write("")
except Exception as e:
    print(f"FATAL: Could not write to log file at {data_manager.LOG_FILE}. Error: {e}")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# --- دیکشنری برای مدیریت وظایف پس‌زمینه هر کاربر ---
user_tasks = {}

# --- توابع کمکی برای مدیریت وظایف ---
def _cleanup_task(task: asyncio.Task, user_id: int):
    if user_id in user_tasks and user_tasks[user_id] == task:
        del user_tasks[user_id]
        logger.info(f"Cleaned up finished task for user {user_id}.")
    try:
        exception = task.exception()
        if exception:
            logger.error(f"Background task for user {user_id} failed: {exception}")
    except asyncio.CancelledError:
        logger.info(f"Task for user {user_id} was cancelled.")

# --- هندلرهای اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    
    data_manager.update_user_stats(user_id, user)
    
    welcome_msg = data_manager.DATA.get('welcome_message', "سلام {user_mention}! 🤖\n\nمن یک ربات مدیریت گروه هستم. با دستور /help از قابلیت‌های من مطلع شوید.")
    try:
        await update.message.reply_html(
            welcome_msg.format(user_mention=user.mention_html()),
            disable_web_page_preview=True
        )
    except TelegramError as e:
        logger.error(f"Failed to send start message: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش راهنمای ربات."""
    help_text = (
        "🤖 **راهنمای ربات مدیریت گروه**\n\n"
        "📋 **دستورات عمومی:**\n"
        "• `/start` - شروع ربات و نمایش پیام خوشامدگویی\n"
        "• `/help` - نمایش این راهنما\n\n"
        "🛡️ **دستورات مدیریت گروه (فقط برای ادمین‌ها):**\n"
        "• `/ban` - مسدود کردن ارسال پیام کاربر (با ریپلای)\n"
        "• `/unban` - رفع مسدودیت ارسال پیام کاربر (با ریپلای)\n"
        "• `/mute` - بی‌صدا کردن کاربر با ریپلای روی پیام او\n"
        "• `/unmute` - درآوردن از حالت بی‌صدا\n"
        "• `/warn` - اخطار دادن به کاربر با ریپلای روی پیام او\n"
        "• `/del` - حذف پیام با ریپلای روی آن\n"
        "• `/purge` - حذف تمام پیام‌ها بعد از پیام مورد نظر\n"
        "• `/pin` - سنجاق کردن پیام با ریپلای روی آن\n"
        "• `/unpin` - درآوردن پیام از حالت سنجاق شده\n"
        "• `/rules` - نمایش قوانین گروه\n"
        "• `/setrules` - تنظیم قوانین جدید گروه\n"
        "• `/info` - نمایش اطلاعات گروه\n\n"
        "🔧 **دستورات ادمین ربات:**\n"
        "• `/commands` - نمایش تمام دستورات ادمین ربات"
    )
    try:
        await update.message.reply_text(help_text, parse_mode='Markdown')
    except TelegramError as e:
        logger.error(f"Failed to send help message: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مدیریت پیام‌های کاربران در گروه."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    message = update.message
    
    # بررسی مسدود بودن کاربر (برای بن‌های سراسری از پنل ادمین)
    if data_manager.is_user_banned(user_id):
        logger.info(f"Globally banned user {user_id} tried to send a message in group {chat_id}.")
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Failed to delete message from globally banned user: {e}")
        return
    
    # بررسی حالت نگهداری (فقط برای کاربران عادی)
    if data_manager.DATA.get('maintenance_mode', False) and user_id not in admin_panel.ADMIN_IDS:
        try:
            await update.message.reply_text("🔧 ربات در حال حاضر در حالت نگهداری قرار دارد. لطفاً بعداً تلاش کنید.")
        except TelegramError as e:
            logger.error(f"Failed to send maintenance message: {e}")
        return

    # بررسی کلمات مسدود شده
    if data_manager.contains_blocked_words(message.text):
        logger.info(f"User {user_id} sent a message with a blocked word in group {chat_id}.")
        try:
            await message.delete()
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⚠️ پیام شما حاوی کلمات نامناسب بود و حذف شد.",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Failed to handle blocked word message: {e}")
        return
    
    # به‌روزرسانی آمار کاربر
    data_manager.update_user_stats(user_id, update.effective_user)

# --- هندلرهای مدیریت گروه ---
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مسدود کردن ارسال پیام کاربر (بدون اخراج از گروه)."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for ban command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return
    
    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیام کاربری که می‌خواهید مسدود کنید ریپلای کنید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    
    # بررسی اینکه آیا کاربر هدف ادمین است
    try:
        target_chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_chat_member.status in ['administrator', 'creator']:
            await update.message.reply_text("🛡️ شما نمی‌توانید یک ادمین را مسدود کنید!")
            return
    except TelegramError as e:
        logger.error(f"Failed to check target admin status for ban command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی کاربر هدف.")
        return
    
    try:
        # مسدود کردن کامل ارسال پیام
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions={
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_polls': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False,
                'can_change_info': False,
                'can_invite_users': False,
                'can_pin_messages': False
            }
        )
        
        await update.message.reply_text(
            f"🔇 کاربر {target_user.mention_html()} مسدود شد و دیگر نمی‌تواند در گروه پیام ارسال کند.",
            parse_mode='HTML'
        )
        
        # ارسال پیام به کاربر مسدود شده
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🔇 شما توسط ادمین گروه {update.effective_chat.title} مسدود شدید و دیگر نمی‌توانید پیام ارسال کنید."
            )
        except Exception as e:
            logger.warning(f"Could not send ban notification to user {target_user_id}: {e}")
            
    except Exception as e:
        logger.error(f"Error banning user {target_user_id}: {e}")
        await update.message.reply_text(f"❌ خطا در مسدود کردن کاربر: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رفع مسدودیت ارسال پیام کاربر."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for unban command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیام کاربری که می‌خواهید مسدودیتش را بردارید ریپلای کنید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    
    try:
        # بازگرداندن تمام دسترسی‌های ارسال پیام
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions={
                'can_send_messages': True,
                'can_send_media_messages': True,
                'can_send_polls': True,
                'can_send_other_messages': True,
                'can_add_web_page_previews': True
            }
        )
        
        await update.message.reply_text(
            f"🔊 مسدودیت کاربر {target_user.mention_html()} برداشته شد و می‌تواند دوباره پیام ارسال کند.",
            parse_mode='HTML'
        )
        
        # ارسال پیام به کاربر برای رفع مسدودیت
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🔊 مسدودیت شما در گروه {update.effective_chat.title} برداشته شد. می‌توانید دوباره پیام ارسال کنید."
            )
        except Exception as e:
            logger.warning(f"Could not send unban notification to user {target_user_id}: {e}")
            
    except Exception as e:
        logger.error(f"Error unbanning user {target_user_id}: {e}")
        await update.message.reply_text(f"❌ خطا در رفع مسدودیت کاربر: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بی‌صدا کردن کاربر با ریپلای روی پیام او."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for mute command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return
    
    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیام کاربری که می‌خواهید بی‌صدا کنید ریپلای کنید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    
    # بررسی اینکه آیا کاربر هدف ادمین است
    try:
        target_chat_member = await context.bot.get_chat_member(chat_id, target_user_id)
        if target_chat_member.status in ['administrator', 'creator']:
            await update.message.reply_text("🛡️ شما نمی‌توانید یک ادمین را بی‌صدا کنید!")
            return
    except TelegramError as e:
        logger.error(f"Failed to check target admin status for mute command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی کاربر هدف.")
        return
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions={'can_send_messages': False}
        )
        
        await update.message.reply_text(
            f"🔇 کاربر {target_user.mention_html()} با موفقیت بی‌صدا شد.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error muting user {target_user_id}: {e}")
        await update.message.reply_text(f"❌ خطا در بی‌صدا کردن کاربر: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """درآوردن کاربر از حالت بی‌صدا."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for unmute command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیام کاربری که می‌خواهید از حالت بی‌صدا درآورید ریپلای کنید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions={'can_send_messages': True}
        )
        
        await update.message.reply_text(
            f"🔊 کاربر {target_user.mention_html()} با موفقیت از حالت بی‌صدا درآمد.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Error unmuting user {target_user_id}: {e}")
        await update.message.reply_text(f"❌ خطا در درآوردن کاربر از حالت بی‌صدا: {e}")

async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اخطار دادن به کاربر با ریپلای روی پیام او."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for warn command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیام کاربری که می‌خواهید اخطار دهید ریپلای کنید.")
        return
    
    target_user = update.message.reply_to_message.from_user
    target_user_id = target_user.id
    
    # دریافت یا ایجاد شمارنده اخطار برای کاربر
    if 'warnings' not in data_manager.DATA:
        data_manager.DATA['warnings'] = {}
    
    user_warnings = data_manager.DATA['warnings'].get(str(target_user_id), 0)
    user_warnings += 1
    data_manager.DATA['warnings'][str(target_user_id)] = user_warnings
    data_manager.save_data()
    
    # تعیین متن اخطار بر اساس تعداد اخطارها
    if user_warnings == 1:
        warn_text = f"⚠️ {target_user.mention_html()} این اولین اخطار شماست. لطفاً قوانین گروه را رعایت کنید."
    elif user_warnings == 2:
        warn_text = f"⚠️ {target_user.mention_html()} این دومین اخطار شماست. در صورت تکرار، از ارسال پیام مسدود خواهید شد."
    else:
        warn_text = f"⚠️ {target_user.mention_html()} این سومین اخطار شماست. به دلیل تخلف مکرر از ارسال پیام مسدود شدید."
        try:
            # مسدود کردن کامل ارسال پیام به جای اخراج
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_user_id,
                permissions={
                    'can_send_messages': False,
                    'can_send_media_messages': False,
                    'can_send_polls': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False,
                }
            )
        except Exception as e:
            logger.error(f"Error restricting user after 3 warnings: {e}")
    
    try:
        await update.message.reply_text(warn_text, parse_mode='HTML')
    except TelegramError as e:
        logger.error(f"Failed to send warning message: {e}")

async def del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """حذف پیام با ریپلای روی آن."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for del command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیامی که می‌خواهید حذف کنید ریپلای کنید.")
        return
    
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete()
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        await update.message.reply_text(f"❌ خطا در حذف پیام: {e}")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """حذف تمام پیام‌ها بعد از پیام مورد نظر."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for purge command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیامی که می‌خواهید از آن به بعد پیام‌ها حذف شوند ریپلای کنید.")
        return
    
    target_message_id = update.message.reply_to_message.message_id
    
    try:
        # حذف پیام دستور
        await update.message.delete()
        
        # دریافت پیام‌های بعد از پیام هدف
        messages = await context.bot.get_chat_history(
            chat_id=chat_id,
            offset_id=target_message_id,
            limit=100
        )
        
        # حذف پیام‌ها
        for message in messages:
            try:
                await message.delete()
            except Exception as e:
                logger.error(f"Error deleting message {message.message_id}: {e}")
        
        # حذف پیام هدف
        try:
            await context.bot.delete_message(chat_id, target_message_id)
        except Exception as e:
            logger.error(f"Error deleting target message: {e}")
            
    except Exception as e:
        logger.error(f"Error in purge command: {e}")
        # We cannot reply here because the command message is deleted.
        # Consider sending a new message if this is critical.
        # await context.bot.send_message(chat_id, f"❌ خطا در حذف پیام‌ها: {e}")

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """سنجاق کردن پیام با ریپلای روی آن."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for pin command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    # بررسی اینکه آیا پیام ریپلای شده است
    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ لطفاً روی پیامی که می‌خواهید سنجاق کنید ریپلای کنید.")
        return
    
    try:
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=update.message.reply_to_message.message_id,
            disable_notification=True
        )
        
        await update.message.reply_text("📌 پیام با موفقیت سنجاق شد.")
        
    except Exception as e:
        logger.error(f"Error pinning message: {e}")
        await update.message.reply_text(f"❌ خطا در سنجاق کردن پیام: {e}")

async def unpin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """درآوردن پیام از حالت سنجاق شده."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for unpin command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    try:
        await context.bot.unpin_chat_message(chat_id=chat_id)
        await update.message.reply_text("📌 پیام با موفقیت از حالت سنجاق درآمد.")
        
    except Exception as e:
        logger.error(f"Error unpinning message: {e}")
        await update.message.reply_text(f"❌ خطا در درآوردن پیام از حالت سنجاق: {e}")

async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش قوانین گروه."""
    chat_id = update.effective_chat.id
    
    # دریافت قوانین گروه از دیتابیس
    group_rules = data_manager.DATA.get('group_rules', {}).get(str(chat_id), "قوانین گروه هنوز تنظیم نشده است.")
    
    try:
        await update.message.reply_text(
            f"📋 **قوانین گروه:**\n\n{group_rules}",
            parse_mode='Markdown'
        )
    except TelegramError as e:
        logger.error(f"Failed to send rules message: {e}")

async def setrules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تنظیم قوانین جدید گروه."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # بررسی اینکه آیا کاربر ادمین است
    try:
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        if chat_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌توانند از این دستور استفاده کنند.")
            return
    except TelegramError as e:
        logger.error(f"Failed to check admin status for setrules command: {e}")
        await update.message.reply_text("❌ خطا در بررسی سطح دسترسی شما.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ لطفاً قوانین جدید را بنویسید.\nمثال: `/setrules 1. احترام به دیگران\n2. ارسال اسپم ممنوع`")
        return
    
    new_rules = " ".join(context.args)
    
    # ذخیره قوانین جدید در دیتابیس
    if 'group_rules' not in data_manager.DATA:
        data_manager.DATA['group_rules'] = {}
    
    data_manager.DATA['group_rules'][str(chat_id)] = new_rules
    data_manager.save_data()
    
    try:
        await update.message.reply_text("✅ قوانین گروه با موفقیت به‌روزرسانی شد.")
    except TelegramError as e:
        logger.error(f"Failed to send setrules confirmation: {e}")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """نمایش اطلاعات گروه."""
    chat = update.effective_chat
    
    # دریافت اطلاعات گروه
    try:
        chat_info = await context.bot.get_chat(chat.id)
    except TelegramError as e:
        logger.error(f"Failed to get chat info: {e}")
        await update.message.reply_text("❌ خطا در دریافت اطلاعات گروه.")
        return
    
    # تعداد اعضا
    try:
        member_count = await chat.get_member_count()
    except Exception:
        member_count = "نامشخص"
    
    # دریافت اطلاعات ادمین‌ها با مدیریت خطا
    admin_list = "نامشخص (ربات باید ادمین باشد)"
    try:
        administrators = await context.bot.get_chat_administrators(chat.id)
        admin_list = "\n".join([f"• {admin.user.mention_html()}" for admin in administrators])
    except TelegramError as e:
        logger.warning(f"Could not fetch chat administrators (bot might not be admin): {e}")
    
    # استفاده از getattr برای دسترسی امن به ویژگی description
    description = getattr(chat_info, 'description', None)
    
    info_text = (
        f"ℹ️ **اطلاعات گروه:**\n\n"
        f"📝 **نام:** {chat.title}\n"
        f"🆔 **آیدی:** `{chat.id}`\n"
        f"👥 **تعداد اعضا:** {member_count}\n"
        f"📝 **توضیحات:** {description or 'ندارد'}\n\n"
        f"👑 **لیست ادمین‌ها:**\n{admin_list}"
    )
    
    try:
        await update.message.reply_text(info_text, parse_mode='HTML')
    except TelegramError as e:
        logger.error(f"Failed to send info message: {e}")

# --- مدیریت خطای عمومی ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Errors caused by Updates."""
    logger.error('Exception while handling an update: %s', context.error)

def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN not set in environment variables!")
        return

    application = (
        Application.builder()
        .token(token)
        .concurrent_updates(True)
        .build()
    )

    # ثبت مدیریت خطای عمومی
    application.add_error_handler(error_handler)

    # هندلرهای دستورات عمومی
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # هندلرهای دستورات مدیریت گروه
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    application.add_handler(CommandHandler("warn", warn_command))
    application.add_handler(CommandHandler("del", del_command))
    application.add_handler(CommandHandler("purge", purge_command))
    application.add_handler(CommandHandler("pin", pin_command))
    application.add_handler(CommandHandler("unpin", unpin_command))
    application.add_handler(CommandHandler("rules", rules_command))
    application.add_handler(CommandHandler("setrules", setrules_command))
    application.add_handler(CommandHandler("info", info_command))
    
    # هندلر پیام‌ها
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # راه‌اندازی و ثبت هندلرهای پنل ادمین
    admin_panel.setup_admin_handlers(application)

    port = int(os.environ.get("PORT", 8443))
    webhook_url = os.environ.get("RENDER_EXTERNAL_URL") + "/webhook"
    
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
        url_path="webhook"
    )

if __name__ == "__main__":
    main()
