FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# паки, обложки и виджет собираются при сборке образа
RUN python make_assets.py

CMD ["python", "-u", "bot.py"]
