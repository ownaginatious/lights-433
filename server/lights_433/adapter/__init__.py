class Adapter(object):
    """
    An adapter to be used by the driver for
    initializing/resetting the external serial
    device.
    """

    def initialize(self):
        """
        Initializes the necessary connection(s) to the external device.
        """
        raise NotImplementedError

    def reset(self):
        """
        Performs a reset function on the external device.
        """
        raise NotImplementedError

    def close(self):
        """
        Performs actions necessary for terminating the connection to the
        external device.
        """
        raise NotImplementedError

    def read(self, *args, **kwargs):
        """
        Read from the underlying communication stream.
        """
        raise NotImplementedError

    def write(self, *args, **kwargs):
        """
        Write to the underlying communication stream.
        """
        raise NotImplementedError

    def flush(self):
        """
        Flush the underlying communication stream.
        """
        raise NotImplementedError


class NoSuchAdapterException(Exception):
    pass


def get_adapter(name):
    if name.lower() == 'rpi':
        from .rpi import RPiAdapter
        return RPiAdapter
    else:
        raise NoSuchAdapterException(name)
