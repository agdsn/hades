import pytest
from celery.utils.threads import LocalStack

from hades.agent.tasks import RPCTask, rpc_task


@pytest.fixture(autouse=True, scope="session")
def celery_request_context():
    RPCTask.request_stack = LocalStack()


def test_rpc_task_nullary():
    @rpc_task()
    def const5() -> int:
        return 5

    assert const5() == 5


def test_rpc_task_unary():
    @rpc_task()
    def add1(i: int) -> int:
        return i + 1

    assert add1(1) == 2


def test_rpc_task_unary_kwonly():
    @rpc_task()
    def add1(*, i: int) -> int:
        return i + 1

    assert add1(i=1) == 2
