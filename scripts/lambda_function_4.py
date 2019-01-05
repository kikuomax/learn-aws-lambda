from __future__ import print_function
import boto3
import json
import logging
import os
import traceback


# logging level
# may be specified in the environment variable COMPREHEND_S3_LOGGING_LEVEL
LOGGING_LEVEL_ENV_NAME = 'COMPREHEND_S3_LOGGING_LEVEL'
DEFAULT_LOGGING_LEVEL = 'INFO'
LOGGING_LEVEL = os.getenv(LOGGING_LEVEL_ENV_NAME, DEFAULT_LOGGING_LEVEL)
LOGGING_LEVEL = LOGGING_LEVEL in ('NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL') and LOGGING_LEVEL or DEFAULT_LOGGING_LEVEL
LOGGER = logging.getLogger()
print('setting logging level to %s' % LOGGING_LEVEL)
LOGGER.setLevel(getattr(logging, LOGGING_LEVEL))

# name of the region that hosts Amazon Comprehend
# may be specified in the environment variable COMPREHEND_REGION
COMPREHEND_REGION_ENV_NAME = 'COMPREHEND_REGION'
DEFAULT_COMPREHEND_REGION = 'us-east-2'
COMPREHEND_REGION = os.getenv(
    COMPREHEND_REGION_ENV_NAME, DEFAULT_COMPREHEND_REGION)
LOGGER.info('Amazon Comprehend is hosted in %s', COMPREHEND_REGION)

# bucket of the output
# may be specified in the environment variable COMPREHEND_S3_OUTPUT_BUCKET
# same as the input object if omitted = None
OUTPUT_BUCKET_ENV_NAME = 'COMPREHEND_S3_OUTPUT_BUCKET'
OUTPUT_BUCKET = os.getenv(OUTPUT_BUCKET_ENV_NAME)

# folder of the output
# may be specified in the environment variable COMPREHEND_S3_OUTPUT_FOLDER
# "comprehend" by default
# trailing slash ('/') is removed
OUTPUT_FOLDER_ENV_NAME = 'COMPREHEND_S3_OUTPUT_FOLDER'
DEFAULT_OUTPUT_FOLDER = 'comprehend'
OUTPUT_FOLDER = os.getenv(OUTPUT_FOLDER_ENV_NAME, DEFAULT_OUTPUT_FOLDER)
OUTPUT_FOLDER = OUTPUT_FOLDER.rstrip('/')
LOGGER.info('output bucket=%s, folder=%s', OUTPUT_BUCKET, OUTPUT_FOLDER)

s3 = boto3.client('s3')
comprehend = boto3.client('comprehend', region_name=COMPREHEND_REGION)


def detect_dominant_language(text):
    """
    Detects the dominant language of a given text.

    :type text: string
    :param text: text to be analyzed
    :rtype: dict
    :return: dictionary of language code and score of ``text``,
        which is similar to the following::

            {
                'LanguageCode': 'string',
                'Score': 1.0
            }

    :see also: `Comprehend.Client.detect_dominant_language() <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/comprehend.html#Comprehend.Client.detect_dominant_language>`_
    """
    global comprehend
    detection = comprehend.detect_dominant_language(Text=text)
    languages = sorted(detection['Languages'], key=lambda x: -x['Score'])
        # sorts languages in descending order of their Score
        # because no ordering is documented
    return languages[0]


def detect_entities(text, language_code):
    """
    Detects entities in a given text.

    :type text: string
    :param text: text to be analyzed
    :type language_code: string
    :param language_code: language code of ``text``
    :rtype: list
    :return: list of entities in ``text``, which is similar to
        the following::

            [
                {
                    'Score': 1.0,
                    'Type': 'string',
                    'Text': 'string',
                    'BeginOffset': 123,
                    'EndOffset': 123
                }, ...
            ]

    :see also: `Comprehend.Client.detect_entities() <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/comprehend.html#Comprehend.Client.detect_entities>`_
    """
    global comprehend
    detection = comprehend.detect_entities(
        Text=text, LanguageCode=language_code)
    return detection['Entities']


def detect_key_phrases(text, language_code):
    """
    Detects key phrases in a given text.

    :type text: string
    :param text: text to be analyzed
    :type language_code: string
    :param language_code: language code of ``text``
    :rtype: list
    :return: list of key phrases in ``text``,
        which is similar to the following::

            [
                {
                    'Score': 1.0,
                    'Text': 'string',
                    'BeginOffset': 123,
                    'EndOffset': 123
                }, ...
            ]

    :see also: `Comprehend.Client.detect_key_phrases() <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/comprehend.html#Comprehend.Client.detect_key_phrases>`_
    """
    global comprehend
    detection = comprehend.detect_key_phrases(
        Text=text, LanguageCode=language_code)
    return detection['KeyPhrases']


def detect_sentiment(text, language_code):
    """
    Detects sentiment of a given text.

    :type text: string
    :param text: text to be analyzed
    :type language_code: string
    :param language_code: language code of ``text``
    :rtype: dict
    :return: dictionary of the sentiment of ``text``,
        which is similar to the following::

            {
                'Sentiment': 'string',
                'SentimentScore': {
                    'Positive': 1.0f,
                    'Negative': 1.0f,
                    'Neutral': 1.0f,
                    'Mixed': 1.0f
                }
            }

    :see also: `Comprehend.Client.detect_sentiment() <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/comprehend.html#Comprehend.Client.detect_sentiment>`_
    """
    global comprehend
    return comprehend.detect_sentiment(Text=text, LanguageCode=language_code)


def detect_syntax(text, language_code):
    """
    Detects syntax in a given text.

    :type text: string
    :param text: text to be analyzed
    :type language_code: string
    :param language_code: language code of ``text``
    :rtype: list
    :return: list of syntax tokens in ``text``,
        which is similar to the following::

            [
                {
                    'TokenId': 123,
                    'Text': 'string',
                    'BeginOffset': 123,
                    'EndOffset': 123,
                    'PartOfSpeech': {
                        'Tag': 'string',
                        'Score': 1.0
                    }
                } ...
            ]

    :see also: `Comprehend.Client.detect_syntax() <https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/comprehend.html#Comprehend.Client.detect_syntax>`_
    """
    global comprehend
    detection = comprehend.detect_syntax(Text=text, LanguageCode=language_code)
    return detection['SyntaxTokens']


def analyze_record(record):
    """
    Analyzes Amazon Comprehend to a given S3 object.

    :type record: dict
    :param record: S3 object to be analyzed
    :rtype: dict
    :return: analysis results of ``record``,
        which is similar to the following::

            {
                'DominangLanguage': result of detect_dominant_language(),
                'Entities': result of detect_entities(),
                'KeyPhrases': result of detect_key_phrases(),
                'Sentiment': result of detect_sentiment(),
                'SyntaxToken': result of detect_syntax()
            }

    :see also:
        * :py:func:`detect_dominant_language()`
        * :py:func:`detect_entities()`
        * :py:func:`detect_key_phrases()`
        * :py:func:`detect_sentiment()`
        * :py:func:`detect_syntax()`
    """
    global LOGGER
    global s3
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    LOGGER.info('obtaining: s3://%s/%s', bucket, key)
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj['Body']
    text = body.read().decode(encoding='utf-8')
    try:
        LOGGER.debug('input: %s' % text)
        LOGGER.info('detecting dominant language')
        dominant_language = detect_dominant_language(text)
        LOGGER.debug(
            'Language=%s (Score=%f)',
            dominant_language['LanguageCode'],
            dominant_language['Score'])
        language_code = dominant_language['LanguageCode']
            # subsequent analyses depend on the detected language
        LOGGER.info('detecting entities')
        entities = detect_entities(text, language_code)
        for entity in entities:
            LOGGER.debug('[%s] %s', entity['Type'], entity['Text'])
        LOGGER.info('detecting key phrases')
        key_phrases = detect_key_phrases(text, language_code)
        for phrase in key_phrases:
            LOGGER.debug(
                'Key Phrase=%s (Score=%f)', phrase['Text'], phrase['Score'])
        LOGGER.info('detecting sentiment')
        sentiment = detect_sentiment(text, language_code)
        LOGGER.debug(
            'Sentiment=%s (Score=%f)',
            sentiment['Sentiment'],
            sentiment['SentimentScore'][sentiment['Sentiment'].capitalize()])
        LOGGER.info('detecting syntax')
        syntax_tokens = detect_syntax(text, language_code)
        for token in syntax_tokens:
            LOGGER.debug(
                '[%s] %s (Score=%f)',
                token['PartOfSpeech']['Tag'],
                token['Text'],
                token['PartOfSpeech']['Score'])
        return {
            'DominantLanguage': dominant_language,
            'Entities': entities,
            'KeyPhrases': key_phrases,
            'Sentiment': sentiment,
            'SyntaxTokens': syntax_tokens
        }
    finally:
        body.close()  # is this really necessary?


def save_analysis(input_bucket, input_key, analysis):
    """
    Saves a given analysis results.

    ``analysis`` is converted into a JSON object and saved in the location
    satisfying all of the following conditions,

    * Bucket is ``input_bucket`` unless the environment variable
      ``COMPREHEND_S3_OUTPUT_BUCKET`` is specified
    * Object folder is "comprehend" unless the environment variable
      ``COMPREHEND_S3_OUTPUT_FOLDER`` is specified
    * Object name is same as ``input_key`` except the extension is replaced
      with ".json"

    :type input_bucket: string
    :param input_bucket: bucket of the input object
    :type input_key: string
    :param input_key: key of the input object
    :type analysis: dict
    :param analysis: analysis results returned by :py:func:`analyze_record`
    """
    output_bucket = OUTPUT_BUCKET or input_bucket
    output_name = os.path.splitext(os.path.basename(input_key))[0]
    output_key = '%s/%s.json' % (OUTPUT_FOLDER, output_name)
    LOGGER.info('saving: s3://%s/%s', output_bucket, output_key)
    s3.put_object(
        Bucket=output_bucket,
        Key=output_key,
        Body=json.dumps(analysis, indent=2).encode(encoding='utf-8'))


def main(event):
    """
    Applies Amazon Comprehend to given S3 objects.

    :type event: dict
    :param event: should be an S3 PUT event
    :rtype: list
    :return: list of analysis results, where each element is the result of
        :py:func:`analyze_record`.
    """
    # analyzes each record
    analyses = [analyze_record(record) for record in event['Records']]
    # saves analysis results
    for (record, analysis) in zip(event['Records'], analyses):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        save_analysis(input_bucket=bucket, input_key=key, analysis=analysis)
    return analyses


def lambda_handler(event, context):
    """
    Entry function of the Lambda function.

    Wraps :py:func:`main` to catch and log any exception raised from it.

    :type event: dict
    :param event: should be an S3 PUT event
    :rtype: list
    :return: result of :py:func:`main`
    """
    global LOGGER
    try:
        LOGGER.info('request ID: %s', context.aws_request_id)
        return main(event)
    except Exception as e:
        # prints the stack trace of the exception
        LOGGER.error(e)
        traceback.print_exc()
        raise e
