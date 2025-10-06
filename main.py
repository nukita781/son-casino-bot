import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import time
import random
import threading
import requests
import json
import os
from datetime import datetime
import logging

BOT_TOKEN = "8260791120:AAFoDJDs9Bzthp3MB_jJ1kkjEprTLxWt3fg"
PHOTO_PATH = "result.jpg"
WIN_PHOTO_PATH = "win.jpg"
LOSE_PHOTO_PATH = "lose.jpg"
CHANNEL_ID = "-1003120338447"
SEND_BOT_TOKEN = "428680:AAyTMpIyLvcHY1qdZgclt1pumgUxpNd5U0z"
ADMIN_ID = 6524423095

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('casino_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

bot = telebot.TeleBot(BOT_TOKEN)

# Файлы для сохранения данных
DATA_FILES = {
    'user_status': 'user_status.json',
    'user_state': 'user_state.json',
    'pending_invoices': 'pending_invoices.json',
    'game_stats': 'game_stats.json',
    'withdrawals': 'withdrawals.json',
    'transactions': 'transactions.json',
    'user_balances': 'user_balances.json'
}


# Функции для работы с JSON
def save_to_json(data, filename):
    """Сохраняет данные в JSON файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Данные сохранены в {filename}")
    except Exception as e:
        logging.error(f"Ошибка сохранения в JSON {filename}: {e}")


def load_from_json(filename):
    """Загружает данные из JSON файла"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки из JSON {filename}: {e}")
    return {}


# Загрузка данных при старте
def load_all_data():
    data = {}
    for key, filename in DATA_FILES.items():
        data[key] = load_from_json(filename)
        logging.info(f"Загружены данные: {key} - {len(data[key]) if isinstance(data[key], (dict, list)) else 'N/A'}")
    return data


# Инициализация глобальных переменных
global_data = load_all_data()
user_status = global_data['user_status'] or {}
user_state = global_data['user_state'] or {}
pending_invoices = global_data['pending_invoices'] or {}


def save_all_data():
    """Сохраняет все данные в файлы"""
    save_to_json(user_status, DATA_FILES['user_status'])
    save_to_json(user_state, DATA_FILES['user_state'])
    save_to_json(pending_invoices, DATA_FILES['pending_invoices'])


def save_game_stats(user_id, username, game_type, bet_amount, win_amount, result):
    """Сохраняет статистику игры в JSON"""
    stats = load_from_json(DATA_FILES['game_stats'])

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    game_data = {
        'user_id': user_id,
        'username': username,
        'game_type': game_type,
        'bet_amount': bet_amount,
        'win_amount': win_amount,
        'result': result,
        'timestamp': date_str
    }

    if 'games' not in stats:
        stats['games'] = []

    stats['games'].append(game_data)
    save_to_json(stats, DATA_FILES['game_stats'])

    logging.info(
        f"Игра: {username} | {game_type} | Ставка: ${bet_amount} | Выигрыш: ${win_amount} | Результат: {result}")


def save_withdrawal_request(user_id, username, amount):
    """Сохраняет заявку на вывод в JSON"""
    withdrawals = load_from_json(DATA_FILES['withdrawals'])

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    withdraw_data = {
        'user_id': user_id,
        'username': username,
        'amount': amount,
        'status': 'pending',
        'timestamp': date_str
    }

    if 'withdrawals' not in withdrawals:
        withdrawals['withdrawals'] = []

    withdrawals['withdrawals'].append(withdraw_data)
    save_to_json(withdrawals, DATA_FILES['withdrawals'])

    logging.info(f"Заявка на вывод: {username} | ${amount}")


def save_transaction(user_id, username, transaction_type, amount, details=""):
    """Сохраняет транзакцию в лог"""
    transactions = load_from_json(DATA_FILES['transactions'])

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transaction_data = {
        'user_id': user_id,
        'username': username,
        'type': transaction_type,
        'amount': amount,
        'details': details,
        'timestamp': date_str
    }

    if 'transactions' not in transactions:
        transactions['transactions'] = []

    transactions['transactions'].append(transaction_data)
    save_to_json(transactions, DATA_FILES['transactions'])

    logging.info(f"Транзакция: {username} | {transaction_type} | ${amount} | {details}")


def save_user_balance_snapshot():
    """Сохраняет снимок балансов всех пользователей"""
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, balance, tg_id FROM users')
    users = cursor.fetchall()
    conn.close()

    balances = {}
    for user in users:
        user_id, username, balance, tg_id = user
        balances[str(user_id)] = {
            'username': username,
            'balance': balance,
            'tg_id': tg_id,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    save_to_json(balances, DATA_FILES['user_balances'])
    logging.info(f"Сохранены балансы {len(balances)} пользователей")


def init_db():
    if os.path.exists('casino.db'):
        logging.info("База данных casino.db уже существует")
        return

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
        CREATE TABLE IF NOT EXISTS withdrawals (
            withdraw_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logging.info("База данных инициализирована")


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
        logging.info(f"Создан новый пользователь: {username} (ID: {tg_id})")

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

    cursor.execute('SELECT username, balance FROM users WHERE tg_id = ?', (tg_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        username, new_balance = user_data
        logging.info(f"Обновлен баланс: {username} | Изменение: ${amount:.2f} | Новый баланс: ${new_balance:.2f}")

    save_user_balance_snapshot()


def save_withdrawal(user_id, amount):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO withdrawals (user_id, amount) VALUES (?, ?)',
        (user_id, amount)
    )
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

        cursor.execute('SELECT tg_id, username FROM users WHERE user_id = ?', (user_id,))
        user_result = cursor.fetchone()
        conn.close()

        if user_result:
            tg_id, username = user_result
            logging.info(f"Оплачен счет: {username} | ${amount:.2f}")
            return tg_id
    conn.close()
    return None


def save_game_result(user_id, game_type, bet_amount, win_amount, result):
    conn = sqlite3.connect('casino.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO games (user_id, game_type, bet_amount, win_amount, result) VALUES (?, ?, ?, ?, ?)',
        (user_id, game_type, bet_amount, win_amount, result)
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
            logging.error(f"Ошибка CryptoBot API: {result}")
            return None
    except Exception as e:
        logging.error(f"Ошибка создания счета: {e}")
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
        logging.error(f"Ошибка проверки счета: {e}")
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
                        user_data = get_user_data(tg_id)

                        success_message = f"✅ ПЛАТЕЖ ПОДТВЕРЖДЕН! 💰\n\n💵 Сумма: ${invoice_data['amount']:.2f}\n💎 Новый баланс: ${user_data['balance']:.2f}\n\n🎰 Удачи в играх! 🍀"
                        bot.send_message(tg_id, success_message)

                        save_transaction(
                            user_data['user_id'],
                            user_data['username'],
                            'deposit',
                            invoice_data['amount'],
                            f"CryptoBot invoice: {send_invoice_id}"
                        )

                    processed_invoices.append(send_invoice_id)

            for send_invoice_id in processed_invoices:
                if send_invoice_id in pending_invoices:
                    del pending_invoices[send_invoice_id]

            save_all_data()

        except Exception as e:
            logging.error(f"Ошибка в проверке счетов: {e}")

        time.sleep(10)


def show_main_menu(message):
    if message.chat.id in user_state:
        del user_state[message.chat.id]

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
        "🎰 Добро пожаловать в Son Casino! 🎰\n\n🍀 Удачи в ставках! Выберите раздел:",
        reply_markup=keyboard
    )


def show_wallet(message):
    if message.chat.id in user_state:
        del user_state[message.chat.id]

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

    wallet_text = f"💼 Ваш кошелек 💼\n\n💰 Баланс: ${user_data['balance']:.2f}\n🆔 ID: {user_data['user_id']}\n👤 Ник: @{username}"

    bot.send_message(message.chat.id, wallet_text, reply_markup=keyboard)


def ask_deposit_amount(message):
    user_state[message.chat.id] = "waiting_deposit_amount"
    save_all_data()

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_wallet"))

    bot.send_message(
        message.chat.id,
        "💵 ВВЕДИТЕ СУММУ ДЛЯ ПОПОЛНЕНИЯ 💵\n\n📊 Минимум: $0.02\n📈 Максимум: $30.00\n\n💡 Пример: 5.50",
        reply_markup=keyboard
    )


def ask_withdraw_amount(message):
    user_state[message.chat.id] = "waiting_withdraw_amount"
    save_all_data()

    user_data = get_user_data(message.chat.id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки данных")
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_wallet"))

    bot.send_message(
        message.chat.id,
        f"💰 ВЫВОД СРЕДСТВ 💰\n\n💵 Минимум для вывода: $0.30\n💎 Ваш баланс: ${user_data['balance']:.2f}\n\n💡 Введите сумму для вывода:",
        reply_markup=keyboard
    )


def process_withdraw_request(user_id, tg_id, username, amount):
    user_data = get_user_data(tg_id)

    if not user_data:
        bot.send_message(tg_id, "❌ Ошибка загрузки данных")
        return

    if amount < 0.30:
        bot.send_message(tg_id, "❌ Минимальная сумма для вывода: $0.30")
        return

    if user_data['balance'] < amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    update_balance(tg_id, -amount)
    save_withdrawal(user_id, amount)
    save_withdrawal_request(user_id, username, amount)

    save_transaction(user_id, username, 'withdraw', amount, "Ожидает обработки")

    user_message = f"✅ ЗАЯВКА НА ВЫВОД ПРИНЯТА! ✅\n\n💰 Сумма: ${amount:.2f}\n💎 Новый баланс: ${user_data['balance'] - amount:.2f}\n\n⏳ Ожидайте обработки заявки администратором"
    bot.send_message(tg_id, user_message)

    admin_message = f"🔄 НОВАЯ ЗАЯВКА НА ВЫВОД 🔄\n\n👤 Пользователь: @{username}\n🆔 ID: {user_id}\n💰 Сумма: ${amount:.2f}\n💎 Баланс после списания: ${user_data['balance'] - amount:.2f}\n\n🔗 Ссылка на чат: https://t.me/{username}" if username else f"🔄 НОВАЯ ЗАЯВКА НА ВЫВОД 🔄\n\n👤 Пользователь: ID {user_id}\n💰 Сумма: ${amount:.2f}\n💎 Баланс после списания: ${user_data['balance'] - amount:.2f}"

    bot.send_message(ADMIN_ID, admin_message)


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
        save_all_data()

        deposit_text = f"💳 СЧЕТ ДЛЯ ОПЛАТЫ 💳\n\n💰 Сумма: ${amount:.2f} USDT\n🔗 Ссылка: {invoice_url}\n\n📋 Инструкция:\n1️⃣ Нажмите на ссылку выше\n2️⃣ Оплатите счет в USDT\n3️⃣ Баланс пополнится автоматически\n\n⏱ Счет действителен 15 минут\n📞 Поддержка: @support"

        bot.send_message(tg_id, deposit_text)
    else:
        bot.send_message(tg_id, "❌ Ошибка создания счета. Попробуйте позже.")


def show_games_menu(message):
    if message.chat.id in user_state:
        del user_state[message.chat.id]

    keyboard = InlineKeyboardMarkup(row_width=1)
    buttons = [
        InlineKeyboardButton("🎲 ЧЕТ/НЕЧЕТ", callback_data="game_even_odd"),
        InlineKeyboardButton("🎯 БОЛЬШЕ/МЕНЬШЕ", callback_data="game_high_low"),
        InlineKeyboardButton("🎯 ДАРТС", callback_data="game_darts"),
        InlineKeyboardButton("🏀 БАСКЕТБОЛ", callback_data="game_basketball"),
        InlineKeyboardButton("🎰 СЛОТЫ", callback_data="game_slots"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    ]
    keyboard.add(*buttons)

    games_text = """🎮 ИГРОВОЙ ЗАЛ 🎮

🎲 ЧЕТ/НЕЧЕТ
• Коэффициент: 1.8x 🎯
• Минимальная ставка: $0.02
• Максимальная ставка: $30.00

🎯 БОЛЬШЕ/МЕНЬШЕ
• Коэффициент: 1.8x 🎯
• Меньше: 1,2,3 | Больше: 4,5,6

🎯 ДАРТС
• Коэффициент: 3.0x 🎯
• Попадание в центр! 🎯

🏀 БАСКЕТБОЛ
• Коэффициент: 1.7x 🏀
• Попадание в корзину! 🏀

🎰 СЛОТЫ
• Коэффициент: 3.0x 🎰
• Только 777! 💎
"""

    bot.send_message(message.chat.id, games_text, reply_markup=keyboard)


def ask_bet_amount(message, game_type):
    user_state[message.chat.id] = f"waiting_bet_{game_type}"
    save_all_data()

    user_data = get_user_data(message.chat.id)
    if not user_data:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки данных")
        return

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_games"))

    bet_info = f"💰 ВВЕДИТЕ СУММУ СТАВКИ 💰\n\n💸 Минимум: $0.02\n💰 Максимум: $30.00\n💎 Ваш баланс: ${user_data['balance']:.2f}\n\n💡 Пример: 1.50 или 5"

    bot.send_message(message.chat.id, bet_info, reply_markup=keyboard)


def ask_even_odd_choice(message, bet_amount):
    user_state[message.chat.id] = f"waiting_choice_even_odd_{bet_amount}"
    save_all_data()

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🔵 ЧЕТ", callback_data=f"choice_even_{bet_amount}"),
        InlineKeyboardButton("🔴 НЕЧЕТ", callback_data=f"choice_odd_{bet_amount}"),
        InlineKeyboardButton("🔙 Назад", callback_data=f"back_bet_{bet_amount}")
    ]
    keyboard.add(*buttons[:2], buttons[2])

    bot.send_message(
        message.chat.id,
        f"🎲 Ставка: ${bet_amount:.2f}\n\n🎯 Выберите вариант:",
        reply_markup=keyboard
    )


def ask_high_low_choice(message, bet_amount):
    user_state[message.chat.id] = f"waiting_choice_high_low_{bet_amount}"
    save_all_data()

    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("📉 МЕНЬШЕ", callback_data=f"choice_low_{bet_amount}"),
        InlineKeyboardButton("📈 БОЛЬШЕ", callback_data=f"choice_high_{bet_amount}"),
        InlineKeyboardButton("🔙 Назад", callback_data=f"back_bet_{bet_amount}")
    ]
    keyboard.add(*buttons[:2], buttons[2])

    bot.send_message(
        message.chat.id,
        f"🎲 Ставка: ${bet_amount:.2f}\n\n🎯 Выберите вариант:\n📉 Меньше (1,2,3)\n📈 Больше (4,5,6)",
        reply_markup=keyboard
    )


def process_game_result(user_id, tg_id, username, bet_amount, game_type, result, win_amount, win):
    if win:
        update_balance(tg_id, win_amount)
        save_game_result(user_id, game_type, bet_amount, win_amount, "win")
        save_game_stats(user_id, username, game_type, bet_amount, win_amount, "win")

        save_transaction(user_id, username, 'game_win', win_amount, f"{game_type} - {result}")

        try:
            win_channel_text = f"🎉 ПОЗДРАВЛЯЮ С ПОБЕДОЙ! 🎉\n\n💰 Вы выиграли ${win_amount:.2f}\n💎 Ваши монеты начислены вам в бота"
            keyboard = InlineKeyboardMarkup()
            buttons = [
                InlineKeyboardButton("🎯 СДЕЛАТЬ СТАВКУ", url="https://t.me/SonCasinoBet_bot?start=play")
            ]
            keyboard.add(*buttons)

            with open(WIN_PHOTO_PATH, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=win_channel_text, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка отправки победы в канал: {e}")

        bot.send_message(
            tg_id,
            f"🎉 ПОЗДРАВЛЯЮ ВЫ ПОБЕДИЛИ! 🎉\n\n💰 Выигрыш: ${win_amount:.2f}\n💎 Начислено на ваш баланс"
        )

    else:
        save_game_result(user_id, game_type, bet_amount, 0, "lose")
        save_game_stats(user_id, username, game_type, bet_amount, 0, "lose")

        save_transaction(user_id, username, 'game_lose', -bet_amount, f"{game_type} - {result}")

        try:
            lose_channel_text = "💔 К сожалению, вы проиграли, но не расстраивайся! 💔\n\n🎯 Поставь еще - удача на твоей стороне! 🍀"
            keyboard = InlineKeyboardMarkup()
            buttons = [
                InlineKeyboardButton("🎯 СДЕЛАТЬ СТАВКУ", url="https://t.me/SonCasinoBet_bot?start=play")
            ]
            keyboard.add(*buttons)

            with open(LOSE_PHOTO_PATH, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo, caption=lose_channel_text, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка отправки проигрыша в канал: {e}")

        bot.send_message(
            tg_id,
            f"💔 К сожалению, вы проиграли ${bet_amount:.2f} 💔\n\n🎯 Попробуйте еще раз - удача на вашей стороне! 🍀"
        )


def process_even_odd_game(user_id, tg_id, username, bet_amount, choice):
    user_data = get_user_data(tg_id)

    if user_data['balance'] < bet_amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    update_balance(tg_id, -bet_amount)

    choice_text = "ЧЕТ" if choice == "even" else "НЕЧЕТ"

    try:
        channel_message = f"🚀 СТАВКА ЗАПУЩЕНА! 🚀\n\n👤 {username}\n💰 Ставка: ${bet_amount:.2f}\n🎮 Игра: Чет/Нечет\n🎯 Исход: {choice_text}\n🎁 Выигрыш: ${bet_amount * 1.8:.2f}"
        sent_message = bot.send_message(CHANNEL_ID, channel_message)

        dice_message = bot.send_dice(CHANNEL_ID, emoji='🎲', reply_to_message_id=sent_message.message_id)
        dice_result = dice_message.dice.value

    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")
        dice_result = random.randint(1, 6)

    time.sleep(3)

    is_even = dice_result % 2 == 0

    # Честная вероятность 50/50
    win = (choice == "even" and is_even) or (choice == "odd" and not is_even)

    if win:
        win_amount = round(bet_amount * 1.8, 2)
        process_game_result(user_id, tg_id, username, bet_amount, "even_odd",
                            f"Выпало: {dice_result} ({'ЧЕТ' if is_even else 'НЕЧЕТ'})", win_amount, True)
    else:
        process_game_result(user_id, tg_id, username, bet_amount, "even_odd",
                            f"Выпало: {dice_result} ({'ЧЕТ' if is_even else 'НЕЧЕТ'})", 0, False)


def process_high_low_game(user_id, tg_id, username, bet_amount, choice):
    user_data = get_user_data(tg_id)

    if user_data['balance'] < bet_amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    update_balance(tg_id, -bet_amount)

    choice_text = "МЕНЬШЕ" if choice == "low" else "БОЛЬШЕ"

    try:
        channel_message = f"🚀 СТАВКА ЗАПУЩЕНА! 🚀\n\n👤 {username}\n💰 Ставка: ${bet_amount:.2f}\n🎮 Игра: Больше/Меньше\n🎯 Исход: {choice_text}\n🎁 Выигрыш: ${bet_amount * 1.8:.2f}"
        sent_message = bot.send_message(CHANNEL_ID, channel_message)

        dice_message = bot.send_dice(CHANNEL_ID, emoji='🎲', reply_to_message_id=sent_message.message_id)
        dice_result = dice_message.dice.value

    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")
        dice_result = random.randint(1, 6)

    time.sleep(3)

    is_low = dice_result in [1, 2, 3]
    is_high = dice_result in [4, 5, 6]

    # Честная вероятность 50/50
    win = (choice == "low" and is_low) or (choice == "high" and is_high)

    if win:
        win_amount = round(bet_amount * 1.8, 2)
        process_game_result(user_id, tg_id, username, bet_amount, "high_low",
                            f"Выпало: {dice_result} ({'МЕНЬШЕ' if is_low else 'БОЛЬШЕ'})", win_amount, True)
    else:
        process_game_result(user_id, tg_id, username, bet_amount, "high_low",
                            f"Выпало: {dice_result} ({'МЕНЬШЕ' if is_low else 'БОЛЬШЕ'})", 0, False)


def process_darts_game(user_id, tg_id, username, bet_amount):
    user_data = get_user_data(tg_id)

    if user_data['balance'] < bet_amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    update_balance(tg_id, -bet_amount)

    try:
        channel_message = f"🚀 СТАВКА ЗАПУЩЕНА! 🚀\n\n👤 {username}\n💰 Ставка: ${bet_amount:.2f}\n🎮 Игра: Дартс\n🎯 Исход: ПОПАДАНИЕ В ЦЕНТР\n🎁 Выигрыш: ${bet_amount * 3.0:.2f}"
        sent_message = bot.send_message(CHANNEL_ID, channel_message)

        darts_message = bot.send_dice(CHANNEL_ID, emoji='🎯', reply_to_message_id=sent_message.message_id)
        darts_result = darts_message.dice.value

    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")
        darts_result = random.randint(1, 6)

    time.sleep(3)

    # В дартсе выигрыш - это попадание в центр (значение 6)
    win = darts_result == 6

    if win:
        win_amount = round(bet_amount * 3.0, 2)
        process_game_result(user_id, tg_id, username, bet_amount, "darts",
                            f"Результат: {darts_result} (ПОПАЛ В ЦЕНТР!)", win_amount, True)
    else:
        process_game_result(user_id, tg_id, username, bet_amount, "darts", f"Результат: {darts_result}", 0, False)


def process_basketball_game(user_id, tg_id, username, bet_amount):
    user_data = get_user_data(tg_id)

    if user_data['balance'] < bet_amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    update_balance(tg_id, -bet_amount)

    try:
        channel_message = f"🚀 СТАВКА ЗАПУЩЕНА! 🚀\n\n👤 {username}\n💰 Ставка: ${bet_amount:.2f}\n🎮 Игра: Баскетбол\n🎯 Исход: ПОПАДАНИЕ В КОРЗИНУ\n🎁 Выигрыш: ${bet_amount * 1.7:.2f}"
        sent_message = bot.send_message(CHANNEL_ID, channel_message)

        basketball_message = bot.send_dice(CHANNEL_ID, emoji='🏀', reply_to_message_id=sent_message.message_id)
        basketball_result = basketball_message.dice.value

    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")
        basketball_result = random.randint(1, 5)

    time.sleep(3)

    # В баскетболе выигрыш - это попадание в корзину (значение 4 или 5)
    win = basketball_result in [4, 5]

    if win:
        win_amount = round(bet_amount * 1.7, 2)
        process_game_result(user_id, tg_id, username, bet_amount, "basketball",
                            f"Результат: {basketball_result} (ПОПАЛ В КОРЗИНУ! 🏀)", win_amount, True)
    else:
        process_game_result(user_id, tg_id, username, bet_amount, "basketball",
                            f"Результат: {basketball_result} (ПРОМАХ ❌)", 0, False)


def process_slots_game(user_id, tg_id, username, bet_amount):
    user_data = get_user_data(tg_id)

    if user_data['balance'] < bet_amount:
        bot.send_message(tg_id, "❌ Недостаточно средств на балансе")
        return

    update_balance(tg_id, -bet_amount)

    try:
        channel_message = f"🚀 СТАВКА ЗАПУЩЕНА! 🚀\n\n👤 {username}\n💰 Ставка: ${bet_amount:.2f}\n🎮 Игра: Слоты\n🎯 Исход: ВЫПАДЕНИЕ 777\n🎁 Выигрыш: ${bet_amount * 3.0:.2f}"
        sent_message = bot.send_message(CHANNEL_ID, channel_message)

        slots_message = bot.send_dice(CHANNEL_ID, emoji='🎰', reply_to_message_id=sent_message.message_id)
        slots_result = slots_message.dice.value

    except Exception as e:
        print(f"Ошибка отправки в канал: {e}")
        slots_result = random.randint(1, 64)

    time.sleep(3)

    win = slots_result == 64

    if win:
        win_amount = round(bet_amount * 3.0, 2)
        process_game_result(user_id, tg_id, username, bet_amount, "slots", "Результат: 777! 🎰", win_amount, True)
    else:
        process_game_result(user_id, tg_id, username, bet_amount, "slots", f"Результат: {slots_result}", 0, False)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    if message.text and 'play' in message.text:
        show_games_menu(message)
        return

    user_id = get_or_create_user(chat_id, message.from_user.username)

    if user_status.get(chat_id):
        show_main_menu(message)
        return

    # Создаем keyboard ДО try-except блока
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("📄 Пользовательское соглашение",
                             url="https://telegra.ph/Son-Casino--Polzovatelskoe-soglashenie-10-04"),
        InlineKeyboardButton("❌ Отказаться", callback_data="decline"),
        InlineKeyboardButton("✅ Принять", callback_data="accept")
    ]
    keyboard.add(*buttons)

    try:
        with open(PHOTO_PATH, 'rb') as photo:
            bot.send_photo(
                chat_id,
                photo,
                caption="🎰 Привет! Я Son Bet 🎰\n\n📖 Настоятельно рекомендую прочитать Пользовательское соглашение",
                reply_markup=keyboard
            )
    except Exception as e:
        bot.send_message(
            chat_id,
            "🎰 Привет! Я Son Bet 🎰\n\n📖 Настоятельно рекомендую прочитать Пользовательское соглашение",
            reply_markup=keyboard
        )


# Секретная команда для накрутки денег
@bot.message_handler(commands=['admin1234mon1'])
def admin_add_money(message):
    try:
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "❌ Доступ запрещен")
            return

        parts = message.text.split()
        if len(parts) != 3:
            bot.send_message(message.chat.id, "❌ Использование: /admin1234mon1 @username сумма")
            return

        username = parts[1].replace('@', '')
        amount = float(parts[2])

        conn = sqlite3.connect('casino.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT tg_id FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            bot.send_message(message.chat.id, f"❌ Пользователь @{username} не найден")
            return

        tg_id = result[0]

        update_balance(tg_id, amount)
        user_data = get_user_data(tg_id)

        save_transaction(user_data['user_id'], username, 'admin_add', amount, "Админская накрутка")

        bot.send_message(
            message.chat.id,
            f"✅ ДЕНЬГИ НАЧИСЛЕНЫ!\n\n👤 Пользователь: @{username}\n💰 Сумма: ${amount:.2f}\n💎 Новый баланс: ${user_data['balance']:.2f}"
        )

        bot.send_message(
            tg_id,
            f"🎉 ВАМ НАЧИСЛЕНЫ ДЕНЬГИ! 🎉\n\n💰 Сумма: ${amount:.2f}\n💎 Новый баланс: ${user_data['balance']:.2f}\n\n🎰 Удачи в играх!"
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")


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
        if user_data and user_data['balance'] >= 0.30:
            ask_withdraw_amount(call.message)
        else:
            bot.send_message(chat_id, "❌ НЕДОСТАТОЧНО СРЕДСТВ ❌\n\n💵 Минимум для вывода: $0.30")

    elif call.data == "back_to_wallet":
        show_wallet(call.message)

    elif call.data == "back_to_menu":
        show_main_menu(call.message)

    elif call.data == "back_to_games":
        show_games_menu(call.message)

    elif call.data.startswith("back_bet_"):
        bet_amount = float(call.data.split("_")[2])
        show_games_menu(call.message)

    elif call.data == "game_even_odd":
        ask_bet_amount(call.message, "even_odd")

    elif call.data == "game_high_low":
        ask_bet_amount(call.message, "high_low")

    elif call.data == "game_darts":
        ask_bet_amount(call.message, "darts")

    elif call.data == "game_basketball":
        ask_bet_amount(call.message, "basketball")

    elif call.data == "game_slots":
        ask_bet_amount(call.message, "slots")

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

    elif call.data.startswith("choice_low_"):
        bet_amount = float(call.data.split("_")[2])
        process_high_low_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            bet_amount,
            "low"
        )

    elif call.data.startswith("choice_high_"):
        bet_amount = float(call.data.split("_")[2])
        process_high_low_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            bet_amount,
            "high"
        )

    elif call.data == "game_darts_bet":
        # Для дартса сразу запускаем игру со стандартной ставкой
        process_darts_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            1.00  # Стандартная ставка $1
        )

    elif call.data == "game_basketball_bet":
        # Для баскетбола сразу запускаем игру со стандартной ставкой
        process_basketball_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            1.00  # Стандартная ставка $1
        )

    elif call.data == "game_slots_bet":
        # Для слотов сразу запускаем игру со стандартной ставкой
        process_slots_game(
            get_or_create_user(chat_id, call.from_user.username),
            chat_id,
            call.from_user.username or "Игрок",
            1.00  # Стандартная ставка $1
        )


@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id

    if not user_status.get(chat_id):
        return

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

    if user_state.get(chat_id) == "waiting_withdraw_amount":
        try:
            amount = float(message.text)
            user_data = get_user_data(chat_id)
            if user_data:
                process_withdraw_request(user_data['user_id'], chat_id, user_data['username'], amount)
            user_state[chat_id] = None
        except ValueError:
            bot.send_message(chat_id, "❌ Введите число (например: 1.50)")
        return

    if user_state.get(chat_id) and user_state[chat_id].startswith("waiting_bet_"):
        try:
            bet_amount = float(message.text)
            if bet_amount < 0.02:
                bot.send_message(chat_id, "❌ Минимум $0.02")
            elif bet_amount > 30:
                bot.send_message(chat_id, "❌ Максимум $30.00")
            else:
                user_data = get_user_data(chat_id)
                if user_data and user_data['balance'] >= bet_amount:
                    game_type = user_state[chat_id].replace("waiting_bet_", "")

                    if game_type == "even_odd":
                        ask_even_odd_choice(message, bet_amount)
                    elif game_type == "high_low":
                        ask_high_low_choice(message, bet_amount)
                    elif game_type == "darts":
                        process_darts_game(
                            get_or_create_user(chat_id, message.from_user.username),
                            chat_id,
                            message.from_user.username or "Игрок",
                            bet_amount
                        )
                    elif game_type == "basketball":
                        process_basketball_game(
                            get_or_create_user(chat_id, message.from_user.username),
                            chat_id,
                            message.from_user.username or "Игрок",
                            bet_amount
                        )
                    elif game_type == "slots":
                        process_slots_game(
                            get_or_create_user(chat_id, message.from_user.username),
                            chat_id,
                            message.from_user.username or "Игрок",
                            bet_amount
                        )

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
        bot.send_message(chat_id, "🆘 ПОДДЕРЖКА: @support 📞")
    elif text == "📢 Канал":
        bot.send_message(chat_id, "📢 НАШ КАНАЛ: https://t.me/+ry1sJ2l8EFY0YzBi 📢")
    else:
        bot.send_message(chat_id, "🤔 Используйте кнопки меню 🎰")


if __name__ == "__main__":
    print("🚀 Бот запущен! 🎰")
    logging.info("=== БОТ ЗАПУЩЕН ===")

    init_db()

    for filename in DATA_FILES.values():
        if not os.path.exists(filename):
            save_to_json({}, filename)

    save_all_data()
    save_user_balance_snapshot()

    payment_thread = threading.Thread(target=check_invoice_payments, daemon=True)
    payment_thread.start()


    def auto_save():
        while True:
            time.sleep(60)
            save_all_data()
            save_user_balance_snapshot()
            logging.info("Автосохранение данных выполнено")


    save_thread = threading.Thread(target=auto_save, daemon=True)
    save_thread.start()

    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.error(f"Ошибка бота: {e}")
    finally:
        save_all_data()
        save_user_balance_snapshot()
        logging.info("=== БОТ ОСТАНОВЛЕН ===")
