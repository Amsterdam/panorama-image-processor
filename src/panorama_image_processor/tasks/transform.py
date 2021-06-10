from .base import BaseTask, TaskStatus


class TransformTask(BaseTask):

    def run(self):
        self._state = TaskStatus.RUNNING
        print("Transform task is running")