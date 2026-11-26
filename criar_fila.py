"""Cria a fila 'guias' com VisibilityTimeout=15.

Uso:
    py criar_fila.py          # só a fila guias
    py criar_fila.py --dlq    # guias + guias-dlq, com maxReceiveCount=3

Equivale ao comando da CLI:
    aws sqs create-queue --queue-name guias --attributes VisibilityTimeout=15 \
        --endpoint-url http://localhost:9324
"""
import json
import sys

from config import FILA, cliente_sqs

sqs = cliente_sqs()

url = sqs.create_queue(QueueName=FILA, Attributes={"VisibilityTimeout": "15"})["QueueUrl"]
print("fila criada:", url)

if "--dlq" in sys.argv:
    dlq_url = sqs.create_queue(QueueName=FILA + "-dlq")["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(
        QueueUrl=dlq_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    sqs.set_queue_attributes(QueueUrl=url, Attributes={
        "RedrivePolicy": json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"})})
    print("DLQ criada:", dlq_url, "(maxReceiveCount=3)")

attrs = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["All"])["Attributes"]
print("VisibilityTimeout:", attrs.get("VisibilityTimeout"))
if "RedrivePolicy" in attrs:
    print("RedrivePolicy:", attrs["RedrivePolicy"])
