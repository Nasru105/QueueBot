from telebot.types import BotCommand

commands = [
    BotCommand("start", "Запустить бота"),
    BotCommand("generate_queue", "Сгенерировать очередь"),
    BotCommand("generate_b_queue", "Сгенерировать очередь для группы Б"),
    BotCommand("generate_a_queue", "Сгенерировать очередь для группы А"),
]