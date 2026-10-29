"""Поиск соседнего тела по точке сразу во всей детали, без обхода тел."""
from time import perf_counter

from common.reference_edge import coordinates, same_point


FACE_SELECTION_FILTER = 15877  # SelectionFilterEnum.kPartFaceFilter


def collection_items(collection):
    return [collection.Item(i) for i in range(1, collection.Count + 1)]


def face_filter_array():
    # Сгенерированная pywin32-обёртка сама формирует SAFEARRAY нужного типа.
    # VARIANT(VT_ARRAY | VT_I4, ...) здесь вызывает повторную упаковку массива
    # и TypeError "Objects for SAFEARRAYS must be sequences ...".
    return (FACE_SELECTION_FILTER,)


def body_targets(inventor, face_pairs, point_jobs, body_cache=None):
    component = inventor.comp
    filters = face_filter_array()
    jobs = {id(job["colored_face"]): job for job in point_jobs}
    result = {}
    tolerance = 1e-5
    for first_face, _ in face_pairs:
        started = perf_counter()
        owner = first_face.SurfaceBody
        owner_name = owner.Name
        if body_cache is not None:
            body_cache[owner_name] = owner
        job = jobs[id(first_face)]
        points = {id(p): p for p in (*job["outer_points"], *job["inner_points"])}.values()
        model_points = [job["sketch"].SketchToModelSpace(p.Geometry) for p in points]
        if not model_points:
            raise ValueError("Для поиска соседнего тела отсутствуют центры сверления.")
        xyz = [coordinates(p) for p in model_points]
        conversion_seconds = perf_counter() - started
        search_seconds = check_seconds = 0.0
        neighbors = set()
        search_calls = candidate_count = 0
        errors = []
        for sample in model_points:
            started = perf_counter()
            search_calls += 1
            try:
                # False включает скрытые тела; возвращаются все грани у точки.
                hits = component.FindUsingPoint(sample, filters, tolerance, False)
                faces = collection_items(hits) if hits is not None else []
            except (AttributeError, TypeError) as exc:
                raise RuntimeError("Не удалось вызвать поиск граней по точке во всей детали.") from exc
            except Exception as exc:
                errors.append(str(exc))
                search_seconds += perf_counter() - started
                continue
            search_seconds += perf_counter() - started
            started = perf_counter()
            candidate_count += len(faces)
            for face in faces:
                body = face.SurfaceBody
                name = body.Name
                if name == owner_name or name in neighbors or not body.IsSolid:
                    continue
                try:
                    same_plane = inventor.same_plane_entity(first_face, face, tol=tolerance)
                except Exception:
                    continue
                if same_plane and all(
                    same_point(coordinates(face.GetClosestPointTo(p)), p_xyz, tolerance)
                    for p, p_xyz in zip(model_points, xyz)
                ):
                    neighbors.add(name)
                    if body_cache is not None:
                        body_cache[name] = body
            check_seconds += perf_counter() - started
            # Все кандидаты у точки проверены; при попадании на шов без
            # подходящей грани повторить запрос на следующем центре.
            if neighbors:
                break
        print(f"05: Поиск соседа: запросов по всей детали — {search_calls}; "
              f"найденных граней — {candidate_count}", flush=True)
        print(f"    Центры в координатах модели: {conversion_seconds:.2f}s; "
              f"поиск граней: {search_seconds:.2f}s; проверка кандидатов: {check_seconds:.2f}s",
              flush=True)
        if len(neighbors) != 1:
            if errors:
                print("05: Ошибки поиска по точке: " + "; ".join(errors), flush=True)
            raise ValueError(
                f"Для первой грани тела '{owner_name}' требуется одно соседнее тело "
                f"с совпадающей гранью во всех центрах сверления. Найдено: {len(neighbors)}."
            )
        neighbor = next(iter(neighbors))
        result[id(first_face)] = {"owner_body": owner_name, "neighbor_body": neighbor}
        print(f"05: Тело выбранной грани: {owner_name}; соседнее тело: {neighbor}", flush=True)
    return result
