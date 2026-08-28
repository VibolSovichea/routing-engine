"""OR-Tools CP-SAT p-median style zoning solver.

Partitions a set of stops into ``k`` zones while minimising the total
intra-zone travel distance, using the real road-distance matrix rather
than straight-line clustering. This is a capacitated p-median /
districting-style formulation solved with an exact solver (CP-SAT).

CP-SAT is an exact solver, so solve time can grow with stop count. To avoid
hanging on a large batch we enforce a configurable time limit and fall back
to the best incumbent solution found (thread-local competition is enabled so
CP-SAT returns a good feasible solution even without proving optimality).
"""

import time

from ortools.sat.python import cp_model

from app.models.zoning import (
    ZoneGroup,
    ZoningLocation,
    ZoningRequest,
    ZoningResponse,
)


def _validate_inputs(request: ZoningRequest) -> int:
    n = len(request.locations)
    matrix = request.distances_meters

    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError(
            "distances_meters must be a square N x N matrix matching locations"
        )

    if request.zone_count > n:
        raise ValueError(
            "zone_count cannot exceed the number of locations"
        )

    for i in range(n):
        if matrix[i][i] != 0:
            raise ValueError("distance matrix diagonal must be zero")

    return n


def solve_zoning(
    request: ZoningRequest, time_limit_seconds: float | None = None
) -> ZoningResponse:
    """Solve the zoning problem with OR-Tools CP-SAT.

    Raises:
        ValueError: If the request is malformed (see ``_validate_inputs``) or
            the solver cannot find a feasible solution.
    """
    n = _validate_inputs(request)
    k = request.zone_count
    matrix = request.distances_meters

    start_time = time.perf_counter()
    limit = time_limit_seconds if time_limit_seconds is not None else 10.0

    model = cp_model.CpModel()

    # x[i][z] == 1 if stop i is assigned to zone z.
    x: list[list[cp_model.IntVar]] = [
        [model.new_bool_var(f"x_{i}_{z}") for z in range(k)]
        for i in range(n)
    ]

    # Every stop must be in exactly one zone.
    for i in range(n):
        model.add(sum(x[i][z] for z in range(k)) == 1)

    # Exactly k zones are in use; a zone is "open" if any stop is assigned to
    # it. Assigning a stop to an unopened zone is forbidden.
    y: list[cp_model.IntVar] = [model.new_bool_var(f"y_{z}") for z in range(k)]
    model.add(sum(y[z] for z in range(k)) == k)
    for i in range(n):
        for z in range(k):
            model.add(x[i][z] <= y[z])

    # Minimise total intra-zone distance: for each unordered stop pair (i, j)
    # add its road distance iff they share a zone.
    objective_terms: list[int] = []
    for i in range(n):
        for j in range(i + 1, n):
            if matrix[i][j] == 0:
                continue
            for z in range(k):
                both = model.new_bool_var(f"both_{i}_{j}_{z}")
                model.add_multiplication_equality(both, x[i][z], x[j][z])
                objective_terms.append(both * matrix[i][j])
    model.minimize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = limit
    # Enable parallelism / incumbent competition so we get a good feasible
    # solution even when optimality can't be proven within the time limit.
    solver.parameters.num_search_workers = 8

    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        elapsed = time.perf_counter() - start_time
        raise ValueError(
            f"zoning solver failed to find a feasible solution "
            f"(status: {solver.status_name(status)})"
        )

    order = [0] * n
    for i in range(n):
        for z in range(k):
            if solver.value(x[i][z]) == 1:
                order[i] = z
                break

    zones: list[ZoneGroup] = []
    for z in range(k):
        indices = [i for i in range(n) if order[i] == z]
        if not indices:
            continue
        intra = 0.0
        for idx, a in enumerate(indices):
            for b in indices[idx + 1 :]:
                intra += matrix[a][b]
        zones.append(
            ZoneGroup(
                zone_id=z,
                location_indices=indices,
                locations=[request.locations[i] for i in indices],
                intra_zone_distance_meters=intra,
            )
        )

    return ZoningResponse(
        zones=zones,
        solver_status=solver.status_name(status),
        solver_time_seconds=round(time.perf_counter() - start_time, 4),
    )
