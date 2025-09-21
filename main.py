import os
import telebot
import psycopg2 as ps
import datetime
import bcrypt
import requests

from telebot import types
from psycopg2 import Error
from dotenv import load_dotenv

# load protected variables
load_dotenv('info.env')

# API of Telegram chatbot
API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)

# variables that may change through the way of development
category_icon = os.getenv('CATEGORY_ICON')
admin = os.getenv('ADMIN')
worker = os.getenv('WORKER')
user = os.getenv('USER')

URL = os.getenv('URL')

salt = os.urandom(32)

# connecting to DB
try:
    connection = ps.connect(user=os.getenv('DT_USER'),
                            password=os.getenv('DT_PASS'),
                            host=os.getenv('DT_HOST'),
                            port=os.getenv('DT_PORT'),
                            database=os.getenv('DT'))
    cursor = connection.cursor()
    print("Connected to DB")
except (Exception, Error) as error:
    print("Error connecting to DB:", error)

# global variables
is_user_typing_text = False
is_user_typing_category = False
is_worker_contact = False
is_user_choosing_category = False
user_location = user_photo = user_text = 'null'
category_id = 1
role_name = user

# bot.send_message(message.from_user.id, f'Привіт, {message.from_user.first_name}!', reply_markup=markup)
# bot.send_message(message.from_user.id, "Щоб продовжити, надайте мені номер свого телефону.\nЦе необхідно для "
#                                          "того, аби я Вам не докучав наступного разу.", reply_markup=markup)



# welcome message for new user
def hello(message, markup):
    btn1 = types.KeyboardButton("Надати номер телефону", request_contact=True)
    markup.add(btn1)
    bot.send_message(message.from_user.id, f'Hi, {message.from_user.first_name}!', reply_markup=markup)
    bot.send_message(message.from_user.id, "To continue, give me your phone number, so that I don't bother you next time.", reply_markup=markup)


# function that shows user's role
def show_user_role(message):
    if role_name == admin:
        bot.send_message(message.from_user.id, "Ви - Адміністратор")
    elif role_name == worker:
        bot.send_message(message.from_user.id, "Ви - Працівник комунального підприємства")
    else:
        bot.send_message(message.from_user.id, "Ви - Звичайний користувач")


# first bot command
@bot.message_handler(commands=['start'])
def start(message):
    # check for user
    cursor.execute(f"SELECT * FROM \"user\" WHERE id = {message.from_user.id}")
    result = cursor.fetchone()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # non registered user
    if result is None:
        # first time welcoming
        hello(message, markup)

    # user or admin or worker
    else:
        # getting role_name of current user
        cursor.execute(f"SELECT name FROM role WHERE id = '{result[5]}'")
        global role_name
        role_name = cursor.fetchone()[0]

        add_buttons_to_start_menu(markup)
        show_user_role(message)
        bot.send_message(message.from_user.id, "Оберіть опцію меню", reply_markup=markup)


# function that adds buttons to start menu
def add_buttons_to_start_menu(markup):
    btn1 = types.KeyboardButton("Повідомити про проблему")
    markup.add(btn1)

    if role_name == admin:
        btn2 = types.KeyboardButton("Додати працівника комунального підприємства")
        btn3 = types.KeyboardButton("Додати категорію проблеми")
        markup.add(btn2)
        markup.add(btn3)
    elif role_name == worker:
        btn2 = types.KeyboardButton("Додати категорію проблеми")
        markup.add(btn2)


# dispatcher for every pressed button
@bot.message_handler(content_types=['text'])
def add_info(message):
    if message.text == 'Повідомити про проблему':
        menu(message)
    elif message.text == 'Додати опис':
        bot.send_message(message.from_user.id, 'Коротко опишіть проблему:')
        global is_user_typing_text
        is_user_typing_text = True
    elif message.text == 'Прикріпити фотографію':
        bot.send_message(message.from_user.id, 'Натисніть на булавку в нижній частині екрану та оберіть відповідне '
                                               'фото:')
    elif message.text == 'Обрати категорію':
        global is_user_choosing_category
        is_user_choosing_category = True
        show_category_list(message)
    elif message.text == 'Надіслати':
        send_problem_info(message)
    elif message.text == 'Повернутися назад':
        return_back(message)
    elif message.text == 'Додати працівника комунального підприємства':
        global is_worker_contact
        is_worker_contact = True
        bot.send_message(message.from_user.id, 'Натисніть на булавку в нижній частині екрану та виберіть розділ '
                                               '"Контакт". Поділіться контактом людини, яка є працівником '
                                               'комунального підприємства.')
    elif message.text == 'Додати категорію проблеми':
        global is_user_typing_category
        is_user_typing_category = True
        bot.send_message(message.from_user.id, 'Введіть назву категорії проблеми:')
    else:
        get_other_user_info(message)


# send problem info to DB
def send_problem_info(message):
    if user_location != 'null':
        filepath = 'null'
        if user_photo != 'null':
            file_id = user_photo[-1].file_id
            file = bot.get_file(file_id)
            filepath = file.file_path

            downloaded_file = bot.download_file(filepath)
            filepath = filepath.split("/", 1)
            with open(filepath[1], 'wb') as new_file:
                new_file.write(downloaded_file)

            files = {'image': open(filepath[1].encode(), 'rb')}
            response = requests.post(url=URL, files=files)
            print(response.status_code)

            if response.status_code == 200:
                response_data = response.json()
                filepath = response_data.get('url')
                print(filepath)

        insert_q = "INSERT INTO problem_info_point (img, description, user_id, geom, \"createdAt\", \"updatedAt\", " \
                   "\"categoryProblemId\") VALUES (%s, %s, %s, ST_GeomFromText('POINT(%s %s)', 4326), %s, %s, %s)"
        cursor.execute(insert_q, (filepath, user_text, message.chat.id, user_location.longitude, user_location.latitude,
                                  datetime.datetime.now(), datetime.datetime.now(), category_id))
        connection.commit()

        bot.send_message(message.from_user.id,
                         "Дякую за те, що повідомили про проблему. Зробимо наше місто кращим разом!")
        return_back(message)

    else:
        bot.send_message(message.from_user.id,
                         "На жаль Ви не можете повідомити про проблему, не надавши свою геолокацію.")


# show category list for use to choose one
def show_category_list(message):
    markup_category = types.ReplyKeyboardMarkup(resize_keyboard=True)
    cursor.execute("SELECT name FROM category_problem ORDER BY id ASC")
    for record in cursor:
        btn = types.KeyboardButton(str(record[0]))
        markup_category.add(btn)
    bot.send_message(message.from_user.id, "Оберіть категорію із наявних у списку. Якщо такої немає, то виберіть "
                                           "\"Інше\".", reply_markup=markup_category)


# return_back button in menu
def return_back(message):
    reset_globals()
    telebot.types.ReplyKeyboardRemove()

    markup_back = types.ReplyKeyboardMarkup(resize_keyboard=True)
    add_buttons_to_start_menu(markup_back)
    bot.send_message(message.from_user.id, "Чекаю на Вас наступного разу.", reply_markup=markup_back)


# menu for 'sharing problem'
def menu(message):
    reset_is_user_typing_text()
    reset_is_user_typing_category()
    reset_is_worker_contact()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Надати адресу", request_location=True)
    btn2 = types.KeyboardButton("Додати опис")
    btn3 = types.KeyboardButton("Прикріпити фотографію")
    btn4 = types.KeyboardButton("Обрати категорію")
    btn5 = types.KeyboardButton("Надіслати")
    btn6 = types.KeyboardButton("Повернутися назад")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5)
    markup.add(btn6)
    bot.send_message(message.from_user.id, "Оберіть опцію меню", reply_markup=markup)


# hash password before adding to DB
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ---------- FROM USER INFO GETTERS ------------

# receiving user or worker contact
@bot.message_handler(content_types=['contact'])
def get_contact(message):

    if is_worker_contact:
        print(f"worker: {message.contact}")

        cursor.execute(f"SELECT * FROM \"user\" WHERE id = {message.contact.user_id}")
        result = cursor.fetchone()

        cursor.execute(f"SELECT id FROM role WHERE name = '{worker}'")
        worker_id = cursor.fetchone()[0]

        if result is None:
            # insert user to database
            # id, email, password, createdAt, updatedAt, roleId
            cursor.execute(f"INSERT INTO \"user\" VALUES ('{message.contact.user_id}',"
                           f"'{message.contact.first_name}','{hash_password(message.contact.phone_number)}',"
                           f"'{datetime.datetime.now()}','{datetime.datetime.now()}','{worker_id}')")
            connection.commit()

        else:
            cursor.execute(f"UPDATE \"user\" SET \"roleId\" = {worker_id} WHERE id = {message.contact.user_id}")
            connection.commit()

        bot.send_message(message.from_user.id, "Працівник комунального підприємства доданий.")
        reset_is_worker_contact()

    else:
        print(f"user: {message.contact}")

        # find id of role 'user'
        cursor.execute(f"SELECT id FROM role WHERE name = '{user}'")
        role_id = cursor.fetchone()[0]

        # insert user to database
        # id, email, password, createdAt, updatedAt, roleId
        cursor.execute(f"INSERT INTO \"user\" VALUES ('{message.from_user.id}',"
                       f"'{message.from_user.first_name}','{hash_password(message.contact.phone_number)}',"
                       f"'{datetime.datetime.now()}','{datetime.datetime.now()}','{role_id}')")
        connection.commit()
        show_user_role(message)

        # continue with user
        telebot.types.ReplyKeyboardRemove()
        markup_problem = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton("Повідомити про проблему")
        markup_problem.add(btn1)
        bot.send_message(message.from_user.id, f"Дякую, {message.from_user.first_name}!\nЯкщо Ви "
                                               f"хочете повідомити про проблему, то натисніть відповідну клавішу меню. "
                                               f"Якщо не виявили проблему зараз, то повертайтеся коли вона з'явиться.",
                         reply_markup=markup_problem)


# receiving user_location
@bot.message_handler(content_types=['location'])
def get_geo(message):
    set_user_location(message.location)
    print(f"user location: {user_location}")
    bot.send_message(message.from_user.id, "Адресу отримав.")


# receiving user_photo
@bot.message_handler(content_types=['photo'])
def get_photo(message):
    set_user_photo(message.photo)
    print(f"user photo: {user_photo}")
    bot.send_message(message.from_user.id, "Фото отримав.")


# receiving user_text
def get_text_messages(record):
    if is_user_typing_text:
        set_user_text(record)
        print(f"user description: {user_text}")


# get entered user text or chosen category
def get_other_user_info(message):
    # user entering text
    if is_user_typing_text:
        get_text_messages(message.text)
        bot.send_message(message.from_user.id, "Опис отримав.")
        reset_is_user_typing_text()

    # user entering category name
    elif is_user_typing_category:
        category_name = message.text
        print(f"user entered category: {category_name}")

        cursor.execute(f"SELECT * FROM category_problem WHERE name = '{category_name}'")
        result = cursor.fetchone()

        if result is None:
            cursor.execute(f"INSERT INTO category_problem (name, layer_img) VALUES ('{category_name}', '{category_icon}')")
            connection.commit()
            bot.send_message(message.from_user.id, "Категорія додана.")
        else:
            bot.send_message(message.from_user.id, "Така категорія вже існує.")

        reset_is_user_typing_category()

    # user choose category
    elif is_user_choosing_category:
        cursor.execute(f"SELECT id FROM category_problem WHERE name = '{message.text}'")
        category_id_from_db = cursor.fetchone()[0]
        set_category_id(category_id_from_db)
        print(f"user chosen category: {message.text}")
        bot.send_message(message.from_user.id, "Категорію отримав.")
        menu(message)

        reset_is_user_choosing_category()


# ---------- GLOBAL SETTERS ------------

# global setter for variable user_location
def set_user_location(location):
    global user_location
    user_location = location


# global setter for variable user_photo
def set_user_photo(photo):
    global user_photo
    user_photo = photo


# global setter for variable user_text
def set_user_text(message):
    global user_text
    user_text = message


# global setter for variable category_id
def set_category_id(record):
    global category_id
    category_id = record


# --------- GLOBAL RESET ------------------

# give variable is_user_choosing_category her default value
def reset_is_user_choosing_category():
    global is_user_choosing_category
    is_user_choosing_category = False


# give variable is_user_typing_text her default value
def reset_is_user_typing_text():
    global is_user_typing_text
    is_user_typing_text = False


# give variable is_user_typing_category her default value
def reset_is_user_typing_category():
    global is_user_typing_category
    is_user_typing_category = False


# give variable is_worker_contact her default value
def reset_is_worker_contact():
    global is_worker_contact
    is_worker_contact = False


# give global variables their default values
def reset_globals():
    global user_location, user_photo, user_text, category_id
    reset_is_user_typing_text()
    reset_is_user_typing_category()
    reset_is_worker_contact()
    reset_is_user_choosing_category()
    user_location = user_photo = user_text = 'null'
    category_id = 1


# heart of bot
bot.polling(none_stop=True, interval=0)
