"""
Interfaces e contratos para o módulo de autenticação Senior
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from .models import AuthenticationResult


class IAuthenticator(ABC):
    """Interface para autenticadores"""

    @abstractmethod
    def authenticate(self, username: str, password: str, **kwargs) -> AuthenticationResult:
        """
        Realiza autenticação

        Args:
            username (str): Nome de usuário
            password (str): Senha
            **kwargs: Parâmetros adicionais específicos do autenticador

        Returns:
            AuthenticationResult: Resultado da autenticação
        """
        pass

    @abstractmethod
    def close(self):
        """Fecha recursos do autenticador"""
        pass


class ITokenProvider(ABC):
    """Interface para provedores de token"""

    @abstractmethod
    def get_token(self, auth_result: AuthenticationResult, **kwargs) -> Optional[str]:
        """
        Obtém token usando resultado de autenticação

        Args:
            auth_result (AuthenticationResult): Resultado de autenticação anterior
            **kwargs: Parâmetros adicionais específicos do provedor

        Returns:
            str or None: Token obtido ou None se falhou
        """
        pass

    @abstractmethod
    def close(self):
        """Fecha recursos do provedor"""
        pass


class ITokenDecoder(ABC):
    """Interface para decodificadores de token"""

    @abstractmethod
    def decode_token(self, encoded_token: str) -> Optional[Dict[str, Any]]:
        """
        Decodifica um token

        Args:
            encoded_token (str): Token codificado

        Returns:
            Dict or None: Token decodificado ou None se erro
        """
        pass

    @abstractmethod
    def is_token_valid(self, token_data: Dict[str, Any]) -> bool:
        """
        Verifica se token é válido

        Args:
            token_data (Dict): Dados do token decodificado

        Returns:
            bool: True se válido
        """
        pass


class IHttpClient(ABC):
    """Interface para clientes HTTP"""

    @abstractmethod
    def post(self, url: str, headers: Dict[str, str], data: Any, **kwargs) -> Any:
        """
        Realiza requisição POST

        Args:
            url (str): URL da requisição
            headers (Dict): Headers HTTP
            data (Any): Dados da requisição
            **kwargs: Parâmetros adicionais

        Returns:
            Any: Resposta da requisição
        """
        pass

    @abstractmethod
    def get(self, url: str, headers: Dict[str, str], **kwargs) -> Any:
        """
        Realiza requisição GET

        Args:
            url (str): URL da requisição
            headers (Dict): Headers HTTP
            **kwargs: Parâmetros adicionais

        Returns:
            Any: Resposta da requisição
        """
        pass

    @abstractmethod
    def close(self):
        """Fecha cliente HTTP"""
        pass
