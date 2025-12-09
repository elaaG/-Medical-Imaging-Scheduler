from PySide6.QtCore import QThread, Signal
import logging

from .model import solve_multi_machine

logger = logging.getLogger(__name__)

class SolveThread(QThread):
    
    finished_signal = Signal(object, object)   
    error_signal = Signal(str)

    def __init__(self, tasks, objective="weighted_completion", time_limit=30):
        super().__init__()
        self.tasks = tasks
        self.objective = objective
        self.time_limit = time_limit

    def run(self):
        try:
            solution, obj_val, model = solve_multi_machine(self.tasks,
                                                           time_limit=self.time_limit,
                                                           objective=self.objective)
            self.finished_signal.emit(solution, obj_val)
        except Exception as e:
            logger.exception("Solver thread exception")
            self.error_signal.emit(str(e))
