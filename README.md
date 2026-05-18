# 🚀 Minecraft Docker Manager (Senior Architect Edition)

Este sistema permite gestionar un servidor de Minecraft Fabric de forma profesional, automatizada y totalmente contenerizada. Utiliza una arquitectura **DooD (Docker-outside-of-Docker)** para que el gestor pueda correr en cualquier PC con Docker sin dependencias locales.

---

## 🛠️ Instalación y Arranque Rápido

Para poner en marcha el sistema en cualquier máquina nueva:

1. **Clonar el repositorio** y entrar a la carpeta.
2. **Levantar el gestor con Docker Compose:**
   ```bash
   docker-compose up -d --build
   ```
3. **Entrar al Panel de Control:**
   ```bash
   docker exec -it mc-manager python3 minecraft_docker_manager.py
   ```

---

## 🎮 Comandos del Gestor (Dentro del contenedor)

Una vez dentro del panel interactivo (`minecraft_docker_manager.py`), tenés las siguientes opciones:

| Opción | Comando Interno | Descripción |
| :--- | :--- | :--- |
| **[1] Iniciar Servidor** | `start_server_flow()` | Inicia el flujo completo: chequeo de sistema, elección de túnel (Playit/Ngrok), construcción de imagen y lanzamiento del Minecraft. |
| **[2] Gestión de Docker** | `docker_menu()` | Submenú para ver logs en vivo, entrar a la consola Bash del server, ver estadísticas de recursos o hacer limpieza total. |
| **[3] Abrir Dashboard** | `MCDashboard().run()` | Abre la interfaz visual de monitoreo (TPS, RAM, Jugadores) sin reiniciar nada. |
| **[4] Crear Backup** | `create_backup()` | Genera un archivo `.zip` en `/backups` con el mundo, mods y configuraciones actuales. |
| **[5] Gestión de Mods** | `mod_menu()` | Herramienta para analizar y organizar mods entre Cliente (`modsC`) y Servidor (`mods`). |
| **[6] Configuración** | `interactive_config()` | Ajusta RAM, Distancia de Renderizado, CPU Cores y propiedades del `server.properties`. |
| **[7] Ver Errores** | `show_processed_errors()` | Analiza los logs actuales y muestra errores conocidos (crashes, fallos de mods). |

---

## 📊 Monitoreo y Acceso Directo

El sistema utiliza `tmux` dentro del contenedor para mantener los procesos vivos. Podés acceder a ellos directamente desde el host:

### Dashboard Visual
Para ver el estado del servidor (TPS, RAM, Entidades):
```bash
docker exec -it mc-manager tmux attach -t mc-dashboard
```

### Túneles (Logs de Red)
*   **Playit.gg:** `docker exec -it mc-manager tmux attach -t playit-mc`
*   **Ngrok:** `docker exec -it mc-manager tmux attach -t ngrok-mc`

### Logs de Minecraft
Para ver la salida directa del servidor de Minecraft:
```bash
docker logs -f minecraft-fabric-server
```

---

## 📁 Estructura de Archivos Importantes

*   `world/`: Contiene los datos del mapa de Minecraft.
*   `mods/`: Mods instalados en el servidor.
*   `server_config/`: Configuraciones (`server.properties`, `whitelist.json`, etc.).
*   `backups/`: Copias de seguridad automáticas y manuales.
*   `docker-compose.yml`: Define cómo se levanta el entorno de gestión.

---

## ⚠️ Notas de Seguridad y Arquitectura

*   **Socket de Docker:** El contenedor manager monta `/var/run/docker.sock`. Esto le da permisos para crear y destruir otros contenedores en el host.
*   **Persistencia:** Todos los datos importantes están bindeados a carpetas locales. Si borrás el contenedor manager, tus mundos y configuraciones **NO** se pierden.
*   **Apagado Robusto:** Al usar `Ctrl+C` en el panel principal y elegir `[a]pagar`, el script asegura el cierre de RCON, detiene el contenedor de Minecraft y mata los procesos de los túneles automáticamente.

---
*Desarrollado con mentalidad de Senior Architect. Keep it clean, keep it fast.*
