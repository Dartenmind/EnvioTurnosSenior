"""
Módulo principal de autenticação Senior - Ponto de entrada unificado

Este módulo fornece uma interface simples e modular para autenticação
na plataforma Senior e obtenção de tokens para diferentes serviços.

Exemplo de uso:
    from src.auth import SeniorAuth

    # Fluxo completo de autenticação
    auth = SeniorAuth()
    tokens = auth.authenticate_complete("usuario@empresa.com", "senha")

    if tokens['success']:
        senior_token = tokens['senior_token']
        gestaoponto_token = tokens['gestaoponto_token']
"""

import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass
from .interfaces import IAuthenticator, ITokenProvider, ITokenDecoder
from .providers import SeniorPlatformAuthenticator, GestaopontoTokenProvider
from .token_decoder import SeniorTokenDecoder
from .http_client import RequestsHttpClient
from .models import AuthenticationResult
from .exceptions import SeniorAuthError


@dataclass
class AuthenticationFlow:
    """Configuração de um fluxo de autenticação"""
    name: str
    authenticator: IAuthenticator
    token_providers: List[ITokenProvider]
    description: str


class SeniorAuth:
    """
    Classe principal para autenticação Senior - Facade Pattern

    Esta classe orquestra todo o processo de autenticação, seguindo
    os princípios SOLID e oferecendo uma interface simples para uso.
    """

    def __init__(self,
                 timeout: int = 30,
                 verify_ssl: bool = True,
                 max_retries: int = 3):
        """
        Inicializa o sistema de autenticação Senior

        Args:
            timeout (int): Timeout para requisições HTTP
            verify_ssl (bool): Verificar certificados SSL
            max_retries (int): Número máximo de tentativas em caso de falha
        """
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

        # Configurar componentes
        self._setup_components()
        self._setup_flows()

    def _setup_components(self):
        """Configura componentes básicos"""
        # Cliente HTTP compartilhado
        self.http_client = RequestsHttpClient(
            timeout=self.timeout,
            verify_ssl=self.verify_ssl,
            max_retries=self.max_retries
        )

        # Decodificador de token
        self.token_decoder = SeniorTokenDecoder()

        # Autenticador principal
        self.senior_authenticator = SeniorPlatformAuthenticator(self.http_client)

        # Provedores de token
        self.gestaoponto_provider = GestaopontoTokenProvider(self.http_client)

    def _setup_flows(self):
        """Configura fluxos de autenticação disponíveis"""
        self.flows = {
            'senior_only': AuthenticationFlow(
                name='senior_only',
                authenticator=self.senior_authenticator,
                token_providers=[],
                description='Apenas autenticação na plataforma Senior'
            ),
            'complete': AuthenticationFlow(
                name='complete',
                authenticator=self.senior_authenticator,
                token_providers=[self.gestaoponto_provider],
                description='Autenticação completa: Senior + Gestão de Ponto'
            )
        }

    def authenticate(self, username: str, password: str, **kwargs) -> AuthenticationResult:
        """
        Realiza apenas autenticação na plataforma Senior

        Args:
            username (str): Email do usuário
            password (str): Senha do usuário
            **kwargs: Parâmetros adicionais (redirect_to, etc.)

        Returns:
            AuthenticationResult: Resultado da autenticação Senior

        Raises:
            SeniorAuthError: Erro durante autenticação
        """
        try:
            self.logger.info(f"Iniciando autenticação para usuário: {username}")

            result = self.senior_authenticator.authenticate(username, password, **kwargs)

            if result.success:
                self.logger.info("Autenticação Senior concluída com sucesso")
            else:
                self.logger.warning(f"Falha na autenticação: {result.error_message}")

            return result

        except Exception as e:
            self.logger.error(f"Erro durante autenticação: {str(e)}")
            raise

    def get_gestaoponto_token(self, auth_result: AuthenticationResult) -> Optional[str]:
        """
        Obtém token da API de Gestão de Ponto usando resultado de autenticação Senior

        Args:
            auth_result (AuthenticationResult): Resultado da autenticação Senior

        Returns:
            str or None: Token da Gestão de Ponto ou None se erro

        Raises:
            SeniorAuthError: Erro durante obtenção do token
        """
        try:
            self.logger.info("Obtendo token da Gestão de Ponto")

            token = self.gestaoponto_provider.get_token(auth_result)

            if token:
                self.logger.info("Token da Gestão de Ponto obtido com sucesso")
            else:
                self.logger.warning("Falha ao obter token da Gestão de Ponto")

            return token

        except Exception as e:
            self.logger.error(f"Erro ao obter token da Gestão de Ponto: {str(e)}")
            raise

    def authenticate_complete(self, username: str, password: str, **kwargs) -> Dict[str, Any]:
        """
        Realiza autenticação completa: Senior + Gestão de Ponto

        Args:
            username (str): Email do usuário
            password (str): Senha do usuário
            **kwargs: Parâmetros adicionais

        Returns:
            Dict: Resultado completo com todos os tokens

        Example:
            {
                'success': True,
                'senior_token': 'token_senior_aqui',
                'gestaoponto_token': 'token_gestaoponto_aqui',
                'decoded_senior_token': {...},
                'user_info': {...},
                'error': None
            }
        """
        result = {
            'success': False,
            'senior_token': None,
            'gestaoponto_token': None,
            'decoded_senior_token': None,
            'user_info': None,
            'error': None
        }

        try:
            self.logger.info(f"Iniciando autenticação completa para: {username}")

            # Etapa 1: Autenticação Senior
            senior_result = self.authenticate(username, password, **kwargs)

            if not senior_result.success:
                result['error'] = senior_result.error_message
                return result

            # Adicionar dados do Senior
            result['senior_token'] = senior_result.senior_token
            result['decoded_senior_token'] = senior_result.get_decoded_token()
            result['user_info'] = senior_result.get_token_info()

            # Etapa 2: Token da Gestão de Ponto
            try:
                gestaoponto_token = self.get_gestaoponto_token(senior_result)
                result['gestaoponto_token'] = gestaoponto_token

                # Marcar como sucesso se pelo menos o Senior funcionou
                result['success'] = True

                if gestaoponto_token:
                    self.logger.info("Autenticação completa realizada com sucesso")
                else:
                    self.logger.warning("Autenticação Senior OK, mas falha no token Gestão de Ponto")

            except Exception as e:
                # Senior OK, mas Gestão de Ponto falhou
                result['success'] = True  # Senior funcionou
                result['error'] = f"Erro no token Gestão de Ponto: {str(e)}"
                self.logger.warning(f"Falha parcial: {result['error']}")

            return result

        except Exception as e:
            error_msg = f"Erro durante autenticação completa: {str(e)}"
            self.logger.error(error_msg)
            result['error'] = error_msg
            return result

    def execute_flow(self, flow_name: str, username: str, password: str, **kwargs) -> Dict[str, Any]:
        """
        Executa um fluxo de autenticação específico

        Args:
            flow_name (str): Nome do fluxo ('senior_only', 'complete')
            username (str): Email do usuário
            password (str): Senha do usuário
            **kwargs: Parâmetros adicionais

        Returns:
            Dict: Resultado do fluxo executado

        Raises:
            SeniorAuthError: Fluxo não encontrado ou erro durante execução
        """
        if flow_name not in self.flows:
            available_flows = list(self.flows.keys())
            raise SeniorAuthError(f"Fluxo '{flow_name}' não encontrado. Disponíveis: {available_flows}")

        flow = self.flows[flow_name]
        self.logger.info(f"Executando fluxo '{flow_name}': {flow.description}")

        if flow_name == 'senior_only':
            # Apenas autenticação Senior
            senior_result = self.authenticate(username, password, **kwargs)
            return {
                'success': senior_result.success,
                'senior_token': senior_result.senior_token,
                'decoded_senior_token': senior_result.get_decoded_token(),
                'user_info': senior_result.get_token_info(),
                'error': senior_result.error_message
            }

        elif flow_name == 'complete':
            # Fluxo completo
            return self.authenticate_complete(username, password, **kwargs)

        else:
            # Fluxo customizado (implementação futura)
            raise SeniorAuthError(f"Fluxo '{flow_name}' ainda não implementado")

    def get_available_flows(self) -> Dict[str, str]:
        """
        Retorna fluxos de autenticação disponíveis

        Returns:
            Dict: Mapeamento nome -> descrição dos fluxos
        """
        return {name: flow.description for name, flow in self.flows.items()}

    def decode_token(self, encoded_token: str) -> Optional[Dict[str, Any]]:
        """
        Decodifica um token Senior

        Args:
            encoded_token (str): Token codificado

        Returns:
            Dict or None: Token decodificado ou None se erro
        """
        return self.token_decoder.decode_token(encoded_token)

    def get_token_info(self, encoded_token: str) -> Dict[str, Any]:
        """
        Obtém informações estruturadas de um token

        Args:
            encoded_token (str): Token codificado

        Returns:
            Dict: Informações estruturadas do token
        """
        decoded = self.decode_token(encoded_token)
        if decoded:
            return self.token_decoder.get_token_info(decoded)
        return {}

    def close(self):
        """Fecha todos os recursos"""
        try:
            if hasattr(self, 'senior_authenticator'):
                self.senior_authenticator.close()
            if hasattr(self, 'gestaoponto_provider'):
                self.gestaoponto_provider.close()
            if hasattr(self, 'http_client'):
                self.http_client.close()
        except Exception as e:
            self.logger.warning(f"Erro ao fechar recursos: {str(e)}")

    def __enter__(self):
        """Suporte para context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup automático"""
        self.close()


# Funções de conveniência para uso simples
def authenticate_senior(username: str, password: str, **kwargs) -> AuthenticationResult:
    """
    Função de conveniência para autenticação apenas na plataforma Senior

    Args:
        username (str): Email do usuário
        password (str): Senha do usuário
        **kwargs: Parâmetros adicionais

    Returns:
        AuthenticationResult: Resultado da autenticação
    """
    with SeniorAuth() as auth:
        return auth.authenticate(username, password, **kwargs)


def authenticate_complete(username: str, password: str, **kwargs) -> Dict[str, Any]:
    """
    Função de conveniência para autenticação completa

    Args:
        username (str): Email do usuário
        password (str): Senha do usuário
        **kwargs: Parâmetros adicionais

    Returns:
        Dict: Resultado completo com todos os tokens
    """
    with SeniorAuth() as auth:
        return auth.authenticate_complete(username, password, **kwargs)


def get_gestaoponto_token(senior_token: str) -> Optional[str]:
    """
    Função de conveniência para obter token da Gestão de Ponto

    Args:
        senior_token (str): Token Senior já obtido

    Returns:
        str or None: Token da Gestão de Ponto
    """
    # Criar um AuthenticationResult mock com o token fornecido
    from .token_decoder import SeniorTokenDecoder

    # Decodificar token para verificar validade
    decoded = SeniorTokenDecoder.decode_token(senior_token)
    if not decoded:
        raise SeniorAuthError("Token Senior inválido fornecido")

    # Criar resultado mock
    mock_result = AuthenticationResult(
        success=True,
        cookies={'com.senior.token': senior_token},
        senior_token=senior_token
    )

    with SeniorAuth() as auth:
        return auth.get_gestaoponto_token(mock_result)
