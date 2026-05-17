import re
import os
from pathlib import Path

class LogProcessor:
    def __init__(self, log_path="server_logs/latest.log"):
        self.log_path = Path(log_path)
        self.patterns = [
            {
                "id": "mixin_failure",
                "regex": r"Mixin apply for mod (\w+) failed.*Critical injection failure: @(\w+) annotation on (\w+) could not find any targets matching '(.+)' in (\w+)",
                "template": "Error de Mixin en el mod '{0}': La anotación @{1} en '{2}' no encontró su objetivo '{3}' en la clase '{4}'. Esto suele ser por una versión de mod incompatible con la versión de Minecraft."
            },
            {
                "id": "class_not_found",
                "regex": r"java\.lang\.ClassNotFoundException: (.+)",
                "template": "Clase no encontrada: '{0}'. Te falta una dependencia o el mod está dañado."
            },
            {
                "id": "out_of_memory",
                "regex": r"java\.lang\.OutOfMemoryError: (.+)",
                "template": "Error de Memoria: El servidor se quedó sin RAM. Aumentá RAM_GB en la configuración."
            },
            {
                "id": "generic_crash",
                "regex": r"\[main/ERROR\]: Minecraft has crashed!",
                "template": "Minecraft crasheó. Revisá los logs de arriba para más detalle."
            }
        ]

    def process_logs(self):
        if not self.log_path.exists():
            return []

        processed_errors = []
        seen_ids = set()

        try:
            with open(self.log_path, "r", errors="ignore") as f:
                content = f.read()

            for pattern in self.patterns:
                matches = re.findall(pattern["regex"], content)
                for match in matches:
                    # Create a unique key for this error instance
                    error_key = f"{pattern['id']}:{str(match)}"
                    if error_key not in seen_ids:
                        if isinstance(match, tuple):
                            summary = pattern["template"].format(*match)
                        else:
                            summary = pattern["template"].format(match)
                        
                        processed_errors.append({
                            "type": pattern["id"],
                            "summary": summary
                        })
                        seen_ids.add(error_key)
        except Exception as e:
            processed_errors.append({"type": "internal_error", "summary": f"Error al procesar logs: {e}"})

        return processed_errors
