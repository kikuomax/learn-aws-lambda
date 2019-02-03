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

## サーバレスアプリケーションをAWS SAMで記述する

[AWS CloudFormation](https://aws.amazon.com/cloudformation/)の拡張である[AWS Serverless Application Model (AWS SAM)](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)を使うと、上述したリソース確保と設定のステップをひとつのAWS SAMテンプレートファイルにまとめることができます。
AWS SAMを初めて使う方は、[こちらのチュートリアル](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-quick-start.html)をお勧めします。

基本ステップは、
1. [記述](#aws-samテンプレートを記述する)
2. [ビルド](#aws-samでサーバレスアプリケーションをビルドする)
3. [パッケージ](#aws-samでサーバレスアプリケーションをパッケージする)
4. [デプロイ](#aws-samでサーバレスアプリケーションをデプロイする)

### AWS SAMテンプレートを記述する

サーバレスアプリケーションのAWS SAMテンプレートとソースコードは`sam`ディレクトリにあります。

- `sam`
    - [`template.yaml`](sam/template.yaml): AWS SAMテンプレート
    - `src`
        - [`lambda_function_4.py`](sam/src/lambda_function_4.py): Lambdaハンドラ(前の例と一緒)
        - [`requirements.txt`](sam/src/requirements.txt): 依存関係

[`sam/template.yaml`](sam/template.yaml)はサーバレスアプリケーションを記述するAWS SAMテンプレートです。
我々のサーバレスアプリケーションは特に依存関係がないので[`sam/src/requirements.txt`](sam/src/requirements.txt)は空のテキストです。

以降のセクションは、`sam`ディレクトリで作業することを想定していますので、そちらに移動しましょう。

```bash
cd sam
```

### Dockerサービスを起動する

AWS SAMで作業をする前に、Dockerサービスを起動するのを忘れないようにしましょう。
そうしないと`sam build --use-container`コマンドを実行した際に、以下のようなエラーに出くわします。

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

このエラーメッセージは直感的ではありませんでしたが、実のところDockerサービスが走っていないということでした。
私のケースでは、[Docker Desktop](https://www.docker.com/products/docker-desktop)をインストールして解決しました。

### AWS SAMでサーバレスアプリケーションをビルドする

[`sam build`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-build.html)コマンドを実行します。

```bash
sam build --use-container
```

この例では、このコマンドは必要なさそうです。
依存関係がないからです。

#### リージョンを指定する

`sam build`コマンドを実行した時、リージョンが指定されていないとの文句を言われました。
`--region`オプションを指定して、解決しました。

```bash
sam build --region ap-northeast-1 --use-container
```

### AWS SAMでサーバレスアプリケーションをパッケージする

[`sam package`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-package.html)コマンドを実行する。

```bash
sam package --template-file template.yaml --output-template-file packaged.yaml --s3-bucket artifacts-bucket
```

**注意:** `artifacts-bucket`を生成物を保存するバケット名に置き換えてください。

#### プロフィールを指定する

`sam package`コマンドはS3バケットにアクセスする必要があるので、十分な権限を持ったクリデンシャルを与えなければなりません。
デフォルト以外のクリデンシャルを使いたい場合は、`sam package --help`には出てきませんが`--profile`オプションを指定することができます。

```bash
sam package --profile your-profile --template-file template.yaml --output-template-file packaged.yaml --s3-bucket artifacts-bucket
```

### AWS SAMでサーバレスアプリケーションをデプロイする

[`sam deploy`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-deploy.html)コマンドを実行します。

```
sam deploy --template-file packaged.yaml --stack-name comprehend-s3 --capabilities CAPABILITY_IAM
```

これで、`comprehend-s3`と名付けられた新しいスタックがCloudFormationコンソール上に現れます。

### AWS SAMテンプレート内の循環参照を回避する

Lambda関数がS3バケットにアクセスする権限を必要とするのと同時にS3バケットはLambda関数に通知する権限を必要とするため、以下の循環参照が発生します.

Lambda関数 &rightarrow; S3バケット &rightarrow; Lambda関数 &rightarrow; ...

AWS SAMテンプレート内に循環参照があると、`sam deploy`コマンドは以下のようなエラーで失敗します。

```
Failed to create the changeset: Waiter ChangeSetCreateComplete failed: Waiter encountered a terminal failure state Status: FAILED. Reason: Circular dependency between resources: [ComprehendS3FunctionTextUploadPermission, ComprehendS3FunctionRole, ComprehendS3Function, ComprehendS3Bucket]
```

[こちらの記事](https://aws.amazon.com/premiumsupport/knowledge-center/unable-validate-circular-dependency-cloudformation/)はどうやって循環参照を回避するかを解説しています。
我々のサーバレスアプリケーションに適用するには試行錯誤が必要でした。

#### S3バケットをARNで直接参照する

AWS SAMテンプレート内の循環参照を断ち切るのに、[上で紹介した記事](https://aws.amazon.com/premiumsupport/knowledge-center/unable-validate-circular-dependency-cloudformation/)はS3バケットをロジカルIDではなく絶対的なARNで参照することを提案しています。
これはS3バケットの名前を事前に知る必要があるということです。
CloudFormationはデフォルトでS3バケットにユニークな名前を生成しますが、この挙動を抑えるためにS3バケットの名前を指定しなければなりません。

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

#### Lambda関数の`Events`プロパティを使う

私は最初、S3バケットの`NotificationConfiguration`プロパティを直接追加しようとしていました。
しかし`NotificationConfiguration`をS3バケットに追加するだけでは十分でなく、`AWS::Lambda::Permission`リソースも定義しなければならないことに気づきました。
これはちょっと面倒臭いなあと感じました。

しかしもっといい方法があります。
`AWS::Serveless::Function`リソースには`Events`プロパティがあり、トリガーされるイベントをそこに記述することができます。

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

Lambda関数の`Events`プロパティを設定した場合、`NotificationConfiguration`プロパティをS3バケットに指定する必要はありません。

**注意:** イベントの`Bucket`プロパティが受け付けるのはS3バケットのロジカルIDのみです。
私は最初、S3バケットのARNを`Bucket`プロパティに指定しており、エラーになりました。

### AWS SAMテンプレートのバリデーション

**注意:** これは特に重要な内容ではありません。

[`sam validate`](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-validate.html)というコマンドがあります。

```bash
sam validate --template template.yaml
```

`sam validate`を実行した時、以下のような奇妙なエラーに出くわしました。

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

[こちらで](https://github.com/awslabs/aws-sam-cli/issues/442#issuecomment-417489857)示唆されている通り、`AWS_DEFAULT_REGION`環境変数にリージョンを指定したら解決しました。

```bash
export AWS_DEFAULT_REGION=ap-northeast-1
```
