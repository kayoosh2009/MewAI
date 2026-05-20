# Используем официальный легкий образ Python
FROM python:3.10-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /code

# Копируем файл зависимостей (если его нет, мы установим всё напрямую ниже)
# Но лучше зафиксировать их
RUN pip install --no-cache-dir fastapi uvicorn supabase python-dotenv ollama postgrest

# Копируем все файлы проекта в контейнер
COPY . .

# Hugging Face Spaces требует, чтобы контейнер слушал порт 7860
EXPOSE 7860

# Запускаем Uvicorn, указывая порт 7860, который ожидает Hugging Face
CMD ["uvicorn", "py.main:app", "--host", "0.0.0.0", "--port", "7860"]