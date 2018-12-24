# Getting Started with AWS Lambda

## Introduction

This repository is just a note for myself, but I hope some might feel this useful.

To learn [AWS Lambda](https://docs.aws.amazon.com/lambda/index.html#lang/en_us), I supposed a function that
1. Is triggered when an object is put in a specific S3 location (`my-bucket/inbox`)
2. Processes the contents of the object with [Amazon Comprehend](https://docs.aws.amazon.com/comprehend/index.html#lang/en_us)
3. Saves the results of Amazon Comprehend processing as an object in another S3 location (`my-bucket/comprehend`)

My Lambda function was written in Python 3.7.
I am primarily working on the Tokyo region (`ap-northeast-1`), so region specific resources are located in the Tokyo region unless otherwise noted.

**You need a credential with sufficient permissions to complete the following AWS manipulations.**
I set up a profile but I omitted it in the following examples.

## Creating a Lambda function

Before creating a Lambda function, I had to create a role `comprehend-s3` for it.

```bash
aws iam create-role --role-name comprehend-s3 --description 'Executes Lambda function comprehend-s3' --assume-role-policy-document file://iam/policy/lambda-assume-role-policy.json
```

Suppose the ARN of the role is `arn:aws:iam::123456789012:role/comprehend-s3`.

The role should have at least the policy `AWSLambdaBasicExecutionRole` attached, which allows a Lambda function to write logs to [CloudWatch](https://aws.amazon.com/cloudwatch/).

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

I also had to zip the [initial code](scripts/lambda_function_1.py) of my Lambda function.

```bash
cd scripts
zip lambda_function_1.zip lambda_function_1.py
cd ..
```

`lambda_function_1.py` looks like the following,

```python
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
```

I created a Lambda function `comprehend-s3` with the following command.

```bash
aws lambda create-function --function-name comprehend-s3 --runtime python3.7 --role arn:aws:iam::123456789012:role/comprehend-s3 --handler lambda_function_1.lambda_handler --description "Comprehends S3" --zip-file fileb://scripts/lambda_function_1.zip
```

Suppose the ARN of the function is `arn:aws:lambda:ap-northeast-1:123456789012:function:comprehend-s3`.

You can do the same manipulations on the AWS Lambda console as I initially did.
