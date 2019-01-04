from __future__ import print_function
import boto3
import logging
import traceback


LOGGER = logging.getLogger()
LOGGER.setLevel(logging.DEBUG)

COMPREHEND_REGION = 'us-east-2'
    # specifies the region where Amazon Comprehend is hosted
    # because not all regions provide Amazon Comprehend

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


def main(event):
    """
    Applies Amazon Comprehend to given S3 objects.

    :type event: dict
    :param event: should be an S3 PUT event
    :rtype: list
    :return: list of analysis results, where each element is the result of
        :py:func:`analyze_record`.
    """
    return [analyze_record(record) for record in event['Records']]


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
