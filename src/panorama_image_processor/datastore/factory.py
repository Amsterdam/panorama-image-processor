from panorama_image_processor.datastore.base import Datastore, AZURE_STORAGE, OBJECTSTORE
from panorama_image_processor.datastore.azure import AzureStorageDatastore
from panorama_image_processor.datastore.objectstore import ObjectstoreDatastore


class DatastoreFactory:

    @staticmethod
    def get_datastore(config: dict, read_config: dict = None) -> Datastore:
        stores = {
            AZURE_STORAGE: AzureStorageDatastore,
            OBJECTSTORE: ObjectstoreDatastore,
        }

        store = stores.get(config.pop('type'))

        if store is None:
            raise NotImplementedError

        return store(config)
