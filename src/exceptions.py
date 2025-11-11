"""
Exceções customizadas para o módulo de autenticação Senior
"""


class SeniorAuthError(Exception):
    """Exceção base para erros de autenticação Senior"""
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class SeniorLoginError(SeniorAuthError):
    """Exceção para erros específicos de login"""
    pass


class SeniorNetworkError(SeniorAuthError):
    """Exceção para erros de rede/conexão"""
    pass


class SeniorTokenNotFoundError(SeniorAuthError):
    """Exceção quando o token não é encontrado na resposta"""
    def __init__(self, message: str = "Token com.senior.token não encontrado na resposta"):
        super().__init__(message)
