import asyncio
from typing import Optional
import re

import discord
from discord.ext import commands

from src.config import get_settings
from src.db import Database, ApplicationStatus
import src.steam_api as steam_api

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True

STATUS_TEXT = {
    "pending": "В ожидании",
    "approved": "Подтверждена",
    "rejected": "Отклонена",
}

STATUS_COLOR = {
    "pending": 0xF39C12,
    "approved": 0x27AE60,
    "rejected": 0xE74C3C,
}

def get_status_ui(status: str) -> tuple[str, int]:
    """Возвращает подпись и цвет для статуса заявки."""
    return (
        STATUS_TEXT.get(status, status),
        STATUS_COLOR.get(status, 0x95A5A6),
    )

class ApplicationModal(discord.ui.Modal):
    """Форма подачи или повторной подачи заявки."""
    def __init__(self, db: Database, is_resubmit: bool = False, original_app_id: int = None, original_data: dict = None):
        """Инициализируем поля формы, при необходимости подставляем прошлые данные."""
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
            placeholder="PC/PS/XBOX",
            required=True,
            max_length=32,
            default=original_data.get('platform', '')
        )
        self.steamid = discord.ui.TextInput(
            label="SteamID",
            placeholder="SteamID64",
            required=False,
            max_length=17,
            default=original_data.get('steamid', '')
        )

        self.add_item(self.nickname)
        self.add_item(self.armaid)
        self.add_item(self.platform)
        self.add_item(self.steamid)

        if is_resubmit:
            self.title = "Повторная подача заявки"

    async def on_submit(self, interaction: discord.Interaction):
        """Проверяем поля и создаём или обновляем заявку."""
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

        if platform_norm == "PC":
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
                    description="Формат указан неверно.",
                    color=0xe74c3c
                )
                embed.add_field(name="Ожидаемый формат", value="SteamID64: 17 цифр", inline=False)
                embed.add_field(name="Пример", value="76561198000000000", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            settings = get_settings()
            if settings.steam_api_key and steamid:
                try:
                    import asyncio as _asyncio
                    profile_check = await _asyncio.to_thread(steam_api.check_profile_open, settings.steam_api_key, steamid)
                    if not profile_check.get('open', False):
                        embed = discord.Embed(
                            title="Ваш профиль Steam закрыт",
                            description="Ваш Steam профиль не является публичным или игровая информация скрыта.",
                            color=0xe74c3c
                        )
                        embed.add_field(
                            name="Что нужно сделать", 
                            value="• Сделайте профиль публичным\n• Откройте игровую информацию\n• Убедитесь, что у вас не стоит галочка 'Скрывать общее время в игре'", 
                            inline=False
                        )
                        embed.add_field(
                            name="Как открыть профиль", 
                            value="1. Зайдите в настройки Steam\n2. Приватность → Мой профиль → Открытый\n3. Приватность → Доступ к игровой информации → Открытый", 
                            inline=False
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                        return
                except Exception:
                    pass

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
                description="Статус: Ожидание\n\nЗаявка обновлена и отправлена на повторное рассмотрение.",
                color=0xf39c12,
                timestamp=discord.utils.utcnow()
            )
            app_id_for_admin = self.original_app_id
            
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
                description="Статус: Ожидание\n\nСпасибо! Заявка отправлена на рассмотрение.",
                color=0x27ae60,
                timestamp=discord.utils.utcnow()
            )
            app_id_for_admin = app_id
            

        await interaction.response.send_message(embed=embed, ephemeral=True)

        settings = get_settings()
        bot = interaction.client
        if settings.admin_channel_id and bot:
            channel = bot.get_channel(settings.admin_channel_id)
            if isinstance(channel, (discord.TextChannel, discord.Thread)):
                app = await self.db.get_application(app_id_for_admin)
                if app:
                    view = AdminDecisionView(bot, self.db, app_id_for_admin)
                    admin_embed = await bot.build_admin_embed(app)
                    await channel.send(embed=admin_embed, view=view)

class ApplyView(discord.ui.View):
    def __init__(self, db: Database):
        super().__init__(timeout=None)
        self.db = db

    @discord.ui.button(label="Подать заявку", style=discord.ButtonStyle.primary, custom_id="apply_button")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Открывает форму подачи; если отклонена — сразу переподача."""
        existing_app = await self.db.get_user_latest_application(interaction.user.id)
        if existing_app:
            if existing_app.status == "rejected":
                modal = ApplicationModal(
                    self.db,
                    is_resubmit=True,
                    original_app_id=existing_app.id,
                    original_data={
                        'nickname': existing_app.username,
                        'armaid': existing_app.arma_id,
                        'platform': existing_app.platform,
                        'steamid': existing_app.steam_id,
                    }
                )
                await interaction.response.send_modal(modal)
                return
            else:
                text = STATUS_TEXT.get(existing_app.status, existing_app.status)
                embed = discord.Embed(
                    title="Ваша заявка уже создана",
                    description=f"Статус: **{text}**\n\nУ одного пользователя может быть только одна активная заявка.",
                    color=0xf39c12
                )
                embed.add_field(
                    name="Как проверить статус",
                    value="Используйте команду `/status` для просмотра подробной информации.",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        await interaction.response.send_modal(ApplicationModal(self.db))


class WhitelistBot(commands.Bot):
    """Бот для управления заявками в whitelist."""
    def __init__(self, db: Database):
        """Настраиваем бота и подключаем нужные вьюхи/кнопки."""
        super().__init__(command_prefix=commands.when_mentioned, intents=INTENTS)
        self.db = db
        self.add_view(ApplyView(self.db))

    async def setup_hook(self) -> None:
        """Синхронизируем слэш‑команды с Discord без дублирования."""
        settings = get_settings()
        try:
            if settings.guild_id:
                guild = discord.Object(id=settings.guild_id)
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()
        except Exception:
            pass

        await self._restore_admin_views()

    async def _restore_admin_views(self) -> None:
        """Восстанавливаем view для всех активных заявок после рестарта."""
        try:
            pending_apps = await self.db.get_pending_applications()
            for app in pending_apps:
                view = AdminDecisionView(self, self.db, app.id)
                self.add_view(view)
        except Exception as e:
            print(f"Ошибка при восстановлении admin views: {e}")

    async def on_ready(self) -> None:
        """Бот запустился; проверяем стартовое сообщение с кнопкой."""
        print(f"Bot is running as {self.user}")
        await self.ensure_application_message()
        
    async def ensure_application_message(self) -> None:
        """Если в канале нет сообщения с кнопкой — отправляем его."""
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
                        "• **Платформа** - PC, Xbox, PS\n"
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

    async def has_admin_role(self, user_id: int) -> bool:
        """Проверяем, что у пользователя есть нужная админ‑роль."""
        settings = get_settings()
        if not settings.admin_role_id or not settings.guild_id:
            return False
        guild = self.get_guild(settings.guild_id)
        if not guild:
            return False
        member = guild.get_member(user_id)
        if member is None:
            return False
        return any(r.id == settings.admin_role_id for r in getattr(member, "roles", []))

    async def build_admin_embed(self, app) -> discord.Embed:
        """Собираем карточку заявки для админ‑канала."""
        text, color = get_status_ui(app.status)
        
        is_resubmit = app.admin_id is not None and app.status == "pending"
        title = f"Заявка #{app.id}" + (" (Повторная)" if is_resubmit else "")
        
        embed = discord.Embed(title=title, description=f"Статус: {text}", color=color, timestamp=discord.utils.utcnow())
        embed.add_field(name="Игрок", value=f"{app.username} (<@{app.user_id}>)", inline=False)
        steam_id_display = f"`{app.steam_id}`" if app.steam_id else "-"
        if app.steam_id and re.fullmatch(r"\d{17}", str(app.steam_id)):
            steam_id_display = f"[{app.steam_id}](https://steamcommunity.com/profiles/{app.steam_id})"
        embed.add_field(name="Данные", value=f"Arma ID: `{app.arma_id}`\nПлатформа: `{app.platform}`\nSteamID: {steam_id_display}", inline=False)
        
        if app.admin_comment:
            embed.add_field(name="Комментарий администратора", value=f"```{app.admin_comment}```", inline=False)
        if app.admin_id:
            admin_user = self.get_user(app.admin_id)
            admin_name = admin_user.display_name if admin_user else f"ID: {app.admin_id}"
            field_name = "Предыдущий обработчик" if is_resubmit else "Обработал"
            embed.add_field(name=field_name, value=f"**{admin_name}** (<@{app.admin_id}>)", inline=False)

        try:
            settings = get_settings()
            api_key = settings.steam_api_key
            if api_key and app.steam_id:
                import asyncio as _asyncio
                games = await _asyncio.to_thread(steam_api.get_arma_games, api_key, app.steam_id, True)
                if games:
                    sorted_games = sorted(games, key=lambda x: x[1] or 0, reverse=True)
                    lines = [f"{name} — {int(round(hours))} ч" for name, hours in sorted_games]
                    embed.add_field(name="Количество наигранных часов", value="\n".join(lines), inline=False)
                else:
                    embed.add_field(name="Количество наигранных часов", value="Профиль закрыт или наигранных часов нет", inline=False)
        except Exception:
            pass

        return embed

    async def notify_user_status_change(self, app, new_status: str, comment: Optional[str] = None):
        """Пишем пользователю про изменение статуса заявки."""
        user = self.get_user(app.user_id)
        if not user:
            return

        status_info = {
            "approved": ("одобрена", 0x27ae60),
            "rejected": ("отклонена", 0xe74c3c)
        }

        text, color = status_info.get(new_status, (new_status, 0x95a5a6))

        embed = discord.Embed(title="Заявка в Whitelist", description=f"Статус: **{text}**", color=color)

        if new_status == "approved":
            embed.add_field(name="Поздравляем!", value="Вы успешно добавлены в Whitelsit", inline=False)
        else:
            if comment:
                embed.add_field(name="Комментарий администратора", value=f"```{comment}```", inline=False)

        admin_user = self.get_user(app.admin_id) if app.admin_id else None
        if admin_user:
            embed.add_field(name="Обработал", value=f"**{admin_user.display_name}**", inline=False)

        if new_status == "rejected":
            embed.add_field(name="Что делать дальше?", value="Вы можете повторно подать заявку через кнопку в канале.", inline=False)
        elif new_status == "approved":
            pass

        embed.set_footer(text="Whitelist Bot • Arma Reforger")
        await user.send(embed=embed)


class RejectReasonModal(discord.ui.Modal):
    """Окно для ввода причины отклонения."""
    def __init__(self, bot: WhitelistBot, db: Database, app_id: int, message: Optional[discord.Message] = None):
        super().__init__(title="Причина отклонения")
        self.bot = bot
        self.db = db
        self.app_id = app_id
        self.message = message
        self.reason = discord.ui.TextInput(label="Причина", placeholder="Укажите причину (кратко)", required=True, max_length=300)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        """Сохраняем причину, ставим rejected и обновляем карточку."""
        await self.db.update_status_with_comment(self.app_id, "rejected", str(self.reason), interaction.user.id)
        app = await self.db.get_application(self.app_id)
        await self.bot.notify_user_status_change(app, "rejected", str(self.reason))

        try:
            updated_app = await self.db.get_application(self.app_id)
            view = AdminDecisionView(self.bot, self.db, self.app_id)
            for child in view.children:
                try:
                    child.disabled = True
                except Exception:
                    pass
            embed = await self.bot.build_admin_embed(updated_app)
            if self.message:
                await self.message.edit(embed=embed, view=view)
            else:
                if interaction.message:
                    await interaction.message.edit(embed=embed, view=view)
        except Exception:
            pass

        await interaction.response.defer(ephemeral=True)


class AdminDecisionView(discord.ui.View):
    """Кнопки одобрения и отклонения в админ‑канале."""
    def __init__(self, bot: WhitelistBot, db: Database, app_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.db = db
        self.app_id = app_id
        
        approve_btn = discord.ui.Button(
            label="Принять", 
            style=discord.ButtonStyle.success,
            custom_id=f"admin_approve_{app_id}"
        )
        reject_btn = discord.ui.Button(
            label="Отклонить", 
            style=discord.ButtonStyle.danger,
            custom_id=f"admin_reject_{app_id}"
        )
        
        approve_btn.callback = self.approve_btn
        reject_btn.callback = self.reject_btn
        
        self.add_item(approve_btn)
        self.add_item(reject_btn)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Проверяем, что у пользователя есть админ‑роль."""
        is_admin = await self.bot.has_admin_role(interaction.user.id)
        if not is_admin:
            await interaction.response.send_message("Недостаточно прав.", ephemeral=True)
            return False
        return True

    async def approve_btn(self, interaction: discord.Interaction):
        """Одобряем заявку и обновляем карточку."""
        if not await self._check_admin(interaction):
            return
        
        app_id = int(interaction.data["custom_id"].split("_")[-1])
        
        await self.db.update_status_with_comment(app_id, "approved", "Пользователь добавлен в Whitelist", interaction.user.id)
        app = await self.db.get_application(app_id)
        await self.bot.notify_user_status_change(app, "approved")

        updated_app = await self.db.get_application(app_id)
        view = AdminDecisionView(self.bot, self.db, app_id)
        for child in view.children:
            try:
                child.disabled = True
            except Exception:
                pass
        embed = await self.bot.build_admin_embed(updated_app)
        await interaction.response.edit_message(embed=embed, view=view)

    async def reject_btn(self, interaction: discord.Interaction):
        """Запрашиваем причину и отклоняем заявку."""
        if not await self._check_admin(interaction):
            return
        
        app_id = int(interaction.data["custom_id"].split("_")[-1])
        
        await interaction.response.send_modal(RejectReasonModal(self.bot, self.db, app_id, message=interaction.message))

def build_bot(db: Database) -> WhitelistBot:
    """Создаём бота и регистрируем слэш‑команды."""
    bot = WhitelistBot(db)

    @bot.tree.command(name="status", description="Показать статус вашей заявки")
    async def status_slash(interaction: discord.Interaction):
        """Показывает статус последней заявки пользователя."""
        app = await db.get_user_latest_application(interaction.user.id)
        if not app:
            embed = discord.Embed(title="Заявка не найдена", description="У вас пока нет заявок на whitelist.\n\nИспользуйте кнопку **\"Подать заявку\"** для создания новой заявки.", color=0xe74c3c)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        text, color = get_status_ui(app.status)
        embed = discord.Embed(title="Ваша заявка", description=f"**Статус:** {text}", color=color)

        embed.add_field(name="Информация о игроке", value=f"**Никнейм:** {app.username}\n**Discord:** <@{app.user_id}>", inline=False)
        embed.add_field(name="Игровые данные", value=f"**Arma ID:** `{app.arma_id}`\n**Платформа:** `{app.platform}`\n**Steam ID:** `{app.steam_id}`", inline=False)
        

        if app.status != "approved" and app.admin_comment:
            embed.add_field(name="Комментарий администратора", value=f"```{app.admin_comment}```", inline=False)

        if app.status == "rejected":
            embed.add_field(name="Заявка отклонена", value="К сожалению, ваша заявка была отклонена.\nПовторно подать можно через кнопку в канале.", inline=False)

        embed.set_footer(text="Whitelist Bot • Arma Reforger")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(name="help", description="Показать справку по командам")
    async def help_slash(interaction: discord.Interaction):
        """Короткая справка по доступным командам."""
        embed = discord.Embed(title="Whitelist Bot - Справка", description="**Добро пожаловать в систему управления заявками на whitelist!**\n\nЗдесь вы можете подать заявку на получение доступа к серверу Arma Reforger.", color=0x3498db)

        embed.add_field(name="Доступные команды", value="`/status` - Показать статус вашей заявки\n`/help` - Показать эту справку", inline=False)
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