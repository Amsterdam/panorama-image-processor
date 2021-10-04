import asyncio
from asyncio.tasks import wait_for
from re import M
from asyncio.queues import Queue
import click
import time
import datetime
import json
import io
import csv
from queue import Queue
from os import path
from pathlib import Path
from collections import defaultdict

from tabulate import tabulate
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

from azure.storage.queue.aio import QueueClient

PANORAMA_FILE = 'panorama1.csv'


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


async def _coroutine_with_retries( coroutine, retries: int, batchsize: int):
    '''
    Coroutine from Azure are not that stable, and sometimes do not respond
    back. No problem, just retry...
    '''
    timeout = batchsize // 100
    while retries > 0:
        try:
            return await asyncio.wait_for(coroutine, timeout=timeout)
            break
        except asyncio.TimeoutError:
            retries -= 1
            if retries == 0:
                raise


def grouper(iterable, n):
    chunk = []
    for i in iterable:
        chunk.append(i)
        if len(chunk) == n:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


async def check_message(container_client, msg):
    '''
      Expected to be present in processed container is ('cubic/', 'equirectangular/')
    '''
    base_path = Path(msg['path']) / Path(msg['filename']).stem
    blobs = set()
    async for blob in container_client.walk_blobs(name_starts_with=str(base_path) + '/', timeout=10):
        blobs.add(blob.name)
    expected = { msg['path'] + Path(msg['filename']).stem + '/' + i for i in ('cubic/', 'equirectangular/')}
    return json.dumps(msg) if (expected - blobs) else None


async def queue_status_async(msgs, connection_string, batchsize):
    ret = []
    from azure.storage.blob.aio import BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    async with blob_service_client:
        container_client = blob_service_client.get_container_client('processed')
        with click.progressbar(length=len(msgs)) as bar:
            for msgs_chunk in grouper(msgs, batchsize):
                res = await _coroutine_with_retries(asyncio.gather(
                            *[check_message(container_client, msg) for msg in msgs_chunk],
                            return_exceptions=True), retries=3, batchsize=batchsize)
                [ret.append(r) for r in res if r is not None]
                bar.update(len(res))
        await container_client.close()
    return ret


def queue_status(msgfile, batchsize):
    object_store = None
    msgs = [json.loads(line.strip()) for line in msgfile]
    first_msg = msgs[0]
    ds = get_datastore_config(first_msg['destination'])
    object_store = DatastoreFactory.get_datastore(ds)
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(queue_status_async(msgs, object_store._connection_string, batchsize))
    loop.close()
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
            pano_csv = self.object_store.get_blob(
                full_path='/'.join((self.base_path, missie_path)) + '/',
                filename=PANORAMA_FILE)
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


def queue_prepare(base_path: str, limit: int, out_file):
    source = 'azure_panorama'
    print(f'Processing container={base_path}')
    source_datastore_config = get_datastore_config(source)
    object_store = DatastoreFactory.get_datastore(source_datastore_config)
    print('Collecting files to process, be patience...')
    all_files = defaultdict(list)
    all_file_sizes = dict()
    try:
        for idx, (name, size) in enumerate(object_store.listfiles(
                base_path, fields=['name', 'size'])):
            try:
                path, fname = name.rsplit('/', 1)
            except ValueError:
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


async def _send_message(queue_client: QueueClient, msg: str, timeout: int, res_queue: asyncio.Queue):
    try:
        # queue_client.send_message(msg, timeout)
        res_queue.put(msg)
    except Exception:
        print('Error filling')

def _empty_queue(queue: Queue):
    ret = set()
    while not queue.empty():
        ret.add(queue.get())
    return ret

async def queue_fill_async(
        msg_file, queue: BaseQueue, dry_run, batch_size: int = 10000):
    print('Filling processing queue')
    connection_string = queue.connection_string
    queue_client = QueueClient.from_connection_string(
        connection_string, queue_name=PANORAMA_PROCESSING_QUEUE)
    msgs = [line.strip() for line in msg_file]
    with click.progressbar(length=len(msgs)) as bar:
        for msgs_chunk in grouper(msgs, batch_size):
            if not dry_run:
                msg_done_queue =  Queue()
                while retries:=3 > 0:
                    try:
                        await asyncio.wait_for(
                                asyncio.gather(
                                    *[_send_message(queue_client, m.strip(), timeout=10, res_queue=msg_done_queue)
                                    for m in msgs_chunk if m.strip() != '']), batch_size // 100)
                        break
                    except asyncio.TimeoutError:
                        msgs_chunk = set(msgs_chunk) - set(m for m in _empty_queue(msg_done_queue))
                        retries -= 1
                        if retries == 0:
                            raise
                assert len(msgs_chunk) == len(_empty_queue(msg_done_queue))
            bar.update(len(msgs_chunk))
    print(f'Finished processing total={len(msgs)}')
    await queue_client.close()


def queue_fill(msg_file, queue: BaseQueue, dry_run):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(queue_fill_async(msg_file, queue, dry_run))
    loop.close()