import aiosqlite
from dataclasses import dataclass
from typing import Optional, Literal, List, Dict, Any

ApplicationStatus = Literal["pending", "approved", "rejected"]

@dataclass
class Application:
    id: int
    user_id: int
    username: str
    arma_id: str
    platform: str
    steam_id: str
    status: ApplicationStatus
    created_at: str
    updated_at: str
    admin_comment: Optional[str] = None
    admin_id: Optional[int] = None


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    arma_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    steam_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected')) DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    admin_comment TEXT,
    admin_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
"""


class Database:
    """Простая обёртка вокруг aiosqlite для управления заявками."""
    def __init__(self, path: str):
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Открыть соединение и применить схему (без миграций)."""
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        """Закрыть соединение, если открыто."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def create_application(
        self,
        user_id: int,
        username: str,
        arma_id: str,
        platform: str,
        steam_id: str,
    ) -> int:
        """Создать новую заявку со статусом pending. Возвращает ID заявки."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            INSERT INTO applications (user_id, username, arma_id, platform, steam_id, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (user_id, username, arma_id, platform, steam_id),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_application(self, app_id: int) -> Optional[Application]:
        """Получить заявку по ID."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM applications WHERE id = ?",
            (app_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_app(row)

    async def get_user_latest_application(self, user_id: int) -> Optional[Application]:
        """Получить последнюю (по ID) заявку пользователя."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM applications WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_app(row)

    async def get_steam_id_by_arma_id(self, arma_id: str) -> Optional[str]:
        """Вернуть steam_id по arma_id, если запись есть."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT steam_id FROM applications WHERE arma_id = ? LIMIT 1",
            (arma_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None

    async def is_whitelisted_by_arma_id(self, arma_id: str) -> bool:
        """True если есть заявка с arma_id и статусом approved."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT 1 FROM applications WHERE arma_id = ? AND status = 'approved' LIMIT 1",
            (arma_id,)
        )
        row = await cursor.fetchone()
        return bool(row)

    async def get_arma_id_by_steam_id(self, steam_id: str) -> Optional[str]:
        """Вернуть arma_id по steam_id, если запись есть."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT arma_id FROM applications WHERE steam_id = ? LIMIT 1",
            (steam_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row and row[0] else None

    async def is_whitelisted_by_steam_id(self, steam_id: str) -> bool:
        """True если есть заявка с steam_id и статусом approved."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT 1 FROM applications WHERE steam_id = ? AND status = 'approved' LIMIT 1",
            (steam_id,)
        )
        row = await cursor.fetchone()
        return bool(row)

    async def update_status(self, app_id: int, status: ApplicationStatus) -> bool:
        """Обновить статус заявки."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            UPDATE applications
            SET status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, app_id),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def update_fields(self, app_id: int, fields: Dict[str, Any]) -> bool:
        """Обновить произвольные поля заявки + метку updated_at."""
        assert self._conn is not None
        if not fields:
            return True
        columns = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [app_id]
        cursor = await self._conn.execute(
            f"UPDATE applications SET {columns}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def update_status_with_comment(
        self,
        app_id: int,
        status: ApplicationStatus,
        comment: Optional[str] = None,
        admin_id: Optional[int] = None,
    ) -> bool:
        """Обновить статус + комментарий/ID администратора."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            """
            UPDATE applications
            SET status = ?, admin_comment = ?, admin_id = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, comment, admin_id, app_id),
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def get_pending_applications(self) -> List[Application]:
        """Вернуть все заявки со статусом 'pending'."""
        assert self._conn is not None
        cursor = await self._conn.execute(
            "SELECT * FROM applications WHERE status = 'pending' ORDER BY id ASC"
        )
        rows = await cursor.fetchall()
        apps: List[Application] = []
        for row in rows:
            app = self._row_to_app(row)
            if app:
                apps.append(app)
        return apps

    async def get_application_by_identifier(self, identifier: str) -> Optional[Application]:
        """Вернуть заявку по одному из идентификаторов"""
        assert self._conn is not None
        ident = identifier.strip()

        l = len(ident)
        if l == 36:
            col, params = "arma_id", (ident,)
        elif l == 17 and ident.isdigit():
            col, params = "steam_id", (ident,)
        else:
            return None

        cursor = await self._conn.execute(
            f"SELECT * FROM applications WHERE {col} = ? ORDER BY id DESC LIMIT 1",
            params,
        )
        row = await cursor.fetchone()
        return self._row_to_app(row)

    def _row_to_app(self, row) -> Optional[Application]:
        """Преобразование строки БД в dataclass Application."""
        if not row:
            return None
        return Application(
            id=row[0],
            user_id=row[1],
            username=row[2],
            arma_id=row[3],
            platform=row[4],
            steam_id=row[5],
            status=row[6],
            created_at=row[7],
            updated_at=row[8],
            admin_comment=row[9] if len(row) > 9 else None,
            admin_id=row[10] if len(row) > 10 else None,
        )