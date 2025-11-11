"""
Provedores específicos de autenticação e tokens
"""

import json
import urllib.parse
import logging
from typing import Dict, Optional
from .interfaces import IAuthenticator, ITokenProvider, IHttpClient
from .models import AuthenticationResult
from .exceptions import SeniorAuthError, SeniorLoginError
from .http_client import RequestsHttpClient


class SeniorPlatformAuthenticator(IAuthenticator):
    """
    Autenticador para plataforma Senior
    """

    # Constantes
    BASE_URL = "https://platform.senior.com.br"
    LOGIN_URL = f"{BASE_URL}/auth/LoginServlet"
    DEFAULT_REDIRECT_URL = (
        f"{BASE_URL}/senior-x/#/Gest%C3%A3o%20de%20Pessoas%20%7C%20HCM/1/"
        "res:%2F%2Fsenior.com.br%2Fmenu%2Frh%2Fponto%2Fgestaoponto%2Fgestor?"
        "category=frame&link=https:%2F%2Fwebp20.seniorcloud.com.br:31531%2F"
        "gestaoponto-frontend%2Fissues%2Fredirect%3Factiveview%3Dmanager%26portal%3Dg7"
        "&withCredentials=true&helpUrl=http:%2F%2Fdocumentacao.senior.com.br%2F"
        "gestao-de-pessoas-hcm%2F6.10.4%2F%23gestao-ponto%2Fnova-interface%2F"
        "apuracao-do-ponto%2Fgestor-rh%2Facertos-da-minha-equipe.htm&r=1"
    )

    def __init__(self, http_client: Optional[IHttpClient] = None):
        """
        Inicializa autenticador Senior

        Args:
            http_client (IHttpClient, optional): Cliente HTTP personalizado
        """
        self.http_client = http_client or RequestsHttpClient()
        self.logger = logging.getLogger(__name__)

    def authenticate(self, username: str, password: str, **kwargs) -> AuthenticationResult:
        """
        Realiza autenticação na plataforma Senior

        Args:
            username (str): Email do usuário
            password (str): Senha do usuário
            **kwargs: redirect_to (opcional)

        Returns:
            AuthenticationResult: Resultado da autenticação
        """
        if not username or not password:
            raise SeniorLoginError("Username e password são obrigatórios")

        redirect_to = kwargs.get('redirect_to', self.DEFAULT_REDIRECT_URL)

        try:
            # Preparar requisição
            headers = self._build_headers(redirect_to)
            form_data = self._build_form_data(username, password, redirect_to)

            self.logger.info(f"Autenticando usuário: {username}")

            # Realizar requisição
            response = self.http_client.post(
                self.LOGIN_URL,
                headers=headers,
                data=form_data,
                allow_redirects=False
            )

            # Processar resposta
            result = self._process_response(response)

            self.logger.info(f"Autenticação {'bem-sucedida' if result.success else 'falhou'}")
            return result

        except Exception as e:
            if not isinstance(e, SeniorAuthError):
                error_msg = f"Erro inesperado durante autenticação: {str(e)}"
                self.logger.error(error_msg)
                raise SeniorAuthError(error_msg)
            raise

    def _build_headers(self, redirect_to: str) -> Dict[str, str]:
        """Constrói headers para requisição"""
        return {
            'Host': 'platform.senior.com.br',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': self.BASE_URL,
            'Connection': 'keep-alive',
            'Referer': f"{self.BASE_URL}/login/?redirectTo={redirect_to}",
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }

    def _build_form_data(self, username: str, password: str, redirect_to: str) -> Dict[str, str]:
        """Constrói dados do formulário"""
        return {
            'redirectTo': redirect_to,
            'lng': '',
            'emailSuffix': '',
            'expirationRememberMe': '',
            'scope': '',
            'user': username,
            'password': password,
            'g-recaptcha-response': ''
        }

    def _process_response(self, response) -> AuthenticationResult:
        """Processa resposta da autenticação"""
        cookies = self._extract_cookies(response)
        success = self._is_login_successful(response, cookies)

        return AuthenticationResult(
            success=success,
            cookies=cookies,
            senior_token=cookies.get('com.senior.token'),
            status_code=response.status_code,
            redirect_location=response.headers.get('Location'),
            response_headers=dict(response.headers),
            error_message=None if success else self._extract_error_message(response)
        )

    def _extract_cookies(self, response) -> Dict[str, str]:
        """Extrai cookies da resposta"""
        cookies = {}

        # Cookies do objeto response
        for cookie in response.cookies:
            cookies[cookie.name] = cookie.value

        # Cookies do header Set-Cookie
        set_cookie_headers = response.headers.get('Set-Cookie', '').split(',')
        for header in set_cookie_headers:
            if '=' in header:
                cookie_part = header.split(';')[0].strip()
                if '=' in cookie_part:
                    name, value = cookie_part.split('=', 1)
                    cookies[name.strip()] = value.strip()

        return cookies

    def _is_login_successful(self, response, cookies: Dict[str, str]) -> bool:
        """Verifica sucesso do login"""
        # Presença do token Senior
        if 'com.senior.token' in cookies and cookies['com.senior.token']:
            return True

        # Status de redirecionamento válido
        redirect_codes = [301, 302, 303, 307, 308]
        if (response.status_code in redirect_codes and
            'Location' in response.headers and
            not self._has_error_indicators(response)):
            return True

        return False

    def _has_error_indicators(self, response) -> bool:
        """Verifica indicadores de erro"""
        if not response.text:
            return False

        error_indicators = [
            'erro', 'error', 'inválid', 'incorrect', 'failed',
            'senha incorreta', 'usuário não encontrado', 'login failed'
        ]

        response_text = response.text.lower()
        return any(indicator in response_text for indicator in error_indicators)

    def _extract_error_message(self, response) -> str:
        """Extrai mensagem de erro"""
        if response.status_code == 401:
            return "Credenciais inválidas"
        elif response.status_code == 403:
            return "Acesso negado"
        elif response.status_code >= 500:
            return "Erro interno do servidor Senior"
        elif self._has_error_indicators(response):
            return "Falha na autenticação - verifique suas credenciais"

        return f"Erro HTTP {response.status_code}"

    def close(self):
        """Fecha recursos"""
        if self.http_client:
            self.http_client.close()


class GestaopontoTokenProvider(ITokenProvider):
    """
    Provedor de token para API de Gestão de Ponto
    """

    BASE_URL = "https://webp20.seniorcloud.com.br:31531"
    AUTH_ENDPOINT = f"{BASE_URL}/gestaoponto-backend/api/senior/auth/g7"

    def __init__(self, http_client: Optional[IHttpClient] = None):
        """
        Inicializa provedor de token

        Args:
            http_client (IHttpClient, optional): Cliente HTTP personalizado
        """
        self.http_client = http_client or RequestsHttpClient()
        self.logger = logging.getLogger(__name__)

    def get_token(self, auth_result: AuthenticationResult, **kwargs) -> Optional[str]:
        """
        Obtém token da API de Gestão de Ponto

        Args:
            auth_result (AuthenticationResult): Resultado da autenticação Senior
            **kwargs: Parâmetros adicionais

        Returns:
            str or None: Token obtido ou None se erro
        """
        if not auth_result.success or not auth_result.has_senior_token:
            raise SeniorAuthError("Resultado de autenticação inválido")

        # Extrair access token
        token_info = auth_result.get_token_info()
        if not token_info or 'tokens' not in token_info:
            raise SeniorAuthError("Não foi possível extrair access token")

        access_token = token_info['tokens']['access_token']
        if not access_token:
            raise SeniorAuthError("Access token não encontrado")

        try:
            # Preparar requisição
            headers = self._build_headers(access_token)

            self.logger.info("Obtendo token da API de Gestão de Ponto...")

            # Fazer requisição
            response = self.http_client.post(
                self.AUTH_ENDPOINT,
                headers=headers,
                json={}
            )

            # Extrair token da resposta
            return self._extract_token_from_response(response)

        except Exception as e:
            if not isinstance(e, SeniorAuthError):
                error_msg = f"Erro ao obter token de Gestão de Ponto: {str(e)}"
                self.logger.error(error_msg)
                raise SeniorAuthError(error_msg)
            raise

    def _build_headers(self, access_token: str) -> Dict[str, str]:
        """Constrói headers para requisição"""
        return {
            'Host': 'webp20.seniorcloud.com.br:31531',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'token': access_token,
            'expires': '604800',
            'Origin': 'https://webp20.seniorcloud.com.br:31531',
            'Connection': 'keep-alive',
            'Referer': 'https://webp20.seniorcloud.com.br:31531/gestaoponto-frontend/login-portal',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

    def _extract_token_from_response(self, response) -> Optional[str]:
        """Extrai token da resposta"""
        self.logger.info(f"Status da resposta: {response.status_code}")

        if response.status_code != 200:
            self.logger.error(f"Erro na API: {response.status_code}")
            return None

        try:
            # Tentar parsear JSON
            response_data = response.json()

            # String direta (token)
            if isinstance(response_data, str):
                return response_data

            # Objeto com possíveis campos de token
            if isinstance(response_data, dict):
                token_fields = ['token', 'access_token', 'authToken', 'jwt', 'bearer']

                for field in token_fields:
                    if field in response_data and response_data[field]:
                        return response_data[field]

                # Primeiro valor string encontrado
                for key, value in response_data.items():
                    if isinstance(value, str) and len(value) > 10:
                        self.logger.info(f"Token encontrado no campo '{key}'")
                        return value

            return None

        except json.JSONDecodeError:
            # Resposta como texto puro
            if response.text and len(response.text.strip()) > 10:
                return response.text.strip()

            return None

    def close(self):
        """Fecha recursos"""
        if self.http_client:
            self.http_client.close()
