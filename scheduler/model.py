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

    # --- Extract parameters safely ---
    p, m, w, r, d, staff = {}, {}, {}, {}, {}, {}
    s = {i: {k: 0.0 for k in J} for i in J}

    for i in J:
        t = tasks[i]
        try:
            p[i] = float(t.get('duration', 1.0))
        except (ValueError, TypeError):
            logger.warning("Invalid duration for task %s: %s. Using 1.0", t['id'], t.get('duration'))
            p[i] = 1.0

        m[i] = t.get('machine', 'M1')

        try:
            w[i] = float(t.get('priority', 1.0))
        except (ValueError, TypeError):
            logger.warning("Invalid priority for task %s: %s. Using 1.0", t['id'], t.get('priority'))
            w[i] = 1.0

        try:
            r[i] = float(t.get('release', 0.0))
        except (ValueError, TypeError):
            logger.warning("Invalid release for task %s: %s. Using 0.0", t['id'], t.get('release'))
            r[i] = 0.0

        d_val = t.get('deadline', None)
        if d_val in [None, '']:
            d[i] = None
        else:
            try:
                d[i] = float(d_val)
            except (ValueError, TypeError):
                logger.warning("Invalid deadline for task %s: %s. Ignoring deadline.", t['id'], d_val)
                d[i] = None

        staff[i] = t.get('staff_group', None)

        # Setup times
        setup_after = t.get('setup_after', {}) or {}
        for other_id, st in setup_after.items():
            if other_id in id_to_index:
                k = id_to_index[other_id]
                try:
                    s[i][k] = float(st)
                except (ValueError, TypeError):
                    logger.warning("Invalid setup_after for %s after %s: %s. Using 0.", t['id'], other_id, st)
                    s[i][k] = 0.0

        logger.debug("Task %s -> duration=%s, release=%s, deadline=%s, setup_after=%s",
                     t['id'], p[i], r[i], d[i], {tasks[k]['id']: s[i][k] for k in J if s[i][k]>0})

    bigM = sum(p.values()) + sum(max(s[i].values()) for i in J)

    # --- Create model ---
    model = Model("Scheduler_Medical")
    model.Params.TimeLimit = time_limit
    model.Params.OutputFlag = 0
    model.Params.MIPFocus = 1

    # Start times
    S = model.addVars(J, lb=0.0, vtype=GRB.CONTINUOUS, name='Start')

    # Order binary variables
    x = model.addVars(J, J, vtype=GRB.BINARY, name='Order')

    # Makespan
    Cmax = model.addVar(vtype=GRB.CONTINUOUS, name='Cmax')

    # --- Sequencing constraints ---
    for i in J:
        for k in J:
            if i >= k:
                continue

            # Same machine
            if m[i] == m[k]:
                model.addConstr(S[i] + p[i] + s[i][k] <= S[k] + bigM*(1 - x[i,k]))
                model.addConstr(S[k] + p[k] + s[k][i] <= S[i] + bigM*x[i,k])

            # Same staff
            if staff[i] and staff[i] == staff[k]:
                model.addConstr(S[i] + p[i] + s[i][k] <= S[k] + bigM*(1 - x[i,k]))
                model.addConstr(S[k] + p[k] + s[k][i] <= S[i] + bigM*x[i,k])

    # --- Setup_after constraints ---
    for i in J:
        for k in J:
            if s[i][k] > 0:
                model.addConstr(S[i] >= S[k] + p[k] + s[i][k])

    # --- Release and deadline constraints ---
    for i in J:
        model.addConstr(S[i] >= r[i])
        if d[i] is not None:
            model.addConstr(S[i] + p[i] <= d[i])

    # --- Makespan constraint ---
    for i in J:
        model.addConstr(Cmax >= S[i] + p[i])

    # --- Objective ---
    if objective == "makespan":
        model.setObjective(Cmax, GRB.MINIMIZE)
    elif objective == "weighted_completion":
        model.setObjective(quicksum(w[i]*(S[i] + p[i]) for i in J), GRB.MINIMIZE)
    elif objective == "multi_criteria":
        staff_groups = set(staff[i] for i in J if staff[i] is not None)
        staff_work = {s: quicksum(p[i] for i in J if staff[i]==s) for s in staff_groups}
        alpha = 1.0
        beta = 0.5
        model.setObjective(alpha*Cmax + beta*quicksum(staff_work.values()), GRB.MINIMIZE)

    model.optimize()

    solution = []
    obj_val = None
    if model.Status in [GRB.OPTIMAL, GRB.TIME_LIMIT]:
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
    elif model.Status == GRB.UNBOUNDED:
        logger.error("Model is unbounded")
    else:
        logger.error("Solver did not return a solution. Status=%d", model.Status)

    return solution, obj_val, model
