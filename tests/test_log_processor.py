import pytest
from core.log_processor import LogProcessor
import os

def test_mixin_failure_detection():
    # Mock log content
    mock_log = """
[19:19:42] [main/ERROR]: Mixin apply for mod modernfix failed modernfix-common.mixins.json:perf.thread_priorities.UtilMixin from mod modernfix -> net.minecraft.class_156: org.spongepowered.asm.mixin.injection.throwables.InvalidInjectionException Critical injection failure: @ModifyArg annotation on adjustPriorityOfThreadFactory could not find any targets matching 'Lnet/minecraft/class_156;method_28122(Ljava/lang/String;)Ljava/util/concurrent/ExecutorService;' in net.minecraft.class_156.
[19:19:42] [main/ERROR]: Minecraft has crashed!
    """
    
    # Create temp log file
    log_path = "test_latest.log"
    with open(log_path, "w") as f:
        f.write(mock_log)
    
    processor = LogProcessor(log_path=log_path)
    errors = processor.process_logs()
    
    # Cleanup
    if os.path.exists(log_path):
        os.remove(log_path)
    
    assert len(errors) >= 1
    assert any("Error de Mixin en el mod 'modernfix'" in e["summary"] for e in errors)
    assert any("Minecraft crasheó" in e["summary"] for e in errors)

def test_duplicate_handling():
    mock_log = "java.lang.ClassNotFoundException: SomeClass\njava.lang.ClassNotFoundException: SomeClass"
    log_path = "test_dup.log"
    with open(log_path, "w") as f:
        f.write(mock_log)
        
    processor = LogProcessor(log_path=log_path)
    errors = processor.process_logs()
    
    if os.path.exists(log_path):
        os.remove(log_path)
        
    assert len(errors) == 1
    assert "Clase no encontrada: 'SomeClass'" in errors[0]["summary"]
