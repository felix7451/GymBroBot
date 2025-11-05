import telebot
from telebot import types
import sqlite3
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Token verification
if TELEGRAM_TOKEN is None:
    print("Ошибка: Не удалось загрузить TELEGRAM_TOKEN.")
    exit() 

def init_db():
    """Initialization + db create."""
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        
        # day tren table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS TrainingDays (
            day_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER NOT NULL,
            day_name TEXT NOT NULL
        )
        ''')
        
        # day ex table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Exercises (
            exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            FOREIGN KEY (day_id) REFERENCES TrainingDays (day_id)
        )
        ''')

        # logs table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight REAL NOT NULL,
            reps INTEGER NOT NULL,
            FOREIGN KEY (exercise_id) REFERENCES Exercises (exercise_id)
        )
        ''')
        
        conn.commit()
        print("'workouts.db' successfully initialized.")
    
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    
    finally:
        if conn:
            conn.close()

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def get_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # button create
    btn_add_day = types.KeyboardButton("➕ Добавить день")
    btn_my_days = types.KeyboardButton("📅 Мои дни")
    btn_delete_day = types.KeyboardButton("🗑️ Удалить день") 
    
    # keyboard create
    keyboard.add(btn_add_day, btn_my_days)
    keyboard.add(btn_delete_day) 
    return keyboard

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, 
                     "Это твой GymBro. let's get it started!", 
                     reply_markup=get_main_keyboard())
    
@bot.message_handler(func=lambda message: message.text == "➕ Добавить день")
def handle_add_day(message):
    msg = bot.send_message(message.chat.id, 
                           "Введи названия нового дня тренировок;")
    
# pass to the save_day function(IMPORTANT)
    bot.register_next_step_handler(msg, save_day)

def save_day(message):
    """Save log names in workouts.db."""
    user_id = message.from_user.id
    day_name = message.text
    
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        # specify user_id to find which user it is.
        cursor.execute(
            "INSERT INTO TrainingDays (user_id, day_name) VALUES (?, ?)", 
            (user_id, day_name)
        )
        conn.commit()
        
        bot.send_message(message.chat.id, 
                         f"👍 День '{day_name}' успешно добавлен!", 
                         reply_markup=get_main_keyboard())
    
    except sqlite3.Error as e:
        print(f"Ошибка при добавлении дня в БД: {e}")
        bot.send_message(message.chat.id, 
                         "Произошла ошибка при сохранении. Попробуй еще раз.", 
                         reply_markup=get_main_keyboard())
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == "📅 Мои дни")
def show_my_days(message):
    user_id = message.from_user.id
    
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        
        # get id and name of day from db
        cursor.execute(
            "SELECT day_id, day_name FROM TrainingDays WHERE user_id = ?", 
            (user_id,)
        )
        days = cursor.fetchall()
        
        if not days:
            bot.send_message(message.chat.id, 
                             "У тебя пока нет тренировочного дня. \nНажми '➕ Добавить день', чтобы создать первый.", 
                             reply_markup=get_main_keyboard())
            return

        # creating an inline keyboard
        inline_keyboard = types.InlineKeyboardMarkup()
        
        for day_id, day_name in days:
            button = types.InlineKeyboardButton(
                text=day_name, 
                callback_data=f"select_day_{day_id}" 
            )
            inline_keyboard.add(button)
            
        bot.send_message(message.chat.id, 
                         "Выбери день для просмотра или логгирования:", 
                         reply_markup=inline_keyboard)

    except sqlite3.Error as e:
        print(f"Ошибка при чтении дней из БД: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при получении дней.")
    finally:
        if conn:
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_day_'))
def show_day_exercises(call):
    day_id = int(call.data.split('_')[-1])
    
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT exercise_id, exercise_name FROM Exercises WHERE day_id = ?", 
            (day_id,)
        )
        exercises = cursor.fetchall()
        
        inline_keyboard = types.InlineKeyboardMarkup()
        
        # create buttons for each ex
        if exercises:
            for ex_id, ex_name in exercises:
                button = types.InlineKeyboardButton(
                    text=ex_name,
                    callback_data=f"log_ex_{ex_id}" # some necessary logs
                )
                inline_keyboard.add(button)
        
        # new button
        add_button = types.InlineKeyboardButton(
            text="➕ Добавить упражнение",
            callback_data=f"add_ex_{day_id}" 
        )
        inline_keyboard.add(add_button)
        bot.answer_callback_query(call.id)
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text="Выбери упражнение для логгирования или добавь новое:",
                              reply_markup=inline_keyboard)

    except sqlite3.Error as e:
        print(f"Ошибка при получении упражнений: {e}")
        bot.answer_callback_query(call.id, text="Ошибка!")
    finally:
        if conn:
            conn.close()

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить день")
def handle_delete_day(message):
    user_id = message.from_user.id
    
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        
        # Take the ID and name of the day from ‘workout.bd’.
        cursor.execute(
            "SELECT day_id, day_name FROM TrainingDays WHERE user_id = ?", 
            (user_id,)
        )
        days = cursor.fetchall()
        
        if not days:
            bot.send_message(message.chat.id, 
                             "Нечего удалять.", 
                             reply_markup=get_main_keyboard())
            return
        inline_keyboard = types.InlineKeyboardMarkup()
        
        for day_id, day_name in days:
            # text - what the user sees.
            # callback_data - what bot will receive. 
            # “hide” the ID of the day in callback_data
            button = types.InlineKeyboardButton(
                text=f"❌ {day_name}", 
                callback_data=f"delete_day_{day_id}"
            )
            inline_keyboard.add(button)
            
        bot.send_message(message.chat.id, 
                         "Какой день ты хочешь удалить?", 
                         reply_markup=inline_keyboard)

    except sqlite3.Error as e:
        print(f"Ошибка при получении дней для удаления: {e}")
    finally:
        if conn:
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_day_'))
def process_day_deletion(call):
    try:
        day_id_to_delete = int(call.data.split('_')[-1])
    except (ValueError, IndexError):
        bot.answer_callback_query(call.id, text="Ошибка! Неверный ID дня.")
        return

    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()

        # --- Deletion logs + ex(3 steps) ---
        cursor.execute("SELECT exercise_id FROM Exercises WHERE day_id = ?", (day_id_to_delete,))
        exercise_ids_to_delete = [row[0] for row in cursor.fetchall()]

        if exercise_ids_to_delete:
            placeholders = ','.join('?' * len(exercise_ids_to_delete))
            cursor.execute(f"DELETE FROM Logs WHERE exercise_id IN ({placeholders})", 
                           exercise_ids_to_delete)
        cursor.execute("DELETE FROM Exercises WHERE day_id = ?", (day_id_to_delete,))
        cursor.execute("DELETE FROM TrainingDays WHERE day_id = ?", (day_id_to_delete,))
        
        conn.commit()

        bot.answer_callback_query(call.id, text="День удален!")
        
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text="✅ День был успешно удален.")
        
        bot.send_message(call.message.chat.id, 
                         "Выбери следующее действие:", 
                         reply_markup=get_main_keyboard())

    except sqlite3.Error as e:
        print(f"Ошибка при удалении дня: {e}")
        bot.answer_callback_query(call.id, text="Ошибка при удалении.")
    finally:
        if conn:
            conn.close()
def save_logs_to_db(message, exercise_id, sets_to_log, existing_conn=None):
    """
    Secondary function: saves the list of sets (reps, weight) 
    to the Logs table.
    """
    conn = None
    try:
        if existing_conn:
            conn = existing_conn
        else:
            conn = sqlite3.connect('workouts.db')
        
        cursor = conn.cursor()
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        logs_data = []
        for reps, weight in sets_to_log:
            logs_data.append((exercise_id, current_date, weight, reps))
        
        # executemany - inserts all reps with one quick query
        cursor.executemany(
            "INSERT INTO Logs (exercise_id, date, weight, reps) VALUES (?, ?, ?, ?)",
            logs_data
        )
        if not existing_conn:
            conn.commit()
        if not existing_conn:
             bot.send_message(message.chat.id, 
                              f"🎉 {len(sets_to_log)} подходов записано.", 
                              reply_markup=get_main_keyboard())

    except sqlite3.Error as e:
        print(f"Ошибка сохранения лога: {e}")
        bot.send_message(message.chat.id, "Ошибка сохранения в БД!")
    finally:
        if conn and not existing_conn:
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_ex_'))
def handle_add_new_exercise(call):
    """
    Start logging NEW exercise.
    Asks the user for the full line.
    """
    day_id = int(call.data.split('_')[-1])
    
    bot.answer_callback_query(call.id)
    msg = bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text="Введи |название|, |подходы| и |веса| в одну строку:\n"
                                     "Пример: `Жим 2 20 15`\n")
    
    bot.register_next_step_handler(msg, parse_new_exercise_and_logs, day_id)


def parse_new_exercise_and_logs(message, day_id):
    parts = message.text.strip().split()
    
    # check if right format
    if not parts or len(parts) < 3:
        msg = bot.reply_to(message, "🚫 Ошибка формата Bro. \n")                              
        bot.register_next_step_handler(msg, parse_new_exercise_and_logs, day_id)
        return

    exercise_name = parts[0]
    sets_to_log = []

# validation
    try:
        common_reps = int(parts[1])
        if common_reps <= 0:
            raise ValueError("Подходы должны быть > 0")

        weights_list_str = parts[2:]
        if not weights_list_str:
            raise ValueError("Нужно указать хотя бы один вес")

        for w_str in weights_list_str:
            weight = float(w_str.replace(',', '.'))
            if weight < 0:
                raise ValueError("Вес не может быть отрицательным ಠ_ಠ")
            
            sets_to_log.append((common_reps, weight))

    except ValueError as e:
        print(f"Ошибка валидации: {e}")
        msg = bot.reply_to(message, "🚫 Ошибка формата Bro. \n")
        bot.register_next_step_handler(msg, parse_new_exercise_and_logs, day_id)
        return
    conn = None
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO Exercises (day_id, exercise_name) VALUES (?, ?)", 
            (day_id, exercise_name)
        )
        new_exercise_id = cursor.lastrowid
        # IMPORTANT: commit immediately after creating the ex
        conn.commit() 
        save_logs_to_db(message, new_exercise_id, sets_to_log, existing_conn=conn)
        conn.commit() # logs commit
        
        bot.send_message(message.chat.id, 
                         f"👍 Упражнение '{exercise_name}' добавлено и {len(sets_to_log)} подходов записано!",
                         reply_markup=get_main_keyboard())

    except sqlite3.Error as e:
        print(f"Ошибка при создании упражнения/сохранении логов: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при сохранении.")
    finally:
        if conn:
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('log_ex_'))
def show_exercise_summary(call):
    exercise_id = int(call.data.split('_')[-1])
    
    conn = None
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT exercise_name, day_id FROM Exercises WHERE exercise_id = ?", 
            (exercise_id,)
        )
        result = cursor.fetchone()
        if not result:
            bot.answer_callback_query(call.id, text="Ошибка: Упражнение не найдено.")
            return
            
        ex_name, day_id = result
    
        cursor.execute(
            "SELECT date, reps, weight FROM Logs WHERE exercise_id = ? ORDER BY date DESC",
            (exercise_id,)
        )
        logs = cursor.fetchall()
        
        response_text = f"**Упражнение: {ex_name}**\n\n"
        if not logs:
            response_text += "Записей пока нет."
            last_date_str = None
        else:
            last_date_str = logs[0][0] 
            last_date_obj = datetime.strptime(last_date_str, "%Y-%m-%d %H:%M:%S")
            
            session_logs = [log for log in logs if log[0] == last_date_str]
            
            common_reps = session_logs[0][1] 
            
            weights_list = []
            for _, _, weight in session_logs:
                weight_str = int(weight) if weight.is_integer() else weight
                weights_list.append(str(weight_str))
            
            weights_str_formatted = " ".join(weights_list)
            
            response_text += f"**Последняя запись ({last_date_obj.strftime('%Y-%m-%d')}):**\n"
            response_text += f"  `{common_reps} {weights_str_formatted}`\n"
        
        if last_date_str:
            previous_date_str = None
            previous_session_logs = []
            
            # find the first date that is NOT equal to the last date
            for log_date_str, reps, weight in logs:
                if log_date_str != last_date_str:
                    if previous_date_str is None:
                        previous_date_str = log_date_str # e.g., '2025-11-02 14:00:00'
                    
                    if log_date_str == previous_date_str:
                        previous_session_logs.append((reps, weight))
                    else:
                        break
            
            if previous_session_logs:
                previous_date_obj = datetime.strptime(previous_date_str, "%Y-%m-%d %H:%M:%S")
                
                common_reps = previous_session_logs[0][0] # (reps)
                weights_list = []
                for reps_val, weight_val in previous_session_logs:
                    weight_str = int(weight_val) if weight_val.is_integer() else weight_val
                    weights_list.append(str(weight_str))
                
                weights_str_formatted = " ".join(weights_list)
                
                response_text += f"\n**Прошлая запись ({previous_date_obj.strftime('%Y-%m-%d')}):**\n"
                response_text += f"  `{common_reps} {weights_str_formatted}`\n"

        response_text += "\nЧто делаем?"

        inline_keyboard = types.InlineKeyboardMarkup()
        
        inline_keyboard.add(types.InlineKeyboardButton(
            text="🏋️‍♂️ Записать новую тренировку",
            callback_data=f"log_new_{exercise_id}"
        ))
        
        inline_keyboard.add(types.InlineKeyboardButton(
            text="⬅️ Назад к упражнениям",
            callback_data=f"select_day_{day_id}"
        ))

        bot.answer_callback_query(call.id)
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=response_text,
                              reply_markup=inline_keyboard,
                              parse_mode="Markdown")

    except sqlite3.Error as e:
        print(f"Ошибка при получении сводки: {e}")
        bot.answer_callback_query(call.id, text="Ошибка БД.")
    finally:
        if conn:
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('log_new_'))
def handle_log_existing_exercise_new(call):
    exercise_id = int(call.data.split('_')[-1])
    
    try:
        conn = sqlite3.connect('workouts.db')
        cursor = conn.cursor()
        cursor.execute("SELECT exercise_name FROM Exercises WHERE exercise_id = ?", (exercise_id,))
        ex_name = cursor.fetchone()[0]
    except Exception:
        ex_name = "выбранное упражнение"
    finally:
        if conn:
            conn.close()

    bot.answer_callback_query(call.id)
    msg = bot.edit_message_text(chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=f"Запись для: **{ex_name}**.\n\n"
                                     f"Введи |подходы| и |веса| в одну строку:\n"
                                     "**Пример: `3 80 85 90`\n",
                                parse_mode="Markdown")
    
    # previous parser
    bot.register_next_step_handler(msg, parse_logs_for_existing_exercise, exercise_id)

def parse_logs_for_existing_exercise(message, exercise_id):
    parts = message.text.strip().split()
    
    # first check
    if not parts or len(parts) < 2:
        msg = bot.reply_to(message, "🚫 Ошибка формата. \n"
                                    "Нужен минимум: `подходы Вес`\n"
                                    "Попробуй еще раз:")
        bot.register_next_step_handler(msg, parse_logs_for_existing_exercise, exercise_id)
        return

    sets_to_log = []
    try:
        # second check
        common_reps = int(parts[0])
        if common_reps <= 0:
            raise ValueError("подходы должны быть > 0")

        # third check
        weights_list_str = parts[1:]
        if not weights_list_str:
            raise ValueError("Нужно указать хотя бы один вес")

        for w_str in weights_list_str:
            weight = float(w_str.replace(',', '.'))
            if weight < 0:
                raise ValueError("Вес не может быть отрицательным ಠ_ಠ")
            
            sets_to_log.append((common_reps, weight))

    except ValueError as e:
        print(f"Ошибка валидации: {e}")
        msg = bot.reply_to(message, "🚫 Ошибка формата Bro. \n"
                                    "Пример: `3 80 85 90`\n"
                                    "It's not that difficult. Try again:")
        bot.register_next_step_handler(msg, parse_logs_for_existing_exercise, exercise_id)
        return

    # If everything complete, save the logs.
    save_logs_to_db(message, exercise_id, sets_to_log)

# --- main part(starttttt) ---
if __name__ == '__main__':
    # init db ¯\(°_o)/¯
    init_db()
    
    # bot start(hell yeahhhh)
    print("Бот успешно запущен...")
    bot.polling(none_stop=True)