# STR_ReforgerWhiteList

Discord бот и REST API для управления whitelist-ом в Arma Reforger.

## Возможности
- Discord бот для управления заявками на whitelist
- REST API для проверки статуса игроков по Arma ID или Steam ID
- Два варианта установки: 
  - Классический Python (с файлом .env)
  - Docker (с настройками в docker-compose.yml)
- Хранение данных в SQLite
- Скрипт для сервера Arma Reforger

## Установка и настройка

### Вариант 1: Классическая установка (Python)

1. Клонируйте репозиторий:
```bash
git clone https://github.com/Stranni15k/STR_ReforgerWhiteList.git
cd STR_ReforgerWhiteList
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env`:
```env
# Discord Bot token (обязательно)
DISCORD_TOKEN=your_token_here

# Настройки сервера (обязательно)
GUILD_ID=your_guild_id
CHANNEL_ID=your_channel_id
ADMIN_CHANNEL_ID=your_admin_channel_id
ADMIN_ROLE=your_admin_role_id

# База данных
DATABASE_PATH=whitelist.db
```

5. Запустите сервисы:
```bash
# В разных терминалах:
python src/api.py  # REST API
python src/bot.py  # Discord бот
```

### Вариант 2: Установка через Docker

1. Клонируйте репозиторий:
```bash
git clone https://github.com/Stranni15k/STR_ReforgerWhiteList.git
cd STR_ReforgerWhiteList
```

2. Настройте переменные окружения в файле `docker-compose.yml`:
```yaml
  bot:
    environment:
      DISCORD_TOKEN: "your-discord-token"    # Токен Discord бота
      GUILD_ID: "your-guild-id"              # ID сервера
      CHANNEL_ID: "your-channel-id"          # ID канала для стартового сообщения о подаче заявок
      ADMIN_CHANNEL_ID: "your-admin-channel" # ID канала для вывода заявок для администрации
      ADMIN_ROLE: "your-admin-role"          # ID роли админа
```

3. Запустите через скрипт развертывания:
```bash
# Linux/Mac
chmod +x deploy.sh
./deploy.sh

# Windows
deploy.cmd
```