# 🚀 Minecraft Docker Manager (Senior Architect Edition)

Este sistema permite gestionar un servidor de Minecraft Fabric de forma profesional, automatizada y totalmente contenerizada. Utiliza una arquitectura **DooD (Docker-outside-of-Docker)** para máxima portabilidad.

> [!TIP]
> **¿Querés entender cómo funciona por dentro?** Revisá nuestra [Documentación de Arquitectura y Diagramas](./docs/ARCHITECTURE.md).

---

## 🛠️ Instalación y Arranque Rápido

Para poner en marcha el sistema en cualquier máquina nueva:

1. **Levantar el gestor:**
   ```bash
   docker-compose up -d --build
   ```
2. **Entrar al Panel de Control:**
   ```bash
   docker exec -it mc-manager python3 minecraft_docker_manager.py
   ```

---

## 🎮 Comandos del Gestor

| Acción | Comando / Opción | Descripción |
| :--- | :--- | :--- |
| **Lanzar Server** | Opción `[1]` | Inicia el flujo completo (Red, Imagen, Minecraft). |
| **Monitoreo** | Opción `[3]` | Abre el Dashboard interactivo (TPS, RAM, Players). |
| **Mantenimiento** | Opción `[2]` | Acceso a Logs, Consola Bash y Limpieza. |
| **Respaldo** | Opción `[4]` | Crea un backup completo en la carpeta `/backups`. |
| **Hardware** | Opción `[6]` | Ajusta RAM y CPU Cores en caliente. |

---

## 📊 Monitoreo Directo (Desde el Host)

Podés acceder a las sesiones internas de `tmux` sin entrar al panel principal:

*   **Dashboard Visual:** `docker exec -it mc-manager tmux attach -t mc-dashboard`
*   **Logs del Túnel:** `docker exec -it mc-manager tmux attach -t playit-mc` (o `ngrok-mc`)
*   **Salida del Server:** `docker logs -f minecraft-fabric-server`

---

## 🏗️ Resumen de Arquitectura

El sistema separa la **Lógica de Gestión** del **Servidor de Juego**:

*   **Manager (Contenedor):** Orquestador en Python, maneja la red y el monitoreo.
*   **Minecraft (Contenedor):** Instancia pura de Fabric alimentada por el Manager.
*   **Persistencia:** Todos los datos (mundos, mods, configs) viven en tu máquina host y se montan como volúmenes.

---
*Senior Architect Note: Keep it clean, keep it fast.*
