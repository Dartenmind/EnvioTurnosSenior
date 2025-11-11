"""
Módulo de autenticação para plataforma Senior

Este módulo fornece funcionalidades para autenticação na plataforma Senior,
incluindo captura de tokens e gerenciamento de sessão.

Exemplo de uso básico:
    from src.auth import SeniorAuth

    # Autenticação completa
    with SeniorAuth() as auth:
        result = auth.authenticate_complete("usuario@empresa.com", "senha123")

        if result['success']:
            print(f"Token Senior: {result['senior_token']}")
            print(f"Token Gestão Ponto: {result['gestaoponto_token']}")

Exemplo de uso com funções de conveniência:
    from src.auth import authenticate_complete

    result = authenticate_complete("usuario@empresa.com", "senha123")
    if result['success']:
        print("Autenticação realizada com sucesso!")
"""

# Importações principais (nova arquitetura)
from .auth import SeniorAuth, authenticate_senior, authenticate_complete, get_gestaoponto_token

# Importações para uso avançado e modular
from .token_decoder import SeniorTokenDecoder
from .providers import SeniorPlatformAuthenticator, GestaopontoTokenProvider
from .http_client import RequestsHttpClient

# Modelos e exceções
from .models import AuthenticationResult
from .exceptions import SeniorAuthError, SeniorLoginError, SeniorNetworkError, SeniorTokenNotFoundError

# Interfaces (para extensibilidade)
from .interfaces import IAuthenticator, ITokenProvider, ITokenDecoder, IHttpClient

__version__ = "1.0.0"
__author__ = "Senior Auth Module"

__all__ = [
    # API Principal (recomendada)
    "SeniorAuth",
    "authenticate_senior",
    "authenticate_complete",
    "get_gestaoponto_token",

    # Classes e modelos
    "AuthenticationResult",
    "SeniorTokenDecoder",


    # Componentes modulares (uso avançado)
    "SeniorPlatformAuthenticator",
    "GestaopontoTokenProvider",
    "RequestsHttpClient",

    # Interfaces (extensibilidade)
    "IAuthenticator",
    "ITokenProvider",
    "ITokenDecoder",
    "IHttpClient",

    # Exceções
    "SeniorAuthError",
    "SeniorLoginError",
    "SeniorNetworkError",
    "SeniorTokenNotFoundError"
]
