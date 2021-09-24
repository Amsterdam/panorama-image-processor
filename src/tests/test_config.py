import pytest

from panorama_image_processor import config
from panorama_image_processor.datastore.base import AZURE_STORAGE

def test_get_datastore_config():
    with pytest.raises(config.DatastoreConfigException):
        config.get_datastore_config('unkown name')
    ds = config.get_datastore_config('azure_panorama')
    ds['type'] = AZURE_STORAGE
    ds['connection_stringa'] = config.AZURE_STORAGE_CONNECTION_STRING