# Especificación Técnica - Sistema de Gestión de Tickets (TP Final Integrador)

## 1. Objetivo y Stack Tecnológico
Implementar el sistema de gestión de tickets diseñado en los Hitos 1 a 6.
- **Lenguaje:** Python 3.x aplicando Programación Orientada a Objetos (POO) estricta, encapsulamiento, herencia, composición, agregación y tipado estático (`typing`, `abc`, `enum`, `datetime`).
- **Base de Datos:** SQLite 3 (`sqlite3` nativo de Python) con integridad referencial activada (`PRAGMA foreign_keys = ON;`).
- **Arquitectura de Archivos Sugerida:**
  - `enums.py`: Definición de enumeraciones (`TicketStatus`, `ProductType`).
  - `models.py`: Entidades del dominio y reglas de negocio puras.
  - `database.py`: Conexión SQLite, creación de esquema DDL y capa de persistencia (Repositorios / DAOs) para guardar y reconstruir objetos.
  - `demo_flujos.py`: Script automatizado que ejecuta y verifica paso a paso los 4 Diagramas de Secuencia del Hito 6 (incluyendo casos de éxito y validaciones de error).
  - `main.py`: Interfaz de consola (CLI) interactiva para operar el sistema manualmente.

---

## 2. Enumeraciones (`enums.py`)

### `TicketStatus(Enum)`
Representa el ciclo de vida de un ticket:
- `OPEN = "open"`
- `IN_PROGRESS = "in-progress"`
- `RESOLVED = "resolved"`
- `CLOSED = "closed"`

### `ProductType(Enum)`
Representa los rubros de productos soportados por el negocio y las especialidades de los técnicos:
- `KITCHEN = "kitchen"`
- `ELECTRONICS = "electronics"`
- `SMALL_APPLIANCES = "small_appliances"`

---

## 3. Modelo de Clases y Relaciones (`models.py` - UML V2.1 Final)

### 3.1. Jerarquía de Usuarios (Herencia)

#### `User(ABC)` (Clase Abstracta)
- **Atributos:**
  - `id: Optional[int]`
  - `name: str`
  - `email: str`
  - `password: str`
- **Métodos:**
  - `login(email: str, password: str) -> bool`: Verifica si las credenciales coinciden con las del usuario.

#### `Client(User)` (Hereda de `User`)
- **Atributos adicionales:**
  - `active: bool = True`

#### `Agent(User)` (Hereda de `User`)
- **Atributos adicionales:**
  - `active: bool = True`
  - `available: bool = True`
  - `speciality: ProductType` (Dependencia `<<use>>` con `ProductType`)
- **Métodos:**
  - `get_speciality() -> ProductType`: Retorna la especialidad del técnico.
  - `is_available() -> bool`: Retorna si el técnico está disponible para recibir tickets.

#### `Admin(User)` (Hereda de `User`)
- **Atributos adicionales:** Ninguno (hereda todos los de `User`).

---

### 3.2. Entidades del Dominio

#### `Product`
- **Atributos:**
  - `id: Optional[int]`
  - `name: str`
  - `brand: str`
  - `type: ProductType` (Dependencia `<<use>>` con `ProductType`)
- **Métodos:**
  - `set_type(type: ProductType) -> None`: Valida que `type` sea una instancia válida de `ProductType` y actualiza el rubro del producto.
  - `get_type() -> ProductType`: Retorna el `ProductType` asignado al producto.

#### `Milestone` (Composición con `Ticket` - 1 a `*`)
Registra cada evento de auditoría dentro de un ticket. Su ciclo de vida depende estrictamente del `Ticket` padre.
- **Atributos:**
  - `id: Optional[int]`
  - `event_type: str` (Ej: `"Ticket Opened"`, `"Agent Assigned"`, `"Status Change"`)
  - `detail: str`
  - `date_time: datetime`
  - `user_id: int` (ID del usuario que ejecutó la acción)
- **Constructor:**
  - `__init__(self, event_type: str, detail: str, date_time: datetime, user_id: int, id: Optional[int] = None)`

#### `Message` (Agregación con `Ticket` - 1 a `*`)
Representa los mensajes intercambiados en el contexto de un ticket.
- **Atributos:**
  - `id: Optional[int]`
  - `content: str`
  - `date_time: datetime`
  - `sender_id: int`
  - `is_read: bool = False`

#### `Ticket` (Entidad Central)
- **Relaciones:**
  - Asociación Simple (`*` a `1`) con `Product`: Un ticket pertenece a exactamente un producto.
  - Asociación (`*` a `1`) con `Client`: Un cliente abre el ticket (`client_id`).
  - Asociación (`*` a `0..1`) con `Agent`: Un técnico especializado atiende el ticket (`agent_id`).
  - Composición (`1` a `*`) con `Milestone`: Lista interna `milestones: List[Milestone]`.
  - Agregación (`1` a `*`) con `Message`: Lista interna `messages: List[Message]`.
- **Atributos:**
  - `id: Optional[int]`
  - `title: str`
  - `description: str`
  - `status: TicketStatus` (Inicializa en `TicketStatus.OPEN`)
  - `created_at: datetime`
  - `closed_at: Optional[datetime] = None`
  - `category: str`
  - `priority: str`
  - `product: Product`
  - `client_id: int`
  - `agent_id: Optional[int] = None`
  - `milestones: List[Milestone]`
  - `messages: List[Message]`
- **Métodos:**
  - `open() -> None`: Establece `status = TicketStatus.OPEN` y `created_at = datetime.now()`.
  - `assign_agent(agent: Agent, admin_id: int) -> None`: Valida la regla de negocio (`self.product.get_type() == agent.get_speciality()` y `agent.is_available()`). Si cumple, asigna `self.agent_id = agent.id` y crea automáticamente un `Milestone("Agent Assigned", f"Agent {agent.name} assigned", datetime.now(), admin_id)` agregándolo a `self.milestones`. Si no cumple, lanza `ValueError` con mensaje descriptivo.
  - `update_status(new_status: TicketStatus, user_id: int) -> None`: Valida que `new_status` sea un `TicketStatus` válido, actualiza `self.status = new_status` (si es `TicketStatus.CLOSED`, llama a `self.close()`), y crea automáticamente un `Milestone("Status Change", f"Status changed to {new_status.value}", datetime.now(), user_id)` agregándolo a `self.milestones`.
  - `close() -> None`: Establece `self.status = TicketStatus.CLOSED` y `self.closed_at = datetime.now()`.
  - `add_message(message: Message) -> None`: Agrega un mensaje a `self.messages`.

---

## 4. Diagramas de Secuencia a Respetar (Hito 6)

1. **Secuencia 1 - Asignar Tipo de Producto al Producto:**
   - Actor `Admin` selecciona un `Product` por ID y ejecuta `product.set_type(type)`. Se valida el enum `ProductType` y se persiste el cambio en SQLite.
2. **Secuencia 2 - Cambiar Estado del Ticket:**
   - Actor `Agent` ejecuta `ticket.update_status(new_status, user_id)`. Se valida `TicketStatus`, se actualiza el estado del ticket y **emerge** una nueva instancia de `Milestone` que se guarda en la base de datos junto al ticket.
3. **Secuencia 3 - Crear / Abrir Ticket:**
   - Actor `Client` selecciona un `Product`, instancia un nuevo `Ticket` (`ticket.open()`) y **emerge** automáticamente el primer `Milestone("Ticket Opened", ...)` asociado al `client_id`. Todo se persiste en SQLite.
4. **Secuencia 4 - Asignar Técnico Especializado al Ticket:**
   - Actor `Admin` ejecuta `ticket.assign_agent(agent, admin_id)`. El sistema consulta `product.get_type()`, `agent.get_speciality()` y `agent.is_available()`.
   - **Rama `alt` (éxito):** Si coinciden especialidades y está disponible, asigna el agente y **emerge** un `Milestone("Agent Assigned", ...)`.
   - **Rama `else` (error):** Si no coincide la especialidad o no está disponible, rechaza la operación lanzando `ValueError("Incompatible speciality or agent unavailable")`.

---

## 5. Diseño de Base de Datos SQLite (`database.py`)

- Ejecutar siempre `PRAGMA foreign_keys = ON;` al abrir cada conexión.
- **Tabla `users`** (Single Table Inheritance):
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `name TEXT NOT NULL`
  - `email TEXT UNIQUE NOT NULL`
  - `password TEXT NOT NULL`
  - `role TEXT NOT NULL` (`'CLIENT'`, `'AGENT'`, `'ADMIN'`)
  - `active INTEGER DEFAULT 1` (usado por `Client` y `Agent`)
  - `available INTEGER DEFAULT 1` (usado por `Agent`)
  - `speciality TEXT` (valor de `ProductType`, usado por `Agent`)
- **Tabla `products`**:
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `name TEXT NOT NULL`
  - `brand TEXT NOT NULL`
  - `type TEXT NOT NULL` (valor de `ProductType`)
- **Tabla `tickets`**:
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `title TEXT NOT NULL`
  - `description TEXT NOT NULL`
  - `status TEXT NOT NULL`
  - `created_at TEXT NOT NULL` (ISO 8601)
  - `closed_at TEXT` (ISO 8601, nullable)
  - `category TEXT NOT NULL`
  - `priority TEXT NOT NULL`
  - `product_id INTEGER NOT NULL REFERENCES products(id)`
  - `client_id INTEGER NOT NULL REFERENCES users(id)`
  - `agent_id INTEGER REFERENCES users(id)`
- **Tabla `milestones`** (Composición):
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE`
  - `event_type TEXT NOT NULL`
  - `detail TEXT NOT NULL`
  - `date_time TEXT NOT NULL`
  - `user_id INTEGER NOT NULL REFERENCES users(id)`
- **Tabla `messages`** (Agregación):
  - `id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE`
  - `content TEXT NOT NULL`
  - `date_time TEXT NOT NULL`
  - `sender_id INTEGER NOT NULL REFERENCES users(id)`
  - `is_read INTEGER DEFAULT 0`