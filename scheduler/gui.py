import json
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QHeaderView, 
    QProgressBar, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from scheduler.threads import SolveThread
from scheduler.gantt import GanttCanvas
from scheduler.utils import setup_logging, export_json, export_pdf

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Scheduler - Imagerie Médicale (Pro)')
        self.resize(800, 800)
        self._apply_styles()

        central = QWidget()
        self.setCentralWidget(central)
        v = QVBoxLayout(central)

       
        toolbar = QHBoxLayout()
        add_btn = QPushButton('➕ Ajouter patient')
        add_btn.clicked.connect(self.add_row)
        load_btn = QPushButton('📂 Charger exemple')
        load_btn.clicked.connect(self.load_example)
        load_json_btn = QPushButton('🔁 Import JSON')
        load_json_btn.clicked.connect(self.import_json)
        export_json_btn = QPushButton('💾 Export JSON')
        export_json_btn.clicked.connect(self.export_json)
        self.solve_btn = QPushButton('▶ Résoudre (Gurobi)')
        self.solve_btn.clicked.connect(self.start_solve)
        self.pdf_btn = QPushButton('📄 Export PDF')
        self.pdf_btn.clicked.connect(self.export_pdf)
        self.pdf_btn.setEnabled(False)

        for w in [add_btn, load_btn, load_json_btn, export_json_btn, self.solve_btn, self.pdf_btn]:
            toolbar.addWidget(w)
        toolbar.addStretch()
        v.addLayout(toolbar)

        # --- Table ---
        self.table = QTableWidget(0, 9)
        headers = ['ID','Durée','Machine','Priorité','Release','Deadline','StaffGroup','SetupAfter(JSON)','Notes']
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v.addWidget(self.table, 5)

        
        lower = QHBoxLayout()
        left = QVBoxLayout()
        self.gantt = GanttCanvas(self)
        left.addWidget(self.gantt, 3)
        self.info = QLabel('Prêt')
        left.addWidget(self.info)
        lower.addLayout(left, 3)

        right = QVBoxLayout()
        self.res_table = QTableWidget(0,5)
        self.res_table.setHorizontalHeaderLabels(['ID','Machine','Start','End','Staff'])
        self.res_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right.addWidget(self.res_table)
        self.progress = QProgressBar()
        self.progress.setRange(0,0)
        self.progress.setVisible(False)
        right.addWidget(self.progress)
        lower.addLayout(right,2)
        v.addLayout(lower,4)

        footer = QHBoxLayout()
        footer.addWidget(QLabel('Recherche ID:'))
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.search_table)
        footer.addWidget(self.search_input)
        v.addLayout(footer)

        self.load_example()

    # --- Styles ---
    def _apply_styles(self):
        qss = """
        QMainWindow { 
            background-color: #1e1e2f;  /* Dark blue-purple base */
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #e0e0e0;
        }
        QPushButton { 
            padding: 6px 12px; 
            border-radius: 6px; 
            background-color: #6a5acd;  /* Slate purple */
            color: white; 
            font-weight: bold;
        }
        QPushButton:hover { 
            background-color: #836fff;  /* Lighter purple on hover */
        }
        QPushButton:disabled {
            background-color: #555573;
            color: #cccccc;
        }
        QTableWidget { 
            font-size: 12px; 
            background-color: #2a2a3e;  /* Slightly lighter dark blue */
            gridline-color: #444466; 
            alternate-background-color: #35354b;
            color: #e0e0e0;
        }
        QTableWidget::item:selected { 
            background-color: #836fff;  /* Highlight selection in mauve */
            color: white;
        }
        QHeaderView::section { 
            background-color: #3b3b5c; 
            padding: 4px;
            border: 1px solid #555573;
            font-weight: bold;
            color: #e0e0e0;
        }
        QLabel { 
            font-size: 12px; 
            color: #e0e0e0; 
        }
        QLineEdit { 
            background-color: #2a2a3e; 
            border: 1px solid #555573; 
            padding: 4px;
            border-radius: 4px;
            color: #e0e0e0;
        }
        QLineEdit:focus {
            border: 1px solid #836fff;
        }
        QProgressBar { 
            background-color: #2a2a3e; 
            border: 1px solid #555573;
            border-radius: 5px;
            text-align: center;
            color: #e0e0e0;
        }
        QProgressBar::chunk { 
            background-color: #6a5acd; 
            border-radius: 5px;
        }
        """
        self.setStyleSheet(qss)



    # --- Add row ---
    def add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r,0, QTableWidgetItem(f'P{r+1}'))
        self.table.setItem(r,1, QTableWidgetItem('20'))
        self.table.setItem(r,2, QTableWidgetItem('IRM1'))
        self.table.setItem(r,3, QTableWidgetItem('1'))
        self.table.setItem(r,4, QTableWidgetItem('0'))
        self.table.setItem(r,5, QTableWidgetItem(''))
        self.table.setItem(r,6, QTableWidgetItem('TechA'))
        self.table.setItem(r,7, QTableWidgetItem('{}'))
        self.table.setItem(r,8, QTableWidgetItem(''))
        

    # --- Lod example ---
    def load_example(self):
        sample = [
            {"id":"P1","duration":20,"machine":"IRM1","priority":5,"release":0,"staff_group":"TechA"},
            {"id":"P2","duration":30,"machine":"IRM1","priority":2,"release":0,"staff_group":"TechA","setup_after":{"P1":5}},
            {"id":"P3","duration":15,"machine":"Scanner1","priority":3,"release":10,"staff_group":"TechB"},
            {"id":"P4","duration":45,"machine":"IRM2","priority":4,"release":0,"staff_group":"TechA"},
            {"id":"P5","duration":25,"machine":"Scanner1","priority":1,"release":0,"staff_group":"TechB"},
            {"id":"P6","duration":10,"machine":"IRM1","priority":10,"release":5,"staff_group":"TechA"}
        ]
        self.table.setRowCount(0)
        for t in sample:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r,0,QTableWidgetItem(t['id']))
            self.table.setItem(r,1,QTableWidgetItem(str(t['duration'])))
            self.table.setItem(r,2,QTableWidgetItem(t['machine']))
            self.table.setItem(r,3,QTableWidgetItem(str(t['priority'])))
            self.table.setItem(r,4,QTableWidgetItem(str(t.get('release',0))))
            self.table.setItem(r,5,QTableWidgetItem(str(t.get('deadline',''))))
            self.table.setItem(r,6,QTableWidgetItem(t.get('staff_group','')))
            self.table.setItem(r,7,QTableWidgetItem(json.dumps(t.get('setup_after',{}))))
            self.table.setItem(r,8,QTableWidgetItem(''))
        


    def import_json(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Ouvrir JSON', '', 'JSON Files (*.json)')
        if not path: return
        try:
            with open(path,'r',encoding='utf-8') as f:
                data = json.load(f)
            self.table.setRowCount(0)
            for t in data:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r,0,QTableWidgetItem(str(t.get('id',''))))
                self.table.setItem(r,1,QTableWidgetItem(str(t.get('duration',''))))
                self.table.setItem(r,2,QTableWidgetItem(str(t.get('machine',''))))
                self.table.setItem(r,3,QTableWidgetItem(str(t.get('priority',1))))
                self.table.setItem(r,4,QTableWidgetItem(str(t.get('release',0))))
                self.table.setItem(r,5,QTableWidgetItem(str(t.get('deadline',''))))
                self.table.setItem(r,6,QTableWidgetItem(str(t.get('staff_group',''))))
                self.table.setItem(r,7,QTableWidgetItem(json.dumps(t.get('setup_after',{}))))
                self.table.setItem(r,8,QTableWidgetItem(''))
            
        except Exception as e:
            QMessageBox.critical(self,'Erreur import',str(e))

    def export_json(self):
        tasks = self.read_table_tasks()
        if not tasks: return
        path, _ = QFileDialog.getSaveFileName(self,'Enregistrer JSON','', 'JSON Files (*.json)')
        if not path: return
        export_json(tasks, path)
        QMessageBox.information(self,'Export','Exporté avec succès')

    def read_table_tasks(self):
        tasks = []
        for r in range(self.table.rowCount()):
            try:
                tid = self.table.item(r,0).text() if self.table.item(r,0) else f'P{r+1}'
                duration = float(self.table.item(r,1).text()) if self.table.item(r,1) else 1.0
                machine = self.table.item(r,2).text() if self.table.item(r,2) else 'M1'
                priority = float(self.table.item(r,3).text()) if self.table.item(r,3) else 1.0
                release = float(self.table.item(r,4).text()) if self.table.item(r,4) and self.table.item(r,4).text()!='' else 0.0
                deadline = self.table.item(r,5).text() if self.table.item(r,5) and self.table.item(r,5).text()!='' else None
                staff_group = self.table.item(r,6).text() if self.table.item(r,6) else None
                setup_json = self.table.item(r,7).text() if self.table.item(r,7) else '{}'
                setup_after = json.loads(setup_json)
                tasks.append({
                    'id': tid,
                    'duration': duration,
                    'machine': machine,
                    'priority': priority,
                    'release': release,
                    'deadline': float(deadline) if deadline not in (None,'') else None,
                    'staff_group': staff_group if staff_group not in (None,'') else None,
                    'setup_after': setup_after
                })
            except Exception as e:
                QMessageBox.warning(self,'Erreur données',f'Ligne {r+1} invalide: {e}')
                return []
        return tasks

    # --- Solve ---
    def start_solve(self):
        from .model import solve_multi_machine
        tasks = self.read_table_tasks()
        if not tasks: return
        self.solve_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.thread = SolveThread(tasks)
        self.thread.finished_signal.connect(self.on_solved)
        self.thread.error_signal.connect(self.on_error)
        self.thread.start()
        self.info.setText('Résolution en cours...')

    def on_solved(self, solution, obj):
        logger.info('Received solution with %d items', len(solution))
        self.progress.setVisible(False)
        self.solve_btn.setEnabled(True)
        self.pdf_btn.setEnabled(True)
        self.info.setText(f'Terminé - objectif: {obj:.2f}')
        # populate result table
        self.res_table.setRowCount(0)
        for s in sorted(solution, key=lambda x: (x['machine'], x['start'] if x['start'] is not None else 0)):
            r = self.res_table.rowCount()
            self.res_table.insertRow(r)
            self.res_table.setItem(r,0,QTableWidgetItem(str(s['id'])))
            self.res_table.setItem(r,1,QTableWidgetItem(str(s['machine'])))
            self.res_table.setItem(r,2,QTableWidgetItem(f"{s['start']:.2f}" if s['start'] is not None else ''))
            self.res_table.setItem(r,3,QTableWidgetItem(f"{s['end']:.2f}" if s['end'] is not None else ''))
            self.res_table.setItem(r,4,QTableWidgetItem(str(s.get('staff_group',''))))
        self.gantt.plot_gantt(solution, title=f'Planning - Obj {obj:.2f}')
        self._last_solution = solution

    def on_error(self, msg):
        logger.error('Solver error: %s', msg)
        QMessageBox.critical(self,'Erreur solveur', str(msg))
        self.progress.setVisible(False)
        self.solve_btn.setEnabled(True)

    def export_pdf(self):
        if not hasattr(self,'_last_solution') or not self._last_solution:
            QMessageBox.warning(self,'PDF','Pas de solution à exporter')
            return
        path, _ = QFileDialog.getSaveFileName(self,'Exporter PDF','planning.pdf','PDF Files (*.pdf)')
        if not path: return
        export_pdf(self._last_solution, path)

    def search_table(self, text):
        t = text.strip().lower()
        for r in range(self.table.rowCount()):
            idv = self.table.item(r,0).text().lower() if self.table.item(r,0) else ''
            self.table.setRowHidden(r, t not in idv)

def main():
    import sys
    from PySide6.QtWidgets import QApplication

    setup_logging()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
