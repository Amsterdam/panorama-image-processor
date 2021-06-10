import json
import os
import uuid

from azure.storage.queue import QueueClient

from .base import BaseQueue, EmptyQueueException
from panorama_image_processor.config import AZURE_STORAGE_CONNECTION_STRING


class AzureStorageQueue(BaseQueue):

    def __init__(self, name, connection_string=None):
        self.name = name
        self.connection_string = connection_string if connection_string else AZURE_STORAGE_CONNECTION_STRING

        assert self.connection_string, "A connection string must be provided or defined in" \
                                        "config to use AzureStorageQueue"

        self.queue = QueueClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING, self.name)

    def close(self):
        """
        Close or release any connections used by the queue.
        :returns: (optional) boolean indicating success
        """
        pass

    def enqueue(self, data):
        """
        Add the provided data as json to the queue.
        :param data:
        :return: No return value.
        """
        json_data = json.dumps(data)
        self.queue.send_message(json_data)

    def dequeue(self):
        """
        Get a single message from the front of the queue, the visibility will be changed so
        the message will not be processed by other clients. Use delete_message to delete
        the message once the job is done.
        :return: The message itself and the separate job_info (contents) of the message.
        """
        pages = self.queue.receive_messages(messages_per_page=1).by_page()
        try:
            page = next(pages)
            message = next(page)
            # Job information is stored in message.content
            job_info = json.loads(message.content)
            return message, job_info
        except StopIteration:
            raise EmptyQueueException()

    def delete_message(self, message):
        """
        Delete a specific message from the queue.
        :return: No return value.
        """
        self.queue.delete_message(message.id, message.pop_receipt)

    def purge(self):
        """
        Remove all messages from the queue.
        :return: No return value.
        """
        self.queue.clear_messages()