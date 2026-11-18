import sqlite3
from datetime import datetime
from typing import Optional, Type, cast

from database import Database
from enums import ProductType, TicketStatus
from models import Admin, Agent, Client, Message, Product, Ticket, User

DB_PATH = "ticketing.db"

PRODUCT_TYPES = {
    "1": ProductType.KITCHEN,
    "2": ProductType.ELECTRONICS,
    "3": ProductType.SMALL_APPLIANCES,
}

TICKET_STATUSES = {
    "1": TicketStatus.OPEN,
    "2": TicketStatus.IN_PROGRESS,
    "3": TicketStatus.RESOLVED,
    "4": TicketStatus.CLOSED,
}

PRIORITIES = {
    "1": "Baja",
    "2": "Media",
    "3": "Alta",
    "4": "Urgente",
}


def _require(entity_id: Optional[int], entity: str) -> int:
    if entity_id is None:
        raise RuntimeError(f"{entity} no tiene id asignado")
    return entity_id


def _read_text(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("El valor no puede estar vacío.")


def _read_int(prompt: str) -> int:
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("Ingresá un número entero válido.")


def _read_bool(prompt: str) -> bool:
    while True:
        value = input(prompt).strip().lower()
        if value in ("s", "si", "sí", "y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("Respondé s/n.")


def _select_product_type() -> ProductType:
    print("Rubros disponibles:")
    for key, value in PRODUCT_TYPES.items():
        print(f"  {key}) {value.value}")
    while True:
        option = input("Opción: ").strip()
        if option in PRODUCT_TYPES:
            return PRODUCT_TYPES[option]
        print("Opción inválida.")


def _select_ticket_status() -> TicketStatus:
    print("Estados disponibles:")
    for key, value in TICKET_STATUSES.items():
        print(f"  {key}) {value.value}")
    while True:
        option = input("Opción: ").strip()
        if option in TICKET_STATUSES:
            return TICKET_STATUSES[option]
        print("Opción inválida.")


def _select_priority() -> str:
    print("Prioridades disponibles:")
    for key, value in PRIORITIES.items():
        print(f"  {key}) {value}")
    while True:
        option = input("Opción: ").strip()
        if option in PRIORITIES:
            return PRIORITIES[option]
        print("Opción inválida.")


def _role_of(user: User) -> str:
    if isinstance(user, Admin):
        return "ADMIN"
    if isinstance(user, Agent):
        return "AGENT"
    if isinstance(user, Client):
        return "CLIENT"
    return "USER"


def _user_detail(user: User) -> str:
    if isinstance(user, Agent):
        return (
            f" | especialidad={user.get_speciality().value}, "
            f"disponible={user.is_available()}"
        )
    if isinstance(user, Client):
        return f" | activo={user.active}"
    return ""


def _list_users(db: Database) -> None:
    users = db.users.find_all()
    if not users:
        print("No hay usuarios cargados.")
        return
    print("\nUsuarios:")
    for user in users:
        print(
            f"  #{user.id} [{_role_of(user)}] {user.name} <{user.email}>"
            f"{_user_detail(user)}"
        )


def _select_user(db: Database, user_type: Type[User], label: str) -> User:
    users = [user for user in db.users.find_all() if isinstance(user, user_type)]
    if not users:
        raise LookupError(f"No hay {label} cargados")
    print(f"\n{label.capitalize()}:")
    for user in users:
        print(f"  #{user.id} {user.name} <{user.email}>{_user_detail(user)}")
    selected_id = _read_int("ID: ")
    selected = next((user for user in users if user.id == selected_id), None)
    if selected is None:
        raise LookupError(f"No existe un {label[:-1]} con id {selected_id}")
    return selected


def _select_product(db: Database) -> Product:
    products = db.products.find_all()
    if not products:
        raise LookupError("No hay productos cargados")
    print("\nProductos:")
    for product in products:
        print(
            f"  #{product.id} {product.name} ({product.brand}) - "
            f"{product.get_type().value}"
        )
    product_id = _read_int("ID del producto: ")
    product = db.products.find_by_id(product_id)
    if product is None:
        raise LookupError(f"No existe un producto con id {product_id}")
    return product


def _select_ticket(db: Database) -> Ticket:
    tickets = db.tickets.find_all()
    if not tickets:
        raise LookupError("No hay tickets cargados")
    print("\nTickets:")
    for ticket in tickets:
        print(
            f"  #{ticket.id} {ticket.title} - {ticket.status.value} - "
            f"producto #{ticket.product.id}"
        )
    ticket_id = _read_int("ID del ticket: ")
    ticket = db.tickets.find_by_id(ticket_id)
    if ticket is None:
        raise LookupError(f"No existe un ticket con id {ticket_id}")
    return ticket


def _print_ticket_detail(ticket: Ticket) -> None:
    print("\nDetalle del ticket:")
    print(f"  ID: {ticket.id}")
    print(f"  Título: {ticket.title}")
    print(f"  Descripción: {ticket.description}")
    print(f"  Estado: {ticket.status.value}")
    print(f"  Categoría: {ticket.category} | Prioridad: {ticket.priority}")
    print(f"  Producto: {ticket.product.name} ({ticket.product.get_type().value})")
    print(f"  Cliente: {ticket.client_id} | Técnico: {ticket.agent_id}")
    print(f"  Creado: {ticket.created_at.isoformat()}")
    print(f"  Cerrado: {ticket.closed_at.isoformat() if ticket.closed_at else '-'}")
    print("  Milestones:")
    for milestone in ticket.milestones:
        print(
            f"    #{milestone.id} [{milestone.date_time.isoformat()}] "
            f"{milestone.event_type} - {milestone.detail} (user_id={milestone.user_id})"
        )
    print("  Mensajes:")
    for message in ticket.messages:
        print(
            f"    #{message.id} [{message.date_time.isoformat()}] "
            f"de {message.sender_id}: {message.content} "
            f"(leído={message.is_read})"
        )


def _create_client(db: Database) -> None:
    client = Client(
        _read_text("Nombre: "),
        _read_text("Email: "),
        _read_text("Contraseña: "),
    )
    db.users.save(client)
    print(f"Cliente #{client.id} creado.")


def _create_agent(db: Database) -> None:
    agent = Agent(
        _read_text("Nombre: "),
        _read_text("Email: "),
        _read_text("Contraseña: "),
        _select_product_type(),
        available=_read_bool("¿Disponible para tickets? (s/n): "),
    )
    db.users.save(agent)
    print(f"Técnico #{agent.id} creado.")


def _create_product(db: Database) -> None:
    product = Product(
        _read_text("Nombre: "),
        _read_text("Marca: "),
        _select_product_type(),
    )
    db.products.save(product)
    print(f"Producto #{product.id} creado.")


def _set_product_type(db: Database) -> None:
    product = _select_product(db)
    print(f"Tipo actual: {product.get_type().value}")
    product.set_type(_select_product_type())
    db.products.update(product)
    print(f"Tipo actualizado a: {product.get_type().value}")


def _create_ticket(db: Database) -> None:
    product = _select_product(db)
    client = cast(Client, _select_user(db, Client, "clientes"))
    print("\nDatos seleccionados para el nuevo ticket:")
    print(
        f"  Producto: #{product.id} - {product.name} ({product.brand}) "
        f"[{product.get_type().value}]"
    )
    print(f"  Cliente: #{client.id} - {client.name} <{client.email}>")
    if not _read_bool("¿Es correcto? (s/n): "):
        print("Creación de ticket cancelada.")
        return

    ticket = Ticket(
        _read_text("Título: "),
        _read_text("Descripción: "),
        _read_text("Categoría (ej: Garantía, Hardware, Software): "),
        _select_priority(),
        product,
        _require(client.id, "cliente"),
    )
    ticket.open()
    db.tickets.save(ticket)
    print(f"Ticket #{ticket.id} creado y abierto. Estado: {ticket.status.value}")


def _change_status(db: Database) -> None:
    ticket = _select_ticket(db)
    new_status = _select_ticket_status()
    user_id = _read_int("ID del usuario que ejecuta el cambio: ")
    ticket.update_status(new_status, user_id)
    db.tickets.save(ticket)
    print(f"Estado actualizado a: {ticket.status.value}")


def _assign_agent(db: Database) -> None:
    ticket = _select_ticket(db)
    agent = cast(Agent, _select_user(db, Agent, "técnicos"))
    admin_id = _read_int("ID del admin que ejecuta la asignación: ")
    ticket.assign_agent(agent, admin_id)
    db.tickets.save(ticket)
    print(f"Técnico #{agent.id} asignado al ticket #{ticket.id}")


def _toggle_agent_availability(db: Database) -> None:
    agent = cast(Agent, _select_user(db, Agent, "técnicos"))
    agent.available = _read_bool("¿Disponible para tickets? (s/n): ")
    db.users.update(agent)
    print(f"Disponibilidad del técnico #{agent.id} actualizada.")


def _add_message(db: Database) -> None:
    ticket = _select_ticket(db)
    sender_id = _read_int("ID del remitente: ")
    content = _read_text("Mensaje: ")
    ticket.add_message(Message(content, datetime.now(), sender_id))
    db.tickets.save(ticket)
    print(f"Mensaje agregado al ticket #{ticket.id}")


def _delete_ticket(db: Database) -> None:
    ticket = _select_ticket(db)
    if db.tickets.delete(ticket):
        print("Ticket eliminado; milestones y messages se eliminaron por cascada.")
    else:
        print("No se pudo eliminar el ticket.")


def _print_menu() -> None:
    print("\n=== Sistema de Gestión de Tickets ===")
    print("1) Listar usuarios")
    print("2) Crear cliente")
    print("3) Crear técnico")
    print("4) Crear producto")
    print("5) Asignar/cambiar tipo de producto")
    print("6) Crear y abrir ticket")
    print("7) Cambiar estado de ticket")
    print("8) Asignar técnico a ticket")
    print("9) Listar tickets")
    print("10) Ver detalle de ticket")
    print("11) Agregar mensaje a ticket")
    print("12) Cambiar disponibilidad de técnico")
    print("13) Eliminar ticket")
    print("0) Salir")


def main() -> None:
    with Database(DB_PATH) as db:
        print(f"Usando base de datos SQLite: {DB_PATH}")
        while True:
            _print_menu()
            try:
                option = input("Opción: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                break

            if option == "0":
                print("Hasta luego.")
                break

            try:
                if option == "1":
                    _list_users(db)
                elif option == "2":
                    _create_client(db)
                elif option == "3":
                    _create_agent(db)
                elif option == "4":
                    _create_product(db)
                elif option == "5":
                    _set_product_type(db)
                elif option == "6":
                    _create_ticket(db)
                elif option == "7":
                    _change_status(db)
                elif option == "8":
                    _assign_agent(db)
                elif option == "9":
                    for ticket in db.tickets.find_all():
                        print(
                            f"  #{ticket.id} {ticket.title} - {ticket.status.value} - "
                            f"producto #{ticket.product.id}"
                        )
                elif option == "10":
                    _print_ticket_detail(_select_ticket(db))
                elif option == "11":
                    _add_message(db)
                elif option == "12":
                    _toggle_agent_availability(db)
                elif option == "13":
                    _delete_ticket(db)
                else:
                    print("Opción inválida.")
            except (ValueError, LookupError, RuntimeError, sqlite3.IntegrityError) as error:
                print(f"Error: {error}")

            try:
                input("\nPresioná Enter para continuar...")
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                break


if __name__ == "__main__":
    main()
