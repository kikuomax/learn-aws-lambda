from __future__ import print_function
import boto3
import logging
import traceback


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

s3 = boto3.client('s3')


# Main Function
def main(event, context):
    global LOGGER
    global s3
    LOGGER.info('request ID: %s', context.aws_request_id)
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        LOGGER.info('obtaining: s3://%s/%s', bucket, key)
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj['Body']
        text = body.read().decode()
        body.close()  # is this necessary?
        print('%s' % text)
    return {
        'message': 'hello world!'
    }


# Entry Function
# wraps the main function so that any exceptions are logged
def lambda_handler(event, context):
    global LOGGER
    try:
        return main(event, context)
    except Exception as e:
        # prints the stack trace of the exception
        LOGGER.error(e)
        traceback.print_exc()
        raise e
