"""Client Claude factice partagé entre les tests — évite d'avoir besoin d'une vraie
clé ANTHROPIC_API_KEY pour tester la logique applicative."""


class BlocFactice:
    def __init__(self, type_, input_=None):
        self.type = type_
        self.input = input_


class ReponseFactice:
    def __init__(self, content):
        self.content = content


class _MessagesFactices:
    def __init__(self, parent):
        self._parent = parent

    def create(self, **kwargs):
        self._parent.dernier_appel = kwargs
        if self._parent.leve is not None:
            raise self._parent.leve
        return ReponseFactice(self._parent.blocs)


class ClientFactice:
    def __init__(self, reponse_input: dict | None = None, leve: Exception | None = None):
        self.dernier_appel = None
        self.leve = leve
        self.blocs = [BlocFactice("tool_use", reponse_input)] if reponse_input is not None else []

    @property
    def messages(self):
        return _MessagesFactices(self)
