# Getting Started with AWS Lambda

## Introduction

This repository is just a note for myself, but I hope some might feel this useful.

To learn [AWS Lambda](https://docs.aws.amazon.com/lambda/index.html#lang/en_us), I supposed a function that
1. Is triggered when an object is put in a specific S3 location (`my-bucket/inbox`)
2. Processes the contents of the object with [Amazon Comprehend](https://docs.aws.amazon.com/comprehend/index.html#lang/en_us)
3. Saves the results of Amazon Comprehend processing as an object in another S3 location (`my-bucket/comprehend`)

My Lambda function is written in Python 3.7.
I am primarily working on the Tokyo region (`ap-northeast-1`), so region specific resources are located in the Tokyo region unless otherwise noted.

**You need a credential with sufficient permissions to complete the following AWS manipulations.**
I set up a profile but I omitted it in the following examples.

The following examples use [AWS CLI](https://aws.amazon.com/cli/) for to configure components.
If you just started learning AWS Lambda, I recommend you first to try the AWS Lambda Console like I did.

## Creating a Lambda function

First, let's deploy a silly function.

### Creating a dedicated role

Before creating a Lambda function, create a role `comprehend-s3` dedicated to it.

```bash
aws iam create-role --role-name comprehend-s3 --description 'Executes Lambda function comprehend-s3' --assume-role-policy-document file://iam/policy/lambda-assume-role-policy.json
```

Suppose the ARN of the role is `arn:aws:iam::123456789012:role/comprehend-s3`.

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

Suppose the ARN of the function is `arn:aws:lambda:ap-northeast-1:123456789012:function:comprehend-s3`.

## Triggering the Lambda function from S3

### Creating an S3 bucket

Create an S3 bucket `my-bucket`.
Note that `my-bucket` is too general that you have to choose a more specific name.

```bash
aws s3api create-bucket --bucket my-bucket --region ap-northeast-1 --create-bucket-configuration LocationConstraint=ap-northeast-1
```

Block public access to the bucket, because it is unnecessary in this use case.

```bash
aws s3api put-public-access-block --bucket my-bucket --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### Adding a permission to the Lambda function

Before enabling the notification from the S3 bucket to the Lambda function, add an appropriate permission to the function.

```bash
aws lambda add-permission --function-name comprehend-s3 --principal s3.amazonaws.com --statement-id something_unique --action "lambda:InvokeFunction" --source-arn arn:aws:s3:::my-bucket --source-account 123456789012
```
Do not forget to replace `--statement-id something_unique` and `--source-acount 123456789012` appropriately.

### Adding a trigger to the S3 bucket

Then enable the notification that is triggered when an object is `PUT` into a path like `inbox/*.txt`.
The following is the configuration,

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

You can examine logs in the CloudWatch Logs.
Its log group name should be `/aws/lambda/comprehend-s3`.
They are retained forever, though I am going to change it to a week.

```bash
aws logs put-retention-policy --log-group-name /aws/lambda/comprehend-s3 --retention-in-days 7
```

## Obtaining the contents of a given S3 object from the Lambda function

### Allowing the Lambda function to get S3 objects from the bucket

Define a policy that can get S3 objects from `my-bucket`.

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

The ARN of the new policy should be similar to `arn:aws:iam::123456789012:policy/learn-aws-lambda/S3GetObject_my-bucket_inbox`.

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

I found that no stack trace is left in the CloudWatch Logs when the Lambda function fails.
This is very inconvenient, so I wrapped the main function with a `try-except` clause to log the stack trace of any exception.

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

### Replacing the test text

Copy the test text into the S3 bucket again.

```bash
aws s3 cp test/test.txt s3://my-bucket/inbox/test.txt
```

Check the CloudWatch Logs to see if the function is invoked.
