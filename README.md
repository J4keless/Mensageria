# Atividade individual 2: Mensageria

Infraestrutura de Software · ADS · CESAR School · 2026.2

Comunicação assíncrona com fila compatível com o Amazon SQS. Um produtor publica pedidos de guia de transporte do Rota Vital, consumidores retiram, processam e só então confirmam (apagam) a mensagem.

## Caminho escolhido

**Caminho A: ElasticMQ local.** O ElasticMQ implementa a API do SQS, então o mesmo código boto3 roda contra ele ou contra o SQS de verdade trocando só o endereço (`endpoint_url`). Não precisa de conta na AWS.

Também fiz o opcional da **DLQ** (fila de mensagens mortas com `maxReceiveCount=3`).

## Estrutura

| Arquivo | O que faz |
|---|---|
| `config.py` | Cria o cliente boto3. Por padrão aponta para `http://localhost:9324` (ElasticMQ). |
| `criar_fila.py` | Cria a fila `guias` com `VisibilityTimeout=15`. Com `--dlq`, cria também a `guias-dlq` e liga as duas com `maxReceiveCount=3`. |
| `produtor.py` | Publica 20 pedidos válidos (`R-001` a `R-020`) e 1 inválido (sem `requisicaoId`). |
| `consumidor.py` | Recebe em lotes de até 10 com long polling, gera a guia e só depois apaga a mensagem. Se falhar, não apaga, e a mensagem volta após o visibility timeout. Cada linha mostra hora e PID. |
| `evidencias/` | Prints e logs (`.txt`) das saídas de cada cenário. |

## Como rodar

### 1. Pré-requisitos

- Docker Desktop
- Python 3.12+ e boto3:

```bash
pip install -r requirements.txt
```

- AWS CLI v2 (opcional; o `criar_fila.py` faz a mesma coisa em Python)

### 2. Subir o ElasticMQ

Num terminal, deixar rodando:

```bash
docker run --rm -p 9324:9324 softwaremill/elasticmq-native
```

Sem Docker, dá para usar o jar oficial com Java 11+ (mesma porta 9324):

```bash
java -jar elasticmq-server-1.6.11.jar
```

(download em https://s3-eu-west-1.amazonaws.com/softwaremill-public/elasticmq-server-1.6.11.jar)

### 3. Criar a fila

Com a AWS CLI (Git Bash):

```bash
export AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=x AWS_DEFAULT_REGION=us-east-1
aws sqs create-queue --queue-name guias --attributes VisibilityTimeout=15 \
    --endpoint-url http://localhost:9324
aws sqs get-queue-attributes --queue-url http://localhost:9324/000000000000/guias \
    --attribute-names VisibilityTimeout --endpoint-url http://localhost:9324
```

Ou com Python:

```bash
python criar_fila.py
```

### 4. Cenário 1: um consumidor

```bash
# terminal 2
python consumidor.py
# terminal 3
python produtor.py
```

O consumidor gera as 20 guias e a mensagem inválida aparece como `falhou; volta para a fila` a cada ~15 s, com `ApproximateReceiveCount` subindo (1, 2, 3, ...).

### 5. Cenário 2: dois consumidores

Parar os consumidores (Ctrl+C), reiniciar o ElasticMQ (ele guarda tudo em memória, então a fila zera e a mensagem inválida da rodada anterior some) e criar a fila de novo. Depois:

```bash
# terminal 2
python consumidor.py
# terminal 3
python consumidor.py
# terminal 4
python produtor.py
```

Cada consumidor imprime o próprio PID; dá para ver quais guias cada um gerou.

### 6. Opcional: DLQ

Reiniciar o ElasticMQ e criar as filas com DLQ:

```bash
python criar_fila.py --dlq
python consumidor.py
python produtor.py
```

A mensagem inválida falha 3 vezes (receive count 1, 2 e 3). Na quarta tentativa de recebimento o ElasticMQ move ela para a `guias-dlq` e ela some da `guias`: no teste, depois da terceira falha a `guias` ficou com 0 mensagens e a `guias-dlq` com 1 (`{"hospital": "H-Recife"}`). Para conferir:

```bash
aws sqs receive-message --queue-url http://localhost:9324/000000000000/guias-dlq \
    --endpoint-url http://localhost:9324
```

### Caminho B (SQS na nuvem)

O código já está pronto para isso: basta não passar o endpoint local, e o boto3 usa as credenciais do `aws configure`.

```bash
ENDPOINT_URL= AWS_DEFAULT_REGION=us-east-1 python consumidor.py
```

## Respostas

### 1. Por que o consumidor só apaga a mensagem depois de processar?

Porque apagar é a confirmação de que o trabalho foi feito. Enquanto a mensagem não é apagada, ela só fica invisível por um tempo; se o consumidor cair no meio do processamento ou der erro, ela volta para a fila e outro consumidor tenta de novo. Se apagasse antes de processar e o processo morresse ou lançasse exceção logo depois, a mensagem já teria sumido da fila e a guia nunca seria gerada. O pedido seria perdido sem ninguém perceber.

### 2. Com dois consumidores, como as mensagens se dividiram? A ordem foi mantida?

No meu teste, um consumidor (PID 30956) gerou 11 guias (R-001, 003, 005, 007, 009, 011, 013, 015, 017, 018, 020) e o outro (PID 33020) gerou 9 (R-002, 004, 006, 008, 010, 012, 014, 016, 019). Ficou quase alternado porque os dois estavam parados no long polling quando o produtor começou a publicar: como o produtor manda uma mensagem por vez, cada mensagem que chegava era entregue a quem estava esperando, e os dois foram se revezando. Perto do fim o revezamento quebrou (R-017 e R-018 foram para o mesmo consumidor), então a divisão não é exata nem previsível. A mensagem inválida também passou pelos dois: a primeira tentativa caiu num PID, a segunda no outro e a terceira voltou para o primeiro.

A ordem global não foi mantida. Cada terminal viu só uma parte da sequência, e não há nada garantindo que G-R-002 seja gerada depois de G-R-001; os dois consumidores processam ao mesmo tempo e qualquer um pode terminar primeiro.

A documentação do SQS diz que a fila padrão faz *best-effort ordering*: ela tenta manter a ordem, mas não garante, e mensagens podem ser entregues fora da ordem em que foram enviadas. Quem precisa de ordem garantida tem que usar fila FIFO.

### 3. Entrega pelo menos uma vez: o que isso exige do consumidor?

Exige que o consumidor seja idempotente, ou seja, processar a mesma mensagem duas vezes tem que dar o mesmo resultado que processar uma vez. Isso pode acontecer, por exemplo, se o consumidor gera a guia mas demora mais que o visibility timeout para apagar, ou se cai entre gerar e apagar: a mensagem volta e outro consumidor gera a guia de novo.

Para tornar idempotente, usaria o `requisicaoId` como chave. Antes de gerar a guia, o consumidor consulta um registro (uma tabela no banco com chave única em `requisicaoId`, ou um `SET` no Redis) para saber se aquela requisição já tem guia. Se tiver, só apaga a mensagem e segue. Se não tiver, grava e gera. Com a chave única no banco, mesmo que dois consumidores tentem ao mesmo tempo, só um insere e o outro recebe erro de duplicidade e trata como "já feito". O próprio ID da guia já é derivado da requisição (`G-R-001`), então gerar de novo não cria uma guia diferente.

### 4. Visibility timeout e DLQ

Quando um consumidor recebe a mensagem, ela não sai da fila: fica invisível para os outros consumidores pelo tempo do visibility timeout (15 s aqui). Se ninguém apagar nesse prazo, ela volta a ficar visível e é entregue de novo. Foi exatamente o que aconteceu com a mensagem inválida: o consumidor lançava `ValueError`, não apagava, e uns 15 segundos depois ela aparecia de novo no log com `ApproximateReceiveCount` uma unidade maior. Sem DLQ, ela fica nesse ciclo para sempre, gastando processamento e poluindo o log.

A DLQ serve para tirar essas mensagens "envenenadas" do caminho. Depois de `maxReceiveCount` tentativas (3, na minha configuração), a fila move a mensagem para a DLQ, onde ela fica guardada para alguém analisar o que deu errado e reprocessar manualmente se for o caso. Assim a fila principal continua limpa e o erro não se perde.

### 5. Rota Vital: síncrono x assíncrono

No síncrono, o sistema do hospital chama o serviço de emissão de guia e fica esperando a resposta. Se o serviço estiver fora do ar, lento ou sobrecarregado, o hospital recebe erro ou fica travado, e a requisição de transporte pode ser perdida se ninguém tentar de novo. Os dois sistemas ficam acoplados: um depende do outro estar de pé no mesmo momento.

Com a fila, o hospital só publica o pedido e segue a vida; a resposta é rápida porque só depende da fila estar disponível. Se o emissor de guias cair, os pedidos ficam acumulados e são processados quando ele voltar. Também dá para colocar mais consumidores em horário de pico sem mexer no hospital, e uma falha num pedido não derruba os outros.

O que se perde: o hospital não recebe a guia na hora, só a confirmação de que o pedido foi aceito, então é preciso outro mecanismo para avisar quando a guia ficou pronta (notificação, evento de volta ou consulta de status). A ordem não é garantida na fila padrão, pode haver processamento duplicado (o consumidor precisa ser idempotente) e o sistema fica mais difícil de depurar, porque o fluxo não está mais numa única chamada e tem mais uma peça de infraestrutura para manter e monitorar.

## Uso de IA

<!-- preencher -->
