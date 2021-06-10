from enum import Enum


class TaskStatus(Enum):
    INIT = "init"
    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    STOPPED = "stopped"
    FAILED = "failed"


class BaseTask(object):

    def __init__(self):
        self._state = TaskStatus.INIT

    @property
    def is_running(self):
        return self._state == TaskStatus.RUNNING

    def run(self):
        pass


