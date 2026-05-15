# 🎮 Minecraft Docker Cheatsheet

Guía rápida para gestionar tu servidor mientras el script principal está corriendo.

## 📦 Gestión del Contenedor (Docker)

| Comando | Acción |
| :--- | :--- |
| `docker ps` | Ver si el servidor está prendido y qué puerto usa. |
| `docker logs -f minecraft-fabric-server` | Ver la consola del Minecraft en tiempo real (si cerraste el script). |
| `docker restart minecraft-fabric-server` | Reiniciar el servidor (útil después de agregar mods). |
| `docker stop minecraft-fabric-server` | Apagar el servidor (sin borrarlo). |
| `docker start minecraft-fabric-server` | Prender el servidor si estaba apagado. |

## 🌐 Gestión del Túnel (Playit)

| Comando | Acción |
| :--- | :--- |
| `tmux ls` | Ver si la sesión de playit está activa. |
| `tmux attach -t playit-mc` | **Entrar a ver Playit**. (Para salir de tmux sin cerrar Playit, apretá `Ctrl+B` y luego `D`). |
| `tmux kill-session -t playit-mc` | Cerrar el túnel Playit por completo. |

## 🚀 Comandos del Script Manager

Uso: `python3 minecraft_docker_manager.py [OPCIONES]`

| Opción | Acción |
| :--- | :--- |
| `--playit keep` | (Default) Mantiene Playit si ya está corriendo; si no, lo arranca. |
| `--playit new` | Reinicia Playit y archiva el log anterior. Útil si el túnel se trabó. |
| `--playit reset` | **Borra la configuración local** y permite vincular una cuenta nueva. |
| `--playit skip` | No toca Playit y arranca el servidor directo (si ya tenés túnel manual). |
| `--yes` | Saltea la pregunta de confirmación manual antes de lanzar el server. |

## 📊 Dashboard y Monitoreo

El dashboard corre en una sesión de `tmux` en segundo plano para que siempre esté disponible.

| Comando / Tecla | Acción |
| :--- | :--- |
| `tmux attach -t mc-dashboard` | **Entrar al Dashboard** (Rich TUI). |
| `Ctrl+B` y luego `D` | Salir del Dashboard sin cerrarlo (Desconectar tmux). |
| `python3 minecraft_docker_manager.py --dashboard-only` | Abrir el dashboard directamente. |
| `-n 5.0` | Cambiar intervalo de refresco (ej: cada 5s). |

> **💡 Tip de Performance:**
> Para ver **TPS** y **MSPT** en tiempo real, te recomiendo instalar el mod [Spark](https://spark.lucko.me/). Solo tirá el `.jar` en la carpeta `mods/` y reiniciá. El dashboard lo detectará automáticamente.

### Dentro del Dashboard (TUI)
- **[Q]**: Salir del dashboard.
- **[R]**: Reiniciar servidor (Próximamente).

### Control de Salida (Ctrl+C)
Al presionar `Ctrl+C` en el script principal (viendo logs), el sistema te preguntará:
- **[a]**: Apagado limpio vía RCON (guarda mundo) y cierra todo.
- **[m]**: Mantiene todo en segundo plano (Server + Dashboard).

## 🧪 Testing y Calidad (TDD)

| Comando | Acción |
| :--- | :--- |
| `./.venv/bin/python3 -m pytest tests/` | Ejecutar todos los tests unitarios. |

## 🛠️ Archivos y Mods (En tu PC)

| Carpeta | Qué hay ahí |
| :--- | :--- |
| `./mods/` | Tirá acá tus archivos `.jar`. Luego hacé un `docker restart`. |
| `./minecraft_world/` | Acá está tu mapa. Hacé backup de esta carpeta siempre. |
| `./server_config/` | Editá `server.properties` o `ops.json` (para darte OP) acá. |

---

> **¿Agregaste un mod nuevo?**
> 1. Copiá el .jar a la carpeta `mods/`.
> 2. Ejecutá `docker restart minecraft-fabric-server`.
