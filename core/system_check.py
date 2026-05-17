import subprocess
import sys
import os
from core.config import Colors, log

class SystemChecker:
    @staticmethod
    def check_command(cmd):
        """Verifica si un comando existe en el sistema"""
        return subprocess.call(["which", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0

    @staticmethod
    def check_python_module(module_name):
        """Verifica si un módulo de Python está instalado"""
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False

    @staticmethod
    def run_with_sudo(cmd_list, description):
        """Ejecuta un comando con sudo pidiendo permiso al usuario"""
        print(f"\n{Colors.WARNING}[!] Falta {description}.{Colors.ENDC}")
        print(f"Comando necesario: {Colors.OKBLUE}{' '.join(cmd_list)}{Colors.ENDC}")
        
        choice = input(f"¿Querés que lo instale automáticamente? (s/n): ").lower()
        if choice == 's':
            try:
                # Usamos shell=True solo si es necesario, pero mejor pasar la lista a sudo
                final_cmd = ["sudo"] + cmd_list
                subprocess.check_call(final_cmd)
                log(f"{description} instalado con éxito.", Colors.OKGREEN)
                return True
            except subprocess.CalledProcessError:
                log(f"Error al instalar {description}. Por favor, hacelo manualmente.", Colors.FAIL)
                return False
        else:
            log(f"Por favor, instalá {description} manualmente para continuar.", Colors.WARNING)
            return False

    @staticmethod
    def check_docker_connectivity():
        """Verifica si el usuario tiene permisos reales para usar Docker"""
        try:
            subprocess.check_call(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    @classmethod
    def check_all(cls):
        log("--- 0. PRE-FLIGHT CHECKS (Sistema) ---", Colors.HEADER)
        
        # 1. Verificar Docker instalado
        if not cls.check_command("docker"):
            if not cls.run_with_sudo(["apt-get", "update"], "Actualizar repositorios"): return False
            if not cls.run_with_sudo(["apt-get", "install", "-y", "docker.io"], "Docker"): return False
        else:
            log("Docker detectado.", Colors.OKGREEN)

        # 2. Verificar Permisos Docker (Conectividad real)
        if not cls.check_docker_connectivity():
            try:
                user = os.getlogin()
            except OSError:
                import pwd
                user = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name
            
            # Verificamos si es un problema de grupo
            groups = subprocess.check_output(["groups", user]).decode()
            if "docker" not in groups:
                print(f"\n{Colors.WARNING}[!] Tu usuario '{user}' no tiene permisos para usar Docker.{Colors.ENDC}")
                if cls.run_with_sudo(["usermod", "-aG", "docker", user], f"Agregar {user} al grupo docker"):
                    log("\n¡Usuario agregado al grupo 'docker' con éxito!", Colors.OKGREEN)
                    log("IMPORTANTE: Debes cerrar sesión y volver a entrar (o reiniciar la terminal)", Colors.WARNING)
                    log("para que los cambios de permisos surtan efecto.", Colors.WARNING)
                    log("Una vez hecho, volvé a ejecutar el script.", Colors.OKBLUE)
                    return False # Abortamos porque la sesión actual no tiene el grupo activo
            else:
                log(f"\n{Colors.FAIL}[!] Tenés el grupo 'docker' pero no tenés acceso al socket.{Colors.ENDC}", Colors.FAIL)
                log("Esto suele pasar si acabás de agregarte al grupo y no reiniciaste la sesión.", Colors.WARNING)
                log(f"Probá ejecutando: {Colors.OKBLUE}newgrp docker{Colors.ENDC} o reiniciando tu terminal.", Colors.OKBLUE)
                return False
        else:
            log("Conectividad con Docker verificada.", Colors.OKGREEN)

        # 3. Verificar Tmux (Necesario para túneles y dashboard)
        if not cls.check_command("tmux"):
            if not cls.run_with_sudo(["apt-get", "install", "-y", "tmux"], "Tmux"): return False
        else:
            log("Tmux detectado.", Colors.OKGREEN)

        # 4. Verificar Librerías de Python
        pip_available = subprocess.call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0
        
        for lib in ["requests", "rich"]:
            if not cls.check_python_module(lib):
                if not pip_available:
                    log(f"Falta '{lib}' y no se detectó 'pip'. Por favor, instalalo manualmente.", Colors.FAIL)
                    return False
                
                print(f"\n{Colors.WARNING}[!] Falta la librería '{lib}' de Python.{Colors.ENDC}")
                choice = input(f"¿Instalar '{lib}' ahora con pip? (s/n): ").lower()
                if choice == 's':
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
                        log(f"'{lib}' instalado con éxito.", Colors.OKGREEN)
                    except subprocess.CalledProcessError:
                        log(f"Error al instalar '{lib}'. Por favor, hacelo manualmente.", Colors.FAIL)
                        return False
                else:
                    return False
        log("Librerías de Python verificadas.", Colors.OKGREEN)

        # 5. Verificar Playit
        if not cls.check_command("playit"):
            install_cmd = "curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/playit.gpg > /dev/null && echo 'deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data-ppa /' | sudo tee /etc/apt/sources.list.d/playit-cloud.list > /dev/null && sudo apt update && sudo apt install playit -y"
            print(f"\n{Colors.WARNING}[!] Falta Playit.{Colors.ENDC}")
            print(f"Comando: {Colors.OKBLUE}{install_cmd}{Colors.ENDC}")
            choice = input("¿Instalar Playit automáticamente? (s/n): ").lower()
            if choice == 's':
                os.system(install_cmd)
                log("Playit instalado.", Colors.OKGREEN)
        else:
            log("Playit detectado.", Colors.OKGREEN)

        # 4. Verificar Ngrok (Opcional)
        if not cls.check_command("ngrok"):
            print(f"\n{Colors.WARNING}[!] Ngrok no está instalado.{Colors.ENDC}")
            choice = input("¿Querés instalar Ngrok ahora? (s/n): ").lower()
            if choice == 's':
                install_cmds = [
                    "curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc > /dev/null",
                    "echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list",
                    "sudo apt update",
                    "sudo apt install ngrok"
                ]
                for cmd in install_cmds:
                    os.system(cmd)
                log("Ngrok instalado con éxito.", Colors.OKGREEN)
        else:
            log("Ngrok detectado.", Colors.OKGREEN)

        return True
