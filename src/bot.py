import asyncio
from typing import Optional
import re
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore

import discord
from discord import app_commands
from discord.ext import commands

from src.config import get_settings
from src.db import Database, ApplicationStatus


INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True


try:
    ZONE_MOSCOW = ZoneInfo("Europe/Moscow") if ZoneInfo is not None else timezone(timedelta(hours=3))
except Exception:
    ZONE_MOSCOW = timezone(timedelta(hours=3))


def to_unix_msk(sqlite_text: str) -> int:
    """Convert SQLite UTC timestamp text (YYYY-MM-DD HH:MM:SS) to Unix seconds in MSK."""
    try:
        dt_naive = datetime.strptime(sqlite_text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt_naive = datetime.fromisoformat(sqlite_text.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return int(datetime.now(tz=ZONE_MOSCOW).timestamp())
    dt_utc = dt_naive.replace(tzinfo=timezone.utc)
    dt_msk = dt_utc.astimezone(ZONE_MOSCOW)
    return int(dt_msk.timestamp())


STATUS_TEXT = {
    "pending": "В ожидании",
    "approved": "Подтверждена",
    "rejected": "Отклонена",
    "needs_fix": "На доработку",
}

STATUS_COLOR = {
    "pending": 0xF39C12,
    "approved": 0x27AE60,
    "rejected": 0xE74C3C,
    "needs_fix": 0xF39C12,
}

STATUS_EMOJI = {
    "pending": "⏳",
    "approved": "✅",
    "rejected": "❌",
    "needs_fix": "🔧",
}


def get_status_ui(status: str) -> tuple[str, str, int]:
    """Return (emoji, text, color) for a status with sane defaults."""
    return (
        STATUS_EMOJI.get(status, "❓"),
        STATUS_TEXT.get(status, status),
        STATUS_COLOR.get(status, 0x95A5A6),
    )


class ApplicationModal(discord.ui.Modal):
    def __init__(self, db: Database, is_resubmit: bool = False, original_app_id: int = None, original_data: dict = None):
        super().__init__(title="Заявка на Whitelist")
        self.db = db
        self.is_resubmit = is_resubmit
        self.original_app_id = original_app_id

        if original_data is None:
            original_data = {}

        self.nickname = discord.ui.TextInput(
            label="Никнейм",
            placeholder="Ваш ник",
            required=True,
            max_length=64,
            default=original_data.get('nickname', '')
        )
        self.armaid = discord.ui.TextInput(
            label="Arma ID",
            placeholder="Ваш Arma Reforger ID",
            required=True,
            max_length=64,
            default=original_data.get('armaid', '')
        )
        self.platform = discord.ui.TextInput(
            label="Платформа",
            placeholder="PC/Xbox",
            required=True,
            max_length=32,
            default=original_data.get('platform', '')
        )
        self.steamid = discord.ui.TextInput(
            label="SteamID",
            placeholder="64-bit SteamID (если есть)",
            required=True,
            max_length=32,
            default=original_data.get('steamid', '')
        )

        self.add_item(self.nickname)
        self.add_item(self.armaid)
        self.add_item(self.platform)
        self.add_item(self.steamid)

        if is_resubmit:
            self.title = "Повторная подача заявки"

    async def on_submit(self, interaction: discord.Interaction):
        assert interaction.user is not None
        user_id = interaction.user.id
        nickname = str(self.nickname).strip()
        armaid = str(self.armaid).strip()
        platform_input = str(self.platform).strip()
        steamid = str(self.steamid).strip()

        platform_norm = platform_input.upper()
        if platform_norm not in {"PC", "XBOX", "PS"}:
            embed = discord.Embed(
                title="Ошибка в поле 'Платформа'",
                description="Пожалуйста, укажите платформу из списка ниже.",
                color=0xe74c3c
            )
            embed.add_field(name="Допустимые значения", value="PC, XBOX, PS", inline=False)
            embed.set_footer(text="Подсказка: можно вводить в любом регистре")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        steam_lower = steamid.lower()
        if steam_lower.startswith("http://") or steam_lower.startswith("https://") or "steamcommunity" in steam_lower:
            embed = discord.Embed(
                title="Ошибка в поле 'SteamID'",
                description="Обнаружена ссылка. Укажите сам идентификатор, а не URL.",
                color=0xe74c3c
            )
            embed.add_field(name="Пример SteamID64", value="76561198000000000", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        valid_steam = bool(re.fullmatch(r"\d{17}", steamid)) or bool(re.fullmatch(r"STEAM_[0-5]:[01]:\d+", steamid, flags=re.IGNORECASE))
        if not valid_steam:
            embed = discord.Embed(
                title="Ошибка в поле 'SteamID'",
                description="Похоже, формат указан неверно.",
                color=0xe74c3c
            )
            embed.add_field(name="Ожидаемые форматы", value="SteamID64: 17 цифр", inline=False)
            embed.add_field(name="Примеры", value="76561198000000000", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if self.is_resubmit and self.original_app_id:
            fields = {
                "username": nickname,
                "arma_id": armaid,
                "platform": platform_norm,
                "steam_id": steamid,
                "admin_comment": None
            }
            await self.db.update_fields(self.original_app_id, fields)
            await self.db.update_status(self.original_app_id, "pending")

            embed = discord.Embed(
                title="Заявка обновлена",
                description=f"**ID заявки:** #{self.original_app_id}\n**Статус:** ⏳ Ожидание (повторно)\n\nВаша заявка была успешно обновлена и отправлена на повторное рассмотрение.",
                color=0xf39c12,
                timestamp=discord.utils.utcnow()
            )
        else:
            app_id = await self.db.create_application(
                user_id=user_id,
                username=nickname,
                arma_id=armaid,
                platform=platform_norm,
                steam_id=steamid,
            )

            embed = discord.Embed(
                title="Заявка отправлена",
                description=f"**ID заявки:** #{app_id}\n**Статус:** ⏳ Ожидание\n\nСпасибо за подачу заявки! Ваша заявка будет рассмотрена в ближайшее время.",
                color=0x27ae60,
                timestamp=discord.utils.utcnow()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class ApplyView(discord.ui.View):
    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.primary, custom_id="apply_button")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        existing_app = await self.db.get_user_latest_application(interaction.user.id)
        if existing_app:
            status_text = {
                "pending": "В ожидании",
                "approved": "Подтверждена",
                "rejected": "Отклонена",
                "needs_fix": "На доработку"
            }

            embed = discord.Embed(
                title="У вас уже есть заявка",
                description=f"**Заявка #{existing_app.id}** - **{status_text.get(existing_app.status, existing_app.status)}**\n\nОдин пользователь может иметь только одну активную заявку.",
                color=0xf39c12
            )

            if existing_app.status in ("rejected", "needs_fix"):
                embed.add_field(
                    name="Требуется действие",
                    value="Используйте команду `/resubmit` для повторной подачи заявки с исправлениями.",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Проверка статуса",
                    value="Используйте команду `/status` для просмотра подробной информации о заявке.",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_modal(ApplicationModal(self.db))


class WhitelistBot(commands.Bot):
    def __init__(self, db: Database):
        super().__init__(command_prefix=commands.when_mentioned_or("!"), intents=INTENTS)
        self.db = db
        self.add_view(ApplyView(self.db))

    async def setup_hook(self) -> None:
        settings = get_settings()
        try:
            await self.tree.sync()
            if settings.guild_id:
                guild = discord.Object(id=settings.guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
        except Exception:
            pass

    async def on_ready(self) -> None:
        print(f"Bot is running as {self.user}")
        await self.ensure_application_message()

    async def on_message(self, message):
        if message.author.bot:
            return

        if not isinstance(message.channel, discord.DMChannel):
            return

        content = (message.content or "").strip()
        if not content.startswith("!"):
            return

        settings = get_settings()
        if message.author.id not in settings.admin_ids:
            return

        await self.handle_admin_command(message)

    async def ensure_application_message(self) -> None:
        settings = get_settings()
        if not settings.channel_id:
            return

        try:
            channel = self.get_channel(settings.channel_id)
            if not channel:
                return

            found_existing = False
            async for message in channel.history(limit=5):
                if (message.author == self.user and
                    message.embeds and
                    len(message.embeds) > 0 and
                    "Whitelist" in message.embeds[0].title and
                    message.components):
                    found_existing = True
                    break

            if not found_existing:
                view = ApplyView(self.db)
                embed = discord.Embed(
                    title="Whitelist заявки - Arma Reforger",
                    description=(
                        "**Добро пожаловать!**\n\n"
                        "Для получения доступа на сервер, необходимо подать заявку в whitelist.\n"
                        "Нажмите кнопку ниже и заполните форму с вашими данными."
                    ),
                    color=0x27ae60,
                    timestamp=discord.utils.utcnow()
                )

                embed.add_field(
                    name="Что нужно указать",
                    value=(
                        "• **Никнейм** - ваш игровой ник\n"
                        "• **Arma ID** - ваш ID в Arma Reforger\n"
                        "• **Платформа** - PC или Xbox\n"
                        "• **Steam ID** - ваш Steam ID (если есть)"
                    ),
                    inline=False
                )

                embed.set_footer(text="Whitelist Bot • Arma Reforger")
                await channel.send(embed=embed, view=view)
            else:
                pass

        except Exception:
            pass

    async def handle_admin_command(self, message):
        """Обработка админских команд в личных сообщениях"""
        content = message.content.strip()

        if content == "!list":
            await self.admin_list_applications(message)
        elif content == "!help":
            await self.admin_help(message)
        elif content.startswith("!view "):
            app_id = content[6:].strip()
            if app_id.isdigit():
                await self.admin_view_application(message, int(app_id))
            else:
                await message.reply("Неверный ID заявки. Используйте: `!view 123`")
        elif content.startswith("!approve "):
            parts = content[9:].strip().split(" ", 1)
            if parts[0].isdigit():
                await self.admin_update_status(message, int(parts[0]), "approved", parts[1] if len(parts) > 1 else None)
            else:
                await message.reply("Неверный ID заявки. Используйте: `!approve 123 [комментарий]`")
        elif content.startswith("!reject "):
            parts = content[8:].strip().split(" ", 1)
            if parts[0].isdigit():
                await self.admin_update_status(message, int(parts[0]), "rejected", parts[1] if len(parts) > 1 else None)
            else:
                await message.reply("Неверный ID заявки. Используйте: `!reject 123 [комментарий]`")
        elif content.startswith("!fix "):
            parts = content[5:].strip().split(" ", 1)
            if parts[0].isdigit():
                await self.admin_update_status(message, int(parts[0]), "needs_fix", parts[1] if len(parts) > 1 else None)
            else:
                await message.reply("Неверный ID заявки. Используйте: `!fix 123 [комментарий]`")
        else:
            await message.reply("Неизвестная команда. Используйте `!help` для справки.")

    async def admin_list_applications(self, message):
        """Показать список всех заявок"""
        try:
            apps_all = await self.db.list_applications(limit=100)
            apps = [a for a in apps_all if a.status != "approved"]
            if not apps:
                embed = discord.Embed(title="Список заявок", description="Заявок пока нет.", color=0x3498db)
                await message.reply(embed=embed)
                return
            
            embed = discord.Embed(title="Список заявок (ожидают обработки)", color=0x3498db)
            lines = []
            for app in apps[:20]:
                status_name = STATUS_TEXT.get(app.status, app.status)
                created_rel = f"<t:{to_unix_msk(app.created_at)}:R>"
                lines.append(f"#{app.id} — {app.username} (<@{app.user_id}>) — {status_name} — {created_rel}")
            embed.description = "\n".join(lines)
            if len(apps) > 20:
                embed.set_footer(text=f"Показаны первые 20 из {len(apps)}. Используйте !view <id> для подробностей")
            else:
                embed.set_footer(text="Используйте !view <id> для подробной информации")
            await message.reply(embed=embed)
        except Exception as e:
            await message.reply(f"Ошибка при получении списка: {e}")

    async def admin_view_application(self, message, app_id: int):
        """Показать подробную информацию о заявке"""
        app = await self.db.get_application(app_id)
        if not app:
            await message.reply(f"Заявка #{app_id} не найдена.")
            return

        emoji, text, color = get_status_ui(app.status)
        embed = discord.Embed(title=f"Заявка #{app.id}", description=f"**Статус:** {emoji} {text}", color=color)

        embed.add_field(
            name="Информация о заявителе",
            value=f"**Никнейм:** {app.username}\n**Discord:** <@{app.user_id}>\n**ID пользователя:** `{app.user_id}`",
            inline=False
        )

        embed.add_field(
            name="Игровые данные",
            value=f"**Arma ID:** `{app.arma_id}`\n**Платформа:** `{app.platform}`\n**Steam ID:** `{app.steam_id}`",
            inline=False
        )

        embed.add_field(
            name="Временные метки",
            value=f"**Создано:** <t:{to_unix_msk(app.created_at)}:R>\n**Обновлено:** <t:{to_unix_msk(app.updated_at)}:R>",
            inline=False
        )

        if app.admin_comment:
            embed.add_field(name="Комментарий администратора", value=f"```{app.admin_comment}```", inline=False)

        if app.admin_id:
            admin_user = self.get_user(app.admin_id)
            admin_name = admin_user.display_name if admin_user else f"ID: {app.admin_id}"
            embed.add_field(name="Обработал администратор", value=f"**{admin_name}** (<@{app.admin_id}>)", inline=False)

        embed.set_footer(text="Используйте !approve/!reject/!fix <id> [комментарий] для изменения статуса")
        await message.reply(embed=embed)

    async def admin_update_status(self, message, app_id: int, status: str, comment: Optional[str] = None):
        """Обновить статус заявки"""
        app = await self.db.get_application(app_id)
        if not app:
            await message.reply(f"Заявка #{app_id} не найдена.")
            return

        if status == "approved":
            comment = "Пользователь находится в Whitelist"

        success = await self.db.update_status_with_comment(app_id, status, comment, message.author.id)
        if not success:
            await message.reply(f"Ошибка при обновлении заявки #{app_id}.")
            return

        await self.notify_user_status_change(app, status, comment)

        action_text = {"approved": "одобрена", "rejected": "отклонена", "needs_fix": "отправлена на доработку"}
        embed = discord.Embed(title="Статус заявки обновлен", description=f"Заявка #{app_id} {action_text.get(status, status)}", color=STATUS_COLOR.get(status, 0x27AE60))

        if comment:
            embed.add_field(name="Комментарий", value=f"```{comment}```", inline=False)

        embed.set_footer(text=f"Пользователь {app.username} получил уведомление")
        await message.reply(embed=embed)

    async def notify_user_status_change(self, app, new_status: str, comment: Optional[str] = None):
        """Уведомить пользователя об изменении статуса заявки"""
        user = self.get_user(app.user_id)
        if not user:
            return

        status_info = {
            "approved": ("одобрена", 0x27ae60),
            "rejected": ("отклонена", 0xe74c3c),
            "needs_fix": ("отправлена на доработку", 0xf39c12)
        }

        text, color = status_info.get(new_status, (new_status, 0x95a5a6))

        embed = discord.Embed(
            title="Статус вашей заявки изменен",
            description=f"**Заявка #{app.id}** **{text}**",
            color=color
        )

        if new_status == "approved":
            embed.add_field(name="Поздравляем!", value="Вы успешно добавлены в Whitelsit", inline=False)
        else:
            if comment:
                embed.add_field(name="Комментарий администратора", value=f"```{comment}```", inline=False)

        admin_user = self.get_user(app.admin_id) if app.admin_id else None
        if admin_user:
            embed.add_field(name="Обработал", value=f"**{admin_user.display_name}**", inline=False)

        if new_status == "needs_fix":
            embed.add_field(name="Что делать дальше", value="Исправьте указанные замечания и используйте команду `/resubmit` для повторной подачи заявки.", inline=False)
        elif new_status == "rejected":
            embed.add_field(name="Что делать дальше", value="Вы можете подать новую заявку, используя команду `/resubmit`.", inline=False)
        elif new_status == "approved":
            pass

        embed.set_footer(text="Whitelist Bot • Arma Reforger")
        await user.send(embed=embed)

    async def admin_help(self, message):
        """Показать справку по админским командам"""
        embed = discord.Embed(title="Админские команды", description="Команды для управления заявками на whitelist", color=0x3498db)

        embed.add_field(name="Просмотр заявок", value="`!list` - показать последние 10 заявок\n`!view <id>` - подробная информация о заявке", inline=False)
        embed.add_field(name="Управление статусами", value="`!approve <id> [комментарий]` - одобрить заявку\n`!reject <id> [комментарий]` - отклонить заявку\n`!fix <id> [комментарий]` - отправить на доработку", inline=False)
        embed.add_field(name="Примеры", value="`!view 123`\n`!approve 123 Отличный игрок!`\n`!fix 123 Укажите правильный Steam ID`", inline=False)
        embed.set_footer(text="Все команды работают только в личных сообщениях с ботом")
        await message.reply(embed=embed)


def build_bot(db: Database) -> WhitelistBot:
    bot = WhitelistBot(db)

    @bot.tree.command(name="status", description="Показать статус вашей заявки")
    async def status_slash(interaction: discord.Interaction):
        app = await db.get_user_latest_application(interaction.user.id)
        if not app:
            embed = discord.Embed(title="Заявка не найдена", description="У вас пока нет заявок на whitelist.\n\nИспользуйте кнопку **\"Подать заявку\"** для создания новой заявки.", color=0xe74c3c)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        emoji, text, color = get_status_ui(app.status)
        embed = discord.Embed(title=f"Заявка #{app.id}", description=f"**Статус:** {emoji} {text}", color=color)

        embed.add_field(name="Информация о игроке", value=f"**Никнейм:** {app.username}\n**Discord:** <@{app.user_id}>", inline=False)
        embed.add_field(name="Игровые данные", value=f"**Arma ID:** `{app.arma_id}`\n**Платформа:** `{app.platform}`\n**Steam ID:** `{app.steam_id}`", inline=False)
        

        if app.status != "approved" and app.admin_comment:
            embed.add_field(name="Комментарий администратора", value=f"```{app.admin_comment}```", inline=False)

        if app.status == "needs_fix":
            embed.add_field(name="Требуется действие", value="Ваша заявка требует доработки.\nИспользуйте команду `/resubmit` для повторной подачи с исправлениями.", inline=False)
        elif app.status == "rejected":
            embed.add_field(name="Заявка отклонена", value="К сожалению, ваша заявка была отклонена.\nИспользуйте команду `/resubmit` для подачи новой заявки.", inline=False)

        embed.set_footer(text="Whitelist Bot • Arma Reforger")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="resubmit", description="Повторная подача заявки (если отклонена/на доработку)")
    async def resubmit_slash(interaction: discord.Interaction):
        app = await db.get_user_latest_application(interaction.user.id)
        if not app:
            embed = discord.Embed(title="Заявка не найдена", description="У вас нет заявок для повторной подачи.\n\nСначала создайте заявку с помощью кнопки **\"Подать заявку\"**.", color=0xe74c3c)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if app.status not in ("rejected", "needs_fix"):
            status_text = {"pending": "В ожидании", "approved": "Подтверждена"}
            embed = discord.Embed(title="Заявка не требует переподачи", description=f"Текущий статус: **{status_text.get(app.status, app.status)}**\n\nПовторная подача доступна только для отклоненных заявок или заявок на доработку.", color=0x3498db)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        modal = ApplicationModal(db, is_resubmit=True, original_app_id=app.id, original_data={'nickname': app.username, 'armaid': app.arma_id, 'platform': app.platform, 'steamid': app.steam_id})
        await interaction.response.send_modal(modal)

    @bot.tree.command(name="help", description="Показать справку по командам")
    async def help_slash(interaction: discord.Interaction):
        embed = discord.Embed(title="Whitelist Bot - Справка", description="**Добро пожаловать в систему управления заявками на whitelist!**\n\nЗдесь вы можете подать заявку на получение доступа к серверу Arma Reforger.", color=0x3498db)

        embed.add_field(name="Доступные команды", value="`/status` - Показать статус вашей заявки\n`/resubmit` - Повторная подача заявки\n`/help` - Показать эту справку", inline=False)
        embed.add_field(name="Как подать заявку", value="1. Найдите сообщение с кнопкой **\"Подать заявку\"**\n2. Нажмите на кнопку и заполните форму\n3. Дождитесь рассмотрения заявки\n4. Проверяйте статус командой `/status`", inline=False)
        embed.add_field(name="Где использовать", value="Все команды работают как в сервере, так и в **личных сообщениях** с ботом!", inline=False)
        embed.set_footer(text="Whitelist Bot • Arma Reforger")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    return bot


async def main():
    settings = get_settings()
    db = Database(settings.database_path)
    await db.connect()
    bot = build_bot(db)

    async with bot:
        await bot.start(settings.token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
