import os
import logging

logger = logging.getLogger()


# -----------------------------------------
# ------------- General Helpers -----------
# -----------------------------------------

def setup_logger(name, level='INFO'):
    """Set up a logger

    Args:
        name (string): Name of the logger
        level (string, optional): Log level. Defaults to 'INFO'.

    Returns:
        logger: the logger class
    """
    formatter = logging.Formatter(
        '%(asctime)s : %(levelname)s : %(name)s :  %(message)s')

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False

    return logger


def string_to_bool(string):
    """string_to_bool

    Arguments:
        string {string} -- Input string which should be transformed to bool

    Raises:
        TypeError: Input type not a bool or a string
        ValueError: String does not equal true or false

    Returns:
        res -- Input transformed to bool
    """
    # Check if input value is a string
    try:
        if type(string) == bool:
            res = string
        elif type(string) != str:
            raise TypeError('Not string or bool')
        else:
            if string.lower() == 'true':
                res = True
            elif string.lower() == 'false':
                res = False
            else:
                raise ValueError('String value not known')
        return res
    except Exception as err:
        print(err)
        logger.error('Transformation from string to bool not poosible, due to {}'.format(err))


