from collections import namedtuple
from unittest.mock import patch, MagicMock

from azure.core.exceptions import ResourceNotFoundError
from panorama_image_processor.job import PanoramaStatus
from panorama_image_processor.worker import PanoramaWorker
from panorama_image_processor.queues.base import EmptyQueueException


@patch("panorama_image_processor.worker.PanoramaJob")
def test_PanoramaWorker(PanoramaJob):

    queue = MagicMock()
    worker = PanoramaWorker(queue, exit_on_empty=True)
    Message = namedtuple('Message', ['id'])
    message = Message('123')
    job_info = {'info': 'info'}

    job = MagicMock()
    PanoramaJob.return_value = job
    queue.dequeue.side_effect = (message, job_info), EmptyQueueException
    worker.run()
    job.process.assert_called_once_with()
    queue.delete_message.side_effect = ResourceNotFoundError
    queue.dequeue.side_effect = (message, job_info), EmptyQueueException
    worker.run()


