import logging

from panorama_image_processor.config import WORKERS
from panorama_image_processor.worker import PanoramaWorker
from panorama_image_processor.queues.azure import AzureStorageQueue

logger = logging.getLogger(__name__)

processing_queue = AzureStorageQueue('panorama-processing-queue')
result_queue = AzureStorageQueue('panorama-result-queue')

def main():
    workers = []

    for x in range(WORKERS):
        worker = PanoramaWorker(processing_queue)
        workers.append(worker)
        worker.start()

    for w in workers:
        w.join()

    print("No more jobs to process")

if __name__ == '__main__':
    main()