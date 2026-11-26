import json

from config import FILA, cliente_sqs

sqs = cliente_sqs()
url = sqs.get_queue_url(QueueName=FILA)["QueueUrl"]

for i in range(1, 21):
    pedido = {"requisicaoId": f"R-{i:03d}", "hospital": "H-Recife"}
    sqs.send_message(QueueUrl=url, MessageBody=json.dumps(pedido))

# mensagem inválida: falta o requisicaoId
sqs.send_message(QueueUrl=url, MessageBody=json.dumps({"hospital": "H-Recife"}))
print("21 mensagens enviadas")
