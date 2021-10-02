import click

from panorama_image_processor.config import WORKERS
from panorama_image_processor.worker import PanoramaWorker
from panorama_image_processor.queues.azure import AzureStorageQueue
from panorama_image_processor.utils.queue import \
    queue_flush, queue_speed, queue_peek, queue_fill, queue_prepare, queue_status

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


@click.group()
def queue():
    pass


@queue.command()
@click.option('--dry-run/--no-dry-run', default=False, help='Do not fill the queue')
@click.argument('msgfile', type=click.File('r'))
def fill(dry_run, msgfile):
    queue_fill(msgfile, processing_queue, dry_run=dry_run)


@queue.command()
@click.option('--batch-size', type=int, default=5000,
              help='Batch size for getting status info')
@click.argument('msgfile', type=click.File('r'))
def status(msgfile, batch_size):
    '''
       Checks if a all messages in \b msgfile \b are processed
       by checking if the equirectangle plsu the cubic are present
       in the processed object store.
    '''
    queue_status(msgfile, batch_size)


@queue.command()
@click.option('--limit', default=-1, help='Stop processing after '
              'limit amount of files, used for debugging')
@click.argument('outfile', type=click.File('w'))
@click.argument('container')
def prepare(limit, container, outfile):
    ''' Prepare a year(container) to be processed by creating a file which contains
        messages and a report about the files being processed.

        \b
        OUTFILE:   The file that will be created with the messages. This file
                   can be used by the fill command
        CONTAINER: The container (year) to prepare
    '''
    queue_prepare(container, limit, outfile)

@queue.command()
@click.option('--interval', default=10, help='Measurement interval in seconds')
def speed(interval: int):
    '''
    Calculates msg/sec and ETA based on the approximate message count in
    queue.
    '''
    print(f'Calculating speed with an interval of {interval} seconds')
    queue_speed(processing_queue, interval)
    print('Calculating speed finished')


@queue.command()
def flush():
    '''
    Flushes the queue with all the messages, handle with care
    '''
    queue_flush(processing_queue)


@queue.command()
def peek():
    '''
    Flushes queue and return remaining messages to stdout.
    '''
    queue_peek(processing_queue)


if __name__ == '__main__':
    main()
