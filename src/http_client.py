"""
Cliente HTTP modular e reutilizável
"""

import requests
import logging
from typing import Dict, Any, Optional
from .interfaces import IHttpClient
from .exceptions import SeniorNetworkError


class RequestsHttpClient(IHttpClient):
    """
    Implementação de cliente HTTP usando requests
    """

    def __init__(self, timeout: int = 30, verify_ssl: bool = True, max_retries: int = 3):
        """
        Inicializa cliente HTTP

        Args:
            timeout (int): Timeout para requisições
            verify_ssl (bool): Verificar certificados SSL
            max_retries (int): Número máximo de tentativas
        """
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.max_retries = max_retries
        self.session = self._create_session()
        self.logger = logging.getLogger(__name__)

    def _create_session(self) -> requests.Session:
        """Cria e configura sessão HTTP com retry"""
        session = requests.Session()

        # Configurar retry strategy
        if self.max_retries > 0:
            retry_strategy = requests.adapters.Retry(
                total=self.max_retries,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )

            adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)

        return session

    def post(self, url: str, headers: Dict[str, str], data: Any = None, **kwargs) -> requests.Response:
        """
        Realiza requisição POST

        Args:
            url (str): URL da requisição
            headers (Dict): Headers HTTP
            data (Any): Dados da requisição
            **kwargs: Parâmetros adicionais (json, timeout, etc.)

        Returns:
            requests.Response: Resposta da requisição

        Raises:
            SeniorNetworkError: Erro de rede
        """
        try:
            # Configurar parâmetros padrão
            request_kwargs = {
                'headers': headers,
                'timeout': kwargs.get('timeout', self.timeout),
                'verify': kwargs.get('verify', self.verify_ssl),
                'allow_redirects': kwargs.get('allow_redirects', False)
            }

            # Adicionar dados da requisição
            if 'json' in kwargs:
                request_kwargs['json'] = kwargs['json']
            elif data is not None:
                request_kwargs['data'] = data

            # Adicionar outros parâmetros
            for key, value in kwargs.items():
                if key not in ['timeout', 'verify', 'allow_redirects', 'json']:
                    request_kwargs[key] = value

            self.logger.debug(f"POST {url}")
            response = self.session.post(url, **request_kwargs)

            return response

        except requests.RequestException as e:
            error_msg = f"Erro de rede em POST {url}: {str(e)}"
            self.logger.error(error_msg)
            raise SeniorNetworkError(error_msg)

    def get(self, url: str, headers: Dict[str, str], **kwargs) -> requests.Response:
        """
        Realiza requisição GET

        Args:
            url (str): URL da requisição
            headers (Dict): Headers HTTP
            **kwargs: Parâmetros adicionais

        Returns:
            requests.Response: Resposta da requisição

        Raises:
            SeniorNetworkError: Erro de rede
        """
        try:
            request_kwargs = {
                'headers': headers,
                'timeout': kwargs.get('timeout', self.timeout),
                'verify': kwargs.get('verify', self.verify_ssl),
                'allow_redirects': kwargs.get('allow_redirects', True)
            }

            # Adicionar outros parâmetros
            for key, value in kwargs.items():
                if key not in ['timeout', 'verify', 'allow_redirects']:
                    request_kwargs[key] = value

            self.logger.debug(f"GET {url}")
            response = self.session.get(url, **request_kwargs)

            return response

        except requests.RequestException as e:
            error_msg = f"Erro de rede em GET {url}: {str(e)}"
            self.logger.error(error_msg)
            raise SeniorNetworkError(error_msg)

    def close(self):
        """Fecha a sessão HTTP"""
        if self.session:
            self.session.close()

    def __enter__(self):
        """Suporte para context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup automático"""
        self.close()
