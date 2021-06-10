from abc import ABC, abstractmethod

AZURE_STORAGE = 'azure_storage'
OBJECTSTORE = 'objectstore'


class Datastore(ABC):

    @abstractmethod
    def __init__(self, connection_config: dict):
        """

        :param connection_config: The datastore connection config
        :param read_config:
        """
        self.connection_config = connection_config

    @abstractmethod
    def connect(self):
        pass  # pragma: no cover

    @abstractmethod
    def disconnect(self):
        pass  # pragma: no cover