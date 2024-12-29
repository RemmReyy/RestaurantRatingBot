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
    ctrl.Rule(food_quality['poor'] & service['poor'] & ambience['poor'], satisfaction['very_low']),
    ctrl.Rule(food_quality['poor'] & service['poor'] & ambience['average'], satisfaction['low']),
    ctrl.Rule(food_quality['poor'] & service['average'] & ambience['poor'], satisfaction['low']),
    ctrl.Rule(food_quality['average'] & service['poor'] & ambience['poor'], satisfaction['low']),
    ctrl.Rule(food_quality['average'] & service['average'] & ambience['average'], satisfaction['medium']),
    ctrl.Rule(food_quality['excellent'] & service['poor'] & ambience['poor'], satisfaction['medium']),
    ctrl.Rule(food_quality['poor'] & service['excellent'] & ambience['excellent'], satisfaction['medium']),
    ctrl.Rule(food_quality['excellent'] & service['average'] & ambience['average'], satisfaction['high']),
    ctrl.Rule(food_quality['average'] & service['excellent'] & ambience['excellent'], satisfaction['high']),
    ctrl.Rule(food_quality['excellent'] & service['excellent'] & ambience['average'], satisfaction['high']),
    ctrl.Rule(food_quality['excellent'] & service['excellent'] & ambience['excellent'], satisfaction['very_high'])
]

# Create control system
satisfaction_ctrl = ctrl.ControlSystem(rules)
satisfaction_sim = ctrl.ControlSystemSimulation(satisfaction_ctrl)


# Database initialization
def init_db():
    conn = sqlite3.connect('restaurants.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS restaurants
                 (name TEXT, rating REAL, total_ratings INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ratings
                 (restaurant TEXT, food_quality REAL, service REAL, ambience REAL, 
                  satisfaction REAL, date TIMESTAMP)''')
    conn.commit()
    conn.close()


# User states dictionary
user_states = {}


class UserState:
    def __init__(self):
        self.restaurant = None
        self.waiting_for = None


# Calculate satisfaction using fuzzy logic
def calculate_satisfaction(food_q, serv, amb):
    satisfaction_sim.input['food_quality'] = food_q
    satisfaction_sim.input['service'] = serv
    satisfaction_sim.input['ambience'] = amb
    satisfaction_sim.compute()
    return satisfaction_sim.output['satisfaction']


# Start command handler
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
                 "Вітаю! Я бот для оцінки ресторанів.\n"
                 "Будь ласка, введіть назву ресторану, який ви хочете оцінити.")
    user_states[message.chat.id] = UserState()


# Handle restaurant name input
@bot.message_handler(func=lambda message:
message.chat.id in user_states and user_states[message.chat.id].waiting_for is None)
def handle_restaurant_name(message):
    restaurant_name = message.text.strip().lower()
    user_state = user_states[message.chat.id]
    user_state.restaurant = restaurant_name

    # Check if restaurant exists in database
    conn = sqlite3.connect('restaurants.db')
    c = conn.cursor()
    c.execute("SELECT rating FROM restaurants WHERE name = ?", (restaurant_name,))
    result = c.fetchone()
    conn.close()

    if result:
        bot.reply_to(message,
                     f"Поточний рейтинг ресторану: {result[0]:.2f}/10\n"
                     f"Тепер оцініть якість їжі від 0 до 10:")
    else:
        bot.reply_to(message, "Оцініть якість їжі від 0 до 10:")

    user_state.waiting_for = 'food_quality'


# Handle ratings input
@bot.message_handler(func=lambda message:
message.chat.id in user_states and user_states[message.chat.id].waiting_for is not None)
def handle_rating(message):
    try:
        rating = float(message.text)
        if not 0 <= rating <= 10:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "Будь ласка, введіть число від 0 до 10.")
        return

    user_state = user_states[message.chat.id]

    if user_state.waiting_for == 'food_quality':
        user_state.food_quality = rating
        user_state.waiting_for = 'service'
        bot.reply_to(message, "Оцініть якість обслуговування від 0 до 10:")

    elif user_state.waiting_for == 'service':
        user_state.service = rating
        user_state.waiting_for = 'ambience'
        bot.reply_to(message, "Оцініть атмосферу від 0 до 10:")

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

        bot.reply_to(message,
                     f"Дякуємо за оцінку!\n\n"
                     f"Ваша оцінка: {satisfaction:.2f}/10\n"
                     f"Загальний рейтинг ресторану: {rating:.2f}/10\n"
                     f"Всього оцінок: {total_ratings}")

        # Reset user state
        user_states[message.chat.id] = UserState()


# Error handler
@bot.error_handler(func=lambda message: True)
def error_handler(message):
    bot.reply_to(message,
                 "Виникла помилка. Будь ласка, спробуйте ще раз або зв'яжіться з адміністратором.")


# Initialize database and start bot
if __name__ == "__main__":
    try:
        init_db()
        print("Bot started successfully!")
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Error starting bot: {e}")