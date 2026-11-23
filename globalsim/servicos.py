import json
import os
import random
import re
import itertools
import math

from estruturas import ArvoreB, IndiceSecundario, TabelaHash, grafo

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arquivos")
REGIOES = ["Europa", "América do Sul", "América do Norte", "Ásia", "África", "Oceania"]
TECNOLOGIAS = ["3G", "4G", "5G"]
STATUS = ["ativo", "inativo", "suspenso"]
ORDEM_ARVORE_B = 4
LARGURA_MAPA, ALTURA_MAPA = 1200, 1200 # dimensao do mapa da rede/grafo
DISTANCIA_MINIMA = 150 # distância mínima entre vértices no mapa da rede/grafo


def lerJson(nome):
    with open(os.path.join(PASTA, nome), "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def gravarJson(nome, dados):
    with open(os.path.join(PASTA, nome), "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2, ensure_ascii=False)


class GlobalSIM:
    def __init__(self):
        self.carregar()

    def carregar(self):
        self.paises = TabelaHash()
        for pais in lerJson("paises.json"):
            self.paises.inserir(pais["codigo"], pais)

        self.pacotes = lerJson("pacotes.json")

        self.clientes = ArvoreB(ORDEM_ARVORE_B)
        self.ordemCarga = []
        for cliente in lerJson("clientes.json"):
            if self.clientes.inserir(cliente["id"], cliente):
                self.ordemCarga.append(cliente["id"])

        rede = lerJson("rede.json")
        vertices = [v for v in rede["vertices"] if self.paises.buscar(v["codigo"]) is not None]
        self.posicoes = {v["codigo"]: (v["x"], v["y"]) for v in vertices}
        conexoes = [(a["origem"], a["destino"], a["latencia"]) for a in rede["arestas"]
                    if a["origem"] in self.posicoes and a["destino"] in self.posicoes]
        self.rede = grafo.criarGrafo(list(self.posicoes), conexoes)
        for pais in self.paises.listar():
            if pais["codigo"] not in self.posicoes:
                self._novoVertice(pais["codigo"])

        # índices secundários (diferencial): refeitos a cada carga
        self.idxRegiao = IndiceSecundario("região")
        self.idxTecnologia = IndiceSecundario("tecnologia")
        for pais in self.paises.listar():
            self._indexarPais(pais)
        self.idxStatus = IndiceSecundario("status")
        self.idxPacote = IndiceSecundario("pacote")
        for registro in self.clientes.emOrdem():
            self._indexarCliente(registro.Elemento)

    def salvarPaises(self):
        gravarJson("paises.json", self.paises.listar())

    def salvarClientes(self):
        gravarJson("clientes.json", [self.clientes.buscar(i, registrar=False) for i in self.ordemCarga])

    def salvarRede(self):
        gravarJson("rede.json", {
            "vertices": [{"codigo": v, "x": self.posicoes[v][0], "y": self.posicoes[v][1]}
                         for v in self.codigosRede()],
            "arestas": [{"origem": o, "destino": d, "latencia": p} for o, d, p in self.conexoes()],
        })

    @staticmethod
    def lerPais(form):
        pais = {c: form.get(c, "").strip() for c in ["codigo", "pais", "regiao", "operadora", "tecnologia"]}
        pais["codigo"] = pais["codigo"].upper()
        return pais

    @staticmethod
    def validarPais(pais):
        if not all(pais.values()):
            return "Preencha todos os campos."
        if len(pais["codigo"]) != 2 or not pais["codigo"].isalpha():
            return "O código deve ter 2 letras."
        return None

    def _indexarPais(self, pais):
        self.idxRegiao.adicionar(pais["regiao"], pais["codigo"])
        self.idxTecnologia.adicionar(pais["tecnologia"], pais["codigo"])

    def _desindexarPais(self, pais):
        self.idxRegiao.remover(pais["regiao"], pais["codigo"])
        self.idxTecnologia.remover(pais["tecnologia"], pais["codigo"])

    def buscarPais(self, codigo):
        return self.paises.buscar(codigo.upper())

    def cadastrarPais(self, pais):
        if self.paises.buscar(pais["codigo"]) is not None:
            return False
        self.paises.inserir(pais["codigo"], pais)
        self._indexarPais(pais)
        self._novoVertice(pais["codigo"])
        self.salvarPaises()
        self.salvarRede()
        return True

    def alterarPais(self, codigo, novo):
        antigo = self.paises.buscar(codigo)
        if antigo is None:
            return False
        novo["codigo"] = codigo  # a chave não muda
        self._desindexarPais(antigo)
        self.paises.inserir(codigo, novo)
        self._indexarPais(novo)
        self.salvarPaises()
        return True

    def removerPais(self, codigo):
        antigo = self.paises.buscar(codigo)
        if antigo is None:
            return False, 0
        conexoes = self.rede.degree(codigo)
        self.paises.remover(codigo)
        self._desindexarPais(antigo)
        grafo.removerVertice(self.rede, codigo)
        self.posicoes.pop(codigo, None)
        self.salvarPaises()
        self.salvarRede()
        return True, conexoes

    def buscaPaises(self, regiao="", tecnologia=""):
        criterios = []
        if regiao:
            criterios.append((f"região = {regiao}",) + self.idxRegiao.buscar(regiao))
        if tecnologia:
            criterios.append((f"tecnologia = {tecnologia}",) + self.idxTecnologia.buscar(tecnologia))
        codigos, comparacoes = self._combinar(criterios)
        return {"paises": [self.paises.buscar(c) for c in codigos], "base": self.paises.tamanho,
                "criterios": [{"descricao": d, "candidatos": len(i), "custo": c} for d, i, c in criterios],
                "intersecao": comparacoes, "varredura": self.paises.tamanho * len(criterios)}

    def pacote(self, codigo):
        return next((p for p in self.pacotes if str(p["codigo"]) == str(codigo)), None)

    def cliente(self, id, registrar=True):
        return self.clientes.buscar(id, registrar=registrar)

    def proximoId(self):
        return (self.clientes.maiorChave() or 0) + 1

    def listarClientes(self, pagina=1, porPagina=25):
        inicio = (pagina - 1) * porPagina
        itens = []
        for posicao, registro in enumerate(self.clientes.emOrdem()):
            if posicao >= inicio + porPagina:
                break
            if posicao >= inicio:
                itens.append(registro.Elemento)
        return itens

    def _indexarCliente(self, c):
        self.idxStatus.adicionar(c["status"], c["id"])
        if c.get("pacote"):
            self.idxPacote.adicionar(c["pacote"], c["id"])

    def _desindexarCliente(self, c):
        self.idxStatus.remover(c["status"], c["id"])
        if c.get("pacote"):
            self.idxPacote.remover(c["pacote"], c["id"])

    def _emUso(self, campo, valor, idAtual=None):
        return any(r.Elemento[campo].lower() == valor.lower() and r.Chave != idAtual
                   for r in self.clientes.emOrdem())

    def validarDadosCliente(self, nome, email, status, idAtual=None):
        if not nome.strip():
            return "Informe o nome do cliente."
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
            return "Informe um e-mail válido."
        if self._emUso("email", email.strip(), idAtual):
            return "Este e-mail já está cadastrado para outro cliente."
        if status not in STATUS:
            return "Status inválido."
        return None

    def cadastrarCliente(self, id, nome, email):
        erro = self.validarDadosCliente(nome, email, "inativo")
        if erro:
            return None, erro
        cliente = {"id": id, "nome": nome.strip(), "email": email.strip(),
                   "esim": "", "pacote": None, "status": "inativo"}
        if not self.clientes.inserir(id, cliente):
            return None, f"Já existe um cliente com o ID {id}."
        self.ordemCarga.append(id)
        self._indexarCliente(cliente)
        self.salvarClientes()
        return cliente, None

    def alterarCliente(self, id, nome, email, status):
        antigo = self.cliente(id, registrar=False)
        if antigo is None:
            return None, "Cliente não encontrado."
        erro = self.validarDadosCliente(nome, email, status, idAtual=id)
        if erro:
            return None, erro
        novo = dict(antigo, nome=nome.strip(), email=email.strip(), status=status)
        self._desindexarCliente(antigo)
        self.clientes.atualizar(id, novo)
        self._indexarCliente(novo)
        self.salvarClientes()
        return novo, None

    def associarEsimPacote(self, id, codigoPacote, esim=""):
        antigo = self.cliente(id, registrar=False)
        if antigo is None:
            return None, "Cliente não encontrado."
        pacote = self.pacote(codigoPacote)
        if pacote is None:
            return None, "Pacote inexistente."
        esim = esim.strip().upper() or antigo["esim"]
        while not esim or (not antigo["esim"] and self._emUso("esim", esim)):
            esim = f"ESIM-{random.randint(10000, 99999)}"
        if not re.fullmatch(r"ESIM-\d{5}", esim):
            return None, "O eSIM deve seguir o formato ESIM-12345."
        if self._emUso("esim", esim, id):
            return None, f"O eSIM {esim} já está associado a outro cliente."
        novo = dict(antigo, esim=esim, pacote=pacote["codigo"])
        if antigo["status"] == "inativo" and not antigo["esim"]:
            novo["status"] = "ativo"
        self._desindexarCliente(antigo)
        self.clientes.atualizar(id, novo)
        self._indexarCliente(novo)
        self.salvarClientes()
        return novo, None

    def buscaClientes(self, status="", pacote="", limite=50):
        criterios = []
        if status:
            criterios.append((f"status = {status}",) + self.idxStatus.buscar(status))
        if pacote:
            criterios.append((f"pacote = {pacote}",) + self.idxPacote.buscar(pacote))
        ids, comparacoes = self._combinar(criterios)

        mostrados, paginas, compsArvore = [], 0, 0
        for id_ in ids[:limite]:
            valor, p, c = self.clientes.custoBusca(id_)
            mostrados.append(valor)
            paginas += p
            compsArvore += c
        return {
            "total": len(ids), "clientes": mostrados, "limite": limite, "base": self.clientes.tamanho,
            "criterios": [{"descricao": d, "candidatos": len(i), "custo": f"{c} comparação(ões) no hash"}
                          for d, i, c in criterios],
            "custo": {"intersecao": comparacoes, "paginasArvore": paginas, "comparacoesArvore": compsArvore,
                      "varredura": self.clientes.tamanho * len(criterios)},
        }

    @staticmethod
    def _combinar(criterios):
        criterios = sorted(criterios, key=lambda c: len(c[1]))
        resultado, comparacoes = criterios[0][1], 0
        for _, ids, _ in criterios[1:]:
            resultado, c = IndiceSecundario.intersecar(resultado, ids)
            comparacoes += c
        return resultado, comparacoes

    def codigosRede(self):
        return sorted(grafo.nomes(self.rede))

    def conexoes(self):
        return grafo.conexoes(self.rede)

    def _novoVertice(self, codigo):
        grafo.adicionarVertice(self.rede, codigo)
        if codigo not in self.posicoes:
            self.posicoes[codigo] = self._posicaoLivre()

    def _posicaoLivre(self):
        for y in range(70, ALTURA_MAPA - 30, 130):
            for x in range(80, LARGURA_MAPA - 40, 110):
                if all((x - ux) ** 2 + (y - uy) ** 2 >= 90 ** 2 for ux, uy in self.posicoes.values()):
                    return (x, y)
        return (random.randint(60, LARGURA_MAPA - 60), random.randint(60, ALTURA_MAPA - 60))

    def reorganizarMapa(self):
        bruto = grafo.layout(self.rede)
        if len(bruto) < 2:
            return
        xs, ys = [c[0] for c in bruto.values()], [c[1] for c in bruto.values()]
        largura, altura = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
        self.posicoes = {v: (round(70 + (x - min(xs)) / largura * (LARGURA_MAPA - 140)),
                            round(60 + (y - min(ys)) / altura * (ALTURA_MAPA - 140)))
                        for v, (x, y) in bruto.items()}
        self._afastarVertices()
        self.salvarRede()

    def _afastarVertices(self):
        p = {v: list(c) for v, c in self.posicoes.items()}
        for _ in range(300):
            for a, b in itertools.combinations(p, 2):
                dx, dy = p[b][0] - p[a][0], p[b][1] - p[a][1]
                d = math.hypot(dx, dy) or 1
                if d < DISTANCIA_MINIMA:
                    f = (DISTANCIA_MINIMA - d) / 2 / d
                    p[a][0] -= dx * f; p[a][1] -= dy * f
                    p[b][0] += dx * f; p[b][1] += dy * f
            for c in p.values():
                c[0] = min(LARGURA_MAPA - 70, max(70, c[0]))
                c[1] = min(ALTURA_MAPA - 70, max(60, c[1]))
        self.posicoes = {v: (round(x), round(y)) for v, (x, y) in p.items()}

    def salvarConexao(self, origem, destino, latencia):
        try:
            grafo.salvarConexao(self.rede, origem, destino, latencia)
        except ValueError as erro:
            return str(erro)
        self.salvarRede()
        return None

    def removerConexao(self, origem, destino):
        if grafo.removerConexao(self.rede, origem, destino):
            self.salvarRede()
            return True
        return False

    def nomePais(self, codigo):
        pais = self.paises.buscar(codigo)
        return pais["pais"] if pais else codigo

    def executarAlgoritmo(self, algoritmo, origem, destino=""):
        if not grafo.temVertice(self.rede, origem):
            return {"erro": "Escolha um país de origem válido."}
        if algoritmo in ("bfs", "dfs"):
            r = grafo.bfs(self.rede, origem) if algoritmo == "bfs" else grafo.dfs(self.rede, origem)
            detalhe = r["nivel"] if algoritmo == "bfs" else r["profundidade"]
            return {"algoritmo": algoritmo, "origem": origem, "ordem": r["ordem"], "detalhe": detalhe,
                    "arestas": [(r["pai"][v], v) for v in r["ordem"] if r["pai"][v]],
                    "naoAlcancados": [v for v in self.codigosRede() if v not in detalhe]}
        if algoritmo == "dijkstra":
            if not grafo.temVertice(self.rede, destino):
                return {"erro": "Para o Dijkstra, escolha também o país de destino."}
            r = grafo.dijkstra(self.rede, origem, destino)
            caminho = r["caminho"] or []
            return {"algoritmo": "dijkstra", "origem": origem, "destino": destino, "caminho": caminho,
                    "latencia": r["latencia"], "distancias": r["distancias"],
                    "arestas": list(zip(caminho, caminho[1:])), "ordem": caminho}
        return {"erro": "Algoritmo desconhecido."}

    def consultaIntegrada(self, idCliente, origem, destino):
        r = {"idCliente": idCliente, "origem": origem, "destino": destino, "cliente": None, "pais": None,
             "pacote": None, "rota": None, "avisos": [], "erro": None, "instrumentacao": {}}

        r["cliente"] = self.cliente(idCliente)  # 1. Árvore B
        r["instrumentacao"]["arvoreB"] = dict(self.clientes.ultimaBusca)
        if r["cliente"] is None:
            r["erro"] = f"Cliente {idCliente} não encontrado na Árvore B."
            return r

        r["pais"] = self.paises.buscar(destino)  # 2. Tabela Hash
        r["instrumentacao"]["hash"] = dict(self.paises.ultimaBusca)
        if r["pais"] is None:
            r["erro"] = f"Cobertura indisponível: o destino \"{destino}\" não é atendido pela GlobalSIM."
            return r

        r["pacote"] = self.pacote(r["cliente"]["pacote"]) if r["cliente"]["pacote"] else None  # 3. pacote
        if r["pacote"] is None:
            r["avisos"].append("O cliente ainda não possui pacote associado.")
        if r["cliente"]["status"] != "ativo":
            r["avisos"].append(f"O eSIM do cliente está {r['cliente']['status']}.")

        if not grafo.temVertice(self.rede, origem):  # 4. origem e destino no grafo
            r["erro"] = f"A origem \"{origem}\" não faz parte da rede."
            return r
        dij = grafo.dijkstra(self.rede, origem, destino)  # 5. Dijkstra
        if dij["caminho"] is None:
            r["avisos"].append("Não existe rota entre a origem e o destino na rede atual.")
        else:
            r["rota"] = {"caminho": dij["caminho"], "nomes": [self.nomePais(c) for c in dij["caminho"]],
                         "latencia": dij["latencia"]}
        return r

    def mapaRede(self, resultado=None):
        resultado = resultado if resultado and not resultado.get("erro") else None
        destacadas = {frozenset(par) for par in (resultado["arestas"] if resultado else [])}
        ordem = {v: i + 1 for i, v in enumerate(resultado["ordem"])} if resultado else {}
        vertices = []
        for v in self.codigosRede():
            x, y = self.posicoes[v]
            vertices.append({"codigo": v, "nome": self.nomePais(v), "x": x, "y": y,
                             "ordem": ordem.get(v), "origem": bool(resultado) and v == resultado["origem"],
                             "destino": bool(resultado) and v == resultado.get("destino"),
                             "ativo": v in ordem})
        arestas = []
        for o, d, peso in self.conexoes():
            (x1, y1), (x2, y2) = self.posicoes[o], self.posicoes[d]
            t = 0.58 if y2 >= y1 else 0.42  # rótulo longe do nome do vértice de cima
            arestas.append({"origem": o, "destino": d, "peso": peso, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "mx": x1 + t * (x2 - x1), "my": y1 + t * (y2 - y1),
                            "destaque": frozenset((o, d)) in destacadas})
        return {"vertices": vertices, "arestas": arestas, "largura": LARGURA_MAPA, "altura": ALTURA_MAPA}
