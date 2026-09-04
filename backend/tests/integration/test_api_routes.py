import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.api.dependencies import (
    get_catalog_client,
    get_image_cache,
    get_minifig_recognizer,
    get_session,
)
from app.api.routers import minifigs, missing_parts, sets, stats
from app.domain.repositories.dtos import (
    MinifigRecognitionDTO,
    MinifigRosterEntryDTO,
    MinifigSearchResultDTO,
)
from tests.unit.fakes import (
    FakeImageCache,
    FakeMinifigRecognizer,
    FakePartsCatalogClient,
    make_minifig_metadata_dto,
    make_part_dto,
    make_set_metadata_dto,
)


@pytest.fixture
def catalog():
    """Exposed separately from `client` so a test can make the catalog start failing mid-flight."""
    return FakePartsCatalogClient(
        sets={"75192-1": make_set_metadata_dto()},
        set_parts={"75192-1": [make_part_dto("3001", 0, quantity=4)]},
        set_minifigs={"75192-1": [MinifigRosterEntryDTO(fig_num="sw0001", quantity=1, image_url=None)]},
        minifigs={"sw0001": make_minifig_metadata_dto()},
        minifig_parts={"sw0001": [make_part_dto("3624", 14, quantity=1)]},
        minifig_search={
            "Luke Skywalker": [
                MinifigSearchResultDTO(
                    fig_num="sw0001", name="Luke Skywalker", num_parts=7, image_url="https://x/fig.jpg"
                )
            ]
        },
    )


@pytest.fixture
def recognizer():
    """Exposed separately so a test can make recognition fail or come back empty."""
    return FakeMinifigRecognizer(
        [
            MinifigRecognitionDTO(
                external_id="sw0001bl",
                name="Luke Skywalker (Tatooine, White Legs)",
                score=0.87,
                image_url="https://brickognize.example/luke.webp",
                reference_url="https://www.bricklink.com/v2/catalog/catalogitem.page?M=sw0001",
            )
        ]
    )


@pytest.fixture
def client(tmp_path, catalog, recognizer):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    from app.infrastructure.db import (
        models,  # noqa: F401 — registers tables on SQLModel.metadata
    )

    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    images = FakeImageCache()

    test_app = FastAPI()
    test_app.include_router(sets.router)
    test_app.include_router(minifigs.router)
    test_app.include_router(missing_parts.router)
    test_app.include_router(stats.router)
    test_app.dependency_overrides[get_session] = override_get_session
    test_app.dependency_overrides[get_catalog_client] = lambda: catalog
    test_app.dependency_overrides[get_image_cache] = lambda: images
    test_app.dependency_overrides[get_minifig_recognizer] = lambda: recognizer

    return TestClient(test_app)


def test_add_set_and_get(client):
    resp = client.post("/api/sets", json={"set_num": "75192-1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["set"]["set_num"] == "75192-1"
    assert len(resp.json()["set"]["parts"]) == 1

    assert client.get("/api/sets/75192-1").status_code == 200


def test_adding_an_owned_set_reports_it_as_already_owned(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    resp = client.post("/api/sets", json={"set_num": "75192"})
    assert resp.status_code == 200
    # Re-adding is not an error, but it is not a fresh add either — the caller needs to be able
    # to say "you already own this" instead of reporting a second successful add.
    assert resp.json()["status"] == "exists"
    assert len(client.get("/api/sets").json()) == 1


def test_add_unknown_set_returns_404(client):
    resp = client.post("/api/sets", json={"set_num": "unknown-1"})
    assert resp.status_code == 404


FOUND = "/api/sets/75192-1/parts/3001/colors/0/found"
CONDITION = "/api/sets/75192-1/parts/3001/colors/0/condition"
SORTING = "/api/sets/75192-1/sorting"


def finish_sorting(client, path=SORTING):
    return client.post(path, json={"finished": True})


def test_a_new_set_starts_not_started_and_owes_nothing(client):
    """A freshly added set has nothing confirmed, so it is pending work rather than complete."""
    client.post("/api/sets", json={"set_num": "75192-1"})

    summary = client.get("/api/sets").json()[0]
    assert summary["status"] == "not_started"
    assert summary["quantity_found_total"] == 0
    assert summary["quantity_missing_total"] == 0
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []


def test_confirming_a_whole_part_line_completes_the_set(client):
    """One tap in find mode sends the full required quantity."""
    client.post("/api/sets", json={"set_num": "75192-1"})

    resp = client.post(FOUND, json={"found_delta": 4})
    assert resp.status_code == 200
    part = resp.json()["part"]
    assert (part["quantity_found"], part["quantity_unaccounted"]) == (4, 0)
    assert part["is_fully_found"] is True
    assert resp.json()["set_summary"]["status"] == "complete"

    # Clamped at quantity_required, so an over-large delta cannot exceed the parts list.
    assert client.post(FOUND, json={"found_delta": 99}).json()["part"]["quantity_found"] == 4


def test_partial_progress_reports_sorting_and_owes_nothing_yet(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    resp = client.post(FOUND, json={"found_delta": 1})
    assert resp.json()["set_summary"]["status"] == "sorting"
    assert resp.json()["set_summary"]["quantity_missing_total"] == 0
    # Still unfinished, so the three unfound pieces stay off the shopping list.
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []


def test_a_broken_piece_stays_found_and_is_returned_as_condition(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    resp = client.post(CONDITION, json={"quantity_found": 1, "quantity_broken": 1})

    assert resp.status_code == 200
    assert resp.json()["part"]["quantity_found"] == 1
    assert resp.json()["part"]["quantity_broken"] == 1
    assert resp.json()["part"]["quantity_unaccounted"] == 3

    finish_sorting(client)
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json()[0][
        "total_missing"
    ] == 3
    actions = [entry["action"] for entry in client.get("/api/sets/75192-1/history").json()]
    assert actions == ["marked_found", "marked_broken"]


def test_fully_found_broken_piece_appears_in_replacement_list(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(CONDITION, json={"quantity_found": 4, "quantity_broken": 1})
    finish_sorting(client)

    summary = client.get("/api/missing-parts", params={"group_by": "part"}).json()

    assert len(summary) == 1
    assert summary[0]["total_missing"] == 0
    assert summary[0]["total_broken"] == 1
    assert summary[0]["total_needed"] == 1
    assert summary[0]["contributors"][0]["quantity_found"] == 4
    assert summary[0]["contributors"][0]["quantity_broken"] == 1

    replaced = client.post(CONDITION, json={"quantity_found": 4, "quantity_broken": 0})
    assert replaced.json()["part"]["quantity_found"] == 4
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []


def test_finishing_sorting_turns_unfound_pieces_into_missing(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(FOUND, json={"found_delta": 1})

    finished = finish_sorting(client)
    assert finished.status_code == 200
    assert finished.json()["status"] == "sorted"
    assert finished.json()["quantity_missing_total"] == 3
    assert finished.json()["sorting_finished_at"] is not None

    summary = client.get("/api/missing-parts", params={"group_by": "part"}).json()
    assert len(summary) == 1
    assert summary[0]["total_missing"] == 3

    csv_resp = client.get("/api/missing-parts/export.csv")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert "3001" in csv_resp.text


def test_resuming_sorting_puts_the_set_back_in_progress(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(FOUND, json={"found_delta": 1})
    finish_sorting(client)

    resumed = client.post(SORTING, json={"finished": False})
    assert resumed.json()["status"] == "sorting"
    assert resumed.json()["sorting_finished_at"] is None
    # Found counts survive resuming; only the missing interpretation is withdrawn.
    assert resumed.json()["quantity_found_total"] == 1
    assert resumed.json()["quantity_missing_total"] == 0
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []


def test_sorting_endpoint_404s_for_unknown_set(client):
    assert client.post("/api/sets/nope-1/sorting", json={"finished": True}).status_code == 404


def test_set_summary_reports_required_total_from_parts_list(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    summary = client.get("/api/sets").json()[0]
    # num_parts is upstream metadata; quantity_required_total comes from the cached parts list
    # and is the only sound denominator for a completion percentage.
    assert summary["quantity_required_total"] == 4


def test_history_records_found_transitions_per_part(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(FOUND, json={"found_delta": 2})
    client.post(FOUND, json={"found_delta": -1})

    history = client.get("/api/sets/75192-1/history").json()
    assert [(e["part_num"], e["color_id"], e["action"]) for e in history] == [
        ("3001", 0, "marked_found"),
        ("3001", 0, "marked_missing"),
    ]
    # Quantities are found counts: two turned up, then one was walked back.
    assert (history[0]["quantity_before"], history[0]["quantity_after"]) == (0, 2)
    assert (history[1]["quantity_before"], history[1]["quantity_after"]) == (2, 1)


def test_undo_by_inverse_delta_restores_previous_count(client):
    """The undo toast replays the applied delta negated; that must land exactly back where it was."""
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(FOUND, json={"found_delta": 1})

    applied = 3
    assert client.post(FOUND, json={"found_delta": applied}).json()["part"]["quantity_found"] == 4
    assert client.post(FOUND, json={"found_delta": -applied}).json()["part"]["quantity_found"] == 1

    # The undo is itself an auditable event, not a rewrite of history.
    actions = [e["action"] for e in client.get("/api/sets/75192-1/history").json()]
    assert actions == ["marked_found", "marked_found", "marked_missing"]


def test_delete_set_removes_it_from_every_view(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post("/api/sets/75192-1/parts/3001/colors/0/mark", json={"delta": 2})
    assert len(client.get("/api/minifigs/instances").json()) == 1

    assert client.delete("/api/sets/75192-1").status_code == 204

    assert client.get("/api/sets").json() == []
    assert client.get("/api/sets/75192-1").status_code == 404
    # The set's minifig instances and its contribution to the shopping list go with it.
    assert client.get("/api/minifigs/instances").json() == []
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []
    assert client.get("/api/sets/75192-1/history").json() == []


def test_delete_unknown_set_returns_404(client):
    assert client.delete("/api/sets/nope-1").status_code == 404


def test_deleted_set_can_be_added_again_with_clean_state(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(FOUND, json={"found_delta": 3})
    finish_sorting(client)
    client.delete("/api/sets/75192-1")

    readded = client.post("/api/sets", json={"set_num": "75192-1"}).json()["set"]
    # The previous ownership's progress is gone: the set is pending work again rather than
    # inheriting stale found counts or a finished-sorting marker.
    assert readded["parts"][0]["quantity_found"] == 0
    assert readded["status"] == "not_started"
    assert readded["sorting_finished_at"] is None
    assert client.get("/api/sets/75192-1/history").json() == []


def test_bulk_add_normalizes_bare_set_numbers_and_flags_duplicates(client):
    resp = client.post("/api/sets/bulk", json={"set_nums": ["75192", "75192-1", "nope"]})
    results = resp.json()["results"]

    # A bare number gains the "-1" variant suffix, and the report shows what was stored.
    assert results[0] == {
        "set_num": "75192-1",
        "input_set_num": "75192",
        "status": "ok",
        "name": "Millennium Falcon",
        "error": None,
    }
    # The same set a second time is reported as already owned, not as a fresh add.
    assert results[1]["status"] == "exists"
    assert results[2]["status"] == "error"
    assert results[2]["error"] == "not found on Rebrickable"

    assert len(client.get("/api/sets").json()) == 1


def test_add_reports_a_set_that_landed_without_its_minifigs(client, catalog):
    """A roster failure must not read as "the set failed": the set is in the collection, and
    saying otherwise sends you looking for a set that is already on the Sets page."""
    catalog.minifigs.clear()  # the roster still lists sw0001, but fetching it now raises

    resp = client.post("/api/sets", json={"set_num": "75192-1"}).json()
    assert resp["status"] == "ok"
    assert "minifigures could not be fetched" in resp["warning"]
    assert client.get("/api/sets/75192-1").status_code == 200
    assert client.get("/api/sets/75192-1/minifigs").json() == []


def test_bulk_add_reports_a_partial_set_as_partial_not_failed(client, catalog):
    catalog.minifigs.clear()

    results = client.post("/api/sets/bulk", json={"set_nums": ["75192-1"]}).json()["results"]

    assert results[0]["status"] == "partial"
    assert "resync" in results[0]["error"]
    assert len(client.get("/api/sets").json()) == 1


def test_resync_fills_in_a_roster_that_failed_at_add_time(client, catalog):
    catalog.minifigs.clear()
    client.post("/api/sets", json={"set_num": "75192-1"})
    assert client.get("/api/sets/75192-1/minifigs").json() == []

    # Whatever made the roster fail has passed; the resync is the advertised recovery.
    catalog.minifigs.update({"sw0001": make_minifig_metadata_dto()})
    assert client.post("/api/sets/75192-1/resync").status_code == 200

    assert len(client.get("/api/sets/75192-1/minifigs").json()) == 1


def test_bulk_add_keeps_going_when_one_set_blows_up(client, monkeypatch):
    """A failure the catalog does not model (a malformed payload, a failed write) must not take
    the rest of the batch down with it: the pasted list is long and retyping it is the cost."""
    from app.application.use_cases import fetch_set as fetch_set_module

    original = fetch_set_module.FetchSetUseCase.execute_with_outcome

    async def explode_on_one(self, set_num):
        if set_num.startswith("boom"):
            raise RuntimeError("kaboom")
        return await original(self, set_num)

    monkeypatch.setattr(fetch_set_module.FetchSetUseCase, "execute_with_outcome", explode_on_one)

    resp = client.post("/api/sets/bulk", json={"set_nums": ["boom-1", "75192-1"]})
    assert resp.status_code == 200
    results = resp.json()["results"]

    assert results[0]["status"] == "error"
    assert "RuntimeError" in results[0]["error"]
    assert results[1]["status"] == "ok"
    # The good set still landed rather than being abandoned after the failure.
    assert len(client.get("/api/sets").json()) == 1


def test_sets_report_added_at(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    summary = client.get("/api/sets").json()[0]
    assert summary["added_at"].endswith("Z") or "+00:00" in summary["added_at"]


def test_missing_summary_group_by_set(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    client.post(FOUND, json={"found_delta": 3})
    finish_sorting(client)

    resp = client.get("/api/missing-parts", params={"group_by": "set"})
    assert resp.status_code == 200
    assert resp.json()[0]["source_id"] == "75192-1"
    assert resp.json()[0]["total_missing"] == 1


def test_minifig_roster_created_from_set_and_reachable(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    instances = client.get("/api/minifigs/instances").json()
    assert len(instances) == 1
    assert instances[0]["source_set_name"] == "Millennium Falcon"

    detail = client.get(f"/api/minifigs/instances/{instances[0]['instance_id']}")
    assert detail.status_code == 200
    assert detail.json()["fig_num"] == "sw0001"


def test_minifig_instance_tracks_found_and_sorting_independently(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]
    found_path = f"/api/minifigs/instances/{instance_id}/parts/3624/colors/14/found"

    overview = client.get("/api/minifigs/instances").json()[0]
    assert overview["status"] == "not_started"
    assert overview["quantity_missing_total"] == 0

    resp = client.post(found_path, json={"found_delta": 1})
    assert resp.status_code == 200
    assert resp.json()["part"]["quantity_found"] == 1
    assert resp.json()["instance_summary"]["status"] == "complete"

    overview = client.get("/api/minifigs/instances").json()[0]
    assert overview["quantity_found_total"] == 1
    assert overview["is_complete"] is True


def test_single_piece_minifig_part_can_be_found_and_broken(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]
    condition_path = (
        f"/api/minifigs/instances/{instance_id}/parts/3624/colors/14/condition"
    )

    resp = client.post(condition_path, json={"quantity_found": 1, "quantity_broken": 1})

    assert resp.status_code == 200
    assert resp.json()["part"]["quantity_broken"] == 1
    assert resp.json()["instance_summary"]["status"] == "complete"


def test_minifig_sorting_endpoint_converts_unfound_to_missing(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]
    sorting_path = f"/api/minifigs/instances/{instance_id}/sorting"

    # Nothing found and sorting unfinished, so the head is not missing yet.
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []

    finished = client.post(sorting_path, json={"finished": True})
    assert finished.status_code == 200
    assert finished.json()["status"] == "sorted"
    assert finished.json()["quantity_missing_total"] == 1

    summary = client.get("/api/missing-parts", params={"group_by": "part"}).json()
    assert len(summary) == 1
    assert summary[0]["contributors"][0]["source_type"] == "minifig_instance"

    resumed = client.post(sorting_path, json={"finished": False})
    assert resumed.json()["status"] == "not_started"
    assert client.get("/api/missing-parts", params={"group_by": "part"}).json() == []


def test_minifig_sorting_endpoint_404s_for_unknown_instance(client):
    assert client.post("/api/minifigs/instances/nope/sorting", json={"finished": True}).status_code == 404


PHOTO = ("photo.jpg", b"jpeg-bytes", "image/jpeg")


def test_identify_returns_candidates_without_adding_anything(client):
    resp = client.post("/api/minifigs/identify", files={"photo": PHOTO})

    assert resp.status_code == 200
    body = resp.json()
    assert [m["fig_num"] for m in body["matches"]] == ["sw0001"]
    assert body["matches"][0]["recognized_as"] == "Luke Skywalker (Tatooine, White Legs)"
    assert body["recognitions"][0]["external_id"] == "sw0001bl"
    # Identification is a suggestion, not a write.
    assert client.get("/api/minifigs/instances").json() == []


def test_identify_flags_a_candidate_already_owned_via_a_set(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    body = client.post("/api/minifigs/identify", files={"photo": PHOTO}).json()

    owned = body["matches"][0]["owned_instances"]
    assert len(owned) == 1
    assert owned[0]["source_set_num"] == "75192-1"
    assert owned[0]["source_set_name"] == "Millennium Falcon"


def test_identify_reports_recognitions_when_nothing_matches_the_catalog(client, catalog):
    catalog.minifig_search = {}

    body = client.post("/api/minifigs/identify", files={"photo": PHOTO}).json()

    assert body["matches"] == []
    assert len(body["recognitions"]) == 1


def test_identify_502s_when_recognition_is_unavailable(client, recognizer):
    recognizer.unavailable = True

    assert client.post("/api/minifigs/identify", files={"photo": PHOTO}).status_code == 502


def test_identify_400s_on_an_unreadable_upload(client):
    resp = client.post("/api/minifigs/identify", files={"photo": ("empty.jpg", b"", "image/jpeg")})

    assert resp.status_code == 400


def test_add_loose_minifig_creates_an_instance_with_no_source_set(client):
    resp = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["fig_num"] == "sw0001"
    assert body["source_set_num"] is None
    assert body["source_set_name"] is None
    assert len(body["parts"]) == 1

    listed = client.get("/api/minifigs/instances").json()
    assert [i["instance_id"] for i in listed] == [body["instance_id"]]


def test_a_loose_instance_sorts_like_any_other(client):
    instance_id = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]

    detail = client.get(f"/api/minifigs/instances/{instance_id}")
    assert detail.status_code == 200
    assert detail.json()["source_set_num"] is None

    found = client.post(
        f"/api/minifigs/instances/{instance_id}/parts/3624/colors/14/found", json={"found_delta": 1}
    )
    assert found.status_code == 200
    assert found.json()["instance_summary"]["is_complete"] is True


def test_add_loose_minifig_404s_for_an_unknown_fig(client):
    assert client.post("/api/minifigs/instances/loose", json={"fig_num": "fig-nope"}).status_code == 404


def test_marking_a_set_minifig_found_completes_it_without_adding_a_loose_copy(client):
    """Identifying a figure an owned set already lists resolves to that copy, not a duplicate."""
    client.post("/api/sets", json={"set_num": "75192-1"})
    before = client.get("/api/minifigs/instances").json()
    instance_id = before[0]["instance_id"]

    resp = client.post(f"/api/minifigs/instances/{instance_id}/found")

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_complete"] is True
    assert body["status"] == "complete"
    assert body["source_set_num"] == "75192-1"
    # No second instance appeared: the set's own copy is what got accounted for.
    assert len(client.get("/api/minifigs/instances").json()) == len(before)


def test_marking_found_is_logged_and_reversible(client):
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]

    client.post(f"/api/minifigs/instances/{instance_id}/found")

    history = client.get(f"/api/minifigs/instances/{instance_id}/history").json()
    assert [e["action"] for e in history] == ["marked_found"]
    # The same audit trail as checking the piece off by hand, so it undoes the same way.
    undone = client.post(
        f"/api/minifigs/instances/{instance_id}/parts/3624/colors/14/found", json={"found_delta": -1}
    )
    assert undone.json()["instance_summary"]["is_complete"] is False


def test_marking_found_leaves_a_duplicate_copy_of_the_same_fig_still_expected(client):
    """Sets often list the same fig twice; one figure in hand accounts for exactly one of them."""
    client.post("/api/sets", json={"set_num": "75192-1"})
    first = client.get("/api/minifigs/instances").json()[0]["instance_id"]
    # A second physical copy of the same fig_num, as a set with duplicates would produce.
    second = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]

    client.post(f"/api/minifigs/instances/{first}/found")

    assert client.get(f"/api/minifigs/instances/{first}").json()["is_complete"] is True
    assert client.get(f"/api/minifigs/instances/{second}").json()["is_complete"] is False


def test_marking_an_unknown_instance_found_returns_404(client):
    assert client.post("/api/minifigs/instances/nope/found").status_code == 404


def test_identify_reports_which_owned_copy_is_still_expected(client, recognizer):
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]
    client.post(f"/api/minifigs/instances/{instance_id}/found")

    resp = client.post("/api/minifigs/identify", files={"photo": ("fig.jpg", b"jpeg", "image/jpeg")})

    owned = resp.json()["matches"][0]["owned_instances"]
    assert owned[0]["instance_id"] == instance_id
    assert owned[0]["is_complete"] is True
    assert owned[0]["quantity_found_total"] == owned[0]["quantity_required_total"]


def test_delete_loose_minifig_removes_it_from_every_view(client):
    instance_id = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]
    client.post(f"/api/minifigs/instances/{instance_id}/parts/3624/colors/14/found", json={"found_delta": 1})

    assert client.delete(f"/api/minifigs/instances/{instance_id}").status_code == 204

    assert client.get(f"/api/minifigs/instances/{instance_id}").status_code == 404
    assert client.get("/api/minifigs/instances").json() == []
    assert client.get(f"/api/minifigs/instances/{instance_id}/history").json() == []


def test_delete_loose_minifig_leaves_a_duplicate_copy_alone(client):
    first = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]
    second = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]

    client.delete(f"/api/minifigs/instances/{first}")

    assert client.get(f"/api/minifigs/instances/{second}").status_code == 200


def test_delete_unknown_minifig_instance_returns_404(client):
    assert client.delete("/api/minifigs/instances/nope").status_code == 404


def test_delete_refuses_a_minifig_that_came_from_a_set(client):
    """It would reappear on the set's next resync, so the API says so instead of half-doing it."""
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]

    resp = client.delete(f"/api/minifigs/instances/{instance_id}")

    assert resp.status_code == 409
    assert "75192-1" in resp.json()["detail"]
    assert client.get(f"/api/minifigs/instances/{instance_id}").status_code == 200


def _add_second_fig_to_catalog(catalog) -> None:
    """A second catalog entry to correct a misfiled minifig onto, with its own parts list."""
    catalog.minifigs["sw0002"] = make_minifig_metadata_dto("sw0002", name="Han Solo")
    catalog.minifig_parts["sw0002"] = [make_part_dto("3626", 14, quantity=1)]


def test_correcting_a_loose_fig_num_refiles_it_under_the_new_catalog_entry(client, catalog):
    _add_second_fig_to_catalog(catalog)
    instance_id = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]

    resp = client.post(f"/api/minifigs/instances/{instance_id}/fig-num", json={"fig_num": "sw0002"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "replaced"
    assert body["previous_instance_id"] == instance_id
    assert body["instance"]["fig_num"] == "sw0002"
    assert body["instance"]["fig_name"] == "Han Solo"
    assert [p["part_num"] for p in body["instance"]["parts"]] == ["3626"]
    # The misfiled record is gone, so the collection holds one figure rather than two.
    assert client.get(f"/api/minifigs/instances/{instance_id}").status_code == 404
    assert [i["instance_id"] for i in client.get("/api/minifigs/instances").json()] == [
        body["instance"]["instance_id"]
    ]


def test_correcting_onto_a_fig_an_owned_set_still_expects_hands_it_to_that_set(client, catalog):
    _add_second_fig_to_catalog(catalog)
    client.post("/api/sets", json={"set_num": "75192-1"})
    expected_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]
    loose_id = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0002"}).json()["instance_id"]

    resp = client.post(f"/api/minifigs/instances/{loose_id}/fig-num", json={"fig_num": "sw0001"})

    body = resp.json()
    assert body["outcome"] == "claimed_by_set"
    assert body["claimed_set_num"] == "75192-1"
    assert body["claimed_set_name"] == "Millennium Falcon"
    assert body["instance"]["instance_id"] == expected_id
    assert body["instance"]["is_complete"] is True
    # The loose duplicate is gone and the set is no longer short a minifig.
    assert client.get(f"/api/minifigs/instances/{loose_id}").status_code == 404
    assert len(client.get("/api/minifigs/instances").json()) == 1


def test_correcting_a_fig_num_to_itself_changes_nothing(client):
    instance_id = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]
    client.post(f"/api/minifigs/instances/{instance_id}/parts/3624/colors/14/found", json={"found_delta": 1})

    resp = client.post(f"/api/minifigs/instances/{instance_id}/fig-num", json={"fig_num": "sw0001"})

    body = resp.json()
    assert body["outcome"] == "unchanged"
    assert body["instance"]["instance_id"] == instance_id
    assert body["instance"]["quantity_found_total"] == 1


def test_correcting_to_an_unknown_fig_num_returns_404_and_keeps_the_instance(client):
    instance_id = client.post("/api/minifigs/instances/loose", json={"fig_num": "sw0001"}).json()["instance_id"]

    resp = client.post(f"/api/minifigs/instances/{instance_id}/fig-num", json={"fig_num": "fig-nope"})

    assert resp.status_code == 404
    assert client.get(f"/api/minifigs/instances/{instance_id}").status_code == 200


def test_correcting_the_fig_num_of_a_set_minifig_is_refused(client, catalog):
    """The set's roster states which fig it holds; a resync would undo anything changed here."""
    _add_second_fig_to_catalog(catalog)
    client.post("/api/sets", json={"set_num": "75192-1"})
    instance_id = client.get("/api/minifigs/instances").json()[0]["instance_id"]

    resp = client.post(f"/api/minifigs/instances/{instance_id}/fig-num", json={"fig_num": "sw0002"})

    assert resp.status_code == 409
    assert "75192-1" in resp.json()["detail"]
    assert client.get(f"/api/minifigs/instances/{instance_id}").json()["fig_num"] == "sw0001"


def test_correcting_the_fig_num_of_an_unknown_instance_returns_404(client):
    resp = client.post("/api/minifigs/instances/nope/fig-num", json={"fig_num": "sw0001"})

    assert resp.status_code == 404


def test_manual_add_takes_a_rebrickable_link(client, catalog):
    catalog.minifigs["fig-000068"] = make_minifig_metadata_dto("fig-000068", name="Chief Wiggum")
    catalog.minifig_parts["fig-000068"] = [make_part_dto("3626", 14, quantity=1)]

    resp = client.post(
        "/api/minifigs/instances/manual",
        json={"reference": "https://rebrickable.com/minifigs/fig-000068/chief-wiggum/"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["instance"]["fig_num"] == "fig-000068"
    assert body["instance"]["fig_name"] == "Chief Wiggum"
    assert body["instance"]["source_set_num"] is None
    assert body["already_owned_count"] == 0
    assert len(client.get("/api/minifigs/instances").json()) == 1


def test_manual_add_reports_a_bricklink_link_as_unconvertible(client):
    resp = client.post(
        "/api/minifigs/instances/manual",
        json={"reference": "https://www.bricklink.com/v2/catalog/catalogitem.page?M=sw0001"},
    )

    assert resp.status_code == 400
    assert "BrickLink" in resp.json()["detail"]
    assert client.get("/api/minifigs/instances").json() == []


def test_manual_add_rejects_text_with_no_id_in_it(client):
    resp = client.post("/api/minifigs/instances/manual", json={"reference": "Chief Wiggum"})

    assert resp.status_code == 400
    assert client.get("/api/minifigs/instances").json() == []


def test_manual_add_404s_for_a_fig_id_the_catalog_does_not_have(client):
    resp = client.post("/api/minifigs/instances/manual", json={"reference": "fig-999999"})

    assert resp.status_code == 404


def test_bulk_manual_add_reports_every_line_and_keeps_the_good_ones(client, catalog):
    """One bad line must not cost the rest of a long paste."""
    catalog.minifigs["fig-000068"] = make_minifig_metadata_dto("fig-000068", name="Chief Wiggum")
    catalog.minifig_parts["fig-000068"] = [make_part_dto("3626", 14, quantity=1)]

    resp = client.post(
        "/api/minifigs/instances/manual/bulk",
        json={"references": ["fig-000068", "sw0001", "fig-999999", "https://rebrickable.com/minifigs/fig-68/"]},
    )

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert [r["status"] for r in results] == ["ok", "error", "error", "ok"]
    assert [r["input_reference"] for r in results][1] == "sw0001"
    assert "BrickLink" in results[1]["error"]
    assert results[2]["error"] == "not found on Rebrickable"
    # The short form resolved to the same figure, so the second copy knows about the first.
    assert results[3]["fig_num"] == "fig-000068"
    assert results[3]["already_owned_count"] == 1
    assert len(client.get("/api/minifigs/instances").json()) == 2


def test_stats_on_an_empty_collection(client):
    """The dashboard is the first screen a new owner sees, so it has to render before anything
    has been added rather than dividing by an empty collection."""
    body = client.get("/api/stats").json()

    assert body["totals"]["sets"] == 0
    assert body["burn_up"]["points"] == []
    assert body["sessions"]["count"] == 0
    assert len(body["activity_by_hour"]) == 24
    assert body["minifigs"]["loose_figs"] == []


def test_stats_follow_the_collection_and_its_finds(client):
    client.post("/api/sets", json={"set_num": "75192-1"})

    body = client.get("/api/stats").json()
    assert body["totals"]["sets"] == 1
    assert body["totals"]["quantity_required"] == 5  # 4 set pieces + 1 on the set's minifig
    assert body["totals"]["quantity_found"] == 0
    assert body["burn_up"]["points"] == []

    client.post("/api/sets/75192-1/parts/3001/colors/0/found", json={"found_delta": 3})

    body = client.get("/api/stats").json()
    assert body["totals"]["quantity_found"] == 3
    # The curve is replayed from the audit trail, so its last point must agree with the total.
    assert body["burn_up"]["points"][-1]["quantity_found"] == 3
    assert body["sessions"]["count"] == 1
