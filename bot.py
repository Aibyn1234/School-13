import telebot
import sqlite3
from telebot import types
from config import TOKEN

bot = telebot.TeleBot(TOKEN)
user_state = {}

CLASSES_PER_PAGE = 10  # сколько классов показывать на странице

# ====================== Старт ======================
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("Показать расписание"),
        types.KeyboardButton("Изменить урок")
    )
    bot.send_message(message.chat.id, "Здравствуйте! Выберите опцию:", reply_markup=markup)

@bot.message_handler(commands=['secret'])
def secret_command(message):
    with open("secret.jpg", "rb") as photo:
        bot.send_photo(message.chat.id, photo)

# ====================== Пагинация классов ======================
def get_classes_page(classes, page=0, per_page=CLASSES_PER_PAGE):
    start = page * per_page
    end = start + per_page
    page_classes = classes[start:end]

    markup = types.InlineKeyboardMarkup()
    for cls in page_classes:
        markup.add(types.InlineKeyboardButton(cls[0], callback_data=f"show_{cls[0]}"))

    nav_buttons = []
    if start > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅ Назад", callback_data=f"page_show_{page-1}"))
    if end < len(classes):
        nav_buttons.append(types.InlineKeyboardButton("Вперёд ➡", callback_data=f"page_show_{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    return markup

def get_classes_page_edit(classes, page=0, per_page=CLASSES_PER_PAGE):
    start = page * per_page
    end = start + per_page
    page_classes = classes[start:end]

    markup = types.InlineKeyboardMarkup()
    for cls in page_classes:
        markup.add(types.InlineKeyboardButton(cls[0], callback_data=f"edit_{cls[0]}"))

    nav_buttons = []
    if start > 0:
        nav_buttons.append(types.InlineKeyboardButton("⬅ Назад", callback_data=f"page_edit_{page-1}"))
    if end < len(classes):
        nav_buttons.append(types.InlineKeyboardButton("Вперёд ➡", callback_data=f"page_edit_{page+1}"))
    if nav_buttons:
        markup.row(*nav_buttons)

    return markup

# ====================== Показ классов ======================
@bot.message_handler(func=lambda message: message.text == "Показать расписание")
def show_classes(message):
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM classes")
    classes = cursor.fetchall()
    conn.close()

    markup = get_classes_page(classes, page=0)
    bot.send_message(message.chat.id, "Выберите класс:", reply_markup=markup)

# ====================== Редактирование классов ======================
@bot.message_handler(func=lambda message: message.text == "Изменить урок")
def edit_start(message):
    conn = sqlite3.connect("db.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM classes")
    classes = cursor.fetchall()
    conn.close()

    markup = get_classes_page_edit(classes, page=0)
    bot.send_message(message.chat.id, "Выберите класс для редактирования:", reply_markup=markup)

# ====================== Обработка callback ======================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data

    # ===== Пагинация для просмотра =====
    if data.startswith("page_show_"):
        page = int(data.split("_")[2])
        conn = sqlite3.connect("db.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM classes")
        classes = cursor.fetchall()
        conn.close()

        markup = get_classes_page(classes, page)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    # ===== Пагинация для редактирования =====
    if data.startswith("page_edit_"):
        page = int(data.split("_")[2])
        conn = sqlite3.connect("db.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM classes")
        classes = cursor.fetchall()
        conn.close()

        markup = get_classes_page_edit(classes, page)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=markup)
        return

    # ===== Показ расписания =====
    if data.startswith("show_"):
        class_name = data[5:]
        show_schedule(call, class_name)

    # ===== Редактирование =====
    elif data.startswith("edit_"):
        class_name = data[5:]
        user_state[call.from_user.id] = {"class_name": class_name}
        show_days_for_edit(call, class_name)

    elif data.startswith("day_"):
        day = data[4:]
        user_state[call.from_user.id]["day"] = day
        show_subjects_for_edit(call, user_state[call.from_user.id]["class_name"], day)

    elif data.startswith("subject_"):
        index = int(data.split("_")[1])
        user_state[call.from_user.id]["subject_index"] = index
        bot.send_message(call.message.chat.id, "Введите новый предмет:")

# ====================== Функции для показа расписания ======================
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

# ====================== Редактирование ======================
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

# ====================== Обновление предмета ======================
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

    cursor.execute("SELECT id FROM lessons WHERE class_id = ? AND day_of_week = ?", (class_id, day))
    lesson_ids = cursor.fetchall()
    lesson_id = lesson_ids[index][0]

    cursor.execute("UPDATE lessons SET subject = ? WHERE id = ?", (new_subject, lesson_id))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, f"Урок успешно изменён на '{new_subject}'!")
    user_state.pop(message.from_user.id)

# ====================== Запуск бота ======================
bot.infinity_polling()
