from models.task import Task, TaskGroup
from models.task_key import TaskKey


def test_task_key_default_is_no_task() -> None:
    k = TaskKey()
    assert k.task_id is None
    assert k.task_title is None


def test_task_key_with_id_only() -> None:
    k = TaskKey(task_id="DRIVE-1234")
    assert k.task_id == "DRIVE-1234"
    assert k.task_title is None


def test_task_key_with_id_and_title() -> None:
    k = TaskKey(task_id="DRIVE-1234", task_title="Fix bug")
    assert k.task_id == "DRIVE-1234"
    assert k.task_title == "Fix bug"


def test_task_key_is_frozen() -> None:
    k = TaskKey(task_id="X")
    try:
        k.task_id = "Y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("TaskKey should be frozen")


def test_task_key_equality() -> None:
    a = TaskKey(task_id="X", task_title="title")
    b = TaskKey(task_id="X", task_title="title")
    assert a == b


def test_task_key_inequality_on_id() -> None:
    a = TaskKey(task_id="X")
    b = TaskKey(task_id="Y")
    assert a != b


def test_task_key_is_hashable() -> None:
    a = TaskKey(task_id="X", task_title="t")
    b = TaskKey(task_id="X", task_title="t")
    assert {a, b} == {a}


def test_task_dataclass_defaults() -> None:
    t = Task(id="DRIVE-1234")
    assert t.id == "DRIVE-1234"
    assert t.title is None
    assert t.first_seen_ts == 0.0


def test_task_group_holds_apps() -> None:
    g = TaskGroup(task_id="X", task_title="t", apps=())
    assert g.task_id == "X"
    assert g.apps == ()
