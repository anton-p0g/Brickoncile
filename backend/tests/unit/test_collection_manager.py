import pytest
from sqlmodel import Session, select

from app.domain.errors import (
    CollectionNameConflictError,
    CollectionNotFoundError,
    InvalidCollectionNameError,
    LastCollectionDeletionError,
)
from app.infrastructure.db.collection_manager import CollectionManager
from app.infrastructure.db.models import SetTable


@pytest.fixture
def manager(tmp_path):
    collection_manager = CollectionManager(tmp_path / "brickoncile.db")
    collection_manager.initialize()
    yield collection_manager
    collection_manager.close()


def test_adopts_existing_database_as_stable_default(tmp_path):
    database_path = tmp_path / "brickoncile.db"
    first_manager = CollectionManager(database_path)
    first = first_manager.initialize()
    first_manager.close()

    second_manager = CollectionManager(database_path)
    second = second_manager.initialize()
    records = second_manager.list_collections()
    second_manager.close()

    assert first.id == second.id
    assert [(record.name, record.is_default) for record in records] == [("My Collection", True)]
    assert records[0].database_path == database_path


def test_creates_an_empty_isolated_database_with_an_opaque_filename(manager):
    default = manager.get_collection(None)
    created = manager.create_collection("Sister's collection")

    assert created.database_path.parent.name == "collections"
    assert created.database_path.name == f"{created.id}.db"
    assert "Sister" not in str(created.database_path)

    with Session(manager.get_engine(default.id)) as session:
        session.add(SetTable(set_num="75192-1", name="Falcon"))
        session.commit()

    with Session(manager.get_engine(default.id)) as session:
        assert len(session.exec(select(SetTable)).all()) == 1
    with Session(manager.get_engine(created.id)) as session:
        assert session.exec(select(SetTable)).all() == []


@pytest.mark.parametrize("name", ["", "   ", "line\nbreak", "hidden\u202eright-to-left", "x" * 51])
def test_rejects_invalid_names(manager, name):
    with pytest.raises(InvalidCollectionNameError):
        manager.create_collection(name)


def test_names_are_unique_after_trimming_case_and_unicode_normalisation(manager):
    created = manager.create_collection("  Family LEGO  ")

    assert created.name == "Family LEGO"
    with pytest.raises(CollectionNameConflictError):
        manager.create_collection("family lego")


def test_unknown_collection_does_not_fall_back_to_default(manager):
    with pytest.raises(CollectionNotFoundError):
        manager.get_engine("not-a-real-id")


def test_renames_collection_without_moving_its_database(manager):
    created = manager.create_collection("Before")

    renamed = manager.rename_collection(created.id, "  After  ")

    assert renamed.name == "After"
    assert renamed.database_path == created.database_path
    assert manager.get_collection(created.id).name == "After"


def test_rename_allows_the_same_collection_name_but_rejects_another(manager):
    first = manager.create_collection("Family")
    second = manager.create_collection("Projects")

    assert manager.rename_collection(first.id, " family ").name == "family"
    with pytest.raises(CollectionNameConflictError):
        manager.rename_collection(second.id, "FAMILY")


def test_duplicates_collection_data_into_an_independent_database(manager):
    source = manager.create_collection("Original")
    with Session(manager.get_engine(source.id)) as session:
        session.add(SetTable(set_num="10305-1", name="Lion Knights' Castle"))
        session.commit()

    duplicate = manager.duplicate_collection(source.id, "Original copy")

    assert duplicate.id != source.id
    assert duplicate.database_path != source.database_path
    with Session(manager.get_engine(duplicate.id)) as session:
        copied = session.exec(select(SetTable)).all()
        assert [row.set_num for row in copied] == ["10305-1"]
        session.add(SetTable(set_num="21318-1", name="Tree House"))
        session.commit()
    with Session(manager.get_engine(source.id)) as session:
        assert [row.set_num for row in session.exec(select(SetTable)).all()] == ["10305-1"]


def test_deletes_non_default_collection_and_its_database(manager):
    created = manager.create_collection("Temporary")
    database_path = created.database_path
    manager.get_engine(created.id)

    manager.delete_collection(created.id)

    assert not database_path.exists()
    with pytest.raises(CollectionNotFoundError):
        manager.get_collection(created.id)


def test_deleting_default_promotes_another_collection(manager):
    default = manager.get_collection(None)
    replacement = manager.create_collection("Replacement")

    manager.delete_collection(default.id)

    assert manager.get_collection(None).id == replacement.id
    assert manager.get_collection(replacement.id).is_default is True


def test_refuses_to_delete_the_only_collection(manager):
    default = manager.get_collection(None)

    with pytest.raises(LastCollectionDeletionError):
        manager.delete_collection(default.id)

    assert manager.get_collection(default.id) == default
