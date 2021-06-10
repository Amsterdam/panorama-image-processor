import os
from pathlib import Path
import re

from azure.storage.blob import BlobServiceClient

from .base import Datastore
from panorama_image_processor.config import PANORAMA_RAW_PATH


class AzureStorageDatastore(Datastore):

    def __init__(self, connection_config={}):
        assert connection_config.get('connection_string') is not None, \
            "An Azure Storage connection string is required to use the AzureStorageDatastore"
        self._connection_string = connection_config.get('connection_string')

        self._service_client = self.connect()

    def connect(self):
        return BlobServiceClient.from_connection_string(self._connection_string)

    def disconnect(self):
        self._service_client = None

    def download_file(self, full_path, filename):
        container_name, path = re.match('([0-9]{4})/(.+)', full_path).group(1, 2)

        container_client = self._service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(path + filename)

        panorama_local_path = Path(PANORAMA_RAW_PATH) / full_path
        panorama_local_path.mkdir(parents=True, exist_ok=True)

        panorama_filename = panorama_local_path / filename

        with open(panorama_filename, "wb") as file:
            download_stream = blob_client.download_blob()
            file.write(download_stream.readall())

    def upload(self, container_name, source, destination='', source_base=''):
        container_client = self._service_client.get_container_client(container_name)

        full_path = Path(source_base) / source

        if (full_path.is_dir()):
            self.upload_dir(container_client, source, destination, source_base)
        else:
            self.upload_file(container_client, source, destination)

    def upload_file(self, container_client, source, destination, source_base=''):
        full_path = Path(source_base) / source
        with open(full_path, 'rb') as data:
            container_client.upload_blob(name=destination, data=data, overwrite=True)

    def upload_dir(self, container_client, source, destination='', source_base=''):
        full_path = Path(source_base) / source

        prefix = '' if destination == '' else destination
        prefix += Path(source).stem + '/'
        for root, dirs, files in os.walk(full_path):
            for name in files:
                dir_part = os.path.relpath(root, source)
                dir_part = '' if dir_part == '.' else dir_part + '/'
                file_path = os.path.join(root, name)
                blob_path = prefix + dir_part + name
                self.upload_file(container_client, file_path, blob_path, source_base)