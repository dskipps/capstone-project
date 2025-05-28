import boto3
import json

secret_name = "prod/capstone/mysql-cZILKj"
region_name = "us-west-1"

client = boto3.client("secretsmanager", region_name=region_name)

try:
    response = client.get_secret_value(SecretId=secret_name)
    secret = json.loads(response["SecretString"])
    print("Secret found:", secret)
except Exception as e:
    print("Error retrieving secret:", e)
