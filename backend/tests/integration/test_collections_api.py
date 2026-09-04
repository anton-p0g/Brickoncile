from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routers import collections
from app.infrastructure.db.collection_manager import CollectionManager
from app.infrastructure.db.models import SetTable
from app.infrastructure.db.session import get_session


def make_client(tmp_path):
    manager = CollectionManager(tmp_path / "brickoncile.db")
    manager.initialize()
    app = FastAPI()
    app.state.collection_manager = manager
    app.include_router(collections.router)

    @app.get("/probe")
    def probe(session: Annotated[Session, Depends(get_session)]) -> list[str]:
        return [row.set_num for row in session.exec(select(SetTable)).all()]

    @app.post("/probe/{set_num}")
    def add_probe(set_num: str, session: Annotated[Session, Depends(get_session)]) -> None:
        session.add(SetTable(set_num=set_num, name=set_num))
        session.commit()

    return TestClient(app), manager


def test_lists_default_and_creates_collection(tmp_path):
    client, manager = make_client(tmp_path)
    try:
        listed = client.get("/api/collections").json()
        assert len(listed) == 1
        assert listed[0]["name"] == "My Collection"
        assert listed[0]["is_default"] is True

        response = client.post("/api/collections", json={"name": "Test Collection"})
        assert response.status_code == 201
        assert response.json()["name"] == "Test Collection"
        assert len(client.get("/api/collections").json()) == 2
    finally:
        manager.close()


def test_rejects_duplicate_collection_name_with_a_clear_conflict(tmp_path):
    client, manager = make_client(tmp_path)
    try:
        assert client.post("/api/collections", json={"name": "Family"}).status_code == 201
        response = client.post("/api/collections", json={"name": " family "})
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]
    finally:
        manager.close()


def test_header_and_download_query_select_independent_databases(tmp_path):
    client, manager = make_client(tmp_path)
    try:
        default_id = client.get("/api/collections").json()[0]["id"]
        other_id = client.post("/api/collections", json={"name": "Other"}).json()["id"]

        client.post("/probe/default-set", headers={"X-Collection-ID": default_id})
        client.post("/probe/other-set", headers={"X-Collection-ID": other_id})

        assert client.get("/probe", headers={"X-Collection-ID": default_id}).json() == ["default-set"]
        assert client.get("/probe", params={"collection_id": other_id}).json() == ["other-set"]
        assert client.get("/probe").json() == ["default-set"]
    finally:
        manager.close()


def test_unknown_collection_returns_404_instead_of_using_default(tmp_path):
    client, manager = make_client(tmp_path)
    try:
        response = client.get("/probe", headers={"X-Collection-ID": "missing"})
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    finally:
        manager.close()


def test_renames_duplicates_and_deletes_a_collection(tmp_path):
    client, manager = make_client(tmp_path)
    try:
        source = client.post("/api/collections", json={"name": "Projects"}).json()
        client.post("/probe/10305-1", headers={"X-Collection-ID": source["id"]})

        renamed = client.patch(
            f"/api/collections/{source['id']}",
            json={"name": "Castle projects"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Castle projects"

        duplicated = client.post(
            f"/api/collections/{source['id']}/duplicate",
            json={"name": "Castle projects copy"},
        )
        assert duplicated.status_code == 201
        duplicate_id = duplicated.json()["id"]
        assert client.get("/probe", headers={"X-Collection-ID": duplicate_id}).json() == ["10305-1"]

        deleted = client.delete(f"/api/collections/{source['id']}")
        assert deleted.status_code == 204
        assert client.get("/probe", headers={"X-Collection-ID": source["id"]}).status_code == 404
    finally:
        manager.close()


def test_collection_management_reports_conflicts_and_protects_the_last_collection(tmp_path):
    client, manager = make_client(tmp_path)
    try:
        default = client.get("/api/collections").json()[0]
        other = client.post("/api/collections", json={"name": "Family"}).json()

        conflict = client.patch(
            f"/api/collections/{other['id']}",
            json={"name": default["name"].upper()},
        )
        assert conflict.status_code == 409

        assert client.delete(f"/api/collections/{other['id']}").status_code == 204
        protected = client.delete(f"/api/collections/{default['id']}")
        assert protected.status_code == 409
        assert "only collection" in protected.json()["detail"].lower()
    finally:
        manager.close()
