import telebot
import sqlite3
from telebot import types
from config import TOKEN

bot = telebot.TeleBot(TOKEN)

# Словарь для хранения промежуточных состояний пользователя
user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_show = types.KeyboardButton("Показать расписание")
    btn_edit = types.KeyboardButton("Изменить урок")
    markup.add(btn_show, btn_edit)
    bot.send_message(message.chat.id, "Здравствуйте! Выберите опцию:", reply_markup=markup)

# Показ расписания
@bot.message_handler(func=lambda message: message.text == "Показать расписание")
def show_classes(message):
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM classes")
    classes = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    for cls in classes:
        markup.add(types.InlineKeyboardButton(cls[0], callback_data=f"show_{cls[0]}"))
    bot.send_message(message.chat.id, "Выберите класс:", reply_markup=markup)

# Начало редактирования урока
@bot.message_handler(func=lambda message: message.text == "Изменить урок")
def edit_start(message):
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM classes")
    classes = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    for cls in classes:
        markup.add(types.InlineKeyboardButton(cls[0], callback_data=f"edit_{cls[0]}"))
    bot.send_message(message.chat.id, "Выберите класс для редактирования:", reply_markup=markup)

# Обработка нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data

    if data.startswith("show_"):
        class_name = data[5:]
        show_schedule(call, class_name)

    elif data.startswith("edit_"):
        class_name = data[5:]
        # Сохраняем класс в состоянии пользователя
        user_state[call.from_user.id] = {"class_name": class_name}
        show_days_for_edit(call, class_name)

    elif data.startswith("day_"):
        day = data[4:]
        user_state[call.from_user.id]["day"] = day
        show_subjects_for_edit(call, user_state[call.from_user.id]["class_name"], day)

    elif data.startswith("subject_"):
        # subject_index это индекс урока в выбранный день
        index = int(data.split("_")[1])
        user_state[call.from_user.id]["subject_index"] = index
        bot.send_message(call.message.chat.id, "Введите новый предмет:")

# Функции для показа расписания
def show_schedule(call, class_name):
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM classes WHERE name = ?", (class_name,))
    class_id = cursor.fetchone()[0]

    cursor.execute("SELECT day_of_week, subject FROM lessons WHERE class_id = ?", (class_id,))
    lessons = cursor.fetchall()
    conn.close()

    if lessons:
        text = f"Расписание для класса {class_name}:\n\n"
        days = {}
        for day, subject in lessons:
            if day not in days:
                days[day] = []
            days[day].append(subject)
        for day, subjects in days.items():
            text += f"{day}:\n"
            for sub in subjects:
                text += f"  - {sub}\n"
            text += "\n"
    else:
        text = "Расписание не найдено."

    bot.send_message(call.message.chat.id, text)

# Функции для редактирования
def show_days_for_edit(call, class_name):
    days_of_week = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]
    markup = types.InlineKeyboardMarkup()
    for day in days_of_week:
        markup.add(types.InlineKeyboardButton(day, callback_data=f"day_{day}"))
    bot.send_message(call.message.chat.id, f"Выберите день для редактирования урока класса {class_name}:", reply_markup=markup)

def show_subjects_for_edit(call, class_name, day):
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM classes WHERE name = ?", (class_name,))
    class_id = cursor.fetchone()[0]

    cursor.execute("SELECT subject FROM lessons WHERE class_id = ? AND day_of_week = ?", (class_id, day))
    subjects = cursor.fetchall()
    conn.close()

    markup = types.InlineKeyboardMarkup()
    for i, sub in enumerate(subjects):
        markup.add(types.InlineKeyboardButton(sub[0], callback_data=f"subject_{i}"))
    bot.send_message(call.message.chat.id, f"Выберите урок для изменения в {day}:", reply_markup=markup)

# Получение нового предмета
@bot.message_handler(func=lambda message: message.from_user.id in user_state and "subject_index" in user_state[message.from_user.id])
def update_subject(message):
    info = user_state[message.from_user.id]
    class_name = info["class_name"]
    day = info["day"]
    index = info["subject_index"]
    new_subject = message.text

    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM classes WHERE name = ?", (class_name,))
    class_id = cursor.fetchone()[0]

    # Получаем id урока, который нужно изменить
    cursor.execute("SELECT id FROM lessons WHERE class_id = ? AND day_of_week = ?", (class_id, day))
    lesson_ids = cursor.fetchall()
    lesson_id = lesson_ids[index][0]

    cursor.execute("UPDATE lessons SET subject = ? WHERE id = ?", (new_subject, lesson_id))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, f"Урок успешно изменён на '{new_subject}'!")
    user_state.pop(message.from_user.id)

bot.infinity_polling()
