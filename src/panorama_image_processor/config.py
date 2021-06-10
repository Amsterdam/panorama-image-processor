import os
from pathlib import Path

from panorama_image_processor.datastore.base import AZURE_STORAGE, OBJECTSTORE
from panorama_image_processor.exceptions import DatastoreConfigException

PROJECT_ROOT = Path(__file__).resolve().parent
DETECTION_BASE_PATH = PROJECT_ROOT / 'detection'

PANORAMA_BASE_PATH = os.getenv('PANORAMA_BASE_PATH', PROJECT_ROOT.parents[1] / 'panorama-images')

PANORAMA_RAW_PATH = f"{PANORAMA_BASE_PATH}/raw"
PANORAMA_INTERMEDIATE_PATH = f"{PANORAMA_BASE_PATH}/intermediate"
PANORAMA_PROCESSED_PATH = f"{PANORAMA_BASE_PATH}/processed"

AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')

PANORAMA_PROCESSING_QUEUE = os.getenv('PANORAMA_PROCESSING_QUEUE', 'panorama-processing-queue')
PANORAMA_RESULT_QUEUE = os.getenv('PANORAMA_RESULT_QUEUE', 'panorama-result-queue')

PANORAMA_PROCESSED_CONTAINER = os.getenv('PANORAMA_PROCESSED_CONTAINER', 'processed')

DATASTORE_CONFIG = {
    'azure_panorama': {
        'type': AZURE_STORAGE,
        'connection_string': AZURE_STORAGE_CONNECTION_STRING
    },
    'cloudvps_objectstore_panorama': {
        'type': OBJECTSTORE
    }
}

def get_datastore_config(name: str) -> dict:
    try:
        config = DATASTORE_CONFIG[name].copy()
    except KeyError:
        raise DatastoreConfigException(f"Datastore config for {name} not found.")

    config['name'] = name
    return config