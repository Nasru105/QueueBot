FROM python:3.13-slim

WORKDIR /app

# Копируем весь проект
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Запуск бота
ENTRYPOINT ["python", "-m", "app.bot"]
