from collections import namedtuple
from unittest.mock import patch, MagicMock

import pytest

from azure.core.exceptions import ResourceNotFoundError
from panorama_image_processor.config import EMPTY_PROCESSING_QUEUE_TIMEOUT
from panorama_image_processor.job import PanoramaStatus
from panorama_image_processor.worker import PanoramaWorker, time
from panorama_image_processor.queues.base import EmptyQueueException


rounds = 0

@patch("panorama_image_processor.worker.PanoramaJob")
def test_PanoramaWorker(PanoramaJob, monkeypatch):
    global rounds

    queue = MagicMock()
    worker = PanoramaWorker(queue)
    Message = namedtuple('Message', ['id'])
    message = Message('123')
    job_info = {'info': 'info'}
    rounds = 2

    def _sleep(seconds):
        assert seconds == EMPTY_PROCESSING_QUEUE_TIMEOUT
        global rounds
        rounds -= 1
        if rounds == 0:
            raise Exception

    monkeypatch.setattr(time, 'sleep', _sleep)

    job = MagicMock()
    PanoramaJob.return_value = job
    queue.dequeue.side_effect = (message, job_info), EmptyQueueException, EmptyQueueException
    with pytest.raises(Exception):
        worker.run()
    job.process.assert_called_once_with()
    queue.delete_message.side_effect = ResourceNotFoundError
    queue.dequeue.side_effect = (message, job_info), EmptyQueueException, EmptyQueueException
    with pytest.raises(Exception):
        worker.run()