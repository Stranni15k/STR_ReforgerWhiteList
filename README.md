# STR_ReforgerWhiteList

Discord-бот и скрипт для Arma Reforger, управляющий **вайтлистом игроков**.

## Возможности
- Отправка заявок на вайтлист через Discord  
- Одобрение/удаление/редактирование игроков (админами)  
- Хранение данных в SQLite  
- Скрипт для сервера Arma Reforger, проверяющий игроков в списке  

## Установка
```bash
git clone https://github.com/Stranni15k/STR_ReforgerWhiteList.git
cd STR_ReforgerWhiteList
pip install -r requirements.txt
```

Создай `.env`:
```
# Discord Bot token (обязательно)
DISCORD_TOKEN=

# Опционально: ID сервера для быстрой синхронизации слэш-команд (один ID)
GUILD_ID=

# Обязательно: канал по умолчанию для публикации сообщения с кнопкой
CHANNEL_ID=

# Обязательно: канал по умолчанию для публикации заявок для решений администрации по заявкам
ADMIN_CHANNEL_ID=

# Обязательно: ID роли администратора, для управления заявками
ADMIN_ROLE=

# Путь к файлу SQLite базы
DATABASE_PATH=whitelist.db
```

## Запуск
```bash
python -m src
```

## Структура
- `src/` — Discord-бот (Python)  
- `Scripts/Game/Whitelist/` — скрипт для Reforger  
