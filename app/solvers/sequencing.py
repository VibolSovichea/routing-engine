"""OR-Tools TSP sequencing solver with a fixed-first-stop constraint.

Given a driver's live start point and an ordered list of stops, solve the
TSP-style "best order to visit these stops" problem. The driver's outward-in
or inward-out preference is implemented as a fixed-first-stop constraint on
this TSP solve:

- outward_in: the first stop is the one farthest from the start point;
- inward_out: the first stop is the one nearest to the start point.

The fixed first stop is then treated as a hard constraint and the solver
optimises the remaining visits by total road distance (OR-Tools RoutingModel,
a TSP solver), so the rest of the route is still optimal given the fixed start.

The matrix is indexed 0 == start point, 1..N == stops. An optional duration
matrix may be provided for reporting leg durations.
"""

import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.models.sequencing import (
    DriverPreference,
    SequencingLeg,
    SequencingRequest,
    SequencingResponse,
)

MAX_ROUTING_TIME_SECONDS = 5.0

# Pseudo-infinite cost used to make an arc effectively forbidden.
_FORBIDDEN = 1_000_000_000


def _validate_inputs(request: SequencingRequest) -> int:
    n = len(request.stops)
    matrix = request.distances_meters

    if len(matrix) != n + 1 or any(len(row) != n + 1 for row in matrix):
        raise ValueError(
            "distances_meters must be a square (N+1) x (N+1) matrix "
            "where index 0 is the start point and indices 1..N are the stops"
        )

    for i in range(n + 1):
        if matrix[i][i] != 0:
            raise ValueError("distance matrix diagonal must be zero")

    return n


def _select_first_stop(request: SequencingRequest) -> int:
    """Pick the fixed first stop index (1..N) per driver preference."""
    n = len(request.stops)
    dists = [request.distances_meters[0][i] for i in range(1, n + 1)]

    if request.driver_preference == DriverPreference.INWARD_OUT:
        return dists.index(min(dists)) + 1
    return dists.index(max(dists)) + 1


def solve_sequencing(
    request: SequencingRequest,
    time_limit_seconds: float | None = None,
) -> SequencingResponse:
    """Solve the per-zone sequencing TSP.

    Raises:
        ValueError: If the request is malformed (see ``_validate_inputs``) or
            the solver cannot find a feasible route.
    """
    n = _validate_inputs(request)
    matrix = request.distances_meters
    first_stop = _select_first_stop(request)

    start_time = time.perf_counter()
    limit = (
        time_limit_seconds if time_limit_seconds is not None else MAX_ROUTING_TIME_SECONDS
    )

    manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == 0 and to_node != 0 and to_node != first_stop:
            # Only the fixed first stop may be reached directly from the
            # start point; every other first arc is effectively forbidden.
            return _FORBIDDEN
        return int(round(matrix[from_node][to_node]))

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.time_limit.seconds = int(limit)

    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        elapsed = time.perf_counter() - start_time
        raise ValueError(
            f"sequencing solver failed to find a feasible route "
            f"after {elapsed:.2f}s"
        )

    index = routing.Start(0)
    visit_indices: list[int] = []
    while not routing.IsEnd(index):
        visit_indices.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))

    # Node 0 is the start/depot (and the closing end node), so dropping all
    # zeros leaves exactly the stops in visit order, starting with the fixed
    # first stop.
    stop_order = [node for node in visit_indices if node != 0]
    ordered_stops = [request.stops[node - 1] for node in stop_order]

    # Build legs start -> order[0] -> order[1] -> ...
    full_nodes = [0, *stop_order]
    legs: list[SequencingLeg] = []
    total_distance = 0.0
    total_duration = 0.0
    has_durations = request.durations_seconds is not None

    for idx in range(len(full_nodes) - 1):
        a = full_nodes[idx]
        b = full_nodes[idx + 1]
        dist = matrix[a][b]
        total_distance += dist
        from_label = (
            request.start_point.label if a == 0 else request.stops[a - 1].label
        )
        to_label = (
            request.start_point.label if b == 0 else request.stops[b - 1].label
        )
        legs.append(
            SequencingLeg(
                from_label=from_label,
                to_label=to_label,
                distance_meters=dist,
                duration_seconds=(
                    request.durations_seconds[a][b] if has_durations else None
                ),
            )
        )
        if has_durations:
            total_duration += request.durations_seconds[a][b]

    return SequencingResponse(
        start_point=request.start_point,
        stops_order=ordered_stops,
        labels_order=[s.label for s in ordered_stops],
        legs=legs,
        total_distance_meters=round(total_distance, 2),
        total_duration_seconds=round(total_duration, 2) if has_durations else None,
        solver_status="SOLVED",
        solver_time_seconds=round(time.perf_counter() - start_time, 4),
    )
