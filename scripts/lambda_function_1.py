import logging

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

# Entry Function
def lambda_handler(event, context):
    global LOGGER
    LOGGER.info('request ID: %s', context.aws_request_id)
    return {
        'message': 'hello world!'
    }
