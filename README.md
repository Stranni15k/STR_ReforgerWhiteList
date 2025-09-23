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
# пример: 123456789012345678
GUILD_ID=

# Опционально: канал по умолчанию для публикации сообщения с кнопкой
# пример: 123456789012345678
CHANNEL_ID=

# Опционально: список Discord ID админов через запятую (для управления в ЛС)
# пример: 111111111111111111,222222222222222222
ADMIN_IDS=

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
