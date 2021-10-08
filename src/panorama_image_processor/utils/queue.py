import asyncio
import click
import time
import datetime
import json
import io
import csv
import sys
from queue import Queue
from os import path
from pathlib import Path
from collections import defaultdict

from tabulate import tabulate
from azure.storage.queue.aio import QueueClient

from panorama_image_processor.datastore.factory import DatastoreFactory
from panorama_image_processor.datastore.base import Datastore
from panorama_image_processor.queues.base import BaseQueue
from panorama_image_processor.config import \
    get_datastore_config, PANORAMA_PROCESSING_QUEUE
from panorama_image_processor.queues.azure import AzureStorageQueue

'''
Messages have the following format:

{"path": "2016/09/15/TMX7316010203-000098/",
 "filename": "pano_0003_000129.jpg", "heading": 88.385210743338,
 "pitch": -0.353604755029295, "roll": -0.536943093754482,
 "source": "azure_panorama", "destination": "azure_panorama"}

Path is concatenation of container and path and must end with a dash.
Parameters pitch, roll and heading come from the panorama1.csv file, referenced
using the basename of the filename.

'''


PANORAMA_FILE = 'panorama1.csv'
PROCESSED_QUEUE_NAME = 'processed'


def _get_appr_count(storage_queue: AzureStorageQueue):
    ret = storage_queue.queue.get_queue_properties()
    return ret.approximate_message_count


def queue_speed(storage_queue: AzureStorageQueue, interval_sec: int):
    p1 = _get_appr_count(storage_queue)
    print(f'Sleeping {interval_sec} seconds')
    time.sleep(interval_sec)
    p2 = _get_appr_count(storage_queue)
    msg_sec = (p1 - p2) / interval_sec
    print(f'p1={p1} p2={p2}')
    if p1 == p2:
        print('Speed is 0..')
    else:
        print(f"Speed = {msg_sec} msg/sec")
        print(f"Speed = {msg_sec * 3600} msg/hour")
        delta_sec = datetime.timedelta(seconds=int(p2 / msg_sec))
        print(f'delatseconds = {delta_sec}')
        eta = datetime.datetime.now() + delta_sec
        print(f'ETA= { eta }, approx {delta_sec.days} days from now')


def _async_loop(func):
    loop = asyncio.get_event_loop()
    ret = loop.run_until_complete(func)
    loop.close()
    return ret


async def _process_chunk(msgs_chunk: list[str], func, retries=3, **func_args):
    '''
     Process a chunk of messages, using a result queue, named res_queue
     to report back which of the messages are handled succesfull.
     Each msg is handled by one coroutine, func.
     Timeout for all coroutines is set to min(len(msgs_chunk) // 100, 10).
     At max 3 retries are done. Retries only do the remaining messages.
    '''

    def _empty_queue(queue: Queue):
        ret = set()
        while not queue.empty():
            ret.add(queue.get())
        return ret

    msg_done_queue = Queue()
    remaining_msgs = set(msgs_chunk)
    processed = 0
    result = []
    timeout = max(len(msgs_chunk) // 100, 10)
    while retries > 0:
        coroutines = [func(m, res_queue=msg_done_queue, **func_args)
                      for m in remaining_msgs if m.strip() != '']
        try:
            result += await asyncio.wait_for(asyncio.gather(*coroutines), timeout)
            processed += len(result)
            break
        except asyncio.TimeoutError:
            queued_messages = set(m for m in _empty_queue(msg_done_queue))
            processed += len(queued_messages)
            remaining_msgs = set(remaining_msgs) - queued_messages
            retries -= 1
            if retries == 0:
                raise
    assert len(msgs_chunk) == processed
    return result


def grouper(iterable, n):
    chunk = []
    for i in iterable:
        chunk.append(i)
        if len(chunk) == n:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


async def _check_message(msg_str, res_queue: Queue, container_client):
    '''
      Expected to be present in processed container is ('cubic/', 'equirectangular/')
      Return msg if processed container dirs not found, else None
    '''
    msg = json.loads(msg_str)
    base_path = Path(msg['path']) / Path(msg['filename']).stem
    blobs = set()
    async for blob in container_client.walk_blobs(name_starts_with=str(base_path) + '/', timeout=10):
        blobs.add(blob.name)
    expected = {msg['path'] + Path(msg['filename']).stem + '/' + i for i in ('cubic/', 'equirectangular/')}
    res_queue.put(msg_str)
    return json.dumps(msg) if (expected - blobs) else None


async def queue_status_async(msgs, connection_string, batch_size):
    ret = []
    from azure.storage.blob.aio import BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    async with blob_service_client:
        container_client = blob_service_client.get_container_client(PROCESSED_QUEUE_NAME)
        with click.progressbar(length=len(msgs)) as bar:
            for msgs_chunk in grouper(msgs, batch_size):
                res = await _process_chunk(msgs_chunk, _check_message, container_client=container_client)
                [ret.append(r) for r in res if r is not None]
                bar.update(len(res))
        await container_client.close()
    return ret


def queue_status(msgfile, batchsize):
    object_store = None
    msgs = [line.strip() for line in msgfile]
    first_msg = json.loads(msgs[0])
    ds = get_datastore_config(first_msg['destination'])
    object_store = DatastoreFactory.get_datastore(ds)
    res = _async_loop(queue_status_async(msgs, object_store._connection_string, batchsize))
    if len(res):
        fname = msgfile.name + '.missing'
        print(f'Missing panorama images found, result in {fname}')
        with open(fname, 'w') as f:
            f.writelines([r + '\n' for r in res])
    else:
        print('No missing panorama images found')


def queue_peek(storage_queue: AzureStorageQueue, max_messages=32):
    '''
    Peeks at messages in the queue, with visibility timeout not set.
    '''
    for msg in storage_queue.queue.peek_messages(max_messages=max_messages):
        print(msg.content)


def queue_flush(storage_queue: AzureStorageQueue):
    click.confirm('Are you sure you want to flush the processing queue')
    storage_queue.purge()


class MissionCollector():

    def __init__(self, object_store: Datastore, base_path: str, missie_files, file_sizes):
        self.object_store = object_store
        self.base_path = base_path
        self.missie_files = missie_files
        self.file_sizes = file_sizes

    def __iter__(self):
        self.mission_missing = defaultdict(list)
        self.mission_queued = defaultdict(int)
        self.mission_pictures = defaultdict(int)
        self.mission_zero = defaultdict(list)
        for missie_path, files in self.missie_files.items():
            files_ext_map = {path.splitext(f)[0]: f for f in files}
            full_path = '/'.join((self.base_path, missie_path)) + '/'
            pano_csv = self.object_store.get_blob(full_path=full_path, filename=PANORAMA_FILE)
            pano_csv_reader = csv.DictReader(
                io.StringIO(pano_csv.decode('utf-8')), delimiter='\t')
            for row in pano_csv_reader:
                filename_without_ext = row['panorama_file_name']
                filename_ext = files_ext_map.get(filename_without_ext)
                if filename_ext is None:
                    self.mission_missing[missie_path].append(
                        filename_without_ext)
                    continue
                if self.file_sizes['/'.join((missie_path, filename_ext))] == 0:
                    self.mission_zero[missie_path].append(filename_ext)
                yield {
                    'source': 'azure_panorama',
                    'destination': 'azure_panorama',
                    'path': '/'.join((self.base_path, missie_path)) + '/',
                    'filename': filename_ext,
                    'heading': float(row['heading[deg]']),
                    'roll': float(row['roll[deg]']),
                    'pitch': float(row['pitch[deg]'])
                }
                self.mission_queued[missie_path] += 1
            self.mission_pictures[missie_path] = \
                len([f for f in files if f.endswith('.jpg')])

    def print_report(self):
        headers = ["Mission", "Queued", "Pictures", "Missing", "ZeroSize"]
        table = [
         (
                '/'.join((self.base_path, m)),
                self.mission_queued[m],
                self.mission_pictures[m],
                len(self.mission_missing[m]),
                '-' if len(self.mission_zero[m]) == 0
                else ','.join([i for i in self.mission_zero[m]])
         ) for m in self.mission_pictures.keys()]
        print(tabulate(table, headers=headers))
        report_missing = [
            (k, v) for k, v in self.mission_missing.items() if len(v) > 0]
        print('\nMissing files:')
        for mission, missing in report_missing:
            print(mission + ': ' + ','.join(missing))


def limit(iterable, limit: int):
    count = 0
    for i in iterable:
        yield iterable
        count += 1
        if count == limit:
            break


def queue_prepare(base_path: str, limit: int, out_file):  # noqa: C901
    source = 'azure_panorama'
    print(f'Processing container={base_path}')
    source_datastore_config = get_datastore_config(source)
    object_store = DatastoreFactory.get_datastore(source_datastore_config)
    print('Collecting files to process, be patience...')
    all_files = defaultdict(list)
    all_file_sizes = dict()
    try:
        for idx, (name, size) in enumerate(object_store.listfiles(
                base_path, extra_fields=['size'], recursive=True)):
            try:
                path, fname = name.rsplit('/', 1)
            except ValueError:
                print('ValueError')
                continue
            all_files[path].append(fname)
            all_file_sizes['/'.join((path, fname))] = size
            if idx == limit:
                break
    except FileNotFoundError:
        raise Exception(f'Path {base_path} not found')
    print('Collected files to process')
    missie_files = dict(
        (key, value) for key, value in all_files.items()
        if PANORAMA_FILE in [v for v in value])
    print('Creating output file')
    mission_collector = MissionCollector(
        object_store, base_path, missie_files, all_file_sizes)
    for msg in mission_collector:
        print(json.dumps(msg), file=out_file)
    mission_collector.print_report()


async def _send_message(msg: str, res_queue: asyncio.Queue, dry_run: bool, queue_client: QueueClient):
    try:
        if not dry_run:
            await queue_client.send_message(msg, timeout=10)
        res_queue.put(msg)
    except Exception:
        print('Error filling')


async def queue_fill_async(msg_file, queue: BaseQueue, dry_run, batch_size: int = 10000):
    print('Filling processing queue', file=sys.stderr)
    connection_string = queue.connection_string
    queue_client = QueueClient.from_connection_string(
        connection_string, queue_name=PANORAMA_PROCESSING_QUEUE)
    msgs = [line.strip() for line in msg_file]
    with click.progressbar(length=len(msgs)) as bar:
        for msgs_chunk in grouper(msgs, batch_size):
            await _process_chunk(msgs_chunk, _send_message, dry_run=dry_run, queue_client=queue_client)
            bar.update(len(msgs_chunk))
    print(f'Finished processing total={len(msgs)}', file=sys.stderr)
    await queue_client.close()


def queue_fill(msg_file, queue: BaseQueue, dry_run):
    _async_loop(queue_fill_async(msg_file, queue, dry_run))
