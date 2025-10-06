import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import time
import random
import threading
import requests
import json
import os
from datetime import datetime, timedelta

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = "8260791120:AAFoDJDs9Bzthp3MB_jJ1kkjEprTLxWt3fg"
PHOTO_PATH = r"C:\Users\никита\Documents\Майнер\result.jpg"
WIN_PHOTO_PATH = r"C:\Users\никита\Documents\Майнер\win.jpg"
LOSE_PHOTO_PATH = r"C:\Users\никита\Documents\Майнер\lose.jpg"
CHANNEL_ID = "-1003120338447"  # Твой канал
SEND_BOT_TOKEN = "428680:AAyTMpIyLvcHY1qdZgclt1pumgUxpNd5U0z"
ADMIN_ID = 6524423095  # Твой айди

# ===== ИНИЦИАЛИЗАЦИЯ БОТА =====
bot = telebot.TeleBot(BOT_TOKEN)

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
user_status = {}
user_state = {}
pending_invoices = {}
game_sessions = {}


def init_db():
    if os.path.exists('casino.db'):
        os.remove('casino.db')

    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            balance REAL DEFAULT 0.0,
            tg_id INTEGER UNIQUE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            invoice_url TEXT,
            send_invoice_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_type TEXT,
            bet_amount REAL,
            win_amount REAL,
            result TEXT,
            game_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


def get_or_create_user(tg_id, username):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('SELECT user_id FROM users WHERE tg_id = ?', (tg_id,))
    result = cursor.fetchone()

    if not result:
        cursor.execute('INSERT INTO users (username, tg_id) VALUES (?, ?)', (username, tg_id))
        conn.commit()
        cursor.execute('SELECT user_id FROM users WHERE tg_id = ?', (tg_id,))
        result = cursor.fetchone()

    conn.close()
    return result[0]


def get_user_data(tg_id):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, balance FROM users WHERE tg_id = ?', (tg_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'user_id': result[0],
            'username': result[1],
            'balance': result[2]
        }
    return None


def update_balance(tg_id, amount):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE tg_id = ?', (amount, tg_id))
    conn.commit()
    conn.close()


def save_invoice(user_id, amount, invoice_url, send_invoice_id):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO invoices (user_id, amount, invoice_url, send_invoice_id) VALUES (?, ?, ?, ?)',
        (user_id, amount, invoice_url, send_invoice_id)
    )
    conn.commit()
    conn.close()


def mark_invoice_paid(send_invoice_id):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, amount FROM invoices WHERE send_invoice_id = ?', (send_invoice_id,))
    result = cursor.fetchone()

    if result:
        user_id, amount = result
        cursor.execute('UPDATE invoices SET status = ? WHERE send_invoice_id = ?', ('paid', send_invoice_id))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()

        cursor.execute('SELECT tg_id FROM users WHERE user_id = ?', (user_id,))
        tg_id_result = cursor.fetchone()
        conn.close()
        return tg_id_result[0] if tg_id_result else None
    conn.close()
    return None


def save_game_result(user_id, game_type, bet_amount, win_amount, result, game_data=None):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO games (user_id, game_type, bet_amount, win_amount, result, game_data) VALUES (?, ?, ?, ?, ?, ?)',
        (user_id, game_type, bet_amount, win_amount, result, json.dumps(game_data) if game_data else None)
    )
    conn.commit()
    conn.close()


def create_send_invoice(amount, description):
    try:
        url = "https://pay.crypt.bot/api/createInvoice"

        headers = {
            "Crypto-Pay-API-Token": SEND_BOT_TOKEN,
            "Content-Type": "application/json"
        }

        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": description,
            "paid_btn_name": "viewItem",
            "paid_btn_url": "https://t.me/SonCasinoBet_bot",
            "payload": f"deposit_{int(time.time())}",
            "allow_comments": True,
            "allow_anonymous": False
        }

        response = requests.post(url, headers=headers, json=payload)
        result = response.json()

        if result.get('ok'):
            invoice_data = result['result']
            return {
                'invoice_url': invoice_data['pay_url'],
                'invoice_id': invoice_data['invoice_id']
            }
        else:
            print(f"❌ Ошибка CryptoBot API: {result}")
            return None
    except Exception as e:
        print(f"❌ Ошибка создания счета: {e}")
        return None


def check_invoice_status(invoice_id):
    try:
        url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"

        headers = {
            "Crypto-Pay-API-Token": SEND_BOT_TOKEN
        }

        response = requests.get(url, headers=headers)
        result = response.json()

        if result.get('ok') and result['result']['items']:
            return result['result']['items'][0]['status']
        return 'active'
    except Exception as e:
        print(f"❌ Ошибка проверки счета: {e}")
        return 'active'


def check_invoice_payments():
    while True:
        try:
            current_time = time.time()
            processed_invoices = []

            for send_invoice_id, invoice_data in list(pending_invoices.items()):
                if current_time - invoice_data['created_at'] > 900:
                    processed_invoices.append(send_invoice_id)
                    continue

                status = check_invoice_status(send_invoice_id)

                if status == 'paid':
                    tg_id = mark_invoice_paid(send_invoice_id)
                    if tg_id:
                        update_balance(tg_id, invoice_data['amount'])
                        user_data = get_user_data(tg_id)

                        success_message = f"""
✅ **ПЛАТЕЖ ПОДТВЕРЖДЕН!**

💳 Сумма: ${invoice_data['amount']:.2f}
💎 Новый баланс: ${user_data['balance']:.2f}

🎰 Удачи в играх!"""
                        bot.send_message(tg_id, success_message)

                    processed_invoices.append(send_invoice_id)

            for send_invoice_id in processed_invoices:
                if send_invoice_id in pending_invoices:
                    del pending_invoices[send_invoice_id]

        except Exception as e:
            print(f"❌ Ошибка в проверке счетов: {e}")

        time.sleep(10)


def show_main_menu(message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton("🎮 Игры"),
        KeyboardButton("💳 Кошелек"),
        KeyboardButton("🆘 Поддержка"),
        KeyboardButton("📢 Канал")
    ]
    keyboard.add(*buttons)

    bot.send_message(
        message.chat.id,
        "🎰 Добро пожаловать в Son Casino!\n\n🍀 Удачи в ставках! Выберите раздел:",
        reply_markup=keyboard
    )


def show_wallet(message):
    user_data = get_user_data(message.chat.id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки данных")
        return

    username = message.from_user.username or "Не указан"

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("💵 Пополнить", callback_data="deposit"),
        InlineKeyboardButton("💰 Вывести", callback_data="withdraw")
    ]
    keyboard.add(*buttons)

    wallet_text = f"""💼 **Ваш кошелек**

💰 Баланс: ${user_data['balance']:.2f}
🆔 ID: {user_data['user_id']}
👤 Ник: @{username}"""

    bot.send_message(message.chat.id, wallet_text, reply_markup=keyboard)


def ask_deposit_amount(message):
    user_state[message.chat.id] = "waiting_deposit_amount"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_wallet"))

    bot.send_message(
        message.chat.id,
        "💵 Введите сумму для пополнения\n\nМинимум: $0.02\nМаксимум: $30.00\n\nПример: 5.50",
        reply_markup=keyboard
    )


def process_deposit_request(user_id, tg_id, amount, username):
    description = f"Пополнение баланса Son Casino на ${amount:.2f}"
    invoice_data = create_send_invoice(amount, description)

    if invoice_data:
        invoice_url = invoice_data['invoice_url']
        send_invoice_id = str(invoice_data['invoice_id'])

        save_invoice(user_id, amount, invoice_url, send_invoice_id)

        pending_invoices[send_invoice_id] = {
            'user_id': user_id,
            'tg_id': tg_id,
            'amount': amount,
            'username': username,
            'created_at': time.time(),
            'invoice_url': invoice_url
        }

        deposit_text = f"""💳 **СЧЕТ ДЛЯ ОПЛАТЫ**

💰 Сумма: ${amount:.2f} USDT
🔗 Ссылка: {invoice_url}

📋 **Инструкция:**
1. Нажмите на ссылку выше
2. Оплатите счет в USDT
3. Баланс пополнится автоматически

⏱ Счет действителен 15 минут
📞 Поддержка: @support"""

        bot.send_message(tg_id, deposit_text)
    else:
        bot.send_message(tg_id, "❌ Ошибка создания счета. Попробуйте позже.")


def show_games_menu(message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton("🎲 ЧЕТ/НЕЧЕТ", callback_data="game_even_odd"),
        InlineKeyboardButton("❓ Как играть?", url="https://t.me/c/3120338447/19"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    ]
    keyboard.add(*buttons)

    games_text = """
🎮 **ИГРОВОЙ ЗАЛ**

🎲 **ЧЕТ/НЕЧЕТ**
• Коэффициент: 1.8x
• Минимальная ставка: $0.02
• Максимальная ставка: $30.00

🎯 **Правила:**
• Бросок виртуального кубика (1-6)
• ЧЕТ: 2, 4, 6
• НЕЧЕТ: 1, 3, 5
• Выигрыш: ставка × 1.8
"""

    bot.send_message(message.chat.id, games_text, reply_markup=keyboard)


def ask_bet_amount(message, game_type):
    user_state[message.chat.id] = f"waiting_bet_{game_type}"

    user_data = get_user_data(message.chat.id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки данных")
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_games"))

    bet_info = f"""
💰 **ВВЕДИТЕ СУММУ СТАВКИ**

💸 Минимум: $0.02
💰 Максимум: $30.00
💎 Ваш баланс: ${user_data['balance']:.2f}

📝 Пример: 1.50 или 5
"""

    bot.send_message(message.chat.id, bet_info, reply_markup=keyboard)


def ask_even_odd_choice(message, bet_amount):
    user_state[message.chat.id] = f"waiting_choice_{bet_amount}"

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🔵 ЧЕТ", callback_data=f"choice_even_{bet_amount}"),
        InlineKeyboardButton("🔴 НЕЧЕТ", callback_data=f"choice_odd_{bet_amount}"),
        InlineKeyboardButton("🔙 Назад", callback_data=f"back_bet_{bet_amount}")
    ]
    keyboard.add(*buttons[:2], buttons[2])

    bot.send_message(
        message.chat.id,
        f"🎲 **Ставка: ${bet_amount:.2f}**\n\nВыберите вариант:",
        reply_markup=keyboard
    )


def process_even_odd_game(user_id, tg_id, username, bet_amount, choice):
    user_data = get_user_data(tg_id)

    # Проверяем баланс
    if user_data['balance'] < bet_amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    # Снимаем ставку
    update_balance(tg_id, -bet_amount)

    # Отправляем сообщение о запуске ставки в канал
    try:
        channel_message = f"🚀 Ставка запущена\n\n👤 <i>{username}</i>\n💰 Ставка: ${bet_amount:.2f}\n🎮 Игра: Чет/Нечет\n🎁 <b>Выигрыш: ${bet_amount * 1.8:.2f}</b>"
        sent_message = bot.send_message(CHANNEL_ID, channel_message, parse_mode='HTML')

        # Цитируем это сообщение в следующем
        time.sleep(1)
        bot.send_message(CHANNEL_ID, "🎲", reply_to_message_id=sent_message.message_id)

    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")

    # Генерируем результат (1-6 как на кубике)
    time.sleep(2)
    dice_result = random.randint(1, 6)  # Теперь любое число от 1 до 6
    is_even = dice_result % 2 == 0

    # Определяем победу
    win = (choice == "even" and is_even) or (choice == "odd" and not is_even)

    if win:
        # ПОБЕДА
        win_amount = round(bet_amount * 1.8, 2)
        update_balance(tg_id, win_amount)
        save_game_result(user_id, "even_odd", bet_amount, win_amount, "win", {"dice": dice_result, "choice": choice})

        # Сообщение о победе в канал
        try:
            win_channel_text = f"🎉 Поздравляю с победой! Вы выиграли <b>${win_amount:.2f}</b>\n\n💎 Ваши монеты начислены вам в бота"
            keyboard = InlineKeyboardMarkup()
            buttons = [
                InlineKeyboardButton("❓ Как играть?", url="https://t.me/c/3120338447/19"),
                InlineKeyboardButton("🎯 Поставить ставку", url="https://t.me/SonCasinoBet_bot?start=play")
            ]
            keyboard.add(*buttons)

            with open(WIN_PHOTO_PATH, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=win_channel_text, reply_markup=keyboard, parse_mode='HTML')
        except Exception as e:
            print(f"Ошибка отправки победы в канал: {e}")

        # Сообщение пользователю
        bot.send_message(
            tg_id,
            f"🎉 Поздравляю вы победили!\n\n💰 Выигрыш: ${win_amount:.2f}\n💎 Начислено на ваш баланс"
        )

    else:
        # ПРОИГРЫШ - просто снимаем ставку, НЕ умножаем
        save_game_result(user_id, "even_odd", bet_amount, 0, "lose", {"dice": dice_result, "choice": choice})

        # Сообщение о проигрыше в канал
        try:
            lose_channel_text = "💔 К сожалению, вы проиграли, но не расстраивайся\n\n🎯 Поставь еще - удача на твоей стороне!"
            keyboard = InlineKeyboardMarkup()
            buttons = [
                InlineKeyboardButton("❓ Как играть?", url="https://t.me/c/3120338447/19"),
                InlineKeyboardButton("🎯 Поставить ставку", url="https://t.me/SonCasinoBet_bot?start=play")
            ]
            keyboard.add(*buttons)

            with open(LOSE_PHOTO_PATH, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=lose_channel_text, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка отправки проигрыша в канал: {e}")

        # Сообщение пользователю
        bot.send_message(
            tg_id,
            f"💔 К сожалению, вы проиграли ${bet_amount:.2f}\n\n🎯 Попробуйте еще раз - удача на вашей стороне!"
        )


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    # Проверяем параметр start=play
    if message.text and 'play' in message.text:
        show_games_menu(message)
        return

    user_id = get_or_create_user(chat_id, message.from_user.username)

    if user_status.get(chat_id):
        show_main_menu(message)
        return

    try:
        with open(PHOTO_PATH, 'rb') as photo:
            keyboard = InlineKeyboardMarkup(row_width=2)
            buttons = [
                InlineKeyboardButton("📄 Пользовательское соглашение",
                                     url="https://telegra.ph/Son-Casino--Polzovatelskoe-soglashenie-10-04"),
                InlineKeyboardButton("❌ Отказаться", callback_data="decline"),
                InlineKeyboardButton("✅ Принять", callback_data="accept")
            ]
            keyboard.add(*buttons)

            bot.send_photo(
                chat_id,
                photo,
                caption="👋 Привет! Я Son Bet\n\n📝 Настоятельно рекомендую прочитать Пользовательское соглашение",
                reply_markup=keyboard
            )
    except Exception as e:
        bot.send_message(
            chat_id,
            "👋 Привет! Я Son Bet\n\n📝 Настоятельно рекомендую прочитать Пользовательское соглашение",
            reply_markup=keyboard
        )


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id

    if call.data == "decline":
        bot.edit_message_caption(
            chat_id=chat_id,
            message_id=call.message.message_id,
            caption="❌ Вы отказались от пользовательского соглашения\n\n🚫 Доступ запрещен\n\n📝 Введите /start если готовы передумать"
        )

    elif call.data == "accept":
        user_status[chat_id] = True
        bot.delete_message(chat_id, call.message.message_id)
        show_main_menu(call.message)

    elif call.data == "deposit":
        ask_deposit_amount(call.message)

    elif call.data == "withdraw":
        user_data = get_user_data(chat_id)
        if user_data and user_data['balance'] >= 1.0:
            bot.send_message(chat_id, "💰 Вывод средств\n\nМинимальная сумма: $1.00\nСвяжитесь с поддержкой: @support")
        else:
            bot.send_message(chat_id, "❌ Недостаточно средств\n\nМинимум для вывода: $1.00")

    elif call.data == "back_to_wallet":
        show_wallet(call.message)

    elif call.data == "back_to_menu":
        show_main_menu(call.message)

    elif call.data == "back_to_games":
        show_games_menu(call.message)

    elif call.data.startswith("back_bet_"):
        bet_amount = float(call.data.split("_")[2])
        ask_bet_amount(call.message, "even_odd")

    elif call.data == "game_even_odd":
        ask_bet_amount(call.message, "even_odd")

    elif call.data.startswith("choice_even_"):
        bet_amount = float(call.data.split("_")[2])
        process_even_odd_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            bet_amount,
            "even"
        )

    elif call.data.startswith("choice_odd_"):
        bet_amount = float(call.data.split("_")[2])
        process_even_odd_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            bet_amount,
            "odd"
        )


@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id

    if not user_status.get(chat_id):
        return

    # Проверяем, не нажата ли кнопка (если сообщение начинается с эмодзи - это кнопка)
    if message.text and any(char in message.text for char in ['🎮', '💳', '🆘', '📢']):
        return

    # Обработка депозита
    if user_state.get(chat_id) == "waiting_deposit_amount":
        try:
            amount = float(message.text)
            if amount < 0.02:
                bot.send_message(chat_id, "❌ Минимум $0.02")
            elif amount > 30:
                bot.send_message(chat_id, "❌ Максимум $30.00")
            else:
                user_data = get_user_data(chat_id)
                if user_data:
                    process_deposit_request(user_data['user_id'], chat_id, amount,
                                            message.from_user.username or 'Unknown')
                user_state[chat_id] = None
        except ValueError:
            bot.send_message(chat_id, "❌ Введите число (например: 5.50)")
        return

    # Обработка ставки для Чет/Нечет
    if user_state.get(chat_id) and user_state[chat_id].startswith("waiting_bet_even_odd"):
        try:
            bet_amount = float(message.text)
            if bet_amount < 0.02:
                bot.send_message(chat_id, "❌ Минимум $0.02")
            elif bet_amount > 30:
                bot.send_message(chat_id, "❌ Максимум $30.00")
            else:
                user_data = get_user_data(chat_id)
                if user_data and user_data['balance'] >= bet_amount:
                    ask_even_odd_choice(message, bet_amount)
                    user_state[chat_id] = None
                else:
                    bot.send_message(chat_id, "❌ Недостаточно средств на балансе")
        except ValueError:
            bot.send_message(chat_id, "❌ Введите число (например: 1.50)")
        return

    text = message.text
    if text == "🎮 Игры":
        show_games_menu(message)
    elif text == "💳 Кошелек":
        show_wallet(message)
    elif text == "🆘 Поддержка":
        bot.send_message(chat_id, "🆘 Поддержка: @support")
    elif text == "📢 Канал":
        bot.send_message(chat_id, "📢 Наш канал: https://t.me/+ry1sJ2l8EFY0YzBi")
    else:
        # Игнорируем сообщения от кнопок
        if not any(char in text for char in ['🎮', '💳', '🆘', '📢']):
            bot.send_message(chat_id, "🤔 Используйте кнопки меню")


if __name__ == "__main__":
    print("🚀 Запуск бота... 🎰")

    # Простая инициализация
    try:
        init_db()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"⚠️ Ошибка БД: {e}")

    # Запускаем бота с перезапуском при ошибках
    while True:
        try:
            print("🔄 Запуск телеграм бота...")
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ Ошибка бота: {e}")
            print("🔄 Перезапуск через 10 секунд...")
            time.sleep(10)
