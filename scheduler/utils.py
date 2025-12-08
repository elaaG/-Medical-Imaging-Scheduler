import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import logging
import os
from datetime import datetime

def setup_logging(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
            logging.StreamHandler()
        ]
    )

def export_json(tasks, path):
    with open(path,'w',encoding='utf-8') as f:
        json.dump(tasks,f,indent=2)

def export_pdf(solution, path):
    with PdfPages(path) as pdf:
        fig, ax = plt.subplots(figsize=(11,6))
        machines = sorted(list({s['machine'] for s in solution}))
        machine_to_idx = {m:i for i,m in enumerate(machines)}
        palette = [plt.cm.tab20(i%20) for i in range(len(machines))]

        for s in solution:
            if s['start'] is None: continue
            mi = machine_to_idx[s['machine']]
            ax.barh(mi, s['duration'], left=s['start'], height=0.5, edgecolor='black', color=palette[mi])
            ax.text(s['start']+s['duration']/2, mi, str(s['id']), va='center', ha='center', color='white', fontsize=8)

        ax.set_yticks(range(len(machines)))
        ax.set_yticklabels(machines)
        ax.set_xlabel('Temps (minutes)')
        ax.set_title('Diagramme de Gantt - Planning patients')
        ax.invert_yaxis()
        pdf.savefig(fig)
        plt.close(fig)

        df = pd.DataFrame([{'ID':s['id'],'Machine':s['machine'],'Start':s['start'],'End':s['end'],'Staff':s.get('staff_group','')} for s in solution])
        fig2, ax2 = plt.subplots(figsize=(11,6))
        ax2.axis('off')
        tbl = ax2.table(cellText=df.values, colLabels=df.columns, loc='center')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1,1.5)
        ax2.set_title('Détail des tâches')
        pdf.savefig(fig2)
        plt.close(fig2)
