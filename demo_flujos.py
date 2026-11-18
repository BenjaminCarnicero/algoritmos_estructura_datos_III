from pathlib import Path
from typing import Optional, Tuple

from database import Database
from enums import ProductType, TicketStatus
from models import Admin, Agent, Client, Product, Ticket

DB_PATH = Path(__file__).with_name("ticketing.db")


def _require(entity_id: Optional[int], entity: str) -> int:
    if entity_id is None:
        raise RuntimeError(f"{entity} no tiene id asignado")
    return entity_id


def _reset_database() -> None:
    for suffix in ("", "-journal", "-wal", "-shm"):
        candidate = Path(str(DB_PATH) + suffix)
        if candidate.exists():
            candidate.unlink()


def _print_step(number: int, title: str) -> None:
    print(f"\n=== Flujo {number}: {title} ===")


def _load_initial_data(db: Database) -> Tuple[Admin, Client, Agent, Agent, Product]:
    admin = db.users.save(Admin("Admin Principal", "admin@ticketing.com", "admin123"))
    client = db.users.save(Client("Cliente Ejemplo", "cliente@ticketing.com", "cliente123"))
    kitchen_agent = db.users.save(
        Agent("Técnica de Cocina", "cocina@ticketing.com", "tec123", ProductType.KITCHEN)
    )
    electronics_agent = db.users.save(
        Agent("Técnico de Electrónica", "electronica@ticketing.com", "tec123", ProductType.ELECTRONICS)
    )
    tv = db.products.save(Product("Smart TV 42", "Vision", ProductType.SMALL_APPLIANCES))
    db.products.save(Product("Heladera No Frost", "Friol", ProductType.KITCHEN))
    db.products.save(Product("Licuadora 500W", "Mix", ProductType.SMALL_APPLIANCES))

    _require(admin.id, "admin")
    _require(client.id, "cliente")
    _require(kitchen_agent.id, "técnico de cocina")
    _require(electronics_agent.id, "técnico de electrónica")
    _require(tv.id, "producto")
    return admin, client, kitchen_agent, electronics_agent, tv


def _print_initial_data(admin: Admin, client: Client, kitchen: Agent, electronics: Agent) -> None:
    print("Datos iniciales cargados en ticketing.db:")
    for user in (admin, client, kitchen, electronics):
        role = (
            "ADMIN"
            if isinstance(user, Admin)
            else "CLIENT"
            if isinstance(user, Client)
            else "AGENT"
        )
        extra = f" | especialidad={user.get_speciality().value}" if isinstance(user, Agent) else ""
        print(f"  [{role}] {user.name} (id={user.id}){extra}")


def _print_final_state(db: Database, ticket_id: int) -> Ticket:
    final = db.tickets.find_by_id(ticket_id)
    if final is None:
        raise LookupError(f"Ticket {ticket_id} no encontrado al recuperarlo desde SQLite")

    print("\n=== Estado final recuperado desde SQLite ===")
    print(f"Ticket #{final.id}: {final.title}")
    print(f"Descripción: {final.description}")
    print(f"Categoría: {final.category} | Prioridad: {final.priority}")
    print(f"Status: {final.status.value}")
    print(f"Producto: {final.product.name} ({final.product.get_type().value})")
    print(f"Cliente: {final.client_id} | Técnico asignado: {final.agent_id}")
    print(f"Creado: {final.created_at.isoformat()}")
    print(f"Cerrado: {final.closed_at.isoformat() if final.closed_at is not None else '-'}")
    print(f"Milestones ({len(final.milestones)}):")
    for milestone in final.milestones:
        print(
            f"  #{milestone.id} [{milestone.date_time.isoformat()}] "
            f"{milestone.event_type} - {milestone.detail} (user_id={milestone.user_id})"
        )
    return final


def main() -> None:
    _reset_database()
    with Database(str(DB_PATH)) as db:
        admin, client, kitchen_agent, electronics_agent, tv = _load_initial_data(db)
        _print_initial_data(admin, client, kitchen_agent, electronics_agent)

        _print_step(1, "Asignar tipo de producto al producto")
        product = db.products.find_by_id(_require(tv.id, "producto"))
        if product is None:
            raise LookupError("No se pudo recuperar el producto seleccionado")
        print(f"Admin #{admin.id} selecciona el producto #{product.id}: {product.name}")
        print(f"Tipo antes: {product.get_type().value}")
        product.set_type(ProductType.ELECTRONICS)
        db.products.update(product)
        persisted_product = db.products.find_by_id(_require(product.id, "producto"))
        if persisted_product is None:
            raise LookupError("No se pudo recuperar el producto persistido")
        print(f"Tipo después (persistido): {persisted_product.get_type().value}")

        _print_step(3, "Crear / Abrir Ticket")
        ticket = Ticket(
            "Pantalla sin imagen",
            "El televisor no enciende y no muestra el menú principal.",
            "Garantía",
            "Alta",
            persisted_product,
            _require(client.id, "cliente"),
        )
        ticket.open()
        db.tickets.save(ticket)
        ticket_id = _require(ticket.id, "ticket")
        print(f"Ticket #{ticket_id} abierto por el cliente #{client.id}")
        print(f"Status: {ticket.status.value} | Milestones: {len(ticket.milestones)}")

        _print_step(2, "Cambiar estado del ticket")
        ticket.update_status(TicketStatus.IN_PROGRESS, _require(electronics_agent.id, "técnico"))
        db.tickets.save(ticket)
        print(f"Nuevo status: {ticket.status.value} | Milestones: {len(ticket.milestones)}")
        print(f"Último milestone: {ticket.milestones[-1].event_type} - {ticket.milestones[-1].detail}")

        _print_step(4, "Asignar técnico especializado al ticket")
        milestones_before_error = len(ticket.milestones)
        try:
            ticket.assign_agent(kitchen_agent, _require(admin.id, "admin"))
        except ValueError as error:
            print(f"Fallo controlado (especialidad incompatible): {error}")
            print(f"Milestones sin cambios: {len(ticket.milestones)} == {milestones_before_error}")
        else:
            raise AssertionError("La asignación con especialidad incompatible no debió aceptarse")

        ticket.assign_agent(electronics_agent, _require(admin.id, "admin"))
        db.tickets.save(ticket)
        print(f"Técnico asignado: {electronics_agent.name} (agent_id={ticket.agent_id})")

        final = _print_final_state(db, ticket_id)
        assert final.status is TicketStatus.IN_PROGRESS
        assert final.agent_id == electronics_agent.id
        assert len(final.milestones) == 3
        print("\nDemo finalizada sin errores.")


if __name__ == "__main__":
    main()
