class EmptyQueueException(Exception):
    pass


class BaseQueue(object):

    def __init__(self, name):
        self.name = name

    def close(self):
        """
        Close or release any connections used by the queue.
        :returns: (optional) boolean indicating success
        """
        pass

    def enqueue(self, data):
        """
        Add the provided data to the queue.
        :param bytes data: Task data.
        :return: No return value.
        """
        raise NotImplementedError

    def dequeue(self):
        """
        Get a message from the front of the queue, the visibility will be changed so
        the message will not be processed by other clients. Use delete_message to delete
        the message once the job is done.
        :return: No return value.
        """
        raise NotImplementedError


    def delete_message(self, message_id):
        """
        Delete a specific message from the queue.
        :return: No return value.
        """
        raise NotImplementedError

    def purge(self):
        """
        Remove all messages from the queue.
        :return: No return value.
        """
        raise NotImplementedError