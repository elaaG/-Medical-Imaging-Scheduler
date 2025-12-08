from PySide6.QtCore import QThread, Signal
from .model import solve_multi_machine
import logging
logger = logging.getLogger(__name__)

class SolveThread(QThread):
    finished_signal = Signal(object, float)
    error_signal = Signal(str)

    def __init__(self, tasks, parent=None):
        super().__init__(parent)
        self.tasks = tasks

    def run(self):
        try:
            solution, obj, _ = solve_multi_machine(self.tasks)
            self.finished_signal.emit(solution, obj)
        except Exception as e:
            logger.exception("Solver error")
            self.error_signal.emit(str(e))
