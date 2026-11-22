class Registro:
    __slots__ = ("chave", "valor")

    def __init__(self, chave, valor):
        self.chave = chave
        self.valor = valor


class Pagina:
    """Página da Árvore B: registros ordenados e (se não for folha) len(registros)+1 filhos."""

    def __init__(self, id):
        self.id = id
        self.registros = []
        self.filhos = []

    @property
    def folha(self):
        return not self.filhos


class ArvoreB:
    """Árvore B em memória. `ordem` = número máximo de chaves por página.

    Inserção: desce até a folha; se a página estoura (ordem + 1 chaves) ela é
    dividida e a chave do meio sobe para o pai. Se a raiz dividir, a árvore
    cresce em altura. As operações guardam métricas (páginas visitadas,
    comparações, divisões) para instrumentação.
    """

    def __init__(self, ordem=4):
        if ordem < 2:
            raise ValueError("A ordem deve ser pelo menos 2.")
        self.ordem = ordem
        self.raiz = None
        self.tamanho = 0
        self.divisoes = 0
        self._proximoId = 1
        self.ultimaBusca = {"chave": None, "encontrado": False, "paginas": 0,
                            "comparacoes": 0, "caminho": []}
        self.ultimaInsercao = {"chave": None, "paginas": 0, "comparacoes": 0,
                               "divisoes": 0, "raizDividiu": False}

    # ------------------------------------------------------------ utilidades
    def _novaPagina(self):
        pagina = Pagina(self._proximoId)
        self._proximoId += 1
        return pagina

    @staticmethod
    def _posicao(pagina, chave):
        """Busca sequencial dentro da página.
        Retorna (posição, achou, comparações)."""
        i = 0
        comparacoes = 0
        while i < len(pagina.registros):
            comparacoes += 1
            atual = pagina.registros[i].chave
            if chave == atual:
                return i, True, comparacoes
            if chave < atual:
                break
            i += 1
        return i, False, comparacoes

    # ----------------------------------------------------------------- busca
    def _localizar(self, chave):
        """Retorna (registro | None, caminho de páginas, comparações)."""
        pagina = self.raiz
        caminho = []
        comparacoes = 0
        while pagina is not None:
            i, achou, c = self._posicao(pagina, chave)
            comparacoes += c
            caminho.append({"pagina": pagina.id, "nivel": len(caminho),
                            "chaves": [r.chave for r in pagina.registros]})
            if achou:
                return pagina.registros[i], caminho, comparacoes
            pagina = None if pagina.folha else pagina.filhos[i]
        return None, caminho, comparacoes

    def buscar(self, chave, registrar=True):
        """Retorna o valor associado à chave ou None."""
        registro, caminho, comparacoes = self._localizar(chave)
        if registrar:
            self.ultimaBusca = {"chave": chave, "encontrado": registro is not None,
                                "paginas": len(caminho), "comparacoes": comparacoes,
                                "caminho": caminho}
        return registro.valor if registro else None

    def custoBusca(self, chave):
        """Busca sem alterar `ultimaBusca`; devolve (valor, páginas, comparações)."""
        registro, caminho, comparacoes = self._localizar(chave)
        return (registro.valor if registro else None), len(caminho), comparacoes

    def atualizar(self, chave, valor):
        """Substitui o valor de uma chave existente (a chave não muda)."""
        registro, _, _ = self._localizar(chave)
        if registro is None:
            return False
        registro.valor = valor
        return True

    # -------------------------------------------------------------- inserção
    def inserir(self, chave, valor):
        """Insere o registro. Retorna False (sem alterar nada) se a chave já existir."""
        operacao = {"chave": chave, "paginas": 0, "comparacoes": 0,
                    "divisoes": 0, "raizDividiu": False}
        registro = Registro(chave, valor)

        if self.raiz is None:
            self.raiz = self._novaPagina()
            self.raiz.registros.append(registro)
            self.tamanho = 1
            operacao["paginas"] = 1
            self.ultimaInsercao = operacao
            return True

        inseriu, promovido = self._inserir(self.raiz, registro, operacao)
        if not inseriu:
            return False
        if promovido is not None:  # a raiz dividiu: nova raiz, árvore cresce em altura
            subiu, nova = promovido
            novaRaiz = self._novaPagina()
            novaRaiz.registros = [subiu]
            novaRaiz.filhos = [self.raiz, nova]
            self.raiz = novaRaiz
            operacao["raizDividiu"] = True
        self.tamanho += 1
        self.ultimaInsercao = operacao
        return True

    def _inserir(self, pagina, registro, operacao):
        i, achou, c = self._posicao(pagina, registro.chave)
        operacao["comparacoes"] += c
        operacao["paginas"] += 1
        if achou:
            return False, None

        if pagina.folha:
            pagina.registros.insert(i, registro)
        else:
            inseriu, promovido = self._inserir(pagina.filhos[i], registro, operacao)
            if not inseriu:
                return False, None
            if promovido is not None:
                subiu, nova = promovido
                pagina.registros.insert(i, subiu)
                pagina.filhos.insert(i + 1, nova)

        if len(pagina.registros) > self.ordem:  # overflow
            return True, self._dividir(pagina, operacao)
        return True, None

    def _dividir(self, pagina, operacao):
        meio = len(pagina.registros) // 2
        nova = self._novaPagina()
        subiu = pagina.registros[meio]
        nova.registros = pagina.registros[meio + 1:]
        pagina.registros = pagina.registros[:meio]
        if pagina.filhos:
            nova.filhos = pagina.filhos[meio + 1:]
            pagina.filhos = pagina.filhos[:meio + 1]
        self.divisoes += 1
        operacao["divisoes"] += 1
        return subiu, nova

    # ------------------------------------------------------------ percursos
    def emOrdem(self):
        """Gera os registros em ordem crescente de chave."""
        yield from self._emOrdem(self.raiz)

    def _emOrdem(self, pagina):
        if pagina is None:
            return
        for i, registro in enumerate(pagina.registros):
            if pagina.filhos:
                yield from self._emOrdem(pagina.filhos[i])
            yield registro
        if pagina.filhos:
            yield from self._emOrdem(pagina.filhos[-1])

    def listar(self):
        return [r.valor for r in self.emOrdem()]

    def maiorChave(self):
        pagina = self.raiz
        while pagina is not None and not pagina.folha:
            pagina = pagina.filhos[-1]
        return pagina.registros[-1].chave if pagina else None

    # ------------------------------------------------------- instrumentação
    def niveis(self):
        """Lista de níveis; cada nível é uma lista de páginas {id, chaves}."""
        resultado = []
        atual = [self.raiz] if self.raiz else []
        while atual:
            resultado.append([{"id": p.id, "chaves": [r.chave for r in p.registros]} for p in atual])
            atual = [f for p in atual for f in p.filhos]
        return resultado

    def altura(self):
        return len(self.niveis())

    def estatisticas(self):
        niveis = self.niveis()
        paginas = sum(len(n) for n in niveis)
        return {
            "ordem": self.ordem,
            "altura": len(niveis),
            "paginas": paginas,
            "chaves": self.tamanho,
            "divisoes": self.divisoes,
            "ocupacao": round(100 * self.tamanho / (paginas * self.ordem), 1) if paginas else 0,
            "paginasPorNivel": [len(n) for n in niveis],
        }
