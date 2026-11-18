from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, List, Optional, Tuple

from enums import ProductType, TicketStatus
from models import Admin, Agent, Client, Message, Milestone, Product, Ticket, User

__all__ = [
    "Database",
    "UserRepository",
    "ProductRepository",
    "MilestoneRepository",
    "MessageRepository",
    "TicketRepository",
]

FOREIGN_KEYS_PRAGMA = "PRAGMA foreign_keys = ON;"

SCHEMA: Tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        available INTEGER DEFAULT 1,
        speciality TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        brand TEXT NOT NULL,
        type TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        closed_at TEXT,
        category TEXT NOT NULL,
        priority TEXT NOT NULL,
        product_id INTEGER NOT NULL REFERENCES products(id),
        client_id INTEGER NOT NULL REFERENCES users(id),
        agent_id INTEGER REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS milestones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        detail TEXT NOT NULL,
        date_time TEXT NOT NULL,
        user_id INTEGER NOT NULL REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        date_time TEXT NOT NULL,
        sender_id INTEGER NOT NULL REFERENCES users(id),
        is_read INTEGER DEFAULT 0
    )
    """,
)


def _require_id(value: Optional[int], entity: str) -> int:
    if value is None:
        raise ValueError(f"{entity} must have an id")
    return value


def _inserted_id(cursor: sqlite3.Cursor, entity: str) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError(f"Could not determine the inserted {entity} id")
    return int(cursor.lastrowid)


class Database:
    def __init__(self, path: str = "tickets.db") -> None:
        self.path = path
        self._connection: Optional[sqlite3.Connection] = None
        self.users = UserRepository(self)
        self.products = ProductRepository(self)
        self.milestones = MilestoneRepository(self)
        self.messages = MessageRepository(self)
        self.tickets = TicketRepository(self)
        self.create_schema()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            connection = sqlite3.connect(self.path, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute(FOREIGN_KEYS_PRAGMA)
            pragma_row = connection.execute("PRAGMA foreign_keys").fetchone()
            if pragma_row is None or pragma_row[0] != 1:
                connection.close()
                raise RuntimeError("Foreign key enforcement could not be enabled")
            self._connection = connection
        return self._connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connection
        if connection.in_transaction:
            yield connection
            return
        connection.execute("BEGIN")
        try:
            yield connection
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        else:
            connection.execute("COMMIT")

    def create_schema(self) -> None:
        with self.transaction() as connection:
            for statement in SCHEMA:
                connection.execute(statement)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, user: User) -> User:
        if user.id is None:
            return self.insert(user)
        return self.update(user)

    def insert(self, user: User) -> User:
        if user.id is not None:
            raise ValueError("user already has an id")
        role = self._role_of(user)
        active = int(user.active) if isinstance(user, (Client, Agent)) else 1
        available = int(user.available) if isinstance(user, Agent) else 1
        speciality = user.speciality.value if isinstance(user, Agent) else None
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users (name, email, password, role, active, available, speciality)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user.name, user.email, user.password, role, active, available, speciality),
            )
            user.id = _inserted_id(cursor, "user")
        return user

    def update(self, user: User) -> User:
        user_id = _require_id(user.id, "user")
        role = self._role_of(user)
        active = int(user.active) if isinstance(user, (Client, Agent)) else 1
        available = int(user.available) if isinstance(user, Agent) else 1
        speciality = user.speciality.value if isinstance(user, Agent) else None
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET name = ?, email = ?, password = ?, role = ?, active = ?, available = ?,
                    speciality = ?
                WHERE id = ?
                """,
                (
                    user.name,
                    user.email,
                    user.password,
                    role,
                    active,
                    available,
                    speciality,
                    user_id,
                ),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"User {user_id} not found")
        return user

    def find_by_id(self, user_id: int) -> Optional[User]:
        row = self.db.connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._from_row(row) if row is not None else None

    def find_by_email(self, email: str) -> Optional[User]:
        row = self.db.connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return self._from_row(row) if row is not None else None

    def find_all(self) -> List[User]:
        rows = self.db.connection.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, user: User) -> bool:
        return self.delete_by_id(_require_id(user.id, "user"))

    def delete_by_id(self, user_id: int) -> bool:
        with self.db.transaction() as connection:
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cursor.rowcount > 0

    def _role_of(self, user: User) -> str:
        if isinstance(user, Admin):
            return "ADMIN"
        if isinstance(user, Agent):
            return "AGENT"
        if isinstance(user, Client):
            return "CLIENT"
        raise ValueError("unsupported user type")

    def _from_row(self, row: sqlite3.Row) -> User:
        role = row["role"]
        if role == "ADMIN":
            return Admin(row["name"], row["email"], row["password"], id=row["id"])
        if role == "CLIENT":
            return Client(
                row["name"],
                row["email"],
                row["password"],
                active=bool(row["active"]),
                id=row["id"],
            )
        if role == "AGENT":
            speciality_value = row["speciality"]
            if speciality_value is None:
                raise ValueError(f"Agent {row['id']} has no speciality")
            return Agent(
                row["name"],
                row["email"],
                row["password"],
                ProductType(speciality_value),
                active=bool(row["active"]),
                available=bool(row["available"]),
                id=row["id"],
            )
        raise ValueError(f"Unknown user role: {role}")


class ProductRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, product: Product) -> Product:
        if product.id is None:
            return self.insert(product)
        return self.update(product)

    def insert(self, product: Product) -> Product:
        if product.id is not None:
            raise ValueError("product already has an id")
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO products (name, brand, type) VALUES (?, ?, ?)",
                (product.name, product.brand, product.type.value),
            )
            product.id = _inserted_id(cursor, "product")
        return product

    def update(self, product: Product) -> Product:
        product_id = _require_id(product.id, "product")
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "UPDATE products SET name = ?, brand = ?, type = ? WHERE id = ?",
                (product.name, product.brand, product.type.value, product_id),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"Product {product_id} not found")
        return product

    def find_by_id(self, product_id: int) -> Optional[Product]:
        row = self.db.connection.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def find_all(self) -> List[Product]:
        rows = self.db.connection.execute("SELECT * FROM products ORDER BY id").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, product: Product) -> bool:
        return self.delete_by_id(_require_id(product.id, "product"))

    def delete_by_id(self, product_id: int) -> bool:
        with self.db.transaction() as connection:
            cursor = connection.execute("DELETE FROM products WHERE id = ?", (product_id,))
            return cursor.rowcount > 0

    def _from_row(self, row: sqlite3.Row) -> Product:
        return Product(
            row["name"],
            row["brand"],
            ProductType(row["type"]),
            id=row["id"],
        )


class MilestoneRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, ticket_id: int, milestone: Milestone) -> Milestone:
        if milestone.id is None:
            return self.insert(ticket_id, milestone)
        return self.update(ticket_id, milestone)

    def insert(self, ticket_id: int, milestone: Milestone) -> Milestone:
        if milestone.id is not None:
            raise ValueError("milestone already has an id")
        _require_id(ticket_id, "ticket")
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO milestones (ticket_id, event_type, detail, date_time, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    milestone.event_type,
                    milestone.detail,
                    milestone.date_time.isoformat(),
                    milestone.user_id,
                ),
            )
            milestone.id = _inserted_id(cursor, "milestone")
        return milestone

    def update(self, ticket_id: int, milestone: Milestone) -> Milestone:
        milestone_id = _require_id(milestone.id, "milestone")
        _require_id(ticket_id, "ticket")
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE milestones
                SET ticket_id = ?, event_type = ?, detail = ?, date_time = ?, user_id = ?
                WHERE id = ? AND ticket_id = ?
                """,
                (
                    ticket_id,
                    milestone.event_type,
                    milestone.detail,
                    milestone.date_time.isoformat(),
                    milestone.user_id,
                    milestone_id,
                    ticket_id,
                ),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"Milestone {milestone_id} not found in ticket {ticket_id}")
        return milestone

    def find_by_id(self, milestone_id: int) -> Optional[Milestone]:
        row = self.db.connection.execute(
            "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def find_by_ticket_id(self, ticket_id: int) -> List[Milestone]:
        rows = self.db.connection.execute(
            "SELECT * FROM milestones WHERE ticket_id = ? ORDER BY date_time, id", (ticket_id,)
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_all(self) -> List[Milestone]:
        rows = self.db.connection.execute("SELECT * FROM milestones ORDER BY id").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, milestone: Milestone) -> bool:
        return self.delete_by_id(_require_id(milestone.id, "milestone"))

    def delete_by_id(self, milestone_id: int) -> bool:
        with self.db.transaction() as connection:
            cursor = connection.execute("DELETE FROM milestones WHERE id = ?", (milestone_id,))
            return cursor.rowcount > 0

    def delete_by_ticket_id(self, ticket_id: int) -> int:
        with self.db.transaction() as connection:
            cursor = connection.execute(
                "DELETE FROM milestones WHERE ticket_id = ?", (ticket_id,)
            )
            return cursor.rowcount

    def _from_row(self, row: sqlite3.Row) -> Milestone:
        return Milestone(
            row["event_type"],
            row["detail"],
            datetime.fromisoformat(row["date_time"]),
            row["user_id"],
            id=row["id"],
        )


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, ticket_id: int, message: Message) -> Message:
        if message.id is None:
            return self.insert(ticket_id, message)
        return self.update(ticket_id, message)

    def insert(self, ticket_id: int, message: Message) -> Message:
        if message.id is not None:
            raise ValueError("message already has an id")
        _require_id(ticket_id, "ticket")
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO messages (ticket_id, content, date_time, sender_id, is_read)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    ticket_id,
                    message.content,
                    message.date_time.isoformat(),
                    message.sender_id,
                    int(message.is_read),
                ),
            )
            message.id = _inserted_id(cursor, "message")
        return message

    def update(self, ticket_id: int, message: Message) -> Message:
        message_id = _require_id(message.id, "message")
        _require_id(ticket_id, "ticket")
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE messages
                SET ticket_id = ?, content = ?, date_time = ?, sender_id = ?, is_read = ?
                WHERE id = ? AND ticket_id = ?
                """,
                (
                    ticket_id,
                    message.content,
                    message.date_time.isoformat(),
                    message.sender_id,
                    int(message.is_read),
                    message_id,
                    ticket_id,
                ),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"Message {message_id} not found in ticket {ticket_id}")
        return message

    def find_by_id(self, message_id: int) -> Optional[Message]:
        row = self.db.connection.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def find_by_ticket_id(self, ticket_id: int) -> List[Message]:
        rows = self.db.connection.execute(
            "SELECT * FROM messages WHERE ticket_id = ? ORDER BY date_time, id", (ticket_id,)
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_all(self) -> List[Message]:
        rows = self.db.connection.execute("SELECT * FROM messages ORDER BY id").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, message: Message) -> bool:
        return self.delete_by_id(_require_id(message.id, "message"))

    def delete_by_id(self, message_id: int) -> bool:
        with self.db.transaction() as connection:
            cursor = connection.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            return cursor.rowcount > 0

    def delete_by_ticket_id(self, ticket_id: int) -> int:
        with self.db.transaction() as connection:
            cursor = connection.execute("DELETE FROM messages WHERE ticket_id = ?", (ticket_id,))
            return cursor.rowcount

    def _from_row(self, row: sqlite3.Row) -> Message:
        return Message(
            row["content"],
            datetime.fromisoformat(row["date_time"]),
            row["sender_id"],
            is_read=bool(row["is_read"]),
            id=row["id"],
        )


class TicketRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, ticket: Ticket) -> Ticket:
        if ticket.id is None:
            return self.insert(ticket)
        return self.update(ticket)

    def insert(self, ticket: Ticket) -> Ticket:
        if ticket.id is not None:
            raise ValueError("ticket already has an id")
        with self.db.transaction() as connection:
            product_id = self._product_id(ticket)
            cursor = connection.execute(
                """
                INSERT INTO tickets
                    (title, description, status, created_at, closed_at, category, priority,
                     product_id, client_id, agent_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticket.title,
                    ticket.description,
                    ticket.status.value,
                    ticket.created_at.isoformat(),
                    ticket.closed_at.isoformat() if ticket.closed_at is not None else None,
                    ticket.category,
                    ticket.priority,
                    product_id,
                    ticket.client_id,
                    ticket.agent_id,
                ),
            )
            ticket.id = _inserted_id(cursor, "ticket")
            for milestone in ticket.milestones:
                self.db.milestones.insert(ticket.id, milestone)
            for message in ticket.messages:
                self.db.messages.insert(ticket.id, message)
        return ticket

    def update(self, ticket: Ticket) -> Ticket:
        ticket_id = _require_id(ticket.id, "ticket")
        with self.db.transaction() as connection:
            product_id = self._product_id(ticket)
            cursor = connection.execute(
                """
                UPDATE tickets
                SET title = ?, description = ?, status = ?, created_at = ?, closed_at = ?,
                    category = ?, priority = ?, product_id = ?, client_id = ?, agent_id = ?
                WHERE id = ?
                """,
                (
                    ticket.title,
                    ticket.description,
                    ticket.status.value,
                    ticket.created_at.isoformat(),
                    ticket.closed_at.isoformat() if ticket.closed_at is not None else None,
                    ticket.category,
                    ticket.priority,
                    product_id,
                    ticket.client_id,
                    ticket.agent_id,
                    ticket_id,
                ),
            )
            if cursor.rowcount == 0:
                raise LookupError(f"Ticket {ticket_id} not found")
            self._sync_milestones(ticket_id, ticket.milestones)
            self._sync_messages(ticket_id, ticket.messages)
        return ticket

    def find_by_id(self, ticket_id: int) -> Optional[Ticket]:
        row = self.db.connection.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
        ).fetchone()
        return self._from_row(row) if row is not None else None

    def find_by_client_id(self, client_id: int) -> List[Ticket]:
        rows = self.db.connection.execute(
            "SELECT * FROM tickets WHERE client_id = ? ORDER BY id", (client_id,)
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_by_agent_id(self, agent_id: int) -> List[Ticket]:
        rows = self.db.connection.execute(
            "SELECT * FROM tickets WHERE agent_id = ? ORDER BY id", (agent_id,)
        ).fetchall()
        return [self._from_row(row) for row in rows]

    def find_all(self) -> List[Ticket]:
        rows = self.db.connection.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, ticket: Ticket) -> bool:
        return self.delete_by_id(_require_id(ticket.id, "ticket"))

    def delete_by_id(self, ticket_id: int) -> bool:
        with self.db.transaction() as connection:
            cursor = connection.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
            return cursor.rowcount > 0

    def _product_id(self, ticket: Ticket) -> int:
        if ticket.product.id is None:
            self.db.products.save(ticket.product)
        return _require_id(ticket.product.id, "product")

    def _sync_milestones(self, ticket_id: int, milestones: List[Milestone]) -> None:
        rows = self.db.connection.execute(
            "SELECT id FROM milestones WHERE ticket_id = ?", (ticket_id,)
        ).fetchall()
        stored_ids = {row["id"] for row in rows}
        kept_ids = {milestone.id for milestone in milestones if milestone.id is not None}
        for milestone_id in stored_ids - kept_ids:
            self.db.milestones.delete_by_id(milestone_id)
        for milestone in milestones:
            if milestone.id is None:
                self.db.milestones.insert(ticket_id, milestone)
            elif milestone.id in stored_ids:
                self.db.milestones.update(ticket_id, milestone)
            else:
                raise ValueError(
                    f"Milestone {milestone.id} does not belong to ticket {ticket_id}"
                )

    def _sync_messages(self, ticket_id: int, messages: List[Message]) -> None:
        rows = self.db.connection.execute(
            "SELECT id FROM messages WHERE ticket_id = ?", (ticket_id,)
        ).fetchall()
        stored_ids = {row["id"] for row in rows}
        kept_ids = {message.id for message in messages if message.id is not None}
        for message_id in stored_ids - kept_ids:
            self.db.messages.delete_by_id(message_id)
        for message in messages:
            if message.id is None:
                self.db.messages.insert(ticket_id, message)
            elif message.id in stored_ids:
                self.db.messages.update(ticket_id, message)
            else:
                raise ValueError(f"Message {message.id} does not belong to ticket {ticket_id}")

    def _from_row(self, row: sqlite3.Row) -> Ticket:
        product = self.db.products.find_by_id(row["product_id"])
        if product is None:
            raise ValueError(f"Product {row['product_id']} not found for ticket {row['id']}")
        closed_at_value = row["closed_at"]
        return Ticket(
            title=row["title"],
            description=row["description"],
            category=row["category"],
            priority=row["priority"],
            product=product,
            client_id=row["client_id"],
            status=TicketStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            closed_at=datetime.fromisoformat(closed_at_value) if closed_at_value else None,
            agent_id=row["agent_id"],
            milestones=self.db.milestones.find_by_ticket_id(row["id"]),
            messages=self.db.messages.find_by_ticket_id(row["id"]),
            id=row["id"],
        )
