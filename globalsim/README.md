## 1 Equipe
João Moura

## 2 Como executar
pip install flask
pip install igraph

python app.py

Acesse http://127.0.0.1:5000

## 3 Estruturas Implementadas
**Tabela Hash** (própria) | países atendidos (chave = código de 2 letras) | capacidade, fator de carga, colisões, maior cadeia, redimensionamentos, posição base e comparações de cada busca

**Árvore B** (própria, ordem 4) | clientes (chave = ID único) | altura, páginas, divisões, ocupação, páginas por nível, caminho e comparações da busca/inserção

**Grafo** (python-igraph) | rede internacional (vértice = país; aresta = latência em ms) | ordem de visita e nível/profundidade (BFS/DFS); menor latência até cada país (Dijkstra)

## Diferencial: índices secundários e consultas multidimensionais
**Problema:** a Árvore B só localiza clientes pelo ID. Perguntas como "clientes ativos com o pacote Europa Plus" exigiriam varrer todos os registros.

**Solução:** cada atributo consultado tem um índice secundário (`IndiceSecundario`), montado sobre a própria Tabela Hash: valor do atributo → lista ordenada de chaves primárias.
- Clientes: status e pacote. Países: região e tecnologia.
- Os critérios escolhidos são combinados por **interseção de listas ordenadas** (começando pela menor) e os registros finais são lidos na Árvore B.
- Os índices são mantidos a cada cadastro, alteração e associação, e refeitos a partir dos dados ao iniciar.
- Os filtros das páginas **Países** e **Clientes** mostram o plano de execução e comparam as comparações feitas com as de uma varredura completa.