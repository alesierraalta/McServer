# 🏗️ Arquitectura del Sistema (McServer)

Este documento detalla la arquitectura técnica, los flujos de datos y las decisiones de diseño que permiten que el sistema de gestión de Minecraft sea portátil, resiliente y fácil de operar.

---

## 📐 Vista General del Sistema

El sistema utiliza un patrón **DooD (Docker-outside-of-Docker)**. El gestor corre en un contenedor separado pero tiene acceso al socket de Docker del host, permitiéndole orquestar el servidor de Minecraft como si fuera un proceso local.

### Diagrama de Componentes

```text
                  ┌───────────────────────────────────────────┐
                  │               MÁQUINA HOST                │
                  │        (Ubuntu / Windows / Mac)           │
                  └─────────────────────┬─────────────────────┘
                                        │
                  ┌─────────────────────▼─────────────────────┐
                  │            DOCKER ENGINE                  │
                  │      (/var/run/docker.sock)               │
                  └───────────────┬──────────────┬────────────┘
                                  │              │
        ┌─────────────────────────▼───┐  ┌───────▼────────────────────────┐
        │       CONTENEDOR MANAGER    │  │     CONTENEDOR MINECRAFT       │
        │      (mc-manager)           │  │  (minecraft-fabric-server)     │
        ├─────────────────────────────┤  ├────────────────────────────────┤
        │ - Python 3.12 (Manager API) │  │ - Java 21 (Fabric Server)      │
        │ - Tmux (Dashboard / Red)    │  │ - RCON (Port 25575)            │
        │ - Playit / Ngrok Client     │  │ - Minecraft (Port 25565)       │
        └──────────────┬──────────────┘  └───────────────┬────────────────┘
                       │                                 │
                       │          COMUNICACIÓN           │
                       └─────────────────────────────────┘
                         - Docker API (Socket)
                         - RCON (Comandos de Juego)
                         - Logs (docker logs -f)
```

---

## 🔄 Flujos de Datos y Ciclo de Vida

### 1. Inicialización y Lanzamiento
Cuando ejecutás `start_server_flow()`, ocurre la siguiente secuencia:

1.  **Validación**: Se chequean dependencias (Docker, Tmux).
2.  **Preparación**: Se configuran directorios y se restaura backup si el mundo está vacío.
3.  **Túnel**: Se lanza Playit/Ngrok en una sesión `tmux` dentro del manager.
4.  **Orquestación**: El manager invoca a la API de Docker del host para levantar el contenedor de Minecraft con los límites de CPU/RAM configurados.
5.  **Dashboard**: Se lanza el monitoreo visual en otra sesión `tmux`.

### 2. Apagado Robusto (Signal Handling)
El sistema está diseñado para evitar la corrupción de mundos:

```text
Ctrl+C (User) ──▶ Interceptado por Python ──▶ Prompt (Apagar/Mantener)
                                                     │
      ┌──────────────────────────────────────────────┘
      ▼
   OPCIÓN: APAGAR
   1. RCON Connect ──▶ Send "/stop" ──▶ Wait (20s max)
   2. Container Inspect ──▶ If Still Running? ──▶ Force "docker stop"
   3. Backup Create ──▶ Sincronizar world/ a backups/
   4. Tmux Kill ──▶ Cerrar Dash, Playit, Ngrok
   5. Exit 0
```

---

## 🌐 Red y Conectividad

El sistema soporta tres modos de conectividad, abstraídos por el manager:

| Modo | Mecanismo | Persistencia |
| :--- | :--- | :--- |
| **Playit.gg** | Túnel TCP (Secret Key) | **Alta**: IP fija basada en `playit.toml`. |
| **Ngrok** | Proxy TCP dinámico | **Baja**: La IP cambia en cada reinicio. |
| **Local/Skip** | Direct Port Forwarding | **N/A**: Depende de la red del usuario. |

---

## 💾 Estrategia de Persistencia y DooD

### Traducción de Rutas (Path Translation)
Al estar en un contenedor DooD, las rutas internas del manager (`/app/world`) no son las mismas que el Docker Engine ve en el host. El sistema resuelve esto dinámicamente:

*   **PROJECT_DIR**: Ruta absoluta dentro del contenedor manager (para backups, configs).
*   **HOST_PROJECT_PATH**: Variable de entorno que indica dónde está el proyecto en la máquina host.
*   **Binds**: El manager le dice al host: *"Montá `HOST_PROJECT_PATH/world` en el nuevo contenedor de Minecraft"*.

---

## 🛠️ Stack Tecnológico

*   **Runtime**: Python 3.12 (Manager) / Java 21 (Minecraft).
*   **CLI UI**: Rich (Panels, Tables, Live updates).
*   **Process Management**: Tmux (Sesiones persistentes).
*   **Orchestration**: Docker Engine API via CLI.
*   **Logging**: Procesador de logs regex para detectar fallos comunes.

---
*Senior Architect Note: Esta arquitectura garantiza que el estado (mundo) y la lógica (gestor) estén desacoplados, permitiendo actualizaciones del sistema sin riesgo para los datos del usuario.*
