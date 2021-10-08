import time
from threading import Thread

from azure.core.exceptions import ResourceNotFoundError

from panorama_image_processor.job import PanoramaJob
from panorama_image_processor.queues.base import EmptyQueueException


class PanoramaWorker(Thread):

    def __init__(self, queue):
        Thread.__init__(self)
        self.queue = queue
        self.job = None
        self.message = None
        self._isrunning = True

    def run(self):
        print("Worker started")
        while self._isrunning:
            try:
                # Get the next job from the queue
                message, job_info = self.queue.dequeue()
                print("Job processed")
            except EmptyQueueException:
                print("Empty queueu exception")
                time.sleep(60)
                continue

            # Create the panorama job and store the current message
            self.job = PanoramaJob(**job_info)
            self.message = message

            self.job.process()

            self.finish()

    def finish(self):
        # Remove message from queue
        print(f"Job finished, removing {self.message.id}")
        try:
            self.queue.delete_message(self.message)
        except ResourceNotFoundError:
            # Message could not be deleted, probably deleted by another process
            pass
