# Getting Started with AWS Lambda

English/[日本語](README_ja.md)

**Table of Contents**

<!-- TOC depthFrom:1 depthTo:6 withLinks:1 updateOnSave:1 orderedList:0 indent:ICAgIA== -->

- [Getting Started with AWS Lambda](#getting-started-with-aws-lambda)
    - [Introduction](#introduction)
    - [Creating a Lambda function](#creating-a-lambda-function)
        - [Creating a dedicated role](#creating-a-dedicated-role)
        - [Deploying initial code](#deploying-initial-code)
    - [Triggering the Lambda function from S3](#triggering-the-lambda-function-from-s3)
        - [Creating a dedicated S3 bucket](#creating-a-dedicated-s3-bucket)
        - [Adding a permission for S3 to the Lambda function](#adding-a-permission-for-s3-to-the-lambda-function)
        - [Adding a trigger to the S3 bucket](#adding-a-trigger-to-the-s3-bucket)
        - [Putting an object into the bucket](#putting-an-object-into-the-bucket)
    - [Obtaining the contents of a given S3 object from the Lambda function](#obtaining-the-contents-of-a-given-s3-object-from-the-lambda-function)
        - [Allowing the Lambda function to get S3 objects from the bucket](#allowing-the-lambda-function-to-get-s3-objects-from-the-bucket)
        - [Updating the Lambda function](#updating-the-lambda-function)
        - [Testing if the Lambda function works](#testing-if-the-lambda-function-works)
    - [Processing a text with Amazon Comprehend](#processing-a-text-with-amazon-comprehend)
        - [Allowing the Lambda function to run Amazon Comprehend](#allowing-the-lambda-function-to-run-amazon-comprehend)
        - [Updating the Lambda function](#updating-the-lambda-function)
        - [Changing logging level of the Lambda function](#changing-logging-level-of-the-lambda-function)
    - [Saving analysis results as an S3 object](#saving-analysis-results-as-an-s3-object)
        - [Allowing the Lambda function to PUT an S3 object](#allowing-the-lambda-function-to-put-an-s3-object)
        - [Updating the Lambda function](#updating-the-lambda-function)
        - [Testing if the Lambda function works](#testing-if-the-lambda-function-works)
        - [Retrieving the latest logs through CLI](#retrieving-the-latest-logs-through-cli)
    - [Generating documentation with Sphinx](#generating-documentation-with-sphinx)
    - [Describing a serverless application with AWS SAM](#describing-a-serverless-application-with-aws-sam)
        - [Describing an AWS SAM template](#describing-an-aws-sam-template)
        - [Starting a Docker service](#starting-a-docker-service)
        - [Building a serverless application with AWS SAM](#building-a-serverless-application-with-aws-sam)
            - [Specifying the region](#specifying-the-region)
        - [Packaging a serverless application with AWS SAM](#packaging-a-serverless-application-with-aws-sam)
            - [Specifying a profile](#specifying-a-profile)
        - [Deploying a serverless application with AWS SAM](#deploying-a-serverless-application-with-aws-sam)
        - [Avoiding circular dependency in an AWS SAM template](#avoiding-circular-dependency-in-an-aws-sam-template)
            - [Directly referencing an S3 bucket by ARN](#directly-referencing-an-s3-bucket-by-arn)
            - [Using `Events` property of a Lambda function](#using-events-property-of-a-lambda-function)
        - [Validating an AWS SAM template](#validating-an-aws-sam-template)

<!-- /TOC -->

## Introduction

This repository is just a note for myself, but I hope someone might feel this useful.

To learn [AWS Lambda](https://docs.aws.amazon.com/lambda/index.html#lang/en_us), I supposed a function that
1. Is triggered when an object is put in a specific S3 location (`my-bucket/inbox`)
2. Processes the contents of the object with [Amazon Comprehend](https://docs.aws.amazon.com/comprehend/index.html#lang/en_us)
3. Saves the results of Amazon Comprehend processing as an object in another S3 location (`my-bucket/comprehend`)

My Lambda function is written in Python 3.7.
I am primarily working on the Tokyo region (`ap-northeast-1`), so region specific resources are located in the Tokyo region unless otherwise noted.

**You need a credential with sufficient permissions to complete the following AWS manipulations.**
I set up a profile for me but I omitted it in the following examples.

The following examples use [AWS CLI](https://aws.amazon.com/cli/) to configure components in favor of reproducibility, though, if you just started learning AWS Lambda, I recommend you first to try the AWS Lambda Console like I did.

## Creating a Lambda function

First, let's deploy a silly function.

### Creating a dedicated role

Before creating a Lambda function, create a role `comprehend-s3` dedicated to it.

```bash
aws iam create-role --role-name comprehend-s3 --description 'Executes Lambda function comprehend-s3' --assume-role-policy-document file://iam/policy/lambda-assume-role-policy.json
```

The ARN of the role will be similar to `arn:aws:iam::123456789012:role/comprehend-s3`.

The role should have at least the predefined policy `AWSLambdaBasicExecutionRole` or equivalent attached, which allows a Lambda function to write logs to [CloudWatch](https://aws.amazon.com/cloudwatch/).

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### Deploying initial code

Zip the [initial code](scripts/lambda_function_1.py).

```bash
cd scripts
zip lambda_function_1.zip lambda_function_1.py
cd ..
```

Create a Lambda function `comprehend-s3` with the following command.

```bash
aws lambda create-function --function-name comprehend-s3 --runtime python3.7 --role arn:aws:iam::123456789012:role/comprehend-s3 --handler lambda_function_1.lambda_handler --description "Comprehends S3" --zip-file fileb://scripts/lambda_function_1.zip
```

The ARN of the function will be `arn:aws:lambda:ap-northeast-1:123456789012:function:comprehend-s3`.

## Triggering the Lambda function from S3

Let's invoke the Lambda function when an S3 object is PUT into a specific location.

### Creating a dedicated S3 bucket

Create a dedicated S3 bucket `my-bucket`.
Note that `my-bucket` is too general that you have to choose a more specific name.

```bash
aws s3api create-bucket --bucket my-bucket --region ap-northeast-1 --create-bucket-configuration LocationConstraint=ap-northeast-1
```

Block public access to the bucket, because it is unnecessary in this use case.

```bash
aws s3api put-public-access-block --bucket my-bucket --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### Adding a permission for S3 to the Lambda function

Before enabling the notification from the S3 bucket to the Lambda function, add an appropriate permission to the function.

```bash
aws lambda add-permission --function-name comprehend-s3 --principal s3.amazonaws.com --statement-id something_unique --action "lambda:InvokeFunction" --source-arn arn:aws:s3:::my-bucket --source-account 123456789012
```

Do not forget to replace `--statement-id something_unique` and `--source-acount 123456789012` appropriately.

### Adding a trigger to the S3 bucket

Enable the notification that is triggered when an object is `PUT` into a path like `inbox/*.txt`.
The following is the [configuration](s3/notificiation-config.json),

```json
{
  "LambdaFunctionConfigurations": [
    {
      "Id": "TextPutIntoMyBucket",
      "LambdaFunctionArn": "arn:aws:lambda:ap-northeast-1:123456789012:function:comprehend-s3",
      "Events": [
        "s3:ObjectCreated:Put"
      ],
      "Filter": {
        "Key": {
          "FilterRules": [
            {
              "Name": "Prefix",
              "Value": "inbox/"
            },
            {
              "Name": "Suffix",
              "Value": ".txt"
            }
          ]
        }
      }
    }
  ]
}
```

**Note that you have to replace `LambdaFunctionArn` with the ARN of your Lambda function.**

```bash
aws s3api put-bucket-notification-configuration --bucket my-bucket --notification-configuration file://s3/notification-config.json
```

### Putting an object into the bucket

Test if the Lambda function is invoked when an object is put into the bucket.

```bash
aws s3 cp test/test.txt s3://my-bucket/inbox/test.txt
```

You can examine logs in CloudWatch Logs.
Its log group name should be `/aws/lambda/comprehend-s3`.
They are retained forever by default, so I changed its retention period to a week to save storage.

```bash
aws logs put-retention-policy --log-group-name /aws/lambda/comprehend-s3 --retention-in-days 7
```

## Obtaining the contents of a given S3 object from the Lambda function

Let's add a contents retrieval feature to the Lambda function.

### Allowing the Lambda function to get S3 objects from the bucket

Define a policy that allows retrieval of S3 objects from `my-bucket`.

```bash
aws iam create-policy --path /learn-aws-lambda/ --policy-name S3GetObject_my-bucket_inbox --policy-document file://iam/policy/S3GetObject_my-bucket_inbox.json --description "Allows getting an object from s3://my-bucket/inbox"
```

The following is the [policy document](iam/policy/S3GetObject_my-bucket_inbox.json),

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": [
        "arn:aws:s3:::my-bucket/inbox/*"
      ]
    }
  ]
}
```

The ARN of the new policy will be similar to `arn:aws:iam::123456789012:policy/learn-aws-lambda/S3GetObject_my-bucket_inbox`.

Attach the policy to the role `comprehend-s3`.

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::123456789012:policy/learn-aws-lambda/S3GetObject_my-bucket_inbox
```

### Updating the Lambda function

We are going to update the Lambda function with another code [`lambda_function_2.py`](scripts/lambda_function_2.py).
Before updating the function, zip the code.

```bash
cd scripts
zip lambda_function_2.zip lambda_function_2.py
cd ..
```

Then update the function with the new zip file.

```bash
aws lambda update-function-code --function-name comprehend-s3 --zip-file fileb://scripts/lambda_function_2.zip
```

The handler function also has to be changed.

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --handler lambda_function_2.lambda_handler
```

By the way, I found that no stack trace is left in CloudWatch Logs when the Lambda function fails.
This was very inconvenient, so I wrapped the main function with a `try-except` clause to log the stack trace of any exception raised from it.

```python
def lambda_handler(event, context):
    global LOGGER
    try:
        return main(event, context)
    except Exception as e:
        # prints the stack trace of the exception
        traceback.print_exc()
        LOGGER.error(e)
        raise e
```

### Testing if the Lambda function works

Copy the test text into the S3 bucket again.

```bash
aws s3 cp test/test.txt s3://my-bucket/inbox/test.txt
```

Check CloudWatch Logs to see if the function is invoked.

## Processing a text with Amazon Comprehend

Let's add a Amazon Comprehend analysis feature to the Lambda function.

### Allowing the Lambda function to run Amazon Comprehend

Create a policy that allows detection with Amazon Comprehend ([policy document](iam/policy/ComprehendDetectAny.json)).

```bash
aws iam create-policy --policy-name ComprehendDetectAny --path /learn-aws-lambda/ --policy-document file://iam/policy/ComprehendDetectAny.json --description "Allows detection with Amazon Comprehend"
```

The ARN of the policy will be similar to `arn:aws:iam::123456789012:policy/learn-aws-lambda/ComprehendDetectAny`.

Then attach the policy to the role `comprehend-s3`.

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::123456789012:policy/learn-aws-lambda/ComprehendDetectAny
```

### Updating the Lambda function

Zip the new code [lambda_function_3.py](scripts/lambda_function_3.py).

```bash
cd scripts
zip lambda_function_3.zip lambda_function_3.py
cd ..
```

Update the code of the Lambda function.

```bash
aws lambda update-function-code --function-name comprehend-s3 --zip-file fileb://scripts/lambda_function_3.zip
```

Do not forget to replace the handler function with `lambda_function_3.lambda_handler`.

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --handler lambda_function_3.lambda_handler
```

My Lambda function is running in the Tokyo region and any [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) client is associated with that region by default, but unfortunately the Tokyo region does not host Amazon Comprehend as of January 4, 2019.
So I configured my Amazon Comprehend client with the Ohio region; i.e., `us-east-2`.
Anyway, the region does not matter as long as it supports Amazon Comprehend.

```python
COMPREHEND_REGION = 'us-east-2'
    # specifies the region where Amazon Comprehend is hosted
    # because not all regions provide Amazon Comprehend
```
```python
comprehend = boto3.client('comprehend', region_name=COMPREHEND_REGION)
```

Well, update the S3 object and check CloudWatch Logs to see if the Lambda function works.
I refrain from repeating the trivial command.

### Changing logging level of the Lambda function

The [third script](scripts/lambda_function_3.py) interprets the environment variable `COMPREHEND_S3_LOGGING_LEVEL` as the logging level of the function, which is `DEBUG` by default.
You can control the logging level of the Lambda function by configuring the environment variable `COMPREHEND_S3_LOGGING_LEVEL`.
For instance, you can change it to `INFO` with the following command,

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --environment 'Variables={COMPREHEND_S3_LOGGING_LEVEL=INFO}'
```

If you want to delete environment variables from the Lambda function, run the following command,

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --environment 'Variables={}'
```

## Saving analysis results as an S3 object

Let's add a results saving feature to the Lambda function.

### Allowing the Lambda function to PUT an S3 object

Create a policy that allows putting an S3 object.

```bash
aws iam create-policy --path /learn-aws-lambda/ --policy-name S3PutObject_my-bucket_comprehend --policy-document file://iam/policy/S3PutObject_my-bucket_comprehend.json --description "Allows putting an S3 object into s3://my-bucket/comprehend"
```

The ARN of the policy will be similar to `arn:aws:iam::123456789012:policy/learn-aws-lambda/S3PutObject_my-bucket_comprehend`.

Attach the policy to the role `comprehend-s3`.

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::123456789012:policy/learn-aws-lambda/S3PutObject_my-bucket_comprehend
```

### Updating the Lambda function

Zip the new code [lambda_function_4.py](scripts/lambda_function_4.py).

```bash
cd scripts
zip lambda_function_4.zip lambda_function_4.py
cd ..
```

Update the code of the Lambda function.

```bash
aws lambda update-function-code --function-name comprehend-s3 --zip-file fileb://scripts/lambda_function_4.zip
```

Do not forget to replace the handler with `lambda_function_4.lambda_handler`.

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --handler lambda_function_4.lambda_handler
```

### Testing if the Lambda function works

Well, update the S3 object and check CloudWatch Logs to see if the Lambda function is invoked.

You will find a JSON file at `s3://my-bucket/comprehend/test.json`.
Test if it matches the [reference](test/test-ref.json).

```bash
aws s3 cp s3://my-bucket/comprehend/test.json test/test.json
diff test/test.json test/test-ref.json
```

### Retrieving the latest logs through CLI

Let's check the latest logs through CLI.
The following are brief steps to get logs,

1. Obtain the latest log stream with `aws logs describe-log-streams`.
2. Obtain the last n lines of the log stream identified at the step 1 with `aws logs get-log-events`.

Here is a one-liner for bash,

```bash
aws logs get-log-events --log-group-name /aws/lambda/comprehend-s3 --log-stream-name `aws --query 'logStreams[0].logStreamName' logs describe-log-streams --log-group-name /aws/lambda/comprehend-s3 --descending --order-by LastEventTime --max-items 1 | tr -d '"'` --limit 12 --no-start-from-head --query 'events[].message'
```

You will get results similar to the following by running the command shown above,

```
[
    "START RequestId: a7f14ae4-10a4-11e9-ab9d-478d60f1dab7 Version: $LATEST\n",
    "[INFO]\t2019-01-05T04:45:58.535Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\trequest ID: a7f14ae4-10a4-11e9-ab9d-478d60f1dab7\n",
    "\n[INFO]\t2019-01-05T04:45:58.535Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tobtaining: s3://my-bucket/inbox/test.txt\n",
    "\n[INFO]\t2019-01-05T04:45:58.557Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tdetecting dominant language\n",
    "\n[INFO]\t2019-01-05T04:45:58.743Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tdetecting entities\n",
    "\n[INFO]\t2019-01-05T04:45:58.984Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tdetecting key phrases\n",
    "\n[INFO]\t2019-01-05T04:45:59.200Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tdetecting sentiment\n",
    "\n[INFO]\t2019-01-05T04:45:59.405Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tdetecting syntax\n",
    "\n[INFO]\t2019-01-05T04:45:59.598Z\ta7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tsaving: s3://my-bucket/comprehend/test.json\n",
    "END RequestId: a7f14ae4-10a4-11e9-ab9d-478d60f1dab7\n",
    "REPORT RequestId: a7f14ae4-10a4-11e9-ab9d-478d60f1dab7\tDuration: 1162.23 ms\tBilled Duration: 1200 ms \tMemory Size: 128 MB\tMax Memory Used: 34 MB\t\n",
    "\n"
]
```

## Generating documentation with Sphinx

**This section has really nothing to do with AWS.**

You may have noticed that functions in the [fourth script](scripts/lambda_function_4.py) have [docstrings](https://www.python.org/dev/peps/pep-0257/).
You can generate documentation with [Sphinx](http://www.sphinx-doc.org/en/master/) by running `make` in the [`docs` directory](docs).

Take the following steps,

1. Install Sphinx.

    ```bash
    pip install -U Sphinx
    ```

2. Move down to the `docs` directory.

    ```bash
    cd docs
    ```

3. Run the `make` script.

    ```bash
    make html
    ```

4. You will find the `html` directory in the `build` directory.

## Describing a serverless application with AWS SAM

By using [AWS Serverless Application Model (AWS SAM)](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html) which is an extension of [AWS CloudFormation](https://aws.amazon.com/cloudformation/), we can integrate resource allocation and configuration steps described above in a single AWS SAM template file.
If you are new to AWS SAM, I recommend you to take [this tutorial](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-quick-start.html).

Basic steps are,
1. [Describe](#describing-an-aws-sam-template)
2. [Build](#building-a-serverless-application-with-aws-sam)
3. [Package](#packaging-a-serverless-application-with-aws-sam)
4. [Deploy](#deploying-a-serverless-application-with-aws-sam)

### Describing an AWS SAM template

The AWS SAM template and source code of our serverless application are in the directory `sam`.

- `sam`
    - [`template.yaml`](sam/template.yaml): AWS SAM template
    - `src`
        - [`lambda_function_4.py`](sam/src/lambda_function_4.py): Lambda handler (identical to the last example)
        - [`requirements.txt`](sam/src/requirements.txt): dependencies

[`sam/template.yaml`](sam/template.yaml) is the AWS SAM template describing our serverless application.
[`sam/src/requirements.txt`](sam/src/requirements.txt) is an empty text because our serverless application has no dependencies.

The following sections suppose you are in the `sam` directory.
So move down to it.

```bash
cd sam
```

### Starting a Docker service

Before working with AWS SAM, do not forget to boot a Docker service.
Otherwise you will get an error similar to the following when you run `sam build --use-container` command.

```
2019-01-06 22:14:12 Starting Build inside a container
2019-01-06 22:14:12 Found credentials in shared credentials file: ~/.aws/credentials
2019-01-06 22:14:12 Building resource 'HelloWorldFunction'
Traceback (most recent call last):
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/connectionpool.py", line 600, in urlopen
    chunked=chunked)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/connectionpool.py", line 354, in _make_request
    conn.request(method, url, **httplib_request_kw)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1229, in request
    self._send_request(method, url, body, headers, encode_chunked)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1275, in _send_request
    self.endheaders(body, encode_chunked=encode_chunked)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1224, in endheaders
    self._send_output(message_body, encode_chunked=encode_chunked)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1016, in _send_output
    self.send(msg)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 956, in send
    self.connect()
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/transport/unixconn.py", line 42, in connect
    sock.connect(self.unix_socket)
FileNotFoundError: [Errno 2] No such file or directory

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/requests/adapters.py", line 449, in send
    timeout=timeout
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/connectionpool.py", line 638, in urlopen
    _stacktrace=sys.exc_info()[2])
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/util/retry.py", line 367, in increment
    raise six.reraise(type(error), error, _stacktrace)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/packages/six.py", line 685, in reraise
    raise value.with_traceback(tb)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/connectionpool.py", line 600, in urlopen
    chunked=chunked)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/urllib3/connectionpool.py", line 354, in _make_request
    conn.request(method, url, **httplib_request_kw)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1229, in request
    self._send_request(method, url, body, headers, encode_chunked)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1275, in _send_request
    self.endheaders(body, encode_chunked=encode_chunked)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1224, in endheaders
    self._send_output(message_body, encode_chunked=encode_chunked)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 1016, in _send_output
    self.send(msg)
  File "/Library/Frameworks/Python.framework/Versions/3.7/lib/python3.7/http/client.py", line 956, in send
    self.connect()
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/transport/unixconn.py", line 42, in connect
    sock.connect(self.unix_socket)
urllib3.exceptions.ProtocolError: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/kikuo/Library/Python/3.7/bin/sam", line 11, in <module>
    sys.exit(cli())
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 722, in __call__
    return self.main(*args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 697, in main
    rv = self.invoke(ctx)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 1066, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 895, in invoke
    return ctx.invoke(self.callback, **ctx.params)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 535, in invoke
    return callback(*args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/decorators.py", line 64, in new_func
    return ctx.invoke(f, obj, *args[1:], **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 535, in invoke
    return callback(*args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/commands/build/command.py", line 94, in cli
    skip_pull_image, parameter_overrides)  # pragma: no cover
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/commands/build/command.py", line 132, in do_cli
    artifacts = builder.build()
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/lib/build/app_builder.py", line 129, in build
    lambda_function.runtime)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/lib/build/app_builder.py", line 201, in _build_function
    runtime)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/lib/build/app_builder.py", line 249, in _build_function_on_container
    self._container_manager.run(container)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/local/docker/manager.py", line 75, in run
    is_image_local = self.has_image(image_name)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/local/docker/manager.py", line 153, in has_image
    self.docker_client.images.get(image_name)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/models/images.py", line 312, in get
    return self.prepare_model(self.client.api.inspect_image(name))
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/utils/decorators.py", line 19, in wrapped
    return f(self, resource_id, *args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/api/image.py", line 245, in inspect_image
    self._get(self._url("/images/{0}/json", image)), True
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/utils/decorators.py", line 46, in inner
    return f(self, *args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/docker/api/client.py", line 215, in _get
    return self.get(url, **self._set_request_timeout(kwargs))
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/requests/sessions.py", line 546, in get
    return self.request('GET', url, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/requests/sessions.py", line 533, in request
    resp = self.send(prep, **send_kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/requests/sessions.py", line 646, in send
    r = adapter.send(request, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/requests/adapters.py", line 498, in send
    raise ConnectionError(err, request=request)
requests.exceptions.ConnectionError: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
```

The error message was not very intuitive but actually meant no Docker service was running.
In my case, I just installed [Docker Desktop](https://www.docker.com/products/docker-desktop) to resolve it.

### Building a serverless application with AWS SAM

Run the [`sam build`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html) command.

```bash
sam build --use-container
```

In this example, the command may not matter.
Because this example has no dependencies.

#### Specifying the region

When I ran the `sam build` command, it complained that no region was specified.
If I supplied the `--region` option, it was resolved.

```bash
sam build --region ap-northeast-1 --use-container
```

### Packaging a serverless application with AWS SAM

Run the [`sam package`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-package.html) command.

```bash
sam package --template-file template.yaml --output-template-file packaged.yaml --s3-bucket artifacts-bucket
```

**NOTE:** You have to replace `artifacts-bucket` with the bucket where you want to store artifacts.

#### Specifying a profile

Because the `sam package` command needs to access an S3 bucket, you have to provide a credential with sufficient privileges.
If you want to use a credential other than default, you can specify the `--profile` option even though `sam package --help` does not show it.

```bash
sam package --profile your-profile --template-file template.yaml --output-template-file packaged.yaml --s3-bucket artifacts-bucket
```

### Deploying a serverless application with AWS SAM

Run the [`sam deploy`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html) command.

```
sam deploy --template-file packaged.yaml --stack-name comprehend-s3 --capabilities CAPABILITY_IAM
```

Now, you will find a new stack named `comprehend-s3` on the CloudFormation console.

### Avoiding circular dependency in an AWS SAM template

Because the Lambda function needs privileges to access the S3 bucket and at the same time the S3 bucket needs a privilege to notify the Lambda function, they have the following circular dependency.

Lambda Function &rightarrow; S3 Bucket &rightarrow; Lambda Function &rightarrow; ...

If you have circular dependency in your AWS SAM template, the `sam deploy` command fails with an error similar to the following,

```
Failed to create the changeset: Waiter ChangeSetCreateComplete failed: Waiter encountered a terminal failure state Status: FAILED. Reason: Circular dependency between resources: [ComprehendS3FunctionTextUploadPermission, ComprehendS3FunctionRole, ComprehendS3Function, ComprehendS3Bucket]
```

[This article](https://aws.amazon.com/premiumsupport/knowledge-center/unable-validate-circular-dependency-cloudformation/) explains how to avoid circular dependencies.
I needed some trial and error to adapt it to our serverless application.

#### Directly referencing an S3 bucket by ARN

To break circular dependency in an AWS SAM template, [the article introduced above](https://aws.amazon.com/premiumsupport/knowledge-center/unable-validate-circular-dependency-cloudformation/) suggests referencing an S3 bucket with its absolute ARN instead of its logical ID.
This means you need to know the name of the S3 bucket in advance.
Because CloudFormation generates a unique name for an S3 bucket by default, you have to override this behavior by giving a predictable name to the S3 bucket.

```yaml
Parameters:
  ComprehendS3BucketName:
    Description: 'Name of the S3 bucket where input texts and output results are saved'
    Type: String
    Default: 'learn-aws-lambda-comprehend-s3-bucket'

Resources:
  ComprehendS3Function:
    Type: 'AWS::Serverless::Function'
    Properties:
      ...
      Policies:
        ...
        # policy to get S3 objects in the inbox folder
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - 's3:GetObject'
              Resource: !Sub 'arn:aws:s3:::${ComprehendS3BucketName}/inbox/*'
                # instead of '${ComprehendS3Bucket.Arn}/inbox/*'
                # to avoid circular dependency
        # policy to put S3 objects in the comprehend folder
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - 's3:PutObject'
              Resource: !Sub 'arn:aws:s3:::${ComprehendS3BucketName}/comprehend/*'
                # instead of '${ComprehendS3Bucket.Arn}/comprehend/*'
                # to avoid circular dependency
    ...

  ComprehendS3Bucket:
    Type: 'AWS::S3::Bucket'
    Properties:
      BucketName: !Ref ComprehendS3BucketName
        # overrides automatic name assignment
```

#### Using `Events` property of a Lambda function

At first I was trying to directly add the `NotificationConfiguration` property to the S3 bucket.
And I noticed that just adding `NotificationConfiguration` to the S3 bucket was not sufficient, but an `AWS::Lambda::Permission` resource also had to be defined.
I felt it somewhat cumbersome.

But there is a better way to address it.
An `AWS::Serveless::Function` resource can have an `Events` property and you can describe events to be triggered there.

```yaml
ComprehendS3Function:
  Type: 'AWS::Serverless::Function'
  Properties:
    ...
    Events:
      TextUpload:
        Type: S3
        Properties:
          Bucket: !Ref ComprehendS3Bucket
          Events: 's3:ObjectCreated:Put'
          Filter:
            S3Key:
              Rules:
                - Name: prefix
                  Value: 'inbox/'
                - Name: suffix
                  Value: '.txt'
```

If you configure the `Events` property of the Lambda function, you do not need to specify the `NotificationConfiguration` property to the S3 bucket.

**NOTE:** The `Bucket` property of an event only accepts a logical ID of an S3 bucket.
At first I specified an ARN of the S3 bucket to the `Bucket` property and I got an error.

### Validating an AWS SAM template

**NOTE:** This is not essential part of this document.

There is the [`sam validate`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-validate.html) command.

```bash
sam validate --template template.yaml
```

When I ran `sam validate`, I got the following wierd error,

```
Traceback (most recent call last):
  File "/Users/kikuo/Library/Python/3.7/bin/sam", line 11, in <module>
    sys.exit(cli())
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 722, in __call__
    return self.main(*args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 697, in main
    rv = self.invoke(ctx)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 1066, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 895, in invoke
    return ctx.invoke(self.callback, **ctx.params)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 535, in invoke
    return callback(*args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/decorators.py", line 64, in new_func
    return ctx.invoke(f, obj, *args[1:], **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/click/core.py", line 535, in invoke
    return callback(*args, **kwargs)
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/commands/validate/validate.py", line 30, in cli
    do_cli(ctx, template)  # pragma: no cover
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/commands/validate/validate.py", line 44, in do_cli
    validator.is_valid()
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samcli/commands/validate/lib/sam_template_validator.py", line 83, in is_valid
    parameter_values={})
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samtranslator/translator/translator.py", line 60, in translate
    deployment_preference_collection = DeploymentPreferenceCollection()
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samtranslator/model/preferences/deployment_preference_collection.py", line 30, in __init__
    self.codedeploy_iam_role = self._codedeploy_iam_role()
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samtranslator/model/preferences/deployment_preference_collection.py", line 89, in _codedeploy_iam_role
    ArnGenerator.generate_aws_managed_policy_arn('service-role/AWSCodeDeployRoleForLambda')
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samtranslator/translator/arn_generator.py", line 28, in generate_aws_managed_policy_arn
    return 'arn:{}:iam::aws:policy/{}'.format(ArnGenerator.get_partition_name(),
  File "/Users/kikuo/Library/Python/3.7/lib/python/site-packages/samtranslator/translator/arn_generator.py", line 49, in get_partition_name
    region_string = region.lower()
AttributeError: 'NoneType' object has no attribute 'lower'
```

As it is suggested [here](https://github.com/awslabs/aws-sam-cli/issues/442#issuecomment-417489857), it was resolved if I specified the region to the `AWS_DEFAULT_REGION` environment variable.

```bash
export AWS_DEFAULT_REGION=ap-northeast-1
```
