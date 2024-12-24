import os
import random
from telebot import TeleBot
from commands import commands  # Убедитесь, что команды правильно структурированы
from config import TOKEN

TOKEN = os.getenv('TOKEN') or TOKEN
bot = TeleBot(TOKEN)

Students = [
    ["Беллер Николай", "Б"],
    ["Беляев Юрий", "А"],
    ["Бобов Владислав", "А"],
    ["Виноградов Алексей", "Б"],
    ["Горшенков Артём", "Б"],
    ["Ердеков Александр", "Б"],
    ["Загибалов Артём", "Б"],
    ["Злобина Анастасия", "Б"],
    ["Капустина Мария", "А"],
    ["Касмынин Кирилл", "А"],
    ["Косарев Евгений", "А"],
    ["Ладынский Вячеслав", "Б"],
    ["Мельников Егор", "А"],
    ["Мирхабибов Бохиржон", "Б"],
    ["Насибов Руслан", "Б"],
    ["Никифоров Данил", "А"],
    ["Олеников Валерий", "А"],
    ["Смольянинова Милана", "Б"],
    ["Фокин Михаил", "А"],
    ["Фоминцов Михаил", "Б"],
    ["Яфаев Алексей", "А"]
]


@bot.message_handler(commands=['generate_queue'])
def generate_queue(message):
    # Перемешиваем студентов без повторений
    random_students = random.sample(Students, len(Students))

    # Формируем сообщение с перемешанным списком студентов
    list_of_students = ""
    for i in range(len(random_students)):
        # Выводим имя студента и его оценку
        list_of_students += f"{i + 1}: {random_students[i][0]}\n"

    # Отправляем сообщение пользователю
    bot.send_message(message.chat.id, list_of_students)


@bot.message_handler(commands=['generate_b_queue'])
def generate_b_queue(message):
    # Перемешиваем студентов без повторений
    random_students = random.sample(Students, len(Students))

    list_of_students = ""
    i=0
    for student in random_students:
        if student[1] == "Б":
            i+=1
            list_of_students += f"{i}. {student[0]}\n"

    # Проверяем, что список студентов не пуст
    if list_of_students.strip():
        bot.send_message(message.chat.id, list_of_students)
    else:
        bot.send_message(message.chat.id, "Нет студентов с оценкой 'Б'.")


@bot.message_handler(commands=['generate_a_queue'])
def generate_a_queue(message):
    # Перемешиваем студентов без повторений
    random_students = random.sample(Students, len(Students))

    list_of_students = ""
    i=0
    for student in random_students:
        if student[1] == "А":
            i+=1
            list_of_students += f"{i}. {student[0]}\n"

    # Проверяем, что список студентов не пуст
    if list_of_students.strip():
        bot.send_message(message.chat.id, list_of_students)
    else:
        bot.send_message(message.chat.id, "Нет студентов с оценкой 'Б'.")


if __name__ == "__main__":
    bot.set_my_commands(commands)
    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=[],
    )
