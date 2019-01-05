# AWS Lambdaを始めよう

[English](README.md)/日本語

## 導入

このリポジトリは自分用のメモですが、誰かが役に立つと感じてくださると幸いです。

[AWS Lambda](https://docs.aws.amazon.com/lambda/index.html#lang/en_us)の勉強のために、今回考えた関数は以下のような感じです。
1. S3の特定の場所(`my-bucket/inbox`)にオブジェクトが書き込まれた際にトリガーされる
2. そのオブジェクトのコンテンツを[Amazon Comprehend](https://docs.aws.amazon.com/comprehend/index.html#lang/en_us)で処理する
3. Amazon Comprehendの処理結果をS3の別の場所(`my-bucket/comprehend`)に保存する

Lambda関数はPython 3.7で書きました.
私は主に東京リージョン(`ap-northeast-1`)で作業しているので、リージョン指定のあるリソースは特に断りがない限り東京リージョンに置いてます。

**このREADMEのAWS操作を遂行するためには、十分なパーミッションをもったクリデンシャルが必要です。**
私は自分用のプロファイルを作成しましたが、掲載した例からは省略しています。

以下の例は再現性のために[AWS CLI](https://aws.amazon.com/cli/)を使っていますが、もしAWS Lambdaを始めたばかりなら、AWS Lambda Consoleがオススメです。
私も最初はそうしました。

## Lambda関数を作る

最初にしょうもない関数をデプロイしましょう。

### 専用のロールを作る

Lambda関数を作る前に、専用のロール`comprehend-s3`を作ります。

```bash
aws iam create-role --role-name comprehend-s3 --description 'Executes Lambda function comprehend-s3' --assume-role-policy-document file://iam/policy/lambda-assume-role-policy.json
```

作成したロールのARNは`arn:aws:iam::123456789012:role/comprehend-s3`みたいになります。

このロールには少なくともLambda関数が[CloudWatch](https://aws.amazon.com/cloudwatch/)にログを書き込むことを許可するポリシー(AWS定義済みの`AWSLambdaBasicExecutionRole`かそれ相当のポリシー)を割り当てなければいけません。

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

### 最初のコードをデプロイする

[最初のコード`lambda_function_1.py`](scripts/lambda_function_1.py)をzip圧縮します。

```bash
cd scripts
zip lambda_function_1.zip lambda_function_1.py
cd ..
```

以下のコマンドでLambda関数`comprehend-s3`を作ります。

```bash
aws lambda create-function --function-name comprehend-s3 --runtime python3.7 --role arn:aws:iam::123456789012:role/comprehend-s3 --handler lambda_function_1.lambda_handler --description "Comprehends S3" --zip-file fileb://scripts/lambda_function_1.zip
```

作成した関数のARNは`arn:aws:lambda:ap-northeast-1:123456789012:function:comprehend-s3`みたいになります。

## S3からLambda関数をトリガーする

S3の特定の場所にオブジェクトがPUTされたときにLambda関数を呼び出してみましょう。

### 専用のS3バケットを作る

専用のS3バケット`my-bucket`を作ります。
ただし、`my-bucket`は確実に他と被るので何かもっと限定的な名前をつけなければいけません。

```bash
aws s3api create-bucket --bucket my-bucket --region ap-northeast-1 --create-bucket-configuration LocationConstraint=ap-northeast-1
```

S3バケットへのパブリックアクセスはこのケースでは必要ないので、ブロックします。

```bash
aws s3api put-public-access-block --bucket my-bucket --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

### Lambda関数にS3用パーミッションを追加する

S3バケットからLambda関数への通知を有効にする前に、必要なパーミッションをLambda関数に追加します。

```bash
aws lambda add-permission --function-name comprehend-s3 --principal s3.amazonaws.com --statement-id something_unique --action "lambda:InvokeFunction" --source-arn arn:aws:s3:::my-bucket --source-account 123456789012
```

`--statement-id something_unique`と`--source-acount 123456789012`を適切に置き換えるのをお忘れなく。

### S3バケットにトリガーを追加する

`inbox/*.txt`のようなパスにオブジェクトがPUTされた時にトリガーされる通知を有効にします。
以下がその[設定](s3/notification-config.json)です。

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

**`LambdaFunctionArn`のARNはLambda関数の設定に合うように置き換えてください。**

```bash
aws s3api put-bucket-notification-configuration --bucket my-bucket --notification-configuration file://s3/notification-config.json
```

### バケットにオブジェクトをPUTします

オブジェクトがバケットにPUTされた際にLambda関数が呼び出されることをテストします。

```bash
aws s3 cp test/test.txt s3://my-bucket/inbox/test.txt
```

CloudWatch Logsでログを確認できます。
ロググループの名前は`/aws/lambda/comprehend-s3`のはずです。
ログはデフォルトで永久に保存されますが、ストレージ節約のため私は1週間に設定しました。

```bash
aws logs put-retention-policy --log-group-name /aws/lambda/comprehend-s3 --retention-in-days 7
```

## Lambda関数からS3オブジェクトのコンテンツを取得する

Lambda関数にコンテンツ取得機能を追加しましょう。

### Lambda関数がS3オブジェクトを取得するのを許可する

S3オブジェクトを`my-bucket`を取得するのを許可するポリシーを定義します。

```bash
aws iam create-policy --path /learn-aws-lambda/ --policy-name S3GetObject_my-bucket_inbox --policy-document file://iam/policy/S3GetObject_my-bucket_inbox.json --description "Allows getting an object from s3://my-bucket/inbox"
```

[ポリシードキュメント](iam/policy/S3GetObject_my-bucket_inbox.json)は以下のとおりです。

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

作成したポリシーのARNは`arn:aws:iam::123456789012:policy/learn-aws-lambda/S3GetObject_my-bucket_inbox`みたいになります。

ポリシーをロール`comprehend-s3`に割り当てます.

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::123456789012:policy/learn-aws-lambda/S3GetObject_my-bucket_inbox
```

### Lambda関数を更新する

Lambda関数を新しいコード[`lambda_function_2.py`](scripts/lambda_function_2.py)で更新しましょう。
関数を更新する前に、コードをzip圧縮します。

```bash
cd scripts
zip lambda_function_2.zip lambda_function_2.py
cd ..
```

では、Lambda関数を作成したzipファイルで更新します。

```bash
aws lambda update-function-code --function-name comprehend-s3 --zip-file fileb://scripts/lambda_function_2.zip
```

ハンドラ関数も変更する必要があります。

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --handler lambda_function_2.lambda_handler
```

ところで、Lambda関数が失敗した際にCloudWatch Logsに何のスタックトレースも残らないことに気づきました。
これでは非常に不便なので、メイン関数を`try-except`節で囲んで、発生する例外のスタックトレースをログに出力するようにしました。

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

### Lambda関数をテストする

S3バケットに再びテスト用のテキストをコピーします。

```bash
aws s3 cp test/test.txt s3://my-bucket/inbox/test.txt
```

Lambda関数が呼び出されたことをCloudWatch Logsで確認します。

## Amazon Comprehendでテキストを処理する

Amazon Comprehendによる解析機能をLambda関数に追加しましょう。

### Lambda関数がAmazon Comprehendを実行するのを許可する

Amazon Comprehendによる検出を許可するポリシーを作成します。

```bash
aws iam create-policy --policy-name ComprehendDetectAny --path /learn-aws-lambda/ --policy-document file://iam/policy/ComprehendDetectAny.json --description "Allows detection with Amazon Comprehend"
```

作成したポリシーのARNは`arn:aws:iam::123456789012:policy/learn-aws-lambda/ComprehendDetectAny`みたいになります。

では、ポリシーをロール`comprehend-s3`に割り当てます。

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::123456789012:policy/learn-aws-lambda/ComprehendDetectAny
```

### Lambda関数を更新する

新しいコード[lambda_function_3.py](scripts/lambda_function_3.py)をzip圧縮します。

```bash
cd scripts
zip lambda_function_3.zip lambda_function_3.py
cd ..
```

Lambda関数のコードを更新します。

```bash
aws lambda update-function-code --function-name comprehend-s3 --zip-file fileb://scripts/lambda_function_3.zip
```

ハンドラー関数を`lambda_function_3.lambda_handler`に置き換えるのもお忘れなく。

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --handler lambda_function_3.lambda_handler
```

私のLambda関数は東京リージョンで動いており[boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)クライアントはデフォルトでそのリージョンに関連づけられるのですが、残念ながら東京リージョンではAmazon Comprehendは提供されていません(2019年1月4日現在)。
ということで、Amazon Comprehendのクライアントにはオハイオリージョン(`us-east-2`)を指定しました。
とりあえず、リージョンはAmazon Comprehendがサポートされていればどこでも構いません。

```python
COMPREHEND_REGION = 'us-east-2'
    # specifies the region where Amazon Comprehend is hosted
    # because not all regions provide Amazon Comprehend
```
```python
comprehend = boto3.client('comprehend', region_name=COMPREHEND_REGION)
```

では、S3オブジェクトを更新し、CloudWatch LogsでLambda関数が動いていることを確認しておいてください。
しょうもないコマンドは繰り返さないでおきます。

### Lambda関数のログレベルを変更する

[3番目のスクリプト](scripts/lambda_function_3.py)は環境変数`COMPREHEND_S3_LOGGING_LEVEL`をLambda関数のログレベル(デフォルトでDEBUG)として解釈します。
環境変数`COMPREHEND_S3_LOGGING_LEVEL`を変更するとLambda関数のログレベルをコントロールできます。
例えば、下記のコマンドでログレベルを`INFO`に変更できます。

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --environment 'Variables={COMPREHEND_S3_LOGGING_LEVEL=INFO}'
```

Lambda関数の環境変数を削除したい場合は、以下のコマンドを実行します。

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --environment 'Variables={}'
```

## 解析結果をS3オブジェクトとして保存する

Lambda関数に解析結果を保存する機能を追加しましょう。

### Lambda関数がS3オブジェクトをPUTするのを許可します

S3オブジェクトをPUTするのを許可するポリシーを作成します。

```bash
aws iam create-policy --path /learn-aws-lambda/ --policy-name S3PutObject_my-bucket_comprehend --policy-document file://iam/policy/S3PutObject_my-bucket_comprehend.json --description "Allows putting an S3 object into s3://my-bucket/comprehend"
```

作成したポリシーのARNは`arn:aws:iam::123456789012:policy/learn-aws-lambda/S3PutObject_my-bucket_comprehend`みたいになります。

ポリシーをロール`comprehend-s3`に割り当てます。

```bash
aws iam attach-role-policy --role-name comprehend-s3 --policy-arn arn:aws:iam::123456789012:policy/learn-aws-lambda/S3PutObject_my-bucket_comprehend
```

### Lambda関数を更新する

新しいコード[lambda_function_4.py](scripts/lambda_function_4.py)をzip圧縮します。

```bash
cd scripts
zip lambda_function_4.zip lambda_function_4.py
cd ..
```

Lambda関数のコードを更新します。

```bash
aws lambda update-function-code --function-name comprehend-s3 --zip-file fileb://scripts/lambda_function_4.zip
```

ハンドラ関数を`lambda_function_4.lambda_handler`で置き換えるのもお忘れなく。

```bash
aws lambda update-function-configuration --function-name comprehend-s3 --handler lambda_function_4.lambda_handler
```

### Lambda関数をテストする

S3オブジェクトを更新し、CloudWatch LogsでLambda関数が呼び出されたことを確認しておいてください。

JSONファイルは`s3://my-bucket/comprehend/test.json`に保存されます。
保存されたJSONファイルが[リファレンス](test/test-ref.json)と一致することをテストします。

```bash
aws s3 cp s3://my-bucket/comprehend/test.json test/test.json
diff test/test.json test/test-ref.json
```

### 最新のログをCLIを通じて取得する

最新のログをCLIを通じて確認しましょう。
ログ取得のステップはだいたい下記の通りです。

1. 最新のログストリームを`aws logs describe-log-streams`コマンドで取得する。
2. ステップ1で特定したログストリームの最新のn行を`aws logs get-log-events`コマンドで取得する。

bashで1行でやろうとしたらこんな感じです。

```bash
aws logs get-log-events --log-group-name /aws/lambda/comprehend-s3 --log-stream-name `aws --query 'logStreams[0].logStreamName' logs describe-log-streams --log-group-name /aws/lambda/comprehend-s3 --descending --order-by LastEventTime --max-items 1 | tr -d '"'` --limit 12 --no-start-from-head --query 'events[].message'
```

上記のコマンドを実行すると次のような結果が出力されます。

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

## Sphinxでドキュメントを生成する

**このセクションはAWSとは全くもって関係ありません。**

[4番目のスクリプト](scripts/lambda_function_4.py)には[`docstring`](https://www.python.org/dev/peps/pep-0257/)が含まれているのに気づいたかもしれません。
[`docs`ディレクトリ](docs)で`make`を実行すると[Sphinx](http://www.sphinx-doc.org/en/master/)によるドキュメント生成ができます。

次のステップに従います。

1. Sphinxをインストールします。

    ```bash
    pip install -U Sphinx
    ```

2. `docs`ディレクトリに移動します。

    ```bash
    cd docs
    ```

3. `make`スクリプトを実行します。

    ```bash
    make html
    ```

4. `build`ディレクトリ内に`html`ディレクトリが作成されます。
