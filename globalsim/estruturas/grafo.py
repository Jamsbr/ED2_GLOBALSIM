import random

import igraph as ig


def criarGrafo(vertices, conexoes):
    g = ig.Graph(directed=False)
    g.add_vertices(vertices)
    g.add_edges([(o, d) for o, d, _ in conexoes])
    g.es["peso"] = [latencia for _, _, latencia in conexoes]
    return g


def nomes(g): #Devolve lista de nomes dos vértices.
    return g.vs["name"] if "name" in g.vs.attributes() else []


def temVertice(g, vertice):
    return vertice in nomes(g)


def adicionarVertice(g, vertice):
    if not temVertice(g, vertice):
        g.add_vertices([vertice])


def removerVertice(g, vertice):
    if temVertice(g, vertice):
        g.delete_vertices(vertice)


def salvarConexao(g, origem, destino, latencia):
    if origem == destino:
        raise ValueError("Uma conexão precisa ligar dois países diferentes.")
    if not (temVertice(g, origem) and temVertice(g, destino)):
        raise ValueError("Os dois países precisam existir na rede.")
    if latencia <= 0:
        raise ValueError("A latência deve ser maior que zero.")
    existente = g.get_eid(origem, destino, error=False)
    if existente >= 0:
        g.es[existente]["peso"] = latencia
    else:
        g.add_edge(origem, destino, peso=latencia)


def removerConexao(g, origem, destino):
    if not (temVertice(g, origem) and temVertice(g, destino)):
        return False
    existente = g.get_eid(origem, destino, error=False)
    if existente < 0:
        return False
    g.delete_edges(existente)
    return True


def conexoes(g): #Lista as arestas no formato (origem, destino, latencia)
    n = nomes(g)
    return sorted((*sorted((n[a.source], n[a.target])), int(a["peso"])) for a in g.es)


def bfs(g, origem): #Busca em largura.
    n = nomes(g)
    ids, inicios, pais = g.bfs(origem) # funciona com nomes
    nivel = {n[i]: k for k in range(len(inicios) - 1) for i in ids[inicios[k]:inicios[k + 1]]}
    pai = {n[i]: (n[pais[i]] if n[i] != origem else None) for i in ids}
    return {"ordem": [n[i] for i in ids], "nivel": nivel, "pai": pai}


def dfs(g, origem): #Busca em profundidade.
    n = nomes(g)
    ids, pais = g.dfs(n.index(origem)) # funciona com índices numéricos
    pai, profundidade = {}, {}
    for posicao, i in enumerate(ids):  # no dfs do igraph, `pais` segue a ordem de visita
        pai[n[i]] = None if posicao == 0 else n[pais[posicao]]
        profundidade[n[i]] = 0 if posicao == 0 else profundidade[pai[n[i]]] + 1
    return {"ordem": [n[i] for i in ids], "profundidade": profundidade, "pai": pai}


def dijkstra(g, origem, destino=None): #Menor rota.
    n = nomes(g)
    distancias = g.distances(origem, weights="peso")[0]
    resultado = {"distancias": {n[i]: (int(d) if d != float("inf") else None) for i, d in enumerate(distancias)},
                 "caminho": None, "latencia": None}
    if destino is not None and resultado["distancias"].get(destino) is not None:
        caminho = g.get_shortest_paths(origem, to=destino, weights="peso", output="vpath", algorithm="dijkstra")[0]
        resultado["caminho"] = [n[i] for i in caminho]
        resultado["latencia"] = resultado["distancias"][destino]
    return resultado

# Em vez de abrir janela preferi usar SVG no HTML.
def layout(g, semente=0):
    sorteio = random.Random(semente)
    inicial = [[sorteio.random(), sorteio.random()] for _ in nomes(g)]
    coordenadas = g.layout_fruchterman_reingold(niter=500, seed=inicial).coords
    return {nome: tuple(c) for nome, c in zip(nomes(g), coordenadas)}
