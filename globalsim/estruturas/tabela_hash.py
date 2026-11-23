class TabelaHash:
    def __init__(self, capacidade=11):
        self.capacidade = self._proximoPrimo(capacidade - 1)
        self.posicoes = [None] * self.capacidade
        self.tamanho = 0
        self.redimensionamentos = 0
        self.ultimaBusca = {"indice": None, "comparacoes": 0}

    def _hash(self, chave):
        # chave alfanumérica -> número (bytes da chave) e depois chave MOD N
        return int.from_bytes(chave.encode("utf-8"), "big") % self.capacidade

    @staticmethod
    def _proximoPrimo(n):
        """Menor número primo maior que n."""
        n += 1
        while n < 2 or any(n % d == 0 for d in range(2, int(n ** 0.5) + 1)):
            n += 1
        return n

    def inserir(self, chave, valor):
        """Insere o registro. Se a chave já existir, substitui o valor e retorna False;
        retorna True quando a chave é nova."""
        base = self._hash(chave)
        if self.posicoes[base] is None:
            self.posicoes[base] = [chave, valor, None]
            self.tamanho += 1
            return True

        i = base
        while True:  # analisa a lista de busca procurando duplicata e o fim da cadeia
            if self.posicoes[i][0] == chave:
                self.posicoes[i][1] = valor
                return False
            if self.posicoes[i][2] is None:
                break
            i = self.posicoes[i][2]

        livre = next((j for j in range(self.capacidade - 1, -1, -1)
                      if self.posicoes[j] is None), None)
        if livre is None:  # tabela cheia: aumenta para o próximo primo e tenta de novo
            self._redimensionar()
            return self.inserir(chave, valor)

        self.posicoes[livre] = [chave, valor, None]
        self.posicoes[i][2] = livre
        self.tamanho += 1
        return True

    def buscar(self, chave):
        """Retorna o valor ou None. Guarda endereço de base e comparações em ultimaBusca."""
        base = self._hash(chave)
        i = base
        comparacoes = 0
        valor = None
        while i is not None and self.posicoes[i] is not None:
            comparacoes += 1
            if self.posicoes[i][0] == chave:
                valor = self.posicoes[i][1]
                break
            i = self.posicoes[i][2]
        self.ultimaBusca = {"indice": base, "comparacoes": comparacoes}
        return valor

    def remover(self, chave):
        if self.buscar(chave) is None:
            return False
        restantes = [(p[0], p[1]) for p in self.posicoes if p and p[0] != chave]
        self._reconstruir(restantes)
        return True

    def listar(self):
        return sorted((p[1] for p in self.posicoes if p), key=lambda v: v["codigo"])

    def _reconstruir(self, itens):
        self.posicoes = [None] * self.capacidade
        self.tamanho = 0
        for chave, valor in itens:
            self.inserir(chave, valor)

    def _redimensionar(self):
        itens = [(p[0], p[1]) for p in self.posicoes if p]
        self.capacidade = self._proximoPrimo(self.capacidade * 2)
        self._reconstruir(itens)
        self.redimensionamentos += 1

    def estatisticas(self):
        apontadas = {p[2] for p in self.posicoes if p and p[2] is not None}
        maior = 0
        for i, p in enumerate(self.posicoes):
            if p and i not in apontadas:  # início de cadeia
                tamanho, j = 0, i
                while j is not None:
                    tamanho += 1
                    j = self.posicoes[j][2]
                maior = max(maior, tamanho)
        return {
            "capacidade": self.capacidade,
            "tamanho": self.tamanho,
            "fatorCarga": round(self.tamanho / self.capacidade, 2),
            "colisoes": sum(1 for i, p in enumerate(self.posicoes)
                            if p and self._hash(p[0]) != i),
            "maiorCadeia": maior,
            "redimensionamentos": self.redimensionamentos,
        }
