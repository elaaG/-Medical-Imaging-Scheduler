import logging
from gurobipy import Model, GRB, quicksum

logger = logging.getLogger(__name__)

def solve_multi_machine(tasks, time_limit=30, objective="weighted_completion"):
    n = len(tasks)
    logger.info("Solving instance with %d tasks", n)

    if n == 0:
        logger.warning("No tasks provided")
        return [], None, None

    J = range(n)
    id_to_index = {tasks[i]['id']: i for i in J}

    # --- Parameters ---
    p = {i: float(tasks[i].get('duration', 1.0)) for i in J}
    m = {i: tasks[i].get('machine') for i in J}
    w = {i: float(tasks[i].get('priority', 1.0)) for i in J}
    r = {i: float(tasks[i].get('release', 0.0)) for i in J}
    d = {i: tasks[i].get('deadline', None) for i in J}
    staff = {i: tasks[i].get('staff_group', None) for i in J}

    s = {i: {k: 0.0 for k in J} for i in J}
    for i in J:
        smap = tasks[i].get('setup_after', {}) or {}
        for other_id, st in smap.items():
            if other_id in id_to_index:
                k = id_to_index[other_id]
                s[i][k] = float(st)

    bigM = sum(p[i] for i in J) + sum(max(max(s[i].values()),0) for i in J)

    # --- Model ---
    model = Model("Scheduler_Medical")
    model.Params.TimeLimit = time_limit
    model.Params.OutputFlag = 0
    model.Params.MIPFocus = 1

    # Start times
    S = model.addVars(J, lb=0.0, vtype=GRB.CONTINUOUS, name='Start')
    # Ordering binary variables
    x = model.addVars(J, J, vtype=GRB.BINARY, name='Order')
    # Makespan
    Cmax = model.addVar(vtype=GRB.CONTINUOUS, name='Cmax')

    # --- machine ---
    for i in J:
        for k in J:
            if i >= k: continue
            if m[i] == m[k]:
                model.addConstr(S[i] + p[i] + s[i][k] <= S[k] + bigM*(1 - x[i,k]))
                model.addConstr(S[k] + p[k] + s[k][i] <= S[i] + bigM*x[i,k])

    # ---  staff ---
    for i in J:
        for k in J:
            if i >= k: continue
            if staff[i] and staff[i] == staff[k]:
                model.addConstr(S[i] + p[i] + s[i][k] <= S[k] + bigM*(1 - x[i,k]))
                model.addConstr(S[k] + p[k] + s[k][i] <= S[i] + bigM*x[i,k])

    # --- Setup_after constraints ---
    for i in J:
        for k in J:
            if s[i][k] > 0:
                model.addConstr(S[i] >= S[k] + p[k] + s[i][k])

    # --- Release and  deadline ---
    for i in J:
        model.addConstr(S[i] >= r[i])
        if d[i] is not None:
            model.addConstr(S[i] + p[i] <= float(d[i]))

    # ---  constraint ---
    for i in J:
        model.addConstr(Cmax >= S[i] + p[i])

    if objective == "makespan":
        model.setObjective(Cmax, GRB.MINIMIZE)
    else:
        model.setObjective(quicksum(w[i]*(S[i] + p[i]) for i in J), GRB.MINIMIZE)

    model.optimize()

    solution = []
    if model.Status == GRB.OPTIMAL or model.Status == GRB.TIME_LIMIT:
        for i in J:
            s_val = S[i].X
            solution.append({
                "id": tasks[i]['id'],
                "machine": m[i],
                "start": s_val,
                "end": s_val + p[i],
                "duration": p[i],
                "priority": w[i],
                "staff_group": staff[i],
            })
        obj_val = model.ObjVal
        logger.info("Solved. Obj=%.2f", obj_val)
    elif model.Status == GRB.INFEASIBLE:
        logger.error("Model is infeasible")
        obj_val = None
    elif model.Status == GRB.UNBOUNDED:
        logger.error("Model is unbounded")
        obj_val = None
    else:
        logger.error("Solver did not return a solution. Status=%d", model.Status)
        obj_val = None

    return solution, obj_val, model
