import os
import boto3

# Caminho A (ElasticMQ local): ENDPOINT_URL padrão aponta para localhost:9324.
# Caminho B (SQS de verdade): defina ENDPOINT_URL="" e use as credenciais do `aws configure`.
ENDPOINT_URL = os.environ.get("ENDPOINT_URL", "http://localhost:9324")
REGIAO = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
FILA = os.environ.get("FILA", "guias")


def cliente_sqs():
    if ENDPOINT_URL:
        return boto3.client(
            "sqs", endpoint_url=ENDPOINT_URL, region_name=REGIAO,
            aws_access_key_id="x", aws_secret_access_key="x")
    return boto3.client("sqs", region_name=REGIAO)
