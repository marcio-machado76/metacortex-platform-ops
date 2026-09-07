# O que só se sabe abrindo o fake-shop

Commit lido: `a3fa74fcadea2f163dd785313b119d4c8e03ecea`. Nada abaixo está no
manifesto de ninguém — tudo sai do projeto, e é por isso que estas regras do
padrão viram **instrução** e não script.

## Porta

`src/entrypoint.sh`:

```bash
#!/bin/bash
python -m flask db upgrade
python -m gunicorn --bind 0.0.0.0:5000 index:app
```

`containerPort: 5000`. E a primeira linha é a migração de banco rodando no start,
antes de o gunicorn começar a escutar.

## Endpoints — a decisão da regra 2.2

`src/index.py` registra estas rotas: `/`, `/shop`, `/contact`, `/checkout`,
`/cart`, `/detail/<id>`, `/add_to_cart/<id>`, `/update_quantity/<id>`,
`/remove_item/<id>`, `/order_confirmation/<n>`.

**Não existe `/health` nem `/ready`.** Mas existe uma quarta coisa que o enunciado
não menciona e que muda a resposta:

```python
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
metrics = GunicornPrometheusMetrics(app)
metrics.register_endpoint('/metrics')
```

`/metrics` é servido pela aplicação e **não toca o banco**. E a raiz toca:

```python
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)
```

Isso resolve a regra 2.2 sem inventar endpoint:

| Probe | Alvo | Por quê |
|---|---|---|
| `livenessProbe` | `/metrics` | responde "o processo está servindo HTTP" sem depender do banco |
| `readinessProbe` | `/` | responde "posso receber tráfego", e para esta aplicação isso inclui o banco: sem ele a página não renderiza |

É exatamente a separação que a 2.2 cobra. Apontar a liveness para `/` seria o
erro que a própria regra descreve: banco lento derruba a liveness, o container
reinicia, e reinício não conserta banco.

**Custo aceito:** a readiness em `/` executa `Product.query.all()` a cada
checagem. Numa loja com catálogo grande isso pesa. A alternativa — readiness
também em `/metrics` — sai mais barata e deixa de detectar perda de banco, que é
justamente o que readiness existe para detectar. Fica `/`, com `periodSeconds`
folgado.

## O que a aplicação escreve em disco — a colisão com a regra 3.2

`GunicornPrometheusMetrics` exige `PROMETHEUS_MULTIPROC_DIR` apontando para um
diretório **gravável**: cada worker do gunicorn escreve ali os arquivos de
métrica que depois são agregados.

A regra 3.2 exige `readOnlyRootFilesystem: true`. As duas só convivem com um
`emptyDir` montado no caminho. O gunicorn também usa `/tmp` para arquivos
temporários de worker, então o ponto de montagem precisa cobrir os dois.

Sem ler o projeto, ninguém descobre isso a partir do YAML — o manifesto sobe, o
pod entra, e a aplicação falha ao escrever a primeira métrica.

## Variáveis de ambiente

`src/index.py` monta a URL de conexão a partir de cinco variáveis, cada uma com
default embutido no código:

```python
db_host     = os.getenv('DB_HOST', 'localhost')
db_user     = os.getenv('DB_USER', 'ecommerce')
db_password = os.getenv('DB_PASSWORD', 'Pg1234')
db_name     = os.getenv('DB_NAME', 'ecommerce')
db_port     = os.getenv('DB_PORT', 5432)
```

Os nomes exatos são `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT` —
diferentes dos do kube-news (`DB_USERNAME`, `DB_DATABASE`). Errar o nome não gera
erro de manifesto: a aplicação cai no default e tenta `localhost`.

`DB_PASSWORD` é o valor que a regra 3.3 proíbe no manifesto: entra por
`secretKeyRef`.

## Achado sobre o projeto, fora do escopo do manifesto

`app.secret_key = 'supersecretkey'` está fixo no código. Nenhuma regra do padrão
alcança isso — o padrão governa manifesto, não código — mas quem empacota o
fake-shop precisa saber que a chave de sessão é pública no repositório.

## A migração no start, e o que o padrão não diz

`flask db upgrade` roda no entrypoint, antes do gunicorn. Com a regra 2.3
exigindo duas réplicas em prod, **duas migrações partem ao mesmo tempo**.

O padrão não tem vocabulário para isso — não há regra sobre inicialização com
dependência, nem sobre carga com estado. A decisão e as alternativas descartadas
estão em `../DECISOES.md`.
