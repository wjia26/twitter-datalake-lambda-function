# twitter-sentiment-analysis-lambda function
This is an AWS Lambda function which rotates between multiple twitter key's to pull search data into an S3 bucket.
This S3 bucket will then be used as a datalake for analyzing tweets.

You must zip all objects and upload to AWS Lambda for it to work.
You must then change the lambda function reference to "test.py"

I use "EventBridge(CloudWatch Events)" to schedule a cron job to run every 3minutes.

The repository includes all dependencies which will work on the Amazon AMI build for Lambda.

More information can be found on my [website](https://iamwilliamj.com/)
