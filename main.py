import os
from dotenv import load_dotenv
import telebot
from telebot import types
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import sqlite3
from datetime import datetime

# Load environment variables
load_dotenv()

# Bot initialization
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("No TELEGRAM_BOT_TOKEN found in .env file")

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize fuzzy logic system
food_quality = ctrl.Antecedent(np.arange(0, 11, 1), 'food_quality')
service = ctrl.Antecedent(np.arange(0, 11, 1), 'service')
ambience = ctrl.Antecedent(np.arange(0, 11, 1), 'ambience')
satisfaction = ctrl.Consequent(np.arange(0, 11, 1), 'satisfaction')

# Define membership functions
food_quality.automf(names=['poor', 'average', 'excellent'])
service.automf(names=['poor', 'average', 'excellent'])
ambience.automf(names=['poor', 'average', 'excellent'])

satisfaction['very_low'] = fuzz.trimf(satisfaction.universe, [0, 0, 2.5])
satisfaction['low'] = fuzz.trimf(satisfaction.universe, [0, 2.5, 5])
satisfaction['medium'] = fuzz.trimf(satisfaction.universe, [2.5, 5, 7.5])
satisfaction['high'] = fuzz.trimf(satisfaction.universe, [5, 7.5, 10])
satisfaction['very_high'] = fuzz.trimf(satisfaction.universe, [7.5, 10, 10])

# Define rules
rules = [
    # Дуже низька задоволеність
    ctrl.Rule(food_quality['poor'] & service['poor'] & ambience['poor'], satisfaction['very_low']),
    ctrl.Rule(food_quality['poor'] & service['poor'] & ambience['average'], satisfaction['very_low']),
    ctrl.Rule(food_quality['poor'] & service['poor'] & ambience['excellent'], satisfaction['low']),

    # Низька задоволеність
    ctrl.Rule(food_quality['poor'] & service['average'] & ambience['poor'], satisfaction['low']),
    ctrl.Rule(food_quality['poor'] & service['average'] & ambience['average'], satisfaction['low']),
    ctrl.Rule(food_quality['poor'] & service['excellent'] & ambience['poor'], satisfaction['low']),
    ctrl.Rule(food_quality['average'] & service['poor'] & ambience['poor'], satisfaction['low']),

    # Середня задоволеність
    ctrl.Rule(food_quality['average'] & service['average'] & ambience['average'], satisfaction['medium']),
    ctrl.Rule(food_quality['average'] & service['average'] & ambience['excellent'], satisfaction['medium']),
    ctrl.Rule(food_quality['average'] & service['excellent'] & ambience['average'], satisfaction['medium']),
    ctrl.Rule(food_quality['excellent'] & service['average'] & ambience['average'], satisfaction['medium']),
    ctrl.Rule(food_quality['poor'] & service['excellent'] & ambience['excellent'], satisfaction['medium']),

    # Висока задоволеність
    ctrl.Rule(food_quality['excellent'] & service['excellent'] & ambience['average'], satisfaction['high']),
    ctrl.Rule(food_quality['excellent'] & service['average'] & ambience['excellent'], satisfaction['high']),
    ctrl.Rule(food_quality['average'] & service['excellent'] & ambience['excellent'], satisfaction['high']),

    # Дуже висока задоволеність
    ctrl.Rule(food_quality['excellent'] & service['excellent'] & ambience['excellent'], satisfaction['very_high'])
]

# Create control system
satisfaction_ctrl = ctrl.ControlSystem(rules)
satisfaction_sim = ctrl.ControlSystemSimulation(satisfaction_ctrl)


# User state class
class UserState:
    def __init__(self):
        self.restaurant = None
        self.waiting_for = None
        self.food_quality = None
        self.service = None
        self.ambience = None


# User states dictionary
user_states = {}


def create_main_menu():
    """Створює головне меню бота"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("🏆 Оцінити ресторан")
    btn2 = types.KeyboardButton("📊 Топ ресторанів")
    btn3 = types.KeyboardButton("🔍 Знайти ресторан")
    btn4 = types.KeyboardButton("❓ Допомога")
    markup.add(btn1, btn2, btn3, btn4)
    return markup


def create_rating_menu():
    """Створює меню для оцінювання"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=5)
    buttons = [types.KeyboardButton(str(i)) for i in range(11)]
    markup.add(*buttons)
    cancel_btn = types.KeyboardButton("❌ Скасувати")
    markup.add(cancel_btn)
    return markup


def init_db():
    """Initialize database"""
    conn = sqlite3.connect('restaurants.db')
    c = conn.cursor()

    c.execute('DROP TABLE IF EXISTS restaurants')
    c.execute('''CREATE TABLE IF NOT EXISTS restaurants
                 (name TEXT UNIQUE, rating REAL, total_ratings INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ratings
                 (restaurant TEXT, food_quality REAL, service REAL, ambience REAL, 
                  satisfaction REAL, date TIMESTAMP)''')
    conn.commit()
    conn.close()


def calculate_satisfaction(food_q, serv, amb):
    """Calculate satisfaction using fuzzy logic"""
    try:
        satisfaction_sim.input['food_quality'] = food_q
        satisfaction_sim.input['service'] = serv
        satisfaction_sim.input['ambience'] = amb
        satisfaction_sim.compute()
        return satisfaction_sim.output['satisfaction']
    except:
        return (food_q * 0.4 + serv * 0.3 + amb * 0.3)


# Command handlers
@bot.message_handler(commands=['start'])
def start(message):
    welcome_text = (
        "👋 Вітаю! Я бот для оцінки ресторанів.\n\n"
        "🔥 Ось що я вмію:\n"
        "🏆 Оцінити ресторан - додати нову оцінку\n"
        "📊 Топ ресторанів - переглянути рейтинг\n"
        "🔍 Знайти ресторан - пошук по базі\n"
        "❓ Допомога - додаткова інформація\n\n"
        "Оберіть опцію з меню нижче 👇"
    )
    bot.reply_to(message, welcome_text, reply_markup=create_main_menu())
    user_states[message.chat.id] = UserState()


@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "📖 *Інструкція з використання бота:*\n\n"
        "1️⃣ *Оцінити ресторан:*\n"
        "   - Натисніть '🏆 Оцінити ресторан'\n"
        "   - Введіть назву ресторану\n"
        "   - Оцініть їжу, сервіс та атмосферу\n\n"
        "2️⃣ *Топ ресторанів:*\n"
        "   - Показує список найкращих закладів\n\n"
        "3️⃣ *Знайти ресторан:*\n"
        "   - Шукає заклад у базі даних\n"
        "   - Показує його рейтинг\n\n"
        "❌ *Скасувати* - повернутися до головного меню\n\n"
        "Якщо виникли проблеми, спробуйте команду /start"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text == "📊 Топ ресторанів")
def top_restaurants(message):
    try:
        conn = sqlite3.connect('restaurants.db')
        c = conn.cursor()
        c.execute("""
            SELECT name, rating, total_ratings 
            FROM restaurants 
            ORDER BY rating DESC 
            LIMIT 10
        """)
        restaurants = c.fetchall()
        conn.close()

        if not restaurants:
            bot.reply_to(message, "🤷‍♂️ Поки що немає оцінених ресторанів.")
            return

        response = "🏆 *Топ-10 ресторанів:*\n\n"
        for i, (name, rating, total_ratings) in enumerate(restaurants, 1):
            response += f"{i}. *{name.title()}*\n"
            response += f"   ⭐️ Рейтинг: {rating:.2f}/10\n"
            response += f"   👥 Кількість оцінок: {total_ratings}\n\n"

        bot.reply_to(message, response, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "😔 Виникла помилка при отриманні даних.")
        print(f"Error in top_restaurants: {e}")


@bot.message_handler(func=lambda message: message.text == "🔍 Знайти ресторан")
def search_restaurant_command(message):
    bot.reply_to(message, "Введіть назву ресторану для пошуку:")
    user_state = user_states.get(message.chat.id, UserState())
    user_state.waiting_for = 'search'
    user_states[message.chat.id] = user_state


@bot.message_handler(func=lambda message:
message.chat.id in user_states and user_states[message.chat.id].waiting_for == 'search')
def search_restaurant(message):
    try:
        search_query = message.text.strip().lower()
        conn = sqlite3.connect('restaurants.db')
        c = conn.cursor()
        c.execute("""
            SELECT name, rating, total_ratings 
            FROM restaurants 
            WHERE LOWER(name) LIKE ?
        """, (f"%{search_query}%",))
        restaurants = c.fetchall()
        conn.close()

        if not restaurants:
            bot.reply_to(message,
                         "😔 Ресторан не знайдено.\n"
                         "Спробуйте інший запит або додайте нову оцінку.",
                         reply_markup=create_main_menu())
        else:
            response = "🔍 *Результати пошуку:*\n\n"
            for name, rating, total_ratings in restaurants:
                response += f"🏷 *{name.title()}*\n"
                response += f"⭐️ Рейтинг: {rating:.2f}/10\n"
                response += f"👥 Кількість оцінок: {total_ratings}\n\n"

            bot.reply_to(message, response, parse_mode="Markdown",
                         reply_markup=create_main_menu())

        user_states[message.chat.id] = UserState()
    except Exception as e:
        bot.reply_to(message, "😔 Виникла помилка при пошуку.")
        print(f"Error in search_restaurant: {e}")


@bot.message_handler(func=lambda message: message.text == "🏆 Оцінити ресторан")
def start_rating(message):
    bot.reply_to(message,
                 "Введіть назву ресторану, який хочете оцінити:",
                 reply_markup=types.ReplyKeyboardRemove())
    user_states[message.chat.id] = UserState()


@bot.message_handler(func=lambda message: message.text == "❓ Допомога")
def help_message(message):
    help_command(message)


@bot.message_handler(func=lambda message: message.text == "❌ Скасувати")
def cancel_operation(message):
    user_states[message.chat.id] = UserState()
    bot.reply_to(message,
                 "Операцію скасовано. Оберіть опцію з меню:",
                 reply_markup=create_main_menu())


@bot.message_handler(func=lambda message:
message.chat.id in user_states and user_states[message.chat.id].waiting_for is None)
def handle_restaurant_name(message):
    try:
        restaurant_name = message.text.strip().lower()
        user_state = user_states[message.chat.id]
        user_state.restaurant = restaurant_name

        conn = sqlite3.connect('restaurants.db')
        c = conn.cursor()
        c.execute("SELECT rating FROM restaurants WHERE name = ?", (restaurant_name,))
        result = c.fetchone()
        conn.close()

        if result:
            bot.reply_to(message,
                         f"Поточний рейтинг ресторану: {result[0]:.2f}/10\n"
                         f"Тепер оцініть якість їжі від 0 до 10:",
                         reply_markup=create_rating_menu())
        else:
            bot.reply_to(message, "Оцініть якість їжі від 0 до 10:",
                         reply_markup=create_rating_menu())

        user_state.waiting_for = 'food_quality'
    except Exception as e:
        bot.reply_to(message, "Виникла помилка. Будь ласка, спробуйте ще раз.")
        print(f"Error in handle_restaurant_name: {e}")


@bot.message_handler(func=lambda message:
message.chat.id in user_states and user_states[message.chat.id].waiting_for is not None)
def handle_rating(message):
    try:
        if message.text == "❌ Скасувати":
            cancel_operation(message)
            return

        rating = float(message.text)
        if not 0 <= rating <= 10:
            raise ValueError("Rating out of range")

        user_state = user_states[message.chat.id]

        if user_state.waiting_for == 'food_quality':
            user_state.food_quality = rating
            user_state.waiting_for = 'service'
            bot.reply_to(message, "Оцініть якість обслуговування від 0 до 10:",
                        reply_markup=create_rating_menu())

        elif user_state.waiting_for == 'service':
            user_state.service = rating
            user_state.waiting_for = 'ambience'
            bot.reply_to(message, "Оцініть атмосферу від 0 до 10:",
                        reply_markup=create_rating_menu())

        elif user_state.waiting_for == 'ambience':
            user_state.ambience = rating
            satisfaction = calculate_satisfaction(user_state.food_quality,
                                               user_state.service,
                                               user_state.ambience)

            # Save rating to database
            conn = sqlite3.connect('restaurants.db')
            c = conn.cursor()

            # Save individual rating
            c.execute("""INSERT INTO ratings 
                        (restaurant, food_quality, service, ambience, satisfaction, date) 
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (user_state.restaurant, user_state.food_quality, user_state.service,
                      user_state.ambience, satisfaction, datetime.now()))

            # Update or insert restaurant average rating
            c.execute("""INSERT INTO restaurants (name, rating, total_ratings)
                        VALUES (?, ?, 1)
                        ON CONFLICT(name) DO UPDATE SET
                        rating = ((rating * total_ratings) + ?) / (total_ratings + 1),
                        total_ratings = total_ratings + 1""",
                     (user_state.restaurant, satisfaction, satisfaction))

            conn.commit()

            # Get updated rating
            c.execute("SELECT rating, total_ratings FROM restaurants WHERE name = ?",
                     (user_state.restaurant,))
            rating, total_ratings = c.fetchone()
            conn.close()

            response = (
                f"🎉 Дякуємо за оцінку!\n\n"
                f"📊 *Ваші оцінки:*\n"
                f"🍽 Їжа: {user_state.food_quality}/10\n"
                f"👨‍🍳 Сервіс: {user_state.service}/10\n"
                f"🌟 Атмосфера: {user_state.ambience}/10\n"
                f"📈 Загальна оцінка: {satisfaction:.2f}/10\n\n"
                f"📍 *Статистика ресторану \"{user_state.restaurant.title()}\":*\n"
                f"⭐️ Середній рейтинг: {rating:.2f}/10\n"
                f"👥 Всього оцінок: {total_ratings}"
            )

            bot.reply_to(message, response, parse_mode="Markdown",
                        reply_markup=create_main_menu())

            # Reset user state
            user_states[message.chat.id] = UserState()

    except ValueError:
        bot.reply_to(message,
                    "Будь ласка, введіть число від 0 до 10 або натисніть 'Скасувати'.",
                    reply_markup=create_rating_menu())
    except Exception as e:
        bot.reply_to(message, "😔 Виникла помилка. Будь ласка, спробуйте ще раз.")
        print(f"Error in handle_rating: {e}")

# General error handler
@bot.message_handler(func=lambda message: True)
def handle_errors(message):
    if message.chat.id not in user_states:
        user_states[message.chat.id] = UserState()
        bot.reply_to(message,
                    "🤔 Щось пішло не так. Давайте почнемо спочатку.\n"
                    "Оберіть опцію з меню:",
                    reply_markup=create_main_menu())

# Main execution
if __name__ == "__main__":
    try:
        init_db()
        print("✨ Bot started successfully!")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"❌ Error starting bot: {e}")