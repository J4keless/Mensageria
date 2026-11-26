import json
import os
import time

from config import FILA, cliente_sqs

sqs = cliente_sqs()
url = sqs.get_queue_url(QueueName=FILA)["QueueUrl"]


def agora():
    return time.strftime("%H:%M:%S")


def processar(pedido):
    if "requisicaoId" not in pedido:
        raise ValueError("mensagem sem requisicaoId")
    print(agora(), os.getpid(), "guia G-" + pedido["requisicaoId"], pedido.get("hospital"), flush=True)


print(agora(), "consumidor", os.getpid(), "ouvindo a fila", url, flush=True)

while True:
    resp = sqs.receive_message(
        QueueUrl=url, MaxNumberOfMessages=10, WaitTimeSeconds=10,
        MessageSystemAttributeNames=["ApproximateReceiveCount"])
    for m in resp.get("Messages", []):
        try:
            processar(json.loads(m["Body"]))
            # só apaga depois de processar com sucesso (confirmação)
            sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
        except Exception as e:
            # não apaga: a mensagem volta para a fila quando o visibility timeout vencer
            print(agora(), os.getpid(), "falhou; volta para a fila:", e, m.get("Attributes"), flush=True)
