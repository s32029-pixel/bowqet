import asyncio
import logging
import sys
from os import getenv
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message as MessageType
from aiogram.types import BusinessMessagesDeleted, InlineKeyboardButton, InlineKeyboardMarkup
import db
from db.models.message import Message
from db.models.file import File
from sqlmodel import Session as SQLSession
from sqlmodel import select
from pathlib import Path
from uuid import uuid4
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram.types import FSInputFile

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()

@dp.message(CommandStart())
async def command_start_handler(message: MessageType) -> None:
    """
    Handle the /start command with a welcome message and buttons.
    """
    bot_username = (await message.bot.get_me()).username
    welcome_text = f"""✨ <b>Этот бот создан, чтобы облегчить вам жизнь в Telegram</b> ✨

🛡️ <b>Основные функции:</b>

• Я присылаю уведомления, когда собеседник удаляет или редактирует сообщения.
• Могу сохранять сгорающие фото, голосовые и видео.

📋 <b>Чтобы подключить бота:</b>
Скопируйте username бота: <code>@{bot_username}</code> и следуйте инструкции ниже.

🔌 <b>Статус подключения:</b> ✅ Подключен"""
    
    
    # Create inline keyboard with two buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Инструкция", url="https://teletype.in/@egorxuligan/IzyArFPmEV_")],
        [InlineKeyboardButton(text="Проверить разрешения", callback_data="check_permissions")]
    ])
    
    await message.answer(welcome_text, reply_markup=keyboard)



# Store active business connections
active_connections = {}

@dp.business_connection()
async def handle_business_connection(connection):
    """
    Handle business connection events (connect/disconnect).
    """
    if connection.is_enabled:
        # Bot connected to business account
        active_connections[connection.id] = connection.user_chat_id
        
        # Send connection notification
        welcome_text = """🎉 <b>Бот успешно подключен к вашему бизнес аккаунту!</b>

🛡️ <b>Ваши преимущества:</b>

⚠️ Защита от мошенников - предупреждаем о вредоносных ботах в реальном времени
💨 Мгновенные уведомления - узнаете сразу, если кто-то удалил или отредактировал сообщение
🔍 Эксклюзивные функции - уникальные инструменты для работы с сообщениями

📋 <b>Что умеет бот:</b>
• Сохранять сгорающие фото, видео, голосовые сообщения
• Уведомлять об удалении и редактировании сообщений
• Работать с любыми типами медиафайлов

🔧 <b>Рекомендации:</b>
Проверьте разрешения в настройках Telegram Business для корректной работы бота."""
        
        await connection.bot.send_message(chat_id=connection.user_chat_id, text=welcome_text)
    else:
        # Bot disconnected from business account
        if connection.id in active_connections:
            user_chat_id = active_connections[connection.id]
            del active_connections[connection.id]
            
            # Send disconnection notification
            disconnect_text = """🚫 <b>Бот был отключён от вашего бизнес аккаунта</b> 😔
            
⚠️ <b>Вы потеряли защиту от удаления сообщений!</b>

🔧 <b>Что делать:</b>
1. Переподключите бота к вашему бизнес аккаунту
2. Проверьте настройки разрешений
3. Убедитесь, что бот имеет доступ к сообщениям

💡 <b>Совет:</b> Используйте официальное SaveBot для надежной защиты!"""
            
            await connection.bot.send_message(chat_id=user_chat_id, text=disconnect_text)


@dp.deleted_business_messages()
async def handle_business_message_deleted(deleted_messages: BusinessMessagesDeleted):
    """
    Handles the event when messages are deleted from a business account.
    """
    print(f"Messages deleted in business connection {deleted_messages.business_connection_id}")
    print(f"Chat ID: {deleted_messages.chat.id}")
    print(f"Deleted message IDs: {deleted_messages.message_ids}")
    # You can add your custom logic here, e.g., logging, updating a database, etc.
    session = SQLSession(db.engine)
    business_connection = await deleted_messages.bot.get_business_connection(deleted_messages.business_connection_id)
    user_chat_id = business_connection.user_chat_id

    for message_id in deleted_messages.message_ids:
        msg = session.exec(select(Message).where(Message.chat_id == deleted_messages.chat.id).where(Message.id == message_id)).first()

        if msg is None:
            continue

        if msg.type == "photos":
            files = session.exec(select(File).where(File.message_id == msg.id)).fetchall()
            
            text = [
                "📸 <b>Удаленные фото</b>",
                f"👤 Удалил @{msg.from_username}",
                "",
                "📝 <b>Описание:</b>",
                msg.content
            ]
            text = '\n'.join(text)

            media_group = MediaGroupBuilder(caption=text)

            for file_name in files:
                # print(file.file_name)
                file_path = Path('.').joinpath("media").joinpath(file_name.file_name)
                file = FSInputFile(file_path)
                # await deleted_messages.bot.send_photo(chat_id=user_chat_id, caption="Удаленные фото", photo=file)
                media_group.add(type="photo", media=file)

            await deleted_messages.bot.send_media_group(chat_id=user_chat_id, media=media_group.build())
                
        elif msg.type == "video":
            msg = session.exec(select(Message).where(Message.chat_id == deleted_messages.chat.id).where(Message.id == message_id)).first()
            if msg is None:
                continue
            files = session.exec(select(File).where(File.message_id == msg.id)).fetchall()
            if not files:
                continue
            # Use the first file if multiple files exist
            fileDb = files[0]
            
            text = [
                "🎥 <b>Удаленное видео</b>",
                f"👤 Удалил @{msg.from_username}",
                "",
                "📝 <b>Описание:</b>",
                msg.content
            ]
            text = '\n'.join(text)

            file_path = Path('.').joinpath("media").joinpath(fileDb.file_name)
            file = FSInputFile(file_path)
            
            await deleted_messages.bot.send_video(chat_id=user_chat_id, video=file, caption=text)
        
        elif msg.type == "video_note":
            msg = session.exec(select(Message).where(Message.chat_id == deleted_messages.chat.id).where(Message.id == message_id)).first()
            if msg is None:
                continue
            fileDb = session.exec(select(File).where(File.message_id == msg.id)).first()
            
            text = [
                "🎬 <b>Удаленный кружочек ⬆️</b>",
                f"👤 Удалил @{msg.from_username}",
            ]
            text = '\n'.join(text)

            file_path = Path('.').joinpath("media").joinpath(fileDb.file_name)
            file = FSInputFile(file_path)
            
            await deleted_messages.bot.send_video_note(chat_id=user_chat_id, video_note=file)
            await deleted_messages.bot.send_message(chat_id=user_chat_id, text=text)

        elif msg.type == "audio":
            msg = session.exec(select(Message).where(Message.chat_id == deleted_messages.chat.id).where(Message.id == message_id)).first()
            if msg is None:
                continue
            fileDb = session.exec(select(File).where(File.message_id == msg.id)).first()
            
            text = [
                "📢 <b>Удаленное гс</b>",
                f"👤 Удалил @{msg.from_username}",
            ]
            text = '\n'.join(text)

            file_path = Path('.').joinpath("media").joinpath(fileDb.file_name)
            file = FSInputFile(file_path)
            
            await deleted_messages.bot.send_audio(chat_id=user_chat_id, audio=file, caption=text)
        
        elif msg.type == "document":
            msg = session.exec(select(Message).where(Message.chat_id == deleted_messages.chat.id).where(Message.id == message_id)).first()
            if msg is None:
                continue
            fileDb = session.exec(select(File).where(File.message_id == msg.id)).first()
            
            text = [
                "📁 <b>Удаленный файл</b>",
                f"👤 Удалил @{msg.from_username}",
                "",
                "📝 <b>Описание:</b>",
                msg.content
            ]
            text = '\n'.join(text)

            file_path = Path('.').joinpath("media").joinpath(fileDb.file_name)
            file = FSInputFile(file_path)
            
            await deleted_messages.bot.send_document(chat_id=user_chat_id, document=file, caption=text)
        
        elif msg.type == "text":
            msg = session.exec(select(Message).where(Message.chat_id == deleted_messages.chat.id).where(Message.id == message_id)).first()
            if msg is None:
                continue
            
            text = [
                "💬 <b>Удаленное сообщение</b>",
                f"👤 Удалил @{msg.from_username}",
                "",
                "📝 <b>Сообщение:</b>",
                msg.content
            ]
            text = '\n'.join(text)

            await deleted_messages.bot.send_message(chat_id=user_chat_id, text=text)



@dp.business_message()
async def handle_business_message(message: MessageType):
    # print(message)
    # file = await message.bot.get_file(message.photo[0].file_id)
    session = SQLSession(db.engine)
    business_connection = await message.bot.get_business_connection(message.business_connection_id)
    user_chat_id = business_connection.user_chat_id

    if message.reply_to_message:
        reply_to = message.reply_to_message

        # if reply_to.has_protected_content:
        if reply_to.photo:
            file_name = str(uuid4())
            file_name = Path('.').joinpath("media").joinpath(file_name+".jpg")
            photo = reply_to.photo[::-1][0]
            fl = await message.bot.get_file(photo.file_id)

            await message.bot.download_file(fl.file_path, file_name)
            await message.bot.send_photo(chat_id=user_chat_id, photo=FSInputFile(file_name))
            Path.unlink(file_name)
        
        elif reply_to.video:
            file_name = str(uuid4())
            file_name = Path('.').joinpath("media").joinpath(file_name+".mp4")
            fl = await message.bot.get_file(reply_to.video.file_id)

            await message.bot.download_file(fl.file_path, file_name)
            await message.bot.send_video(chat_id=user_chat_id, video=FSInputFile(file_name))
            Path.unlink(file_name)
        
        elif reply_to.video_note:
            file_name = str(uuid4())
            file_name = Path('.').joinpath("media").joinpath(file_name+".mp4")
            fl = await message.bot.get_file(reply_to.video_note.file_id)

            await message.bot.download_file(fl.file_path, file_name)
            await message.bot.send_video_note(chat_id=user_chat_id, video_note=FSInputFile(file_name))
            Path.unlink(file_name)
        
        elif reply_to.voice:
            file_name = str(uuid4())
            file_name = Path('.').joinpath("media").joinpath(file_name+".ogg")
            fl = await message.bot.get_file(reply_to.voice.file_id)

            await message.bot.download_file(fl.file_path, file_name)
            await message.bot.send_audio(chat_id=user_chat_id, audio=FSInputFile(file_name))
            Path.unlink(file_name)

    elif message.photo:
        msg = Message(chat_id=message.chat.id, id=message.message_id, type="photos", content=message.caption if message.caption else "", from_username=message.from_user.username if message.from_user.username else "Нету")
        session.add(msg)

        for photo in message.photo[::-1]:
            file_name = str(uuid4())
            fl = await message.bot.get_file(photo.file_id)
            # await photo.download(destination=Path("media").with_name(file_name+".jpg"))
            await message.bot.download_file(fl.file_path, Path('.').joinpath("media").joinpath(file_name+".jpg"))

            file = File(file_name=file_name+".jpg", message_id=message.message_id)
            session.add(file)

            session.commit()

    elif message.video:
        msg = Message(chat_id=message.chat.id, id=message.message_id, type="video", content=message.caption if message.caption else "", from_username=message.from_user.username if message.from_user.username else "Нету")
        session.add(msg)

        file_name = str(uuid4())
        fl = await message.bot.get_file(message.video.file_id)
        # await photo.download(destination=Path("media").with_name(file_name+".jpg"))
        await message.bot.download_file(fl.file_path, Path('.').joinpath("media").joinpath(file_name+".mp4"))

        file = File(file_name=file_name+".mp4", message_id=message.message_id)
        session.add(file)

        session.commit()

    elif message.video_note:
        msg = Message(chat_id=message.chat.id, id=message.message_id, type="video_note", content=message.caption if message.caption else "", from_username=message.from_user.username if message.from_user.username else "Нету")
        session.add(msg)

        file_name = str(uuid4())
        fl = await message.bot.get_file(message.video_note.file_id)
        # await photo.download(destination=Path("media").with_name(file_name+".jpg"))
        await message.bot.download_file(fl.file_path, Path('.').joinpath("media").joinpath(file_name+".mp4"))

        file = File(file_name=file_name+".mp4", message_id=message.message_id)
        session.add(file)

        session.commit()

    elif message.voice:
        msg = Message(chat_id=message.chat.id, id=message.message_id, type="audio", content=message.caption if message.caption else "", from_username=message.from_user.username if message.from_user.username else "Нету")
        session.add(msg)

        file_name = str(uuid4())
        fl = await message.bot.get_file(message.voice.file_id)
        # await photo.download(destination=Path("media").with_name(file_name+".jpg"))
        await message.bot.download_file(fl.file_path, Path('.').joinpath("media").joinpath(file_name+".ogg"))

        file = File(file_name=file_name+".ogg", message_id=message.message_id)
        session.add(file)

        session.commit()

    elif message.document:
        msg = Message(chat_id=message.chat.id, id=message.message_id, type="document", content=message.caption if message.caption else "", from_username=message.from_user.username if message.from_user.username else "Нету")
        session.add(msg)

        file_name = str(uuid4())
        fl = await message.bot.get_file(message.document.file_id)
        # await photo.download(destination=Path("media").with_name(file_name+".jpg"))
        await message.bot.download_file(fl.file_path, Path('.').joinpath("media").joinpath(file_name+"."+message.document.mime_type.split('/')[1]))

        file = File(file_name=file_name+"."+message.document.mime_type.split('/')[1], message_id=message.message_id)
        session.add(file)

        session.commit()

    else:
        msg = Message(chat_id=message.chat.id, id=message.message_id, type="text", content=message.text, from_username=message.from_user.username if message.from_user.username else "Нету")
        session.add(msg)
        session.commit()
        

@dp.edited_business_message()
async def handle_edited_business_message(message: MessageType):
    """
    Handle edited business messages.
    """
    session = SQLSession(db.engine)
    business_connection = await message.bot.get_business_connection(message.business_connection_id)
    user_chat_id = business_connection.user_chat_id
    
    # Get the original message from the database
    original_msg = session.exec(select(Message).where(Message.chat_id == message.chat.id).where(Message.id == message.message_id)).first()
    
    if original_msg is None:
        return
    
    # Create a message with the original and edited content
    text = [
        "✏️ <b>Отредактированное сообщение</b>",
        f"👤 Отправитель: @{original_msg.from_username}",
        "",
        "📝 <b>Оригинальное сообщение:</b>",
        original_msg.content,
        "",
        "🔄 <b>Отредактированное сообщение:</b>",
        message.text or message.caption or "❌ Пустое сообщение"
    ]
    text = '\n'.join(text)
    
    await message.bot.send_message(chat_id=user_chat_id, text=text)

    # print(file.file_path)

@dp.callback_query(lambda c: c.data == 'check_permissions')
async def check_permissions_callback(callback_query):
    """
    Handle the check permissions button callback.
    """
    # Here you would implement the actual permission checking logic
    # For now, we'll just send a message with the required permissions
    permissions_text = """🔐 <b>Необходимые разрешения для корректной работы бота:</b>
    
1. <b>Доступ к сообщениям</b> - для сохранения удаленных сообщений
2. <b>Доступ к медиа файлам</b> - для сохранения фото/видео/аудио
3. <b>Уведомления</b> - для отправки уведомлений о удаленных сообщениях
    
📸 <b>Проверьте, что в настройках бизнеса установлены галочки:</b>
• Уведомления о новых сообщениях
• Уведомления об удалении сообщений
• Уведомления о редактировании сообщений
• Доступ к медиафайлам"""
    
    await callback_query.message.answer(permissions_text)
    await callback_query.answer()


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    db.init()
    asyncio.run(main())