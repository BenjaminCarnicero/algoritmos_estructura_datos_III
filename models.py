from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from enums import ProductType, TicketStatus

__all__ = ["User", "Client", "Agent", "Admin", "Product", "Milestone", "Message", "Ticket"]


class User(ABC):
    def __init__(self, name: str, email: str, password: str, id: Optional[int] = None) -> None:
        self.id = id
        self.name = name
        self.email = email
        self.password = password

    @abstractmethod
    def login(self, email: str, password: str) -> bool:
        return self.email == email and self.password == password


class Client(User):
    def __init__(
        self,
        name: str,
        email: str,
        password: str,
        active: bool = True,
        id: Optional[int] = None,
    ) -> None:
        super().__init__(name, email, password, id)
        self.active = active

    def login(self, email: str, password: str) -> bool:
        return super().login(email, password)


class Agent(User):
    def __init__(
        self,
        name: str,
        email: str,
        password: str,
        speciality: ProductType,
        active: bool = True,
        available: bool = True,
        id: Optional[int] = None,
    ) -> None:
        super().__init__(name, email, password, id)
        if not isinstance(speciality, ProductType):
            raise ValueError("speciality must be a valid ProductType")
        self.active = active
        self.available = available
        self.speciality = speciality

    def login(self, email: str, password: str) -> bool:
        return super().login(email, password)

    def get_speciality(self) -> ProductType:
        return self.speciality

    def is_available(self) -> bool:
        return self.available


class Admin(User):
    def __init__(self, name: str, email: str, password: str, id: Optional[int] = None) -> None:
        super().__init__(name, email, password, id)

    def login(self, email: str, password: str) -> bool:
        return super().login(email, password)


class Product:
    def __init__(self, name: str, brand: str, type: ProductType, id: Optional[int] = None) -> None:
        self.id = id
        self.name = name
        self.brand = brand
        self.set_type(type)

    def set_type(self, type: ProductType) -> None:
        if not isinstance(type, ProductType):
            raise ValueError("type must be a valid ProductType")
        self.type = type

    def get_type(self) -> ProductType:
        return self.type


class Milestone:
    def __init__(
        self,
        event_type: str,
        detail: str,
        date_time: datetime,
        user_id: int,
        id: Optional[int] = None,
    ) -> None:
        if not isinstance(date_time, datetime):
            raise ValueError("date_time must be a datetime instance")
        self.id = id
        self.event_type = event_type
        self.detail = detail
        self.date_time = date_time
        self.user_id = user_id


class Message:
    def __init__(
        self,
        content: str,
        date_time: datetime,
        sender_id: int,
        is_read: bool = False,
        id: Optional[int] = None,
    ) -> None:
        if not isinstance(date_time, datetime):
            raise ValueError("date_time must be a datetime instance")
        self.id = id
        self.content = content
        self.date_time = date_time
        self.sender_id = sender_id
        self.is_read = is_read


class Ticket:
    def __init__(
        self,
        title: str,
        description: str,
        category: str,
        priority: str,
        product: Product,
        client_id: int,
        status: TicketStatus = TicketStatus.OPEN,
        created_at: Optional[datetime] = None,
        closed_at: Optional[datetime] = None,
        agent_id: Optional[int] = None,
        milestones: Optional[List[Milestone]] = None,
        messages: Optional[List[Message]] = None,
        id: Optional[int] = None,
    ) -> None:
        if not isinstance(status, TicketStatus):
            raise ValueError("status must be a valid TicketStatus")
        if not isinstance(product, Product):
            raise ValueError("product must be a Product instance")
        self.id = id
        self.title = title
        self.description = description
        self.status = status
        self.created_at = created_at if created_at is not None else datetime.now()
        self.closed_at = closed_at
        self.category = category
        self.priority = priority
        self.product = product
        self.client_id = client_id
        self.agent_id = agent_id
        self.milestones = milestones if milestones is not None else []
        self.messages = messages if messages is not None else []

    def open(self) -> None:
        self.status = TicketStatus.OPEN
        self.created_at = datetime.now()
        self.milestones.append(
            Milestone(
                "Ticket Opened",
                f"Ticket opened by client {self.client_id}",
                datetime.now(),
                self.client_id,
            )
        )

    def assign_agent(self, agent: Agent, admin_id: int) -> None:
        if self.product.get_type() != agent.get_speciality() or not agent.is_available():
            raise ValueError("Incompatible speciality or agent unavailable")
        self.agent_id = agent.id
        self.milestones.append(
            Milestone("Agent Assigned", f"Agent {agent.name} assigned", datetime.now(), admin_id)
        )

    def update_status(self, new_status: TicketStatus, user_id: int) -> None:
        if not isinstance(new_status, TicketStatus):
            raise ValueError("new_status must be a valid TicketStatus")
        self.status = new_status
        if new_status is TicketStatus.CLOSED:
            self.close()
        self.milestones.append(
            Milestone(
                "Status Change",
                f"Status changed to {new_status.value}",
                datetime.now(),
                user_id,
            )
        )

    def close(self) -> None:
        self.status = TicketStatus.CLOSED
        self.closed_at = datetime.now()

    def add_message(self, message: Message) -> None:
        if not isinstance(message, Message):
            raise ValueError("message must be a Message instance")
        self.messages.append(message)
