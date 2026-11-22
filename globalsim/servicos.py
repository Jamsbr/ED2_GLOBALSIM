"""Regras do GlobalSIM: integra Tabela Hash, Árvore B e Grafo (igraph), sem depender do Flask."""
import random
import re

import persistencia as arquivos
from estruturas import ArvoreB, IndiceSecundario, TabelaHash, grafo

REGIOES = ["Europa", "América do Sul", "América do Norte", "Ásia", "África", "Oceania"]
TECNOLOGIAS = ["3G", "4G", "5G"]
STATUS = ["ativo", "inativo", "suspenso"]
ORDEM_ARVORE_B = 4          # máximo de chaves por página da Árvore B
LARGURA_MAPA, ALTURA_MAPA = 760, 520


class GlobalSIM:
    def __init__(self):
        self.carregar()

    # ===================================================== carga / persistência
    def carregar(self):
        # Etapa 1: Tabela Hash de países
        self.paises = TabelaHash()
        for pais in arquivos.lerJson(arquivos.ARQUIVO_PAISES):
            self.paises.inserir(pais["codigo"], pais)

        # pacotes (lista em JSON: não é uma estrutura principal)
        self.pacotes = arquivos.lerJson(arquivos.ARQUIVO_PACOTES)

        # Etapa 2: Árvore B de clientes
        self.clientes = ArvoreB(ORDEM_ARVORE_B)
        self.ordemCarga = []  # ordem de inserção: o JSON recarrega exatamente a mesma árvore
        for cliente in arquivos.lerJson(arquivos.ARQUIVO_CLIENTES):
            if self.clientes.inserir(cliente["id"], cliente):
                self.ordemCarga.append(cliente["id"])

        # Etapa 3: grafo (igraph). Só países atendidos viram vértices.
        rede = arquivos.lerJson(arquivos.ARQUIVO_REDE)
        vertices = [v for v in rede["vertices"] if self.paises.buscar(v["codigo"]) is not None]
        self.posicoes = {v["codigo"]: (v["x"], v["y"]) for v in vertices}  # só para desenhar
        conexoes = [(a["origem"], a["destino"], a["latencia"]) for a in rede["arestas"]
                    if a["origem"] in self.posicoes and a["destino"] in self.posicoes]
        self.rede = grafo.criarGrafo(list(self.posicoes), conexoes)
        for codigo, _ in self.paises.itens():  # país sem vértice entra isolado
            if codigo not in self.posicoes:
                self._novoVertice(codigo)

        # Diferencial: índices secundários (derivados dos dados; refeitos a cada carga)
        self.idxRegiao = IndiceSecundario("região")
        for codigo, pais in self.paises.itens():
            self.idxRegiao.adicionar(pais["regiao"], codigo)
        self.idxStatus = IndiceSecundario("status")
        self.idxPacote = IndiceSecundario("pacote")
        for registro in self.clientes.emOrdem():
            self._indexarCliente(registro.valor)

    def salvarPaises(self):
        arquivos.gravarJson(arquivos.ARQUIVO_PAISES, self.paises.listar())

    def salvarClientes(self):
        dados = [self.clientes.buscar(i, registrar=False) for i in self.ordemCarga]
        arquivos.gravarJson(arquivos.ARQUIVO_CLIENTES, dados)

    def salvarRede(self):
        arquivos.gravarJson(arquivos.ARQUIVO_REDE, {
            "vertices": [{"codigo": v, "x": self.posicoes[v][0], "y": self.posicoes[v][1]}
                         for v in self.codigosRede()],
            "arestas": [{"origem": o, "destino": d, "latencia": p} for o, d, p in self.conexoes()],
        })

    # ================================================================== países
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

    def buscarPais(self, codigo):
        return self.paises.buscar(codigo.upper())

    def cadastrarPais(self, pais):
        if self.paises.buscar(pais["codigo"]) is not None:
            return False
        self.paises.inserir(pais["codigo"], pais)
        self.idxRegiao.adicionar(pais["regiao"], pais["codigo"])
        self._novoVertice(pais["codigo"])
        self.salvarPaises()
        self.salvarRede()
        return True

    def alterarPais(self, codigo, novo):
        antigo = self.paises.buscar(codigo)
        if antigo is None:
            return False
        novo["codigo"] = codigo  # a chave não muda
        self.idxRegiao.remover(antigo["regiao"], codigo)
        self.paises.inserir(codigo, novo)
        self.idxRegiao.adicionar(novo["regiao"], codigo)
        self.salvarPaises()
        return True

    def removerPais(self, codigo):
        """Remove o país da Tabela Hash e da rede. Retorna (removeu, conexões removidas)."""
        antigo = self.paises.buscar(codigo)
        if antigo is None:
            return False, 0
        conexoes = self.rede.degree(codigo)
        self.paises.remover(codigo)
        self.idxRegiao.remover(antigo["regiao"], codigo)
        grafo.removerVertice(self.rede, codigo)
        self.posicoes.pop(codigo, None)
        self.salvarPaises()
        self.salvarRede()
        return True, conexoes

    # =============================================================== pacotes
    def pacote(self, codigo):
        return next((p for p in self.pacotes if str(p["codigo"]) == str(codigo)), None)

    # =============================================================== clientes
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
                itens.append(registro.valor)
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
        """True se outro cliente já tem esse e-mail/eSIM (percorre a Árvore B em ordem)."""
        return any(r.valor[campo].lower() == valor.lower() and r.chave != idAtual
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
        """Cadastra o cliente (sem eSIM/pacote; ele fica inativo até a associação).
        Retorna (cliente | None, erro | None)."""
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
        """Associa pacote e eSIM ao cliente. Em branco, o eSIM é gerado automaticamente."""
        antigo = self.cliente(id, registrar=False)
        if antigo is None:
            return None, "Cliente não encontrado."
        pacote = self.pacote(codigoPacote)
        if pacote is None:
            return None, "Pacote inexistente."
        esim = esim.strip().upper() or antigo["esim"]
        while not esim or (not antigo["esim"] and self._emUso("esim", esim)):
            esim = f"ESIM-{random.randint(10000, 99999)}"  # gera um eSIM que ninguém usa
        if not re.fullmatch(r"ESIM-\d{5}", esim):
            return None, "O eSIM deve seguir o formato ESIM-12345."
        if self._emUso("esim", esim, id):
            return None, f"O eSIM {esim} já está associado a outro cliente."
        novo = dict(antigo, esim=esim, pacote=pacote["codigo"])
        if antigo["status"] == "inativo" and not antigo["esim"]:
            novo["status"] = "ativo"  # primeira associação ativa o serviço
        self._desindexarCliente(antigo)
        self.clientes.atualizar(id, novo)
        self._indexarCliente(novo)
        self.salvarClientes()
        return novo, None

    # ==================================================== diferencial: buscas
    def buscaClientes(self, status="", pacote="", limite=50):
        """Consulta multidimensional: cada critério vem de um índice secundário (lista de IDs);
        as listas são combinadas por interseção e os registros finais são lidos na Árvore B."""
        criterios = []  # (descrição, ids, comparações no hash)
        if status:
            ids, c = self.idxStatus.buscar(status)
            criterios.append((f"status = {status}", ids, c))
        if pacote:
            ids, c = self.idxPacote.buscar(pacote)
            criterios.append((f"pacote = {pacote}", ids, c))
        if not criterios:
            return {"erro": "Escolha pelo menos um critério."}

        criterios.sort(key=lambda c: len(c[1]))  # começa pela lista menor
        resultado, comparacoes = criterios[0][1], 0
        for _, ids, _ in criterios[1:]:
            resultado, c = IndiceSecundario.intersecar(resultado, ids)
            comparacoes += c

        mostrados, paginas, compsArvore = [], 0, 0
        for id_ in resultado[:limite]:
            valor, p, c = self.clientes.custoBusca(id_)
            mostrados.append(valor)
            paginas += p
            compsArvore += c
        return {
            "erro": None, "total": len(resultado), "clientes": mostrados, "limite": limite,
            "base": self.clientes.tamanho,
            "criterios": [{"descricao": d, "candidatos": len(i), "custo": f"{c} comparação(ões) no hash"}
                          for d, i, c in criterios],
            "custo": {"intersecao": comparacoes, "paginasArvore": paginas, "comparacoesArvore": compsArvore,
                      "varredura": self.clientes.tamanho * len(criterios)},
        }

    def buscaPaises(self, regiao):
        codigos, comparacoes = self.idxRegiao.buscar(regiao)
        return {"paises": [self.paises.buscar(c) for c in codigos], "base": self.paises.tamanho,
                "comparacoes": comparacoes}

    # ================================================================== rede
    def codigosRede(self):
        return sorted(grafo.nomes(self.rede))

    def conexoes(self):
        return grafo.conexoes(self.rede)

    def _novoVertice(self, codigo):
        grafo.adicionarVertice(self.rede, codigo)
        if codigo not in self.posicoes:
            self.posicoes[codigo] = self._posicaoLivre()

    def _posicaoLivre(self):
        """Primeiro ponto da grade que não fica perto de nenhum país já desenhado."""
        for y in range(70, ALTURA_MAPA - 30, 130):
            for x in range(80, LARGURA_MAPA - 40, 110):
                if all((x - ux) ** 2 + (y - uy) ** 2 >= 90 ** 2 for ux, uy in self.posicoes.values()):
                    return (x, y)
        return (random.randint(60, LARGURA_MAPA - 60), random.randint(60, ALTURA_MAPA - 60))

    def reorganizarMapa(self):
        """Pede ao igraph um novo layout e ajusta as posições ao tamanho do mapa."""
        bruto = grafo.layout(self.rede)
        if len(bruto) < 2:
            return
        xs, ys = [c[0] for c in bruto.values()], [c[1] for c in bruto.values()]
        largura, altura = (max(xs) - min(xs)) or 1, (max(ys) - min(ys)) or 1
        self.posicoes = {v: (round(70 + (x - min(xs)) / largura * (LARGURA_MAPA - 140)),
                             round(60 + (y - min(ys)) / altura * (ALTURA_MAPA - 140)))
                         for v, (x, y) in bruto.items()}
        self.salvarRede()

    def salvarConexao(self, origem, destino, latencia):
        """Retorna a mensagem de erro, ou None se salvou."""
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
        """Executa BFS, DFS ou Dijkstra e devolve os dados para a tela de rede."""
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

    # ======================================================== consulta integrada
    def consultaIntegrada(self, idCliente, origem, destino):
        """1) Árvore B  2) Tabela Hash  3) pacote  4) vértices  5) Dijkstra  6) resultado."""
        r = {"idCliente": idCliente, "origem": origem, "destino": destino, "cliente": None, "pais": None,
             "pacote": None, "rota": None, "avisos": [], "erro": None, "instrumentacao": {}}

        r["cliente"] = self.cliente(idCliente)                                   # 1. Árvore B
        r["instrumentacao"]["arvoreB"] = dict(self.clientes.ultimaBusca)
        if r["cliente"] is None:
            r["erro"] = f"Cliente {idCliente} não encontrado na Árvore B."
            return r

        r["pais"] = self.paises.buscar(destino)                                  # 2. Tabela Hash
        r["instrumentacao"]["hash"] = dict(self.paises.ultimaBusca)
        if r["pais"] is None:
            r["erro"] = f"Cobertura indisponível: o destino \"{destino}\" não é atendido pela GlobalSIM."
            return r

        r["pacote"] = self.pacote(r["cliente"]["pacote"]) if r["cliente"]["pacote"] else None   # 3. pacote
        if r["pacote"] is None:
            r["avisos"].append("O cliente ainda não possui pacote associado.")
        if r["cliente"]["status"] != "ativo":
            r["avisos"].append(f"O eSIM do cliente está {r['cliente']['status']}.")

        if not grafo.temVertice(self.rede, origem):                              # 4. grafo
            r["erro"] = f"A origem \"{origem}\" não faz parte da rede."
            return r
        dij = grafo.dijkstra(self.rede, origem, destino)                         # 5. Dijkstra
        if dij["caminho"] is None:
            r["avisos"].append("Não existe rota entre a origem e o destino na rede atual.")
        else:
            r["rota"] = {"caminho": dij["caminho"], "nomes": [self.nomePais(c) for c in dij["caminho"]],
                         "latencia": dij["latencia"]}
        return r

    # ============================================================ visualização
    def mapaRede(self, resultado=None):
        """Dados para desenhar o grafo em SVG, destacando o resultado do algoritmo."""
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
            arestas.append({"origem": o, "destino": d, "peso": peso, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                            "mx": (x1 + x2) / 2, "my": (y1 + y2) / 2,
                            "destaque": frozenset((o, d)) in destacadas})
        return {"vertices": vertices, "arestas": arestas, "largura": LARGURA_MAPA, "altura": ALTURA_MAPA}
